# Environment and inspection evidence

**13 November 2026 supplied update:** [the investigation handoff](investigation-2026-11-13.md)
is the current evidence summary. VM 9000 was last observed stopped/disconnected;
historical task evidence is unavailable and the second start remains uncertain.
Two VirtualBox host faults are established in the supplied investigation, with
root cause unresolved and no nested retest on kernel 43. CPU allocations remain
unverified proposals. The recorded bootstrap expiry has passed. No new lab/host
inspection or configuration change was performed during offline development.
The 12 November snapshots below retain their historical scope.

Latest update: **2026-11-12, operator recovery and renewed instability** — the operator restarted PVE with **one vCPU / 16 GB reported RAM**. Fresh read-only reconciliation established new boot, healthy storage/enforcement, passing access/inventory and the existing guest stopped/unlocked/disconnected. The old operation's current effect was resolved while preserving its unavailable historical result. **One distinct, authorized new start again lost PVE SSH/API responsiveness.** The attempt was halted; current guest status/stop, KVM execution and all guest tests are unverified. The new start remains uncertain, with both owned volumes retained and no link release/deletion. [Current incident and revised budgets](supervised-build.md#operator-restart-and-supervised-recovery-attempt) supersede earlier snapshots.

## Operator-reported recovery and observed recurrence

The operator reports changing pve01 from **2 → 1 vCPU** and **12 → 16 GB RAM**, then restarting it. Similar multi-vCPU hangs in other VirtualBox VMs, absent in single-vCPU VMs, are an **operator-observed pattern/provisional workaround**, not a confirmed root cause. Graceful versus forced shutdown is **not established**. Linux readings corroborated one CPU/increased memory; no agent host-side access or reboot occurred.

| Verified before the new attempt | Evidence / limit |
| --- | --- |
| New boot / resources | Boot ID **`3256e72c-f8a3-4b92-adb4-746acd8b6605`**, one CPU, MemTotal **16,769,753,088 bytes** (~15.62 GiB), available ~14.08 GiB |
| Existing guest | 9000 stopped, no lock, onboot 0, sole net0 firewall 1/link_down 1; original installation/run/resource/nonce/pool/node and exactly root/cloud-init volumes match |
| Old start reconciliation | Original status/log unavailable (`no such task`, archive absent); original worker absent across confirmed node restart, no active task/HA resource, current effect independently stopped. Journal archives the old operation failed/unverifiable, preserves UPID and does not assert historical success/no execution |
| Storage / budget | 90 GiB pool healthy, **data 1.94%, metadata 1.65%**; root free **9,172,987,904 bytes**. Existing full 12 GiB root + 2 GiB auxiliary allowance + 18 GiB reserve unchanged; no new disk commitment. PVE retains ≥4 GiB RAM reserve, guest 2 GiB; one PVE CPU is shared, with no dedicated CPU headroom |
| Enforcement/network | Legacy enabled/running with actual IPv4/IPv6 hooks, bridge guard/effective nine rules/hash/service and guest firewall/IP set persisted; forwarding 0/0, exact bridge physical port and host IPv6 disabled. Management addresses/defaults unchanged; compile/readback passed. Controller tuple/filter preserved |
| Fresh management / inventory | Strict-key dev01 SSH/passwordless sudo and DNS/NAT HTTPS passed. Original verified-TLS inventory **20:07 UTC exit 0**, live/non-simulated/complete, four queried sections and one stopped VM; SHA-256 **`0aafaa10382323acf1566e49467ea64cc2874c6476f7fc57a97a6d4203bedb84`** |
| Kernel logs | Journald reported a corrupted or uncleanly shut down journal. Shutdown method, guest filesystem integrity and hang cause remain unestablished; no repair or host graphics/network workaround was attempted |

Concurrency remains **one operation / one running guest**; added RAM does not authorize another guest. CPU 1 for PVE and vCPU 1 for 9000 share execution time. Pre-attempt capacity passed; post-hang memory/CPU/health cannot be measured. Latest physical-host space remains the earlier supplied 633G observation, not a fresh guarantee.

At **20:16:36 UTC**, after reconciliation and renewed stopped-guest isolation checks, one distinct start returned:

```text
UPID:pve01:00001794:0001C753:6AF61EA4:qmstart:9000:rehearsal-build@pve!bootstrap-9000:
```

Its journal operation is **`a9cf5dc8-7654-40c0-99c0-a0ba6e589a88`**. A passive node-status monitor had 19 successful samples (maximum ~10.23 ms), then timed out at **20:16:43 UTC**. Task polling also timed out. Three bounded read-only SSH probes failed with connection timeout/`No route to host`. **The one-vCPU/increased-RAM attempt again lost responsiveness; the workaround is not validated for this build, and root cause remains unconfirmed.** No more start, link-release or cleanup mutation was issued.

At **20:22 UTC**, controller SSH/sudo, network/filter/disabled forwarding, DNS/NAT HTTPS and original inventory config/CA/token metadata/release remained verified. Post-attempt live inventory returned **exit 3 / timeout**, without fixture fallback. Current PVE/guest status and owned shutdown are **unverified**, not assumed stopped. Root serial evidence remains inaccessible. Guest trust/actual Ubuntu/KVM/cloud-init/filesystem/agent/packet checks never ran.

Protected controller handoff, monitoring/failed probes, original reconciliation and consistent SQLite snapshots remain in `/var/lib/rehearsal/supervised/first-guest-20261112T141215Z`; current handoff is **`recovery-handoff-20261112T200153Z.json`**, with **`journal-after-recovery-uncertainty.sqlite3`**. PVE root evidence is `/root/rehearsal-reconcile-20261112T200153Z`. Existing identity/token/ACLs/key/tool/release were reused; bootstrap expiry stays **2026-11-13 15:08:20 UTC**. No create/import/resize/delete, lock clearing, API grant, identity cleaning, template/clone, commit or push occurred in this recovery turn. New task uncertainty blocks cleanup regardless of expiry. The attempt is stopped pending operator console observation/restored management for safe reconciliation and owned stop.

## VM 9000 admission and unreconciled start

This is the **earlier 15:45–16:20 UTC snapshot**. Its old current-effect uncertainty was resolved after the operator restart above; the newer start is now uncertain.

- **Fresh user-supplied evidence, 15:45:15 UTC:** ubase `/mnt/ssd`, ext4 on `/dev/sdc1`, **916G total / 282G used / 635G available / 31%**. Operator VBoxManage subsequently confirmed PVE running and both attached VDIs at the previously recorded `/mnt/ssd/VirtualBox VMs/Proxmox/Proxmox-training/pve01/` paths. No host access was attempted from dev01. Conservative rounded-unit bounds pass the 14 GiB increment plus 20% host reserve.
- **Post-import user-supplied evidence:** same device/filesystem, **916G total / 283G used / 633G available / 31%**. The command timestamp was not supplied; recorded on the controller about 16:13 UTC. Still above reserve. Original `G` labels are preserved.
- **Verified admission:** unused healthy 90 GiB pool, metadata 1.61%, root 9,192,034,304 bytes free, available RAM 10,002,792,448 bytes, no guests/tasks, journal clear and VMID unused. Existing bootstrap credential passed verified-TLS reads and remained valid. Reused pool, roles, ACLs, credential, image, bundle and key.
- **Created only VM 9000**, rehearsal-noble-build, pve01/pool rehearsal; 1 vCPU, 2048 MiB, kvm 1, onboot 0; raw root **`rehearsal-lvm:vm-9000-disk-0`**, actual 12 GiB block size, plus **`rehearsal-lvm:vm-9000-cloudinit`**. Exact ownership/run/nonce and create/import/resize UPIDs are in the controller journal. The single privileged import was reconciled after non-JSON CLI output, without repeating it.
- **Stopped-guest configuration passed:** exact four-rule per-VM policy/IP set; locked password/root-disable/sudo and SSH password-authentication defaults inspected read-only; generated NoCloud user/key/test IP/no gateway read back. Exact guest bridge pair and controller tuple installed one machine at a time, backups and eight-minute timers verified first. Fresh SSH/sudo, DNS/NAT HTTPS, unchanged routing/forwarding and original real inventory passed after each; both timers canceled **16:04:41/45 UTC**, never ran.
- **Current persistent guard hashes:** controller `f9a207a1958a8ac073893aafbc3f45483b630a010c0309464122d204d801f1dd`; PVE bridge `5d1206cb16128a77fac110ef7b92f8d8f1a60f1474b5c2a01e017d9e9fe46945`. Units/global engine/management policy preserved. Guest-specific reboot persistence is untested.
- **Start, 16:08:44 UTC:** `UPID:pve01:00007245:000A305E:6AF5E4EC:qmstart:9000:rehearsal-build@pve!bootstrap-9000:`. Task polling timed out. Ten strict-key read-only SSH attempts within 150 seconds failed during banner exchange; API version/inventory timed out, ping intermittent. Last verified NIC is sole vmbr1 net0, firewall 1, **link_down 1**; link release never attempted. **No actual KVM/Ubuntu/SSH/agent/packet result or stopped state is claimed.**
- **Controller at 16:13 UTC:** fresh SSH/sudo, unchanged network/defaults/forwarding, active filter, original inventory token metadata/config/CA/release and DNS/NAT HTTPS passed. Latest live inventory **exit 3**, sanitized error `timeout`, no fixture fallback; current PVE access is not passing. Operator console observation requested; no reboot/power/network workaround attempted.
- **Protected handoff:** existing controller supervised directory contains `start-unreconciled-handoff.json`, `journal-after-start-uncertainty.sqlite3`, generated-policy/configuration/input evidence and sanitized failed inventory. Resource retained, start uncertain, shutdown/cleanup blocked pending task/state reconciliation; no uncertain deletion. New sidecar `/opt/rehearsal/supervised-tools/e95e1c7cb30b8f40`, SHA-256 `e95e1c7cb30b8f406949a4f165e58b3e16e6c24f21e25972f3fea3d41b6594ba`; **219 offline tests/Ruff pass**. No new API privileges/identity/token were added in this resumption; expiry remains **2026-11-13 15:08:20 UTC**.

Guest filesystem growth/free space, authenticated console/SSH trust, actual KVM boot, cloud-init, agent, all positive/negative guest packet tests and owned stop remain pending. Root LV size/configuration and compilation alone do not pass these checks. Template cleaning/promotion, clone 9100, peer tests and recovery are not authorized here. No commit/push occurred.

## Supervised first-guest preparation

This initial snapshot covers preparation through **15:43 UTC**, before the resumed admission above; its absent-guest/pending-host statuses are historical.

The user authorized one supervised VM 9000 build/test/stop, including minimal tooling, pool/credentials, verified inputs and one restart of each platform VM. Identity cleaning, template conversion and clone 9100 remain excluded. [Full execution record and continuation procedure](supervised-build.md) distinguish completed preparation from pending guest work.

| Verified, 2026-11-12 | Evidence / limitation |
| --- | --- |
| Controller reboot, 14:16 UTC | Boot ID `4fa3d78f-3a92-4e6e-a5bb-bf88e699a03d` → `ce105dd6-07dc-46c6-a237-1f61c90f882e`; one reboot, bounded strict-key reconnect, no repair |
| PVE reboot, 14:20 UTC | Boot ID `5bd69c40-7d4a-45ab-9971-91c3a4c2db1f` → `d2abd677-b98c-499c-ba7d-516da7beaf38`; one reboot after controller checks passed, no repair |
| Persistent firewall/network | PVE legacy enabled/running, actual IPv4/IPv6 hooks, bridge netfilter 1/1, native bridge guard and enabled oneshot persisted; sole IP-less vmbr1/enp0s16 path, forwarding port, host IPv6 disabled. Controller input/forward table and empty guest set persisted. Addresses/defaults unchanged, routing forwarding 0/0 |
| Fresh access after restart | dev01 SSH/passwordless sudo, DNS, NAT-interface HTTPS 200/TLS verification 0 and runtime verified-TLS inventory passed after each restart; time synchronized |
| Controller input packets after reboot, 15:02 UTC | Three SYN frames arriving enp0s9 to test/management/NAT IPv4 SSH destinations hit input drop: 3 packets/120 IP bytes, accept zero; physical PVE source, **not nested-guest evidence** |
| Inventory preservation | Release 0.2.0/symlink/wheel/config/CA and original token mode/owner/inode/size/mtime/report hashes unchanged; owner/token ACL and metadata comparison unchanged. Fresh inventory 15:32 UTC exit 0, live/non-simulated/complete, four queried sections, six interfaces, zero VMs |
| Signed Ubuntu input | Noble released build 20261017, image SHA-256 `04e8f2461a16a44e78a370284471f29616cdd9baf1893df25807b71f985b6c94`, 621,284,352 bytes; expected signer `D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`; gpgv and authenticated manifest checks passed |
| Actual image format, 14:46 UTC | PVE rehash and qemu-img info/check: qcow2, virtual **3.5 GiB**, no backing/data file, zero check errors. RAM-only PVE staging avoids VDI growth; durable source retained on controller |
| Offline agent bundle, 14:40 UTC | Signed APT indexes/package hashes checked against exact image manifest; liburing2 2.5-1build1 and qemu-guest-agent 1:8.2.2+ds-0ubuntu1.18; download-disabled resolution passed. No guest installation yet |
| Pool/bootstrap access | Created empty shared pool `rehearsal`, five narrow roles, owner `rehearsal-build@pve`, privsep token `rehearsal-build@pve!bootstrap-9000`, ten matching non-propagating owner/token ACL bindings. Both expire **2026-11-13 15:08:20 UTC**. [Exact role/privilege paths](supervised-build.md#pool-identity-and-exact-privileges-created) include VM 9000 only, selected storage/bridge/node and exact-pool audit |
| Actual bootstrap token access, 15:32 UTC | Verified-TLS node/storage/network/pool/task reads passed. No rights on VM 9100, local storage or vmbr0. Uncertain initial handoff was reconciled by transferring the same new server value, without repeating creation or rotating any token; secret never displayed |
| Dedicated guest access | Fresh Ed25519 build key generated as rehearsal, protected 0700/0600 controller directory/file; planned MAC `02:52:40:61:0e:f4` and address `10.77.0.10/24`. No guest known_hosts/trust claim yet |
| Minimal tooling | `src/rehearsal_build/`, **216 offline tests passed**, Ruff check/format passed; real VM mutations/cleanup remain untested. Separate deployed sidecar **`/opt/rehearsal/supervised-tools/2eee1c2236dda805`**, source SHA-256 `2eee1c2236dda805492dd5a19d8ea406f172686bb3d5c1ce06fd71d14905add5`; no new dependency/daemon |
| State and allocation | `/var/lib/rehearsal/supervised/first-guest-20261112T141215Z`, installation `cc8e4939-1846-4891-8a99-7f746db4d31e`; 18 metadata operations complete, none unresolved; **no resource reservation, VM, disk, guest UPID or allow tuple** |
| Capacity | PVE 90 GiB rehearsal-lvm remains unused; metadata 1.61%, root >8 GiB free, available RAM >9 GiB after RAM staging at checked times. VMID 9000 unused. Fresh operator `/mnt/ssd` observation requested; old supplied 636 GB remains an initial planning snapshot, **not a new admission reading** |

Protected evidence: `/root/rehearsal-reboot-20261112T141215Z` on both machines; `/root/rehearsal-firstguest-20261112T141215Z` on PVE; controller supervised state, input directory `/var/lib/rehearsal/inputs/noble-20261017-20261112T141215Z`, dedicated key directory and runtime-owned reports. Credentials/private keys/raw logs are excluded from Git. The PVE comparison excluded only two regenerated pmxcfs inode fields; rule bytes/mode/owner/mtime and all other comparisons passed. No firewall repair, second reboot, guest creation, commit or push occurred.

## Successful PVE-only firewall activation

The user separately authorized completion of PVE firewall changes after correcting/testing the verifier. See the [activation record](firewall-isolation.md#successful-pve-only-activation) for configuration, evidence digests and phase ordering. The restored PVE baseline was reinspected/backed up before changes, while the controller was inspected read-only. No controller firewall/credential/API privilege or unrelated networking change occurred.

| Item | Verified evidence on 2026-11-12 |
| --- | --- |
| Verifier sequencing | Eight offline tests passed, including disabled pre-activation state, compiler failures/warnings and rejection of compilation alone as enforcement; generated syntax and before/enable/after order checked |
| Before activation | **13:56:41 UTC**: selected options staged while cluster disabled; compile exit 0, empty stderr, no active chains expected; `enforcement_verified=false` |
| Explicit selected backend | One journaled digest-protected local API request enabled cluster firewall. `nftables=0` selects legacy; node host-zone `enable=0` preserves management; ebtables enabled, cluster INPUT/OUTPUT ACCEPT |
| After activation | **13:57:01 UTC**: **enabled/running**, compile exit 0/empty stderr, actual IPv4/IPv6 FORWARD hooks into `PVEFW-FORWARD`; bridge IPv4/IPv6 netfilter **1/1**, independent native bridge guard present |
| Bridge guard / guest admission | Five effective rules scoped to `vmbr1`; `guest_pairs` contains only terminal drop. No per-VM firewall profile/allow rule or controller guest tuple installed; zero guests |
| Persistence | Exact PVE nft/unit candidates installed at the planned paths, root-owned 0600/0644; unit enabled/active/exited with no overrides. pmxcfs cluster/node files match API readback/tested state; distribution nftables unit remains inactive/disabled |
| Access/connectivity | Fresh dev01 SSH/passwordless sudo passed; PVE DNS and NAT-interface IPv4 HTTPS **200 / TLS verify 0**; controller verified-TLS live inventory passed with both explicit opt-ins |
| Network invariants | All PVE addresses/defaults unchanged; management `.80/24`, NAT `10.0.5.15/24` through `10.0.5.2`, IPv6 default `fe80::2` on `enp0s10`; IPv4/IPv6 **routing** forwarding remains **0/0** on both VMs |
| Controller preservation | Before/after file hashes/metadata, effective stateless nft JSON including handles, unit state, network state, release/config/CA and token metadata exactly match; firewall was not reloaded or edited |
| Fresh rollback timer | **`rehearsal-pve-firewall-rollback-20261112T135245Z.timer`** armed **13:56:21**, due **14:06:21**, canceled **13:57:11** only after all checks; inactive/dead, rollback never started |
| Final readback | **13:58:19 UTC**: backend/guard remain active, timer inactive, options/persistence correct, no guests |

Private PVE backup, rollback procedure, source/test copies and intent/result/effective-rule evidence are in **`/root/rehearsal-firewall-20261112T135245Z`** (0700 directory, 0600 evidence, 0700 rollback script). Original absent-file markers and rules/network/sysctls are retained; no token contents were copied. The earlier attempt's separate evidence directory is preserved.

Before/after sanitized controller inventory reports are `/var/lib/rehearsal/reports/firewall-20261112T135245Z-{before,after}.json`, with runtime-owned 0600 metadata/stderr. Both returned **exit 0**, real/complete, four queried sections, active `rehearsal-lvm`, six audit-visible interfaces and zero VMs. The final JSON SHA-256 is **`b0d2a157c8ab6d8af4403d72ffc988b6ff9257550ce7a226b7c2a62a2b236041`**. Audit scope/latest pointer and existing token remain unchanged.

This completes platform firewall activation, **not guest isolation**. Exact stopped-resource VM/NIC/port/MAC/IP/ARP rules and the controller tuple, nested-MAC passage, positive guest/return connectivity, IPv4/IPv6/DHCP/RA/ARP/spoof/tag/peer negative tests, controller forwarding packet checks and separately authorized reboot persistence remain pending. Current default-closed guards admit no guest. No guest, reboot, commit or push occurred.

## Firewall activation attempt: controller applied, PVE rolled back (13:38–13:45 history)

On **2026-11-12**, the user explicitly authorized scoped firewall/persistence changes and live verification, one machine at a time, with automatic rollback armed before changes. The [earlier runbook record](firewall-isolation.md#previous-activation-attempt) contains sanitized results, digests, private evidence locations and the failed pre-enable check. This section describes the earlier rollback; the successful separately authorized PVE-only activation above supersedes its PVE-disabled state.

| Target / gate | Verified finding |
| --- | --- |
| Controller filter | Exact repository nft/unit candidates installed; service enabled/active/exited with no overrides; rule file root-owned 0600, unit 0644; seven effective rules, guest set empty; unrelated nftables unchanged |
| Controller timer | Armed **13:39:46 UTC**, due 13:49:46, canceled **13:42:05** only after checks; never fired |
| Controller input packet checks | Three TCP SYN frames from PVE physical test NIC received through **`enp0s9`**, targeting test **`10.77.0.1`**, management **`192.168.56.83`** and NAT **`10.0.2.15`**, port 22; drop counter **0 → 3 / 120 IP bytes**, accept counters zero |
| PVE attempt | Bridge guard briefly installed; host `enable=0,nftables=0` and cluster `enable=0` options staged. Compiler exit 0, empty stderr, `firewall disabled`; verifier incorrectly expected enabled `PVEFW-FORWARD` while disabled, so the cluster-enable request was **never sent** |
| PVE rollback | Timer armed **13:42:57 UTC**, due 13:52:57. Prepared manual rollback returned exit 0; restoration/cleanup verified by **13:44:55** and timer canceled after rollback; never fired. Ledger-matching created installed files removed, original cluster/host files absent, no candidate unit/table installed |
| PVE final firewall state | **`disabled/running`**, empty explicit options/nftables, permissive legacy state and bridge netfilter switches 0; intended guest engine **not active**; no guest boot permitted |
| Fresh access and sudo | New dev01 SSH connections with multiplexing disabled and strict host-key checks passed to both VMs; `sudo -n` root execution passed |
| Addresses/routes/forwarding | All interface addresses and IPv4/IPv6 default gateways match snapshots; management `.80`/`.83` unchanged; both VMs' IPv4/IPv6 routing forwarding **0/0** |
| NAT and DNS | Both resolve `archive.ubuntu.com`; IPv4 HTTPS HEAD through each named NAT NIC returns **HTTP 200, TLS verify 0**, including post-controller and post-PVE-rollback checks |
| Live inventory | Three fresh runs as `rehearsal`, with explicit live opt-ins and verified TLS: before, after controller, after PVE rollback; all **exit 0**, real/complete, four queried sections, active `rehearsal-lvm`, six audit-visible interfaces, zero VMs |
| Credentials/release/configuration | Runtime release target, config/CA hashes and token metadata unchanged; no ACL/token/release or operator network edits; existing latest report pointer preserved |
| Persistence scope | Controller installed files match the checked candidate bytes/hashes and effective rules; enabled unit ordering inspected. Reboot persistence **not exercised**; PVE candidate persistence was removed during rollback |

Each VM retains root-private backups/ledger/rollback/evidence in **`/root/rehearsal-firewall-20261112T133629Z`** (0700 directory, 0600 evidence files, 0700 script). No token contents were backed up or exported. Sanitized live reports and metadata remain under `/var/lib/rehearsal/reports/firewall-20261112T133629Z-{before,controller,after-pve-rollback}.*`, owned by `rehearsal`, mode 0600. The final inventory JSON SHA-256 is **`95a03f95650ed302152185cd0c976321bc68b4000af43e81f4c35482b7fe2713`**; the runbook lists all three digests.

The completed input test uses PVE's **physical** test NIC; it establishes neither nested guest MAC passage nor PVE/guest/peer enforcement. Controller IPv6/forwarding packet tests and guest reply allowances remain pending. Before first guest boot, complete a later PVE-only activation with the corrected verifier and rollback protection, then install/read back the stopped owned guest's exact NIC/MAC/IP/firewall and controller tuple. Nested boot, positive guest access, IPv4/IPv6/DHCP/RA/ARP/spoof/tag/peer negative tests and a separately authorized persistence/reboot check remain outstanding. No VM, API privilege change, reboot, commit or push occurred. The attempt stopped after PVE rollback as instructed.

## Operator-supplied dedicated test network

On **2026-11-12**, the operator supplied these findings. They are **operator-supplied facts**, not independent physical-host inspection from `dev01`:

| Layer / target | Supplied finding |
| --- | --- |
| VirtualBox network | Internal network **`REHEARSAL-TEST`** |
| PVE adapter | `pve01` adapter **5**, **Intel 82540EM**, cable connected, promiscuous policy **allow-vms** |
| Controller adapter | `rehearsal01` adapter **3**, **Intel 82540EM**, cable connected, promiscuous policy **deny** |
| PVE test interface | New **`enp0s16`**, MAC **`08:00:27:0f:b7:12`** |
| PVE bridge | **`vmbr1` UP/LOWER_UP**; `enp0s16` its sole port, forwarding; neither interface has an IP in the supplied address output |
| PVE persistence | Bridge configuration includes post-up commands disabling host IPv6 on `enp0s16` and `vmbr1`; existing management/NAT routes intact |
| Controller test interface | New **`enp0s9`**, MAC **`08:00:27:79:e0:74`**, **`10.77.0.1/24`**, no gateway on this NIC |
| Controller persistence | Netplan disables DHCP, router-advertisement acceptance and link-local addressing on `enp0s9`; existing management/NAT routes intact |

**Interface/bridge configuration step: COMPLETE**, on the operator's findings, with Linux configuration subsequently corroborated over SSH. **End-to-end nested-guest connectivity and firewall enforcement: UNVERIFIED.** Adapter settings do not prove VirtualBox carries nested guest MACs. No claim is made about physical-host firewall state or unrelated `LAB-*` networks.

## Effective firewall inspection and prepared next steps (13:22–13:32 history)

Read-only, strict-host-key SSH inspection on **2026-11-12**, beginning **13:22 UTC**, confirmed the new Linux devices, MACs, bridge membership, persistent configurations and intact management/NAT routes. On PVE, host IPv6 disablement is `1` on both test devices, while all three bridge netfilter call switches are `0`. Host IPv6 disablement does not block bridged IPv6 traffic.

PVE still reports **`disabled/running`**, despite both firewall daemons being active/enabled. Cluster/node options contain only empty-content digests; cluster/host firewall files are absent. nftables is empty, legacy IPv4/IPv6 raw/filter chains are permissive and ebtables policies are ACCEPT. The single node remains `pve01`, with no QEMU or LXC guests in the privileged cluster-resource read.

On the controller, **UFW is inactive** despite its active/exited enabled service. The nftables service is inactive/disabled; nftables has only empty IPv4/IPv6 filter tables, iptables-nft policies ACCEPT, and legacy saves empty. SSH listens on all IPv4/IPv6 addresses, including test IPv4 `10.77.0.1`. The test NIC has no IPv6 address and accepts no RA, but kernel IPv6 is not disabled (`disable_ipv6=0`); reverse-path filtering is loose (`2`). Both VMs' IPv4/IPv6 routing forwarding remains `0`.

The [firewall implementation and rollback plan](firewall-isolation.md) proposes legacy PVE per-VM policy, a scoped native bridge guard for port/MAC/IP/ARP and IPv6, and controller test-interface input/forward filtering. Node host-zone filtering stays off to preserve SSH/API management. Both baseline nft candidates and synthetic guest variants passed **check-only** validation on their target VMs; proposed persistence units passed local validation. These are prepared files, **not applied policy or verified packet enforcement**. No firewall/service/network/ACL/credential/release change, guest creation, live application inventory or reboot occurred in this inspection task.

Final **13:32 UTC** readback confirmed unchanged nftables state, no installed candidate unit on either VM, PVE still disabled with no cluster guests/explicit options, and controller UFW inactive. No candidate table remained after validation.

## User-reported physical-host capacity

On **2026-11-12**, the user supplied a physical-host filesystem report and confirmation from VirtualBox screenshots of both `pve01` disk locations. These are **user-supplied host findings**, not independently inspected from `dev01`:

| Item | Supplied finding |
| --- | --- |
| Mount / filesystem | `/mnt/ssd`, ext4 |
| Device | `/dev/sdc1` |
| Total / used / available | **916 GB / 281 GB / 636 GB**, retaining the reported units and rounding |
| `pve01` system disk | 32 GB, dynamically allocated VDI: `/mnt/ssd/VirtualBox VMs/Proxmox/Proxmox-training/pve01/pve01.vdi` |
| `pve01` workload disk | 100 GB, dynamically allocated VDI: `/mnt/ssd/VirtualBox VMs/Proxmox/Proxmox-training/pve01/pve01_1.vdi` |
| Other VM disk locations | `dev01` and `rehearsal01` backing-file locations remain **unverified**; these screenshots establish only `pve01`'s locations |

**Initial physical backing-capacity gate for `pve01`: SATISFIED**, on the supplied filesystem report and screenshot evidence confirming both attached VDIs under `/mnt/ssd`. The supplied available space comfortably covers the planned 14 GiB initial growth allowance, or later 38 GiB allowance, plus the host reserve of max(10 GiB, 20% of filesystem capacity). Retain the screenshot-reported GB labels separately from the GiB guest/pool budgets. This closes the initial `pve01` capacity gate only; it does not establish other VMs' disk locations, any snapshot-chain layout, or completion of the networking/boot/provisioning gates. No host access from `dev01` is required or assumed.

Satisfaction is an initial admission snapshot, not a permanent reservation. The host operator must keep checking actual `/mnt/ssd` available space before and after image imports/clones and as dynamically allocated disks or snapshot chains grow, recording fresh observations before later admissions. Include concurrent host/VM usage in growth forecasts and retain the host reserve. Stop new admissions if space or fresh evidence is insufficient. PVE pool data/metadata and OS-space checks remain separate; no automated physical-host monitor is installed or claimed.

## Nested guest preparation inspection

This snapshot **predates the operator's dedicated-network configuration above**. Its missing-bridge/controller-NIC findings are retained as history and superseded by that configuration and the later firewall inspection. Storage/image/provisioning observations remain subject to their stated limits.

On **2026-11-12**, bounded batch-mode SSH with strict existing-host-key verification, one connection attempt, five-second connection timeout and outer timeouts rechecked `pve01` and `rehearsal01`. Read public network/storage/API-source metadata only; no credential contents, ACL changes, networking changes, VM creation or reboot. Exact commands included `ip`, bridge-port sysfs, `/etc/network/interfaces`, forwarding procfs, `nft list ruleset`, `iptables-save`, firewall status/options, `qm list`, `pvesm status`, `lvs`, `vgs`, `free` and `df`.

| Verified finding | Meaning / limitation |
| --- | --- |
| PVE version still 9.2.2, kernel `7.0.2-6-pve` | Version-specific API source remains relevant |
| Only bridge `vmbr0`, `192.168.56.80/24`, sole port `nic0`, STP off, VLAN filtering off | Management/host-only connection, no dedicated guest test bridge |
| `nic1` `10.20.20.80/24`, `nic2` `10.30.30.80/24`; NAT `enp0s10` `10.0.5.15/24` not bridged | Storage/cluster links remain separate; node NAT does not provide guest routing |
| IPv4 default via `10.0.5.2` on `enp0s10`; IPv6 default via `fe80::2` there | Node routes only; no guest internet test |
| IPv4/IPv6 forwarding both 0; nftables ruleset empty; iptables-save shows permissive raw/filter chains, no NAT | No inspected forwarding/masquerade path; no established guest egress or isolation |
| `pve-firewall status` `disabled/running`; `pve-firewall` and `proxmox-firewall` services active; cluster/node firewall options contain no explicit settings | Services being active is insufficient; effective guest firewall enforcement is a preparation blocker |
| `interfaces.d` contains only a zero-length `sdn` file | No additional configured test bridge found in inspected configuration |
| `qm list` empty; resource pools list empty | Proposed IDs/pool are not allocated or reserved |
| `rehearsal-lvm` active: 94,371,840 KiB (90 GiB) total/free, used 0; LVM data 0%, metadata 1.61%; VG free 8 GiB | Thin-pool and unallocated VG capacity remain separate; later user-supplied evidence confirms both `pve01` VDIs on `/mnt/ssd` |
| `local` active, 9,027,364 KiB available; `local-lvm` active, 12,378,112 KiB free; root about 8.7 GiB available | Original OS/storage layout unchanged; root image staging must stay bounded |
| PVE about 11 GiB total RAM, about 10 GiB available, swap unused | Point-in-time capacity, not a workload admission guarantee |
| Controller still `.83/24` on `enp0s8`, NAT `10.0.2.15/24` on `enp0s3`, default `10.0.2.2`; forwarding both 0 | No dedicated controller test NIC yet |
| Controller binary reports 0.2.0; runtime-user current symlink resolves `/opt/rehearsal/releases/0.2.0`; structural config validation passes | These are offline/version checks, not another live API run |
| Config/CA root:`rehearsal` 0640, token runtime-owned 0400, reports 0700 | Metadata read only; no credential read/rotation |

`sysctl` was not in the unprivileged PVE PATH; its forwarding values were read directly from procfs. An initial controller operator `readlink` could not traverse the protected release; the follow-up under the correct runtime identity resolved it successfully. No ownership change was made. A unit listing had no Rehearsal unit, as expected. No PVE firewall/network source file was modified. Public installed API source confirms exact-ID create/delete/config/template/clone privileges, per-VM firewall `VM.Config.Network`, informational `VM.GuestAgent.Audit`, and that arbitrary filesystem image-import paths require `root@pam`; the future [permission matrix](nested-guest.md#additional-provisioning-permissions-inventory-unchanged) separates that operator bootstrap from runtime access.

The [first guest/template plan](nested-guest.md) proposes VMID 9000 then a serial full validation clone 9100, Ubuntu 24.04 released build 20261017, 1 vCPU/2 GiB RAM/**12 GiB logical root**, `rehearsal-lvm` and offline package delivery. These guest resources remain **unexecuted choices**. The dedicated `vmbr1`/`REHEARSAL-TEST` interface configuration was subsequently completed by the operator; guest connectivity/enforcement remain unverified. Canonical's published manifest contains OpenSSH/cloud-init but not the guest agent; image bytes/signature/package closure/actual virtual size were not verified. Boot remains untested. Maximum initial concurrency is **one run and one running guest**.

The revised three-disk pool budget is 36 GiB logical commitment + 2 GiB auxiliary allowance + 18 GiB reserve, leaving **34 GiB unassigned**, replacing the earlier 6 GiB disk estimate. Initial thin/clone physical usage must be measured. The [supplied host evidence](#user-reported-physical-host-capacity) satisfies the initial `pve01` backing-capacity gate; actual host-space checks continue as the VDIs grow. At this historical snapshot, firewall/guest connectivity, scoped mutation credentials, image/package verification, durable ownership/cleanup and reboot/boot remained gates. The [current supervised preparation record](#supervised-first-guest-preparation) supersedes those statuses: platform reboot/persistence, tooling, access and inputs now pass; actual guest creation/connectivity remain pending. Inventory identity/token/ACLs and deployed release remain unchanged.

## Verified controller deployment

| Item | Observation |
| --- | --- |
| Controller | `rehearsal01`, host-only `enp0s8` **192.168.56.83/24**, batch-mode/host-key-verified SSH as `jgipsz`; installation outside PVE is user-supplied placement |
| OS / kernel | Ubuntu 24.04.5 LTS; `6.8.0-149-generic`, x86_64 |
| Resources | Two vCPUs, approximately 3.8 GiB RAM; root filesystem approximately 38 GiB, 29 GiB available before deployment |
| Networking | NAT `enp0s3` `10.0.2.15/24`, default via `10.0.2.2`; direct route to PVE through host-only NIC; DNS `10.0.2.3`; time synchronization reported true |
| Setup access | `sudo -n id` reached root; runtime execution uses the separate `rehearsal` account |
| Runtime account | UID 999, GID 988, only its own group; home `/var/lib/rehearsal`, shell `/usr/sbin/nologin` |
| OS packages added | `python3.12-venv` 3.12.3-1ubuntu0.17 and its `python3-pip-whl` / `python3-setuptools-whl` dependencies; zero packages upgraded |
| Python / installation | Python 3.12.3; runtime dependencies installed offline from transferred wheels using the existing hash-checked lock, entirely inside the release venv |
| Release | `/opt/rehearsal/releases/0.2.0`, with `/opt/rehearsal/current` pointing there; code root-owned, group `rehearsal`, base mode 0750 |
| Configuration | `/etc/rehearsal/live.toml` and application-specific `/etc/rehearsal/pve-ca.crt`, root:`rehearsal`, 0640; directory 0750 |
| Credentials | `/etc/rehearsal/api-token.json`, owned by runtime account, mode **0400**; no secret values recorded here |
| State / evidence | `/var/lib/rehearsal` and `reports/`, runtime-owned 0700; report and metadata files 0600 |
| Persistent service | None installed or started for Rehearsal; this is a one-shot CLI deployment |

The existing wheel was transferred and its digest verified against the build artifact: `01527cf052c173773f7183b30b9d9cb1d87fe014a0a772112c3b092d4090d7c7`. It was not rebuilt or modified. Runtime version and `pip check` passed as `rehearsal`. Release ownership markers and the current symlink were checked; a repeated credential bootstrap reused the existing token/file unchanged, with the same expiry. Unrelated configuration was preserved.

### TLS and API authorization now verified

The earlier certificate-inspection timeout was resolved by successful bounded SSH inspection. The PVE certificate CN is `pve01.lab.test` and its SANs include IP `192.168.56.80` and DNS `pve01` / `pve01.lab.test`. The public cluster CA was obtained over existing host-key-verified SSH, fingerprint checked, and installed only as an application CA file. A real handshake as UID 999 negotiated **TLS 1.3**, verified the chain and IP identity, and matched the served leaf fingerprint to the certificate inspected over SSH. No hostname mapping, system-wide CA trust or PVE certificate change was needed. Public fingerprints are recorded in the [deployment runbook](live-inventory.md#verified-deployment-record).

Created dedicated PVE identity `rehearsal-inventory@pve`, token `inventory` with privilege separation, and four custom audit roles. The token expires **2026-12-12 11:51:04 UTC**. Both owner and token have exactly:

| Privilege | ACL path | Propagate |
| --- | --- | --- |
| `Sys.Audit` | `/nodes/pve01` | No |
| `Datastore.Audit` | `/storage/rehearsal-lvm` | No |
| `VM.Audit` | `/vms` | Yes |
| `SDN.Audit` | `/sdn/zones/localnetwork/vmbr0` | No |

No Administrator, `SDN.Use`, allocation, power or configuration privileges were granted. Unrelated ACLs were compared before/after and preserved. Token generation output stayed inside captured subprocess pipes/memory and was relayed over verified SSH stdin into the protected runtime file; it was never displayed or stored in this checkout.

The real network query exposed an additional PVE 9.2.2 filter missed by the earlier method-header review: Linux/OVS bridges are omitted without `SDN.Audit` or `SDN.Use` on the applicable bridge path. Installed `Network.pm` and `RPCEnvironment.pm` confirmed this. Adding **audit only** for `vmbr0` made it visible; PVE networking and storage configuration hashes remained unchanged. The runbook now includes this filter.

### Real live result and retained evidence

Final run at **2026-11-12 12:05:51 UTC**: exit **0**, `backend=live`, `simulated=false`, `complete=true`; node, storage, VM and network sections all `queried` with no error codes. Duration was 0.263 seconds for this metadata query, not a performance or recovery benchmark.

- Node: `pve01`; storage: active `rehearsal-lvm`, 90 GiB total/available, zero data used, `images,rootdir`.
- Network interfaces: `enp0s10`, `nic0`, `nic1`, `nic2`, **`vmbr0`**, matching a privileged API read of the current interface list.
- QEMU VMs/templates: **zero**, also confirmed by a separate privileged list. This is an actual empty list, not an inferred permission success. Other storage IDs are intentionally outside the datastore ACL scope.
- Report: `/var/lib/rehearsal/reports/inventory-20261112T120551652673Z.json`; companion `.metadata.json`; latest pointer `/var/lib/rehearsal/last-live-inventory.json`.
- Report SHA-256: `36d151beafe8ab2ad110705860ff6f1d015038548c32c0709c00b10ef5e1d6bc`. Credential/header/identity values were checked absent before reports were persisted. Raw reports remain on the controller, outside Git.

An initial 11:54 run also passed requested queries but had no bridge-audit scope and omitted `vmbr0`; that earlier evidence is retained, not overwritten. The final run verifies the corrected intended scope. `complete` still means successful requested queries, not unlimited cluster visibility.

Several ancillary SSH connections timed out between successful sessions; a later connection succeeded and controller UFW reported inactive. Their cause is unverified. Checks were bounded, no firewall/SSH configuration was changed, and the final HTTPS run succeeded. Investigate this before depending on unattended bootstrap. Nested workload boot, test isolation and recovery remain unverified. Physical backing capacity was unknown at deployment; the later [user-supplied host evidence](#user-reported-physical-host-capacity) now satisfies the initial `pve01` capacity gate, with ongoing actual-space checks required. No VM, template, storage pool, PVE network, runner or backup job was created/modified; no commit or push occurred.

## Verified repository facts

| Item | Observation |
| --- | --- |
| Directory | `/home/jgipsz/projects/Rehearsal` |
| Starting contents | Only tracked file was `LICENSE`; no application, configuration, workflows or tests |
| Starting Git state | Clean, branch `main`, tracking local reference `origin/main`; no fetch performed |
| Remote | Fetch/push URL `https://github.com/erdosl/rehearsal.git` |
| Initial commit | `2f763cc`, dated 2026-11-12, `Initial commit` |
| Licence | Apache License 2.0; unchanged by this task |
| Instructions | No applicable pre-existing `AGENTS.md` in the repository or ancestor directories checked |
| GitHub repository | Read-only `gh repo view` reported `erdosl/rehearsal`, `PUBLIC`, default branch `main` |
| GitHub authentication | `gh auth status` and `gh api user` confirmed active account `erdosl`, HTTPS Git protocol; token values were not displayed |

The starting local tracking relationship does not establish that the local branch matches the current remote tip. No commit, push, GitHub setting change or runner registration was performed.

## Verified development guest

| Item | Observation |
| --- | --- |
| Hostname / OS | `dev01`; Ubuntu 24.04.5 LTS, Noble |
| Kernel | `6.8.0-149-generic`, x86_64 |
| CPU allocation | One visible vCPU; AMD Ryzen 7 3800X model string; one visible core/thread |
| Virtualisation indicators | `lscpu` exposes AMD-V/`svm`, reports hypervisor vendor KVM; `systemd-detect-virt` reports `oracle` |
| Memory | Approximately 3.8 GiB total, 3.2 GiB available during inspection |
| Swap | Approximately 3.8 GiB, unused during inspection |
| Disk | 100 GiB virtual disk; ext4 root filesystem approximately 97 GiB, 18 GiB used, 75 GiB available as reported by `df -hT` |
| Init | PID 1 is systemd; systemd 255 (`255.4-1ubuntu8.18`); system state `running` |
| Container tools | Docker client/server 29.7.2; Compose v5.4.0; daemon read succeeded; storage driver `overlayfs` |
| Container services | Docker and containerd active; Podman service inactive and CLI absent |

These guest observations do not verify the physical host configuration or the Proxmox node. In particular, CPU flags in `dev01` do not establish KVM usability in a workload VM on `pve01`. The mixed virtualisation identifiers are recorded without inferring a different physical topology.

### Tooling

| Tool / capability | Observation |
| --- | --- |
| Python | `/usr/bin/python3`, 3.12.3; no `python` command on PATH |
| Virtual environments | `venv` and `ensurepip` importable; `python3.12-venv` installed (`3.12.3-1ubuntu0.17`); creation/bootstrap not exercised |
| Packaging | `pip`/`pip3`, uv, Poetry and pipx absent from PATH; pip not importable; setuptools 68.1.2 present; `build` absent |
| Tests / lint | pytest, Ruff and mypy absent from PATH and not importable |
| Potential libraries | PyYAML 6.0.1 present; HTTPX, Pydantic, Psycopg and proxmoxer not importable in the inspected interpreter |
| Standard library | SQLite 3.45.1 via Python; OpenSSL 3.0.13 via Python |
| Git / GitHub CLI | Git 2.43.0; gh 2.45.0 (Ubuntu package reports 2025-07-18) |
| Other tools | curl, OpenSSL, make, systemctl and OpenSSH available; OpenSSH 9.6p1 |
| Other container/VM tools | containerd executable present; Podman, nerdctl and `qemu-system-x86_64` absent from PATH |

At the initial inspection, no tools were installed and no venv was created. Absence above concerns that system PATH/interpreter, not an exhaustive search. The follow-up implementation successfully created project venvs and installed only local build/test tools, as recorded below. Existing Docker availability does not make Docker a controller dependency.

## Verified guest networking

| Interface | State / addresses | Observed role or limitation |
| --- | --- | --- |
| `lo` | `127.0.0.1/8`, `::1/128` | Loopback |
| `enp0s3` | UP, `10.0.2.15/24`; ULA/link-local IPv6 | IPv4 default route via `10.0.2.2`, metric 100; consistent with supplied NAT adapter |
| `enp0s8` | UP, `192.168.56.64/24`; link-local IPv6 | Direct route to `192.168.56.80`; consistent with supplied host-only adapter |
| `enp0s9` | UP, `10.50.10.5/24` | Connected route; VirtualBox internal-network membership not inspected |
| `enp0s10` | UP, `10.50.20.5/24` | Connected route; VirtualBox internal-network membership not inspected |
| `enp0s16` | UP, `10.50.30.5/24` | Connected route; VirtualBox internal-network membership not inspected |
| `docker0` | DOWN/no carrier, `172.17.0.1/16` | Docker bridge; connected route marked linkdown |

IPv6 also has a default route on `enp0s3` via `fe80::2`. `/etc/resolv.conf` resolves to `/run/systemd/resolve/stub-resolv.conf`; systemd-resolved reports DNS servers `10.0.2.3` and `fd17:625c:f037:2::3` on `enp0s3`. Other inspected links have no DNS servers. `getent ahostsv4 github.com` succeeded, as did read-only GitHub API operations. This verifies limited development-guest DNS/HTTPS access, not Proxmox egress.

Guest interface order and addressing are consistent with the supplied adapter layout. They cannot prove the physical host's VirtualBox network names, switching or connectivity to Proxmox storage/cluster interfaces.

### Bounded Proxmox endpoint check

Target: `https://192.168.56.80:8006/api2/json/version`. Checks used no credentials, no proxy, a 3-second connection timeout and an 8-second total timeout. No subnet scanning, insecure TLS retry or authentication attempt was made.

| Layer | Result | Interpretation |
| --- | --- | --- |
| Local route | `ip route get` chose `enp0s8`, source `192.168.56.64` | A direct local route exists |
| TCP | curl connected to `192.168.56.80`; final recorded connection time about 2 ms | TCP port 8006 was reachable during inspection |
| TLS | curl exit 60, verification result 20: unable to get local issuer certificate | TLS trust failed using the current trust store; other certificate checks, including identity, are not established |
| HTTP | curl status `000`; no authenticated response inspected | HTTP/API behaviour was not established |
| Authentication / authorisation | Not tested | No claim about API credentials, permissions or inventory |

The next live check needs a CA certificate obtained through an independently trusted channel, a matching certificate identity and a scoped read-only token. Do not fetch a certificate over this untrusted connection and silently treat it as trusted. No further endpoint retries are needed for this design.

## Follow-up: verified Proxmox SSH findings

This is the earlier baseline before the operator's one-CPU/16-GB change; the current incident/resource budget at the top supersedes its CPU/RAM observations.

Two bounded SSH sessions used alias `pve01` with `BatchMode=yes`, `StrictHostKeyChecking=yes`, `UpdateHostKeys=no`, a five-second connection timeout, one connection attempt, keepalive limits and a 45-second overall timeout. Existing host-key verification succeeded; no new host key was accepted and no SSH configuration/identity file was dumped. No passwords or credential files were read.

| Item | Verified observation |
| --- | --- |
| Identity | Hostname `pve01`; `jgipsz`, UID/GID 1000, groups `jgipsz` and `users` |
| Effective sudo policy | `sudo -n -l` lists `(ALL : ALL) NOPASSWD: ALL`; `sudo -n /usr/bin/id` returned UID/GID 0 without a password prompt |
| Proxmox | `pve-manager/9.2.2/b9984c6d90a4bd80`; `proxmox-ve` package 9.2.0; running kernel `7.0.2-6-pve` |
| CPU / memory | Two visible vCPUs, AMD Ryzen 7 3800X model; approximately 11 GiB RAM reported by `free -h`, approximately 10 GiB available |
| Management | `vmbr0` UP, `192.168.56.80/24`; `nic0` UP without an IP; bridge details readable through `ip` |
| Storage / cluster links | `nic1`: `10.20.20.80/24`; `nic2`: `10.30.30.80/24` |
| New uplink | `enp0s10` UP with dynamic `10.0.5.15/24`; the physical VirtualBox NAT attachment is supplied information, not host-verified |
| IPv4 default route | `default via 10.0.5.2 dev enp0s10`; no default through `192.168.56.254` appears in the current route table |
| IPv6 | ULA/link-local addresses and a default route via `fe80::2` on `enp0s10` |
| DNS | `/etc/resolv.conf` nameserver `10.0.5.3`; `getent ahostsv4 deb.debian.org` succeeded |
| Nested prerequisites | CPU `svm`/AMD-V exposed; `kvm` and `kvm_amd` loaded; nested module parameter `1`; `/dev/kvm` exists, mode 0660, owner `root:kvm` |
| KVM API | A sudo Python process opened `/dev/kvm` and queried `KVM_GET_API_VERSION`, returning `12`; no VM creation ioctl was called |

The broad passwordless sudo grant is an observed inspection capability, not the recommended controller credential model. It does not establish Proxmox API authentication/authorisation. The normal SSH user is not in the observed `kvm` group. KVM capabilities, device access as root and the API-version query **do not prove successful nested workload boot**. No VM was created, started or changed.

The `bridge` executable was not available in the remote unprivileged PATH. `ip` returned bridge details, but full bridge-port inventory and test-network connectivity still need validation. DNS resolution and a default route do not prove unrestricted outbound internet access or successful package downloads. No HTTP egress test was performed on PVE.

### Verified storage layout and capacity

| Layer / storage | Observation |
| --- | --- |
| Virtual block device | `sda`: 32 GiB; LVM partition approximately 31.5 GiB |
| Root LV | 13.81 GiB; ext4, approximately 4.2 GiB used and 8.7 GiB available in rounded `df` output |
| `local` directory storage | Active; 14,145,416 KiB total, 4,351,964 KiB used, 9,053,100 KiB available (about 8.63 GiB), according to `pvesm status` |
| `local-lvm` | Active LVM-thin; 12,378,112 KiB total/available (about 11.80 GiB), reported data used zero |
| Thin-pool health snapshot | `lvs`: `data` 11.80 GiB, data allocation 0.00%, metadata allocation 1.58% |
| VG free space | `vgs`: `pve` 31.50 GiB total, approximately 0.01 GiB unallocated |
| Swap | 3.88 GiB LV; unused at inspection |

Root free space and thin-pool free space are not interchangeable or additive guest capacity. At this earlier inspection, the old 11.8 GiB pool could not fit the proposed template/clone budget with reserve. That bottleneck is superseded by the expanded test storage below; the old store is unchanged. No storage or remote configuration was changed by Rehearsal.

## Storage expansion and runtime update

The user reports completion of a new 100 GiB `/dev/sdb`, VG `rehearsal-vg`, 90 GiB thin pool `data`, registered as `rehearsal-lvm` for `images,rootdir` on `pve01`. Reported metadata is 1 GiB with a separate 1 GiB spare, leaving about 8 GiB unallocated in the VG. Existing `local` and `local-lvm` are unchanged.

**Follow-up verified over bounded, host-key-checked SSH on 2026-11-12 at approximately 11:01 UTC:** `/dev/sdb` is 100 GiB; `pvesm status` reports active `rehearsal-lvm`, total/available 94,371,840 KiB (90 GiB), zero data used. `lvs` confirms 90 GiB, 0.00% data and 1.61% metadata usage; `vgs` reports 100 GiB total and 8 GiB unallocated for `rehearsal-vg`; `lsblk` shows a 1 GiB metadata LV. A selected-property read of storage configuration confirms `thinpool data`, `vgname rehearsal-vg`, `content images,rootdir`, `nodes pve01`. No storage changes were made.

Use **`rehearsal-lvm` for future template and test-VM disks**. The old 11.8 GiB `local-lvm` limit remains historical evidence, not the capacity of the new storage.

| Planning item | Budget inside the new thin pool |
| --- | --- |
| Pool capacity | 90 GiB |
| Explicit free-space reserve | 18 GiB: max(6 GiB, 20% of pool capacity) |
| Template + source + restore, full clones; revised Ubuntu plan | 3 × 12 GiB = 36 GiB logical commitment |
| Initial auxiliary-disk/temporary-growth allowance | 2 GiB; validate actual image/EFI/cloud-init requirements before admission |
| Unassigned pool headroom after these budgets | 34 GiB |

This table was revised during nested-guest preparation: the earlier three-by-6-GiB estimate left 52 GiB; three 12 GiB disks now leave 34 GiB. It is a conservative logical planning budget, not admission approval or expected initial physical consumption. The 8 GiB **unallocated VG space is outside the 90 GiB pool**, not extra current guest capacity. Metadata and its spare are separate allocations. Check data and metadata usage before every future run; thin provisioning is bounded by the pool and its backing storage. The [supplied host evidence](#user-reported-physical-host-capacity) confirms both `pve01` VDIs under `/mnt/ssd` and satisfies its initial physical backing-capacity gate. Continue actual host-space monitoring as dynamic disks grow; the host remains inaccessible from `dev01`, and no sustainable-performance claim follows. Backups and retained reports remain outside disposable VM disks. See [clone behavior, reserves and serial build admission](nested-guest.md#storage-and-concurrency-reconciliation).

An additional read-only `lvs -a` check verified both the 1 GiB metadata LV and separate 1 GiB `lvol0_pmspare`. At that stage, `rehearsal01` installation/access were unverified. Its later deployment and `.83` connectivity are verified in the current record above; nested workload boot remains untested.

## API inspection evidence and limitations (before deployment)

Read-only source inspection confirmed endpoint permissions and response fields in installed official packages: `pve-manager` 9.2.2, `qemu-server` 9.1.15, `libpve-storage-perl` 9.1.5, `libpve-access-control` 9.1.1 and `pve-docs` 9.2.1. Node status requires `Sys.Audit`; storage/VM list endpoints filter by datastore/VM rights. The initial network review checked its authenticated-user method declaration; live deployment later identified and corrected the missing bridge-audit filter assessment. The installed user-management HTML confirms privilege-separated tokens receive the intersection of owner and token ACLs. Current exact paths are in [live-inventory.md](live-inventory.md).

The successful sessions used batch mode, strict existing-host-key verification, one connection attempt, a five-second connection timeout, bounded keepalives and overall timeouts. Only selected non-secret storage properties and public source/documentation were printed; no user ACL database or credential files were read. `pvesh usage` inspected local schemas, not token authorization over HTTPS.

A later attempt during adapter implementation to inspect **public** certificate metadata failed with an SSH connection timeout. That phase made no token, ACL or trust changes. The subsequent authorised deployment resolved certificate inspection and established real application TLS/API access, as recorded above. The earlier timeout did not prove a TLS failure.

## User-supplied facts and historical information

### Physical host and adapter arrangement

- Ubuntu 24.04 Desktop; AMD Ryzen 7 3800X with eight physical cores; 64 GB RAM.
- VirtualBox **7.2.22 r175245**.
- `dev01` adapters: NAT, host-only `vboxnet0`, internal `LAB-EXT`, `LAB-INT`, `LAB-CTRL`, in that order.
- The normal development user cannot administer the physical host or VirtualBox from `dev01`. No SSH-to-host, shared-folder or `VBoxManage` dependency is available.

### Existing nested Proxmox

| Item | Supplied history |
| --- | --- |
| Node / version | `pve01`, previously observed Proxmox VE 9.2.2 |
| Resources | 2 vCPUs, 12 GB RAM, 32 GB virtual disk |
| Nested virtualisation | AMD-V and `/dev/kvm` previously observed |
| Management | `vmbr0`, `192.168.56.80/24`, bridged to `nic0`; HTTPS port 8006 |
| Storage link | `nic1`, `10.20.20.80/24`, VirtualBox internal network `lab-storage` |
| Cluster link | `nic2`, `10.30.30.80/24`, VirtualBox internal network `lab-cluster` |
| Default gateway | Historical `192.168.56.254`; superseded by the verified follow-up route through `10.0.5.2` |

`lab-storage` and `lab-cluster` are different names from all supplied `LAB-*` networks. Do not equate them, rename them implicitly or use them for test traffic. Shell and scoped API access are verified, but physical-host VirtualBox network memberships remain user-supplied. The user reports that the fourth PVE adapter is NAT and that the sudo rule passed `visudo -c`; guest addressing/routes and effective sudo behaviour were checked, not host settings or the earlier syntax-check event.

### Proposed host-only reservations

All addresses below are on `192.168.56.0/24`; reservations are subject to conflict checking by the operator. No address scan was performed.

| Address | Intended use | Evidence of existence |
| --- | --- | --- |
| `.80` | Existing `pve01` | SSH and real application TLS/API identity verified during deployment |
| `.81–.82` | Future Proxmox nodes | None |
| `.83` | `rehearsal01` | Current address, SSH, installed CLI and live read-only API access verified |
| `.84` | Optional trusted Actions runner | None |
| `.85` | Optional PBS | None |
| `.86–.89` | Other lab services | None |

## Unknowns and gates

| Unknown | How to resolve later | Gate |
| --- | --- | --- |
| Current PVE/guest state after second access loss | Operator console/restored management; reconcile new UPID, live ownership/tasks/locks/volumes, then safe owned stop. No additional start under the halted attempt | **Blocked on visibility**, 20:16 UTC incident |
| Controller/PVE reboot persistence | One restart each passed, changed boot IDs and fresh strict-key SSH/sudo plus live inventory; [evidence](supervised-build.md#completed-persistence-checks). Occasional dial timeouts remain bounded operational observations | **Passed**, 2026-11-12 |
| Token renewal/rotation | Existing token expires 2026-12-12; use deliberate operator action, never silent replacement | Before expiry |
| Initial `pve01` physical backing capacity | User-supplied report: 636 GB available on `/mnt/ssd`; screenshots confirm both dynamically allocated VDIs there | **Satisfied**, 2026-11-12; continue actual-space monitoring |
| Fresh capacity/admission evidence | Recheck PVE data/metadata/root plus operator-reported actual host free space as dynamic disks grow; preserve both reserves | Every admission |
| Successful nested workload boot | KVM prerequisites exposed; boot one owned tiny VM and record guest-agent/SSH evidence and cleanup separately | Milestone 3 |
| Template / guest allocation | VM 9000 and its two exact volumes are retained; new start/status/stop uncertain after renewed instability. No template or clone exists | **Recovery gate**, then later Milestone 3A |
| Test network interface/bridge configuration | Operator completed `REHEARSAL-TEST`, `vmbr1`/`enp0s16` and controller `enp0s9`/`10.77.0.1`; Linux configuration corroborated | **Complete**, 2026-11-12 |
| Platform firewall activation | Legacy PVE backend/kernel hooks and default-closed bridge guard active; controller filter preserved; fresh checks passed and new timer canceled | **Complete**, 2026-11-12 13:58 UTC |
| Guest connectivity and firewall enforcement | Exact profile/tuples were installed and PVE persistence read back; link never released. Actual guest/port/packet and peer checks pending; halt on renewed instability | **Unverified**; safe stop/reconciliation first |
| PVE download/HTTPS egress | NAT-route/DNS resolution verified; actual downloads not tested; prefer prepared images and controller-delivered artifacts | No assumed egress dependency |
| GitHub environment/branch controls and runner availability | Review in milestone 5; no configuration changes made now | Milestone 5 |

The original 32 GiB OS disk remains bounded, while test-disk planning now uses the separate 90 GiB `rehearsal-lvm` pool. `dev01` free space and physical-host RAM cannot be counted as its backing capacity. No end-to-end recovery, nested workload boot, performance or fault-tolerance capability has been verified.

## Offline implementation verification (0.1.0 history)

On 2026-11-12, the project `.venv` bootstrapped successfully with Python 3.12.3 and pip 24.0. System Python was not modified. Development tools are pytest 9.2.0, Ruff 0.17.4, build 1.6.1 and setuptools 84.2.1; direct/transitive tools and platform-specific wheel hashes are recorded in `requirements-dev.lock`. The application package has no third-party runtime dependencies.

Verified locally:

- **91 offline tests passed**, with sockets and DNS blocked by the test suite. These cover configuration validation, absence of credential reads, normalized inventory parsing, simulated failures, simulation labelling, output streams and rejection of implicit/live fallback.
- Ruff lint and format checks passed; `pip check` found no broken requirements.
- Editable installation succeeded. A separate fresh setup venv installed the hashed tools from cached wheels and installed the package without an index/build-isolation dependency download.
- Source distribution and wheel builds succeeded. A separate wheel-only venv contained only pip and Rehearsal and loaded both bundled fixtures successfully from outside the checkout.
- Actual console/module commands were exercised: help/version, human/JSON configuration validation, human/JSON fixture inventory, simulated permission failure, unreadable fixture and rejection of missing/live backend selection.

Builds, caches and test venvs are ignored local artifacts. No application API connection, live transport test, VM boot, provisioning, service/executor, database recovery, UI or Actions run was performed. Simulated success/failure output is not additional evidence about the lab. Setup, schema and commands are documented in [development.md](development.md).

## Inspection methods and scope

Read-only tools used: repository file discovery with `rg`, licence/instruction reads, Git status/remotes/history, OS release and kernel queries, `lscpu`, `free`, `df`, `lsblk`, executable/version/module checks, `ip`, `resolvectl`, name resolution, init/service status, Docker version/info, safe GitHub account/repository queries and bounded curl checks to the supplied endpoint. Credential files and environment variables were not dumped.

The initial design/adapter phases were read-only on the lab and used local project tooling. The later, explicitly authorised controller bootstrap added the limited runtime setup and audit identity/token/ACLs recorded above. Public source/documentation is distinguished from actual TLS/API evidence. No test resources, PVE network/storage configuration, runner or backup job was changed, and no commit or push occurred. Secrets and environment variables were not dumped.

## API adapter verification (0.2.0, before deployment)

Development continues on `dev01` in the project venv. HTTPX 0.28.1 is the only direct runtime addition; its transitives and the development tools have separate hashed locks for Python 3.12/Linux x86_64. System Python is unchanged.

- **153 tests passed** with sockets/DNS blocked. Mock transports cover GET-only requests, successful normalization, partial nodes/sections, 401/403, TLS errors/context settings, transient retry limits/deadlines, malformed/oversized responses, token permissions, reflected-secret redaction and CLI opt-ins before credential access. Injected transports are labelled simulated.
- Ruff lint/format and dependency consistency checks passed. Configuration validation, fixture human/JSON output, module/console entry points, simulated failure and missing-live-opt-in examples were exercised outside the checkout.
- Source/wheel packaging and separate runtime-venv installation checks use the versioned wheel, hashed runtime dependencies and bundled fixtures; they require no controller access or real token.

These were offline software checks. The later controller deployment separately verified real TLS/API access and audit permissions; it did not change the application or repeat the unit suite. Nested VM boot remains untested. Current deployment paths and exact audit scopes are in [the runbook](live-inventory.md).
