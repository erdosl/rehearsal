import json
import socket
from importlib.resources import files

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--docker-exercise", action="store_true", help="enable local Docker integration"
    )


@pytest.fixture(autouse=True)
def docker_guard(request, monkeypatch):
    from rehearsal_exercise.docker import Docker

    if request.node.get_closest_marker("docker"):
        import os

        if (
            not request.config.getoption("--docker-exercise")
            or os.environ.get("REHEARSAL_LIVE") != "1"
        ):
            pytest.skip("requires --docker-exercise and REHEARSAL_LIVE=1")
        return

    def denied(*args, **kwargs):
        raise AssertionError("Docker access is forbidden in ordinary unit tests")

    monkeypatch.setattr(Docker, "call", denied)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("network access is forbidden in offline tests")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    # Psycopg's bundled libpq opens C sockets below Python's socket module.
    # Block the application's driver entry point as well as Python networking.
    import psycopg

    monkeypatch.setattr(psycopg, "connect", denied)
    from rehearsal_exercise.guest_transport import SSH

    monkeypatch.setattr(SSH, "_execute", denied)


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
