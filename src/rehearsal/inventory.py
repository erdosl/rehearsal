"""Read-only inventory contract and validation of the normalized fixture schema.

This schema is Rehearsal's own snapshot format, not a raw PVE API response.
The API adapter normalizes only documented inventory fields into these records.
"""

import ipaddress
from dataclasses import asdict, dataclass
from typing import Protocol

from rehearsal.errors import InventoryError


@dataclass(frozen=True)
class Node:
    name: str
    status: str
    cpus: int
    memory_total_bytes: int


@dataclass(frozen=True)
class Storage:
    node: str
    name: str
    kind: str
    active: bool | None
    total_bytes: int | None
    used_bytes: int | None
    available_bytes: int | None
    content: tuple[str, ...] = ()


@dataclass(frozen=True)
class VM:
    node: str
    vmid: int
    name: str
    status: str
    template: bool


@dataclass(frozen=True)
class Network:
    node: str
    name: str
    kind: str
    active: bool | None
    cidr: str | None
    ports: tuple[str, ...]
    cidr6: str | None = None


@dataclass(frozen=True)
class Coverage:
    node: str
    section: str
    status: str
    error_code: str | None = None


@dataclass(frozen=True)
class Inventory:
    source: str
    description: str
    version: str
    nodes: tuple[Node, ...]
    storage: tuple[Storage, ...]
    vms: tuple[VM, ...]
    networks: tuple[Network, ...]
    schema_version: int = 1
    backend: str = "fixture"
    simulated: bool = True
    complete: bool = True
    coverage: tuple[Coverage, ...] = ()
    visibility: str = "synthetic fixture resources"

    def to_dict(self) -> dict:
        return asdict(self)


class InventoryProvider(Protocol):
    def inventory(self) -> Inventory:
        """Return an inventory or raise an explicit error; never fall back."""
        ...


def _invalid(context: str) -> InventoryError:
    return InventoryError("invalid_fixture", f"invalid fixture structure at {context}")


def _object(value: object, fields: set[str], context: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise _invalid(context)
    return value


def _text(value: object, context: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 256
        or any(not c.isprintable() for c in value)
    ):
        raise _invalid(context)
    return value


def _integer(value: object, context: str, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= 2**63 - 1:
        raise _invalid(context)
    return value


def _boolean(value: object, context: str) -> bool:
    if type(value) is not bool:
        raise _invalid(context)
    return value


def _rows(data: dict, name: str, fields: set[str]) -> list[dict]:
    rows = data.get(name)
    if not isinstance(rows, list):
        raise _invalid(name)
    return [_object(row, fields, name) for row in rows]


def _unique(values: list, context: str) -> None:
    if len(set(values)) != len(values):
        raise _invalid(context)


def parse_inventory(data: object, *, source: str, nodes: tuple[str, ...]) -> Inventory:
    data = _object(data, {"version", "nodes", "storage", "vms", "networks"}, "inventory")
    version = _text(data["version"], "version")
    parsed_nodes = []
    for row in _rows(data, "nodes", {"name", "status", "cpus", "memory_total_bytes"}):
        status = _text(row["status"], "nodes.status")
        if status not in {"online", "offline", "unknown"}:
            raise _invalid("nodes.status")
        parsed_nodes.append(
            Node(
                _text(row["name"], "nodes.name"),
                status,
                _integer(row["cpus"], "nodes.cpus", 1),
                _integer(row["memory_total_bytes"], "nodes.memory_total_bytes", 1),
            )
        )
    known_nodes = {row.name for row in parsed_nodes}
    _unique([row.name for row in parsed_nodes], "nodes: duplicate name")
    if not set(nodes) <= known_nodes:
        raise InventoryError(
            "incomplete_inventory", "fixture does not include every requested node"
        )

    def node_name(row: dict) -> str:
        name = _text(row["node"], "resource.node")
        if name not in known_nodes:
            raise _invalid("resource.node: unknown node")
        return name

    storage = []
    for row in _rows(
        data,
        "storage",
        {
            "node",
            "name",
            "kind",
            "active",
            "total_bytes",
            "used_bytes",
            "available_bytes",
        },
    ):
        total = _integer(row["total_bytes"], "storage.total_bytes")
        used = _integer(row["used_bytes"], "storage.used_bytes")
        available = _integer(row["available_bytes"], "storage.available_bytes")
        if used + available > total:
            raise _invalid("storage capacity")
        storage.append(
            Storage(
                node_name(row),
                _text(row["name"], "storage.name"),
                _text(row["kind"], "storage.kind"),
                _boolean(row["active"], "storage.active"),
                total,
                used,
                available,
            )
        )
    _unique([(row.node, row.name) for row in storage], "storage: duplicate identity")
    vms = []
    for row in _rows(data, "vms", {"node", "vmid", "name", "status", "template"}):
        status = _text(row["status"], "vms.status")
        if status not in {"running", "stopped", "paused", "unknown"}:
            raise _invalid("vms.status")
        vms.append(
            VM(
                node_name(row),
                _integer(row["vmid"], "vms.vmid", 100),
                _text(row["name"], "vms.name"),
                status,
                _boolean(row["template"], "vms.template"),
            )
        )
    _unique([row.vmid for row in vms], "vms: duplicate VMID")
    networks = []
    for row in _rows(data, "networks", {"node", "name", "kind", "active", "cidr", "ports"}):
        cidr = row["cidr"]
        if cidr is not None:
            cidr = _text(cidr, "networks.cidr")
            try:
                ipaddress.ip_interface(cidr)
            except ValueError:
                raise _invalid("networks.cidr") from None
        if not isinstance(row["ports"], list):
            raise _invalid("networks.ports")
        ports = tuple(_text(port, "networks.ports") for port in row["ports"])
        _unique(list(ports), "networks.ports")
        networks.append(
            Network(
                node_name(row),
                _text(row["name"], "networks.name"),
                _text(row["kind"], "networks.kind"),
                _boolean(row["active"], "networks.active"),
                cidr,
                ports,
            )
        )
    _unique([(row.node, row.name) for row in networks], "networks: duplicate identity")
    selected = set(nodes)
    return Inventory(
        source=source,
        description="",
        version=version,
        nodes=tuple(sorted((r for r in parsed_nodes if r.name in selected), key=lambda r: r.name)),
        storage=tuple(
            sorted((r for r in storage if r.node in selected), key=lambda r: (r.node, r.name))
        ),
        vms=tuple(sorted((r for r in vms if r.node in selected), key=lambda r: r.vmid)),
        networks=tuple(
            sorted(
                (r for r in networks if r.node in selected),
                key=lambda r: (r.node, r.name),
            )
        ),
    )
