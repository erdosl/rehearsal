# Rehearsal

Rehearsal is a planned infrastructure testing and recovery rehearsal platform. It will run repeatable exercises to show whether a small application can be deployed, upgraded, backed up and recovered, with evidence of application behaviour and data integrity.

This is a portfolio and learning project for Linux/platform engineering: Proxmox, Python automation, PostgreSQL recovery, GitHub Actions and operational troubleshooting. Understandable engineering and reproducible results take priority over scale.

## Status

The local [PostgreSQL application recovery exercise](docs/local-postgres-exercise.md)
implements a synthetic order API, deterministic independent manifest, native
backup, separate Docker restore instance, SQL/schema/API verification, a separate
post-restore canary and owned cleanup. It runs on dev01 without Proxmox or controller
changes. See the runbook for exact opt-ins, image pins, retained artifacts and
measured exercise recovery duration boundaries. Guest deployment, worker and
infrastructure recovery remain future work.

Public [GitHub-hosted CI](docs/ci.md) and the
[prepared Proxmox guest transport](docs/prepared-proxmox-exercise.md) are now
implemented locally. The latter shares the recovery workflow but has only offline
contract validation; guest preparation/power/provisioning and live acceptance are
separate gates. CI has not run on GitHub. No lab deployment or VM mutation occurred.

**13 November 2026:** the [investigation handoff](docs/investigation-2026-11-13.md)
supersedes the historical snapshot below. Supplied host evidence establishes two
VirtualBox NULL-pointer faults; root cause and a fix remain unresolved. VM 9000
was last observed stopped/disconnected, with resources retained and historical
task outcomes unavailable. Live nested-start validation requires a separate
explicit operator decision. Local development adds append-only request timing,
HTTP/transport and UPID-provenance evidence with offline tests; these changes have
not been deployed. The recorded bootstrap expiry, 13 November at 15:08:20 UTC, has
passed. No credentials or infrastructure were changed during this development.
The subsequent [offline review and fixes](CHANGELOG.md) cover crash recovery,
credential handling, journal compatibility and explicit outcome provenance.

**Historical deployment/build snapshot, 12 November:**

The **read-only inventory slice is deployed**, version 0.2.0, as of **12 November 2026**, with real verified-TLS runs and no fixture fallback. Separate [supervised VM 9000 tooling](docs/supervised-build.md) provides the durable journal, bounded reconciliation and ownership checks. After the initial start lost PVE access, an operator restart with **one vCPU / 16 GB RAM** allowed read-only reconciliation of the existing stopped guest. **One distinct new start again lost PVE responsiveness; guest boot and shutdown remain unverified.** The attempt was halted, its sole NIC never released, and no uncertain resource deleted. The journal retains the new UPID for reconciliation. The operator's single-vCPU pattern is provisional, not a confirmed cause or a validated fix for this workload. Executor, application and recovery remain future work.

Development continues on `dev01` using a project `.venv`. Inventory 0.2.0 remains at `/opt/rehearsal/releases/0.2.0` on `rehearsal01`, verified `.83/24`, with unchanged credential/configuration. The last successful real inventory at **20:07 UTC** saw active **90 GiB rehearsal-lvm**, six audit-visible interfaces and one stopped VM. After the new start, inventory failed with API timeout, exit 3. Inventory scope was not broadened. Nested KVM/Ubuntu execution and all guest packet checks remain unverified.

## Try the offline CLI

From the project directory, with Python 3.12 and venv support:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-index --no-build-isolation --no-deps -e .
.venv/bin/rehearsal --version
.venv/bin/rehearsal config validate --config examples/rehearsal.toml
.venv/bin/rehearsal inventory --config examples/rehearsal.toml --backend fixture
.venv/bin/rehearsal inventory --config examples/rehearsal.toml --backend fixture --format json
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests tools
.venv/bin/ruff format --check src tests tools
```

Only initial installation needs a package index or cached wheels. **HTTPX is the single direct inventory runtime dependency**, providing HTTPS, explicit timeouts and mock transports; runtime/development dependencies have separate hashed locks for Linux x86_64/Python 3.12. The development lock also installs optional Psycopg for the local order application; inventory's runtime lock is unchanged. Fixture output remains **SIMULATED**, including `"simulated": true` in JSON. It is not an inspection of `pve01`. There is no automatic backend fallback.

See [development and usage](docs/development.md) for configuration, fixtures, checks and packaging. The [live inventory runbook](docs/live-inventory.md) specifies PVE 9.2.2 ACLs, token privilege separation, certificate trust and independent controller deployment. Live access requires `--backend live`, `--live` and `REHEARSAL_LIVE=1`; configuration validation and fixture commands remain offline.

## Intended workflow

This remains the planned guest workflow. The independent local Docker slice is
implemented separately; it does not satisfy the nested-guest acceptance gates.

1. Validate configuration and check capacity, API permissions and isolation.
2. Allocate an isolated, disposable environment through the Proxmox API.
3. Deploy an order API, a separate worker and PostgreSQL; seed deterministic data.
4. Run a selected deployment, recovery or failure exercise.
5. Verify HTTP behaviour, worker progress and database records from the controller.
6. Retain logs, task identifiers, timings and a structured report outside test VMs.
7. Delete only resources proven to belong to that run, including after interruption.

The local version of the first recovery exercise now takes a PostgreSQL logical
backup, stops the source, restores into a separate isolated target and compares
recovered records with an independently retained manifest. Its real local validation
recovered 100 orders and passed the separate canary; measured exercise recovery
duration was 30.17 seconds, with owned cleanup complete. An altered-field negative
case failed verification as intended. The [runbook](docs/local-postgres-exercise.md)
records boundaries and limitations. Guest deployment, VM backup/restore and
Proxmox Backup Server (PBS) are separate later work.

## Proposed deployment

`dev01` is for editing, offline tests and Git operations. `rehearsal01` is installed directly in VirtualBox outside `pve01` according to the user, and its CLI deployment/access are verified. Configuration and application-specific CA are under `/etc/rehearsal`; protected reports are under `/var/lib/rehearsal/reports`. The CLI needs no application daemon; firewall persistence uses a separate oneshot unit. The supervised tool has separate protected SQLite state; a systemd executor remains future work. Both VMs still depend on the same physical host.

Use `rehearsal-lvm` for planned template and test disks. The [first nested guest/template plan](docs/nested-guest.md) selects Ubuntu 24.04, 1 vCPU, 2 GiB RAM and a 12 GiB disk, replacing the earlier 6 GiB estimate. The 90 GiB pool budgets 18 GiB reserve, 36 GiB for template plus two full clones and 2 GiB auxiliary allowance, leaving 34 GiB unassigned. The VG's separate 8 GiB unallocated space is not pool capacity. **The initial physical backing-capacity gate for `pve01` is satisfied**: user-supplied host evidence confirms both dynamic VDIs under `/mnt/ssd`, with **636 GB available**. Continue monitoring actual host space as they grow; `dev01` and `rehearsal01` disk locations remain unverified. Initially allow one run and one running nested guest, with two workload VMs only after later isolation/capacity validation.

The operator completed `REHEARSAL-TEST`: PVE vmbr1/enp0s16 and controller enp0s9 at `10.77.0.1/24`. [Platform reboot persistence](docs/firewall-isolation.md) passed with actual legacy hooks and both guards, fresh management/API access and routing forwarding disabled. Fresh supplied host capacity later passed admission; only VM 9000 and its two owned volumes were created. Exact guest rules/allow tuples were installed while stopped, with automatic rollback armed before each guard update and canceled after fresh checks. **Guest packet enforcement remains untested**, and PVE's current state is unreadable after the new start following operator recovery. Controller filtering/access remain verified. Existing inventory credentials/ACLs/release are preserved; bootstrap expiry is **2026-11-13 15:08:20 UTC**. [Resource/task IDs, deployment and recovery gate](docs/supervised-build.md) are recorded separately.

## Development and delivery order

1. Local Python scaffold, validated configuration and read-only inventory, tested with fixtures.
2. Install the controller on `rehearsal01`; explicitly enable a live inventory check.
3. Add disposable VM provisioning, task reconciliation and reliable cleanup.
4. Add the test application and independently verified PostgreSQL recovery.
5. Add ordinary GitHub CI, trusted lab integration and richer failure exercises.

Offline tests run with synthetic credentials and mock transport, without Proxmox or lab connectivity, and block network calls. Fixture commands do not load API credentials. Actual live results require explicit opt-ins plus the runbook's deployment, connectivity, trust and read-only token prerequisites.

## Design documents

- [Development rules and boundaries](AGENTS.md)
- [Public GitHub-hosted CI, pins and sanitized artifacts](docs/ci.md)
- [Prepared Proxmox guest integration and bounded live-validation plan](docs/prepared-proxmox-exercise.md)
- [Environment evidence, supplied information and unknowns](docs/environment.md)
- [Architecture, isolation, recovery evidence and CI trust](docs/architecture.md)
- [Implementation milestones and acceptance criteria](docs/implementation-plan.md)
- [First nested Ubuntu guest, template, permissions and cleanup plan](docs/nested-guest.md)
- [Supervised VM 9000 tooling, verified preparation and current admission gate](docs/supervised-build.md)
- [Effective firewall inspection, guest/controller isolation candidates and rollback](docs/firewall-isolation.md)
- [Executed controller/PVE reboot checks and repeatable procedure](docs/controller-reboot.md)
- [Decisions and tradeoffs](docs/decisions.md)

Use synthetic data only. Keep credentials, private keys, dumps and unsanitised lab artifacts out of this public repository. The project does not claim production readiness, realistic performance measurements, high availability or physical-host fault tolerance.

## Licence

[Apache License 2.0](LICENSE). The existing licence is preserved.
