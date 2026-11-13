"""Read-only prepared-guest admission over the established verified-TLS API adapter."""

import json
import time
from types import SimpleNamespace

from rehearsal_build.api import BuildAPI, volume_ids
from rehearsal_build.journal import SafetyError


class PreparedAPI(BuildAPI):
    def __init__(self, config, guest, journal, token, **kwargs):
        super().__init__(
            SimpleNamespace(
                endpoint=config.endpoint, ca_file=config.ca_file, node=guest.node, vmid=guest.vmid
            ),
            journal,
            token,
            **kwargs,
        )
        self.guest = guest

    def _scope(self, *args):
        raise SafetyError("prepared-guest integration permits no Proxmox mutations")

    def owned(self):
        guest = self.guest
        live = self.live()
        try:
            observed = json.loads(live["description"])["rehearsal_ownership"]
            if observed != guest.ownership or any(
                live[key] != value
                for key, value in {
                    "node": guest.node,
                    "pool": guest.pool,
                    "vmid": guest.vmid,
                }.items()
            ):
                raise ValueError
            if (
                live.get("template")
                or live.get("lock")
                or live.get("onboot") != 0
                or live.get("status") not in ("running", "stopped")
            ):
                raise ValueError
            if any(key.startswith("net") and key[3:].isdigit() and key != "net0" for key in live):
                raise ValueError
            nic = dict(part.split("=", 1) for part in live["net0"].split(","))
            nic["virtio"] = nic.get("virtio", "").lower()
            if nic != {
                "virtio": guest.mac,
                "bridge": guest.bridge,
                "firewall": "1",
                "link_down": "0",
            }:
                raise ValueError
            if volume_ids(live, guest.storage) != set(guest.volumes):
                raise ValueError
            now = time.time()
            if (
                not 0 <= now - guest.isolated_at <= 900
                or not now < guest.lease_expires <= now + 3600
            ):
                raise ValueError
            if (
                self.active_tasks()
                or self.read(self.vm_path + "/firewall/options").get("enable") != 1
            ):
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError):
            raise SafetyError(
                "prepared guest ownership, isolation, lease or disk identity is unverified"
            ) from None
        return live

    def reconcile_recorded(self, opid, postcondition):
        operation = self.journal.operation(opid)
        if (
            not operation["upid"]
            or operation["method"] != "POST"
            or operation["path"]
            not in {
                self.vm_path + "/status/start",
                self.vm_path + "/status/stop",
                self.vm_path + "/status/shutdown",
            }
        ):
            raise SafetyError("only exact already-recorded guest lifecycle tasks may be reconciled")
        return self.reconcile(
            opid, postcondition=postcondition, expected_types={"qmstart", "qmstop", "qmshutdown"}
        )
