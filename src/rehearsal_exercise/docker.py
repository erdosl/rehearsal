"""Bounded local Docker CLI adapter with journalled intent and exact ownership checks."""

import json
import re
import subprocess
import time
from uuid import uuid4

from rehearsal_exercise.evidence import ExerciseError

LABEL_PREFIX = "org.rehearsal.exercise."


class CommandFailed(ExerciseError):
    """The CLI exited nonzero; this does not establish the daemon mutation outcome."""


def require_owner(resource, live):
    if not live or live["labels"] != resource["labels"]:
        raise ExerciseError("cleanup refused: live ownership does not match durable state")
    if resource.get("id") and resource["id"] != live["id"]:
        raise ExerciseError("cleanup refused: resource identity changed")
    if resource.get("created") and resource["created"] != live["created"]:
        raise ExerciseError("cleanup refused: resource generation changed")


def require_restore_target(source, target):
    for field in ("container", "volume", "network", "system_identifier"):
        if not source.get(field) or not target.get(field) or source[field] == target[field]:
            raise ExerciseError("source and restore identities must be distinct")


class Docker:
    def __init__(self, evidence):
        self.evidence = evidence
        # Deliberately local. Ignore remote contexts/DOCKER_HOST; never reach another host.
        self.prefix = ["docker", "--host", "unix:///var/run/docker.sock"]

    def call(
        self,
        args,
        *,
        operation="inspect",
        mutation=False,
        data=None,
        source=None,
        output=None,
        timeout=120,
        missing_ok=False,
    ):
        if mutation:
            self.evidence.event("intent", operation=operation)
        started = time.monotonic()
        try:
            with subprocess.Popen(
                self.prefix + args,
                stdin=source if source else subprocess.PIPE,
                stdout=output if output else subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as process:
                try:
                    result, diagnostic = process.communicate(data, timeout=timeout)
                except BaseException:
                    process.kill()
                    process.communicate()
                    raise
                code = process.returncode
        except subprocess.TimeoutExpired:
            self.evidence.event("command_timeout", operation=operation)
            raise ExerciseError(f"{operation}: command timed out; reconcile before retry") from None
        except OSError:
            raise ExerciseError(f"{operation}: local Docker command unavailable") from None
        self.evidence.event(
            "command_result",
            operation=operation,
            exit_code=code,
            duration_seconds=time.monotonic() - started,
        )
        if code:
            if missing_ok and re.search(
                rb"(?i)no such (object|container|image|network|volume)|network [^\r\n]+ not found",
                diagnostic,
            ):
                return None
            raise CommandFailed(f"{operation}: command failed (exit {code})")
        return result or b""

    def inspect(self, kind, identity):
        # Inspect only selected fields; never read/persist container Env or raw logs.
        labels = ".Config.Labels" if kind in ("container", "image") else ".Labels"
        id_field = ".Name" if kind == "volume" else ".Id"
        created = ".CreatedAt" if kind == "volume" else ".Created"
        if kind == "network":
            created = ".Created"
        fmt = '{"id":{{json ' + id_field + '}},"labels":{{json ' + labels + "}}"
        fmt += ',"created":{{json ' + created + "}}}"
        result = self.call([kind, "inspect", "--format", fmt, identity], missing_ok=True)
        if result is None:
            return None
        return json.loads(result)

    def plan(self, kind, role, name=None):
        resource_id = str(uuid4())
        name = name or f"rehearsal-{self.evidence.data['run']}-{role}"
        labels = {
            LABEL_PREFIX + "installation": self.evidence.data["installation"],
            LABEL_PREFIX + "run": self.evidence.data["run"],
            LABEL_PREFIX + "resource": resource_id,
            LABEL_PREFIX + "nonce": str(uuid4()),
            LABEL_PREFIX + "role": role,
        }
        resource = {"kind": kind, "role": role, "name": name, "labels": labels, "state": "planned"}
        self.evidence.data["resources"].append(resource)
        self.evidence.save()
        self.evidence.event("create_intent", resource=resource_id, kind_name=kind, name=name)
        return resource

    @staticmethod
    def label_args(resource):
        return [
            arg
            for key, value in resource["labels"].items()
            for arg in ("--label", f"{key}={value}")
        ]

    def capture(self, resource):
        live = self.inspect(resource["kind"], resource["name"])
        require_owner(resource, live)
        resource.update(id=live["id"], created=live["created"], state="created")
        self.evidence.save()
        return resource

    def create(self, kind, role, args):
        resource = self.plan(kind, role)
        if self.inspect(kind, resource["name"]) is not None:
            raise ExerciseError("resource name already exists; refusing creation or adoption")
        command = (
            [kind, "create", "--name", resource["name"]]
            if kind == "container"
            else [kind, "create"]
        )
        command += self.label_args(resource) + args
        if kind != "container":
            command += [resource["name"]]
        resource["state"] = "intent"
        self.evidence.save()
        self.call(command, operation=f"create_{role}", mutation=True)
        return self.capture(resource)

    def cleanup(self):
        pending = []
        # Containers first, then their exact volumes/networks, finally the unique app image.
        order = {"container": 0, "volume": 1, "network": 2, "image": 3}
        for resource in sorted(self.evidence.data["resources"], key=lambda r: order[r["kind"]]):
            if resource["state"] == "removed":
                continue
            if resource["state"] == "planned":
                resource["state"] = "removed"  # No mutation was submitted for this plan.
                self.evidence.save()
                self.evidence.event("unsubmitted_plan_closed", role=resource["role"])
                continue
            try:
                labels = resource["labels"]
                if (
                    labels.get(LABEL_PREFIX + "installation") != self.evidence.data["installation"]
                    or labels.get(LABEL_PREFIX + "run") != self.evidence.data["run"]
                    or labels.get(LABEL_PREFIX + "role") != resource["role"]
                    or not labels.get(LABEL_PREFIX + "resource")
                    or not labels.get(LABEL_PREFIX + "nonce")
                ):
                    raise ExerciseError(
                        "cleanup refused: resource is outside this installation/run"
                    )
                live = self.inspect(resource["kind"], resource.get("id", resource["name"]))
                if live is None:
                    by_name = self.inspect(resource["kind"], resource["name"])
                    if by_name is not None:
                        # A reused name is never deleted, even with copied ownership labels.
                        require_owner(resource, by_name)
                        live = by_name
                if live is None:
                    if resource["state"] in ("intent", "creation_failed"):
                        raise ExerciseError("creation outcome unresolved; no resource observed")
                    resource["state"] = "removed"
                    self.evidence.save()
                    continue
                require_owner(resource, live)
                resource.update(id=live["id"], created=live["created"], state="deleting")
                self.evidence.save()
                self.evidence.event("delete_intent", resource=resource["id"])
                args = [resource["kind"], "rm"]
                if resource["kind"] == "container":
                    args += ["--force"]
                self.call(args + [resource["id"]], operation="delete_owned", mutation=True)
                if self.inspect(resource["kind"], resource["id"]) is not None:
                    raise ExerciseError("owned resource remains after deletion")
                resource["state"] = "removed"
                self.evidence.save()
                self.evidence.event("delete_confirmed", resource=resource["id"])
            except ExerciseError as error:
                pending.append({"role": resource["role"], "reason": str(error)})
        self.evidence.data["cleanup"] = "pending" if pending else "complete"
        self.evidence.data["cleanup_pending"] = pending
        self.evidence.save()
        return not pending
