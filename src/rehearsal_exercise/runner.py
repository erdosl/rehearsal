"""One controlled local recovery, with external evidence and no lab dependencies."""

import contextlib
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from importlib.resources import files
from pathlib import Path

from rehearsal_exercise.docker import Docker, require_restore_target
from rehearsal_exercise.evidence import Evidence, ExerciseError, atomic_json, sync_directory, utc
from rehearsal_exercise.manifest import compare, intended_order, manifest
from rehearsal_exercise.verification import RECORDS_SQL, SCHEMA_SQL, check_schema, constraint_probes


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextlib.contextmanager
def phase(evidence, name):
    evidence.data["phase"] = name
    entry = {"name": name, "started_utc": utc(), "status": "incomplete"}
    evidence.data["phases"].append(entry)
    evidence.save()
    evidence.event("phase_start", phase=name)
    started = time.monotonic()
    try:
        yield
    except BaseException:
        entry["status"] = "failed"
        raise
    else:
        entry["status"] = "passed"
    finally:
        entry.update(ended_utc=utc(), duration_seconds=time.monotonic() - started)
        evidence.save()
        evidence.event("phase_end", **entry)


class Runner:
    def __init__(self, evidence, project, fault="none", docker=None):
        self.evidence = evidence
        self.project = Path(project)
        self.docker = docker or Docker(evidence)
        self.fault = fault
        self.images = tomllib.loads(files("rehearsal_exercise").joinpath("images.toml").read_text())
        self.expected = manifest()
        self.instances = {}
        self.recovery_started = None

    def sql(self, instance, query, *, operation="sql_read", mutation=False):
        return (
            self.docker.call(
                [
                    "exec",
                    "-i",
                    instance["container"],
                    "psql",
                    "-X",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-At",
                    "-U",
                    "postgres",
                    "-d",
                    "orders",
                ],
                data=query.encode(),
                operation=operation,
                mutation=mutation,
            )
            .decode()
            .strip()
        )

    def json_sql(self, instance, query):
        return json.loads(self.sql(instance, query))

    def http(self, app, requests, *, mutation=False):
        return json.loads(
            self.docker.call(
                ["exec", "-i", app["id"], "python", "-m", "rehearsal_exercise.http_client"],
                operation="http_write" if mutation else "http_read",
                mutation=mutation,
                data=json.dumps(requests).encode(),
            )
        )

    def preflight(self):
        engine = json.loads(
            self.docker.call(
                [
                    "info",
                    "--format",
                    '{"version":{{json .ServerVersion}},"memory_bytes":{{.MemTotal}},'
                    '"cpus":{{.NCPU}},"architecture":{{json .Architecture}},'
                    '"root":{{json .DockerRootDir}}}',
                ]
            )
        )
        if engine["architecture"] not in ("x86_64", "amd64"):
            raise ExerciseError("exercise lock and images currently require Linux x86_64")
        available = shutil.disk_usage(self.evidence.directory).free
        docker_free = shutil.disk_usage(engine.pop("root")).free
        if min(available, docker_free) < 3 * 1024**3 or engine["memory_bytes"] < 2 * 1024**3:
            raise ExerciseError(
                "preflight requires 3 GiB free disk and a 2 GiB Docker memory budget"
            )
        try:
            compose = self.docker.call(["compose", "version", "--short"]).decode().strip()
        except ExerciseError:
            compose = "unavailable; runner uses Docker CLI directly"
        self.evidence.data["preflight"] = {
            "verified_utc": utc(),
            "engine": engine,
            "compose_version": compose,
            "artifact_free_bytes": available,
            "docker_free_bytes": docker_free,
            "existing_container_count": len(self.docker.call(["ps", "-aq"]).splitlines()),
            "existing_volume_count": len(self.docker.call(["volume", "ls", "-q"]).splitlines()),
        }
        if not (self.project / "docker/orders.Dockerfile").is_file():
            raise ExerciseError("project source with docker/orders.Dockerfile required")
        self.evidence.data["images"] = self.images
        self.evidence.data["fault"] = self.fault
        atomic_json(self.evidence.directory / "manifest.json", self.expected)
        self.evidence.data["manifest_sha256"] = sha256(self.evidence.directory / "manifest.json")
        # Record exactly the workload/verifier/config/build inputs, including uncommitted changes.
        inputs = [
            *self.project.glob("src/rehearsal_orders/*"),
            *self.project.glob("src/rehearsal_exercise/*"),
            self.project / "docker/orders.Dockerfile",
            self.project / "requirements-exercise.lock",
            self.project / ".dockerignore",
        ]
        self.evidence.data["source_sha256"] = {
            str(path.relative_to(self.project)): sha256(path) for path in inputs if path.is_file()
        }
        self.evidence.save()

    def prepare_image(self):
        for image in self.images.values():
            self.docker.call(
                ["pull", "--platform", "linux/amd64", image],
                operation="pull_pinned_image",
                mutation=True,
                timeout=600,
            )
        # Download hash-checked wheels on the host; the build itself needs no DNS/egress.
        # The temporary context contains only explicitly copied source and public wheels.
        with tempfile.TemporaryDirectory(prefix="build-", dir=self.evidence.directory) as temp:
            context = Path(temp)
            (context / "docker").mkdir()
            for relative in (
                "docker/orders.Dockerfile",
                "requirements-exercise.lock",
                ".dockerignore",
            ):
                shutil.copyfile(self.project / relative, context / relative)
            for package in ("rehearsal_orders", "rehearsal_exercise"):
                shutil.copytree(
                    self.project / "src" / package,
                    context / "src" / package,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            wheels = context / "wheels"
            wheels.mkdir()
            self.evidence.event("dependency_download_start")
            started = time.monotonic()
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "download",
                        "--only-binary=:all:",
                        "--require-hashes",
                        "--dest",
                        str(wheels),
                        "-r",
                        str(context / "requirements-exercise.lock"),
                    ],
                    capture_output=True,
                    timeout=120,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise ExerciseError(
                    "hash-checked dependency download unavailable or timed out"
                ) from None
            self.evidence.event(
                "dependency_download_end",
                exit_code=result.returncode,
                duration_seconds=time.monotonic() - started,
            )
            if result.returncode:
                raise ExerciseError("hash-checked dependency download failed")
            self.evidence.data["dependency_wheels"] = {
                path.name: sha256(path) for path in wheels.glob("*.whl")
            }
            resource = self.docker.plan(
                "image", "app-image", f"rehearsal-orders:{self.evidence.data['run']}"
            )
            if self.docker.inspect("image", resource["name"]) is not None:
                raise ExerciseError("application image tag already exists; refusing overwrite")
            resource["state"] = "intent"
            self.evidence.save()
            self.docker.call(
                [
                    "build",
                    "--network",
                    "none",
                    "--platform",
                    "linux/amd64",
                    "--file",
                    str(context / "docker/orders.Dockerfile"),
                    "--build-arg",
                    f"PYTHON_IMAGE={self.images['python']}",
                    "--tag",
                    resource["name"],
                    *self.docker.label_args(resource),
                    str(context),
                ],
                operation="build_app_image",
                mutation=True,
                timeout=600,
            )
            self.app_image = self.docker.capture(resource)["id"]
            self.evidence.data["application_image_id"] = self.app_image

    def instance(self, role):
        network = self.docker.create("network", f"{role}-network", ["--internal"])
        volume = self.docker.create("volume", f"{role}-data", [])
        credential = self.evidence.directory / f".{role}-credential"
        credential.write_text(secrets.token_hex(32))
        credential.chmod(0o444)  # Enclosing directory is 0700; readable by container non-root UID.
        admin_credential = self.evidence.directory / f".{role}-admin-credential"
        admin_credential.write_text(secrets.token_hex(32))
        admin_credential.chmod(0o444)
        instance = {
            "network": network["id"],
            "volume": volume["id"],
            "credential": credential,
        }
        database = self.docker.create(
            "container",
            f"{role}-db",
            [
                "--network",
                network["id"],
                "--network-alias",
                "db",
                "--user",
                "postgres",
                "--memory",
                "384m",
                "--cpus",
                "1",
                "--pids-limit",
                "128",
                "--shm-size",
                "64m",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "--tmpfs",
                "/var/run/postgresql:rw,noexec,nosuid,size=8m,mode=1777",
                "--mount",
                f"type=volume,src={volume['id']},dst=/var/lib/postgresql",
                "--mount",
                f"type=bind,src={admin_credential},dst=/run/postgres-credential,readonly",
                "--env",
                "POSTGRES_PASSWORD_FILE=/run/postgres-credential",
                "--env",
                "POSTGRES_DB=orders",
                "--env",
                "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256",
                "--log-driver",
                "none",
                self.images["postgres"],
            ],
        )
        instance["container"] = database["id"]
        self.instances[role] = instance
        self.docker.call(["start", database["id"]], operation=f"start_{role}_db", mutation=True)
        deadline = time.monotonic() + 45
        while True:
            try:
                self.docker.call(
                    [
                        "exec",
                        database["id"],
                        "pg_isready",
                        "-q",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "postgres",
                        "-d",
                        "orders",
                    ],
                    operation="database_readiness",
                    timeout=5,
                )
                break
            except ExerciseError:
                if time.monotonic() >= deadline:
                    raise ExerciseError("database did not become ready within 45 seconds") from None
                time.sleep(0.25)
        instance["system_identifier"] = self.sql(
            instance, "SELECT system_identifier FROM pg_control_system();"
        )
        self.evidence.data[role] = {
            key: value for key, value in instance.items() if key != "credential"
        }
        self.evidence.save()
        # Fresh login is deliberately different for each instance; superuser stays local.
        password = credential.read_text()
        self.sql(
            instance,
            f"CREATE ROLE order_app LOGIN PASSWORD '{password}';",
            operation="setup_app_role",
            mutation=True,
        )
        return instance

    def grant(self, instance):
        self.sql(
            instance,
            "GRANT USAGE ON SCHEMA public TO order_app; "
            "GRANT SELECT ON schema_version TO order_app; "
            "GRANT SELECT, INSERT ON orders TO order_app;",
            operation="grant_app",
            mutation=True,
        )

    def app(self, role):
        instance = self.instances[role]
        app = self.docker.create(
            "container",
            f"{role}-api",
            [
                "--network",
                instance["network"],
                "--memory",
                "128m",
                "--cpus",
                "0.5",
                "--pids-limit",
                "64",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=16m",
                "--log-driver",
                "none",
                "--mount",
                f"type=bind,src={instance['credential']},dst=/run/order-credential,readonly",
                "--env",
                "ORDER_PASSWORD_FILE=/run/order-credential",
                "--env",
                "PGHOST=db",
                "--env",
                "PGDATABASE=orders",
                "--env",
                "PGUSER=order_app",
                self.app_image,
            ],
        )
        self.docker.call(["start", app["id"]], operation=f"start_{role}_api", mutation=True)
        deadline = time.monotonic() + 20
        while True:
            try:
                response = self.http(app, [{"method": "GET", "path": "/health/ready"}])
                if response[0]["status"] == 200:
                    break
            except ExerciseError:
                pass
            if time.monotonic() >= deadline:
                raise ExerciseError("application did not become database-ready within 20 seconds")
            time.sleep(0.25)
        instance["app"] = app
        return app

    def verify_sql(self, role):
        instance = self.instances[role]
        result = compare(self.expected["records"], self.json_sql(instance, RECORDS_SQL))
        self.evidence.data["checks"][f"{role}_data"] = result
        atomic_json(self.evidence.directory / f"{role}-verification.json", result)
        self.evidence.save()
        if not result["passed"]:
            raise ExerciseError(f"{role}: recovered record verification mismatch")
        schema = self.json_sql(instance, SCHEMA_SQL)
        atomic_json(self.evidence.directory / f"{role}-schema.json", schema)
        check_schema(schema)
        for query in constraint_probes():
            self.sql(instance, query, operation="rollback_constraint_probe", mutation=True)
        self.evidence.data["checks"][f"{role}_schema"] = {"passed": True, "constraint_probes": 8}
        self.evidence.save()

    def verify_http(self, role):
        requests = [
            {"method": "GET", "path": f"/orders/{row['id']}"} for row in self.expected["records"]
        ]
        results = self.http(self.instances[role]["app"], requests)
        actual = [item["body"] for item in results if item["status"] == 200]
        result = compare(self.expected["records"], actual)
        self.evidence.data["checks"][f"{role}_api"] = result
        self.evidence.save()
        if not result["passed"]:
            raise ExerciseError(f"{role}: API reads differ from independent manifest")

    def versions(self, source):
        result = {
            "server": self.sql(source, "SHOW server_version;"),
            "pg_dump": self.docker.call(["exec", source["container"], "pg_dump", "--version"])
            .decode()
            .strip(),
            "pg_restore": self.docker.call(["exec", source["container"], "pg_restore", "--version"])
            .decode()
            .strip(),
            "application": json.loads(
                self.docker.call(
                    [
                        "exec",
                        source["app"]["id"],
                        "python",
                        "-c",
                        "import json,platform,psycopg; "
                        "print(json.dumps({'python':platform.python_version(),"
                        "'psycopg':psycopg.__version__,'libpq':psycopg.pq.version()}))",
                    ]
                )
            ),
        }
        if not result["server"].startswith("18.7") or any(
            "18.7" not in result[key] for key in ("pg_dump", "pg_restore")
        ):
            raise ExerciseError("server and native tools must match pinned PostgreSQL 18.7")
        self.evidence.data["versions"] = result
        self.evidence.save()

    def seed(self, source):
        requests = [
            {
                "method": "POST",
                "path": "/orders",
                "body": {key: value for key, value in row.items() if key != "total_cents"},
            }
            for row in self.expected["records"]
        ]
        results = self.http(source["app"], requests, mutation=True)
        if len(results) != len(requests) or any(item["status"] != 201 for item in results):
            raise ExerciseError("deterministic seed did not acknowledge every order")
        if not compare(self.expected["records"], [item["body"] for item in results])["passed"]:
            raise ExerciseError("seed acknowledgements differ from intended manifest")
        self.evidence.data["last_seed_acknowledged_utc"] = utc()
        self.evidence.save()

    def quiesce(self, source):
        self.docker.call(
            ["stop", "--time", "5", source["app"]["id"]],
            operation="stop_source_writers",
            mutation=True,
        )
        self.sql(
            source,
            "ALTER ROLE order_app NOLOGIN; SELECT pg_terminate_backend(pid) "
            "FROM pg_stat_activity WHERE usename='order_app' AND pid<>pg_backend_pid();",
            operation="freeze_source_role",
            mutation=True,
        )
        active = self.sql(
            source,
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname='orders' AND pid<>pg_backend_pid();",
        )
        if active != "0":
            raise ExerciseError("source has other active sessions at frozen-write boundary")
        self.evidence.data["frozen_boundary"] = {
            "utc": utc(),
            "source_api": "stopped",
            "application_login": "disabled",
            "other_database_sessions": 0,
            "external_writers": "none in dedicated synthetic instance",
        }
        self.evidence.save()

    def backup(self, source):
        directory = self.evidence.directory
        if shutil.disk_usage(directory).free < 1024**3:
            raise ExerciseError("insufficient evidence space before backup")
        partial = directory / "backup.partial"
        with partial.open("xb") as stream:
            self.docker.call(
                [
                    "exec",
                    source["container"],
                    "pg_dump",
                    "-U",
                    "postgres",
                    "-d",
                    "orders",
                    "--format=custom",
                    "--no-owner",
                    "--no-privileges",
                ],
                output=stream,
                operation="native_backup",
            )
            stream.flush()
            os.fsync(stream.fileno())
        if not partial.stat().st_size:
            raise ExerciseError("backup is empty")
        os.rename(partial, directory / "backup.dump")
        sync_directory(directory)
        self.evidence.data["backup"] = {
            "file": "backup.dump",
            "bytes": (directory / "backup.dump").stat().st_size,
            "sha256": sha256(directory / "backup.dump"),
        }
        atomic_json(directory / "backup-checksum.json", self.evidence.data["backup"])
        with (directory / "backup.dump").open("rb") as stream:
            # Listing is only an archive sanity check; recovery still needs independent checks.
            self.docker.call(
                ["exec", "-i", source["container"], "pg_restore", "--list"],
                source=stream,
                operation="archive_list",
            )
        self.evidence.save()

    def assert_target(self, source, target):
        require_restore_target(source, target)
        for role in ("source", "restore"):
            instance = self.instances[role]
            # Check live database network and volume mappings against the exact recorded identities.
            mapping = json.loads(
                self.docker.call(
                    [
                        "container",
                        "inspect",
                        "--format",
                        '{"networks":{{json .NetworkSettings.Networks}},"mounts":{{json .Mounts}}}',
                        instance["container"],
                    ]
                )
            )
            networks = list(mapping["networks"].values())
            volumes = [m["Name"] for m in mapping["mounts"] if m["Type"] == "volume"]
            if (
                len(networks) != 1
                or networks[0]["NetworkID"] != instance["network"]
                or volumes != [instance["volume"]]
            ):
                raise ExerciseError("database network/storage mapping differs from journal")
        source_running = self.docker.call(
            ["container", "inspect", "--format", "{{.State.Running}}", source["container"]]
        ).strip()
        if source_running != b"false":
            raise ExerciseError("source must remain stopped during target verification")
        self.evidence.data["checks"]["restore_target_selection"] = {
            "passed": True,
            "source_stopped": True,
            "independent_cluster_storage_network": True,
        }
        self.evidence.save()

    def restore(self, target):
        backup = self.evidence.directory / "backup.dump"
        if sha256(backup) != self.evidence.data["backup"]["sha256"]:
            raise ExerciseError("backup checksum mismatch; restore blocked")
        if (
            sha256(self.evidence.directory / "manifest.json")
            != self.evidence.data["manifest_sha256"]
        ):
            raise ExerciseError("manifest checksum mismatch; restore blocked")
        if self.sql(target, "SELECT count(*) FROM pg_tables WHERE schemaname='public';") != "0":
            raise ExerciseError("restore target is not empty")
        restore_input = backup
        if self.fault == "corrupt-backup":
            restore_input = self.evidence.directory / "corrupt-backup.dump"
            restore_input.write_bytes(backup.read_bytes()[:64])
        with restore_input.open("rb") as stream:
            self.docker.call(
                [
                    "exec",
                    "-i",
                    target["container"],
                    "pg_restore",
                    "-U",
                    "postgres",
                    "-d",
                    "orders",
                    "--exit-on-error",
                    "--single-transaction",
                    "--no-owner",
                    "--no-privileges",
                ],
                source=stream,
                operation="native_restore",
                mutation=True,
            )
        self.grant(target)

    def canary(self, source, target):
        row = intended_order(1001)
        row.update(customer="POST-RESTORE", sku="CANARY")
        # Input intentionally differs from every recovered record, and is retained separately.
        atomic_json(self.evidence.directory / "post-restore-canary.json", row)
        body = {key: value for key, value in row.items() if key != "total_cents"}
        responses = self.http(
            target["app"],
            [
                {"method": "POST", "path": "/orders", "body": body},
                {"method": "GET", "path": f"/orders/{row['id']}"},
                {"method": "POST", "path": "/orders", "body": body},
            ],
            mutation=True,
        )
        if [r["status"] for r in responses] != [201, 200, 200] or any(
            r["body"] != row for r in responses
        ):
            raise ExerciseError("post-restore write/read/idempotency failed")
        result = compare(self.expected["records"] + [row], self.json_sql(target, RECORDS_SQL))
        if not result["passed"]:
            raise ExerciseError("post-restore SQL differs from recovered dataset plus canary")
        self.evidence.data["checks"]["post_restore_canary"] = result
        self.evidence.save()

    def execute(self):
        with phase(self.evidence, "preflight"):
            self.preflight()
        with phase(self.evidence, "image_preparation"):
            self.prepare_image()
        with phase(self.evidence, "source_preparation"):
            source = self.instance("source")
            self.sql(
                source,
                files("rehearsal_orders").joinpath("schema.sql").read_text(),
                operation="initialize_schema_v1",
                mutation=True,
            )
            self.grant(source)
            self.app("source")
            self.versions(source)
        with phase(self.evidence, "seed"):
            self.seed(source)
            self.verify_sql("source")
            self.verify_http("source")
        with phase(self.evidence, "quiesce"):
            self.quiesce(source)
        with phase(self.evidence, "backup"):
            self.backup(source)
        with phase(self.evidence, "source_shutdown"):
            self.docker.call(
                ["stop", "--time", "10", source["container"]],
                operation="stop_source_database",
                mutation=True,
            )
        self.recovery_started = time.monotonic()
        self.evidence.data["recovery"] = {
            "label": "measured exercise recovery duration",
            "started_utc": utc(),
            "complete": False,
            "start_boundary": "before restore network, volume and instance allocation",
            "end_boundary": "recovered SQL/schema/API checks and separate "
            "post-restore write/read passed",
        }
        self.evidence.save()
        with phase(self.evidence, "target_preparation"):
            target = self.instance("restore")
            self.assert_target(source, target)
        with phase(self.evidence, "restore"):
            self.restore(target)
        with phase(self.evidence, "recovered_data_verification"):
            if self.fault == "missing-record":
                self.sql(
                    target,
                    "DELETE FROM orders WHERE id='00000000-0000-0000-0000-000000000001';",
                    operation="inject_missing_record",
                    mutation=True,
                )
            elif self.fault == "changed-record":
                self.sql(
                    target,
                    "UPDATE orders SET customer='ALTERED' "
                    "WHERE id='00000000-0000-0000-0000-000000000001';",
                    operation="inject_changed_record",
                    mutation=True,
                )
            self.verify_sql("restore")
        with phase(self.evidence, "restored_application"):
            app = self.app("restore")
            mapping = json.loads(
                self.docker.call(
                    [
                        "container",
                        "inspect",
                        "--format",
                        "{{json .NetworkSettings.Networks}}",
                        app["id"],
                    ]
                )
            )
            if [value["NetworkID"] for value in mapping.values()] != [target["network"]]:
                raise ExerciseError("restored API is not exclusively on restore network")
            self.assert_target(source, target)
            self.verify_http("restore")
        with phase(self.evidence, "post_restore_write_read"):
            self.canary(source, target)
        self.evidence.data["recovery"].update(
            ended_utc=utc(),
            duration_seconds=time.monotonic() - self.recovery_started,
            complete=True,
        )
        # Source storage is still present, deliberately stopped and never restored over.
        self.evidence.data["checks"]["source_preserved_until_cleanup"] = {"passed": True}
        self.evidence.save()


def perform_run(root, run_id, project, fault="none", runner_factory=Runner):
    evidence = Evidence(root, run_id, create=True)
    runner = runner_factory(evidence, project, fault)
    try:
        runner.execute()
        evidence.data["outcome"] = "passed"
    except (KeyboardInterrupt, SystemExit):
        evidence.data.update(
            outcome="cancelled", failure="interrupted; incomplete phases did not pass"
        )
    except ExerciseError as error:
        evidence.data.update(outcome="failed", failure=str(error))
    except Exception:
        # Never persist driver/subprocess exceptions, DSNs, env, stderr or arbitrary tracebacks.
        evidence.data.update(
            outcome="errored", failure="internal or evidence error; exercise incomplete"
        )
    finally:
        if evidence.data["outcome"] != "passed":
            evidence.data["failure_phase"] = evidence.data["phase"]
        evidence.data["exercise_outcome"] = evidence.data["outcome"]
        if evidence.data["outcome"] == "passed":
            evidence.data["outcome"] = "incomplete"  # Success waits for durable cleanup.
        if evidence.data.get("recovery", {}).get("complete") is False:
            evidence.data["recovery"]["ended_utc"] = utc()
        evidence.save()
        evidence.report()  # Failure evidence must survive even if cleanup is interrupted.
        try:
            with phase(evidence, "cleanup"):
                runner.docker.cleanup()
                if evidence.data["cleanup"] != "complete":
                    raise ExerciseError("owned cleanup remains pending")
        except ExerciseError:
            evidence.data["cleanup"] = "pending"
        remove_credentials(evidence)
        evidence.data["finished_utc"] = utc()
        evidence.data["phase"] = (
            "finished" if evidence.data["cleanup"] == "complete" else "cleanup_pending"
        )
        if evidence.data["exercise_outcome"] == "passed":
            if evidence.data["cleanup"] == "complete":
                evidence.data["outcome"] = "passed"
            else:
                evidence.data.update(
                    outcome="failed", failure="exercise checks passed; cleanup pending"
                )
        evidence.publish()
    return evidence


def remove_credentials(evidence):
    for role in ("source", "restore"):
        for suffix in ("credential", "admin-credential"):
            (evidence.directory / f".{role}-{suffix}").unlink(missing_ok=True)
