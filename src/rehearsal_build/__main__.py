"""Explicit supervised exercise steps, separate from the deployed inventory CLI."""

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

from rehearsal.credentials import load_token
from rehearsal.errors import RehearsalError
from rehearsal_build import TOOL_VERSION
from rehearsal_build.admission import validate_admission
from rehearsal_build.api import BuildAPI, volume_ids
from rehearsal_build.config import BuildConfig
from rehearsal_build.journal import Journal, SafetyError, public_json
from rehearsal_build.redaction import redact


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SafetyError("invalid supervised-tool arguments; values are not displayed")


def expectation(api, request):
    expected = request.get("expect", {"kind": "owned"})

    def check():
        kind = expected["kind"]
        if kind == "owned":
            result = api.owned()
            return {
                key: result[key]
                for key in ("description", "node", "vmid", "pool", "status", "template")
            }
        if kind == "absent":
            return api.deleted()
        if kind == "read":
            result = api.read(expected["path"])
            fields = expected.get("fields", {})
            if not isinstance(result, dict) or any(
                result.get(key) != value for key, value in fields.items()
            ):
                raise SafetyError("readback does not match expected fields")
            return {"readback": fields, "matched": True}
        raise SafetyError("unknown postcondition")

    return check


def attest(api, journal, request):
    resource = journal.resource()
    observed = api.owned()
    if journal.pending() or api.active_tasks():
        raise SafetyError("unresolved task blocks isolation attestation")
    evidence = request["evidence"]
    if (
        evidence.get("resource") != resource["resource"]
        or not 0 <= time.time() - evidence.get("utc_epoch", 0) < 120
    ):
        raise SafetyError("operator evidence is stale or belongs to another resource")
    state = request["state"]
    if state == "isolated":
        required = {
            "stopped",
            "nic_disconnected",
            "per_vm_policy",
            "bridge_guard",
            "controller_filter",
            "kvm",
        }
        if observed["status"] != "stopped":
            raise SafetyError("pre-boot attestation requires stopped state")
    elif state == "network-verified":
        required = {"guest_kernel_chains", "exact_guest_port", "controller_tuple", "routing_off"}
        if observed["status"] != "running":
            raise SafetyError("kernel-port attestation requires a running but disconnected VM")
    else:
        raise SafetyError("unsupported isolation transition")
    if set(evidence.get("checks", [])) != required or "link_down=1" not in observed.get("net0", ""):
        raise SafetyError("operator isolation checks are incomplete")
    options = api.read(api.vm_path + "/firewall/options")
    required_options = dict(
        enable=1,
        policy_in="DROP",
        policy_out="DROP",
        macfilter=1,
        ipfilter=1,
        dhcp=0,
        ndp=0,
        radv=0,
    )
    if any(options.get(key) != value for key, value in required_options.items()):
        raise SafetyError("guest firewall options do not match deny-by-default policy")
    journal.resource_state(state, evidence)
    return {"state": state, "attested": True}


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument("command", choices=("validate", "status", "exercise"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--exercise", choices=("first-guest",))
    parser.add_argument(
        "--operation",
        choices=(
            "reserve",
            "request",
            "operator-intent",
            "operator-result",
            "read",
            "reconcile",
            "attest",
            "record-volumes",
            "mark-stopped",
        ),
    )
    parser.add_argument("--request", type=Path)
    api = None
    try:
        args = parser.parse_args(argv)
        config = BuildConfig.load(args.config)
        if args.command == "validate":
            print(json.dumps(dict(valid=True, vmid=9000, tool_version=TOOL_VERSION)))
            return 0
        if args.command == "exercise" and not (
            args.live and args.exercise == "first-guest" and os.environ.get("REHEARSAL_LIVE") == "1"
        ):
            raise SafetyError(
                "exercise requires --live, --exercise first-guest and REHEARSAL_LIVE=1"
            )
        if (
            args.command == "status"
            and not (Path(config.state_directory) / "journal.sqlite3").is_file()
        ):
            raise SafetyError("journal has not been initialized")
        with Journal(Path(config.state_directory)) as journal:
            if args.command == "status":
                rows = [
                    dict(row) | journal.outcome_evidence(row["id"])
                    for row in journal.db.execute(
                        "SELECT id,label,status,upid FROM operations ORDER BY created"
                    )
                ]
                resource = (
                    journal.resource()
                    if journal.db.execute("SELECT 1 FROM resources").fetchone()
                    else None
                )
                print(
                    json.dumps(
                        redact(
                            dict(
                                installation=journal.installation,
                                operations=rows,
                                resource=resource,
                            )
                        )
                    )
                )
                return 0
            if not args.operation:
                raise SafetyError("select an explicit supervised operation")
            request = {}
            if args.request:
                if args.request.stat().st_size > 64 * 1024:
                    raise SafetyError("operation request exceeds size limit")
                request = json.loads(args.request.read_text())
                public_json(request)
            if args.operation == "operator-intent":
                record = journal.db.execute(
                    "SELECT resource FROM resources WHERE vmid=9000"
                ).fetchone()
                opid = journal.intent(
                    request["label"],
                    "OPERATOR",
                    request["path"],
                    request["desired"],
                    request.get("actor", "root@pam"),
                    record[0] if record else None,
                )
                result = {"operation": opid, "state": "intent"}
            elif args.operation == "operator-result":
                if request["state"] in ("complete", "failed") and not (
                    isinstance(request.get("result"), dict) and request["result"]
                ):
                    raise SafetyError(
                        "terminal operator results require explicit evidence or reason"
                    )
                journal.update(
                    request["operation"],
                    request["state"],
                    upid=request.get("upid"),
                    result=request.get("result"),
                    upid_source="operator-supplied",
                )
                result = {"operation": request["operation"], "state": request["state"]}
            else:
                token = load_token(Path(config.token_file))
                api = BuildAPI(config, journal, token)
                if args.operation == "reserve":
                    evidence = request.get("admission", {})
                    validate_admission(evidence, node=config.node, storage=config.storage)
                    if api.live() is not None or api.active_tasks():
                        raise SafetyError("VMID 9000 is not unused")
                    result = journal.reserve(
                        node=config.node, vmid=9000, pool=config.pool, config_digest=config.digest
                    )
                    journal.event("admission", evidence)
                elif args.operation == "request":
                    opid = api.mutate(
                        request["label"],
                        request["method"],
                        request["path"],
                        request.get("params", {}),
                        postcondition=expectation(api, request),
                        deadline=request.get("deadline", 600),
                    )
                    result = {
                        "operation": opid,
                        "state": "complete",
                        "upid": journal.operation(opid)["upid"],
                    }
                elif args.operation == "read":
                    result = api.sanitize(api.read(request["path"], request.get("params")))
                elif args.operation == "reconcile":
                    result = api.reconcile(
                        request["operation"],
                        postcondition=expectation(api, request),
                        expected_types=set(request["expected_types"]),
                    )
                elif args.operation == "attest":
                    result = attest(api, journal, request)
                elif args.operation == "record-volumes":
                    observed = api.owned()
                    if api.sanitize(observed) != observed:
                        raise SafetyError("secret-bearing volume evidence cannot be recorded")
                    volumes = volume_ids(observed, config.storage)
                    journal.record_volumes(journal.resource(), request["operation"], volumes)
                    result = {"recorded_volumes": sorted(volumes)}
                elif args.operation == "mark-stopped":
                    observed = api.owned()
                    if observed["status"] != "stopped" or api.active_tasks() or journal.pending():
                        raise SafetyError("owned stopped state is not reconciled")
                    journal.resource_state("stopped", {"observed": "stopped"})
                    result = {"state": "stopped"}
                else:
                    raise SafetyError("unknown supervised operation")
            if api is not None:
                result = api.sanitize(result)
            else:
                result = redact(result)
            print(json.dumps(dict(tool_version=TOOL_VERSION, simulated=False, result=result)))
            return 0
    except (
        SafetyError,
        RehearsalError,
        sqlite3.Error,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RecursionError,
    ):
        print(
            json.dumps(
                dict(
                    error="supervised_operation_failed",
                    message=(
                        "Safety, input, transport or task check failed; inspect the private "
                        "journal and reconcile before another mutation."
                    ),
                )
            ),
            file=sys.stderr,
        )
        return 2
    finally:
        if api is not None:
            api.close()


if __name__ == "__main__":
    raise SystemExit(main())
