# Development and CLI usage

Rehearsal 0.2.0 implements configuration checks, explicit fixture simulation and a read-only HTTPS inventory adapter. It is now deployed and live-verified on `rehearsal01`; development remains on `dev01`. It contains no provisioner, executor/service, database/recovery implementation, UI or Actions workflow. See the [verified deployment record](live-inventory.md#verified-deployment-record) for paths, scoped credentials and results.

## Setup and dependencies

Run from `~/projects/Rehearsal` with Python 3.12 and venv support:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-index --no-build-isolation --no-deps -e .
```

Venv bootstrap was verified on `dev01` with Python 3.12.3/pip 24.0. If bootstrap fails, report the specific venv/ensurepip prerequisite (`python3.12-venv` on this Ubuntu guest); do not install into system Python. Initial installation needs an approved package index or cached wheels. Application checks/tests then run offline.

HTTPX 0.28.1 is the only direct inventory runtime dependency: it supplies HTTPS,
explicit timeouts, streaming responses and [mock transport](https://www.python-httpx.org/advanced/transports/).
Its transitives are hash pinned in `requirements-runtime.lock`. The development
lock includes runtime dependencies, optional Psycopg for the order application,
pytest, Ruff, build, setuptools and their transitives. Locks target Python 3.12/Linux
x86_64. Ordinary tests need no Docker server, PostgreSQL server, GitHub authentication
or SSH. Docker integration is separately gated; see the
[local exercise runbook](local-postgres-exercise.md).

## Offline commands

```bash
.venv/bin/rehearsal --help
.venv/bin/rehearsal --version
.venv/bin/rehearsal config validate --config examples/rehearsal.toml
.venv/bin/rehearsal config validate --config examples/live.toml --format json
.venv/bin/rehearsal inventory --config examples/rehearsal.toml --backend fixture
.venv/bin/rehearsal inventory --config examples/rehearsal.toml --backend fixture --format json
.venv/bin/python -m rehearsal inventory --config examples/rehearsal.toml --backend fixture
```

Every inventory command requires `--backend fixture` or `--backend live`. There is no fallback. Fixture data and failures are visibly **SIMULATED**; JSON identifies `backend`, `simulated` and `source`. Live-adapter tests with an injected transport are also marked simulated. `--fixture` overrides only the fixture backend and is rejected with live selection.

This intentional permission failure returns exit 3 with safe JSON on stderr and no success output:

```bash
.venv/bin/rehearsal inventory --config examples/rehearsal.toml --backend fixture --fixture builtin:permission-denied --format json
```

This opt-in demonstration returns exit 2 **without loading secrets or opening a connection**:

```bash
.venv/bin/rehearsal inventory --config examples/live.toml --backend live --format json
```

An enabled live operation additionally requires both `--live` and `REHEARSAL_LIVE=1`; see the [live runbook](live-inventory.md) before enabling it. No token CLI argument is supported, and even rejected CLI argument values are not echoed. A gate failure, missing CA/token, inaccessible endpoint or API failure never switches to fixtures.

## Configuration contract

Examples: [fixture configuration](../examples/rehearsal.toml) and [live configuration](../examples/live.toml). Both contain references only, not credentials.

| Field | Rule |
| --- | --- |
| `schema_version` | Required integer `1` |
| `inventory.nodes` | Nonempty, unique node names; 1–63 ASCII letters/digits/dots/underscores/hyphens, starting with letter/digit |
| `inventory.fixture` | Required for fixture-only configuration; optional when `proxmox` exists; no implicit fixture default |
| Fixture references | `builtin:healthy`, `builtin:permission-denied` or a local JSON path; URLs unsupported |
| `proxmox.endpoint` | Required in a `proxmox` table; HTTPS origin with optional port, no credentials, query, fragment or API path |
| `proxmox.verify_tls` | Optional, defaults true; false/nonboolean values rejected |
| `proxmox.ca_file` / `token_file` | Optional local paths structurally; token required for live access; files are never opened by configuration validation |
| `connect_timeout_seconds` / `read_timeout_seconds` | In `proxmox`, defaults 3/15; finite numeric 0.1–60 seconds |
| `request_deadline_seconds` | In `proxmox`, default 30; finite numeric 0.1–120 seconds |
| `max_attempts` | In `proxmox`, default 3; integer 1–3 total attempts, not retries after an initial attempt |

Unknown fields/tables, including inline token/password values, fail. Configuration is limited to 64 KiB UTF-8 TOML, parsed with [tomllib](https://docs.python.org/3.12/library/tomllib.html). Relative paths are anchored to the configuration directory. Paths are literal: no environment/tilde expansion. Offline validation does not resolve DNS, load credentials, establish certificate trust or check ACLs. Summaries/errors omit credential paths and raw rejected values.

## Fixture schema and output

The [healthy fixture](../src/rehearsal/fixtures/healthy.json) remains the reference for the synthetic snapshot schema. It requires `schema_version: 1`, `simulated: true`, a printable description and exactly one `inventory` or `failure` payload. Inventory contains version, nodes and storage/VM/network arrays; the latter arrays may be empty. This is Rehearsal's normalized snapshot format, not raw API response data.

Fixtures reject missing fields, duplicate JSON keys/resource identities, unknown node references, inconsistent capacities, invalid CIDRs/control characters and files above 2 MiB. Counts/capacities fit signed 64-bit integers; booleans are not integers. Missing requested nodes produce `incomplete_inventory`. Relative override paths use the config directory. Missing/unreadable fixtures never fall back to `healthy`. Only synthetic data belongs in fixtures.

Failure fixtures accept `authentication_failed`, `permission_denied`, `unavailable`, `timeout` or `tls_untrusted`. They simulate presentation, not actual API behaviour. Transport tests exercise the separate HTTP adapter.

Output retains the original resource arrays and adds coverage/completeness metadata, storage content and nullable unknown API capacities/activity, plus optional IPv6 CIDRs. Fixture validation remains strict for its original input fields. Capacities are bytes in JSON and GiB in human output. API reports always state the ACL visibility limitation. `complete: true` means successful requested queries, not complete unfiltered resource visibility; see [operations and visibility](live-inventory.md#operations-and-visibility).

| Exit | Meaning |
| --- | --- |
| `0` | Valid configuration or successful inventory queries |
| `2` | Usage/configuration/explicit opt-in error |
| `3` | Fatal inventory/credential/TLS/transport/schema failure or simulated failure |
| `4` | Partial API inventory; inspect per-node/section coverage on stdout |

Success/partial reports use stdout. Fatal/configuration errors use stderr, with JSON when requested. Parser usage errors remain safe text. Partial output is explicitly labelled, and an inaccessible node has failed/skipped coverage rather than a successfully queried empty record.

## Tests and packaging

The local supervised adapter has additional network-blocked tests for durable
request/UPID evidence, lost responses, interruption, evidence-write failure,
UTC correction, unavailable historical tasks and task-log loss. These tests do
not require starting nested VMs, deployment or credential renewal. See
[the evidence contract](supervised-build.md#offline-request-evidence-13-november-2026)
and [the infrastructure investigation boundary](investigation-2026-11-13.md).

**Pre-review verification on dev01, 13 November 2026:** all **239 offline tests** passed (219
baseline plus 20 added cases), with sockets/DNS blocked. Ruff lint/format checks,
`pip check`, fixture inventory and local documentation-link checks passed. Python
was 3.12.3 in the existing project venv. No dependencies were added, and no lab
requests, deployment, credential renewal, controller-state change, commit or push
were performed. Local client timing/provenance is tested with mocks; actual
nested-start validation remains blocked by the unresolved host fault.

The subsequent [offline review](../CHANGELOG.md) fixes response recovery after
crash, bounded task discovery, task identity validation, credential handling and
journal compatibility. Status now distinguishes a controller status from recorded
task proof, and new operator terminal results require an explicit reason/evidence
object with an append-only transition. Historical rows and missing provenance are
preserved. These source changes remain undeployed and have no live nested-start
validation. The review uses temporary synthetic journals/copies only and does not
read or edit the live controller journal or expired credential.

**Review validation on dev01, 13 November 2026:** all **272 offline tests** passed,
plus Ruff lint/format and dependency checks. Targeted regressions cover retained
response recovery, active leases, fresh timing contexts, late/mismatched tasks,
partial response failures, credential redaction, explicit operator outcomes and
legacy/incompatible journal copies. Wheel/source builds and fixture CLI checks
use a staged source copy outside the repository; the source archive retains
`tests/conftest.py` and firewall examples. No new dependencies were introduced.

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests tools
.venv/bin/ruff format --check src tests tools
.venv/bin/python -m pip check
.venv/bin/python -m build --no-isolation
```

The suite blocks sockets and DNS and uses temporary **synthetic** token files. It exercises configuration/fixture behaviour, the GET-only transport, successful/partial responses, retries/deadlines, TLS settings and error classification, secret redaction, protected token permissions and gating before credential access. It does not establish actual TLS negotiation, real API rights, controller connectivity or VM boot. The [packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/) describes the wheel/entry-point conventions.

Builds produce `dist/rehearsal-0.2.0.tar.gz` and `dist/rehearsal-0.2.0-py3-none-any.whl`, including bundled fixtures and the Apache licence. To test a separate local installation:

```bash
python3 -m venv .cache/api-wheel-smoke
.cache/api-wheel-smoke/bin/python -m pip install --require-hashes -r requirements-runtime.lock
.cache/api-wheel-smoke/bin/python -m pip install --no-index --no-deps dist/rehearsal-0.2.0-py3-none-any.whl
.cache/api-wheel-smoke/bin/rehearsal inventory --config examples/rehearsal.toml --backend fixture --format json
```

With delivered wheels, add `--no-index --find-links /path/to/runtime-wheels` to dependency installation. Run the installed executable outside the checkout with absolute paths to confirm package resources are included. Venvs, caches and build output are ignored. Current implementation has no controller-specific filesystem dependency.

## Refreshing dependency locks

The local application milestone passes **316 offline tests** and **2 separately
opted-in Docker integration tests** on 13 November 2026. Unit guards block both
Python sockets/DNS and Psycopg's C-level connection entry point; Docker calls are
blocked unless the integration marker, command-line flag and environment opt-in
are present. The [runbook](local-postgres-exercise.md) retains real CLI and repeat
integration evidence. These checks do not contact the lab or change deployment.

Keep `requirements-runtime.in` and the runtime pin in `pyproject.toml` aligned; keep setuptools aligned with the build requirement. Use fresh empty download directories and review lock diffs. The stdlib helper reads downloaded wheel metadata/hashes, performs no resolution/network access, and rejects duplicate distributions.

```bash
.venv/bin/python -m pip download --only-binary=:all: --dest .cache/runtime-lock-refresh -r requirements-runtime.in
.venv/bin/python tools/lock_dev_dependencies.py .cache/runtime-lock-refresh --source requirements-runtime.in --scope 'Runtime dependencies' > requirements-runtime.lock
.venv/bin/python -m pip download --only-binary=:all: --dest .cache/dev-lock-refresh -r requirements-dev.in
.venv/bin/python tools/lock_dev_dependencies.py .cache/dev-lock-refresh > requirements-dev.lock

# Optional application lock, also included by requirements-dev.in:
.venv/bin/python -m pip download --only-binary=:all: --dest .cache/exercise-lock-refresh -r requirements-exercise.in
.venv/bin/python tools/lock_dev_dependencies.py .cache/exercise-lock-refresh --source requirements-exercise.in --scope 'Optional application dependencies' > requirements-exercise.lock
```

Do not reuse directories containing stale wheels. Resolution/download needs an approved package index; rendering does not. Runtime locks exclude test/build tools. The existing wheel was deployed unchanged; documentation updates after that deployment do not imply a rebuilt 0.2.0 artifact. See the [live deployment runbook](live-inventory.md#verified-deployment-record) for verified installation and repeatable checks.
