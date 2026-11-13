"""Strict structural configuration validation; no DNS or credential reads."""

import math
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from rehearsal.errors import ConfigError

BUILTIN_FIXTURES = {"healthy", "permission-denied"}
MAX_CONFIG_BYTES = 64 * 1024


@dataclass(frozen=True)
class ProxmoxConfig:
    endpoint: str
    verify_tls: bool = True
    ca_file: Path | None = None
    token_file: Path | None = None
    connect_timeout_seconds: float = 3.0
    read_timeout_seconds: float = 15.0
    request_deadline_seconds: float = 30.0
    max_attempts: int = 3


@dataclass(frozen=True)
class Config:
    directory: Path
    nodes: tuple[str, ...]
    fixture: str | None
    proxmox: ProxmoxConfig | None = None

    def summary(self) -> dict:
        """Do not print credential paths or arbitrary configuration values."""
        return {
            "valid": True,
            "schema_version": 1,
            "validation": "offline structural checks only",
            "nodes": list(self.nodes),
            "proxmox_configured": self.proxmox is not None,
            "tls_verification": True,
            "ca_file_configured": bool(self.proxmox and self.proxmox.ca_file),
            "token_file_configured": bool(self.proxmox and self.proxmox.token_file),
        }


def _table(value: object, allowed: set[str], context: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{context} must be a table")
    if set(value) - allowed:
        raise ConfigError(f"{context} contains unsupported settings; values are not displayed")
    return value


def _text(value: object, context: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 4096
        or any(not c.isprintable() for c in value)
    ):
        raise ConfigError(f"{context} must be a nonempty string without control characters")
    return value


def validate_fixture_reference(value: object) -> str:
    spec = _text(value, "inventory.fixture")
    if spec.startswith("builtin:"):
        if spec.removeprefix("builtin:") not in BUILTIN_FIXTURES:
            raise ConfigError("inventory.fixture names an unknown built-in fixture")
    elif ":" in spec:
        raise ConfigError("inventory.fixture must be a local file or a known builtin: reference")
    return spec


def _path(value: object, directory: Path, context: str) -> Path | None:
    if value is None:
        return None
    text = _text(value, context)
    if ":" in text or text.startswith("~"):
        raise ConfigError(f"{context} must be an absolute or configuration-relative local path")
    path = Path(text)
    return path if path.is_absolute() else directory / path


def _proxmox(value: object, directory: Path) -> ProxmoxConfig:
    data = _table(
        value,
        {
            "endpoint",
            "verify_tls",
            "ca_file",
            "token_file",
            "connect_timeout_seconds",
            "read_timeout_seconds",
            "request_deadline_seconds",
            "max_attempts",
        },
        "proxmox",
    )
    endpoint = _text(data.get("endpoint"), "proxmox.endpoint")
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
        valid = (
            parsed.scheme == "https"
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and parsed.path in ("", "/")
            and not any(c.isspace() for c in endpoint)
            and (port is None or 1 <= port <= 65535)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ConfigError(
            "proxmox.endpoint must be an HTTPS origin without credentials or URL extras"
        )
    if data.get("verify_tls", True) is not True:
        raise ConfigError("proxmox.verify_tls must be true; insecure TLS is unsupported")

    def timeout(name: str, default: float, maximum: float) -> float:
        value = data.get(name, default)
        if (
            type(value) not in (int, float)
            or not 0.1 <= value <= maximum
            or not math.isfinite(value)
        ):
            raise ConfigError(f"proxmox.{name} must be a finite number between 0.1 and {maximum}")
        return float(value)

    attempts = data.get("max_attempts", 3)
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ConfigError("proxmox.max_attempts must be an integer between 1 and 3")
    return ProxmoxConfig(
        endpoint=endpoint.rstrip("/"),
        ca_file=_path(data.get("ca_file"), directory, "proxmox.ca_file"),
        token_file=_path(data.get("token_file"), directory, "proxmox.token_file"),
        connect_timeout_seconds=timeout("connect_timeout_seconds", 3.0, 60.0),
        read_timeout_seconds=timeout("read_timeout_seconds", 15.0, 60.0),
        request_deadline_seconds=timeout("request_deadline_seconds", 30.0, 120.0),
        max_attempts=attempts,
    )


def load_config(path: Path) -> Config:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
    except OSError:
        raise ConfigError("cannot read configuration file") from None
    if len(raw) > MAX_CONFIG_BYTES:
        raise ConfigError("configuration exceeds the 64 KiB limit")
    try:
        document = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError, RecursionError):
        raise ConfigError(
            "configuration is not valid UTF-8 TOML; contents are not displayed"
        ) from None
    data = _table(document, {"schema_version", "inventory", "proxmox"}, "configuration")
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ConfigError("schema_version must be integer 1")
    inventory = _table(data.get("inventory"), {"nodes", "fixture"}, "inventory")
    nodes = inventory.get("nodes")
    if (
        not isinstance(nodes, list)
        or not nodes
        or any(
            not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}", n)
            for n in nodes
        )
        or len(set(nodes)) != len(nodes)
    ):
        raise ConfigError("inventory.nodes must contain unique, nonempty node names")
    directory = path.absolute().parent
    proxmox = _proxmox(data["proxmox"], directory) if "proxmox" in data else None
    fixture = inventory.get("fixture")
    if fixture is not None or proxmox is None:
        fixture = validate_fixture_reference(fixture)
    return Config(
        directory=directory,
        nodes=tuple(nodes),
        fixture=fixture,
        proxmox=proxmox,
    )
