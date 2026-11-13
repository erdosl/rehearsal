# Prepared Proxmox guest recovery slice

## Implemented contract and present evidence

This slice runs the existing PostgreSQL exercise on **two separately prepared
Proxmox guests**, using native PostgreSQL and the same Python application. It does
not clone, create, boot, reconfigure, deploy to, or delete VMs. Preparation is a
separate operator-authorized lifecycle step. This keeps the application integration
useful without introducing a new provisioning framework or weakening the supervised
VM-9000 contract.

`GuestRunner` inherits the actual `Runner.execute`, manifest, seed, quiescence,
native backup/restore publication, SQL/schema/API verifier, negative cases, canary,
timing and evidence finalization. Small transport/lifecycle hooks select local
Docker or authenticated SSH. There is no second recovery algorithm.

Implemented:

- Strict offline configuration for guest identities, addresses/test subnet,
  protected VMIDs (9000 is mandatory), storage volumes, single isolated NIC,
  credential references, machine IDs and approved wheel digests.
- Verified-TLS **read-only** admission using the existing `BuildAPI`: exact durable
  configuration ownership versus live installation/run/resource/nonce/role, node,
  pool, VMID and volumes; no template/lock/active tasks; explicit `onboot=0`,
  firewall enablement and sole test NIC. A fresh operator isolation receipt and
  bounded preparation lease are required. The receipt is a **supplied fact**;
  configuration readback alone cannot prove effective packet enforcement.
- Batch public-key SSH with a separately pinned Ed25519 host key for each resource,
  strict host-key checking, no agent/config/proxy/multiplexing fallback, bounded
  commands and matching machine/release identity. The guest checks installed module
  bytes against its approved wheel, not merely the wheel's presence.
- A guest-side exclusive exercise lease. Another exercise cannot overwrite it or
  stop its services. No expiry-based takeover exists. Native clients use the local
  PostgreSQL socket/port with a sanitized environment; the API uses explicitly
  checked loopback settings. Source database and writers stop before target checks.
- SHA-256/size-framed backup transfer to the observer and checksum validation before
  target `pg_restore`, including an authenticated restore receipt. Archive input is
  bounded to 16 MiB. The source stays intact until deliberate service shutdown;
  prepared guest disks are never deleted.
- The existing protected SQLite `Journal` for intent, leases, operation outcomes
  and request evidence, in a **new independent root**. Guest commands retain durable
  receipts keyed by operation UUID, owner and input hash. Lost responses/interruption
  remain uncertain; matching terminal receipts can reconcile them without reissuing
  the mutation. Missing/conflicting receipts block further mutations and cleanup.
- Reuse of the existing UPID reconciler for an **exact already-recorded** lifecycle
  task belonging to one configured prepared guest. It performs GETs only; missing
  task history stays uncertain. No task discovery or historical VM-9000 search is
  initiated by this slice. All `PreparedAPI.mutate` calls are rejected.
- Owned-service cleanup and retained evidence. Services must stop before the guest
  lease is released. Prior releases from another exercise cannot authorize cleanup.
  A lost local request journal fails closed. Existing recovery artifacts are never
  overwritten by a resumed execution; only explicit reconciliation/cleanup continues.

Admission also requires the dedicated default cluster data directory
`/var/lib/postgresql/18/main`, port 5432, no other database sessions and no unrelated
user schema objects. If admission fails after claiming a lease, cleanup retains
that lease for review and **does not stop the unadmitted cluster**. A preparation
mistake cannot turn an unrelated database into an exercise cleanup target.

**Verified locally:** offline contract tests use HTTPX mock responses and simulated
SSH/SQL/HTTP protocol fixtures. Their reports say `simulated: true`; fixture archives
are not PostgreSQL backups. They exercise the full shared success and altered-data
workflow and failure/ownership boundaries. The shared algorithm also passes real
local Docker recovery tests. **No live Proxmox guest, SSH handshake, native guest
service or guest transfer has been validated in this development task.**

Final local validation: **354 offline tests passed** (two Docker cases skipped by
default), including **26 guest contract/failure cases**; both explicit real Docker
cases passed after the shared transport changes. Ruff lint/format, dependency checks,
offline configuration validation, actionlint and staged wheel/sdist/install/resource
smoke checks passed. The final targeted guest suite was rerun after tightening
per-guest tool-version checks. The package smoke now checks the guest agent/CLI and
preparation examples are shipped. The shared Docker recovery and offline checks
have subsequently [passed on GitHub-hosted runners](ci.md#verified-hosted-execution-13-november-2026);
this adds no live Proxmox guest validation.
Final Docker evidence is retained at
`~/.local/state/rehearsal-final-docker-20261113-e118/`; its successful recovery took
32.005019 seconds and the altered-record case failed as expected. Both cleaned up,
their indexed hashes were checked, and no exercise Docker resources remain.

## Prerequisites and validated inputs

The current one-running-nested-guest ceiling is unchanged. This adapter's
two-already-running-guest contract **cannot be used under that ceiling**. A separate
two-guest capacity/isolation authorization is required, or a later sequential
power/provisioning adapter. The code makes no capacity increase or VM power call.

Prepare only freshly allocated, isolated disposable guests through a separately
reviewed lifecycle. Durable allocation provenance must identify exact ownership
and volumes; copying a name/prefix or choosing a VMID range is not ownership.
The example [prepared-guests.toml](../examples/prepared-guests.toml) contains fake
bindings and addresses, zero digests and expired receipt times; it proves no VM
exists or address is free. Do not point this adapter at VM 9000, a template, the
controller or a guest with unrelated workloads.

Required guest preparation, **not performed by this task**:

1. Independently prove boot, effective IPv4/IPv6 isolation and observer-only SSH/
   application access before admitting application work. Enforce isolation before
   boot, retain the packet evidence, then put its fresh UTC observation in
   `isolated_at`. This admission window is 15 minutes; the configured lease must
   expire within the next hour. No automatic extension is implemented.
2. Install PostgreSQL **18.7** server/native tools, Python 3.12 and an approved
   reviewed workload wheel with hashes. Retain the wheel at
   `/opt/rehearsal/artifacts/rehearsal.whl`, root-owned/read-only. Build on dev01
   with `.venv/bin/python tools/package_smoke.py`; its output identifies the build
   directory. Use that exact approved wheel digest in both guest bindings.
3. On each **fresh** guest create `/opt/rehearsal/venv`, install hash-locked runtime
   and optional exercise wheels from an operator-delivered wheelhouse, then install
   the workload wheel with `--no-index --no-deps`. No guest internet is required.
   Do not overwrite the controller's deployed release or any existing unexpected
   installation. The guest must listen only on loopback, port 5432, in the dedicated
   `postgresql@18-main.service` cluster.
4. Create only database `orders` from `template0` and a limited `order_app` login.
   Give each guest its own generated protected application credential at
   `/etc/rehearsal/order-password`, readable only by `rehearsal-order`. No password
   belongs in argv, config, Git or output. Keep the database empty: no unrelated
   schemas, relations, functions or databases. Source v1 schema initialization is
   performed by the exercise; the restore schema comes exclusively from its dump.
5. Install the reviewed [service template](../examples/guest-orders.service) as
   `rehearsal-orders.service`, owned by root, with no drop-ins or EnvironmentFile.
   It explicitly removes libpq host/service overrides. Keep it stopped initially;
   PostgreSQL must already be ready. Provide the dedicated SSH account a mode-0700
   `/var/lib/rehearsal/exercise` directory and noninteractive permission only for the
   reviewed native database commands as `postgres` and the exact start/stop service
   operations used by `guest_agent.py`. This account controls the synthetic database
   as an administrator inside its disposable guest; it must never hold lab/production
   credentials or serve public PR code.
6. Regenerate and independently authenticate distinct guest SSH host keys. Each
   observer `known_hosts` reference must contain exactly one line:
   `rehearsal-RESOURCE_UUID ssh-ed25519 PUBLIC_KEY`. Verify its fingerprint through
   a trusted bootstrap channel; `ssh-keyscan` alone is not authentication. Private
   key references must be regular runtime-owned 0600/0400 files; public trust files
   must be runtime-owned and not writable by group/others. No credentials are read
   by the offline configuration validator.
7. Retain current machine IDs, exact disks and ownership from the separate lifecycle.
   Choose an existing operator-approved audit token and trusted CA reference with
   the required GET permissions. An expiry or ACL failure does not authorize renewal
   or broader rights. No bootstrap credential, ACL or infrastructure change is
   performed by this adapter.

The adapter checks these conditions where independently observable. Native guest
permissions, process/service compatibility, firewall packet enforcement and capacity
still require supervised live validation. Preparation receipts and configured
identity are supplied assertions until checked against live metadata/SSH.

## Commands and retained state

Offline structural validation (safe now, no credential access/network):

```bash
.venv/bin/python -m rehearsal_exercise.guests validate --config examples/prepared-guests.toml
.venv/bin/python -m pytest -q tests/test_guests.py
```

**Only after separate live authorization and preparation**, run from a trusted
reviewed release, never untrusted PR code:

```bash
REHEARSAL_LIVE=1 .venv/bin/python -m rehearsal_exercise.guests run --live \
  --config /protected/prepared-guests.toml --artifacts /protected/new-guest-exercise-root
```

This may start the prepared **application service** and mutate its synthetic
database; it never starts a VM. Select `--fault changed-record`, `missing-record`
or `corrupt-backup` only for a separately approved negative exercise with fresh
prepared guests. Both explicit opt-ins are required before token/SSH use.

The root retains `guest-requests/journal.sqlite3` and the same `<run_uuid>/`
manifest, archive/checksum, SQL/schema comparison, canary, events, report and evidence
index as Docker. Reports label `backend: prepared-proxmox`, simulation status and
cleanup scope. Guest receipts remain under `/var/lib/rehearsal/exercise/request-*.json`.
No raw SSH/native stderr, key contents, environment or credential text is persisted.
These are protected local operational artifacts, not public CI upload material.
Use the same explicit manual seven-day dump/30-day report review policy; no sweeper
or quota enforcement is implemented. Never remove unresolved ownership/request state.

After interruption, inspect the exact journal and retained report. A completed
receipt can resolve only its matching operation and input hash:

```bash
REHEARSAL_LIVE=1 .venv/bin/python -m rehearsal_exercise.guests reconcile --live \
  --config /protected/prepared-guests.toml --artifacts /protected/new-guest-exercise-root \
  --run-id RUN_UUID --operation OPERATION_UUID
REHEARSAL_LIVE=1 .venv/bin/python -m rehearsal_exercise.guests cleanup --live \
  --config /protected/prepared-guests.toml --artifacts /protected/new-guest-exercise-root \
  --run-id RUN_UUID
```

Reconciliation never reruns the recovery or resumes its monotonic interval. The
exit status continues to reflect the retained exercise outcome; inspect the exact
operation record for reconciliation status. Missing receipts, expired preparation
leases, changed configuration or state loss require separate operator reconciliation;
do not delete owner files, recreate journals, force cleanup or retry provisioning.
An explicit cleanup preserves the original failure/cancellation and reports pending
work. Prepared VMs/disks and database contents are retained, not ordinary disposable
Docker resources. A new exercise requires fresh preparation/empty databases; nothing
silently drops data or restarts PostgreSQL after cleanup.

The metric remains **measured exercise recovery duration**, starting before restore
guest readiness and ending after SQL/schema/API verification plus the distinct
canary. Already completed guest allocation/boot is excluded and stated in reports.
It is not comparable to a full VM recovery interval or a production RTO/RPO.

## Separately authorizable live-validation procedure

No step below is authorized or executed by this development task.

1. **Bound the host investigation first.** The supplied faults occurred close to
   nested-start timestamps. Root cause remains unresolved; one vCPU did not prevent
   the later fault. Kernel/component changes have not established a fix without a
   controlled retest. Have the host operator retain current kernel/component identity,
   clock-correlation evidence and a fresh host-log capture outside the disposable VM.
   Do not describe nested virtualization as the established cause or propose a CPU
   change as a demonstrated remedy.
2. **Ask for one specific controlled boot decision.** Name the guest, existing
   resource ownership, current configuration, fresh capacity/isolation checks,
   authorized actor, one-attempt limit, observation window and safe abort/stop
   actions. Existing unresolved operations must remain protected until explicitly
   reconciled with adequate evidence. Do not evade them with a new journal, rewrite
   historical outcomes, or repeat exhausted task searches without new evidence.
   No import, expiry renewal or CPU/RAM/network change is implicit in that decision.
3. **Capture, do not infer.** During an authorized attempt retain journalled HTTP
   request timings, returned UPID/provenance and terminal task status, actual guest
   identity/readiness and independently collected host evidence. API access loss,
   a host fault or missed deadline stops further mutations; preserve uncertainty and
   disks. A running GUI/listener alone is not boot proof. A clean retest is one
   observation, not established root-cause resolution.
4. **Authorize application prerequisites separately.** Only after boot, isolation
   and owned stop/cleanup gates are proven should an operator authorize preparing
   the source/restore pair and a two-running-guest capacity budget. The current
   ceiling remains one. Verify the exact prepared bindings, release/host-key pins,
   dedicated cluster/roles, receipt times, grants and current connectivity before
   allowing the application exercise. Do not alter VM 9000 or the deployed controller
   as a shortcut to these prerequisites.
5. **One success, then one bounded negative on fresh preparation.** Run the command
   above, independently inspect all retained hashes, exact recovered records, native
   constraints, restored API/canary, source unavailability and lease cleanup. Retain
   prepared guests/disks for review. If approved, use a fresh pair for the altered-field
   case and require a failed recovery report before the canary, with owned cleanup.
   Admit no further attempts until unexpected outcomes are reconciled.

**The next operator decision is whether to authorize that single controlled boot
retest under a named evidence/abort plan.** It is not permission to run this guest
exercise, change allocations or assume the host fault has been fixed.

The [one-boot operator runbook](controlled-boot-retest.md) now supplies the dated
read-only VM-9000 snapshot, exact retained operation identity, expiry/archival gates,
host capture commands and bounded start/abort/end-state procedure. It remains
unexecuted; the one-running-guest ceiling and this adapter's separate two-guest
admission gate remain unchanged.
