"""Explicit local integration: no lab configuration/credentials and no socket guard bypass."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from rehearsal_exercise.evidence import locked_root
from rehearsal_exercise.runner import perform_run, sha256


@pytest.mark.docker
@pytest.mark.parametrize("fault", ["none", "changed-record"])
def test_real_local_recovery(tmp_path, fault):
    with locked_root(tmp_path / "evidence") as root:
        result = perform_run(root, str(uuid4()), Path(__file__).resolve().parents[1], fault)
    assert result.data["outcome"] == ("passed" if fault == "none" else "failed")
    assert result.data["cleanup"] == "complete"
    assert sha256(result.directory / "backup.dump") == result.data["backup"]["sha256"]
    assert all(resource["state"] == "removed" for resource in result.data["resources"])
    if fault == "none":
        assert result.data["recovery"]["complete"]
        assert result.data["checks"]["restore_api"]["passed"]
        assert result.data["checks"]["post_restore_canary"]["passed"]
    else:
        difference = json.loads((result.directory / "restore-verification.json").read_text())
        assert list(difference["changed"].values()) == [["customer"]]
        assert not result.data["recovery"]["complete"]
        assert "post_restore_canary" not in result.data["checks"]
