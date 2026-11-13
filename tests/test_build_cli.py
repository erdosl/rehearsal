import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from rehearsal.errors import InventoryError
from rehearsal_build.__main__ import main
from rehearsal_build.config import BuildConfig
from rehearsal_build.journal import Journal, SafetyError


def test_validate_is_offline_and_does_not_load_credentials(monkeypatch, capsys):
    monkeypatch.setattr(
        "rehearsal_build.__main__.load_token", lambda _: pytest.fail("credential read")
    )
    assert main(["validate", "--config", "examples/first-guest.toml"]) == 0
    assert json.loads(capsys.readouterr().out)["vmid"] == 9000


def test_bootstrap_journal_can_be_inspected_before_resource_reservation(
    monkeypatch, capsys, tmp_path
):
    config = replace(
        BuildConfig.load("examples/first-guest.toml"), state_directory=str(tmp_path / "state")
    )
    with Journal(Path(config.state_directory)):
        pass
    monkeypatch.setattr(BuildConfig, "load", lambda _: config)
    monkeypatch.setattr(
        "rehearsal_build.__main__.load_token", lambda _: pytest.fail("credential read")
    )
    assert main(["status", "--config", "examples/first-guest.toml"]) == 0
    assert json.loads(capsys.readouterr().out)["resource"] is None


@pytest.mark.parametrize(
    "arguments,environment",
    [
        ([], None),
        (["--live"], None),
        (["--live", "--exercise", "first-guest"], None),
        (["--exercise", "first-guest"], "1"),
    ],
)
def test_mutations_require_all_explicit_opt_ins(monkeypatch, arguments, environment, tmp_path):
    monkeypatch.delenv("REHEARSAL_LIVE", raising=False)
    if environment:
        monkeypatch.setenv("REHEARSAL_LIVE", environment)
    monkeypatch.setattr(
        "rehearsal_build.__main__.load_token", lambda _: pytest.fail("credential read")
    )
    assert (
        main(
            [
                "exercise",
                "--config",
                "examples/first-guest.toml",
                "--operation",
                "reserve",
                *arguments,
            ]
        )
        == 2
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("endpoint", "http://192.0.2.80:8006"),
        ("endpoint", "https://user:fake-secret@192.0.2.80:8006"),
        ("vmid", 9100),
        ("memory_mib", 8192),
        ("disk_gib", 6),
        ("bridge", "vmbr0"),
        ("guest_mac", "ff:ff:ff:ff:ff:ff"),
    ],
)
def test_unsafe_configuration_is_rejected_without_echoing_values(tmp_path, field, value):
    data = asdict(BuildConfig.load("examples/first-guest.toml"))
    data[field] = value
    content = "[build]\n" + "\n".join(f"{key} = {json.dumps(item)}" for key, item in data.items())
    path = tmp_path / "build.toml"
    path.write_text(content)
    with pytest.raises(SafetyError) as error:
        BuildConfig.load(path)
    assert "fake-secret" not in str(error.value)


def test_operator_supplied_upid_is_not_labeled_as_an_http_response(monkeypatch, capsys, tmp_path):
    config = replace(
        BuildConfig.load("examples/first-guest.toml"), state_directory=str(tmp_path / "state")
    )
    with Journal(Path(config.state_directory)) as journal:
        opid = journal.intent("import", "OPERATOR", "/config", {}, "root@pam")
    request = tmp_path / "result.json"
    request.write_text(json.dumps(dict(operation=opid, state="running", upid="UPID:synthetic")))
    monkeypatch.setattr(BuildConfig, "load", lambda _: config)
    monkeypatch.setattr(
        "rehearsal_build.__main__.load_token", lambda _: pytest.fail("credential read")
    )
    monkeypatch.setenv("REHEARSAL_LIVE", "1")
    assert (
        main(
            [
                "exercise",
                "--config",
                "unused.toml",
                "--live",
                "--exercise",
                "first-guest",
                "--operation",
                "operator-result",
                "--request",
                str(request),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["result"]["state"] == "running"
    with Journal(Path(config.state_directory)) as journal:
        attribution = json.loads(
            journal.db.execute("SELECT body FROM events WHERE kind='upid-attribution'").fetchone()[
                0
            ]
        )
        assert attribution["source"] == "operator-supplied"
        assert attribution["request"] is None


def test_credential_load_failure_is_reported_without_traceback_or_secret(
    monkeypatch, capsys, tmp_path
):
    config = replace(
        BuildConfig.load("examples/first-guest.toml"), state_directory=str(tmp_path / "state")
    )
    monkeypatch.setattr(BuildConfig, "load", lambda _: config)
    monkeypatch.setenv("REHEARSAL_LIVE", "1")

    def failure(_):
        raise InventoryError("credentials_error", "SYNTHETIC-ERROR-CONTENT")

    monkeypatch.setattr("rehearsal_build.__main__.load_token", failure)
    assert (
        main(
            [
                "exercise",
                "--config",
                "unused",
                "--live",
                "--exercise",
                "first-guest",
                "--operation",
                "read",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert not captured.out
    assert json.loads(captured.err)["error"] == "supervised_operation_failed"
    assert "SYNTHETIC-ERROR-CONTENT" not in captured.err


def test_status_reports_incompatible_journal_without_modifying_it(monkeypatch, capsys, tmp_path):
    config = replace(
        BuildConfig.load("examples/first-guest.toml"), state_directory=str(tmp_path / "state")
    )
    with Journal(Path(config.state_directory)) as journal:
        journal.db.execute("PRAGMA user_version=2")
    path = Path(config.state_directory) / "journal.sqlite3"
    original = path.read_bytes()
    monkeypatch.setattr(BuildConfig, "load", lambda _: config)
    assert main(["status", "--config", "unused"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.err)["error"] == "supervised_operation_failed"
    assert path.read_bytes() == original


def test_operator_terminal_result_requires_explicit_evidence(monkeypatch, capsys, tmp_path):
    config = replace(
        BuildConfig.load("examples/first-guest.toml"), state_directory=str(tmp_path / "state")
    )
    with Journal(Path(config.state_directory)) as journal:
        opid = journal.intent("import", "OPERATOR", "/config", {}, "root@pam")
    request = tmp_path / "result.json"
    request.write_text(json.dumps({"operation": opid, "state": "failed"}))
    monkeypatch.setattr(BuildConfig, "load", lambda _: config)
    monkeypatch.setenv("REHEARSAL_LIVE", "1")
    assert (
        main(
            [
                "exercise",
                "--config",
                "unused",
                "--live",
                "--exercise",
                "first-guest",
                "--operation",
                "operator-result",
                "--request",
                str(request),
            ]
        )
        == 2
    )
    capsys.readouterr()
    with Journal(Path(config.state_directory)) as journal:
        assert journal.operation(opid)["status"] == "intent"


def test_status_redacts_legacy_sensitive_labels_without_loading_credentials(
    monkeypatch, capsys, tmp_path
):
    config = replace(
        BuildConfig.load("examples/first-guest.toml"), state_directory=str(tmp_path / "state")
    )
    with Journal(Path(config.state_directory)) as journal:
        opid = journal.intent("legacy", "OPERATOR", "/start", {}, "synthetic")
        journal.db.execute(
            "UPDATE operations SET label=?,status='failed' WHERE id=?",
            ("Authorization: Bearer SYNTHETIC-LEGACY-CREDENTIAL", opid),
        )
    monkeypatch.setattr(BuildConfig, "load", lambda _: config)
    monkeypatch.setattr(
        "rehearsal_build.__main__.load_token", lambda _: pytest.fail("credential read")
    )
    assert main(["status", "--config", "unused"]) == 0
    captured = capsys.readouterr()
    assert "SYNTHETIC-LEGACY-CREDENTIAL" not in captured.out + captured.err
    row = json.loads(captured.out)["operations"][0]
    assert row["label"] == "[REDACTED]" and row["task_outcome"] == "unknown"
    with Journal(Path(config.state_directory)) as journal:
        assert journal.operation(opid)["label"].endswith("SYNTHETIC-LEGACY-CREDENTIAL")
