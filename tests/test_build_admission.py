import copy

import pytest

from rehearsal_build.admission import GIB, validate_admission
from rehearsal_build.journal import SafetyError


def evidence(now):
    return dict(
        pve=dict(
            observed_at=now,
            node="pve01",
            storage="rehearsal-lvm",
            pool_total_bytes=90 * GIB,
            pool_used_bytes=0,
            other_commitments_bytes=0,
            metadata_percent=1.61,
            healthy=True,
            root_free_bytes=8 * GIB,
            memory_available_bytes=9 * GIB,
            vmid9000_unused=True,
            no_active_work=True,
        ),
        host=dict(
            observed_at=now,
            source="operator",
            filesystem="/mnt/ssd",
            total_bytes=916_000_000_000,
            available_bytes=636_000_000_000,
            both_pve_vdis_confirmed=True,
        ),
    )


def test_admission_charges_full_disk_auxiliary_and_both_reserves():
    result = validate_admission(evidence(10000), node="pve01", storage="rehearsal-lvm", now=10000)
    assert result == dict(
        incremental_budget_bytes=14 * GIB,
        pool_reserve_bytes=18 * GIB,
        host_reserve_bytes=183_200_000_000,
    )


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("host", "observed_at", 6399),
        ("pve", "observed_at", 9099),
        ("host", "observed_at", 10001),
        ("host", "both_pve_vdis_confirmed", False),
        ("host", "available_bytes", 180_000_000_000),
        ("host", "available_bytes", 917_000_000_000),
        ("pve", "pool_used_bytes", 59 * GIB),
        ("pve", "other_commitments_bytes", 59 * GIB),
        ("pve", "metadata_percent", 75),
        ("pve", "healthy", False),
        ("pve", "no_active_work", False),
        ("pve", "vmid9000_unused", False),
        ("pve", "root_free_bytes", 6 * GIB - 1),
        ("pve", "memory_available_bytes", 6 * GIB - 1),
        ("pve", "pool_used_bytes", float("nan")),
        ("pve", "pool_total_bytes", True),
    ],
)
def test_unavailable_stale_or_insufficient_evidence_blocks_admission(section, key, value):
    data = copy.deepcopy(evidence(10000))
    data[section][key] = value
    with pytest.raises(SafetyError, match="capacity evidence"):
        validate_admission(data, node="pve01", storage="rehearsal-lvm", now=10000)


def test_missing_host_reading_is_not_replaced_by_pve_capacity():
    data = evidence(10000)
    del data["host"]
    with pytest.raises(SafetyError):
        validate_admission(data, node="pve01", storage="rehearsal-lvm", now=10000)
