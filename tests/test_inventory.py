import json

import pytest

from rehearsal.config import load_config
from rehearsal.errors import ConfigError, InventoryError
from rehearsal.providers.fixture import FAILURES, MAX_FIXTURE_BYTES, FixtureProvider


def write_fixture(config_path, document):
    path = config_path.parent / "snapshot.json"
    path.write_text(json.dumps(document))
    return path.name


def test_typed_inventory_contains_simulated_resources(config_path):
    result = FixtureProvider(load_config(config_path)).inventory()
    assert result.simulated is True
    assert result.backend == "fixture"
    assert result.source == "builtin:healthy"
    assert result.nodes[0].name == "sim-pve01"
    assert result.nodes[0].cpus == 2
    assert result.storage[0].available_bytes == 10 * 2**30
    assert result.vms[0].vmid == 9000 and result.vms[0].template is True
    assert result.networks[0].cidr == "192.0.2.80/24"
    assert result.to_dict()["simulated"] is True


def test_custom_fixture_is_relative_to_config_not_cwd(config_path, fixture_document, monkeypatch):
    spec = write_fixture(config_path, fixture_document)
    config = load_config(config_path)
    monkeypatch.chdir(config_path.parent.parent)
    result = FixtureProvider(config, spec).inventory()
    assert result.nodes[0].name == "sim-pve01"
    assert result.source == spec


def test_node_selection_does_not_leak_other_resources(config_path, fixture_document):
    node = dict(fixture_document["inventory"]["nodes"][0], name="another-node")
    fixture_document["inventory"]["nodes"].append(node)
    vm = dict(fixture_document["inventory"]["vms"][0], node="another-node", vmid=101)
    fixture_document["inventory"]["vms"].append(vm)
    result = FixtureProvider(load_config(config_path), write_fixture(config_path, fixture_document))
    assert [node.name for node in result.inventory().nodes] == ["sim-pve01"]
    assert [vm.vmid for vm in result.inventory().vms] == [9000]


def test_empty_resource_lists_are_valid(config_path, fixture_document):
    for name in ("storage", "vms", "networks"):
        fixture_document["inventory"][name] = []
    result = FixtureProvider(load_config(config_path), write_fixture(config_path, fixture_document))
    assert result.inventory().vms == ()


@pytest.mark.parametrize("code", FAILURES)
def test_representative_failures_are_explicit(config_path, code):
    document = {
        "schema_version": 1,
        "simulated": True,
        "description": "Synthetic failure",
        "failure": {"code": code},
    }
    with pytest.raises(InventoryError) as error:
        FixtureProvider(load_config(config_path), write_fixture(config_path, document)).inventory()
    assert error.value.code == code
    assert "simulated" in str(error.value)


def test_missing_node_is_not_reported_as_complete(config_path, fixture_document):
    fixture_document["inventory"]["nodes"] = []
    with pytest.raises(InventoryError) as error:
        FixtureProvider(
            load_config(config_path), write_fixture(config_path, fixture_document)
        ).inventory()
    assert error.value.code == "incomplete_inventory"


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(simulated=False),
        lambda d: d.update(simulated=1),
        lambda d: d.update(schema_version=True),
        lambda d: d.update(schema_version=2),
        lambda d: d.update(unexpected="FAKE-SECRET"),
        lambda d: d.update(description="\x1b[31munsafe"),
        lambda d: d["inventory"].pop("storage"),
        lambda d: d["inventory"].update(nodes="wrong"),
        lambda d: d["inventory"]["nodes"][0].update(cpus=True),
        lambda d: d["inventory"]["nodes"][0].update(memory_total_bytes=-1),
        lambda d: d["inventory"]["nodes"][0].update(memory_total_bytes=10**1000),
        lambda d: d["inventory"]["nodes"][0].update(status="invented"),
        lambda d: d["inventory"]["nodes"].append(d["inventory"]["nodes"][0]),
        lambda d: d["inventory"]["storage"][0].update(available_bytes=999999999999),
        lambda d: d["inventory"]["storage"][0].update(used_bytes=-1),
        lambda d: d["inventory"]["storage"][0].update(active=1),
        lambda d: d["inventory"]["storage"].append(d["inventory"]["storage"][0]),
        lambda d: d["inventory"]["vms"][0].update(node="unknown"),
        lambda d: d["inventory"]["vms"][0].update(vmid=99),
        lambda d: d["inventory"]["vms"][0].update(template="false"),
        lambda d: d["inventory"]["vms"].append(d["inventory"]["vms"][0]),
        lambda d: d["inventory"]["networks"][0].update(cidr="not-a-cidr"),
        lambda d: d["inventory"]["networks"][0].update(ports="wrong"),
        lambda d: d["inventory"]["networks"][0].update(ports=["x", "x"]),
        lambda d: d["inventory"]["networks"].append(d["inventory"]["networks"][0]),
    ],
)
def test_malformed_or_inconsistent_inventory_rejected(config_path, fixture_document, change):
    change(fixture_document)
    spec = write_fixture(config_path, fixture_document)
    with pytest.raises(InventoryError) as error:
        FixtureProvider(load_config(config_path), spec).inventory()
    assert error.value.code == "invalid_fixture"
    assert "FAKE-SECRET" not in str(error.value)


@pytest.mark.parametrize(
    "raw",
    [
        b"not JSON FAKE-SECRET",
        b"[]",
        b"\xff",
        "{}".encode("utf-16"),
        b'{"schema_version": 1, "schema_version": 1}',
        b" " * (MAX_FIXTURE_BYTES + 1),
    ],
)
def test_unreadable_or_invalid_fixture_never_falls_back(config_path, raw):
    path = config_path.parent / "invalid.json"
    path.write_bytes(raw)
    with pytest.raises(InventoryError) as error:
        FixtureProvider(load_config(config_path), str(path)).inventory()
    assert error.value.code == "invalid_fixture"
    assert "FAKE-SECRET" not in str(error.value)


def test_missing_file_and_unknown_builtin_never_fall_back(config_path):
    with pytest.raises(InventoryError) as error:
        FixtureProvider(load_config(config_path), "missing.json").inventory()
    assert error.value.code == "fixture_unreadable"
    with pytest.raises(ConfigError):
        FixtureProvider(load_config(config_path), "builtin:typo").inventory()
