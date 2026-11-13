# Phased implementation plan

**13 November 2026 development update:** [the supplied investigation handoff](investigation-2026-11-13.md)
supersedes the 12 November infrastructure summary below. Offline work implements
request timing/HTTP/transport/UPID-provenance evidence and preserves task results
when log retrieval fails. These changes are not deployed. Live nested validation
is blocked by unresolved host faults and requires a separate explicit operator
decision; historical searches are complete and retained resources/state remain
protected.

Status: **inventory deployed; supervised build halted on renewed instability**, 2026-11-12. Inventory 0.2.0 and separate offline-tested journal/reconciliation tooling remain unchanged. VM 9000 creation/import/resize and stopped-guest isolation are verified. An operator restart with one vCPU/16 GB allowed read-only reconciliation of the old attempt's stopped current effect. **One distinct conditional start again lost PVE responsiveness; the new start and guest status/stop are uncertain.** Guest checks/cleanup remain unverified; no link release or uncertain deletion occurred. The next action is recovery visibility, exact new-task reconciliation and owned stop, not another start. See [current evidence and revised budgets](supervised-build.md#operator-restart-and-supervised-recovery-attempt).

Follow [architecture.md](architecture.md) for lifecycle, ownership, recovery and trust rules. Keep the controller on separate runtime VM(s); do not turn `dev01` into the deployed service.

The [first guest/template plan](nested-guest.md) now has current authorization for only VM 9000 build/test/stop. Dedicated networking, selected legacy firewall/bridge guard and controller filtering passed platform reboot persistence and fresh management/API checks. Exact guest policy/packet tests remain gates, with empty allowlists. Pool/temporary bootstrap privileges were added separately; inventory credentials/ACLs remain unchanged. Identity cleaning, template conversion and clone 9100 require later authorization.

## Milestone 1 — Local scaffold and read-only inventory

**Goal:** a useful, installable Python CLI with offline validation and a read-only Proxmox adapter, entirely testable without the lab.

Completed inventory subset: package/CLI, offline validation, explicit fixture/live selection, credential references and protected runtime loading, verified HTTPS context, allowlisted GET normalization, transient retries/deadlines, explicit partial coverage, safe errors and network-blocked transport tests. HTTPX remains the single direct runtime dependency. Minimal SQLite primitives were subsequently added in the separate supervised-build package; the deployed inventory remains read-only.

Work:

- Create `pyproject.toml`, a `src/rehearsal/` package, a test layout and a non-secret TOML example. Add ignore rules before creating `.venv`, local credentials, state or test artifacts.
- Use Python 3.12 and an isolated venv. `python3.12-venv` is installed; test its bootstrap rather than assuming pip is usable. Add only the packaging/test dependencies needed, with documented hashed locks and reproducible commands. No system-wide Python package changes are required.
- Implement structural configuration validation, credential references, TLS policy and explicit live opt-in. Offline validation must not resolve DNS, read real credentials or contact endpoints.
- Implement injectable HTTPX/provider interfaces and read-only inventory of version, allowed node status, visible storage capacity/content types and VM/template/network metadata. Treat partial visibility and missing permissions explicitly; inventory is not a declaration of provisioning readiness.
- Introduce run/operation/resource data models and the first SQLite schema, UUID installation/run identities and redacted structured output. Keep mutation methods unavailable to the inventory command.
- Test sanitized API fixtures, bounded retry/deadline logic and error classification; make default tests reject socket use. Document planned CLI names as implemented only when they actually exist.

Acceptance criteria:

- A fresh venv can install the package and run the documented offline test and lint commands; a fixture inventory command works without Proxmox or credentials.
- Valid configuration produces a redacted summary. Unknown/missing fields, unsafe TLS settings, disallowed workload bridges and invalid budgets fail clearly before any network call.
- Tests cover successful/partial inventory, empty responses, malformed payloads, 401/403, TLS failures, transport timeouts and bounded read retries. They assert inventory sends no mutating request.
- Live test selection is skipped by default. Selecting live tests without both `--live` and `REHEARSAL_LIVE=1` stops before connecting. Unit tests need no GitHub login, Docker or PostgreSQL.
- Fake secret values do not appear in captured output or persisted error records. SQLite schema creation/transaction recovery is covered using temporary local files.
- No VM creation, template changes or live mutation is included in this milestone.

Suggested first implementation slice: **package entry point → TOML schema/validation → fixture inventory → mocked HTTP inventory → tests and usage**. Add state primitives after that slice; avoid building a generic workflow framework first.

## Milestone 2 — Deploy to rehearsal01 and enable live inventory

**Goal:** run the same packaged CLI on a separate controller VM and collect a trusted, read-only lab inventory.

Prerequisites to arrange separately:

- Host operator creates `rehearsal01` outside `pve01`, checks `.83` for conflicts and supplies its OS/access details. Initial sizing is 1 vCPU, 2 GiB RAM and 20 GiB disk. This manual bootstrap does not create a host-management dependency for the software.

- Establish controller management connectivity, time synchronisation and an update/artifact path. Controller deployment/connectivity and its package delivery were verified; PVE's NAT route/DNS do not prove guest egress. Do not reuse the removed `192.168.56.254` default gateway.
- Obtain the PVE CA through a trusted channel and configure a matching certificate hostname or IP SAN. This is now verified with an application-specific CA and dedicated privilege-separated audit token; retain the existing trust/credentials unchanged.

Current runtime status: deployment succeeded at verified `192.168.56.83/24`. The existing wheel's digest matched, runtime dependencies were installed offline with hash checking, configuration validated as UID 999, and real TLS 1.3/API inventory passed. Dedicated user and token have four scoped audit privileges, including bridge `SDN.Audit` discovered from actual filtering. No app service or resource-write privilege was added. The [controlled controller/PVE reboot checks](controller-reboot.md) subsequently passed; intermittent SSH dial timeouts remain an operational follow-up, not a failure of the recorded API run.

Work:

- Install a pinned wheel/dependencies into a versioned runtime venv under a dedicated unprivileged account. Set up protected configuration/credential references and local state/evidence directories.
- Provide a reproducible install/upgrade procedure and a short operator runbook. Introduce the systemd executor when queue processing is available; a long-running service is not necessary merely to run inventory.
- Run one explicitly enabled live inventory **from the controller**. Capture PVE version, node identity, visible templates, bridge configuration and actual storage layout/free capacity. Verify audit permissions without granting mutation privileges.
- Update the environment document with dated evidence and open gates. Keep live checks separate from default tests.

Acceptance criteria:

- The installed CLI reports its build revision and works after a controller reboot, without executing runtime services on `dev01`.
- A live inventory completes with verified TLS and scoped authentication, or produces a precise layer-specific blocker. Success is required before advancing to provisioning.
- Inventory evidence distinguishes storage's virtual/logical availability from backing-space guarantees. Unknown thin-pool health, insufficient visibility and templates with unsafe defaults remain explicit gates.
- Protected credentials are absent from reports/process arguments; controller state/evidence persists independently of test VMs.
- No test VM or platform network is created by the inventory command. A read-only token cannot perform provisioning.

If the controller or trust material is unavailable, finish the deployment package/runbook and retain the blocker. Do not repeatedly probe PVE or move the runtime onto `dev01` as a workaround.

## Milestone 3 — Disposable VMs, reconciliation and cleanup

**Goal:** prove one tiny nested VM can boot and be removed safely, including after controller/API interruption, before deploying a database.

### 3A — First guest and validated template

The [concrete provisioning plan](nested-guest.md) selects Ubuntu Server 24.04 amd64 released build 20261017; build/template ID 9000; later full validation clone 9100; 1 vCPU, 2 GiB RAM and 12 GiB root disk on `rehearsal-lvm`. The shared pool exists; no VM or resource reservation exists yet. Current authorization ends with tested 9000 stopped, before cleaning/conversion/cloning. Initial maximum is one operation/run and one running nested guest.

Gates before any live attempt:

- **Complete:** both authorized platform reboots passed with unchanged installation/trust/credentials and effective platform guards. This does not prove future guest-rule persistence.
- **Implemented/offline-tested:** separate one-shot supervised tool with durable journal/task/ownership/cleanup/capacity checks. Create/import/resize have live evidence; first-start reconciliation is pending PVE recovery. Inventory remains read-only.
- Dedicated `REHEARSAL-TEST` interfaces/bridge, controller filter and [PVE legacy backend/bridge guard](firewall-isolation.md#successful-pve-only-activation) are configured; platform activation passed and the controller was preserved. Both guest allowlists remain empty. Prepare/read back exact stopped-guest policy, then validate nested-MAC passage and positive/negative packet paths in an authorized guest exercise. `vmbr0` remains management-only and both VMs' routing forwarding off; no guest internet route is provided.
- **Inputs verified:** signed image/checksum, actual qcow2/3.5 GiB virtual size, offline guest-agent package closure and dedicated key. Authenticated serial-console host-key bootstrap remains a real-boot gate. The stock manifest lacks the agent. One-time arbitrary-path import is a trusted operator local-API bootstrap; runtime cloning later needs no PVE shell/root token.
- Initial `pve01` physical backing-capacity gate is **satisfied** on user-supplied filesystem/screenshot evidence: both dynamic VDIs are under `/mnt/ssd`, with 636 GB available. Continue actual-host-space monitoring as they grow and fresh pool/root/metadata/RAM admission checks. `dev01`/`rehearsal01` disk locations remain unverified. Pool/credential preparation and fresh host admission passed; 9000 was reserved/created/imported/resized, then its first start became uncertain after PVE access loss; inventory identity/token/ACLs remain unchanged.

Acceptance: real Ubuntu/cloud-init boot and filesystem growth; controller-to-guest pinned SSH command/nonce and agent checks; enforced connectivity/negative isolation evidence; no guest internet dependency; sanitized stopped template with `onboot=0` and no active NIC/build keys; one full clone with new machine ID/host key and working independent credentials; verified owned-clone deletion and retained evidence. No application or recovery exercise yet. Template promotion removes it from ordinary cleanup and ordinary provisioning write scope.

### 3B — Repeatable disposable VM lifecycle

Prerequisites after 3A:

- Use the approved versioned cloud-init template from 3A, with verified image/package hashes, guest agent, regenerated guest identities, `onboot=0` and absent NICs. Include required OS packages or verified controller-delivered bundles; no guest internet is assumed.
- Prepare the dedicated controller-to-PVE test network/bridge and enabled firewall policy. Example names/subnets in the architecture are subject to conflict review. No existing `LAB-*` mapping is assumed.
- Allocate a pool and exclusive VMID set, identify protected template/service IDs, confirm storage headroom, and approve an endpoint/permission matrix for a separate mutation token.

SSH verifies AMD-V/KVM exposure, loaded modules, `nested=1`, `/dev/kvm` and KVM API version 12; these do not pass nested-boot acceptance. Use 90 GiB `rehearsal-lvm`: **18 GiB reserve + 36 GiB for three 12 GiB disks + 2 GiB auxiliary allowance leaves 34 GiB unassigned**, superseding the earlier three-by-6-GiB estimate. Charge full logical capacity independently of initial thin allocation/clone behavior. The separate 8 GiB VG free space is not pool capacity. User-supplied `/mnt/ssd` capacity and both `pve01` VDI locations satisfy its initial backing-capacity gate; continue actual-host-space checks as those dynamic VDIs grow. The PVE NAT adapter is not the planned isolated test segment.

Work:

- Add the serial executor/systemd unit, durable queue, installation/run/resource ownership, request journal, UPID polling/log capture and resource postconditions.
- Implement stopped cloning, ownership marking, cloud-init configuration, firewall/NIC readback and a fail-closed pre-boot gate. Pin guest SSH host keys using an authenticated, tested bootstrap mechanism.
- Implement expiry/lease reconciliation and cleanup under the executor lock, with an inventory/preview mode that explains exactly which resources are eligible and why. Until that exists, supervised 3A attempts need explicit operator lease/expiry reconciliation; do not claim an automatic sweeper.
- Reserve IDs in the journal; reconcile uncertain API responses instead of allocating new IDs. Treat incomplete provenance as a manual reconciliation case.
- Test capacity admission, cancelled runs, state restart and per-step deadlines. Maintain an explicit protected-resource denylist in addition to positive ownership checks.

Acceptance criteria:

- Live, explicitly enabled evidence proves a nested VM on `pve01` actually boots: capture task completion, guest identity, guest-agent readiness and a verified SSH command. CPU flags or an accepted start task alone do not pass.
- Before boot, evidence shows only the approved test NIC, enabled enforcement, fresh identity and no management/storage/cluster mappings. Negative connectivity checks confirm isolation after boot.
- A successful run deletes its owned VM and recorded volumes, then verifies their absence and restored capacity within measurement limits. It never deletes the template, shared infrastructure or unrelated resources.
- Offline failure fixtures cover response lost after accepted clone, crash before ownership marking, reused VMID with wrong nonce, task error with partial disk, active task past deadline, permission loss, concurrent sweeper and missing journal.
- The ambiguous-clone fixture demonstrates no second creation request. Wrong/missing ownership markers produce zero destructive calls. A running/unresolved task prevents disk deletion.
- A controlled live controller restart after provisioning reconciles the existing VM; an expired abandoned run is cleaned after lease/task checks. Failed cleanup remains visible and retryable with retained evidence.
- Concurrent manual submissions cannot exceed one active run. Source/target allocation forecasts plus reserves must fit; insufficient capacity fails before mutation.

Do not proceed to application deployment if real nested boot, isolation or cleanup is unproven. Recheck pool/metadata and physical-host headroom before admission; the new storage budget is planning evidence, not permission to provision. Do not expand storage automatically.

## Milestone 4 — Application and verified PostgreSQL recovery

**Goal:** demonstrate independently checked application behaviour and recovery of a deterministic dataset into a different isolated VM.

Work:

- Build the minimal order API, PostgreSQL schema and separate systemd worker. Use idempotent order/job handling, integer money values and explicit SQL migrations.
- Prepare pinned workload artifacts and a documented database/client major. Install from controller-delivered artifacts; retain release hashes and service logs.
- Build the controller manifest generator and independent HTTP/SQL verifier. Keep expected fixtures independent of application code and outside guest disks.
- Implement the logical backup/restore sequence in the architecture, including write quiescence, archive publication, source unavailability, separate target identity and verification before new target writes.
- Support sequential source deletion/target allocation when capacity requires it. Build reports with phase durations, record-level differences, evidence hashes and cleanup outcomes.
- Add a small v1→v2 upgrade and code rollback using an additive compatible migration; explain the boundary between code rollback and database recovery.

Acceptance criteria:

- HTTP create/read/idempotency behaviour and direct SQL assertions pass for the known dataset. Stop the worker: liveness can stay 200 while the progress canary correctly fails. Restarting it resumes work without duplicate receipts.
- The controller retains the expected manifest before seed, a successfully completed backup and the full recovery report. Source and target VMIDs/endpoints are distinct, and the source is unavailable throughout target verification.
- Restored records, keys, sums, receipt relations, constraints and sequences match the manifest. A new post-restore canary proves HTTP writes and worker completion after the initial comparison.
- Deliberately missing, extra and altered records, a corrupt/truncated dump, failed restore command, stale manifest and wrong verification endpoint each fail the relevant exercise with a useful reason.
- Durations include target provision/boot and verification; discontinuous timings are marked incomplete. The report states the frozen-write boundary and makes no general zero-RPO or service-RTO claim.
- Upgrade and code rollback preserve existing orders and canary behaviour within the declared schema compatibility range. An incompatible migration is rejected or routed to an explicit restore exercise.
- Reports survive guest deletion and failed runs; cleanup still passes the milestone-3 ownership guards. Evidence collection failure cannot be reported as a successful exercise.
- PBS, VM snapshots and whole-VM backup are not prerequisites for this exercise.

## Milestone 5 — CI integration and richer exercises

**Goal:** present a reproducible portfolio workflow while preserving the public-code/lab-access boundary.

Work:

- Add public GitHub-hosted CI for PRs and `main`: package/configuration checks, offline provider/lifecycle/verifier tests and lint. Optionally add a separate PostgreSQL service-container job for application tests; no lab secrets.
- Establish the optional private lab-workflows repository and separately placed runner only in a future task that authorises those changes. Register the runner only there; no self-hosted runner serves this public repository.
- Build the restricted SSH driver contract to the installed controller release. Use maintainer manual dispatch, allowlisted exercises, approved immutable revisions, fixed lab concurrency, timeouts and idempotent submission keys.
- Retrieve sanitised report artifacts on success/failure with bounded retention. Keep the controller's evidence authoritative if a workflow is cancelled or upload fails.
- Add controlled worker termination, database/service interruption, failed deployment, and bounded latency/load exercises one at a time, using only proven owned guests and reversible fault hooks.
- Document troubleshooting examples: TLS failure, missing privilege, guest boot failure, disk admission failure, unhealthy worker, restore mismatch and cleanup pending.

Acceptance criteria:

- A fork PR runs only on GitHub-hosted infrastructure without lab connectivity or credentials. No lab workflow checks out untrusted PR code or consumes its artifacts as executable input.
- The private/manual lab workflow validates its source revision and targets an installed approved controller release. The runner cannot submit arbitrary shell commands, edit controller code/state or obtain a PVE token.
- Two dispatches serialize at GitHub and at the controller; a duplicate submission does not create duplicate resources. Runner/job cancellation leaves a durable controller run that completes or is reconciled/expired safely.
- A failed exercise still yields a sanitised report when the runner is available. Fake-secret export tests demonstrate exclusion of credentials, dumps and raw guest configuration.
- At least one controlled failure is diagnosed by independent checks and recovered, with resource cleanup/evidence intact. Every fault is scoped to a recorded owned guest; no host, storage network or unrelated VM fault is introduced.
- Load reports specify nested topology, limits and run variability. They make no production throughput/latency or physical-host-resilience claims.

Private runner setup is optional: public CI plus trusted manual controller execution remains usable if it is deferred. Review account-supported branch/environment protections when implementing; no GitHub settings were inspected or changed beyond read-only repository metadata in this design task.

## Later, separately scoped work

- Whole-VM backup/restore using PVE backup facilities: test destination space, backup consistency/quiescence, image restore while stopped, identity replacement and pre-boot isolation, then reuse the independent application verifier.
- Optional PBS integration: a separately provisioned datastore/service and credentials, retention/prune/verification policy, capacity and recovery exercises. PBS availability or backup-job success is not evidence of successful application recovery.
- PostgreSQL base backup/WAL archiving and PITR: define continuous-write ledgers, recovery targets and loss measurement before claiming RPO behaviour.
- Multiple Proxmox nodes or manually coordinated node-failure exercises only after observer placement, permissions, network paths, capacity and failure scope are proven. Shared physical-host dependence remains.

## Current blockers and next task

The 12 November baseline passed **219 tests** with network access blocked. Local
13 November work adds request evidence and failure-path coverage without lab
credentials or new dependencies; the subsequent review passes **272 offline tests**, Ruff and dependency checks
pass on dev01. The deployed inventory and original supervised
sidecar remain unchanged. Create/import/resize and stopped-guest policy have
historical live evidence; boot/guest checks and clean shutdown remain unverified.

The [13 November handoff](investigation-2026-11-13.md) records VM 9000 last observed
stopped/disconnected, both task histories unavailable after completed searches,
and the second operation still uncertain. Do not repeat historical searches
without new evidence, rerun automation, start/import again, delete resources or
clear reconciliation state. Live nested-start validation remains blocked by the
unresolved host fault and requires a separate explicit operator decision.

Next development can extend read-only offline evidence inspection/reporting while
keeping confirmed task failure, current resource state, unavailable history and
unknown mutation outcome separate. Executor, workload/recovery, UI and Actions
remain future work. Keep inventory credentials unchanged; the separate bootstrap
expiry **2026-11-13 15:08:20 UTC** has passed, with no renewal or broader rights
authorized by development. No CPU/network/hypervisor changes are part of this work.
