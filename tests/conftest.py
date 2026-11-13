import json
import socket
from importlib.resources import files

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("network access is forbidden in offline tests")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)


@pytest.fixture
def config_path(tmp_path):
    path = tmp_path / "rehearsal.toml"
    path.write_text(
        'schema_version = 1\n[inventory]\nnodes = ["sim-pve01"]\nfixture = "builtin:healthy"\n'
    )
    return path


@pytest.fixture
def fixture_document():
    return json.loads(files("rehearsal").joinpath("fixtures", "healthy.json").read_text())
