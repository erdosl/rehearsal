"""Conservative first-guest budgets over fresh, explicitly sourced observations."""

import math
import time

from rehearsal_build.journal import SafetyError

GIB = 1024**3


def validate_admission(evidence, *, node, storage, now=None):
    """The supervisor supplies PVE reads and a separate operator host reading."""
    now = time.time() if now is None else now
    try:
        pve, host = evidence["pve"], evidence["host"]
        if not 0 <= now - pve["observed_at"] <= 900:
            raise ValueError
        if not 0 <= now - host["observed_at"] <= 3600:
            raise ValueError
        numeric = (
            (pve, "pool_total_bytes"),
            (pve, "pool_used_bytes"),
            (pve, "other_commitments_bytes"),
            (pve, "metadata_percent"),
            (pve, "root_free_bytes"),
            (pve, "memory_available_bytes"),
            (host, "total_bytes"),
            (host, "available_bytes"),
        )
        if any(
            isinstance(source[key], bool)
            or not isinstance(source[key], (int, float))
            or not math.isfinite(source[key])
            or source[key] < 0
            for source, key in numeric
        ):
            raise ValueError
        increment = 14 * GIB  # Full 12 GiB disk plus the entire auxiliary allowance.
        pool_reserve = max(6 * GIB, math.ceil(pve["pool_total_bytes"] / 5))
        host_reserve = max(10 * GIB, math.ceil(host["total_bytes"] / 5))
        if (
            pve["node"] != node
            or pve["storage"] != storage
            or pve["healthy"] is not True
            or pve["vmid9000_unused"] is not True
            or pve["no_active_work"] is not True
            or pve["metadata_percent"] >= 75
            or pve["root_free_bytes"] < 6 * GIB  # 4 GiB reserve + 2 GiB staging budget.
            or pve["memory_available_bytes"] < 6 * GIB  # 4 GiB PVE + 2 GiB guest.
            or pve["pool_used_bytes"] + pve["other_commitments_bytes"] + increment + pool_reserve
            > pve["pool_total_bytes"]
            or host["source"] != "operator"
            or host["filesystem"] != "/mnt/ssd"
            or host["both_pve_vdis_confirmed"] is not True
            or host["available_bytes"] > host["total_bytes"]
            or host["available_bytes"] < increment + host_reserve
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        raise SafetyError("fresh PVE and operator host capacity evidence is required") from None
    return dict(
        incremental_budget_bytes=increment,
        pool_reserve_bytes=pool_reserve,
        host_reserve_bytes=host_reserve,
    )
