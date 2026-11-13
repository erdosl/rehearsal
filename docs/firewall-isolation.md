# Test-network firewall inspection and implementation plan

Updated **2026-11-12, after operator recovery**. Exact VM 9000 policy/tuples were installed while stopped, with passing checks and rollback timers canceled before the initial start. An operator restart with one vCPU/16 GB later allowed read-only reconciliation of the existing stopped guest. **The PVE guest profile, bridge guard/tuples and active legacy hooks persisted and passed fresh checks. A distinct new start again lost management access; the attempt is halted.** Guest status/stop, actual boot and packet enforcement remain unverified. No link release, rule/access widening, lock clearing or uncertain deletion occurred. Controller filtering/access remain verified. [Current incident and recovery boundary](supervised-build.md#operator-restart-and-supervised-recovery-attempt) supersede earlier snapshots.

After the operator restart, node boot ID was `3256e72c-f8a3-4b92-adb4-746acd8b6605`, IP routing remained disabled, bridge enp0s16 was the sole forwarding physical port, host IPv6 stayed disabled and effective/persistent PVE guard SHA-256 remained `5d1206cb16128a77fac110ef7b92f8d8f1a60f1474b5c2a01e017d9e9fe46945`. Exact VM policy/IP set and controller tuple also matched. PVE profile persistence is observed; the controller has not been rebooted since tuple addition, and neither observation passes guest packet enforcement.

The new uncertain start is **`UPID:pve01:00001794:0001C753:6AF61EA4:qmstart:9000:rehearsal-build@pve!bootstrap-9000:`**, operation **`a9cf5dc8-7654-40c0-99c0-a0ba6e589a88`**. Responsiveness monitoring failed at 20:16:43 UTC; no NIC release followed. The earlier original UPID remains preserved with an unavailable historical result but its stopped current effect was independently reconciled across the external restart before this attempt. Further work is read-only reconciliation and a safe owned stop when management returns, not another boot/test attempt. No firewall change or rollback timer was introduced in this resumption; the earlier timers were already canceled and never ran.

## VM 9000 policy applied; packet enforcement pending

The exact guest firewall options, ipfilter-net0 `10.77.0.10`, controller-only SSH/echo allowances and terminal IN/OUT DROP were applied/read back through scoped API operations while stopped. Installed PVE prepends rules; digest-protected bounded moves established the documented order without duplicate writes. The bridge guard now contains the four exact `fwpr9000p0`/`02:52:40:61:0e:f4`/`10.77.0.10`/controller pair rules; controller guests4 contains only that tuple. Persistent hashes and root backups are in the execution record. No global engine, host-zone, forwarding or unrelated rule change occurred.

Controller then PVE guard updates each had a verified eight-minute automatic rollback armed before modification. Fresh strict SSH/sudo, unchanged addresses/defaults/forwarding, DNS/NAT HTTPS and original verified-TLS inventory passed. Timers were canceled at **16:04:41/45 UTC**, never ran, before issuing start. Rollback restores only the empty closed guest allowlist and preserves platform enforcement. Their private scripts/backups are under `/root/rehearsal-guest9000-20261112T154515Z` on the respective machines.

Pre-start compilation and policy readback passed; **actual running guest topology/QMP KVM and kernel-port checks did not complete**. The sole NIC was last read with `link_down=1`; link release never occurred. Start UPID **`UPID:pve01:00007245:000A305E:6AF5E4EC:qmstart:9000:rehearsal-build@pve!bootstrap-9000:`** remains uncertain after API/SSH timeouts. Do not repeat start, remove isolation or delete the resource to guess the outcome. Restore management visibility through the operator recovery path, then reconcile the exact task, ownership, lock, current status and volumes before further mutations.

All guest positive/negative packet tests, authenticated guest SSH trust, actual KVM/Ubuntu boot and guest-rule reboot persistence remain pending. A stopped-VM configuration or compiled chain cannot pass guest isolation. PVE's latest successful guard verification predates the access loss; its current effective state cannot be claimed from the controller's still-passing filter checks.

## Persistence verified before first provisioning

The controller passed its one authorized reboot at **14:16 UTC**, then PVE passed its one reboot by **14:20 UTC**, with changed boot IDs and bounded fresh SSH reconnects. Both retained unchanged management/default routes, disabled routing forwarding, enabled effective custom guards and persistent file bytes. PVE retained selected legacy enforcement and actual IPv4/IPv6 hooks, bridge netfilter 1/1 and the sole IP-less vmbr1/enp0s16 path with host IPv6 disabled. Node host-zone filtering remains off. Fresh SSH/sudo, DNS/NAT HTTPS and real verified-TLS inventory passed after both restarts. No firewall repair/reload was required.

At **15:02 UTC**, repeated physical-test-interface probes through controller enp0s9 to test/management/NAT IPv4 SSH destinations again hit input drops: **3 packets / 120 IP bytes**, accept zero. This verifies those controller input paths after reboot, not a guest path. Both guest allowlists remain empty and no per-VM profile exists. No rollback timer is active; reboot validation did not arm another timer. [Exact reboot evidence and comparison limits](supervised-build.md#completed-persistence-checks) include the harmless pmxcfs inode changes, protected evidence paths and preserved inventory release/credential.

The first-guest authorization permits only stopped-guest exact policy/allowlist changes, followed by supervised boot and packet tests. Preserve the platform guards. Guest-specific rollback is stop/disconnect the positively owned VM, reconcile its tasks, then remove only its matching tuples/profile; never restore an open platform while a guest is connected. Platform reboot persistence is now verified, while persistence of future guest-specific rules remains pending.

## Successful PVE-only activation

The user explicitly resumed **PVE only**, authorizing completion after correcting the verifier sequencing. The controller firewall was neither reloaded nor edited. Bounded SSH used batch mode, `ControlMaster=no`, `ControlPath=none`, strict existing-host-key verification and no host-key replacement. The restored PVE baseline was reinspected: cluster/host firewall files absent, nftables empty, permissive legacy rules, no candidate unit, one node and no guests. Baseline DNS/NAT HTTPS and real controller inventory passed before activation.

The verifier now has explicit **before** and **after** phases. **Eight offline unit tests passed**, including disabled compilation without active chains, rejection of compilation-only enforcement, missing IPv4/IPv6 hooks, missing bridge guard/switches, compiler failures/warnings, wrong backend, changed management/routing policy and phase mismatches. Generated activation syntax and `before → explicit enable → after` ordering were checked locally before changes. Installed `PVE/Firewall.pm:4235` independently confirms that disabled cluster configuration returns empty compiled rules. Verifier sources, tests and results are retained in the private change directory.

| Stage / UTC | Verified evidence |
| --- | --- |
| Backup/preparation, 13:56 | Fresh **`/root/rehearsal-firewall-20261112T135245Z`**, directory 0700; selected backups, absent-file markers, original rules/options/network/sysctls, rollback script and intent/result ledger; no credential contents copied |
| Rollback armed, **13:56:21** | Fresh **`rehearsal-pve-firewall-rollback-20261112T135245Z.timer`**, active/waiting, due **14:06:21**; local rollback procedure verified before applying anything |
| Before activation, **13:56:41** | Digest-protected local API writes staged node `enable=0,nftables=0` and cluster `enable=0,ebtables=1,policy_in=ACCEPT,policy_out=ACCEPT`. nft check/unit validation passed. `pve-firewall compile` exit **0**, empty stderr, disabled output accepted; verifier explicitly recorded **`enforcement_verified=false`** |
| Explicit activation | Journaled **one** digest-protected `pvesh set /cluster/firewall/options --enable 1`. Synchronous readback confirmed success; no UPID is returned by this option operation. No mutation retry |
| After activation, **13:57:01** | Status **`enabled/running`**, warning-free compilation and actual legacy **IPv4 and IPv6 `FORWARD → PVEFW-FORWARD`** kernel hooks. IPv4/IPv6 bridge netfilter switches **1/1**, independent five-rule native bridge guard present, routing forwarding **0/0**. Post-phase verifier recorded **`enforcement_verified=true`** for this platform configuration |
| Fresh checks, **13:57:08–11** | New dev01 SSH/passwordless sudo; DNS plus NAT-interface HTTPS **HTTP 200 / TLS verify 0**; unchanged addresses/default routes and unrelated nftables; persistent files match candidates and effective hooks; controller integrity comparison and verified-TLS live inventory passed |
| Timer canceled, **13:57:11** | Canceled **only after all checks**; timer inactive/dead, rollback service never started (`ExecMainStartTimestampMonotonic=0`). No rollback was required |
| Final readback, **13:58:19** | Backend still enabled/running; guard enabled/active/exited with no overrides; timer inactive, no guests; node/cluster options and persistence unchanged |

The selected backend is **legacy `pve-firewall`**, explicitly `nftables=0`. Existing `pve-firewall` and `proxmox-firewall` daemons remain active/enabled; service activity alone was not accepted as enforcement. There are no competing PVE nftables tables. The distribution nftables service remains inactive/disabled. Node host-zone filtering deliberately remains **off** (`enable=0`), with cluster INPUT/OUTPUT policies ACCEPT, preserving management. Native `bridge rehearsal_test` applies only to `vmbr1`; its guest-pair chain contains only the terminal drop, so **no guest is admitted**.

PVE persistence consists of `/etc/pve/firewall/cluster.fw`, `/etc/pve/nodes/pve01/host.fw`, `/etc/rehearsal-firewall/test-filter.nft` and the enabled `/etc/systemd/system/rehearsal-test-filter.service`. pmxcfs ownership/modes were preserved. The nft file is root-owned 0600, the unit root-owned 0644, and their bytes match the repository candidates:

| PVE file | SHA-256 |
| --- | --- |
| Bridge guard | `578594c83c0acb4d67c8880b07e8d33673a6f4ad43851cf92680c47ed5a208cc` |
| Persistence unit | `0cb393d4a5f6bb17d33e07778d6ba2fff183b2f641e1c0aef1385316b9c4d503` |

All PVE interface addresses and IPv4/IPv6 defaults matched the fresh snapshot, including management `192.168.56.80/24`, NAT `10.0.5.15/24`, default `10.0.5.2` and IPv6 default `fe80::2` on `enp0s10`. IPv4/IPv6 **routing** forwarding remains disabled; the enabled **bridge** netfilter switches are separate settings. No management/storage/cluster/NAT interface or persistent network file was edited. The controller's file metadata/hashes, stateless effective nft JSON (including handles), service state, addresses/routes, application release/config/CA and token metadata exactly match its pre-activation snapshot. Its routing forwarding remains 0/0. No controller firewall operation or API privilege/credential change occurred.

Fresh live inventory ran as `rehearsal`, with `--backend live --live` and `REHEARSAL_LIVE=1`, using the existing trusted CA and token. Both runs returned **exit 0**, `backend=live`, `simulated=false`, `complete=true`, four queried sections, active `rehearsal-lvm`, six audit-visible network interfaces and zero VMs. `vmbr1` audit scope was not broadened. Sanitized runtime-owned 0600 reports, metadata and stderr remain on the controller; the previous latest-report pointer is unchanged:

| Phase | Report | SHA-256 |
| --- | --- | --- |
| Before, 13:55 UTC | `/var/lib/rehearsal/reports/firewall-20261112T135245Z-before.json` | `95a03f95650ed302152185cd0c976321bc68b4000af43e81f4c35482b7fe2713` |
| After, 13:57 UTC | `/var/lib/rehearsal/reports/firewall-20261112T135245Z-after.json` | `b0d2a157c8ab6d8af4403d72ffc988b6ff9257550ce7a226b7c2a62a2b236041` |

**Remaining before/with first guest boot:** create no guest merely to validate the firewall. In a separately authorized owned-resource operation, render and read back the stopped guest's exact VM/NIC firewall, port/MAC/IP/ARP pair and controller tuple before allowing packets. No per-VM rules or tuples are installed yet. Nested-MAC passage, controller-to-guest SSH/ping and return allowances, IPv4/IPv6/DHCP/RA/ARP/spoof/tag/peer negative tests, controller forwarding packet tests and persistence across a separately authorized reboot remain pending. Framework/kernel inspection and compilation do **not** establish guest isolation. No guest, reboot, package install, commit or push occurred in this activation.

## Previous activation attempt

The user authorized the scoped firewall/persistence changes, one machine at a time, with automatic rollback armed before changes and cancellation only after that machine's checks. Execution used fresh SSH connections with `ControlMaster=no`, `ControlPath=none`, batch mode, strict existing-host-key verification and bounded timeouts. No TLS/SSH verification was disabled, no unrelated rules flushed, and no access broadened.

| Machine | Result and rollback timer |
| --- | --- |
| `rehearsal01` | Applied the exact controller nft/unit candidates; root-owned rule file 0600 and unit 0644, service enabled/active/exited, no overrides, seven effective rules and an empty guest set. Ten-minute timer armed at **13:39:46 UTC**, due 13:49:46; canceled at **13:42:05 UTC** after checks. Automatic rollback never ran |
| `pve01` | Ten-minute timer armed at **13:42:57 UTC**, due 13:52:57. Bridge guard installed and disabled cluster/host options staged. The operator verifier incorrectly required `PVEFW-FORWARD` from the **pre-enable** compiler output. Compilation returned exit **0**, empty stderr and **`firewall disabled`**, so the assertion failed before the cluster-enable request. Manual rollback returned exit **0**, verified by **13:44:55 UTC**; its timer was then inactive and never fired. Only ledger-matching newly created installed files were removed; original absent cluster/host configuration and permissive kernel state restored. No PVE reapplication occurred in that window |

The PVE failure was a verifier error, **not evidence of a compiler/daemon failure or lost management access**. The disabled flag makes this version's pre-enable compiler output empty; requiring enabled chains at that point was incorrect. The user required rollback and stop, so that attempt left PVE unconfigured. The separately authorized PVE-only retry above corrected/tested sequencing, preserved the controller and completed activation. The observations in this section describe the earlier window, not current PVE state.

Each VM retains its private backup, staged candidates, intent/result ledger, rollback procedure and selected evidence under **`/root/rehearsal-firewall-20261112T133629Z`**, directory 0700 and evidence files 0600 (rollback script 0700). The PVE ledger includes the original absent-file markers, API digests, compiler result, manual rollback result and final cleanup verification. No backup contains the inventory token. The scripts and raw evidence are not copied into this public repository.

Controller installed paths are `/etc/rehearsal-firewall/test-filter.nft` and `/etc/systemd/system/rehearsal-test-filter.service`. Their SHA-256 values match the repository candidates exactly:

| File | SHA-256 |
| --- | --- |
| Controller nft file | `5aa6de3e99335be8ba328a2e0cf7131916bf1cd05e0c5445b4f082caf154af77` |
| Controller unit | `52334a92bf43422438ee265d58d8e1b5e23154f1b2f2a3564499143d7e3e009e` |

Verified results, including final readback/live inventory at **13:45 UTC**:

- Fresh dev01 SSH and `sudo -n` root access passed on both VMs. All management addresses, IPv4/IPv6 defaults and interface addresses matched their pre-change snapshots. Routing forwarding stayed **IPv4 0 / IPv6 0** on both.
- DNS resolution of `archive.ubuntu.com` and IPv4 HTTPS HEAD through the named NAT interfaces (`enp0s3` controller, `enp0s10` PVE) returned **HTTP 200 / TLS verification 0**, before changes and in each machine's final state. No package was installed.
- The controller filter's persisted files match the tested files, its running chains match the proposed hooks/rules, and unrelated nftables state is unchanged. UFW remains inactive and the distribution nftables unit inactive/disabled. Controller forwarding-deny rules are installed but have not had forwarded traffic exercised.
- At **13:41:43 UTC**, three bounded synthetic TCP SYN frames from PVE's physical test interface were observed arriving on controller **`enp0s9`**, addressed individually to **`10.77.0.1:22`**, **`192.168.56.83:22`** and **`10.0.2.15:22`**. Their source was PVE's existing `192.168.56.80` and test MAC; no IP/interface was added. The input-drop counter increased **0 → 3 packets / 120 IP bytes**, with accept counters zero. This proves those IPv4 controller-input paths hit the interface filter; it does not exercise a nested guest, PVE guest policy, IPv6 or peer isolation.
- Final PVE state matches the initial baseline: `disabled/running`, empty cluster/node options, empty nftables, permissive legacy rules, no candidate unit/table/configuration left installed, bridge netfilter switches **0**. Existing PVE daemons and management/NAT interfaces remain unchanged. PVE guest enforcement is **not active**.
- The release symlink, application configuration/CA hashes and token ownership/mode/inode/size/mtime remained unchanged. The live CLI reused the existing credentials with both explicit live opt-ins and verified TLS; no ACL/token/release changes occurred.

Sanitized live-inventory reports remain runtime-owned 0600 on the controller, with companion metadata and sanitized stderr. All three runs returned **exit 0**, `backend=live`, `simulated=false`, `complete=true`, all four sections queried, `pve01`, active `rehearsal-lvm`, six audit-visible network interfaces and zero VMs. `vmbr1` audit privilege was not added; list visibility remains ACL-filtered. The previous latest-inventory pointer was not changed.

| Phase | Report under `/var/lib/rehearsal/reports/` | SHA-256 |
| --- | --- | --- |
| Before changes, 13:38 UTC | `firewall-20261112T133629Z-before.json` | `95a03f95650ed302152185cd0c976321bc68b4000af43e81f4c35482b7fe2713` |
| After controller, 13:41 UTC | `firewall-20261112T133629Z-controller.json` | `b0d2a157c8ab6d8af4403d72ffc988b6ff9257550ce7a226b7c2a62a2b236041` |
| After PVE rollback, 13:45 UTC | `firewall-20261112T133629Z-after-pve-rollback.json` | `95a03f95650ed302152185cd0c976321bc68b4000af43e81f4c35482b7fe2713` |

Temporary verification tooling also needed two corrections: JSON tuple/list normalization (the actual network values matched), and escaping in the initial packet generator (no frames were sent by that failed generator). Those attempts are retained privately; neither required a rule change. The completed checks above passed. Application code, existing credentials, API privileges and operator network configuration were not changed. No guests, reboot, commit or push occurred.

The subsequent PVE-only activation is recorded above. Exact stopped-guest port/MAC/IP/VM policy and controller tuples plus guest packet tests remain outstanding. A startup admission hook and runtime firewall updater do not exist; platform activation alone does not pass guest admission.

## Original read-only inspection evidence

The [environment record](environment.md#operator-supplied-dedicated-test-network) preserves the operator's VirtualBox and interface findings as supplied facts. Strict existing-host-key SSH independently inspected both VMs beginning **13:22 UTC**, using batch mode, one attempt, five-second connection timeouts and outer timeouts. No physical-host access was used. Only selected public network/firewall configuration, installed source and kernel state were read; raw reports and credentials were not saved in Git.

| Verified on 2026-11-12 | Consequence |
| --- | --- |
| PVE 9.2.2 / kernel `7.0.2-6-pve`; `pve-firewall` 6.0.4, `proxmox-firewall` 1.2.3, nftables 1.1.3 | Match the proposal to the installed implementation, not a service name |
| `vmbr1` and `enp0s16` UP/LOWER_UP, sole port forwarding, MAC `08:00:27:0f:b7:12`, neither has an IP; persistent IPv6-disabling post-up commands present | Interface/bridge step complete; this does not demonstrate a nested MAC crossing VirtualBox |
| PVE host IPv6 `disable_ipv6=1` on both test devices | Disables host-stack IPv6 there; does not filter bridged IPv6 frames |
| Both PVE firewall daemons active/enabled; `pve-firewall status` **`disabled/running`** | No effective PVE guest policy |
| Cluster/node option GETs contain only empty-content digests; `cluster.fw` and `host.fw` absent; firewall directory empty | No explicit engine selection or configured cluster/node rules |
| PVE nftables empty; legacy IPv4/IPv6 raw/filter chains ACCEPT; legacy ebtables INPUT/FORWARD/OUTPUT ACCEPT | No inspected packet-deny boundary; no NAT rules |
| PVE `bridge-nf-call-iptables`, `bridge-nf-call-ip6tables`, `bridge-nf-call-arptables` all `0` | Legacy IP rules alone would not currently cover the bridge path |
| `/nodes` contains only `pve01`; `/cluster/resources?type=vm` and `qm list` empty | No existing guest policy to migrate; recheck before any cluster-wide enable |
| Controller `enp0s9` UP/LOWER_UP, MAC `08:00:27:79:e0:74`, `10.77.0.1/24` only; matching Netplan file disables DHCP4/6, RA acceptance and link-local | Supplied Linux configuration independently corroborated |
| Controller UFW **inactive**, while `ufw.service` active/exited and enabled; nftables service inactive/disabled; firewalld absent | Service enablement is not rule enforcement |
| Controller nftables has only empty `ip filter`/`ip6 filter` tables; iptables-nft ACCEPT; legacy saves empty | No inspected controller input filtering |
| Controller SSH listeners `0.0.0.0:22` and `[::]:22` | SSH also listens on the test address; input policy is required |
| Controller test `accept_ra=0`, no IPv6 address, but `disable_ipv6=0`; `rp_filter=2` | No current IPv6 address is not an IPv6 firewall; loose reverse-path checks are not isolation |
| Both VMs IPv4/IPv6 forwarding `0`; management/NAT routes intact | Preserve these values; explicitly deny controller forwarding as well |

PVE management remains `vmbr0` / `192.168.56.80`; controller management is `enp0s8` / `192.168.56.83`. `dev01` currently uses `192.168.56.64`. PVE's NAT uplink is `enp0s10` via `10.0.5.2`; the controller's is `enp0s3` via `10.0.2.2`. No probing of guests, network scan, image download or live inventory run was needed for this inspection.

A final readback at **13:32 UTC** confirmed unchanged empty/permissive nftables state, no installed `rehearsal-test-filter.service` on either VM, PVE still `disabled/running`, unchanged empty cluster/node options, no cluster guests, and controller UFW still inactive. Check-only validation left no candidate table installed.

## Selected design

Use the installed **legacy PVE engine** for stateful per-VM policy (`nftables: 0`), with cluster enforcement now enabled. Keep **PVE host-zone filtering disabled** (`enable: 0` in `host.fw`), explicitly preserving the current management policy. Installed `PVE/Firewall.pm` compiles guest chains independently of this host-zone switch. A separate, narrowly scoped **native nftables bridge guard** covers only `vmbr1`: it blocks PVE-local input/output on that bridge and, after future admission, permits forwarding only between a recorded guest port/MAC/IP and the controller MAC/IP. All other EtherTypes, including IPv6 and tagged frames, are dropped. PVE's future VM policy restricts the allowed IPv4 pair to controller-originated SSH/ping and replies. Both boundaries are required before admission; the current bridge chain has no guest allow rules.

This avoids switching to the installed PVE nftables backend, which the installed host-option schema labels tech preview. Do not stop either existing PVE daemon, change iptables alternatives, enable the distribution nftables service, or add legacy host `FORWARD` rules as a substitute. The stock PVE engine ignores host/VNet forward rules. See [Proxmox firewall documentation](https://github.com/proxmox/pve-docs/blob/master/pve-firewall.adoc); installed source was checked for the version-specific behaviour described here.

The extra bridge guard is necessary for the exact layer-2/IPv6 policy: PVE inserts conntrack accepts and some protocol exceptions before user rules, and host IPv6 disablement cannot stop forwarding. Native bridge hooks filter the frame path without depending on the `bridge-nf-call-*` switches. See [Netfilter bridge filtering](https://wiki.nftables.org/wiki-nftables/index.php/Bridge_filtering).

On the controller, use one owned **inet nftables table** scoped to `enp0s9`. Allow only recorded IPv4 guest replies to controller SSH/ping, plus related IPv4 errors, addressed to `10.77.0.1`; drop everything else arriving on this NIC, including new guest-to-controller SSH, traffic to the controller's management/NAT addresses, IPv6, DHCP and RA. Deny forwarding both into and out of that NIC regardless of future forwarding sysctl drift. ARP is outside the inet family; the PVE bridge guard constrains guest ARP. Future directly attached machines on `REHEARSAL-TEST` require a separate review of that trust boundary.

No global INPUT/FORWARD default changes, NAT, guest gateway, external DNS, or controller listening service are added. Application HTTP ports and peer communication remain closed; add explicit ports through a later reviewed configuration change. The controller's NAT and SSH/API management flows traverse different interfaces and do not match these guards.

## Reviewable candidate files

| Target | Repository candidate | Installed path |
| --- | --- | --- |
| `pve01` bridge guard | [pve-test-bridge.nft](../examples/firewall/pve-test-bridge.nft) | `/etc/rehearsal-firewall/test-filter.nft` |
| `pve01` persistence unit | [pve-test-filter.service](../examples/firewall/pve-test-filter.service) | `/etc/systemd/system/rehearsal-test-filter.service` |
| `rehearsal01` input/forward guard | [controller-test-input.nft](../examples/firewall/controller-test-input.nft) | `/etc/rehearsal-firewall/test-filter.nft` |
| `rehearsal01` persistence unit | [controller-test-filter.service](../examples/firewall/controller-test-filter.service) | `/etc/systemd/system/rehearsal-test-filter.service` |

Both **default-closed files are now installed**, with no admitted guest. They replace only their own `rehearsal_test` table in one nft transaction: `add` tolerates an existing table, followed by deletion/recreation in the same batch. They never flush the whole ruleset or touch PVE-owned chains. Each unit's stop removes only its own table. Stopping it removes that boundary, so future guests must first be stopped/disconnected and reconciled. Reloading replaces the owned table atomically; do not restart to edit rules.

On **2026-11-12**, both baseline files passed **`sudo -n nft --check --file -` on their actual target VM**, streamed over verified SSH without installing a file. Both units passed local `systemd-analyze verify`. Check-only validation does not apply rules or prove packet enforcement. [Netfilter's nft manual](https://netfilter.org/projects/nftables/manpage.html) documents check mode, bridge interface names, concatenations and conntrack directions. The generated guest-profile syntax check is recorded below; it does not reserve an identity.

The installed controller `/etc/nftables.conf` contains **`flush ruleset`**, and its distribution unit's `ExecStop` also flushes globally. Leave that file/unit untouched and inactive. UFW stays inactive. These candidates need no new packages or Python dependencies. Operator work uses existing SSH/sudo; the unprivileged application receives no firewall-admin capability.

## Original empty-network activation procedure

These steps describe the original empty-network procedure. The first attempt stopped after rollback; the separately authorized PVE-only retry above completed the PVE portion with a fresh backup/timer and the corrected phase verifier. The controller was checked read-only and its installation/absence steps were not repeated. Current installed state supersedes the original absent-file prerequisites. No guest creation/boot belongs to a firewall-only window.

1. Arrange operator console recovery for both VMs and retain existing management SSH sessions. Freeze concurrent PVE/network/firewall changes. Recheck target hostnames, single-node membership, empty cluster guest list, routes, rule dumps and service states against the evidence above. Require no existing `rehearsal_test` table, `/etc/rehearsal-firewall`, or `rehearsal-test-filter.service`, and still-absent PVE cluster/host firewall files. If any baseline differs, preserve it and rebase this plan; do not overwrite it. Keep `vmbr0`, `enp0s8`, all NAT/storage/cluster interfaces and operator-created network configuration out of the edits.
2. On **each target**, in a root shell with `umask 077`, create a new private change directory using `mkdir -m 0700 /root/rehearsal-firewall-20261112`. An existing directory is a stop condition; select and record a fresh change ID instead of overwriting. Save UTC time, selected addresses/routes, `nft -a list ruleset`, both IP-family saves and service enable/active states. On PVE also save ebtables and option GETs and record the absence of the two PVE files. Keep these raw snapshots outside Git. Record candidate SHA-256 values and installed paths in this directory as the change ledger.
3. On **PVE**, save the runtime sysctl values touched by the installed legacy engine before enabling it. The following file contains only the selected numeric network settings; no credentials:

   ```bash
   /usr/sbin/sysctl -e \
     net.bridge.bridge-nf-call-iptables \
     net.bridge.bridge-nf-call-ip6tables \
     net.bridge.bridge-nf-call-arptables \
     net.ipv4.tcp_syncookies \
     net.netfilter.nf_conntrack_max \
     net.netfilter.nf_conntrack_tcp_timeout_established \
     net.netfilter.nf_conntrack_tcp_timeout_syn_recv \
     net.netfilter.nf_conntrack_log_invalid \
     > /root/rehearsal-firewall-20261112/sysctl.before
   ```

   Do not alter/persist these settings manually during activation. Installed `apply_ruleset` sets the IPv4/IPv6 bridge switches to `1`; check that result later. Routing forwarding remains `0`.
4. Prepare `/root/rehearsal-firewall-20261112/rollback.sh` on each target from the corresponding rollback block below; make it root-owned mode 0700. Verify its target paths, shell syntax (`bash -n`) and baseline assumptions. Before activation, arm a local ten-minute recovery timer **on each VM**:

   ```bash
   systemd-run --unit=rehearsal-firewall-rollback --on-active=10m \
     /root/rehearsal-firewall-20261112/rollback.sh
   systemctl list-timers rehearsal-firewall-rollback.timer
   ```

   Require a scheduled timer before proceeding. This is a future local recovery mechanism, not a Rehearsal executor. If it fires or the SSH result is uncertain, read back current state; never blindly repeat activation.
5. Transfer only the matching two candidate files to that VM's private change directory over verified SSH. Recheck their hashes, then install the nft candidate root-owned mode 0600 under a new root-owned 0700 `/etc/rehearsal-firewall`; install the matching unit root-owned mode 0644 as `/etc/systemd/system/rehearsal-test-filter.service`. Use `install -d`, `install -m 0600` and `install -m 0644` with these exact source/destination pairs after the absence checks. No runtime release/config/token file changes. On each target:

   ```bash
   nft --check --file /etc/rehearsal-firewall/test-filter.nft
   systemd-analyze verify /etc/systemd/system/rehearsal-test-filter.service
   systemctl daemon-reload
   systemctl enable --now rehearsal-test-filter.service
   ```

   Apply the **controller first**, verify management, then PVE. Require successful exit and `nft list table inet rehearsal_test` on the controller / `nft list table bridge rehearsal_test` on PVE. Both should still admit no guests.
6. On PVE create these two initially absent files through the local operator session. Prepare **`host.fw` first**, then `cluster.fw` with `enable: 0`; no daemon restart is needed. Keep the node host-zone firewall explicitly disabled, so cluster enable cannot introduce a management INPUT deny policy.

   `/etc/pve/nodes/pve01/host.fw`:

   ```ini
   [OPTIONS]
   enable: 0
   nftables: 0
   ```

   `/etc/pve/firewall/cluster.fw`:

   ```ini
   [OPTIONS]
   enable: 0
   ebtables: 1
   policy_in: ACCEPT
   policy_out: ACCEPT
   ```

   Record exact file contents/hashes and permissions in the private ledger; preserve pmxcfs semantics rather than chmod/chown its files. The attempt used digest-protected local `pvesh set` operations to stage these options, with intent and synchronous readback recorded before the next operation. Run `pve-firewall compile` and treat any warning/parser error as failure even if its exit status is zero. **With cluster `enable: 0`, installed PVE 9.2.2 legitimately emits empty command lists and `firewall disabled`: do not require `PVEFW-FORWARD` yet.** No per-VM chain is expected without guests. Verify the staged options through readback; in a later authorized retry, finally enable the cluster gate **once**:

   ```bash
   pvesh set /cluster/firewall/options --enable 1
   ```

   **After** enabling, rerun `pve-firewall compile` and require warning-free compiled framework hooks plus their actual kernel counterparts. Read back cluster/node options and effective rules. Require `pve-firewall status` enabled/running, `nftables: 0`, node host-zone `enable: 0`, PVE legacy FORWARD hooks, bridge IPv4/IPv6 switches `1`, owned bridge guard present, and IP routing forwarding still `0`. Do not stop the existing `proxmox-firewall` daemon merely because it is running; the selected legacy mode must leave no competing PVE nftables rules. Unexpected rules or incomplete application require rollback and stop. This post-enable stage passed in the successful PVE-only activation above; it was not reached in the earlier rolled-back attempt.
7. From fresh strict-host-key SSH sessions on `dev01`, verify SSH to `.80` and `.83`, and from the controller verify routing and PVE TLS using existing trust, without dumping credentials:

   ```bash
   ip -4 route get 192.168.56.80
   timeout 10s openssl s_client -connect 192.168.56.80:8006 \
     -CAfile /etc/rehearsal/pve-ca.crt -verify_ip 192.168.56.80 \
     -verify_return_error -brief < /dev/null
   ```

   Compare management/NAT routes and existing service states. A retained SSH connection alone is insufficient. A later full inventory still needs its documented explicit live opt-ins; do not broaden audit ACLs just because `vmbr1` now exists.
8. Only after both VMs pass fresh access/rule checks, cancel **both** recovery timers with `systemctl stop rehearsal-firewall-rollback.timer`, confirm they are inactive and that neither rollback service ran, and retain the private evidence. If rollback raced cancellation, reconcile state and classify activation incomplete. Record default-closed configuration as installed only after actual execution. Packet enforcement and persistence across reboot still require separate validation; this inspection does not claim either.

## Future owned guest profile: separate authorization

No VM/MAC is reserved here. The first future resource is proposed 9000, `net0`, `10.77.0.10/24`; validation clone 9100 uses that IP **serially** with a fresh MAC. The later restore `.11`/9101 requires its own review. Keep the resource stopped, sole NIC on `vmbr1`, `firewall=1`, `link_down=1`, no VLAN/trunk/gateway, `onboot=0`, and durable installation/run/resource ownership before constructing a profile. Use validated configuration plus live readback, not prefix/VMID-range inference. Journal intent before API writes and reconcile uncertain responses/UPIDs.

For an actual owned resource, render `/etc/pve/firewall/<VMID>.fw` through its scoped API. Substitute only the recorded guest IPv4 address for `GUEST_IP`:

```ini
[OPTIONS]
enable: 1
policy_in: DROP
policy_out: DROP
macfilter: 1
ipfilter: 1
dhcp: 0
ndp: 0
radv: 0
log_level_in: nolog
log_level_out: nolog

[IPSET ipfilter-net0]
GUEST_IP

[RULES]
IN ACCEPT -source 10.77.0.1 -dest GUEST_IP -p tcp -dport 22
IN ACCEPT -source 10.77.0.1 -dest GUEST_IP -p icmp -icmp-type echo-request
IN DROP
OUT DROP
```

PVE supplies established/related return acceptance; no guest-originated NEW allow exists. Terminal drops precede PVE's default-policy exceptions. The independent bridge guard below drops IPv6 even if a PVE implicit exception or conntrack accept would otherwise permit it. `ipfilter` alone implicitly permits a derived IPv6 link-local address, so it is not an IPv6-disable switch.

In the PVE candidate's `guest_pairs` chain, insert these four rendered rules **before** its final `counter drop`. `GUEST_PORT` is the exact vmbr1-facing port; installed `PVE/Network.pm` derives `fwpr9000p0` for legacy VM 9000 net0 (`fwpr9100p0` for clone 9100). Bind it to the recorded MAC/IP; read back the actual topology before releasing the link. These names may be matched before interfaces exist. Do not wildcard guest ports.

```nft
iifname "enp0s16" oifname "GUEST_PORT" ether saddr 08:00:27:79:e0:74 ether daddr GUEST_MAC ether type ip ip saddr 10.77.0.1 ip daddr GUEST_IP counter accept
iifname "GUEST_PORT" oifname "enp0s16" ether saddr GUEST_MAC ether daddr 08:00:27:79:e0:74 ether type ip ip saddr GUEST_IP ip daddr 10.77.0.1 counter accept
iifname "enp0s16" oifname "GUEST_PORT" ether saddr 08:00:27:79:e0:74 ether daddr { GUEST_MAC, ff:ff:ff:ff:ff:ff } ether type arp arp operation { request, reply } arp saddr ether 08:00:27:79:e0:74 arp saddr ip 10.77.0.1 arp daddr ip GUEST_IP counter accept
iifname "GUEST_PORT" oifname "enp0s16" ether saddr GUEST_MAC ether daddr { 08:00:27:79:e0:74, ff:ff:ff:ff:ff:ff } ether type arp arp operation { request, reply } arp saddr ether GUEST_MAC arp saddr ip GUEST_IP arp daddr ip 10.77.0.1 counter accept
```

This permits ARP only for the pair, checks Ethernet/ARP sender agreement and port identity, and denies guest-to-guest frames even with a spoofed controller IP/MAC. Gratuitous ARP and IPv4 address-conflict probes with sender `0.0.0.0` are denied; if image readiness requires them, review a bounded own-address exception rather than opening ARP generally. No bridge conntrack is used in this guard; stateful filtering remains with PVE, avoiding a second bridge conntrack-zone design.

Render the controller `guests4` set with exactly `{ GUEST_MAC . GUEST_IP }`. Stage the complete files and syntax-check on each target; atomically replace only the owned tables by reloading their unit. Do not use persistent one-off `nft add element` changes that disappear at reboot. Initially permit only one guest tuple/port. Remove the previous owned profile after it is stopped/reconciled before admitting the serial clone. Future software must perform these bounded updates through an explicit interface; no such runtime firewall interface is implemented today.

During this preparation, both nft variants rendered with **synthetic** MAC `02:00:00:00:90:00`, IP `10.77.0.10` and port `fwpr9000p0` passed target-side `nft --check --file -`, entirely in memory/stdin. This was a syntax/kernel validation only: no guest, interface, profile file or table was created. The PVE per-VM stanza still requires compiled/applied validation against the actual future owned resource.

Require compiled/applied per-VM chains, correct MAC/IP sets, live tap/fwbr/fwpr attachment, empty unintended NIC mappings and both guards before allowing packets. If PVE creates tap devices only at QEMU start, start only with the already-guarded NIC disconnected; inspect topology/compiled rules before releasing the link. The boundary must exist before boot, even though successful boot/connectivity is tested afterward. All remaining image, credential, journal and ownership gates still apply.

## Exact rollback for the empty-network activation

These scripts are for the frozen, guest-free window above and the inspected absent-file/table baseline. Rollback restores effective access first and leaves disabled candidate files/private evidence for inspection. It does not restore a whole ruleset or remove operator-created NIC/Netplan/bridge configuration.

Controller `/root/rehearsal-firewall-20261112/rollback.sh`:

```bash
#!/bin/bash
set -euo pipefail
test "$(hostname -s)" = rehearsal01
if systemctl cat rehearsal-test-filter.service >/dev/null 2>&1; then
    systemctl disable --now rehearsal-test-filter.service
fi
if nft list table inet rehearsal_test >/dev/null 2>&1; then
    nft delete table inet rehearsal_test
fi
```

PVE `/root/rehearsal-firewall-20261112/rollback.sh`:

```bash
#!/bin/bash
set -euo pipefail
test "$(hostname -s)" = pve01
pvesh get /cluster/resources --type vm --output-format json |
    python3 -c 'import json,sys; assert json.load(sys.stdin) == [], "guests present; retain isolation and use console"'
pvesh set /cluster/firewall/options --enable 0
for attempt in {1..15}; do
    v4=$(iptables-save)
    v6=$(ip6tables-save)
    l2=$(ebtables-save)
    if [[ "$v4$v6$l2" != *PVEFW-* ]]; then
        if systemctl cat rehearsal-test-filter.service >/dev/null 2>&1; then
            systemctl disable --now rehearsal-test-filter.service
        fi
        if nft list table bridge rehearsal_test >/dev/null 2>&1; then
            nft delete table bridge rehearsal_test
        fi
        /usr/sbin/sysctl --load /root/rehearsal-firewall-20261112/sysctl.before
        exit 0
    fi
    sleep 1
done
echo 'PVE rules did not reconcile; retain bridge guard and inspect from console' >&2
exit 1
```

Invoke the appropriate script locally via the retained management session or console if access/rule checks fail; the timers provide the same recovery if the session is lost. Read back state after any uncertain invocation. The PVE script refuses to remove isolation if guests appeared; stop/disconnect only durably proven owned guests and reconcile tasks before a revised rollback. Never blanket-stop/delete unrelated resources. Controller rollback also requires the freeze to remain in effect; never remove its filter while a later admitted guest is connected.

After successful effective rollback and comparison with snapshots, cancel any remaining timer and remove only ledger-matching files created by this change: the local `rehearsal-test-filter.service`, `/etc/rehearsal-firewall/test-filter.nft`, then the empty directory; run `systemctl daemon-reload`. On PVE, remove the created `cluster.fw` and `host.fw` only if no concurrent edits exist (compare the ledger and expected enable-to-0 change); their original state was absent. Otherwise preserve them for a reviewed merge. Retain the private change directory. Do not remove other firewall files, flush chains, stop existing firewall daemons, restore unrelated network files, or touch the inventory credential/release.

Later guest-policy rollback keeps the platform guards enabled: persist intent, keep/reapply `link_down=1` or stop the exact owned VM through the reconciled API operation, verify disconnection/stopped state and no unresolved tasks, then remove its exact pair rules/controller tuple/VM firewall profile. If ownership or outcome is uncertain, retain isolation and quarantine. Restoring an older allow policy while a guest runs is not a safe rollback.

## Later enforcement acceptance

The controller's three IPv4 input probes and management/NAT/inventory checks are recorded above. Guest-specific checks below remain pending; configuration presence and syntax checks do not pass them:

| Later check | Required evidence |
| --- | --- |
| Management preservation | Fresh dev01 SSH to both VMs, controller-to-PVE verified TLS/API access, unchanged management/NAT routes |
| Positive test path | One owned guest; controller `ping -I 10.77.0.1` and pinned SSH with `BindAddress=10.77.0.1`; relevant PVE/bridge/controller accept counters increase |
| Controller input deny | Guest NEW connections to `.1:22` and controller `.83:22` fail with input-drop counters, while fresh dev01 management SSH still works |
| Management/storage/cluster/internet deny | Bounded probes to named `.80:22/8006`, `10.20.20.80`, `10.30.30.80` and a declared reachable external reference; bridge/PVE drop evidence. Route failure alone does not prove filtering; use a deliberate bounded forced-next-hop probe if authorized |
| Layer-2 and IPv6 deny | Authorized bounded ARP/MAC/IP-spoof, tagged-frame, DHCP/RA and IPv6/link-local probes hit the intended drops; verify known positive reference and counters, not timeout alone |
| Peer deny | Two separately owned guests only after raising the concurrency gate; negative source/restore tests in both directions, including controller-address spoof attempts |
| Persistence/failure | Platform reboot persistence passed with empty allowlists; future guest-profile reboot/reload checks need separate authorization and guests stopped. Read rules back before admission. A missing/failed filter or uncertain PVE rules block boot/link release; no new guest when checks are unavailable |

Use only declared endpoints, bounded probes and sanitized counter summaries. Preserve reports on the controller outside guests; do not publish raw rules/logs/console data. No two-guest recovery isolation, nested boot, automatic startup admission hook or firewall runtime updater is implemented or verified by this preparation.
