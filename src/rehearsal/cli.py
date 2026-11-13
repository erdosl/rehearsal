"""Offline validation, explicit fixture simulation and gated read-only API inventory."""

import argparse
import json
import os
import sys
from pathlib import Path

from rehearsal import __version__
from rehearsal.config import load_config
from rehearsal.errors import ConfigError, RehearsalError
from rehearsal.inventory import Inventory, InventoryProvider
from rehearsal.providers.fixture import FixtureProvider
from rehearsal.providers.proxmox import ProxmoxProvider


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # Rejected arguments may include a mistakenly pasted token. Never echo values.
        self.print_usage(sys.stderr)
        self.exit(2, "error: invalid arguments; see --help (argument values are not displayed)\n")


def _parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(description="Rehearsal read-only inventory")
    parser.add_argument("--version", action="version", version=f"rehearsal {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="offline configuration checks")
    validate = config.add_subparsers(dest="action", required=True).add_parser("validate")
    inventory = commands.add_parser(
        "inventory", help="explicit fixture or read-only live inventory"
    )
    for command in (validate, inventory):
        command.add_argument("--config", type=Path, required=True, help="TOML configuration file")
        command.add_argument("--format", choices=("human", "json"), default="human")
    inventory.add_argument(
        "--backend",
        choices=("fixture", "live"),
        required=True,
        help="required explicit selection; no automatic fallback",
    )
    inventory.add_argument(
        "--fixture", help="override fixture reference; relative to configuration"
    )
    inventory.add_argument("--live", action="store_true", help="also requires REHEARSAL_LIVE=1")
    return parser


def _human(inventory: Inventory) -> str:
    lines = [
        (
            "SIMULATED inventory — fixture data; no infrastructure was contacted"
            if inventory.backend == "fixture"
            else "SIMULATED live-adapter transport test; no live results"
            if inventory.simulated
            else "LIVE inventory — read-only Proxmox API results"
        ),
        f"Source: {inventory.source}",
        inventory.description,
        f"Proxmox version{' (simulated)' if inventory.simulated else ''}: {inventory.version}",
        "Coverage: " + ("complete queries" if inventory.complete else "PARTIAL — failed/skipped"),
        "Nodes:",
    ]
    for node in inventory.nodes:
        lines.append(
            f"  {node.name}: {node.status}, {node.cpus} CPUs, "
            f"{node.memory_total_bytes / 2**30:.2f} GiB RAM"
        )
    lines.append("Storage (each capacity is separate; no admission decision):")
    for storage in inventory.storage:
        capacity = (
            "capacity unknown"
            if storage.total_bytes is None
            else f"{storage.available_bytes / 2**30:.2f} GiB available / "
            f"{storage.total_bytes / 2**30:.2f} GiB total"
        )
        lines.append(
            f"  {storage.node}/{storage.name} [{storage.kind}, active={storage.active}]: "
            f"{capacity}, content={','.join(storage.content) or 'unknown'}"
        )
    lines.append(f"VMs/templates: {len(inventory.vms)}")
    for vm in inventory.vms:
        lines.append(f"  {vm.node}/{vm.vmid} {vm.name}: {vm.status}, template={vm.template}")
    lines.append(f"Networks: {len(inventory.networks)}")
    for network in inventory.networks:
        lines.append(
            f"  {network.node}/{network.name} [{network.kind}]: "
            f"{network.cidr or 'no address'}, ports={','.join(network.ports) or 'none'}"
            f", IPv6={network.cidr6 or 'unknown/unconfigured'}"
        )
    for query in inventory.coverage:
        if query.status != "queried":
            lines.append(f"  {query.node}/{query.section}: {query.status} [{query.error_code}]")
    lines.append(inventory.visibility)
    lines.append("Inventory does not establish provisioning readiness or successful nested boot.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    backend = args.backend if args.command == "inventory" else None
    simulated = backend == "fixture"
    try:
        config = load_config(args.config)
        if args.command == "config":
            output = config.summary()
            human = "Configuration valid (offline structural checks only; no credentials read)."
        else:
            provider: InventoryProvider
            if backend == "live":
                if not args.live or os.environ.get("REHEARSAL_LIVE") != "1":
                    raise ConfigError("live backend requires both --live and REHEARSAL_LIVE=1")
                if args.fixture is not None:
                    raise ConfigError("--fixture cannot be used with the live backend")
                provider = ProxmoxProvider(config)
                simulated = provider.simulated
            else:
                if args.live:
                    raise ConfigError("--live cannot be used with the fixture backend")
                provider = FixtureProvider(config, args.fixture)
            inventory = provider.inventory()
            output = inventory.to_dict()
            human = _human(inventory)
    except RehearsalError as error:
        payload = {"error": {"code": error.code, "message": str(error)}}
        if backend:
            payload.update(backend=backend, simulated=simulated)
        if args.format == "json":
            print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        else:
            prefix = (
                "SIMULATED fixture error"
                if backend == "fixture"
                else "Live inventory error"
                if backend
                else "Configuration error"
            )
            print(f"{prefix} [{error.code}]: {error}", file=sys.stderr)
        return 2 if isinstance(error, ConfigError) else 3
    print(json.dumps(output, indent=2, sort_keys=True) if args.format == "json" else human)
    return 4 if args.command == "inventory" and not inventory.complete else 0
