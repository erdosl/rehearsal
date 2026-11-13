# Changelog

## Public CI publication and verification — 13 November 2026

Resolve GH007 with explicitly authorized email-only rewriting of five unpublished
commits. Obtain the noreply address from GitHub's signed initial commit/account
mapping, configure it only for this repository, retain a local-only backup and
full old-to-new mapping, and verify identical trees/messages/order/dates. Preserve
other identities, published history, global configuration and privacy settings.
Publish normally without force; no local suite rerun solely for metadata changes.

GitHub-hosted run **43513561091**, SHA `d73652c87921af007b99192d2de7525898369671`,
passed both offline and Docker jobs. Real recovery verified 100 orders, SQL/schema/
restored API and the separate canary; altered-customer verification failed as
intended at the same row count, with its test passing. Both run cleanups and the
independent cleanup step passed. Downloaded artifact ZIPs/digests and all JSON fields
were inspected: only the three intended metadata files, no dumps/credentials/raw
reports. See [exact mapping, job links and evidence](docs/ci.md#verified-hosted-execution-13-november-2026).
No lab access, mutation, renewal, journal change, VM start or deployment occurred.

## Controlled boot retest preparation — 13 November 2026

Collect bounded read-only PVE/controller state through verified existing SSH and
the original verified-TLS inventory. Confirm VM 9000 stopped/disconnected, exact
ownership/volumes, healthy reported pool state, loaded firewall guards and the
unchanged uncertain historical operation. Bootstrap expiry has passed; controller
NTP reports unsynchronized. Journal hash/mtime remain unchanged. No host access,
VM power action, credential renewal, state modification or deployment occurred.

Add a concrete separately authorizable one-boot procedure with fresh host capacity/
health and clock gates, expiry-only renewal, evidence-preserving historical archival,
passive serial proof, one start, bounded exact-task reconciliation, explicit abort/
owned end-state authority and private evidence retention. Preserve the one-guest
ceiling and unresolved root cause; neither CPU count nor maintenance proves a fix.

The authorized publication attempt was rejected by GitHub GH007 email privacy;
reviewed local commits/history/settings remain intact and no hosted run is claimed.
Validation: 354 offline tests passed; Ruff lint/format, dependency verification,
package smoke, actionlint 1.7.12, local links and runbook shell/Python/JSON syntax
checks passed. Future mutation/capture snippets were not executed against the lab.

## Prepared Proxmox guests — offline integration slice

Share the actual recovery orchestration, manifest, SQL/schema/API verifier, native
archive checks, canary and evidence between Docker and prepared guest transport.
Add strict protected bindings, verified-TLS read-only Proxmox admission, pinned
SSH, machine/release checks, guest leases, checksummed archive transfer and durable
command receipts. Reuse the existing SQLite request journal and exact recorded-UPID
reconciler; preserve ambiguity and reject all Proxmox mutation calls. Cleanup stops
only leased services and retains prepared VMs/disks and observer evidence.

Add offline success/failure contracts and a concrete separately authorizable live
procedure. Guest tests simulate protocol responses, not real PostgreSQL/SSH/Proxmox
execution. No live retest, provisioning, VM 9000 change, expired-token renewal,
allocation/network/firewall change or controller deployment occurred. The host
faults remain close in time to starts with unresolved root cause; a single vCPU did
not prevent the later fault, and subsequent maintenance has not established a fix.
See [implementation and remaining live gates](docs/prepared-proxmox-exercise.md).

Final local validation: **354 offline tests**, including **26 guest contracts**;
two real Docker cases after the shared-runner changes; Ruff, dependency checks,
configuration validation, actionlint and package/install/resource smoke checks
passed. These results establish no live guest/SSH/Proxmox or GitHub-hosted success.

## Public CI — local implementation, not yet run on GitHub

Add separate Ubuntu-hosted offline and Docker recovery jobs with SHA-pinned
official actions, read-only repository permissions, bounded concurrency/timeouts,
best-effort owned cleanup and seven-day metadata artifacts. Public PR jobs have no
lab credentials or self-hosted runner. Export only an allowlisted projection;
backups, credentials, connection details and raw reports/logs are not uploaded.
Add injection/numeric-boundary tests and locally validate the workflow with
checksum-verified actionlint 1.7.12 and its underlying job commands. See
[CI runbook](docs/ci.md). No push or repository-settings change; remote execution
is untested.

## Recovery milestone review — 13 November 2026

Reviewed source/target separation, independent intended input, SQL/schema/API
checks, credentials, interruption, retained artifacts and packaging before the
first recovery commit. Fix subsecond timestamp loss and numeric-type equality in
verification; validate constraint definitions/enforcement and index definitions.
Keep nonzero Docker creation outcomes unresolved until reconciled; refuse image
tag collisions. Missing status paths no longer create run directories. Suppress
arbitrary socketserver exception details. Add targeted regressions and a repeatable
offline `tools/package_smoke.py` command.

The reported 316-test baseline and retained real Docker reports/checksums were
verified. Review validation: 325 offline tests, two real Docker integration cases,
Ruff, dependency checks and staged package/install smoke checks passed locally.
No lab access or deployment; host faults remain temporally associated with starts,
with root cause unresolved and no established fix after component/kernel changes.

## Unreleased — 13 November 2026 local PostgreSQL exercise

- Add a synchronous synthetic-order API, explicit v1 SQL initialization, database
  readiness separate from HTTP liveness, stable-ID create/read and safe retries.
- Add an independent intended-input manifest, exact SQL/API comparisons, schema
  and constraint checks, and a separately retained post-restore write/read canary.
- Add a dedicated dev01 Docker CLI workflow with pinned PostgreSQL 18.7 and Python
  3.12.16 images, optional hash-locked Psycopg 3.3.9, separate internal source/restore
  networks and volumes, frozen writes, native custom-format backup and transactional
  restore. Host wheel downloads precede a build with networking disabled.
- Retain checksummed backups and sanitized run evidence outside the repository.
  Journal installation/run/resource UUIDs and nonces before mutations; check live
  identities before cleanup, preserve ambiguous creation outcomes, serialize cleanup
  with execution, and refuse to overwrite existing run artifacts. Interrupted runs
  can reconcile cleanup but cannot silently restart recovery or its timer.
- Add 44 offline safety/application/verifier tests and two explicitly gated Docker
  integration cases. Inventory runtime dependencies, deployed controller, lab
  infrastructure, expired credentials, VM 9000 and LICENSE are unchanged.

Validation on dev01: **316 offline tests passed, 2 Docker tests skipped by default**;
Ruff lint/format and dependency checks passed. A real local CLI exercise recovered
all 100 orders, passed SQL/schema/API checks and the distinct canary, and completed
owned cleanup. Its measured exercise recovery duration was **30.17 seconds**;
backup **4,588 bytes**, SHA-256 and full phase boundaries retained. A second real
CLI exercise changed a restored customer field while preserving the row count:
verification failed as intended before the canary, and cleanup completed.
All retained artifact checksums were independently rechecked. Earlier development
attempts remain failed in their reports, with cleanup reconciled/completed.
The explicit Docker integration command also passed **2 tests** against the final
source (success plus altered-record rejection), with owned cleanup complete; its
successful repeat measured **32.63 seconds**. Ordinary tests additionally block
Psycopg's C-level network entry point. Wheel/source builds and packaged-resource
checks passed from a staged copy outside the repository.
The final credential-separation repeat also passed both integration cases; its
successful recovery measured **29.41 seconds**. Administrator credentials are
generated separately and never mounted into the application container.
See the [runbook and dated evidence](docs/local-postgres-exercise.md).

This proves only the frozen synthetic local logical-recovery workflow. It does not
prove guest execution, production RTO/RPO, concurrent-write consistency, PITR,
incremental recovery or host fault tolerance. No commits, pushes or deployment.

## Unreleased — 13 November 2026 offline evidence review

These source changes are **not deployed** and have **not been validated through
a live nested start**. Deployed inventory 0.2.0 and the controller sidecar remain
unchanged. No lab requests, infrastructure changes, credential renewal or live
controller-state edits were performed. The recorded bootstrap expiry has passed.

- Add append-only operation/request correlation, UTC and local monotonic timing,
  HTTP status, safe transport categories and explicit UPID provenance.
- Recover a response UPID retained before a crash without repeating the mutation;
  preserve leases and use a fresh timing context after restart. Require bounded
  request evidence for task discovery; reject mismatched tasks and later unrelated
  tasks. Missing or conflicting evidence requires operator reconciliation.
- Preserve confirmed task failures when log retrieval fails. Missing task history
  or exit status remains uncertain. Offline status separates controller state
  from task-outcome evidence; current resource state never proves historical task
  success. Operator terminal resolutions require an explicit result/reason and
  append an auditable transition.
- Restrict requests to the configured API origin, stream responses with a size
  limit, retain HTTP status on partial-body transport failures, and remove unsafe
  transport exception context. Redact credential fields, recognizable credential
  text and private-key log groups; reject credential-bearing mutation metadata
  before journaling.
- Validate existing version-1 journal shape and installation identity before
  initialization writes. Preserve historical rows and provenance gaps; reject
  incompatible journals without automatic repair or identity replacement.
- Retain the [supplied investigation handoff](docs/investigation-2026-11-13.md),
  separating reported fault evidence from hypotheses and unverified remedies.

Validation: **272 network-blocked tests passed**, plus Ruff lint/format,
dependency checks, fixture CLI checks and wheel/source builds from a staged copy.
Source archives include the test network guard and referenced examples; generated
packages remain outside the repository. See [development validation](docs/development.md#tests-and-packaging) and
the [evidence contract](docs/supervised-build.md#offline-request-evidence-13-november-2026).
Live nested validation remains blocked by the unresolved host fault and requires
a separate explicit operator decision. Local evidence is protected diagnostic
data; arbitrary unlabelled external text is not a safe public report format.
