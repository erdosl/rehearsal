"""Explicit local simulation; this provider cannot contact infrastructure."""

import json
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

from rehearsal.config import Config, validate_fixture_reference
from rehearsal.errors import InventoryError
from rehearsal.inventory import Inventory, _object, _text, parse_inventory

MAX_FIXTURE_BYTES = 2 * 1024 * 1024
FAILURES = {
    "authentication_failed": "API authentication rejected (simulated)",
    "permission_denied": "API permission denied (simulated)",
    "unavailable": "inventory service unavailable (simulated)",
    "timeout": "inventory request timed out (simulated)",
    "tls_untrusted": "TLS certificate trust failed (simulated); verification stays enabled",
}


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InventoryError("invalid_fixture", "fixture contains duplicate JSON fields")
        result[key] = value
    return result


class FixtureProvider:
    def __init__(self, config: Config, fixture: str | None = None) -> None:
        self.config = config
        self.spec = validate_fixture_reference(config.fixture if fixture is None else fixture)

    def inventory(self) -> Inventory:
        if self.spec.startswith("builtin:"):
            name = self.spec.removeprefix("builtin:")
            path = files("rehearsal").joinpath("fixtures", f"{name}.json")
        else:
            path = Path(self.spec)
            if not path.is_absolute():
                path = self.config.directory / path
        try:
            with path.open("rb") as stream:
                raw = stream.read(MAX_FIXTURE_BYTES + 1)
        except OSError:
            raise InventoryError("fixture_unreadable", "cannot read the selected fixture") from None
        if len(raw) > MAX_FIXTURE_BYTES:
            raise InventoryError("invalid_fixture", "fixture exceeds the 2 MiB limit")
        try:
            document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        except (ValueError, UnicodeError, RecursionError):
            raise InventoryError("invalid_fixture", "fixture is not valid UTF-8 JSON") from None
        if not isinstance(document, dict):
            raise InventoryError("invalid_fixture", "fixture root must be an object")
        payload = "failure" if "failure" in document else "inventory"
        _object(document, {"schema_version", "simulated", "description", payload}, "root")
        if type(document["schema_version"]) is not int or document["schema_version"] != 1:
            raise InventoryError("invalid_fixture", "fixture schema_version must be integer 1")
        if document["simulated"] is not True:
            raise InventoryError(
                "invalid_fixture", "fixture must explicitly declare simulated: true"
            )
        description = _text(document["description"], "description")
        if payload == "failure":
            failure = _object(document["failure"], {"code"}, "failure")
            code = failure["code"]
            if not isinstance(code, str) or code not in FAILURES:
                raise InventoryError("invalid_fixture", "fixture failure code is unsupported")
            raise InventoryError(code, FAILURES[code])
        result = parse_inventory(document["inventory"], source=self.spec, nodes=self.config.nodes)
        return replace(result, description=description)
