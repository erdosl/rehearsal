# Design decisions and tradeoffs

**13 November 2026:** the [supplied investigation handoff](investigation-2026-11-13.md)
supersedes the infrastructure summary below. The observed VirtualBox host fault
mechanism is distinct from application defects; root cause is unresolved and
nested validation needs a separate explicit operator decision. Local evidence
changes are offline-tested and undeployed; historical journal meanings remain
unchanged.

Date: **2026-11-12**, updated after operator recovery and renewed instability. Inventory/tooling remain unchanged; VM 9000 and its exact volumes/policy exist. The operator's one-vCPU/16 GB restart enabled read-only reconciliation of the existing stopped guest. A distinct authorized start again lost PVE access; the new operation is uncertain and the attempt halted. Guest boot/status/stop remain unverified. [Current evidence](supervised-build.md#operator-restart-and-supervised-recovery-attempt) takes precedence over lab assumptions; executor/recovery remain future work.

The reported multi-vCPU VirtualBox hang pattern is provisional. Shutdown method and root cause remain unestablished; the renewed loss with verified one CPU/increased RAM does not validate that workaround for this workload. More RAM does not authorize higher guest concurrency. A task result missing after restart remains historically unknown; only a changed boot boundary, ended original worker and independently verified stopped/unlocked owned resource with exact volumes/no active tasks allowed current-effect reconciliation. This did not authorize blind create/import repetition or uncertain cleanup.

## D01 — Separate development and runtime

Use `dev01` for editing, offline tests and Git. Provision `rehearsal01` separately, preferably as a sibling of `pve01` outside the node under test. This preserves an observer and evidence store during PVE failure, at the cost of manual initial host work. Runtime never requires host SSH, shared folders or `VBoxManage`. Hosting the controller inside PVE is a fallback limited to guest-level exercises. Neither placement survives physical-host failure independently.

Revisit for a genuinely independent second host or a deployment environment with different failure domains.

## D02 — One Python process and local durable state

Use Python 3.12, an argparse CLI, a serial systemd executor and transactional SQLite state. A local queue and installation/run/resource journal are sufficient for one controller. This keeps Linux service operation, troubleshooting and restart behaviour visible without broker/database infrastructure for the controller itself. SQLite is separate from workload PostgreSQL.

Revisit only for multiple active controllers or demonstrated concurrency/storage requirements; do not introduce Kubernetes for this lab.

## D03 — A small direct API adapter with explicit task handling

Use HTTPX behind a provider interface, standard-library TOML validation and fixture transports. Keep PVE requests, UPIDs, deadlines and resource postconditions visible rather than adding a provisioning framework initially. This creates some API maintenance work, but directly serves the Python/Proxmox learning goals. Match capabilities and ACLs to the installed API before implementing writes.

HTTPX 0.28.1 is now the single direct runtime dependency for the GET-only API adapter. It provides HTTPS, bounded I/O and injected test transport. Fixtures remain explicit simulations, not fallback data. TLS context and protected token loading precede requests; live CLI access needs both opt-ins. Runtime/development dependencies have separate hashed locks. Partial queries remain failed/skipped coverage and nonzero exit; successful list queries still carry an explicit ACL-filtered visibility limitation.

Revisit a maintained higher-level client if the adapter becomes repetitive; it must preserve timeout, TLS, task and ambiguity semantics.

## D04 — Reconcile uncertain effects instead of assuming exactly-once APIs

Local implementation update, 13 November: append request-start/end observations
with operation/request UUIDs, UTC/monotonic timing, HTTP status, safe transport
categories and UPID source to the existing event table. Record task status before
fetching logs so confirmed failure survives log loss. Missing task evidence or
exit status stays unknown; current stopped state cannot settle historical start
success. No backfill, terminal-row rewrite, new dependency or live deployment is
part of this change. See [the evidence contract](supervised-build.md#offline-request-evidence-13-november-2026).

Persist intent before mutations, reserve exclusive VMIDs locally and retain UPIDs. A lost response is an uncertain outcome; reconcile the existing operation rather than issuing another clone. Provenance gaps stop automation. This may leave quarantined resources requiring review, which is preferable to duplicating VMs or destroying a resource whose ownership is unknown.

Acceptance depends on lost-response/crash fixtures and a live restart exercise, not a general claim of idempotent provisioning.

## D05 — Positive ownership and bounded expiry cleanup

Require the durable installation/run/resource identity and matching live nonce/metadata plus allowlist/protected-resource checks. Names, pools, ranges and TTLs alone do not authorise deletion. A sweeper handles expired runs only after lease/task reconciliation. Keep cleanup status distinct from exercise outcome so a passing application check cannot hide leaked resources.

Shared templates, networks and pools are operator-owned. After state loss, require reconciliation rather than adopting everything with a Rehearsal-looking tag.

## D06 — Dedicated test connectivity is a hard prerequisite

Use the matching VirtualBox internal network between controller and PVE, with a dedicated bridge and deny-by-default guest policy configured before boot. The operator completed `REHEARSAL-TEST`, PVE `enp0s16`/`vmbr1` and controller `enp0s9`/`10.77.0.1`; [supplied findings](environment.md#operator-supplied-dedicated-test-network) distinguish configuration from unverified guest connectivity/enforcement. The [successful activation record](firewall-isolation.md#successful-pve-only-activation) confirms the legacy PVE framework and scoped native bridge guard are active, with the previously verified controller input/forward filter preserved and node host-zone filtering off. Disabled pre-activation compilation is checked separately from post-activation kernel enforcement. Guest allowlists remain empty; exact guest policy and packet checks are required before admitting a guest. Do not assume differently named existing networks connect.

Revisit only with an explicitly designed, verified alternative. A management-bridge attachment is not an automatic fallback.

## D07 — Conservative storage admission and serial runs

Start with full clones and one active exercise, using **`rehearsal-lvm`** for template/test disks. The concrete Ubuntu plan replaces the earlier 6 GiB estimate with **12 GiB per disk**. The 90 GiB pool budgets 18 GiB reserve, 36 GiB for template plus two full clones and 2 GiB auxiliary allowance, leaving **34 GiB unassigned**. Initially only one guest may run; the template is stopped before its validation clone boots. Later two-guest recovery requires additional validated isolation/capacity gates. The 8 GiB unallocated VG space is separate; metadata and its spare are each 1 GiB. Thin allocation, image compression and linked-clone sharing do not reduce worst-case admission commitments.

The original 32 GiB OS disk and 11.8 GiB `local-lvm` remain unchanged and are not the test-disk target. Check fresh pool data/metadata, OS staging space, actual image requirements and operator evidence of physical-host backing space before provisioning. The host remains inaccessible from `dev01`; virtual capacity does not prove host disk headroom.

The user subsequently supplied 636 GB available on ext4 `/mnt/ssd` (`/dev/sdc1`, 916 GB total) and VirtualBox screenshot evidence confirming both `pve01` dynamically allocated VDIs there. **The initial physical backing-capacity gate for `pve01` is satisfied.** Keep fresh operator checks of actual host free space as these VDIs and any snapshots grow. The [environment record](environment.md#user-reported-physical-host-capacity) retains exact paths and supplied disk capacities; it establishes no backing-file location for `dev01` or `rehearsal01`. Do not require host administration from `dev01`.

Revisit cloning mode or add storage only after inventory and an explicit implementation/provisioning task. No capacity or performance promise is inferred from the physical host's RAM/cores.

## D08 — Native systemd workload with a PostgreSQL queue

Use FastAPI/Uvicorn, a separate Python worker, Psycopg 3 and PostgreSQL 16 initially. Native guest services expose logs, process lifecycles and recovery work relevant to Linux engineering. PostgreSQL-backed jobs avoid Redis/Celery and let HTTP stay alive while worker checks fail meaningfully. Keep SQL/schema changes explicit and small.

Docker Compose is useful for optional local/hosted-CI database tests; it is not required on the controller. Revisit application complexity only when a new exercise needs it.

## D09 — Logical restore first; VM recovery and PBS later

The first exercise uses a logical PostgreSQL backup, a fresh separate target and an independent manifest. It demonstrates data recovery without requiring a VM backup stack or PBS. It does not recover an entire guest OS, roles automatically, WAL history or continuous service state. Whole-VM restore needs separate consistency, capacity, identity and isolation checks; PBS is an optional backup backend for later work.

Revisit physical/WAL backups for PITR and write-loss experiments. Never treat backup-job success as recovery evidence.

## D10 — External expectations and qualified recovery metrics

Generate expected domain records before seed and retain their manifest outside guests. Verify through independent controller SQL and HTTP checks, then a worker canary. Freeze writes for the first backup so the expected dataset and recovery boundary are unambiguous. Record recovery/provision/verification durations with explicit start/end conditions.

The result is an observed recovery of a stated synthetic dataset. RTO assessment requires declared objectives and complete outage/detection/recovery boundaries. RPO measurement requires independent acknowledged-write and recovered-boundary evidence; a frozen successful restore does not prove zero RPO for an active service.

## D11 — Immutable releases with explicit schema compatibility

Use pinned wheels/release directories and additive migrations for the first upgrade/rollback exercise. Reverting the active release is understandable and testable when both versions support the schema. A destructive migration cannot be reversed by a code switch; require a separate recovery strategy and evidence before exercising it.

Revisit a migration framework when the number/complexity of schema changes warrants one.

## D12 — Public CI and trusted lab execution have separate runners

Use GitHub-hosted runners for public PR/main CI. Prefer a private, manually dispatched lab-workflows repository for any self-hosted runner, with approved revisions and restricted controller commands. Keep PVE credentials on the controller. This adds a small workflow boundary but avoids attaching a lab-capable runner to a public repository. Until it is established, live runs remain manual on the controller.

Job labels and environment approvals do not alone isolate a persistent machine. Add scheduled lab exercises only after reliable cleanup. The detailed rationale and official references are in the [Actions trust model](architecture.md#github-actions-trust-model).

## D13 — Evidence survives guests, with explicit retention

Retain controller state, manifests, task logs, synthetic dumps and reports outside disposable VMs. Export only a defined sanitised report bundle to Actions. Bounded retention and quotas prevent the evidence store becoming the next disk-full incident. Evidence hashes help detect accidental corruption; they do not establish protection from a malicious controller administrator or physical-host loss.

Revisit off-host storage when host-loss recovery becomes a goal; no such destination is assumed now.

## D14 — Credentials and transport are configuration, not workarounds

Use proper PVE TLS validation and dedicated expiring tokens with separated read/mutation rights. Check operation-level permissions against the real version rather than granting an administrative role to fix errors. Use protected runtime credential references and synthetic data only. The initial issuer-trust failure was resolved with an application-specific CA while certificate identity checking remained enabled.

Do not embed private keys, credentials, production data or unsanitised reports in the public repository. Guest SSH also requires verified host identity; authenticated guest-agent bootstrap is a capability to validate before relying on it.

The new SSH inspection verified broad `NOPASSWD: ALL` for `jgipsz`; this is not adopted as the controller's permission model and does not establish API authorization. KVM prerequisites are exposed, but a successful nested workload boot still requires a separate owned-VM test. The physical host remains inaccessible and the new NAT uplink does not replace test-network preparation.

Real deployment confirmed that method declarations alone do not describe all list filtering. In PVE 9.2.2, bridges also require SDN visibility: add only `SDN.Audit` for `/sdn/zones/localnetwork/vmbr0` to owner and token, alongside node/storage/VM audit. No `SDN.Use` or Administrator role is needed. The [live runbook](live-inventory.md) records the installed-source check and real comparison with privileged lists.

Deployment uses an application-specific CA and the existing IP SAN, so no PVE certificate, system trust or hostname mapping change was required. Token creation output was captured and relayed directly into a runtime-owned 0400 file; reruns reuse that file and never silently rotate an existing token. The verified wheel is immutable/root-owned, and no persistent service was added for the one-shot check. Intermittent SSH dial timeouts and a future reboot test remain operational follow-up, separate from the successful TLS/API result.

## D15 — Validate a guest before template promotion

Use a pinned Ubuntu 24.04 released cloud image, authenticated checksum/signature verification, one temporary build guest (proposed 9000) and one subsequent full validation clone (9100), sequentially. Demonstrate real boot, pinned guest SSH, cloud-init, disk growth, agent and connectivity before converting the build into a stopped template. Clean identities/keys and validate regeneration in the clone before approving it. The published image manifest lacks `qemu-guest-agent`; install a verified offline package bundle after console-based SSH trust bootstrap. No guest internet route is assumed or required.

Installed PVE storage code limits arbitrary filesystem image-import paths to `root@pam`. Keep that one-time image import in a trusted operator's local API bootstrap; do not broaden the runtime token or storage content types. Later runtime cloning uses HTTPS and a separate scoped mutation identity, preserving the inventory token unchanged. Remove build-template write/allocation permissions after approval. The [concrete guest plan](nested-guest.md) records the endpoint/permission matrix, ownership, capacity and failure cleanup gates; none was executed during preparation.

## D16 — Reboot persistence before first provisioning

Validate release/configuration/trust/credential and platform enforcement persistence before provisioning. The authorized one-at-a-time `rehearsal01` and `pve01` checks passed on 2026-11-12, with changed boot IDs, effective guards and fresh management/live inventory without repair. No application daemon was introduced. [Execution evidence](supervised-build.md#completed-persistence-checks) does not establish guest-rule persistence or nested boot.

## D17 — Separate supervised build tool before an executor

Deploy `rehearsal_build` beside the immutable inventory release, using its existing interpreter/dependencies and separate configuration, bootstrap credential and durable SQLite state. Require explicit exercise/live opt-ins, one VMID, committed intent, ownership nonce, bounded UPID reconciliation and exact-volume cleanup checks. Use the existing trusted operator only for the one-time privileged import/console and scoped firewall work. No scheduler or daemon is needed to prove one guest.

The implementation is offline-tested with live preparation, create/import/resize and stopped-guest policy evidence. The newer start after operator recovery is uncertain after renewed PVE management loss; actual boot, guest checks/stop and end-to-end enforcement remain unverified. Retain the resource and both UPIDs, preserving the old result as historically unavailable and reconciling the new current effect; never infer that an unreachable VM is stopped. Keep fresh physical-host capacity as separately supplied input; do not infer it from virtual thin-pool free space. Current authorization stops before identity cleaning, template conversion or clone validation.
