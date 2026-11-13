"""The same recovery workflow on two prepared Proxmox guests; no VM mutations."""

import argparse
import hashlib
import json
import os
import signal
import time
from pathlib import Path
from uuid import uuid4

from rehearsal.credentials import load_token
from rehearsal_build.journal import Journal, SafetyError
from rehearsal_exercise.evidence import Evidence, ExerciseError, locked_root
from rehearsal_exercise.guest_config import GuestConfig
from rehearsal_exercise.guest_provider import PreparedAPI
from rehearsal_exercise.guest_transport import SSH
from rehearsal_exercise.runner import Runner, perform_run


class GuestRunner(Runner):
    recovery_start_boundary = (
        "before prepared restore guest readiness; guest allocation/boot excluded"
    )

    def __init__(self, evidence, project, config, journal, apis, fault="none"):
        super().__init__(evidence, project, fault)
        self.config, self.journal, self.apis = config, journal, apis
        self.ssh = {
            role: SSH(getattr(config, role), journal, evidence, lambda role=role: self.guard(role))
            for role in ("source", "restore")
        }
        self.claimed = {
            r["role"]
            for r in evidence.data["resources"]
            if r.get("kind") == "prepared-guest"
            and r.get("state") != "retained_guest_services_stopped"
        }

    def guard(self, role):
        try:
            live = self.apis[role].owned()
            if live["status"] != "running":
                raise SafetyError("prepared guest is not running")
        except SafetyError:
            raise ExerciseError(
                "prepared guest admission failed; retain resources and journal"
            ) from None

    def probe(self, role):
        try:
            value = json.loads(self.ssh[role].run("probe"))
            if not isinstance(value, dict):
                raise ValueError
        except (ValueError, TypeError):
            raise ExerciseError(
                "authenticated guest identity/readiness response is invalid"
            ) from None
        guest = getattr(self.config, role)
        if (
            value.get("machine_id") != guest.machine_id
            or value.get("release_sha256") != guest.release_sha256
            or value.get("app_target_valid") is not True
        ):
            raise ExerciseError(
                "authenticated guest identity, release or application target mismatch"
            )
        return value

    def preflight(self):
        if self.journal.pending():
            raise ExerciseError("unresolved journal operations require explicit reconciliation")
        self.evidence.data.update(
            exercise="prepared-proxmox-postgres-logical-restore",
            backend="prepared-proxmox",
            simulated=any(api.simulated for api in self.apis.values()),
            guest_config_digest=self.config.digest,
            cleanup_scope="release exercise leases and stop services; prepared VMs/disks retained",
            fault=self.fault,
        )
        self.prepare_manifest()
        keys = [self.ssh[role].argv("probe") for role in ("source", "restore")]
        public_keys = [
            Path(getattr(self.config, role).known_hosts).read_text().split()[2]
            for role in ("source", "restore")
        ]
        if public_keys[0] == public_keys[1] or len(keys) != 2:
            raise ExerciseError("source and restore must have independently pinned SSH host keys")
        for role in ("source", "restore"):
            probe = self.probe(role)
            if (
                probe["database_state"] != "active"
                or probe["app_state"] != "inactive"
                or probe.get("lease_owner") is not None
            ):
                raise ExerciseError(
                    "prepare a running empty database and stopped application separately"
                )

    def prepare_image(self):
        # Prepared release hashes were checked over authenticated SSH; no deployment here.
        self.evidence.data["prepared_release_sha256"] = self.config.source.release_sha256
        self.evidence.save()

    def instance(self, role):
        self.probe(role)
        guest = getattr(self.config, role)
        self.evidence.data["resources"].append(
            {
                "kind": "prepared-guest",
                "role": role,
                "ownership": guest.ownership,
                "state": "lease_intent",
            }
        )
        self.evidence.save()
        self.ssh[role].run("claim", mutation=True)
        self.claimed.add(role)
        instance = {
            "guest_role": role,
            "vmid": guest.vmid,
            "machine_id": guest.machine_id,
            "volumes": guest.volumes,
        }
        self.instances[role] = instance
        if (
            self.sql(
                instance,
                "SELECT count(*) FROM pg_database "
                "WHERE datname NOT IN ('postgres','template0','template1','orders');",
            )
            != "0"
        ):
            raise ExerciseError("prepared cluster contains unrelated databases")
        if self.sql(instance, "SELECT count(*) FROM pg_tables WHERE schemaname='public';") != "0":
            raise ExerciseError("prepared database must be empty; no overwrite permitted")
        empty = """
SELECT
 (SELECT count(*) FROM pg_namespace WHERE nspname !~ '^pg_'
   AND nspname NOT IN ('public','information_schema')) +
 (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema') +
 (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema');
"""
        if self.sql(instance, empty) != "0":
            raise ExerciseError("prepared database contains unrelated user schema objects")
        if (
            self.sql(
                instance,
                "SELECT count(*) FROM pg_roles WHERE rolname='order_app' AND NOT rolsuper;",
            )
            != "1"
        ):
            raise ExerciseError("prepared limited application role is unavailable")
        if self.sql(instance, "SHOW listen_addresses;") not in ("localhost", "127.0.0.1"):
            raise ExerciseError("prepared PostgreSQL must listen only on guest loopback")
        if (
            self.sql(instance, "SHOW data_directory;") != "/var/lib/postgresql/18/main"
            or self.sql(instance, "SHOW port;") != "5432"
        ):
            raise ExerciseError("prepared database does not match the dedicated service cluster")
        if (
            self.sql(
                instance,
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname='orders' AND pid<>pg_backend_pid();",
            )
            != "0"
        ):
            raise ExerciseError("prepared database has other active sessions")
        instance["system_identifier"] = self.sql(
            instance, "SELECT system_identifier FROM pg_control_system();"
        )
        versions = {
            "server": self.sql(instance, "SHOW server_version;"),
            "pg_dump": self.native(instance, ["pg_dump", "--version"]).decode().strip(),
            "pg_restore": self.native(instance, ["pg_restore", "--version"]).decode().strip(),
        }
        if any("18.7" not in value for value in versions.values()):
            raise ExerciseError(
                "both prepared database/tool installations must match PostgreSQL 18.7"
            )
        self.evidence.data.setdefault("guest_database_versions", {})[role] = {
            key: "18.7" for key in versions
        }
        self.evidence.data[role] = dict(instance)
        self.evidence.data["resources"][-1]["state"] = "leased"
        self.evidence.save()
        return instance

    def native(self, instance, args, **kwargs):
        role = instance["guest_role"]
        guest = getattr(self.config, role)
        if any(
            instance.get(key) != expected
            for key, expected in {
                "vmid": guest.vmid,
                "machine_id": guest.machine_id,
                "volumes": guest.volumes,
            }.items()
        ):
            raise ExerciseError("native command target differs from prepared guest binding")
        source = kwargs.get("source")
        data = source.read(16 * 1024**2 + 1) if source else kwargs.get("data", b"")
        checksum = hashlib.sha256(data).hexdigest() if source else None
        if args[0] == "psql":
            operation = "sql"
        elif "--version" in args:
            operation = "dump-version" if args[0] == "pg_dump" else "restore-version"
        else:
            operation = (
                "dump" if args[0] == "pg_dump" else "list" if "--list" in args else "restore"
            )

        def validate(value):
            if operation == "restore":
                receipt = json.loads(value)
                if receipt != {"sha256": checksum, "bytes": len(data)}:
                    raise ExerciseError("restore transfer receipt mismatch")

        output = self.ssh[role].run(
            operation,
            data,
            mutation=kwargs.get("mutation", False),
            checksum=checksum,
            validate=validate,
        )
        if operation == "dump":
            metadata, archive = output.split(b"\n", 1)
            if json.loads(metadata) != {
                "sha256": hashlib.sha256(archive).hexdigest(),
                "bytes": len(archive),
            }:
                raise ExerciseError("backup transfer checksum mismatch")
            output = archive
        if kwargs.get("output"):
            kwargs["output"].write(output)
            return b""
        return output

    def app_command(self, app, args, **kwargs):
        operation = "http" if "rehearsal_exercise.http_client" in args else "versions"
        return self.ssh[app["guest_role"]].run(
            operation, kwargs.get("data", b""), mutation=kwargs.get("mutation", False)
        )

    def app(self, role):
        self.ssh[role].run("app-start", mutation=True)
        app = {"guest_role": role}
        self.instances[role]["app"] = app
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.http(app, [{"method": "GET", "path": "/health/ready"}])[0]["status"] == 200:
                return app
            time.sleep(0.5)
        raise ExerciseError("prepared application readiness deadline expired")

    def stop_app(self, instance):
        self.ssh[instance["guest_role"]].run("app-stop", mutation=True)

    def stop_database(self, instance):
        self.ssh[instance["guest_role"]].run("db-stop", mutation=True)

    def assert_target(self, source, target):
        if source.get("guest_role") != "source" or target.get("guest_role") != "restore":
            raise ExerciseError("source and restore guest roles must remain distinct")
        for field in ("vmid", "machine_id", "system_identifier"):
            if not source.get(field) or not target.get(field) or source[field] == target[field]:
                raise ExerciseError("source and restore guest/database identities must differ")
        if set(source["volumes"]) & set(target["volumes"]):
            raise ExerciseError("source and restore guest storage must differ")
        if self.probe("source")["database_state"] != "inactive":
            raise ExerciseError("source PostgreSQL must remain stopped during recovery")
        self.probe("restore")
        self.evidence.data["checks"]["restore_target_selection"] = {
            "passed": True,
            "source_stopped": True,
        }
        self.evidence.save()

    def assert_app_target(self, instance, app):
        if (
            app["guest_role"] != instance["guest_role"]
            or not self.probe(instance["guest_role"])["app_target_valid"]
        ):
            raise ExerciseError("restored application target is unverified")

    def cleanup(self):
        pending = []
        if self.journal.pending():
            pending.append({"reason": "unresolved operations protect prepared guests"})
        else:
            for role in self.claimed:
                try:
                    admitted = any(
                        r["role"] == role and r["state"] == "leased"
                        for r in self.evidence.data["resources"]
                    )
                    if not admitted:
                        raise ExerciseError(
                            "cluster admission incomplete; retain services for review"
                        )
                    probe = self.probe(role)
                    if probe.get("lease_owner") != self.ssh[role].owner:
                        released = any(
                            row[0] == "complete"
                            and json.loads(row[1]).get("owner") == self.ssh[role].owner
                            for row in self.journal.db.execute(
                                "SELECT status,desired FROM operations "
                                "WHERE method='SSH' AND path=?",
                                (f"/guests/{getattr(self.config, role).vmid}/release",),
                            )
                        )
                        if not (
                            probe.get("lease_owner") is None
                            and released
                            and probe["app_state"] == probe["database_state"] == "inactive"
                        ):
                            raise ExerciseError("guest lease is not owned by this exercise")
                        for resource in self.evidence.data["resources"]:
                            if resource["role"] == role:
                                resource["state"] = "retained_guest_services_stopped"
                        continue
                    self.stop_app({"guest_role": role})
                    self.stop_database({"guest_role": role})
                    self.ssh[role].run("release", mutation=True)
                    for resource in self.evidence.data["resources"]:
                        if resource["role"] == role:
                            resource["state"] = "retained_guest_services_stopped"
                except (ExerciseError, SafetyError):
                    pending.append({"role": role, "reason": "owned service cleanup unavailable"})
        self.evidence.data["cleanup"] = "pending" if pending else "complete"
        self.evidence.data["cleanup_pending"] = pending
        self.evidence.save()
        return not pending


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "run", "cleanup", "reconcile"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--operation")
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--fault",
        choices=("none", "missing-record", "changed-record", "corrupt-backup"),
        default="none",
    )
    args = parser.parse_args(argv)
    try:
        config = GuestConfig.load(args.config)
    except ExerciseError:
        print('{"error":"invalid prepared-guest configuration"}')
        return 2
    if args.command == "validate":
        print('{"valid":true,"live_checked":false}')
        return 0
    if not args.live or os.environ.get("REHEARSAL_LIVE") != "1":
        parser.error("guest operations require --live and REHEARSAL_LIVE=1")
    if args.artifacts is None:
        parser.error("explicit private --artifacts directory required")
    if (args.artifacts / "journal.sqlite3").exists():
        parser.error("a separate guest exercise root is required; legacy build state is protected")
    if args.command != "run" and not (args.artifacts / "guest-requests/journal.sqlite3").is_file():
        parser.error("existing request journal is required; do not recreate lost state")
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        with (
            locked_root(args.artifacts, create=args.command == "run") as root,
            Journal(root / "guest-requests") as journal,
        ):
            token = load_token(Path(config.token_file))
            apis = {
                role: PreparedAPI(config, getattr(config, role), journal, token)
                for role in ("source", "restore")
            }
            try:
                if args.command == "run":
                    evidence = perform_run(
                        root,
                        args.run_id or str(uuid4()),
                        Path.cwd(),
                        fault=args.fault,
                        runner_factory=lambda e, p, fault: GuestRunner(
                            e, p, config, journal, apis, fault
                        ),
                    )
                else:
                    evidence = Evidence(root, args.run_id)
                    if evidence.data.get("guest_config_digest") != config.digest:
                        raise ExerciseError("guest configuration differs from retained run")
                    runner = GuestRunner(evidence, Path.cwd(), config, journal, apis)
                    if args.command == "reconcile":
                        operation = journal.operation(args.operation)
                        if operation["method"] == "SSH":
                            desired = json.loads(operation["desired"])
                            role = next(
                                role
                                for role in ("source", "restore")
                                if runner.ssh[role].owner == desired.get("owner")
                            )
                            runner.ssh[role].reconcile(args.operation)
                        else:
                            role = next(
                                role
                                for role, api in apis.items()
                                if operation["path"].startswith(api.vm_path + "/status/")
                            )
                            expected = (
                                "running" if operation["path"].endswith("/start") else "stopped"
                            )

                            def postcondition():
                                observed = apis[role].owned()
                                return (
                                    {"status": expected}
                                    if observed["status"] == expected
                                    else False
                                )

                            apis[role].reconcile_recorded(args.operation, postcondition)
                    else:
                        if evidence.data["outcome"] == "incomplete":
                            evidence.data.update(
                                outcome="cancelled",
                                failure="interrupted guest exercise; timing incomplete",
                            )
                        runner.cleanup()
                    evidence.publish()
                print(
                    json.dumps(
                        {
                            "run": evidence.data["run"],
                            "outcome": evidence.data["outcome"],
                            "cleanup": evidence.data["cleanup"],
                        }
                    )
                )
                return (
                    0
                    if evidence.data["cleanup"] == "complete"
                    and evidence.data["outcome"] == "passed"
                    else 1
                )
            finally:
                for api in apis.values():
                    api.close()
    except (Exception, KeyboardInterrupt):
        print('{"error":"guest integration incomplete; retain evidence and request journal"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
