# Investigation handoff and development boundary, 13 November 2026

This record summarizes the **user-supplied investigation handoff**, current as of
2026-11-13. Host/controller evidence was not independently recollected during this
development session. It supersedes current-state claims and continuation instructions
in the 12 November build records; those records remain historical evidence.
The [offline code review](../CHANGELOG.md) adds no new infrastructure observation,
deployment or live nested-start result and makes no claim that the fault is fixed.

**Later read-only refresh, 21:05–21:09 UTC:** the new
[controlled-boot runbook](controlled-boot-retest.md) records independently collected
current lab state, separately from this supplied historical handoff. VM 9000 is
stopped/disconnected with matching retained ownership/disks, PVE/controller are
reachable, and the historical pending operation remains uncertain. No start,
credential renewal, journal modification or host maintenance was performed.

## Established mechanism and unresolved cause

The supplied host evidence identifies two NULL-pointer write faults in VirtualBox
execution on `ubase`, Ubuntu 24.04 Desktop, Ryzen 7 3800X (8 cores/16 threads), 64 GB
RAM. Both occurred on kernel `7.0.0-42-generic` on 12 November:

| Task start encoded in recorded UPID, UTC | Host fault, UTC | Outer pve01 allocation |
| --- | --- | --- |
| 16:10:20 | 16:10:21.598647 | 2 vCPUs, 12 GiB RAM |
| 20:16:36 | 20:16:38.496213 | 1 vCPU, 16 GiB RAM |

Both faults reported RIP `0xffffd1251e863194`, zero RAX/RCX, VirtualBox driver
frames and an EMT thread terminating with interrupts disabled. Captured VMMR0
disassembly matches a NULL-destination write. Surviving VM/GUI/network threads
explain why a VirtualBox “running” indication did not establish guest execution.
Historical host/guest clock alignment was not independently verified; the times
above retain their source meanings.

The failure mechanism is established in the supplied evidence; its root cause
remains unknown. A nested AMD-V defect or host-kernel interaction is a hypothesis.
No matching confirmed upstream fix or Ryzen-specific diagnosis was identified in
the investigation. One vCPU did not prevent failure; CPU and RAM changed together,
and the second incident followed the first oops in the same host boot. This does
not rule out CPU-count influence.

Oracle VirtualBox and its usable Extension Pack now both report **7.2.22 r175245**;
the pack was upgraded from 7.2.20. The host rebooted to `7.0.0-43-generic`.
Installed/loaded vboxdrv versions and srcversions matched before and after reboot;
a stale driver was not established. No equivalent fault was found in the collected
kernel-43 logs, but nested execution has **not** been retested. Neither the reboot
nor component maintenance establishes a fix. Host NTP was active/synchronized.
KVM modules were loaded with `enable_virt_at_load=Y`, without `/dev/kvm` users in
the collected fuser check; harmful coexistence is unproven.

## Retained VM and historical operation evidence

The **last supplied Proxmox observation**, rather than a fresh state assertion,
showed VM 9000 stopped, `onboot=0`, sole NIC `link_down=1`, 1 vCPU, 2048 MiB RAM,
12 GiB root disk, `kvm=1` and CPU `host`. Its resource and volumes remain retained.

Controller records remain under
`rehearsal01:/var/lib/rehearsal/supervised/first-guest-20261112T141215Z/`:

- Run: `157c73f9-3f9d-4c38-9ddb-b5c7fb9fe170`.
- Resource: `048c39b1-a339-4891-8230-b6717068c99e`.
- First start: `UPID:pve01:00007245:000A305E:6AF5E4EC:qmstart:9000:rehearsal-build@pve!bootstrap-9000:`.
- Second start: `UPID:pve01:00001794:0001C753:6AF61EA4:qmstart:9000:rehearsal-build@pve!bootstrap-9000:`.

Both historical task records/logs are unavailable. Repeated read-only searches
and exact-UPID lookups were already completed; do not repeat them without new
evidence. Actual HTTP send times and response statuses were not recovered. Stored
UPIDs alone do not establish their response provenance. **Correction to the old
chronology:** the original documented 16:08:44 start time is unverified; the first
UPID encodes 16:10:20. Neither is a verified HTTP send timestamp.

**Correction to historical outcome interpretation:** the original controller
operation was marked failed to represent unavailable historical outcome, not an
observed Proxmox task failure. Preserve that original row and explanation. The
second operation remains uncertain/`NEEDS_RECONCILIATION`. A currently stopped VM
does not establish whether either historical start succeeded. Successful nested
boot and clean shutdown were never established. No controller state is rewritten
by this documentation or the offline development changes.

The recorded bootstrap owner/token expiry is **2026-11-13 15:08:20 UTC**. The
development clock was past that expiry when checked on 13 November. Check expiry
before interpreting any future authorization failure; do not renew, rotate or
broaden access automatically.

## Separate guest incident and maintenance

On host kernel 43, dev01 stalled during ordinary boot after three outer VMs were
started close together. Other VMs remained responsive. No host oops was captured;
dev01's EMT remained present, debugger queries succeeded and virtual clocks
advanced. Repeated unchanged guest RIP samples do not establish an interrupt
delivery fault. dev01 later booted; the exact recovery method is unrecorded.
Simultaneous startup is an observation, not an established cause.

Both dev01 and rehearsal01 run guest kernel `6.8.0-149-generic` and now have Oracle
Guest Additions 7.2.22, with core modules/services verified after reboot. dev01 was
upgraded from 7.2.8; rehearsal01 previously used in-kernel vboxguest. rehearsal01's
optional vboxvideo build failed because `drm_fb_helper_alloc_info` was unavailable;
its active display driver is vmwgfx. Do not describe its installer run as completely
clean. pve01's `7.0.2-6-pve` in-kernel vboxguest/observed chronyd were unchanged;
VBoxService was not observed there.

Both Ubuntu guests booted successfully while reporting
`kernel/rcu/tree_plugin.h:815 rcu_sched_clock_irq+0x3ad/0x3c0`. The warning persisted
on dev01 after the upgrade and has no established causal link to the host faults.
The handoff references [VirtualBox issue 861](https://github.com/VirtualBox/virtualbox/issues/861)
for a similar signature on successful boots; its Intel/multiple-vCPU scenario and
combined APIC/RCU workaround are not validated here. That page was not rechecked
during development.

rehearsal01 now runs VBoxService. systemd-timesyncd is enabled but inactive for an
unexplained reason. Host synchronization is available; actual guest corrections
were not verified and no time-service configuration change was made. The operator
confirmed nested VT-x/AMD-V disabled on rehearsal01; timing relative to the warning
boot is unknown.

Proposed allocations are pve01 **4 vCPUs/16 GiB**, dev01 **2 vCPUs**, rehearsal01
**1 vCPU**. Their application is unverified. Four vCPUs is an untested proposal,
not a remedy; pve01 requires nested AMD-V for its intended KVM workload.

## Development and live validation

Subsequent local work adds [public hosted CI](ci.md) and an independently testable
[prepared-guest recovery slice and supervised procedure](prepared-proxmox-exercise.md).
Those implementations are not live retests, do not change this incident's evidence
or root-cause status, and do not authorize VM 9000 changes. Kernel/component
maintenance still has no controlled nested-start validation establishing a fix.

Continue local implementation and network-blocked tests independently of host
diagnosis. New mutation evidence is described in
[the supervised tooling contract](supervised-build.md#offline-request-evidence-13-november-2026).
It supplies future local request observations and cannot reconstruct missing
historical evidence. Executor, workload provisioning, recovery, UI and Actions
remain future work.

**Live nested-start validation is blocked by the unresolved host fault.** A
separate explicit operator decision is required before attempting it. Do not
rerun supervised automation, start 9000, repeat imports, delete retained resources,
clear reconciliation state or change hypervisor allocations/settings during
development. The later read-only refresh above supersedes the absence of a fresh
resource observation in this historical handoff. Codex does not administer ubase;
any separately requested host instructions must use vim and grep, not ripgrep.

Supplied evidence locations, not assumed accessible from the development checkout:

- ubase: `/home/lerdos/pve01-freeze-20261112T220228Z-fuNtFA`.
- ubase: `/home/lerdos/dev01-startup-20261113T145503Z-9oQf3K`.
- dev01: `/home/jgipsz/dev01-guest-20261113T152832Z-tuxXXr`.
