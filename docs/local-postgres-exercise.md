# Local PostgreSQL application recovery

This implemented development exercise runs entirely on dev01 using Docker. It is
independent of the Proxmox provider, controller, credentials and VM 9000. The
application, intended-input generator and SQL/HTTP verification have no guest or
Docker dependency; only `rehearsal_exercise.docker` and the local runner select
Docker as the execution transport. Guest deployment remains future work.

## Prerequisites and versions

Use Linux x86_64, Python 3.12, a project venv and permission to use the **local**
Docker Engine socket `/var/run/docker.sock`. Remote Docker contexts are deliberately
ignored. There is no daemon installation/configuration or host firewall setup in
these commands. Compose support is inspected and recorded, but Compose is not
required: the runner uses the Docker CLI to retain exact resource identities.

Allow at least 3 GiB free disk for images/build cache/evidence and a 2 GiB Docker
memory budget. The tiny dataset uses two database containers capped at 384 MiB,
two API containers capped at 128 MiB, and independent database volumes. Only one
database/API pair runs during verification. Images/builds are much larger than
the dataset. Preflight checks filesystem space and engine memory; these are
admission estimates, not a disk quota or a performance guarantee. Check other
workloads and current free RAM before running on a busy host.

[images.toml](../src/rehearsal_exercise/images.toml) pins these official images by
digest, with the Debian suite explicitly selected:

| Image | Pinned digest |
| --- | --- |
| `postgres:18.7-bookworm` | `sha256:ece55f7868da684e400f82f1030a050718adbdd65c23aa500c486f6e2950dc0f` |
| `python:3.12.16-slim-bookworm` | `sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df` |

PostgreSQL 18 is [supported upstream](https://www.postgresql.org/support/versioning/).
The same server image supplies both native tools. The runner records actual
server, `pg_dump`, `pg_restore`, Python, Psycopg, libpq and Docker versions, the
built application image ID, and SHA-256 of workload/verifier/build inputs, including
uncommitted changes. Update image pins and version assertions together, then
repeat the exercise; mutable tags are not a reproducibility boundary.

The optional `exercise` dependency is **Psycopg 3.3.9**, with its binary wheel and
typing-extensions hash pinned for Python 3.12/Linux x86_64. It supplies explicit
SQL transactions without an ORM or system libpq installation. Psycopg documents
[binary installation and supported platforms](https://www.psycopg.org/psycopg3/docs/basic/install.html).
The binary package bundles client libraries, which need deliberate dependency
updates. Python's standard HTTP server is sufficient for this bounded synthetic
exercise; production HTTP hosting is outside this milestone. No framework,
worker, queue, authentication, UI or Actions was added. Inventory still requires
only its original HTTPX runtime dependencies.

## Exact commands

From the checkout, install only into the project venv:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-index --no-build-isolation --no-deps -e .
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests tools
.venv/bin/ruff format --check src tests tools

# Read-only checks; do not delete or prune existing resources.
docker version
docker compose version
docker ps -a
docker volume ls
docker network ls
docker system df
df -h . /var/lib/docker
free -m

# Both opt-ins are mandatory; run creates a fresh UUIDv4 and prints its report path.
REHEARSAL_LIVE=1 .venv/bin/rehearsal-exercise run --live
```

For an explicit run ID and artifact destination (outside the public checkout):

```bash
REHEARSAL_LIVE=1 .venv/bin/rehearsal-exercise \
  --artifacts "$HOME/.local/state/rehearsal-exercise" \
  run --live --run-id "$(.venv/bin/python -c 'import uuid; print(uuid.uuid4())')"
```

`--project /absolute/checkout` selects the build context when invoked elsewhere.
The host downloads hash-checked wheels into a temporary allowlisted context with
the application, exercise modules, Dockerfile and dependency lock. The image build
uses `--network none` and installs from those wheels with `--no-index`. Build
containers need no DNS or egress. No lab configuration, credentials or retained
dumps enter the context or the build daemon.

Ordinary tests block sockets/DNS **and Docker CLI access**. Explicit Docker
integration tests create their own UUIDs and always attempt owned cleanup:

```bash
REHEARSAL_LIVE=1 .venv/bin/python -m pytest -q \
  --docker-exercise -m docker tests/test_exercise_docker.py
```

These run a complete success and an altered-record negative exercise. For a
retained diagnostic run, select one bounded fault; its expected CLI exit is 1:

```bash
REHEARSAL_LIVE=1 .venv/bin/rehearsal-exercise run --live --fault changed-record
# Alternatives: missing-record, corrupt-backup
```

The corrupt-backup case truncates a **separate copy**, retaining the original
successful dump and checksum; `pg_restore` must fail. No fault affects another run.

## Application and schema

`POST /orders` creates a stable UUID order with synthetic customer, SKU, quantity,
integer unit price and total in cents, and an explicitly zoned business timestamp.
An identical retry returns the same order (200); a new order returns 201; conflicting
fields or invalid input return 400. `GET /orders/{id}` reads it, returning 404 for
an unknown ID. `/health/live` tests only the HTTP process; `/health/ready` requires
database connectivity and schema version 1, and returns 503 otherwise. Neither
claims a worker is progressing.

[schema.sql](../src/rehearsal_orders/schema.sql) is explicit version-1 initialization:
run it **once on a fresh source** with `psql -X -v ON_ERROR_STOP=1 -f ...`.
The schema-version table, primary key, field constraints, non-null columns and
customer index are included in the logical backup. There is no sequence because
IDs are supplied UUIDs. The restore target receives no schema initialization;
its empty database is populated exclusively by the dump. Future schema changes
need a separately numbered migration and verifier contract.

To use the application outside Docker, provide an initialized PostgreSQL database,
an `order_app` login with `SELECT` on `schema_version`, `SELECT, INSERT` on `orders`
and schema usage, then run:

```bash
.venv/bin/python -m pip install --require-hashes -r requirements-exercise.lock
# Set PGHOST, PGPORT, PGDATABASE, PGUSER and ORDER_PASSWORD_FILE to your local
# synthetic database and protected credential reference; do not put a DSN in Git.
.venv/bin/python -m rehearsal_orders --bind 127.0.0.1 --port 8080
```

`rehearsal_orders.domain` is pure business logic. The independent manifest and
comparison functions in `rehearsal_exercise.manifest` do not import it. The verifier
queries selected fields directly with SQL and checks API results separately.

## Isolation, backup and acceptance

Every run uses a UUIDv4, a persistent local installation UUID, and a fresh resource
UUID and nonce for each image/container/network/volume. Source and restore each
have their own **internal network, database container, PostgreSQL cluster system
identifier and named volume**. Both databases use the same private alias `db`,
resolved on separate networks. The restore API has only the restore network.
No host ports are published. HTTP requests use `docker exec` and API container
loopback; PostgreSQL has no host publication. Containers use non-root users,
capabilities dropped, no-new-privileges, memory/CPU/PID limits, read-only roots and
small temporary filesystems. There are no privileged containers, host networking
or Docker-socket mounts. No lab settings are loaded.

The runner first saves a deterministic intended manifest for 100 orders, including
per-record hashes and an aggregate. It seeds through the API, verifies acknowledged
fields and compares source SQL and HTTP reads against that independent manifest.
It stops the source API, disables the application database login, terminates any
remaining app sessions and checks there are no other database sessions. This is
the recorded frozen-write boundary for this dedicated synthetic environment.

`pg_dump --format=custom --no-owner --no-privileges` writes a partial host artifact,
then publishes the completed archive only after command success and fsync. A
checksum and `pg_restore --list` sanity check follow. A checksum/listing alone
does not prove recovery. The source database is stopped, with its data intact,
before target allocation. Native tools use the private local administrative
socket; application connections use a limited login and a generated credential
file. Administrator and application passwords are generated independently; the
API never mounts the administrator credential. Source and restore also have
different credentials. Cluster-global roles are recreated independently, because logical dumps
do not include them. See [pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html).

The target starts empty on separate storage. Before restore, the runner checks
that container, volume, network and cluster identities differ and that the source
is stopped. `pg_restore --exit-on-error --single-transaction --no-owner --no-privileges`
restores the dump; application grants are then applied. See
[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).

Verification checks exact record IDs and **every defined order field**, reporting
missing, extra, changed and duplicate IDs. It checks schema version, exact columns,
types, nullability, tables, indexes and constraint identities, then tests eight
constraint rejections in rollback-only transactions. HTTP reads through the restored
API must match all 100 expected orders. Only after those comparisons pass does
the API create/read/retry a separate `POST-RESTORE` canary; SQL must contain exactly
the recovered set plus that canary. A failed phase prevents success and prevents
later verification/canary phases from running.

The metric is **measured exercise recovery duration**. It starts immediately
before allocating the restore network, volume and database instance, and ends
after recovered SQL/schema/API checks and the separate post-restore write/read.
It includes target allocation, readiness and restore, but excludes image
preparation, source preparation, backup and cleanup. Phase durations use
`time.monotonic()` within one process, with UTC timestamps for correlation.
Interrupted timings remain incomplete; cleanup cannot resume a recovery timer.
These observations are not a production RTO or RPO. Concurrent-write consistency,
PITR, incremental recovery, VM recovery, guest isolation and host fault tolerance
remain unproven and outside this milestone.

## Evidence, inspection, cleanup and retention

Default root: `~/.local/state/rehearsal-exercise`, mode 0700, outside the repository.
Each `<run_uuid>/` retains `manifest.json`, `backup.dump` (or `backup.partial` after
failure), `backup-checksum.json`, source/restore verification and schema evidence,
separate canary input, append-only `events.jsonl`, atomic `state.json`, `report.json`,
`report.md` and a file-size/SHA-256 `evidence-index.json`. Reports include versions,
phase durations, UTC boundaries, checks, failure phase and cleanup disposition.
The reports are sanitized local artifacts; raw stderr, DSNs, environment,
credential contents and arbitrary exception text are never persisted. Native
command diagnostics are fixed operation names, exit codes and timeouts. Container
log persistence is disabled. Generated credentials are deleted after cleanup;
they are not included in the evidence index.

```bash
# Offline evidence summary (exit reflects original run outcome).
.venv/bin/rehearsal-exercise status RUN_UUID
python3 -m json.tool "$HOME/.local/state/rehearsal-exercise/RUN_UUID/report.json"

# Retry cleanup, under the same installation lock. Original failure stays failed.
REHEARSAL_LIVE=1 .venv/bin/rehearsal-exercise cleanup RUN_UUID --live
```

Creation intent and labels are durable before Docker mutations. Exact immutable
IDs are saved after creation; volumes additionally retain `CreatedAt` and their
random ownership nonce because Docker volumes have no independent immutable ID.
Cleanup rechecks installation/run/resource/nonce/role, exact ID and creation
generation before removing anything, then confirms absence. It removes containers
first, then volumes/networks and the run's application image. It never prunes or
selects ownership by a prefix. Shared base images and build cache are retained.
Unrelated resources and mismatched metadata are left in place as cleanup pending.
An active run and cleanup cannot hold the same evidence-root lock concurrently.

SIGINT/SIGTERM produce cancelled evidence and attempt cleanup. After SIGKILL or a
host crash, use `status`, inspect `state.json`/events, then `cleanup`. An uncertain
creation is reconciled by its exact journalled name and full live labels; it is
never retried. If an intent has no observable resource, it remains pending rather
than assuming a delayed daemon operation cannot finish. Inspect the local daemon
and retain that state for manual reconciliation; do not edit away ownership guards
or run a global prune. A new execution always needs a new run ID. Existing run
directories/artifacts are never silently overwritten. Cleanup updates reports and
the evidence index without erasing the original exercise result.

**Retention is manual and explicit:** synthetic completed/partial/corrupt dumps
are retained after cleanup for diagnosis, with a suggested seven-day review;
reports/manifests/events have a suggested 30-day review. No automatic expiry,
quota enforcement, backup export or sweeper is implemented. Delete only specific
reviewed artifact files after cleanup is complete; preserve state/ownership
evidence for any pending cleanup. Do not commit dumps or entire run directories.
The file index detects accidental changes, not hostile tampering. Everything
still shares dev01's physical failure domain.

## Verified local evidence — 13 November 2026

Verified facts from real dev01 Docker execution, not fixtures: Engine 29.7.2,
Compose 5.4.0 (inspected, not used), two CPUs, approximately 3.8 GiB engine memory
and 73+ GiB free filesystem space. No containers were present initially. The three
pre-existing anonymous volumes and default networks were unchanged after cleanup.
There was no Proxmox/controller access or modification.

| Run UUID | Actual result | Cleanup |
| --- | --- | --- |
| `a0250d1d-2141-49ed-92a7-f8a8e1d5f47d` | Passed: all 100 recovered orders, schema/constraint probes, all 100 API reads, then separate canary (101 exact SQL records) | Complete |
| `b92d33bf-764b-4ccb-94d8-3de83bd23140` | Expected failure: changed `customer` on ID `00000000-0000-0000-0000-000000000001`; row count stayed 100; canary was not attempted | Complete |

The successful run's measured exercise recovery duration was **30.169877 seconds**,
from **18:02:15.473289 UTC** (before target allocation) through **18:02:45.643156 UTC**
(all declared checks including canary complete). Native restore took 0.455 seconds;
target preparation 13.863 seconds; recovered SQL/schema verification 1.454 seconds;
restored application/read verification 12.645 seconds; separate canary 1.122 seconds.
These phase durations and the primary duration come from the process monotonic
clock; UTC is for correlation. The backup took 0.435 seconds, outside recovery timing.

The retained backup is **4,588 bytes**, SHA-256
`de3d922915b0e5a26cce5f780e06d082b0717de066d85f37a9258ba29f3961a4`.
Actual database/native-tool version: **18.7 (Debian 18.7-1.pgdg12+2)**. Actual
application: **Python 3.12.16, Psycopg 3.3.9, bundled libpq 18.6**. The run report
also retains image IDs/digests, manifest checksum and exact source input hashes.

Both runs retain artifacts at `~/.local/state/rehearsal-exercise/<run_uuid>/`.
Every indexed artifact's size and SHA-256, independent manifest, distinct cluster/
container/network/storage identities, check results and credential removal were
verified after cleanup. No exercise containers, volumes, networks or application
image tags remain. Pulled base images and Docker build cache remain intentionally.

Three earlier development attempts remain failed in their original reports:
`422a13f7-5c88-40f2-a7aa-1ee5d10f44d9` (build-container DNS),
`36461286-8bcb-4aeb-b8b6-42192d057631` (Docker missing-network diagnostic handling),
and `9d89d49c-0c91-4aa3-bfb9-f4fca2a47a01` (PostgreSQL 18 explicitly catalogs NOT
NULL constraints). Those issues were fixed without daemon/network changes or
weakening verification. Their resource cleanup is complete; the first two retain
explicit reconciliation events proving respectively a completed failed build with
no image, and no submitted network creation. Their artifacts were also checked.

Local validation: **316 offline tests passed; two Docker integration cases skipped
by default**, Ruff lint/format and `pip check` passed. The successful and negative
CLI exercises above are the actual Docker evidence, separate from unit tests.
The separately opted-in Docker test command also passed **2 integration tests**
against the final source. Repeat success `918d9000-1a76-4213-8b6c-22a36c5a27a1`
measured **32.627497 seconds** (18:10:12.290231–18:10:44.917717 UTC); altered-record
run `8897df10-9c43-43f8-95c2-e11cf89ef1a3` failed as intended. Both cleaned up.
Their reports are retained below
`~/.local/state/rehearsal-docker-tests-20261113-cfae12/`, under the corresponding
test directory's `evidence/<run_uuid>/`. This repeated local timing includes test
and host scheduling variability and is not a performance benchmark. Source/wheel
builds and packaged-resource checks also passed from a staged copy outside Git.

A final repeat after separating administrator/application credentials passed both
Docker integration cases again. Successful run
`d5b513b6-e2fb-4ca2-8a0c-5e1f69d12e81` measured **29.410771 seconds**
(18:16:30.535636–18:16:59.946396 UTC); backup 4,588 bytes, SHA-256
`e1ffd340412bb93628281fc2442ed5731a8daa923ee010d06fec3c0adf494e85`.
Negative run `bc329004-907a-4bb5-a644-dfbc520916da` detected the altered customer
and skipped the canary. Both cleaned up and retain reports under
`~/.local/state/rehearsal-docker-tests-20261113-cfae13/`, with the same test-directory
layout. The final offline suite passes 316 tests with both Docker cases skipped
by default. The ordinary unit suite never uses a PostgreSQL or Docker connection.

No guest boot, production consistency/RTO/RPO, concurrent-write recovery, PITR or
incremental recovery claim follows from these observations.

## Review before first recovery commit

13 November 2026: the initial workspace and retained reports were independently
checked against the handoff. The review preserves fractional business timestamps,
rejects numeric type changes, and checks exact constraint/index definitions plus
constraint validation/enforcement. Docker CLI failure alone no longer proves an
absent creation is resolved; ambiguous outcomes remain pending. Image tag
collisions fail before build. Status on missing evidence creates no directories,
and unexpected HTTP server exceptions produce a fixed diagnostic.

Validation: 325 offline tests and both explicit real Docker cases passed, plus
Ruff/dependency checks and `.venv/bin/python tools/package_smoke.py`. Review Docker
evidence is retained below `~/.local/state/rehearsal-reviewed-20261113-e118/`.
These are local checks; they establish no new lab observation or host-fault cause.
