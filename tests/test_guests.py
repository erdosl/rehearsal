import hashlib
import io
import json
import shlex
import time
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from rehearsal.credentials import APIToken
from rehearsal_build.journal import Journal, SafetyError
from rehearsal_exercise import guest_agent
from rehearsal_exercise.evidence import Evidence, ExerciseError, locked_root
from rehearsal_exercise.guest_config import GuestConfig
from rehearsal_exercise.guest_provider import PreparedAPI
from rehearsal_exercise.guest_transport import SSH
from rehearsal_exercise.guests import GuestRunner, main
from rehearsal_exercise.manifest import manifest
from rehearsal_exercise.runner import Runner, perform_run
from rehearsal_exercise.verification import (
    EXPECTED_COLUMNS,
    EXPECTED_CONSTRAINTS,
    EXPECTED_DEFINITIONS,
    EXPECTED_INDEXES,
    RECORDS_SQL,
    SCHEMA_SQL,
)


def write_config(config, path):
    values = asdict(config)
    guests = {role: values.pop(role) for role in ("source", "restore")}
    lines = ["[proxmox]", *[f"{k} = {json.dumps(v)}" for k, v in values.items()]]
    for role, guest in guests.items():
        owner = guest.pop("ownership")
        lines += [f"[guests.{role}]", *[f"{k} = {json.dumps(v)}" for k, v in guest.items()]]
        lines += [
            f"[guests.{role}.ownership]",
            *[f"{k} = {json.dumps(v)}" for k, v in owner.items()],
        ]
    path.write_text("\n".join(lines))
    return path


@pytest.fixture
def config(tmp_path):
    config = GuestConfig.load(Path(__file__).parents[1] / "examples/prepared-guests.toml")
    guests = {}
    for role in ("source", "restore"):
        guest = getattr(config, role)
        key = tmp_path / (role + ".key")
        key.write_text("fake private key reference; not a usable key")
        key.chmod(0o600)
        hosts = tmp_path / (role + "_known_hosts")
        hosts.write_text("rehearsal-" + guest.ownership["resource"] + " ssh-ed25519 " + role + "\n")
        hosts.chmod(0o644)
        guests[role] = replace(
            guest,
            key_file=str(key),
            known_hosts=str(hosts),
            isolated_at=time.time(),
            lease_expires=time.time() + 1800,
        )
    return replace(config, **guests)


@pytest.fixture
def context(tmp_path):
    with locked_root(tmp_path / "evidence") as root, Journal(tmp_path / "requests") as journal:
        yield Evidence(root, str(uuid4()), create=True), journal


@pytest.mark.parametrize(
    "change", ["same-id", "same-machine", "same-storage", "protected", "bad-time"]
)
def test_configuration_fences_wrong_targets(config, tmp_path, change):
    target = config.restore
    if change == "same-id":
        target = replace(target, vmid=config.source.vmid)
    elif change == "same-machine":
        target = replace(target, machine_id=config.source.machine_id)
    elif change == "same-storage":
        target = replace(target, volumes=config.source.volumes)
    elif change == "protected":
        target = replace(target, vmid=9000)
    else:
        target = replace(target, isolated_at="SECRET")
    path = write_config(replace(config, restore=target), tmp_path / "bad.toml")
    with pytest.raises(ExerciseError) as error:
        GuestConfig.load(path)
    assert "SECRET" not in str(error.value)


def test_ssh_pins_identity_and_keeps_ambiguous_writes_pending(config, context, monkeypatch):
    evidence, journal = context
    ssh = SSH(config.source, journal, evidence, lambda: None)
    argv = ssh.argv("sql")
    assert "StrictHostKeyChecking=yes" in argv
    assert "IdentitiesOnly=yes" in argv and "IdentityAgent=none" in argv
    assert "ProxyCommand=none" in argv and "ForwardAgent=no" in argv
    attempts = []

    def lost(argv, data):
        attempts.append(argv)
        raise RuntimeError("postgresql://private:SECRET@private.invalid/db")

    monkeypatch.setattr(ssh, "_execute", lost)
    with pytest.raises(ExerciseError) as error:
        ssh.run("sql", b"password=SECRET", mutation=True)
    assert "SECRET" not in str(error.value)
    assert len(journal.pending()) == 1
    with pytest.raises(SafetyError, match="unresolved"):
        ssh.run("sql", b"another write", mutation=True)
    assert len(attempts) == 1
    assert "SECRET" not in str([dict(row) for row in journal.db.execute("SELECT * FROM events")])
    op = journal.pending()[0]
    receipt = json.loads(op["desired"]) | {"status": "complete"}
    monkeypatch.setattr(ssh, "_execute", lambda *args: json.dumps(receipt).encode())
    ssh.reconcile(op["id"])
    assert not journal.pending()
    assert journal.operation(op["id"])["status"] == "complete"


def test_receipt_for_another_guest_cannot_resolve_uncertainty(config, context, monkeypatch):
    evidence, journal = context
    ssh = SSH(config.source, journal, evidence, lambda: None)
    desired = {"owner": ssh.owner, "operation": "restore", "input_sha256": "0" * 64}
    opid = journal.intent("restore", "SSH", "/guests/9101/restore", desired, "prepared-guest-ssh")
    journal.update(opid, "uncertain")
    monkeypatch.setattr(
        ssh,
        "_execute",
        lambda *args: json.dumps(desired | {"owner": {}, "status": "complete"}).encode(),
    )
    with pytest.raises(ExerciseError, match="receipt unavailable"):
        ssh.reconcile(opid)
    assert journal.pending()[0]["id"] == opid


class PVE:
    def __init__(self, guest):
        self.guest = guest
        self.config = {
            "description": json.dumps({"rehearsal_ownership": guest.ownership}),
            "onboot": 0,
            "template": 0,
            "net0": f"virtio={guest.mac},bridge={guest.bridge},firewall=1,link_down=0",
            "scsi0": guest.volumes[0] + ",size=12G",
        }
        self.methods = []
        self.history_missing = False

    def request(self, request):
        self.methods.append(request.method)
        path = request.url.path
        if "/tasks/" in path:
            if self.history_missing:
                return httpx.Response(404)
            data = [] if path.endswith("/log") else {"status": "stopped", "exitstatus": "OK"}
        elif path.endswith("/cluster/resources"):
            data = [{"node": self.guest.node, "pool": self.guest.pool, "vmid": self.guest.vmid}]
        elif path.endswith("/config"):
            data = self.config
        elif path.endswith("/status/current"):
            data = {"status": "running"}
        elif path.endswith("/tasks"):
            data = []
        elif path.endswith("/firewall/options"):
            data = {"enable": 1}
        else:
            raise AssertionError(path)
        return httpx.Response(200, json={"data": data})


@pytest.mark.parametrize("damage", ["owner", "template", "disk", "nic", "lock"])
def test_live_metadata_fences_cleanup_and_execution(config, context, damage):
    _, journal = context
    lab = PVE(config.source)
    token = APIToken("sim@pve!inventory", "00000000-1111-2222-3333-444444444444")
    api = PreparedAPI(
        config, config.source, journal, token, transport=httpx.MockTransport(lab.request)
    )
    try:
        assert api.owned()["vmid"] == config.source.vmid
        if damage == "owner":
            lab.config["description"] = "{}"
        elif damage == "template":
            lab.config["template"] = 1
        elif damage == "disk":
            lab.config["scsi0"] = "sim-storage:unrelated-disk"
        elif damage == "nic":
            lab.config["net1"] = "virtio=02:00:00:00:00:ff,bridge=vmbr0"
        else:
            lab.config["lock"] = "backup"
        with pytest.raises(SafetyError):
            api.owned()
        with pytest.raises(SafetyError, match="no Proxmox mutations"):
            api.mutate(
                "forbidden", "POST", api.vm_path + "/status/start", {}, postcondition=lambda: True
            )
        assert set(lab.methods) == {"GET"}
    finally:
        api.close()


@pytest.mark.parametrize("missing", [False, True])
def test_reuse_recorded_upid_reconciliation_without_mutations(config, context, missing):
    _, journal = context
    lab = PVE(config.source)
    lab.history_missing = missing
    token = APIToken("sim@pve!inventory", "00000000-1111-2222-3333-444444444444")
    api = PreparedAPI(
        config, config.source, journal, token, transport=httpx.MockTransport(lab.request)
    )
    opid = journal.intent(
        "prepared-start", "POST", api.vm_path + "/status/start", {}, token.token_id
    )
    upid = (
        f"UPID:{config.source.node}:00000001:00000002:{int(time.time()):08X}:"
        f"qmstart:{config.source.vmid}:{token.token_id}:"
    )
    journal.update(opid, "uncertain", upid=upid, upid_source="operator-supplied")
    try:
        if missing:
            with pytest.raises(SafetyError):
                api.reconcile_recorded(opid, lambda: {"running": True})
            assert journal.pending()[0]["upid"] == upid
        else:
            api.reconcile_recorded(opid, lambda: {"running": True})
            assert not journal.pending()
        assert set(lab.methods) == {"GET"}
    finally:
        api.close()


def test_guest_lease_never_overwrites_or_releases_another_owner(tmp_path, monkeypatch):
    root = tmp_path / "lease"
    root.mkdir(mode=0o700)
    owner = {"run": str(uuid4())}
    with guest_agent.lease(root, owner, "claim"):
        pass
    with pytest.raises(RuntimeError), guest_agent.lease(root, {"run": str(uuid4())}, "claim"):
        pass
    with pytest.raises(RuntimeError), guest_agent.lease(root, {}, "sql"):
        pass
    monkeypatch.setattr(guest_agent, "active", lambda unit: b"active")
    with pytest.raises(RuntimeError), guest_agent.lease(root, owner, "release"):
        pass
    assert (root / "owner.json").exists()
    monkeypatch.setattr(guest_agent, "active", lambda unit: b"inactive")
    with guest_agent.lease(root, owner, "release"):
        pass
    assert not (root / "owner.json").exists()


def test_corrupt_transfer_is_rejected_before_native_restore(monkeypatch):
    called = []
    monkeypatch.setattr(guest_agent, "command", lambda *args: called.append(args))
    with pytest.raises(RuntimeError, match="checksum"):
        guest_agent.perform("restore", b"corrupt", "0" * 64)
    assert not called


def test_release_fingerprint_checks_installed_modules(tmp_path):
    from importlib.resources import files
    from zipfile import ZipFile

    path = tmp_path / "release.whl"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "rehearsal_orders/domain.py",
            files("rehearsal_orders").joinpath("domain.py").read_bytes(),
        )
    assert guest_agent.release_fingerprint(path) == hashlib.sha256(path.read_bytes()).hexdigest()
    with ZipFile(path, "w") as archive:
        archive.writestr("rehearsal_orders/domain.py", b"different code")
    with pytest.raises(RuntimeError, match="installed release"):
        guest_agent.release_fingerprint(path)


def test_remote_receipts_survive_failure_and_release(tmp_path, monkeypatch, capsys):
    import sys

    root = tmp_path / "agent"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(guest_agent, "LEASE_ROOT", root)
    owner = {key: str(uuid4()) for key in ("run", "installation", "resource")}

    def invoke(operation, request, data=b""):
        argv = ["agent", operation, "--request", request]
        for key, value in owner.items():
            argv += ["--" + key, value]
        if operation == "restore":
            argv += ["--sha256", hashlib.sha256(data).hexdigest()]
        monkeypatch.setattr(sys, "argv", argv)
        monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(data)))
        return guest_agent.main()

    claim = str(uuid4())
    assert invoke("claim", claim) == 0
    assert json.loads((root / f"request-{claim}.json").read_text())["status"] == "complete"
    failed = str(uuid4())

    def fail(*args):
        raise RuntimeError("postgresql://private:SECRET@private.invalid/db")

    monkeypatch.setattr(guest_agent, "command", fail)
    assert invoke("restore", failed, b"bad archive") == 1
    assert json.loads((root / f"request-{failed}.json").read_text())["status"] == "failed"
    assert "SECRET" not in capsys.readouterr().err
    monkeypatch.setattr(guest_agent, "active", lambda unit: b"inactive")
    released = str(uuid4())
    assert invoke("release", released) == 0
    assert not (root / "owner.json").exists()
    receipt = json.loads((root / f"request-{released}.json").read_text())
    assert receipt["status"] == "complete" and receipt["owner"] == owner


@pytest.mark.parametrize("malformed", [False, True])
def test_wrong_guest_readiness_blocks_claim(config, context, monkeypatch, malformed):
    evidence, journal = context
    apis = {
        role: SimpleNamespace(simulated=True, owned=lambda: {"status": "running"})
        for role in ("source", "restore")
    }
    runner = GuestRunner(evidence, Path.cwd(), config, journal, apis)
    monkeypatch.setattr(
        runner.ssh["source"],
        "_execute",
        lambda *args: (
            b"malformed response"
            if malformed
            else json.dumps(
                {
                    "machine_id": "f" * 32,
                    "release_sha256": config.source.release_sha256,
                    "app_target_valid": True,
                }
            ).encode()
        ),
    )
    with pytest.raises(ExerciseError, match="identity"):
        runner.instance("source")
    assert not journal.pending() and not evidence.data["resources"]
    wrong = {
        "guest_role": "source",
        "vmid": config.restore.vmid,
        "machine_id": config.restore.machine_id,
        "volumes": config.restore.volumes,
    }
    with pytest.raises(ExerciseError, match="target differs"):
        runner.native(wrong, ["psql"], mutation=True)


def test_cleanup_never_uses_another_exercises_release(config, context, monkeypatch):
    evidence, journal = context
    evidence.data["resources"].append(
        {"kind": "prepared-guest", "role": "source", "state": "leased"}
    )
    apis = {
        role: SimpleNamespace(simulated=True, owned=lambda: {"status": "running"})
        for role in ("source", "restore")
    }
    runner = GuestRunner(evidence, Path.cwd(), config, journal, apis)
    previous_owner = {**runner.ssh["source"].owner, "run": str(uuid4())}
    opid = journal.intent(
        "old-release",
        "SSH",
        f"/guests/{config.source.vmid}/release",
        {"owner": previous_owner},
        "prepared-guest-ssh",
    )
    journal.update(opid, "complete")
    monkeypatch.setattr(
        runner,
        "probe",
        lambda role: {"lease_owner": None, "app_state": "inactive", "database_state": "inactive"},
    )
    assert not runner.cleanup()
    assert evidence.data["cleanup"] == "pending"
    assert len(list(journal.db.execute("SELECT id FROM operations"))) == 1


def test_failed_admission_does_not_stop_unrelated_database_services(config, context, monkeypatch):
    evidence, journal = context
    apis = {
        role: SimpleNamespace(simulated=True, owned=lambda: {"status": "running"})
        for role in ("source", "restore")
    }
    runner = GuestRunner(evidence, Path.cwd(), config, journal, apis)
    commands = []
    monkeypatch.setattr(runner, "probe", lambda role: {})
    monkeypatch.setattr(
        runner.ssh["source"],
        "_execute",
        lambda argv, data: commands.append(shlex.split(argv[-1])[3]) or b"{}",
    )
    monkeypatch.setattr(runner, "sql", lambda *args, **kwargs: "1")
    with pytest.raises(ExerciseError, match="unrelated databases"):
        runner.instance("source")
    assert not runner.cleanup()
    assert commands == ["claim"]
    assert evidence.data["cleanup"] == "pending"


@pytest.mark.parametrize("live,environment", [(False, "1"), (True, "0")])
def test_live_guest_commands_require_both_opt_ins(config, tmp_path, monkeypatch, live, environment):
    path = write_config(config, tmp_path / "guest.toml")
    monkeypatch.setenv("REHEARSAL_LIVE", environment)
    with pytest.raises(SystemExit) as error:
        main(
            [
                "run",
                "--config",
                str(path),
                "--artifacts",
                str(tmp_path / "absent"),
                *(["--live"] if live else []),
            ]
        )
    assert error.value.code == 2
    assert not (tmp_path / "absent").exists()


class GuestSimulation:
    """Protocol fixtures only. These are not SSH, PostgreSQL or guest execution."""

    def __init__(self, runner, changed):
        self.runner, self.changed = runner, changed
        self.rows = {"source": [], "restore": []}
        self.state = {
            role: {"database_state": "active", "app_state": "inactive", "lease_owner": None}
            for role in self.rows
        }

    def execute(self, role, argv, data):
        operation = shlex.split(argv[-1])[3]
        guest = getattr(self.runner.config, role)
        if operation == "probe":
            result = {
                **self.state[role],
                "machine_id": guest.machine_id,
                "release_sha256": guest.release_sha256,
                "app_target_valid": True,
            }
        elif operation == "claim":
            self.state[role]["lease_owner"] = self.runner.ssh[role].owner
            result = {}
        elif operation == "release":
            self.state[role]["lease_owner"] = None
            result = {}
        elif operation in ("app-start", "app-stop", "db-stop"):
            self.state[role]["database_state" if operation == "db-stop" else "app_state"] = (
                "active" if operation == "app-start" else "inactive"
            )
            result = {}
        elif operation == "sql":
            query = data.decode()
            if query == RECORDS_SQL:
                result = self.rows[role]
            elif query == SCHEMA_SQL:
                result = {
                    "tables": ["orders", "schema_version"],
                    "version": [1],
                    "columns": EXPECTED_COLUMNS,
                    "constraints": EXPECTED_CONSTRAINTS,
                    "definitions": EXPECTED_DEFINITIONS,
                    "enforcement": {key: [True, True] for key in EXPECTED_CONSTRAINTS},
                    "indexes": sorted(EXPECTED_INDEXES),
                    "index_definitions": EXPECTED_INDEXES,
                }
            elif "system_identifier" in query:
                return ("1001" if role == "source" else "2002").encode()
            elif "listen_addresses" in query:
                return b"localhost"
            elif "data_directory" in query:
                return b"/var/lib/postgresql/18/main"
            elif query == "SHOW port;":
                return b"5432"
            elif "server_version" in query:
                return b"18.7"
            elif "pg_roles" in query:
                return b"1"
            elif "count(*)" in query:
                return b"0"
            else:
                return b""
        elif operation == "http":
            result = []
            for item in json.loads(data):
                if item["path"] == "/health/ready":
                    result.append({"status": 200, "body": {}})
                elif item["method"] == "POST":
                    row = {
                        **item["body"],
                        "total_cents": item["body"]["quantity"] * item["body"]["unit_price_cents"],
                    }
                    existing = next((r for r in self.rows[role] if r["id"] == row["id"]), None)
                    if existing is None:
                        self.rows[role].append(row)
                    result.append({"status": 200 if existing else 201, "body": row})
                else:
                    row = next(r for r in self.rows[role] if item["path"].endswith(r["id"]))
                    result.append({"status": 200, "body": row})
        elif operation in ("dump-version", "restore-version"):
            return b"PostgreSQL 18.7"
        elif operation == "versions":
            result = {"python": "3.12.16", "psycopg": "3.3.9", "libpq": 180006}
        elif operation == "dump":
            archive = json.dumps(self.rows[role]).encode()
            return (
                json.dumps(
                    {"sha256": hashlib.sha256(archive).hexdigest(), "bytes": len(archive)}
                ).encode()
                + b"\n"
                + archive
            )
        elif operation == "restore":
            self.rows[role] = json.loads(data)
            if self.changed:
                self.rows[role][0]["customer"] = "ALTERED"
            result = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        elif operation == "list":
            return b"fixture archive contents"
        else:
            raise AssertionError(operation)
        return json.dumps(result).encode()


@pytest.mark.parametrize("changed", [False, True])
def test_shared_guest_workflow_contract(config, tmp_path, monkeypatch, changed):
    assert GuestRunner.execute is Runner.execute
    with locked_root(tmp_path / "exercise") as root, Journal(tmp_path / "requests") as journal:
        apis = {
            role: SimpleNamespace(simulated=True, owned=lambda: {"status": "running"})
            for role in ("source", "restore")
        }

        def factory(evidence, project, fault):
            runner = GuestRunner(evidence, project, config, journal, apis)
            simulation = GuestSimulation(runner, changed)
            for role, ssh in runner.ssh.items():
                monkeypatch.setattr(
                    ssh,
                    "_execute",
                    lambda argv, data, role=role: simulation.execute(role, argv, data),
                )
            return runner

        evidence = perform_run(
            root, str(uuid4()), Path(__file__).parents[1], runner_factory=factory
        )
        assert evidence.data["outcome"] == ("failed" if changed else "passed")
        assert evidence.data["simulated"] is True
        assert evidence.data["cleanup"] == "complete"
        assert not journal.pending()
        assert json.loads((evidence.directory / "manifest.json").read_text()) == manifest()
        assert (evidence.directory / "backup.dump").is_file()
        assert all(
            r["state"] == "retained_guest_services_stopped" for r in evidence.data["resources"]
        )
        if changed:
            assert not evidence.data["checks"]["restore_data"]["passed"]
            assert "post_restore_canary" not in evidence.data["checks"]
        else:
            assert evidence.data["checks"]["post_restore_canary"]["actual_count"] == 101
