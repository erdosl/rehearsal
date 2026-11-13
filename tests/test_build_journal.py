import json
import sqlite3
from pathlib import Path

import pytest

from rehearsal_build.journal import Journal, SafetyError, description, require_owner


def resource(journal):
    return journal.reserve(
        node="sim-pve01", vmid=9000, pool="sim-rehearsal", config_digest="a" * 64, now=100
    )


def live(record):
    return dict(
        description=description(record),
        node=record["node"],
        vmid=record["vmid"],
        pool=record["pool"],
        status="stopped",
        template=0,
    )


def test_intent_survives_restart_and_prevents_blind_retry(tmp_path):
    directory = tmp_path / "state"
    with Journal(directory) as journal:
        record = resource(journal)
        op = journal.intent(
            "create",
            "POST",
            "/nodes/sim-pve01/qemu",
            {"vmid": 9000},
            "sim-build@pve!bootstrap",
            record["resource"],
        )
        journal.update(op, "uncertain")
    with Journal(directory) as journal:
        assert journal.resource() == record
        assert journal.pending()[0]["id"] == op
        with pytest.raises(SafetyError, match="reconciled"):
            journal.intent(
                "create-again", "POST", "/nodes/sim-pve01/qemu", {}, "sim-build@pve!bootstrap"
            )
        journal.update(op, "complete", result={"reconciled": True})
        with pytest.raises(SafetyError, match="already attempted"):
            journal.intent("create", "POST", "/nodes/sim-pve01/qemu", {}, "sim-build@pve!bootstrap")


def test_upid_and_failed_outcome_are_retained(tmp_path):
    with Journal(tmp_path / "state") as journal:
        record = resource(journal)
        op = journal.intent(
            "import", "OPERATOR", "/config", {"disk": "scsi0"}, "root@pam", record["resource"]
        )
        journal.update(op, "running", upid="UPID:sim-pve01:0001:0002:0003:qmconfig:9000:root@pam:")
        with pytest.raises(SafetyError, match="identity changed"):
            journal.update(op, "running", upid="UPID:another-task")
        journal.update(op, "failed", result={"exitstatus": "disk import failed"})
        assert journal.operation(op)["upid"].endswith("root@pam:")
        assert journal.operation(op)["status"] == "failed"
        with pytest.raises(SafetyError, match="cannot be rewritten"):
            journal.update(op, "complete")


@pytest.mark.parametrize(
    "field,value",
    [("nonce", "wrong"), ("installation", "wrong"), ("run", "wrong"), ("resource", "wrong")],
)
def test_prefix_vmid_and_expiry_cannot_establish_ownership(tmp_path, field, value):
    with Journal(tmp_path / "state") as journal:
        record = resource(journal)
        observed = live(record)
        metadata = json.loads(observed["description"])
        metadata["rehearsal_ownership"][field] = value
        observed["description"] = json.dumps(metadata)
        with pytest.raises(SafetyError, match="ownership"):
            journal.check_cleanup(observed, tasks=[], volumes=[], now=999999, expiry_only=True)


def test_template_unrelated_pool_and_running_guest_are_protected(tmp_path):
    with Journal(tmp_path / "state") as journal:
        record = resource(journal)
        for changes in (
            {"template": 1},
            {"pool": "unrelated"},
            {"vmid": 9100},
            {"node": "unrelated"},
            {"status": "running"},
            {"lock": "create"},
        ):
            observed = live(record) | changes
            with pytest.raises(SafetyError):
                journal.check_cleanup(observed, tasks=[], volumes=[])


def test_unknown_tasks_and_unrecorded_volumes_block_cleanup(tmp_path):
    with Journal(tmp_path / "state") as journal:
        record = resource(journal)
        observed = live(record)
        with pytest.raises(SafetyError, match="tasks"):
            journal.check_cleanup(observed, tasks=[{"status": "running"}], volumes=[])
        with pytest.raises(SafetyError, match="volumes differ"):
            journal.check_cleanup(observed, tasks=[], volumes=["sim-store:unproven-volume"])
        op = journal.intent("create", "POST", "/create", {}, "synthetic", record["resource"])
        with pytest.raises(SafetyError, match="unresolved"):
            journal.check_cleanup(observed, tasks=[], volumes=[])
        journal.update(op, "complete")
        journal.record_volumes(record, op, ["sim-store:recorded-volume"])
        assert (
            journal.check_cleanup(observed, tasks=[], volumes=["sim-store:recorded-volume"])[
                "resource"
            ]
            == record["resource"]
        )


def test_volume_provenance_requires_completed_operation(tmp_path):
    with Journal(tmp_path / "state") as journal:
        record = resource(journal)
        op = journal.intent("import", "POST", "/config", {}, "synthetic", record["resource"])
        with pytest.raises(SafetyError, match="provenance"):
            journal.record_volumes(record, op, ["sim-store:disk"])


def test_active_lease_blocks_expiry_cleanup_and_cannot_be_stolen(tmp_path):
    with Journal(tmp_path / "state") as journal:
        record = resource(journal)
        journal.db.execute("INSERT INTO lease VALUES (?,?)", ("other-owner", 1000000))
        with pytest.raises(SafetyError, match="active lease"):
            journal.check_cleanup(live(record), tasks=[], volumes=[], now=999999, expiry_only=True)
        with pytest.raises(SafetyError, match="active lease"):
            journal.heartbeat(now=999999)
        journal.heartbeat(now=1000001)
        with pytest.raises(SafetyError, match="active lease"):
            journal.check_cleanup(live(record), tasks=[], volumes=[], now=1000001, expiry_only=True)


def test_file_lock_prevents_concurrent_supervision(tmp_path):
    with Journal(tmp_path / "state"):
        with pytest.raises(SafetyError, match="holds the lock"):
            Journal(tmp_path / "state")


@pytest.mark.parametrize(
    "body",
    [
        {"password": "fake"},
        {"nested": {"authorization": "fake"}},
        {"key": "-----BEGIN OPENSSH PRIVATE KEY-----"},
    ],
)
def test_secrets_are_rejected_before_durable_logging(tmp_path, body):
    with Journal(tmp_path / "state") as journal:
        with pytest.raises(SafetyError, match="secret-bearing"):
            journal.intent("bad", "POST", "/bad", body, "synthetic")
        assert journal.pending() == []


def test_state_database_symlink_and_foreign_resource_are_rejected(tmp_path):
    directory = tmp_path / "state"
    directory.mkdir(mode=0o700)
    target = tmp_path / "unrelated"
    target.write_text("preserve")
    (directory / "journal.sqlite3").symlink_to(target)
    with pytest.raises(SafetyError):
        Journal(directory)
    assert target.read_text() == "preserve"
    with Journal(tmp_path / "other") as journal:
        record = resource(journal)
        with pytest.raises(SafetyError):
            require_owner(record, {"description": "rehearsal-prefix-9000"})


def test_transaction_rolls_back_without_losing_prior_intent(tmp_path):
    with Journal(tmp_path / "state") as journal:
        resource(journal)
        with pytest.raises(RuntimeError):
            with journal.transaction():
                journal.event("transient", {"safe": True})
                raise RuntimeError("synthetic crash")
        assert journal.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        assert Path(journal.directory / "journal.sqlite3").stat().st_mode & 0o777 == 0o600


def test_existing_outcomes_and_missing_provenance_are_not_rewritten_on_reopen(tmp_path):
    directory = tmp_path / "state"
    with Journal(directory) as journal:
        record = resource(journal)
        old = journal.intent("old-start", "POST", "/start", {}, "synthetic", record["resource"])
        journal.update(old, "failed", result={"historical_outcome": "unavailable"})
        new = journal.intent("new-start", "POST", "/start", {}, "synthetic", record["resource"])
        journal.update(new, "uncertain")
        # Reproduce pre-evidence rows without inventing attribution events for them.
        journal.db.executemany(
            "UPDATE operations SET upid=? WHERE id=?",
            [("UPID:legacy-first", old), ("UPID:legacy-second", new)],
        )
        original = [dict(row) for row in journal.db.execute("SELECT * FROM operations")]
        original_events = [tuple(row) for row in journal.db.execute("SELECT * FROM events")]
    with Journal(directory) as journal:
        assert [dict(row) for row in journal.db.execute("SELECT * FROM operations")] == original
        assert journal.db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert [tuple(row) for row in journal.db.execute("SELECT * FROM events")] == original_events
        assert journal.pending()[0]["id"] == new
        with pytest.raises(SafetyError, match="cannot be rewritten"):
            journal.update(old, "complete")
        with pytest.raises(SafetyError, match="unresolved"):
            journal.check_cleanup(live(record), tasks=[], volumes=[], now=999999, expiry_only=True)


def test_upid_attribution_and_attachment_commit_atomically(tmp_path, monkeypatch):
    with Journal(tmp_path / "state") as journal:
        opid = journal.intent("start", "POST", "/start", {}, "synthetic")

        def fail(*_):
            raise OSError("synthetic evidence write failure")

        monkeypatch.setattr(journal, "event", fail)
        with pytest.raises(OSError):
            journal.update(opid, "running", upid="UPID:synthetic", upid_source="mutation-response")
        assert journal.operation(opid)["status"] == "intent"
        assert journal.operation(opid)["upid"] is None


@pytest.mark.parametrize(
    "damage",
    [
        "DROP TABLE events",
        "DELETE FROM installation",
        "PRAGMA user_version=2",
        "ALTER TABLE operations RENAME COLUMN upid TO incompatible",
    ],
)
def test_incompatible_journal_is_rejected_without_repair_or_identity_replacement(tmp_path, damage):
    directory = tmp_path / "state"
    with Journal(directory) as journal:
        journal.db.execute(damage)
    path = directory / "journal.sqlite3"
    original = path.read_bytes()
    for _ in range(2):  # Initialization failures must release the file lock too.
        with pytest.raises(SafetyError, match="preserve it for inspection"):
            Journal(directory)
        assert path.read_bytes() == original


def test_legacy_journal_copy_preserves_rows_and_unrecorded_provenance(tmp_path):
    with Journal(tmp_path / "legacy") as journal:
        record = resource(journal)
        opid = journal.intent("old-start", "POST", "/start", {}, "synthetic", record["resource"])
        journal.db.execute(
            "UPDATE operations SET status='uncertain',upid='UPID:legacy' WHERE id=?", (opid,)
        )
        original = journal.operation(opid)
        installation = journal.installation
        copy = tmp_path / "copy"
        copy.mkdir(mode=0o700)
        path = copy / "journal.sqlite3"
        with sqlite3.connect(path) as destination:
            journal.db.backup(destination)
        path.chmod(0o600)
    with Journal(copy) as copied:
        assert copied.installation == installation
        assert copied.operation(opid) == original
        assert copied.db.execute("SELECT count(*) FROM events").fetchone()[0] == 0
        assert copied.pending()[0]["status"] == "uncertain"


def test_secret_bearing_operation_metadata_is_rejected(tmp_path):
    with Journal(tmp_path / "state") as journal:
        with pytest.raises(SafetyError, match="secret-bearing"):
            journal.intent("Authorization: Bearer SYNTHETIC", "POST", "/start", {}, "synthetic")
        assert not journal.pending()


def test_historical_failed_row_is_not_reported_as_confirmed_task_failure(tmp_path):
    with Journal(tmp_path / "state") as journal:
        opid = journal.intent("historical", "OPERATOR", "/start", {}, "synthetic")
        journal.update(opid, "failed", result={"historical_outcome": "unavailable"})
        assert journal.outcome_evidence(opid) == {
            "task_outcome": "unknown",
            "upid_sources": ["unrecorded"],
        }


def test_operator_outcome_evidence_is_appended_atomically(tmp_path):
    with Journal(tmp_path / "state") as journal:
        opid = journal.intent("historical", "OPERATOR", "/start", {}, "synthetic")
        journal.update(opid, "uncertain")
        reason = {"historical_outcome": "unavailable", "reason": "synthetic operator evidence"}
        journal.update(opid, "failed", result=reason, upid_source="operator-supplied")
        transition = json.loads(
            journal.db.execute(
                "SELECT body FROM events WHERE kind='operation-transition' ORDER BY id DESC LIMIT 1"
            ).fetchone()[0]
        )
        assert transition["previous_status"] == "uncertain"
        assert transition["status"] == "failed"
        assert transition["source"] == "operator-supplied"
        assert transition["evidence"] == reason
        assert journal.outcome_evidence(opid)["task_outcome"] == "unknown"
