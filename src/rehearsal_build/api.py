"""Bounded, single-attempt mutations with durable intent and explicit reconciliation."""

import json
import re
import ssl
import time
import uuid
from urllib.parse import quote, unquote, urlsplit

import httpx

from rehearsal_build.admission import validate_admission
from rehearsal_build.journal import SafetyError, require_owner
from rehearsal_build.redaction import redact


class BuildAPI:
    def __init__(
        self,
        config,
        journal,
        token,
        *,
        transport=None,
        sleeper=time.sleep,
        clock=time.monotonic,
        utc_clock=time.time,
    ):
        self.config = config
        self.journal = journal
        self.token = token
        self.simulated = transport is not None
        self.sleep = sleeper
        self.clock = clock
        self.utc_clock = utc_clock
        self.timing_context = str(uuid.uuid4())
        context = (
            ssl.create_default_context(cafile=config.ca_file)
            if transport is None
            else ssl.create_default_context()
        )
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        self.http = httpx.Client(
            base_url=config.endpoint.rstrip("/") + "/api2/json/",
            headers={"Authorization": token.authorization},
            verify=context,
            timeout=httpx.Timeout(15, connect=3, pool=3),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self):
        self.http.close()

    def _request(self, method, path, params=None, *, operation=None, request=None):
        parsed = urlsplit(path)
        if (
            not path.startswith("/")
            or path.startswith("//")
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or "\\" in unquote(path)
            or any(part in (".", "..") for part in unquote(path).split("/"))
            or not path.isascii()
            or not path.isprintable()
        ):
            raise SafetyError("API path must stay within the configured origin")
        evidence = None
        failure = None
        data = None
        outcome = {
            "outcome": "interrupted",
            "http_status": None,
            "transport_error": None,
            "returned_upid": None,
        }
        if operation is not None:
            self.journal.operation(operation)
            started = self.clock()
            evidence = {
                "schema_version": 1,
                "operation": operation,
                "request": request or str(uuid.uuid4()),
                "timing_context": self.timing_context,
                "simulated": self.simulated,
                "method": method,
                "path": self.sanitize(path),
                "started_utc_epoch": self.utc_clock(),
                "started_monotonic_seconds": started,
            }
            # This commit precedes the HTTP client call; it does not prove wire delivery.
            self.journal.event("api-request-start", evidence)
        try:
            with self.http.stream(
                method,
                "./" + path[1:],
                **({"params": params} if method == "GET" else {"data": params}),
            ) as response:
                outcome["http_status"] = response.status_code
                if response.status_code >= 300:
                    outcome["outcome"] = "http-error"
                    raise SafetyError(
                        f"bootstrap API returned HTTP {response.status_code}; reconcile"
                    )
                outcome["outcome"] = "invalid-response"
                content = bytearray()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    if len(content) + len(chunk) > 2 * 1024**2:
                        raise SafetyError("bootstrap API response exceeds size limit; reconcile")
                    content.extend(chunk)
                body = json.loads(content)
            if not isinstance(body, dict) or "data" not in body:
                raise SafetyError("invalid bootstrap API response")
            if isinstance(body["data"], str) and body["data"].startswith("UPID:"):
                outcome["returned_upid"] = self.sanitize(body["data"])
                if outcome["returned_upid"] != body["data"]:
                    raise SafetyError("secret-bearing task identity; retain for reconciliation")
            outcome["outcome"] = "response"
            data = body["data"]
        except httpx.HTTPError as error:
            outcome["outcome"] = "transport-error"
            # Exception text may contain credentials, URLs or reflected response content.
            outcome["transport_error"] = (
                "timeout" if isinstance(error, httpx.TimeoutException) else "http-transport"
            )
            failure = SafetyError(
                "bootstrap API transport/response failure; mutation outcomes require reconciliation"
            )
        except (httpx.InvalidURL, ValueError, RecursionError):
            failure = SafetyError(
                "bootstrap API transport/response failure; mutation outcomes require reconciliation"
            )
        finally:
            if evidence is not None:
                ended = self.clock()
                self.journal.event(
                    "api-request-end",
                    evidence
                    | outcome
                    | {
                        "ended_utc_epoch": self.utc_clock(),
                        "ended_monotonic_seconds": ended,
                        "elapsed_seconds": ended - started if ended >= started else None,
                    },
                )
        # Raise after leaving the handler so exceptions retain no credential-bearing context.
        if failure is not None:
            raise failure
        return data

    def read(self, path, params=None, *, operation=None, request=None):
        return self._request("GET", path, params, operation=operation, request=request)

    @property
    def vm_path(self):
        return f"/nodes/{self.config.node}/qemu/{self.config.vmid}"

    def resources(self):
        rows = self.read("/cluster/resources", {"type": "vm"})
        if not isinstance(rows, list):
            raise SafetyError("invalid resource inventory")
        return rows

    def live(self):
        row = next((row for row in self.resources() if row.get("vmid") == self.config.vmid), None)
        if row is None:
            return None
        result = dict(self.read(self.vm_path + "/config"))
        current = self.read(self.vm_path + "/status/current")
        result.update(
            node=row.get("node"),
            vmid=row.get("vmid"),
            pool=row.get("pool"),
            status=current.get("status"),
            template=result.get("template", row.get("template", 0)),
        )
        return result

    def owned(self):
        record = self.journal.resource()
        if record["config_digest"] != self.config.digest:
            raise SafetyError("configuration changed since allocation")
        observed = self.live()
        if observed is None:
            raise SafetyError("owned resource is absent; reconcile before proceeding")
        require_owner(record, observed)
        return observed

    def deleted(self):
        if self.live() is not None or self.active_tasks():
            raise SafetyError("resource deletion is not confirmed")
        rows = self.read(
            f"/nodes/{self.config.node}/storage/{self.config.storage}/content",
            {"content": "images", "vmid": self.config.vmid},
        )
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not isinstance(row.get("volid"), str) for row in rows
        ):
            raise SafetyError("volume deletion cannot be verified")
        recorded = {
            row[0]
            for row in self.journal.db.execute(
                "SELECT volume FROM volumes WHERE resource=?",
                (self.journal.resource()["resource"],),
            )
        }
        if recorded.intersection(row.get("volid") for row in rows):
            raise SafetyError("recorded volumes remain; retain cleanup evidence")
        return {"absent": True, "recorded_volumes_absent": sorted(recorded)}

    def active_tasks(self):
        rows = self.read(
            f"/nodes/{self.config.node}/tasks", {"source": "active", "vmid": self.config.vmid}
        )
        active = []
        for row in rows:
            status = self.read(
                f"/nodes/{self.config.node}/tasks/{quote(row['upid'], safe='')}/status"
            )
            if status.get("status") == "running":
                active.append(row)
            elif status.get("status") != "stopped":
                raise SafetyError("ambiguous task status blocks mutation")
        return active

    def _scope(self, method, path, params):
        if (
            any(key in params for key in ("args", "startup", "hostpci0", "usb0", "net1"))
            or params.get("onboot", 0) != 0
        ):
            raise SafetyError("unsafe device/startup change")
        if "net0" in params:
            nic = dict(part.split("=", 1) for part in params["net0"].split(","))
            if (
                set(nic) != {"virtio", "bridge", "firewall", "link_down"}
                or nic["virtio"].lower() != self.config.guest_mac
                or nic["bridge"] != self.config.bridge
                or nic["firewall"] != "1"
                or nic["link_down"] not in ("0", "1")
            ):
                raise SafetyError("NIC isolation mapping does not match configuration")
            if nic["link_down"] == "0" and self.journal.resource()["state"] != "network-verified":
                raise SafetyError("effective isolation must be verified before link release")
        if path == f"/nodes/{self.config.node}/qemu" and method == "POST":
            admission = self.journal.db.execute(
                "SELECT body FROM events WHERE kind='admission' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            validate_admission(
                json.loads(admission[0]) if admission else {},
                node=self.config.node,
                storage=self.config.storage,
            )
            if params.get("vmid") != 9000 or self.live() is not None or self.active_tasks():
                raise SafetyError("VMID is busy or has an unresolved task")
            record = self.journal.resource()
            if record["config_digest"] != self.config.digest:
                raise SafetyError("configuration changed since allocation")
            candidate = dict(params, node=record["node"], pool=params.get("pool"), template=0)
            require_owner(record, candidate)
            if params.get("kvm") != 1 or params.get("onboot") != 0 or params.get("start") != 0:
                raise SafetyError("unsafe initial startup configuration")
            if (
                params.get("cores") != self.config.cores
                or params.get("sockets") != 1
                or params.get("memory") != self.config.memory_mib
                or params.get("balloon") != 0
                or params.get("cpu") != "host"
            ):
                raise SafetyError("initial hardware allocation does not match configuration")
            if "net0" not in params or "link_down=1" not in params["net0"]:
                raise SafetyError("create the guest with its sole NIC disconnected")
            return
        allowed = {
            ("PUT", self.vm_path + "/config"),
            ("POST", self.vm_path + "/config"),
            ("PUT", self.vm_path + "/resize"),
            ("POST", self.vm_path + "/status/start"),
            ("POST", self.vm_path + "/status/shutdown"),
            ("POST", self.vm_path + "/status/stop"),
            ("DELETE", self.vm_path),
            ("PUT", self.vm_path + "/firewall/options"),
            ("POST", self.vm_path + "/firewall/rules"),
            ("POST", self.vm_path + "/firewall/ipset"),
            ("POST", self.vm_path + "/firewall/ipset/ipfilter-net0"),
            ("POST", self.vm_path + "/agent/ping"),
        }
        rule_positions = {self.vm_path + "/firewall/rules/" + str(i) for i in range(4)}
        if method == "PUT" and path in rule_positions:
            if (
                set(params) - {"moveto", "digest"}
                or type(params.get("moveto")) is not int
                or params["moveto"] not in range(4)
            ):
                raise SafetyError("only bounded policy-rule reordering is permitted")
            allowed.add((method, path))
        if (method, path) not in allowed:
            raise SafetyError("operation is outside the supervised VM 9000 contract")
        if path.endswith("/firewall/ipset") and params != {"name": "ipfilter-net0"}:
            raise SafetyError("only the owned NIC source-address set is permitted")
        if path.endswith("/firewall/ipset/ipfilter-net0") and params != {
            "cidr": self.config.guest_ip.split("/", 1)[0]
        }:
            raise SafetyError("source-address set must match the configured guest")
        observed = self.owned()
        tasks = self.active_tasks()
        if tasks:
            raise SafetyError("active task blocks another mutation")
        if path.endswith("/status/start"):
            if (
                self.journal.resource()["state"] != "isolated"
                or observed.get("status") != "stopped"
                or "link_down=1" not in observed.get("net0", "")
                or observed.get("kvm", 1) != 1
            ):
                raise SafetyError("pre-boot isolation or KVM is not established")
        if method == "DELETE":
            self.journal.check_cleanup(
                observed, tasks=tasks, volumes=volume_ids(observed, self.config.storage)
            )

    def sanitize(self, value):
        return redact(value, (self.token.authorization, self.token.secret))

    def mutate(self, label, method, path, params, *, postcondition, deadline=600):
        if not isinstance(deadline, (int, float)) or not 0 < deadline <= 600:
            raise SafetyError("invalid supervised task deadline")
        supplied = {"label": label, "method": method, "path": path, "params": params}
        if self.sanitize(supplied) != supplied:
            raise SafetyError("secret-bearing mutation input is forbidden")
        self.journal.heartbeat()
        self._scope(method, path, params)
        record = self.journal.resource()
        opid = self.journal.intent(
            label, method, path, params, self.token.token_id, record["resource"]
        )
        request = str(uuid.uuid4())
        try:
            data = self._request(method, path, params, operation=opid, request=request)
        except BaseException:
            self.journal.update(opid, "uncertain")
            raise
        if isinstance(data, str) and data.startswith("UPID:"):
            self.journal.update(
                opid, "running", upid=data, upid_source="mutation-response", request=request
            )
            self.wait(opid, deadline=deadline)
        elif (
            method == "DELETE"
            or method == "POST"
            and (path.endswith("/qemu") or path.endswith("/config") or "/status/" in path)
        ):
            self.journal.update(opid, "uncertain")
            raise SafetyError("asynchronous mutation returned no UPID; reconcile without retry")
        elif data is None or isinstance(data, (dict, list)):
            self.journal.update(opid, "running")
        else:
            self.journal.update(opid, "uncertain")
            raise SafetyError("unexpected mutation result; do not repeat")
        try:
            if self.active_tasks():
                raise SafetyError("task remains active; do not infer completion from response")
            if method == "DELETE":
                self.deleted()
            evidence = postcondition()
            if evidence is False or evidence is None:
                raise SafetyError("mutation postcondition was not established")
        except BaseException:
            self.journal.update(opid, "uncertain")
            raise
        self.journal.update(opid, "complete", result=self.sanitize(evidence))
        return opid

    def wait(self, opid, *, deadline=600):
        try:
            return self._wait(opid, deadline=deadline)
        except BaseException:
            if self.journal.operation(opid)["status"] in ("intent", "running", "uncertain"):
                self.journal.update(opid, "uncertain")
            raise

    def _validate_task(self, upid, operation, expected_types=None):
        if not isinstance(upid, str) or self.sanitize(upid) != upid:
            raise SafetyError("invalid task provenance; retain for reconciliation")
        fields = upid.split(":")
        known_types = {
            ("POST", f"/nodes/{self.config.node}/qemu"): {"qmcreate"},
            ("DELETE", self.vm_path): {"qmdestroy"},
            ("POST", self.vm_path + "/status/start"): {"qmstart"},
            ("POST", self.vm_path + "/status/shutdown"): {"qmshutdown"},
            ("POST", self.vm_path + "/status/stop"): {"qmstop"},
            ("PUT", self.vm_path + "/resize"): {"resize"},
        }.get((operation["method"], operation["path"]))
        if (
            len(fields) != 9
            or fields[0] != "UPID"
            or fields[-1] != ""
            or fields[1] != self.config.node
            or fields[6] != str(self.config.vmid)
            or fields[7] != operation["actor"]
            or any(not re.fullmatch(r"[0-9A-Fa-f]{1,16}", part) for part in fields[2:5])
            or expected_types is not None
            and fields[5] not in expected_types
            or known_types is not None
            and fields[5] not in known_types
        ):
            raise SafetyError("mismatched task provenance; retain for reconciliation")
        return upid

    def _wait(self, opid, *, deadline):
        operation = self.journal.operation(opid)
        upid = operation["upid"]
        self._validate_task(upid, operation)
        end = self.clock() + deadline
        while self.clock() < end:
            self.journal.heartbeat()
            request = str(uuid.uuid4())
            status = self.read(
                f"/nodes/{self.config.node}/tasks/{quote(upid, safe='')}/status",
                operation=opid,
                request=request,
            )
            if not isinstance(status, dict):
                raise SafetyError("invalid task status; retain for reconciliation")
            self.journal.event(
                "task-observation",
                self.sanitize(
                    {
                        "schema_version": 1,
                        "operation": opid,
                        "request": request,
                        "upid": upid,
                        "status": status.get("status"),
                        "exitstatus": status.get("exitstatus"),
                    }
                ),
            )
            if status.get("status") == "stopped":
                exitstatus = status.get("exitstatus")
                if not isinstance(exitstatus, str) or not exitstatus.strip():
                    raise SafetyError("task exit status is unavailable; retain for reconciliation")
                failed = exitstatus != "OK"
                if failed:
                    # The observed failure survives even if the separate log request fails.
                    self.journal.update(
                        opid, "failed", result={"exitstatus": "task failed; see redacted event log"}
                    )
                try:
                    log = self.read(
                        f"/nodes/{self.config.node}/tasks/{quote(upid, safe='')}/log",
                        {"limit": 1000},
                        operation=opid,
                    )
                except SafetyError:
                    if failed:
                        raise SafetyError(
                            "PVE task failed; task log unavailable; retain owned partial resources"
                        ) from None
                    raise
                safe = self.sanitize(
                    {
                        "operation": opid,
                        "upid": upid,
                        "status": status.get("exitstatus"),
                        "log": log,
                    }
                )
                self.journal.event("task-terminal", safe)
                if failed:
                    raise SafetyError(
                        "PVE task failed; reconcile owned partial resources before cleanup"
                    )
                return status
            if status.get("status") != "running":
                raise SafetyError("ambiguous task status")
            self.sleep(1)
        raise SafetyError("task deadline expired; task may still be running")

    def reconcile(self, opid, *, postcondition, expected_types):
        operation = self.journal.operation(opid)
        if operation["status"] not in ("intent", "uncertain", "running"):
            raise SafetyError("operation is already terminal")
        if not operation["upid"]:
            start, end = self.journal.mutation_evidence(opid)
            returned = end.get("returned_upid")
            if returned is not None:
                if end.get("outcome") != "response" or not 200 <= end.get("http_status", 0) < 300:
                    raise SafetyError("conflicting response provenance; retain for reconciliation")
                self._validate_task(returned, operation, expected_types)
                self.journal.update(
                    opid,
                    "running",
                    upid=returned,
                    upid_source="mutation-response",
                    request=end["request"],
                )
                operation = self.journal.operation(opid)
        if not operation["upid"]:
            lower, upper = start["started_utc_epoch"], end["ended_utc_epoch"]
            if upper < lower:
                raise SafetyError(
                    "UTC clock discontinuity blocks task discovery; operator evidence required"
                )
            request = str(uuid.uuid4())
            tasks = self.read(
                f"/nodes/{self.config.node}/tasks",
                {
                    "source": "all",
                    "vmid": self.config.vmid,
                    "since": int(lower) - 2,
                    "limit": 100,
                },
                operation=opid,
                request=request,
            )
            candidates = [
                row
                for row in tasks
                if str(row.get("id")) == str(self.config.vmid)
                and row.get("type") in expected_types
                and (
                    row.get("user") == operation["actor"]
                    or (
                        isinstance(row.get("user"), str)
                        and isinstance(row.get("tokenid"), str)
                        and row["user"] + "!" + row["tokenid"] == operation["actor"]
                    )
                )
                and lower - 2 <= row.get("starttime", 0) <= upper + 2
            ]
            if len(candidates) != 1:
                raise SafetyError("task provenance is uncertain; retain resource and do not retry")
            candidate = candidates[0]
            candidate_upid = self._validate_task(candidate["upid"], operation, expected_types)
            if int(candidate_upid.split(":")[4], 16) != candidate.get("starttime"):
                raise SafetyError("task timestamps disagree; retain uncertain provenance")
            self.journal.update(
                opid,
                "running",
                upid=candidate_upid,
                upid_source="task-listing",
                request=request,
            )
        self._validate_task(self.journal.operation(opid)["upid"], operation, expected_types)
        self.wait(opid)
        if operation["method"] == "DELETE":
            self.deleted()
        else:
            self.owned()
        evidence = postcondition()
        if evidence is False or evidence is None:
            raise SafetyError("reconciled task did not establish the intended postcondition")
        self.journal.update(opid, "complete", result=self.sanitize(evidence))
        return evidence

    def external_task(self, label, desired, actor="root@pam"):
        """Persist operator import intent BEFORE an independently executed pvesh call."""
        self.owned()
        if self.active_tasks():
            raise SafetyError("active task blocks operator import")
        return self.journal.intent(
            label,
            "OPERATOR",
            self.vm_path + "/config",
            desired,
            actor,
            self.journal.resource()["resource"],
        )


def volume_ids(config, storage):
    result = set()
    for key, value in config.items():
        if re.fullmatch(r"(?:scsi|ide|sata|virtio|unused)\d+", key) and isinstance(value, str):
            volume = value.split(",", 1)[0]
            if volume in ("none", "cdrom"):
                continue
            if not volume.startswith(storage + ":"):
                raise SafetyError("unexpected storage volume; quarantine")
            result.add(volume)
    return result
