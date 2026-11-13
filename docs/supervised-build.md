# Supervised VM 9000 build: tooling and execution record

**13 November 2026:** the [investigation handoff](investigation-2026-11-13.md)
supersedes current-state and continuation claims in the historical record below.
VM 9000 was last observed stopped/disconnected; both start task histories remain
unavailable and the second operation remains uncertain. The original failed row
denotes unavailable historical outcome, not confirmed PVE task failure. Stored
UPIDs do not independently prove HTTP response provenance. Do not repeat completed
task searches without new evidence or start any nested guest without a separate
explicit operator decision. Bootstrap expiry has passed; no renewal is implied.

## Offline request evidence, 13 November 2026

Implemented locally and tested offline, **not deployed or live-validated**. The
existing schema-version-1 event table receives new append-only records, without
migration or backfill of old operation rows:

| Event | Evidence |
| --- | --- |
| `api-request-start` | Schema version, operation UUID, local request UUID, method/path, simulated flag, UTC epoch seconds, monotonic seconds and timing-context UUID; committed before the HTTP client call |
| `api-request-end` | Same correlation fields, end UTC/monotonic time, monotonic duration, observed HTTP status (nullable), outcome, transport failure category and any returned UPID |
| `upid-attribution` | Operation, UPID, source (`mutation-response`, `task-listing`, `operator-supplied` or `unrecorded`) and request UUID when available; committed atomically with UPID attachment |
| `task-observation` | Operation/request UUIDs, UPID and redacted task status/exit status, persisted before fetching the separate task log |
| `operation-transition` | Previous/new controller status, operation UUID, supplied source and explicit result/reason, committed atomically with each new status update |

Request evidence covers mutations and their task status/log/reconciliation-list
queries. Ordinary standalone reads/preflight queries do not acquire mutation
provenance. `response`, `http-error`, `invalid-response`, `transport-error` and
`interrupted` describe the local request observation. Transport categories are
`timeout` or `http-transport`; exception text, headers, request parameters and raw
error bodies are excluded. Credential fields are omitted from structured output;
known credential strings and recognizable credential-bearing text are redacted.
A log group containing a private-key marker is suppressed as a whole, including
key-body lines. Secret-bearing mutation inputs/metadata are rejected before
journaling. Transport errors are raised outside their handlers to avoid retaining
credential-bearing exception context. These protections do not turn arbitrary
unlabelled text into a safe public export format; there is no public report exporter.

Start/end timestamps bracket the local HTTP client call, including the preceding
start-event commit; they are **not wire-send timestamps** or proof of server
acceptance. Request UUIDs are local correlation IDs, not server idempotency keys.
A new timing-context UUID is generated per API instance; monotonic durations are
measured within one request and are not reconstructed across restarts/contexts.
UTC clock correction can change chronology without changing monotonic duration.
A hard crash may leave only a start event; a response event can retain a returned
UPID even if the process dies before attaching it to the operation. Reconciliation
recovers that exact response UPID first and preserves `mutation-response`
provenance. Pending leases still block work until they expire; restart does not
steal a lease. A start-only record, absent legacy request evidence or conflicting
request records requires explicit operator evidence and never permits resubmission.

Without a retained response UPID, task discovery requires matching start/end
request records in one timing context. Candidates must fit the bounded UTC call
interval (two-second tolerance), actor, VMID and expected task type. Backwards UTC
intervals block discovery. UTC correlation assumes controller/PVE clocks within
that tolerance; alignment is not established by the offline tests. UPID node,
target, actor and known operation type are checked before polling; a discovered
task's listing timestamp must agree with its encoded UPID timestamp. Operator or
legacy supplied UPIDs retain their recorded source, never an inferred response
source. The HTTP client refuses absolute/escaping paths and streams at most 2 MiB
of response data, preserving received HTTP status if the body transfer fails.

HTTP errors, malformed responses, transport failures, unavailable task histories
and missing exit statuses leave mutation outcomes uncertain. A stopped resource
does not resolve a historical start. An observed nonempty failing task exit status
is persisted as a confirmed failure before log retrieval; losing that log cannot
erase the failure. An observed `OK` task with unavailable log retains its task
observation while operation completion remains unverified. Completion still
requires task evidence and the intended postcondition. Ownership, cleanup, lease
and no-retry rules are unchanged. Existing terminal rows are never reinterpreted
or silently corrected; the handoff explicitly explains the historical failed row.
Existing version-1 journals are checked for expected columns and one installation
UUID before initialization writes. Incompatible/missing schema or identity is
reported without repair or replacement. Compatibility checks use synthetic copies.

Offline `status` now includes `task_outcome` and `upid_sources` alongside the
unchanged controller status. A legacy `failed` row without recorded task proof has
`task_outcome=unknown`, rather than a fabricated confirmed PVE failure. New operator
terminal results require a nonempty result/reason object; their transition is
labelled `operator-supplied`. Existing terminal records remain immutable. Review
changes are recorded in [CHANGELOG.md](../CHANGELOG.md); none is deployed or
validated through a live nested start.

## Historical execution record, 12 November 2026

Updated **2026-11-12, after operator recovery and renewed instability**. VM 9000 and its two recorded volumes remain retained. The operator restarted PVE with one vCPU and 16 GB reported RAM. Read-only reconciliation established the existing guest stopped/unlocked/disconnected under a new boot ID and resolved the old operation's current effect, while preserving its unavailable historical result. **One separately journaled, conditionally authorized new start again lost PVE SSH/API responsiveness.** Current guest status and shutdown are **unverified**; the new operation is `NEEDS_RECONCILIATION`. Link release, guest SSH/trust/agent/packet tests and uncertain deletion never occurred. The build attempt was halted as requested. No physical-host access or reboot was performed by the agent.

The user authorized one supervised build and test, ending with the owned guest stopped. Identity cleaning, template conversion, clone 9100 and application/recovery work remain outside this operation. The broader [template plan](nested-guest.md) includes those later stages; do not execute them under the current authorization.

## Operator restart and supervised recovery attempt

**Operator-supplied finding:** pve01 was restarted after changing its VirtualBox allocation from two to **one vCPU**, and from 12 to **16 GB RAM**. The operator has seen similar hangs in other VirtualBox VMs with multiple vCPUs and not in single-vCPU VMs. This is an **observed pattern and provisional workaround, not a confirmed root cause**. Whether the shutdown was graceful or forced is not established. Subsequent guest-visible readings corroborated one CPU and increased RAM; no host-side command or allocation change was made from dev01.

**Read-only reconciliation, 20:04–20:12 UTC:** PVE returned with boot ID **`3256e72c-f8a3-4b92-adb4-746acd8b6605`**, different from `d2abd677-b98c-499c-ba7d-516da7beaf38`. VM 9000 was **stopped**, unlocked, onboot 0, sole NIC firewall 1/link_down 1. Installation/run/resource/nonce/node/pool and exactly the two recorded volumes matched the existing journal; root LV remained 12 GiB and cloud-init 4 MiB. No active PVE task or HA resource existed. No create/import/resize, lock clearing, deletion, credential rotation or API grant occurred.

The original start UPID's status returned **`no such task`**; its log/archive file was absent, as was the original worker PID. Its historical result remains unavailable and is not labeled successful or never executed. The changed boot boundary, absent original worker, empty active-task/HA lists and freshly verified stopped/unlocked owned resource prove the old request cannot still execute. The journal preserved that UPID and archived the original operation as **failed/unverifiable**, backed up state, recorded the manual external-restart reconciliation and observed resource state `stopped`. Missing task metadata alone would not authorize this resolution or another start.

Fresh strict-key dev01 SSH/passwordless sudo, original controller verified-TLS live inventory (exit 0, complete, four queried sections, one stopped VM), DNS/NAT HTTPS and unchanged management/default routes passed. The report `firewall-20261112T141215Z-after-operator-restart-200153Z.json` has SHA-256 **`0aafaa10382323acf1566e49467ea64cc2874c6476f7fc57a97a6d4203bedb84`**. The separate bootstrap credential also passed real API reads and was still valid; original inventory credentials/ACLs/release were reused unchanged.

Legacy enabled/running state, actual IPv4/IPv6 hooks, IP routing forwarding 0/0, sole forwarding enp0s16 port, IP-less vmbr1 and disabled host IPv6 persisted. The PVE native guard file/effective nine rules, enabled persistence service and exact guest policy/IP set survived the operator restart. Current compilation/readback passed. Controller filter/tuple remained intact. This verifies PVE profile persistence/readback across this incident restart, **not guest packet enforcement**. The controller has not been rebooted since adding its guest tuple.

| Revised budget / pre-attempt observation | Value / boundary |
| --- | --- |
| PVE CPUs | **1**; guest's 1 vCPU shares that CPU with PVE, with no dedicated CPU headroom or availability guarantee |
| PVE memory | Operator reports **16 GB**; Linux MemTotal **16,769,753,088 bytes** (about 15.62 GiB) |
| PVE reserve / build guest | At least **4 GiB** for PVE/overhead; guest stays **2 GiB**, balloon 0 |
| Available memory before start | About **15,117,201,408 bytes** (14.08 GiB); ample before start, no claim about physical-host pressure or post-hang memory |
| Storage | Healthy **90 GiB** pool; **1.94% data / 1.65% metadata**, no reported LVM health fault; root free **9,172,987,904 bytes** |
| Logical commitment/reserve | Existing 12 GiB root plus full 2 GiB auxiliary allowance and 18 GiB pool reserve; no new disk commitment/import |
| Host-space evidence | Latest supplied post-import reading remains **633G** at the earlier operation; no fresh physical-host byte reading is inferred here |
| Concurrency | **One operation and one running guest**; no second guest/source/restore admission from increased RAM |

Kernel logs reported a corrupted or uncleanly shut down journal. This does not establish shutdown method, guest filesystem integrity or the hang's cause. Other hypervisor/clock/graphics/discard warnings were retained privately; no repair, graphics change or trim-based admission assumption was introduced.

After all preceding conditions passed, a bounded serial collector and read-only HTTPS responsiveness monitor were prepared, and fresh stopped/disconnected isolation was attested. A distinct start request was journaled once at **20:16:36 UTC**:

```text
UPID:pve01:00001794:0001C753:6AF61EA4:qmstart:9000:rehearsal-build@pve!bootstrap-9000:
```

Its operation UUID is **`a9cf5dc8-7654-40c0-99c0-a0ba6e589a88`**. The monitor recorded **19 successful node-status reads**, maximum about **0.01023 seconds**, with the last success at 20:16:35 UTC. At **20:16:43 UTC** it recorded an API timeout after about 3 seconds. Start-task polling also timed out. Three bounded read-only SSH checks then failed: connection timeout followed by two `No route to host` results. **No further start or link-release request was issued.** The attempt was halted on renewed instability; actual KVM/Ubuntu execution and QMP/guest-port proof never completed.

The one-vCPU setting was actually observed before this attempt. The renewed loss therefore **does not validate that workaround for this workload**; it still does not identify a root cause. Increasing RAM, changing CPU count and restarting together are not an isolated causal experiment. No software-emulation or network fallback was attempted.

At **20:22 UTC**, controller fresh SSH/sudo, unchanged addresses/default routes/forwarding/filter and original inventory config/CA/token metadata/release passed; controller DNS/NAT HTTPS still passed. Post-attempt original live inventory returned **exit 3**, `backend=live`, `simulated=false`, sanitized error **`timeout`**. PVE current enforcement and guest status/stop cannot be verified while management is inaccessible. The sole NIC was last verified disconnected; it was never released.

Controller protected evidence now includes **`reconciliation-after-operator-restart.json`**, **`journal-before-restart-reconciliation.sqlite3`**, **`recovery-responsiveness.jsonl`**, its alert, **`recovery-failure-probes.json`**, **`recovery-handoff-20261112T200153Z.json`**, failed inventory evidence and **`journal-after-recovery-uncertainty.sqlite3`**. The final **`recovery-final-status-20261112T200153Z.json`** and **`journal-recovery-final.sqlite3`** retain the post-checkpoint state: **36 completed / one failed-unverifiable historical operation / one uncertain new start**, resource retained and stop unverified. The prior handoff/current-status snapshots are preserved, and `current-build-status.json` now reflects this final checkpoint. Root preflight, compile and bounded console evidence are under **`/root/rehearsal-reconcile-20261112T200153Z`** on PVE; console progress remains unreadable. Existing controller config/state/tool/release/credential locations are unchanged.

**Current action is stop and retain, not another build attempt.** The old operation's historical result remains unavailable but its current effect was resolved before this distinct attempt. The **new** start is uncertain, current resource retained and stop unverified; cleanup cannot run against an inaccessible/uncertain resource. Operator console observation/restored management is required to reconcile this exact new task and perform a safe owned stop. Do not clear locks, repeat create/import/start, infer stopped state from host loss, or delete by VMID/prefix/expiry. No reboot/power operation was issued by the agent. Both guest-guard rollback timers had already been canceled after their earlier successful checks; no firewall change or new rollback timer occurred during this resumption.

## Resumed admission, resources and unresolved start

This section is the **earlier 15:45–16:20 UTC incident**. Its original unresolved start was later reconciled as described above; the newer 20:16 start is the current uncertainty.

**Fresh user-supplied host evidence:** at **2026-11-12 15:45:15 UTC**, ubase `/mnt/ssd`, ext4 on `/dev/sdc1`, reported **916G total, 282G used, 635G available, 31%**. A subsequent operator VBoxManage inspection confirmed PVE running and both attached paths unchanged:

```text
/mnt/ssd/VirtualBox VMs/Proxmox/Proxmox-training/pve01/pve01.vdi
/mnt/ssd/VirtualBox VMs/Proxmox/Proxmox-training/pve01/pve01_1.vdi
```

These are supplied facts, not host inspection by dev01. For the rounded `G` values, admission conservatively charged a 917 GiB upper bound for total capacity and only 634 decimal GB available. This passes the full 14 GiB growth charge plus max(10 GiB, 20%) host reserve. Fresh PVE reads confirmed healthy unused 90 GiB pool, metadata 1.61%, 9,192,034,304 root bytes free, 10,002,792,448 available RAM bytes, no active tasks/guests and unused 9000. The existing journal had 18 completed metadata operations, no pending writes/reservation; the existing token passed verified-TLS reads and remained unexpired. No pool, role, ACL, token or key was recreated.

The operator subsequently supplied a **post-import** `df -hT` reading: **916G total, 283G used, 633G available, 31%**, same filesystem/device. Its command timestamp was not supplied; it was recorded on the controller at approximately 16:13 UTC. Original units are retained. It remains comfortably above the reserve; no exact byte precision is inferred from rounded values.

| Durable resource field | Actual value |
| --- | --- |
| VM / node / pool | **9000**, `rehearsal-noble-build`, pve01, rehearsal |
| Run UUID | `157c73f9-3f9d-4c38-9ddb-b5c7fb9fe170` |
| Resource UUID | `048c39b1-a339-4891-8230-b6717068c99e` |
| Ownership nonce | `95117fed-1ac6-451d-9f7d-11c75c5078b6` |
| Resource expiry | **2026-11-12 21:48:10 UTC**; expiry does not authorize cleanup with an unresolved task |
| Root volume | **`rehearsal-lvm:vm-9000-disk-0`**, raw thin LV, actual block size **12,884,901,888 bytes (12 GiB)**, scsi0/discard=on |
| Cloud-init volume | **`rehearsal-lvm:vm-9000-cloudinit`**, ide2/NoCloud |
| Hardware / startup | 1 socket/core, CPU host, 2048 MiB, balloon 0, kvm 1, SeaBIOS, serial socket, onboot 0, boot scsi0 |
| Sole NIC, last readback | VirtIO `02:52:40:61:0e:f4`, vmbr1, firewall 1, **link_down 1**; no other NIC |

| Operation | Captured UPID / result |
| --- | --- |
| Create | `UPID:pve01:00005AF3:000831EC:6AF5DFD1:qmcreate:9000:rehearsal-build@pve!bootstrap-9000:` — **OK**, stopped/disconnected readback |
| Single privileged import | `UPID:pve01:00005C72:00084F26:6AF5E01C:qmconfig:9000:root@pam:` — **OK**, exact volume readback |
| Resize | `UPID:pve01:00005E02:00086982:6AF5E060:resize:9000:rehearsal-build@pve!bootstrap-9000:` — **OK**, API and block-device size checked |
| First start, **16:08:44 UTC** | **`UPID:pve01:00007245:000A305E:6AF5E4EC:qmstart:9000:rehearsal-build@pve!bootstrap-9000:`** — **outcome unknown**, no retry |

The local pvesh import emitted non-JSON CLI output. Its unique root-actor qmconfig task and exact owned configuration were inspected and reconciled to success without repeating import. Live task listing also showed separate `user`/`tokenid` fields; reconciliation now supports that exact actor representation, covered offline. The accepted firewall ICMP rule initially failed an ordering assertion because installed PVE `create_rule` unconditionally prepends. Readback reconciled that write; two bounded digest-protected moves established the exact four-rule order. No duplicate allow rule or access widening was used.

The generated NoCloud data contains the dedicated user/key, fixed test address and no gateway/password. Read-only inspection of the stopped owned root LV confirmed signed-image defaults: `disable_root: true`, locked default-user password, passwordless sudo, and `60-cloudimg-settings.conf` with **`PasswordAuthentication no`**. These defaults are inherited rather than repeated in generated user-data. Temporary read-only loop mappings were detached in finally blocks; no guest filesystem or identity was edited.

**Before the start**, VM firewall options/IP set and exact ordered rules passed authenticated readback: controller-only SSH/echo requests, terminal IN/OUT DROP, MAC/IP filtering, DHCP/ND/RA disabled. Controller guest set contains exactly the recorded MAC/IP tuple; bridge guest_pairs contains the four exact port/MAC/IP/ARP pair rules before terminal drop. Neither routing forwarding nor management policy changed.

| Guard update | Persistent SHA-256 | Timer outcome |
| --- | --- | --- |
| Controller | `f9a207a1958a8ac073893aafbc3f45483b630a010c0309464122d204d801f1dd` | Eight-minute rollback armed/verified before changes; canceled **16:04:41 UTC** after checks, never ran |
| PVE bridge | `5d1206cb16128a77fac110ef7b92f8d8f1a60f1474b5c2a01e017d9e9fe46945` | Eight-minute rollback armed/verified before changes; canceled **16:04:45 UTC** after checks, never ran |

Both changes were applied one machine at a time, backing up only owned files under `/root/rehearsal-guest9000-20261112T154515Z`. Rollback restores the empty, closed guest allowlist; it does not disable platform enforcement. Fresh SSH/sudo, unchanged network/forwarding, DNS/NAT HTTPS and original verified-TLS inventory passed after each change, seeing one stopped VM. The runtime reports are `firewall-20261112T141215Z-guest9000-guard-{rehearsal01,pve01}.json`, both SHA-256 `b3c5bcc3bc3ac3a30038a062478144bdbb59de38b133bfbfe457096796ad5d62`. Persistent units were preserved.

Pre-boot compilation passed without warnings/errors. PVE's command uses `/usr/bin/kvm` with kvm 1; a verifier that expected a literal accelerator argument was corrected before issuing any start. Actual QMP `query-kvm`, live guest-port topology and IPv4/IPv6 chain checks were reserved for the running/disconnected stage. **That stage was not reached or attested.** Compilation/configuration alone does not establish KVM execution, Ubuntu readiness or guest enforcement.

The start returned its UPID, then task polling hit a transport timeout. Subsequent strict-key SSH failed during banner exchange; **10 read-only attempts over a bounded 150-second reconnect window** did not recover access. Controller-originated ping received one of two replies; an API version read timed out. No reboot, power operation, network change, emulation fallback, second start or shutdown was issued to guess the result. Original live inventory afterward returned **exit 3**, sanitized error **`timeout`**, no fixture fallback. This is a failed post-start access check, not proof that the token or VM task failed.

At **16:13 UTC** controller fresh SSH/sudo, unchanged addresses/defaults, forwarding 0/0, effective filter, DNS/NAT HTTPS and original inventory config/CA/token metadata/release still passed. PVE's current enforcement, guest status, actual boot and stop are unreadable until it returns. The latest verified PVE guard state is the successful pre-start readback, and both guard timers were already canceled before the access loss. The root serial collector is bounded; its progress/transcript cannot currently be retrieved. **No SSH host trust, actual Ubuntu/cloud-init/filesystem growth, agent or guest packet result is claimed.**

Protected controller evidence includes `operator-host-capacity-20261112T154515Z.json`, `operator-post-import-host-capacity.json`, created/imported configuration, `guest-policy-and-cloudinit.json`, sanitized `inventory-after-start.*`, **`start-unreconciled-handoff.json`** and a consistent **`journal-after-start-uncertainty.sqlite3`** snapshot under the existing supervised state directory. **`current-build-status.json`**, recorded at **16:20 UTC**, confirms **35 operations complete / one uncertain**, both recorded volume identities and unchanged credential expiry. Resource state is retained, start uncertain with its original UPID, and cleanup blocked. Evidence was retained outside the guest; no uncertain resource was deleted.

**Resume only after an operator console observation or restored PVE access.** Reconcile that exact start UPID and live ownership/current status, preserving all resources/credentials. Never repeat start to discover its outcome. If running, verify KVM and the still-disconnected sole NIC/guards before any further action; on a confirmed build failure, stop and reconcile only the owned guest, then apply the documented exact-volume cleanup decision. If status, task, lock, ownership or volumes remain uncertain, retain quarantine. No second platform reboot is authorized by this build.

## Completed persistence checks

Both machines were reinspected, with no active work, guests, PVE tasks or Rehearsal rollback timers. Each received **one reboot**, controller first, with strict existing-host-key verification, fresh connections, a five-minute return deadline and approximately ten-second reconnect cadence. Neither required repair or another reboot.

| Machine | Before boot ID | After boot ID | Result |
| --- | --- | --- | --- |
| rehearsal01 | `4fa3d78f-3a92-4e6e-a5bb-bf88e699a03d` | `ce105dd6-07dc-46c6-a237-1f61c90f882e` | Passed, 14:16 UTC |
| pve01 | `5bd69c40-7d4a-45ab-9971-91c3a4c2db1f` | `d2abd677-b98c-499c-ba7d-516da7beaf38` | Passed, final comparison 14:20 UTC |

After each restart: fresh dev01 SSH/passwordless sudo, unchanged addresses/default routes, IPv4/IPv6 routing forwarding 0/0, synchronized time, DNS and NAT-interface HTTPS (`archive.ubuntu.com`, HTTP 200/TLS verification 0), enabled/active custom filter service and identical persistent rule bytes passed. PVE retained legacy `enabled/running`, actual IPv4/IPv6 FORWARD hooks, bridge netfilter switches 1/1, IP-less vmbr1/enp0s16, sole forwarding bridge port and host IPv6 disabled on both test devices. Controller input/forward filtering and its empty guest set persisted.

PVE's pmxcfs regenerated only the inode numbers of `cluster.fw` and `host.fw`; contents, modes, owner/group and modification times matched. The first overly strict comparison was retained, then the comparison excluded **only these FUSE inode fields**. It still rejected changed rule hashes or routing. This was a verifier correction, with no firewall repair.

Controller release 0.2.0, wheel digest, symlink, configuration/CA, original inventory credential metadata and retained report hashes matched before/after. Runtime version, dependency/config checks and explicitly enabled verified-TLS inventory passed after both reboots: exit 0, real complete results, all four sections queried, active rehearsal-lvm, six audit-visible interfaces, zero VMs. No latest-report pointer was replaced.

Private pre/post snapshots and comparisons: `/root/rehearsal-reboot-20261112T141215Z` on each machine, directory 0700/files 0600. Runtime-owned inventory reports: `/var/lib/rehearsal/reports/firewall-20261112T141215Z-{pre,post}-reboot-{rehearsal01,pve01}.json`, with metadata/stderr companions. Only the four applicable phase/machine combinations exist.

At **15:02 UTC**, three bounded SYN frames arriving on controller enp0s9, individually addressed to `10.77.0.1:22`, controller management `.83:22` and controller NAT `10.0.2.15:22`, again increased input drops **0 → 3 packets / 120 IP bytes**, with accept counters zero. The source was PVE's physical test MAC and existing management IP. This proves the controller's tested IPv4 interface-input paths after reboot; it does not prove a nested-MAC path or guest isolation. Probe evidence remains in the controller's private reboot directory. Rollback timers are inactive; none was newly armed or canceled by these reboot checks.

## Separate minimal tool

`src/rehearsal_build/` provides `python -m rehearsal_build`. It is separate from the read-only `rehearsal` inventory command and its TOML schema. Python 3.12, existing HTTPX and standard-library SQLite are sufficient; **no dependency, system package, daemon, scheduler or executor was added**.

The protected SQLite journal uses FULL synchronization, WAL, foreign keys and an exclusive process lock. It records installation/run/resource UUIDs, a random ownership nonce, six-hour resource expiry, bounded leases, configuration digest, exact volume identities and immutable terminal operation evidence. Intent commits before any mutation. Pending or uncertain operations block subsequent writes; mutating requests are never retried. Returned UPIDs are retained, polled to terminal status and checked with resource postconditions. Lost responses are reconciled using matching task actor/type/VMID/time and live state; zero or multiple candidate tasks require operator review.

Cleanup requires matching durable and live installation/run/resource/nonce, exact VMID/node/pool, a stopped non-template VM, resolved tasks/locks/leases and an exact volume ledger. A successful destroy task also requires absence of the configuration and recorded volumes. No prefix/range/TTL ownership inference, orphan-volume sweep, lock clearing or automatic expiry cleanup exists. An ambiguous partial resource stays quarantined. Shared pool, roles, bridge, images and inventory installation are protected platform inputs.

VM creation requires fresh PVE capacity evidence (at most 15 minutes old) and a separately supplied operator host reading (at most one hour old). Forecast: full 14 GiB increment, pool reserve max(6 GiB, 20%), host reserve max(10 GiB, 20%), metadata below 75%, at least 6 GiB PVE root free including staging allowance, and at least 6 GiB available RAM including 4 GiB PVE reserve. Unknown health, active work or occupied VMID blocks admission. These are explicit supervisor observations, not an automatic physical-host monitor. Recheck before import and later allocations; no sparse-image-size shortcut is accepted.

Before start the tool requires fresh operator evidence for stopped/disconnected state, guest policy, bridge/controller guards and KVM. After start, link release separately requires observed kernel guest chains and the exact guest bridge port/controller tuple. These attestations are supervisor checks, not an installed startup hook. Never start the VM outside this supervised procedure.

The default offline suite blocks sockets/DNS and uses fake credentials/mock transports: **219 tests passed**, plus Ruff check/format. It exercises durable lost-response recovery, task failure/timeouts, uncertain task provenance, scope/KVM/NIC checks, capacity reserves/staleness and ownership/lease/volume cleanup protections. Live exercise selection requires **all three**: `--live`, `--exercise first-guest`, `REHEARSAL_LIVE=1`, before reading credentials. `validate` and `status` stay offline.

## Deployment and protected inputs

The current immutable sidecar is **`/opt/rehearsal/supervised-tools/e95e1c7cb30b8f40`**, containing `rehearsal_build/` and a deployment manifest. Source SHA-256: `e95e1c7cb30b8f406949a4f165e58b3e16e6c24f21e25972f3fea3d41b6594ba`. Directories are root:rehearsal 0750; source/manifest files 0640. Explicit `PYTHONPATH` uses the existing `/opt/rehearsal/current/venv/bin/python`, without switching or modifying inventory. Earlier sidecar revisions are retained for provenance; there is no service or activation symlink for this tool.

| Item | Location / state |
| --- | --- |
| Validated build config | `/etc/rehearsal/first-guest.toml`, root:rehearsal 0640; fake public example in `examples/first-guest.toml` |
| Separate credential | `/etc/rehearsal/bootstrap-9000.json`, rehearsal-owned **0400**, never displayed |
| Durable state/requests/evidence | `/var/lib/rehearsal/supervised/first-guest-20261112T141215Z`, rehearsal-owned 0700, files 0600 |
| Installation UUID | `cc8e4939-1846-4891-8a99-7f746db4d31e` |
| Image, manifest/signature, keyring, package evidence | `/var/lib/rehearsal/inputs/noble-20261017-20261112T141215Z`, rehearsal-owned 0700/files 0600 |
| PVE verified image copy | `/dev/shm/rehearsal-firstguest-20261112T141215Z/ubuntu-24.04-server-cloudimg-amd64.img`, root-owned 0600, volatile RAM staging; no VM disk allocated |
| Dedicated build SSH key | `/var/lib/rehearsal/keys/first-guest-20261112T141215Z/id_ed25519`, generated on controller as rehearsal, 0600; directory 0700 |
| Planned mapping | VM 9000, pve01/rehearsal-lvm, pool rehearsal, vmbr1, `10.77.0.10/24`, MAC `02:52:40:61:0e:f4`, 1 vCPU/2048 MiB/12 GiB |

The reservation/run/nonce now exist as recorded above. No guest `known_hosts` file exists; console-derived host trust has not been established. The dedicated key remains protected access material, not proof of guest identity. Its public fingerprint is `SHA256:OQtVAbTy1pyAqosZ4ifVv4FokT4W5s8cYWRv8PMpqvw`. No developer private key or agent forwarding is used.

Inventory command/release, `/etc/rehearsal/live.toml`, its CA and `/etc/rehearsal/api-token.json` remain unchanged and usable. A fresh live inventory at **15:32 UTC** again passed with zero VMs. Its protected report is `firewall-20261112T141215Z-bootstrap-inventory-preserved.json`, SHA-256 `b0d2a157c8ab6d8af4403d72ffc988b6ff9257550ce7a226b7c2a62a2b236041`.

## Verified image and agent bundle

At **14:23 UTC**, verified HTTPS acquisition, `gpgv` signature validation against the Ubuntu-distributed cloud-image keyring and manifest/image digest comparison passed for the pinned Canonical noble **20261017** build. Expected signer: `D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`, checked against [Canonical's verification procedure](https://ubuntu.com/docs/public-images/public-images-how-to/verify-image-checksum/). No moving image URL was substituted.

| Artifact | Verified value |
| --- | --- |
| Image bytes | 621,284,352 |
| Image SHA-256 | `04e8f2461a16a44e78a370284471f29616cdd9baf1893df25807b71f985b6c94` |
| Manifest SHA-256 | `78d7da6ab1556daa6c0f685bf4e0e3da36395f170e8fad411d7ba032f14d08c2` |
| Actual image format/virtual size | qcow2, **3,758,096,384 bytes (3.5 GiB)**, no backing/external data file |
| PVE format/integrity check, 14:46 UTC | Rehashed transferred bytes; `qemu-img info/check` passed, corruption false, check errors 0 |
| Offline `liburing2` | `2.5-1build1`, 21,092 bytes, SHA-256 `c2aef62accee92a06263c3ad4ef46132c13e409b54296c44792a20491830a7b0` |
| Offline `qemu-guest-agent` | `1:8.2.2+ds-0ubuntu1.18`, 391,458 bytes, SHA-256 `62abf54bf34fed34dc65cbd973b4b6b6f4685fef30fbaa3fb3e8865e957fda75` |

At **14:40 UTC**, isolated APT used signed official noble/noble-updates/noble-security metadata and the exact image manifest as package status. Both package SHA-256 values match authenticated indexes. A download-disabled dependency-resolution test succeeded with network proxies pointed to an unavailable local address. Bundle, index hashes and resolution logs are protected under the input directory's `agent-bundle/`. No controller/PVE system package was installed. Guest installation and agent readiness remain untested.

## Pool, identity and exact privileges created

Created shared platform pool **`rehearsal`** (empty), PVE-realm owner **`rehearsal-build@pve`** with no password, and privilege-separated token **`rehearsal-build@pve!bootstrap-9000`**. Both expire **2026-11-13 15:08:20 UTC** (`1794582500`). No automatic renewal or rotation is configured.

The following five new roles are bound to **both owner and token**, propagation **off**, on only the listed paths:

| Role / path | Privileges |
| --- | --- |
| `RehearsalBuild9000` / `/vms/9000` | `VM.Audit VM.Allocate VM.Config.CPU VM.Config.Memory VM.Config.Disk VM.Config.CDROM VM.Config.HWType VM.Config.Options VM.Config.Cloudinit VM.Config.Network VM.PowerMgmt VM.GuestAgent.Audit` |
| `RehearsalBuildNode` / `/nodes/pve01` | `Sys.Audit` |
| `RehearsalBuildStorage` / `/storage/rehearsal-lvm` | `Datastore.Audit Datastore.AllocateSpace` |
| `RehearsalBuildBridge` / `/sdn/zones/localnetwork/vmbr1` | `SDN.Audit SDN.Use` |
| `RehearsalBuildPoolAudit` / `/pool/rehearsal` | `Pool.Audit` |

Installed PVE source filters pool identity out of cluster-resource results without `Pool.Audit`; this additional read-only exact-pool scope is necessary for positive ownership verification. No Pool.Allocate, VM.Clone, VM 9100 rights, VM.Console, Administrator, Sys.Modify, datastore-wide deletion or guest-agent exec/file privilege was granted. Authenticated serial-console collection will use the existing one-time privileged operator path. VM.Allocate itself permits template conversion server-side; current tooling forbids that endpoint, and current authorization excludes it. Do not claim an API-enforced distinction absent from PVE's privilege model.

Every original pool/role/user/token/ACL change was journaled before mutation; its **18 bootstrap metadata operations are complete**. The later first-start operation is uncertain as recorded above. Token creation initially had an uncertain SSH handoff. Readback proved the new token existed and the destination was absent. Creation was not repeated: the operator recovered only that same newly created server value through authenticated root access, piped directly into the protected controller file, then reconciled the original operation. No token was regenerated, rotated or printed. Root evidence is `/root/rehearsal-firstguest-20261112T141215Z/{bootstrap-plan,bootstrap-verified}.json`; no secret is in those files.

At **15:32 UTC**, the recovered credential independently passed real HTTPS node/storage/network/pool/task reads with verified TLS. Self-permission checks confirmed exact scopes and **empty rights on VM 9100, local storage and vmbr0**. Original inventory owner/token ACLs and token metadata were independently compared unchanged.

## Continue this same operation

**Superseded instructions:** the following describes the 12 November recovery
gate, not a pending task-search request. The [13 November handoff](investigation-2026-11-13.md)
records the subsequently completed lookups and last stopped observation. Do not
repeat historical lookups without new evidence, renew expired credentials or
perform new mutations under this earlier continuation wording.

**The build attempt is halted on renewed instability.** Further authorized work is read-only recovery visibility, reconciliation of the **new** operation and a safe owned stop when possible. Do not release the NIC, run guest tests or make another start attempt under an assumption that the provisional workaround is sufficient. No new create/import/reservation/token/key/role or journal is needed.

Current operation **`a9cf5dc8-7654-40c0-99c0-a0ba6e589a88`**, UPID **`UPID:pve01:00001794:0001C753:6AF61EA4:qmstart:9000:rehearsal-build@pve!bootstrap-9000:`**, must be read back with actual VM state, ownership/nonce/node/pool, exact volume ledger, task/lock status and last disconnected sole NIC/onboot settings. The earlier original operation is already archived with an unavailable historical result and a verified stopped current effect before this new attempt; do not overwrite that evidence or confuse the two UPIDs.

Offline `status` can inspect the existing journal while PVE is unavailable. Once access returns, use explicit `read` operations for this new task's status/log and current resource. Preserve both immutable source/deployment manifests and protected config/state. Reconcile known task evidence rather than repeating a mutation. A process appearing to run does not settle a missing result. If another operator restart has occurred, missing task metadata alone is insufficient: preserve historical uncertainty and prove the current effect/process boundary, ownership, stopped/running state, locks/tasks and exact volumes before deciding what is safe.

If the guest is running and the current task is terminal/reconciled, perform only the authorized owned shutdown with its own durable intent/UPID and observed stop. Reconcile a lost shutdown response before any further action. If access, task, ownership, lock or volume state remains uncertain, retain quarantine. Do not clear locks, guess orphan ownership, delete by prefix/range/expiry, power-cycle the host or add emulation/network/privilege fallbacks. No agent reboot or further build start is authorized by this recovery record.

All live exercise steps continue to require `--live --exercise first-guest` and `REHEARSAL_LIVE=1` before credential access. Existing supported operations remain `reserve`, `request`, `operator-intent`, `operator-result`, `read`, `reconcile`, `attest`, `record-volumes`, `mark-stopped`. Reservation/create/import have already succeeded and must not be repeated. Protected JSON requests contain references/public parameters, never command-line secrets. New evidence/checkpoints retain prior snapshots. Any later supervised build attempt requires explicit direction after investigating the renewed instability.

## Remaining acceptance and promotion gates

Creation/import/resize and guest profile/allow tuples are complete; the newer start task is uncertain after renewed instability and guest status/shutdown are unverified. Pending after PVE recovery and task reconciliation: actual KVM boot; generated/effective cloud-init and SSH policy; authenticated host-key trust; 12 GiB guest filesystem and at least 4 GiB free; controller-to-guest SSH/ping; installed agent; counter-backed management/storage/cluster/internet/spoof/ARP/tag/DHCP/RA/IPv6 negative checks; owned shutdown and post-allocation host/pool measurements. Guest-specific rule persistence is not established by the empty-allowlist platform reboot tests.

Template promotion additionally requires separate authorization for identity cleaning, stopped conversion, distinct-key full clone 9100, new machine/boot/host identities, rejection of the build key, clone cleanup, template protection and removal of temporary template write/allocation rights. Two-guest peer isolation remains a later gate before concurrent recovery work.
