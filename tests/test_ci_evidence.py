import json
from uuid import uuid4

from rehearsal_exercise.ci import cleanup, export, public_run
from rehearsal_exercise.evidence import Evidence, locked_root


def test_export_excludes_credentials_records_and_free_text(tmp_path):
    root = tmp_path / "runs"
    directory = root / "test_real_local_recovery_none_0" / "evidence" / str(uuid4())
    directory.mkdir(parents=True)
    data = {
        "run": directory.name,
        "outcome": "failed",
        "cleanup": "pending",
        "fault": "none",
        "failure": "postgresql://private:SECRET@private.invalid/db",
        "resources": [{"password": "SECRET"}],
        "versions": {"server": "password=SECRET"},
        "checks": {
            "restore_data": {
                "passed": False,
                "actual_count": 100,
                "changed": {"password=SECRET": ["SECRET"]},
            }
        },
        "recovery": {"duration_seconds": "SECRET"},
        "phases": [{"name": "SECRET", "status": "SECRET"}],
    }
    (directory / "report.json").write_text(json.dumps(data))
    (directory / "backup.dump").write_bytes(b"SECRET")
    (directory / ".restore-credential").write_text("SECRET")
    output = tmp_path / "publish" / "recovery.json"
    summary = export(root, output)
    assert "SECRET" not in output.read_text()
    assert summary["runs"][0]["checks"]["restore_data"]["changed_count"] == 1
    assert list(output.parent.iterdir()) == [output]
    assert not summary["backups_uploaded"]


def test_export_rejects_nonfinite_and_boolean_durations():
    for value in (float("nan"), float("inf"), True, -1):
        data = {"run": str(uuid4()), "outcome": "passed", "recovery": {"duration_seconds": value}}
        assert public_run(data)["recovery"]["duration_seconds"] is None


def test_ci_cleanup_preserves_interruption_and_backup(tmp_path):
    root = tmp_path / "runs"
    parent = root / "test_real_local_recovery_none_0" / "evidence"
    with locked_root(parent) as protected:
        evidence = Evidence(protected, str(uuid4()), create=True)
        (evidence.directory / ".source-credential").write_text("fake-credential")
        (evidence.directory / ".source-admin-credential").write_text("fake-admin")
        (evidence.directory / "backup.dump").write_bytes(b"synthetic archive stand-in")
    assert cleanup(root)
    report = json.loads((evidence.directory / "report.json").read_text())
    assert report["outcome"] == "cancelled"
    assert report["cleanup"] == "complete"
    assert not list(evidence.directory.glob(".*-credential"))
    assert (evidence.directory / "backup.dump").read_bytes() == b"synthetic archive stand-in"
