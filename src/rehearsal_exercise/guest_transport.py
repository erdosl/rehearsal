"""Authenticated SSH and the existing durable operation journal, without retries."""

import hashlib
import json
import os
import shlex
import stat
import subprocess
from pathlib import Path
from uuid import uuid4

from rehearsal_exercise.evidence import ExerciseError


class SSH:
    def __init__(self, guest, journal, evidence, guard):
        self.guest, self.journal, self.evidence, self.guard = guest, journal, evidence, guard
        self.owner = {
            "run": evidence.data["run"],
            "installation": evidence.data["installation"],
            "resource": guest.ownership["resource"],
        }

    def argv(self, operation, *, request=None, checksum=None):
        for name, private in ((self.guest.key_file, True), (self.guest.known_hosts, False)):
            info = Path(name).lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & (0o077 if private else 0o022)
            ):
                raise ExerciseError(
                    "SSH trust/credential reference has unsafe ownership or permissions"
                )
        alias = "rehearsal-" + self.guest.ownership["resource"]
        lines = Path(self.guest.known_hosts).read_text().splitlines()
        if len(lines) != 1 or not lines[0].startswith(alias + " ssh-ed25519 "):
            raise ExerciseError("known_hosts must pin exactly this guest resource alias")
        options = {
            "BatchMode": "yes",
            "PreferredAuthentications": "publickey",
            "StrictHostKeyChecking": "yes",
            "UpdateHostKeys": "no",
            "UserKnownHostsFile": self.guest.known_hosts,
            "GlobalKnownHostsFile": "/dev/null",
            "HostKeyAlias": alias,
            "IdentitiesOnly": "yes",
            "IdentityAgent": "none",
            "ForwardAgent": "no",
            "ClearAllForwardings": "yes",
            "ProxyCommand": "none",
            "ProxyJump": "none",
            "PermitLocalCommand": "no",
            "ControlMaster": "no",
            "ControlPath": "none",
            "ConnectTimeout": "3",
            "ConnectionAttempts": "1",
            "ServerAliveInterval": "5",
            "ServerAliveCountMax": "2",
        }
        remote = [
            "/opt/rehearsal/venv/bin/python",
            "-m",
            "rehearsal_exercise.guest_agent",
            operation,
        ]
        for key, value in self.owner.items():
            remote += ["--" + key, value]
        if request:
            remote += ["--request", request]
        if checksum:
            remote += ["--sha256", checksum]
        return [
            "ssh",
            "-T",
            "-F",
            "/dev/null",
            "-i",
            self.guest.key_file,
            *[arg for key, value in options.items() for arg in ("-o", f"{key}={value}")],
            "--",
            self.guest.ssh_user + "@" + self.guest.address,
            shlex.join(remote),
        ]

    def _execute(self, argv, data):
        # Never persist stderr or subprocess exception objects, including SSH connection details.
        with subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ) as process:
            try:
                output, _ = process.communicate(data, timeout=75)
            except BaseException:
                process.kill()
                process.communicate()
                raise
            if process.returncode or len(output) > 17 * 1024**2:
                raise ExerciseError(
                    "authenticated guest command failed; retain operation for reconciliation"
                )
            return output

    def run(self, operation, data=b"", *, mutation=False, checksum=None, validate=None):
        self.guard()
        self.journal.heartbeat()
        opid = None
        if mutation:
            opid = self.journal.intent(
                str(uuid4()),
                "SSH",
                f"/guests/{self.guest.vmid}/{operation}",
                {
                    "owner": self.owner,
                    "operation": operation,
                    "input_sha256": hashlib.sha256(data).hexdigest(),
                },
                "prepared-guest-ssh",
            )
        try:
            output = self._execute(self.argv(operation, request=opid, checksum=checksum), data)
            if validate:
                validate(output)
            if opid:
                self.journal.update(opid, "complete", result={"guest_command": "completed"})
            return output
        except BaseException as error:
            if opid:
                self.journal.update(opid, "uncertain")
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
        raise ExerciseError("guest command/receipt unavailable; no automatic retry") from None

    def reconcile(self, opid):
        """Only this exact guest's durable receipt can resolve an uncertain SSH operation."""
        operation = self.journal.operation(opid)
        desired = json.loads(operation["desired"])
        if operation["method"] != "SSH" or desired.get("owner") != self.owner:
            raise ExerciseError("operation does not belong to this guest exercise")
        self.guard()
        try:
            receipt = json.loads(self._execute(self.argv("receipt", request=opid), b""))
            if any(
                receipt.get(key) != desired[key] for key in ("owner", "operation", "input_sha256")
            ):
                raise ValueError
            if receipt["status"] not in ("complete", "failed"):
                raise ValueError
            self.journal.update(
                opid, receipt["status"], result={"source": "authenticated-guest-receipt"}
            )
        except Exception:
            raise ExerciseError(
                "matching terminal guest receipt unavailable; retain uncertainty"
            ) from None
