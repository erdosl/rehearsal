"""A separate, strict configuration contract for the supervised 9000 build."""

import hashlib
import ipaddress
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

from rehearsal_build.journal import SafetyError


@dataclass(frozen=True)
class BuildConfig:
    endpoint: str
    ca_file: str
    token_file: str
    state_directory: str
    node: str
    storage: str
    bridge: str
    pool: str
    vmid: int
    name: str
    guest_ip: str
    guest_mac: str
    controller_ip: str
    controller_mac: str
    cores: int
    memory_mib: int
    disk_gib: int

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    @classmethod
    def load(cls, path):
        try:
            data = tomllib.loads(Path(path).read_text())
            if set(data) != {"build"}:
                raise ValueError
            config = cls(**data["build"])
            endpoint = urlsplit(config.endpoint)
            if (
                endpoint.scheme != "https"
                or not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
                or endpoint.path not in ("", "/")
            ):
                raise ValueError
            if (
                config.vmid != 9000
                or config.cores != 1
                or config.memory_mib != 2048
                or config.disk_gib != 12
            ):
                raise ValueError
            for value in (config.node, config.storage, config.bridge, config.pool, config.name):
                if not isinstance(value, str) or not re.fullmatch(
                    r"[A-Za-z][A-Za-z0-9_.-]{0,62}", value
                ):
                    raise ValueError
            if config.bridge == "vmbr0":
                raise ValueError
            for value in (config.ca_file, config.token_file, config.state_directory):
                if not Path(value).is_absolute() or ".." in Path(value).parts:
                    raise ValueError
            guest = ipaddress.ip_interface(config.guest_ip)
            controller = ipaddress.ip_address(config.controller_ip)
            if (
                guest.version != 4
                or guest.network.prefixlen != 24
                or controller not in guest.network
                or controller == guest.ip
                or guest.ip in (guest.network.network_address, guest.network.broadcast_address)
            ):
                raise ValueError
            for value in (config.guest_mac, config.controller_mac):
                if (
                    not re.fullmatch(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", value)
                    or int(value[:2], 16) & 1
                ):
                    raise ValueError
            if config.guest_mac == config.controller_mac:
                raise ValueError
            return config
        except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError):
            raise SafetyError(
                "invalid supervised-build configuration; values are not displayed"
            ) from None
