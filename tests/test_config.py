from pathlib import Path

import pytest

from rehearsal.config import MAX_CONFIG_BYTES, load_config
from rehearsal.errors import ConfigError


def test_example_is_valid_without_reading_credentials(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name == "rehearsal.toml", "configuration validation read another file"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    config = load_config(Path("examples/rehearsal.toml"))
    assert config.nodes == ("sim-pve01",)
    assert config.proxmox.verify_tls is True
    assert config.summary()["token_file_configured"] is True
    assert "pve-token" not in str(config.summary())


def test_optional_proxmox_and_relative_fixture(config_path):
    config_path.write_text(
        'schema_version=1\n[inventory]\nnodes=["sim-pve01"]\nfixture="data/snapshot.json"\n'
    )
    config = load_config(config_path)
    assert config.proxmox is None
    assert config.directory == config_path.parent
    assert config.fixture == "data/snapshot.json"


def test_relative_credential_paths_are_not_opened(config_path):
    with config_path.open("a") as stream:
        stream.write(
            '[proxmox]\nendpoint="https://pve.example.invalid:8006/"\n'
            'ca_file="absent/ca.crt"\ntoken_file="absent/token"\n'
        )
    config = load_config(config_path)
    assert config.proxmox.ca_file == config_path.parent / "absent/ca.crt"
    assert config.proxmox.endpoint == "https://pve.example.invalid:8006"


@pytest.mark.parametrize(
    "document",
    [
        "",
        'schema_version="1"',
        "schema_version=true",
        "schema_version=2",
        'schema_version=1\nunknown="FAKE-SECRET"',
        'schema_version=1\ninventory="wrong"',
        'schema_version=1\n[inventory]\nnodes=[]\nfixture="builtin:healthy"',
        'schema_version=1\n[inventory]\nnodes="sim-pve01"\nfixture="builtin:healthy"',
        'schema_version=1\n[inventory]\nnodes=[1]\nfixture="builtin:healthy"',
        'schema_version=1\n[inventory]\nnodes=[{}]\nfixture="builtin:healthy"',
        'schema_version=1\n[inventory]\nnodes=["x", "x"]\nfixture="builtin:healthy"',
        'schema_version=1\n[inventory]\nnodes=["bad/name"]\nfixture="builtin:healthy"',
        'schema_version=1\n[inventory]\nnodes=[".."]\nfixture="builtin:healthy"',
        'schema_version=1\n[inventory]\nnodes=["x"]',
        'schema_version=1\n[inventory]\nnodes=["x"]\nfixture=""',
        'schema_version=1\n[inventory]\nnodes=["x"]\nfixture="builtin:missing"',
        'schema_version=1\n[inventory]\nnodes=["x"]\nfixture="https://example.invalid/data"',
        'schema_version=1\n[inventory]\nnodes=["x"]\nfixture="builtin:healthy"\ntoken="FAKE-SECRET"',
        "schema_version=1\nschema_version=1",
        'FAKE-SECRET = "unterminated',
    ],
)
def test_invalid_config_is_safe(config_path, document):
    config_path.write_text(document)
    with pytest.raises(ConfigError) as error:
        load_config(config_path)
    assert error.value.code == "invalid_configuration"
    assert "FAKE-SECRET" not in str(error.value)


@pytest.mark.parametrize(
    "settings",
    [
        'endpoint="http://pve.example.invalid"',
        'endpoint="https://user:FAKE-SECRET@pve.example.invalid"',
        'endpoint="https://pve.example.invalid?token=FAKE-SECRET"',
        'endpoint="https://pve.example.invalid/#fragment"',
        'endpoint="https://pve.example.invalid/api2/json"',
        'endpoint="https://pve.example.invalid:bad"',
        'endpoint="https://pve.example.invalid:0"',
        'endpoint="https://pve.example.invalid:70000"',
        'endpoint="https://[bad"',
        'endpoint="https:///missing-host"',
        'endpoint="https://pve.example.invalid"\nverify_tls=false',
        'endpoint="https://pve.example.invalid"\nverify_tls="true"',
        'endpoint="https://pve.example.invalid"\ntoken="FAKE-SECRET"',
        'endpoint="https://pve.example.invalid"\nca_file="https://remote/ca"',
        'endpoint="https://pve.example.invalid"\ntoken_file=7',
    ],
)
def test_unsafe_api_settings_rejected_even_offline(config_path, settings):
    with config_path.open("a") as stream:
        stream.write("[proxmox]\n" + settings)
    with pytest.raises(ConfigError) as error:
        load_config(config_path)
    assert "FAKE-SECRET" not in str(error.value)


def test_config_io_and_size_limits(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path / "absent.toml")
    with pytest.raises(ConfigError, match="cannot read"):
        load_config(tmp_path)
    path = tmp_path / "bad.toml"
    path.write_bytes(b"\xff")
    with pytest.raises(ConfigError, match="UTF-8 TOML"):
        load_config(path)
    path.write_bytes(b" " * (MAX_CONFIG_BYTES + 1))
    with pytest.raises(ConfigError, match="64 KiB"):
        load_config(path)


@pytest.mark.parametrize(
    "setting",
    [
        "connect_timeout_seconds=0",
        "connect_timeout_seconds=true",
        "read_timeout_seconds=-1",
        "read_timeout_seconds=61",
        "read_timeout_seconds=nan",
        "read_timeout_seconds=inf",
        "request_deadline_seconds=121",
        "max_attempts=0",
        "max_attempts=4",
        "max_attempts=2.0",
    ],
)
def test_live_timeout_and_retry_bounds(config_path, setting):
    with config_path.open("a") as stream:
        stream.write('[proxmox]\nendpoint="https://pve.example.invalid:8006"\n' + setting)
    with pytest.raises(ConfigError):
        load_config(config_path)


def test_live_example_has_no_fixture_or_credential_reads():
    config = load_config(Path("examples/live.toml"))
    assert config.fixture is None and config.nodes == ("pve01",)
    assert config.proxmox.connect_timeout_seconds == 3
    assert config.proxmox.max_attempts == 3
