"""Strict references for two already provisioned, isolated disposable guests."""

import hashlib
import ipaddress
import json
import math
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from rehearsal_exercise.evidence import ExerciseError


@dataclass(frozen=True)
class Guest:
    node: str
    pool: str
    vmid: int
    address: str
    ssh_user: str
    key_file: str
    known_hosts: str
    machine_id: str
    release_sha256: str
    storage: str
    volumes: list[str]
    bridge: str
    mac: str
    isolated_at: float
    lease_expires: float
    ownership: dict

    def validate(self, role, protected):
        if any(
            type(value) not in (int, float) or not math.isfinite(value) or value < 0
            for value in (self.isolated_at, self.lease_expires)
        ):
            raise ValueError
        if (
            type(self.vmid) is not int
            or self.vmid in protected
            or not 100 <= self.vmid <= 999999999
        ):
            raise ValueError
        ipaddress.IPv4Address(self.address)
        for name in (self.node, self.pool, self.storage, self.bridge, self.ssh_user):
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,62}", name):
                raise ValueError
        if self.bridge == "vmbr0" or not re.fullmatch(r"[0-9a-f]{2}(?::[0-9a-f]{2}){5}", self.mac):
            raise ValueError
        for name in (self.key_file, self.known_hosts):
            if not Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError
        if not re.fullmatch("[0-9a-f]{32}", self.machine_id) or not re.fullmatch(
            "[0-9a-f]{64}", self.release_sha256
        ):
            raise ValueError
        if (
            not self.volumes
            or len(self.volumes) != len(set(self.volumes))
            or any(
                not value.startswith(self.storage + ":")
                or not re.fullmatch(r"[A-Za-z0-9_./:-]+", value)
                for value in self.volumes
            )
        ):
            raise ValueError
        if set(self.ownership) != {
            "installation",
            "run",
            "resource",
            "nonce",
            "node",
            "vmid",
            "pool",
            "role",
        }:
            raise ValueError
        for key in ("installation", "run", "resource", "nonce"):
            if str(UUID(self.ownership[key])) != self.ownership[key]:
                raise ValueError
        if any(
            self.ownership[key] != value
            for key, value in {
                "node": self.node,
                "vmid": self.vmid,
                "pool": self.pool,
                "role": role,
            }.items()
        ):
            raise ValueError


@dataclass(frozen=True)
class GuestConfig:
    endpoint: str
    ca_file: str
    token_file: str
    protected_vmids: list[int]
    test_subnet: str
    source: Guest
    restore: Guest

    @property
    def digest(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()

    @classmethod
    def load(cls, path):
        try:
            data = tomllib.loads(Path(path).read_text())
            if set(data) != {"proxmox", "guests"} or set(data["guests"]) != {"source", "restore"}:
                raise ValueError
            config = cls(
                **data["proxmox"],
                **{role: Guest(**values) for role, values in data["guests"].items()},
            )
            parsed = urlsplit(config.endpoint)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in ("", "/")
            ):
                raise ValueError
            for reference in (config.ca_file, config.token_file):
                if not Path(reference).is_absolute() or ".." in Path(reference).parts:
                    raise ValueError
            if 9000 not in config.protected_vmids or any(
                type(v) is not int for v in config.protected_vmids
            ):
                raise ValueError
            for role in ("source", "restore"):
                getattr(config, role).validate(role, config.protected_vmids)
            network = ipaddress.IPv4Network(config.test_subnet)
            if not network.is_private or not 24 <= network.prefixlen <= 29:
                raise ValueError
            for guest in (config.source, config.restore):
                address = ipaddress.IPv4Address(guest.address)
                if (
                    address not in network
                    or address in (network.network_address, network.broadcast_address)
                    or guest.address == parsed.hostname
                ):
                    raise ValueError
            for field in ("vmid", "address", "machine_id", "mac"):
                if getattr(config.source, field) == getattr(config.restore, field):
                    raise ValueError
            for field in ("resource", "nonce"):
                if config.source.ownership[field] == config.restore.ownership[field]:
                    raise ValueError
            if set(config.source.volumes) & set(config.restore.volumes):
                raise ValueError
            if config.source.release_sha256 != config.restore.release_sha256:
                raise ValueError
            return config
        except (OSError, KeyError, TypeError, ValueError, AttributeError):
            raise ExerciseError(
                "invalid prepared-guest configuration; values are not displayed"
            ) from None
