import copy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from rehearsal_exercise.__main__ import main
from rehearsal_exercise.docker import Docker, require_owner, require_restore_target
from rehearsal_exercise.evidence import Evidence, ExerciseError, locked_root
from rehearsal_exercise.manifest import compare, intended_order, manifest
from rehearsal_exercise.runner import Runner, perform_run, phase, sha256
from rehearsal_exercise.verification import (
    EXPECTED_COLUMNS,
    EXPECTED_CONSTRAINTS,
    EXPECTED_DEFINITIONS,
    EXPECTED_INDEXES,
    check_schema,
)
from rehearsal_orders.domain import order_input

# Keep the implementation callable for adapter tests with a fake subprocess; the
# autouse fixture still forbids normal Docker.call invocations in offline tests.
DOCKER_CALL = Docker.call


@pytest.fixture
def evidence(tmp_path):
    return Evidence(tmp_path, str(uuid4()), create=True)


def test_manifest_is_intended_input_and_deterministic():
    expected = manifest()
    assert expected == manifest()
    assert len(expected["records"]) == len(expected["record_sha256"]) == 100
    assert expected["records"][0]["id"] == "00000000-0000-0000-0000-000000000001"
    assert expected["records"][0]["total_cents"] == 264
    assert expected["total_cents"] == sum(r["total_cents"] for r in expected["records"])
    assert compare(expected["records"], list(reversed(expected["records"])))["passed"]


@pytest.mark.parametrize("damage", ["missing", "extra", "changed", "duplicate"])
def test_negative_record_verification(damage):
    expected = manifest()["records"]
    actual = copy.deepcopy(expected)
    if damage == "missing":
        actual.pop(0)
    elif damage == "extra":
        actual.append(intended_order(101))
    elif damage == "changed":
        actual[0]["customer"] = "ALTERED"
    else:
        actual.append(actual[0])
    result = compare(expected, actual)
    assert not result["passed"]
    if damage == "changed":
        assert result["changed"] == {expected[0]["id"]: ["customer"]}


def test_domain_money_and_validation():
    row = intended_order(1)
    body = {key: value for key, value in row.items() if key != "total_cents"}
    assert order_input(body) == row
    for field, value in [
        ("quantity", True),
        ("quantity", 0),
        ("unit_price_cents", -1),
        ("sku", "a b"),
        ("id", None),
        ("placed_at", None),
    ]:
        with pytest.raises(ValueError):
            order_input({**body, field: value})


@pytest.mark.parametrize("field", ["container", "volume", "network", "system_identifier"])
def test_restore_target_rejects_each_shared_identity(field):
    source = {
        key: f"source-{key}" for key in ("container", "volume", "network", "system_identifier")
    }
    target = {key: f"target-{key}" for key in source}
    require_restore_target(source, target)
    target[field] = source[field]
    with pytest.raises(ExerciseError, match="distinct"):
        require_restore_target(source, target)


def test_schema_missing_constraint_fails():
    schema = {
        "tables": ["orders", "schema_version"],
        "version": [1],
        "columns": EXPECTED_COLUMNS,
        "constraints": EXPECTED_CONSTRAINTS.copy(),
        "definitions": EXPECTED_DEFINITIONS.copy(),
        "enforcement": {key: [True, True] for key in EXPECTED_CONSTRAINTS},
        "index_definitions": EXPECTED_INDEXES.copy(),
        "indexes": ["orders_customer_idx", "orders_pkey", "schema_version_pkey"],
    }
    check_schema(schema)
    del schema["constraints"]["total_matches"]
    with pytest.raises(ExerciseError, match="schema"):
        check_schema(schema)


@pytest.mark.parametrize("change", ["installation", "run", "resource", "nonce", "id", "created"])
def test_cleanup_refuses_wrong_ownership_without_delete(evidence, monkeypatch, change):
    docker = Docker(evidence)
    resource = docker.plan("volume", "source-data")
    resource.update(id=resource["name"], created="generation-one", state="created")
    live = {
        "id": resource["id"],
        "created": resource["created"],
        "labels": resource["labels"].copy(),
    }
    if change in ("id", "created"):
        live[change] = "replacement"
    else:
        live["labels"][f"org.rehearsal.exercise.{change}"] = "replacement"
    monkeypatch.setattr(docker, "inspect", lambda *args: live)
    deletes = []
    monkeypatch.setattr(docker, "call", lambda *args, **kwargs: deletes.append(args))
    assert not docker.cleanup()
    assert evidence.data["cleanup"] == "pending"
    assert not deletes


def test_cleanup_matches_exact_ids_and_verifies_absence(evidence, monkeypatch):
    docker = Docker(evidence)
    resource = docker.plan("container", "source-api")
    resource.update(id="exact-container-id", created="generation-one", state="created")
    live = {"id": resource["id"], "created": resource["created"], "labels": resource["labels"]}
    calls = []
    monkeypatch.setattr(docker, "inspect", lambda *args: None if calls else live)
    monkeypatch.setattr(docker, "call", lambda args, **kwargs: calls.append(args))
    assert docker.cleanup()
    assert calls == [["container", "rm", "--force", "exact-container-id"]]
    assert resource["state"] == "removed"
    assert docker.cleanup()  # Idempotent retry sends no second deletion.
    assert len(calls) == 1


def test_uncertain_creation_is_reconciled_without_recreating(evidence, monkeypatch):
    docker = Docker(evidence)
    resource = docker.plan("network", "source-network")
    resource["state"] = "intent"
    live = {"id": "exact-network-id", "created": "one", "labels": resource["labels"]}
    calls = []
    monkeypatch.setattr(docker, "inspect", lambda *args: None if calls else live)
    monkeypatch.setattr(docker, "call", lambda args, **kwargs: calls.append(args))
    assert docker.cleanup()
    assert calls == [["network", "rm", "exact-network-id"]]


def test_absent_uncertain_creation_stays_pending(evidence, monkeypatch):
    docker = Docker(evidence)
    resource = docker.plan("volume", "source-data")
    resource["state"] = "intent"
    monkeypatch.setattr(docker, "inspect", lambda *args: None)
    assert not docker.cleanup()
    assert "unresolved" in evidence.data["cleanup_pending"][0]["reason"]


def test_run_id_is_never_overwritten(evidence):
    original = (evidence.directory / "state.json").read_bytes()
    with pytest.raises(ExerciseError, match="already exists"):
        Evidence(evidence.directory.parent, evidence.data["run"], create=True)
    assert (evidence.directory / "state.json").read_bytes() == original


def test_lock_prevents_concurrent_cleanup(tmp_path):
    root = tmp_path / "protected"
    with locked_root(root), pytest.raises(ExerciseError, match="lock"), locked_root(root):
        pass


@pytest.mark.parametrize("live,environment", [(False, "1"), (True, "0"), (False, "0")])
def test_mutation_requires_both_opt_ins(monkeypatch, tmp_path, live, environment):
    monkeypatch.setenv("REHEARSAL_LIVE", environment)
    args = ["--artifacts", str(tmp_path / "absent"), "run"]
    with pytest.raises(SystemExit) as error:
        main(args + (["--live"] if live else []))
    assert error.value.code == 2
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize(
    "failure", ["backup", "restore", "verification", "interrupt", "unexpected"]
)
def test_failure_report_survives_cleanup_without_success(tmp_path, failure):
    class FailingRunner:
        def __init__(self, evidence, *args):
            self.evidence = evidence
            self.docker = SimpleNamespace(cleanup=self.cleanup)

        def execute(self):
            with phase(self.evidence, failure):
                if failure == "interrupt":
                    raise KeyboardInterrupt
                if failure == "unexpected":
                    raise RuntimeError("postgresql://private:SECRET@private.invalid/db")
                raise ExerciseError(f"{failure}: failed controlled phase")

        def cleanup(self):
            self.evidence.data["cleanup"] = "complete"

    result = perform_run(tmp_path, str(uuid4()), Path.cwd(), runner_factory=FailingRunner)
    report = json.loads((result.directory / "report.json").read_text())
    assert report["outcome"] in ("failed", "errored", "cancelled")
    assert report["cleanup"] == "complete"
    assert report["failure_phase"] == failure
    assert report["phases"][0]["status"] == "failed"
    assert "SECRET" not in (result.directory / "report.json").read_text()
    for name, metadata in json.loads(
        (result.directory / "evidence-index.json").read_text()
    ).items():
        assert sha256(result.directory / name) == metadata["sha256"]


def test_cleanup_failure_prevents_overall_success(tmp_path):
    class ChecksPassed:
        def __init__(self, evidence, *args):
            self.evidence = evidence
            self.docker = SimpleNamespace(cleanup=lambda: False)

        def execute(self):
            pass

    result = perform_run(tmp_path, str(uuid4()), Path.cwd(), runner_factory=ChecksPassed)
    assert result.data["exercise_outcome"] == "passed"
    assert result.data["outcome"] == "failed"
    assert result.data["cleanup"] == "pending"


def test_failed_backup_never_publishes_completed_archive(evidence):
    class FailedDump:
        def call(self, args, **kwargs):
            kwargs["output"].write(b"partial archive")
            raise ExerciseError("native_backup: command failed (exit 1)")

    runner = Runner(evidence, Path.cwd(), docker=FailedDump())
    with pytest.raises(ExerciseError, match="native_backup"):
        runner.backup({"container": "source"})
    assert (evidence.directory / "backup.partial").read_bytes() == b"partial archive"
    assert not (evidence.directory / "backup.dump").exists()
    assert "backup" not in evidence.data


def test_changed_backup_is_rejected_before_restore(evidence):
    backup = evidence.directory / "backup.dump"
    backup.write_bytes(b"changed archive")
    evidence.data["backup"] = {"sha256": "incorrect-checksum"}
    runner = Runner(evidence, Path.cwd())
    with pytest.raises(ExerciseError, match="checksum"):
        runner.restore({"container": "target"})


def test_api_health_separates_liveness_from_database_failure(monkeypatch):
    import psycopg

    from rehearsal_orders.__main__ import Handler

    results = []
    handler = object.__new__(Handler)
    handler.reply = lambda status, body: results.append((status, body))
    handler.path = "/health/live"
    monkeypatch.setattr(
        "rehearsal_orders.db.ready",
        lambda: (_ for _ in ()).throw(
            psycopg.OperationalError("password=SECRET host=private.invalid")
        ),
    )
    handler.do_GET()
    handler.path = "/health/ready"
    handler.do_GET()
    assert [status for status, _ in results] == [200, 503]
    assert "SECRET" not in json.dumps(results)


def test_owner_requires_live_metadata():
    with pytest.raises(ExerciseError, match="ownership"):
        require_owner({"labels": {"installation": "ours"}}, None)


def test_offline_guard_blocks_libpq_network_entry_point():
    import psycopg

    with pytest.raises(AssertionError, match="network access is forbidden"):
        psycopg.connect("host=127.0.0.1 port=1 dbname=synthetic connect_timeout=1")


@pytest.mark.parametrize("value", [132.0, True])
def test_manifest_rejects_numeric_type_changes(value):
    actual = copy.deepcopy(manifest()["records"])
    field = "unit_price_cents" if type(value) is float else "quantity"
    position = 0 if type(value) is float else 3
    actual[position][field] = value
    assert not compare(manifest()["records"], actual)["passed"]


@pytest.mark.parametrize("part", ["definitions", "enforcement", "index_definitions"])
def test_named_but_changed_schema_objects_are_rejected(part):
    schema = {
        "tables": ["orders", "schema_version"],
        "version": [1],
        "columns": EXPECTED_COLUMNS,
        "constraints": EXPECTED_CONSTRAINTS,
        "definitions": EXPECTED_DEFINITIONS.copy(),
        "enforcement": {key: [True, True] for key in EXPECTED_CONSTRAINTS},
        "index_definitions": EXPECTED_INDEXES.copy(),
        "indexes": sorted(EXPECTED_INDEXES),
    }
    check_schema(schema)
    key = "orders_customer_idx" if part == "index_definitions" else "total_matches"
    schema[part][key] = [False, False] if part == "enforcement" else "changed"
    with pytest.raises(ExerciseError, match="schema"):
        check_schema(schema)


def test_nonzero_creation_exit_remains_uncertain(evidence, monkeypatch):
    from rehearsal_exercise.docker import CommandFailed

    docker = Docker(evidence)
    monkeypatch.setattr(docker, "inspect", lambda *args: None)

    def failed(*args, **kwargs):
        raise CommandFailed("create: command failed (exit 1)")

    monkeypatch.setattr(docker, "call", failed)
    with pytest.raises(CommandFailed):
        docker.create("network", "source-network", ["--internal"])
    assert evidence.data["resources"][0]["state"] == "intent"
    assert not docker.cleanup()


def test_image_collision_is_rejected_before_build(evidence, monkeypatch):
    docker = Docker(evidence)
    calls = []
    monkeypatch.setattr(docker, "inspect", lambda *args: {"id": "unrelated-image"})
    monkeypatch.setattr(docker, "call", lambda args, **kwargs: calls.append(args) or b"")
    monkeypatch.setattr(
        "rehearsal_exercise.runner.subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0)
    )
    runner = Runner(evidence, Path.cwd(), docker=docker)
    with pytest.raises(ExerciseError, match="refusing overwrite"):
        runner.prepare_image()
    assert all(args[0] == "pull" for args in calls)
    assert evidence.data["resources"][0]["state"] == "planned"


def test_unknown_status_does_not_create_run_directory(tmp_path, capsys):
    root = tmp_path / "absent"
    assert main(["--artifacts", str(root), "status", str(uuid4())]) == 2
    assert not root.exists()


def test_server_never_logs_unexpected_exception_details(capsys):
    from rehearsal_orders.__main__ import Server

    server = object.__new__(Server)
    try:
        raise RuntimeError("postgresql://private:SECRET@private.invalid/db")
    except RuntimeError:
        server.handle_error(None, ("private.invalid", 5432))
    assert capsys.readouterr().err == "order request failed\n"


def test_app_credential_cannot_authenticate_as_database_admin(evidence, monkeypatch):
    from rehearsal_exercise.runner import remove_credentials

    creations = []
    queries = []

    class FakeDocker:
        def create(self, kind, role, args):
            creations.append((role, args))
            return {"id": role}

        def call(self, *args, **kwargs):
            return b""

    runner = Runner(evidence, Path.cwd(), docker=FakeDocker())

    def sql(instance, query, **kwargs):
        queries.append(query)
        return "source-cluster"

    monkeypatch.setattr(runner, "sql", sql)
    runner.instance("source")
    app_secret = (evidence.directory / ".source-credential").read_text()
    admin_secret = (evidence.directory / ".source-admin-credential").read_text()
    assert app_secret != admin_secret
    database_args = creations[-1][1]
    assert "POSTGRES_PASSWORD_FILE=/run/postgres-credential" in database_args
    assert any(".source-admin-credential,dst=/run/postgres-credential" in a for a in database_args)
    assert not any(".source-credential,dst=" in a for a in database_args)
    assert app_secret in queries[-1]
    assert admin_secret not in queries[-1]
    state = (evidence.directory / "state.json").read_text()
    assert app_secret not in state and admin_secret not in state
    remove_credentials(evidence)
    assert not list(evidence.directory.glob(".*-credential"))


@pytest.mark.parametrize(
    "diagnostic,absent",
    [
        (b"Error response from daemon: network exact-name not found", True),
        (b"Error: No such container: exact-name", True),
        (b"Error response from daemon: get exact-name: no such volume", True),
        (b"permission denied connecting to Docker", False),
        (b"template parsing error", False),
    ],
)
def test_inspection_only_classifies_explicit_absence(evidence, monkeypatch, diagnostic, absent):
    class FakeProcess:
        returncode = 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def communicate(self, *args, **kwargs):
            return b"", diagnostic

    monkeypatch.setattr("rehearsal_exercise.docker.subprocess.Popen", lambda *a, **k: FakeProcess())
    docker = Docker(evidence)
    if absent:
        assert DOCKER_CALL(docker, ["network", "inspect", "exact-name"], missing_ok=True) is None
    else:
        with pytest.raises(ExerciseError, match="command failed"):
            DOCKER_CALL(docker, ["network", "inspect", "exact-name"], missing_ok=True)
    assert diagnostic.decode() not in (evidence.directory / "events.jsonl").read_text()


def test_unsubmitted_plan_never_touches_docker(evidence):
    docker = Docker(evidence)
    docker.plan("network", "source-network")
    assert docker.cleanup()  # Docker.call is blocked by the ordinary test fixture.


def test_failure_of_native_restore_propagates_before_grants(evidence, monkeypatch):
    from rehearsal_exercise.evidence import atomic_json

    backup = evidence.directory / "backup.dump"
    backup.write_bytes(b"synthetic custom archive stand-in")
    atomic_json(evidence.directory / "manifest.json", manifest())
    evidence.data["backup"] = {"sha256": sha256(backup)}
    evidence.data["manifest_sha256"] = sha256(evidence.directory / "manifest.json")

    class FailedRestore:
        def call(self, args, **kwargs):
            assert "--single-transaction" in args
            assert "target-container" in args
            raise ExerciseError("native_restore: command failed (exit 1)")

    runner = Runner(evidence, Path.cwd(), docker=FailedRestore())
    monkeypatch.setattr(runner, "sql", lambda *args, **kwargs: "0")
    monkeypatch.setattr(runner, "grant", lambda *args: pytest.fail("grant after failed restore"))
    with pytest.raises(ExerciseError, match="native_restore"):
        runner.restore({"container": "target-container"})
