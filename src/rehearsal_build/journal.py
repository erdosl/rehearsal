"""Durable ownership and operation intent for one supervised build resource."""

import contextlib
import fcntl
import json
import os
import sqlite3
import stat
import time
import uuid
from pathlib import Path

from rehearsal_build.redaction import SECRET_TEXT, sensitive_key


class SafetyError(RuntimeError):
    """A precondition cannot be established; do not issue another mutation."""


PENDING = ("intent", "uncertain", "running")


def public_json(value):
    """Reject secret-bearing fields before they can enter durable state."""
    if isinstance(value, dict):
        if any(sensitive_key(key) for key in value):
            raise SafetyError("secret-bearing state is forbidden")
        for key, item in value.items():
            public_json(key)
            public_json(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            public_json(item)
    elif isinstance(value, str) and SECRET_TEXT.search(value):
        raise SafetyError("secret-bearing state is forbidden")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def ownership(resource):
    return {
        key: resource[key]
        for key in ("installation", "run", "resource", "nonce", "node", "vmid", "pool", "role")
    }


def description(resource):
    return public_json({"rehearsal_ownership": ownership(resource)})


def require_owner(resource, live):
    try:
        observed = json.loads(live["description"])["rehearsal_ownership"]
    except (KeyError, TypeError, ValueError):
        raise SafetyError("live ownership metadata is missing or invalid") from None
    if observed != ownership(resource):
        raise SafetyError("live and durable ownership do not match")
    if any(live.get(key) != resource[key] for key in ("node", "vmid", "pool")):
        raise SafetyError("live resource mapping does not match durable state")
    if live.get("template") or resource["role"] != "build" or resource["vmid"] != 9000:
        raise SafetyError("protected or out-of-scope resource")


class Journal:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise SafetyError("state directory must be owned and mode 0700")
        self.lock_fd = os.open(
            self.directory / "supervised.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lock_fd)
            raise SafetyError("another supervised operation holds the lock") from None
        path = self.directory / "journal.sqlite3"
        try:
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            created = False
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                self.close()
                raise SafetyError("state database must be a regular owned mode 0600 file") from None
        else:
            created = True
            os.close(fd)
        try:
            self.db = sqlite3.connect(path, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            self._initialize(created)
        except sqlite3.Error:
            self.close()
            raise SafetyError(
                "incompatible or unreadable journal; preserve it for inspection"
            ) from None
        except BaseException:
            self.close()
            raise

    def _initialize(self, created):
        if not created:
            self._validate_schema()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        if created:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS installation (id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS resources (
                resource TEXT PRIMARY KEY, installation TEXT NOT NULL, run TEXT NOT NULL,
                nonce TEXT NOT NULL, node TEXT NOT NULL, vmid INTEGER NOT NULL UNIQUE,
                pool TEXT NOT NULL, role TEXT NOT NULL, created REAL NOT NULL,
                expires REAL NOT NULL, state TEXT NOT NULL, config_digest TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY, resource TEXT REFERENCES resources(resource),
                label TEXT NOT NULL UNIQUE, method TEXT NOT NULL, path TEXT NOT NULL,
                desired TEXT NOT NULL, actor TEXT NOT NULL, created REAL NOT NULL,
                status TEXT NOT NULL, upid TEXT, result TEXT
            );
            CREATE TABLE IF NOT EXISTS volumes (
                resource TEXT NOT NULL REFERENCES resources(resource), volume TEXT NOT NULL,
                operation TEXT NOT NULL REFERENCES operations(id), PRIMARY KEY(resource, volume)
            );
            CREATE TABLE IF NOT EXISTS lease (owner TEXT PRIMARY KEY, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, utc REAL NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL
            );
        """)
        if created:
            self.db.execute("PRAGMA user_version=1")
            self.db.execute("INSERT INTO installation VALUES (?)", (str(uuid.uuid4()),))
        self.installation = self.db.execute("SELECT id FROM installation").fetchone()[0]
        self.owner = str(uuid.uuid4())

    def _validate_schema(self):
        expected = {
            "installation": {"id"},
            "resources": {
                "resource",
                "installation",
                "run",
                "nonce",
                "node",
                "vmid",
                "pool",
                "role",
                "created",
                "expires",
                "state",
                "config_digest",
            },
            "operations": {
                "id",
                "resource",
                "label",
                "method",
                "path",
                "desired",
                "actor",
                "created",
                "status",
                "upid",
                "result",
            },
            "volumes": {"resource", "volume", "operation"},
            "lease": {"owner", "expires"},
            "events": {"id", "utc", "kind", "body"},
        }
        if self.db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise SafetyError("unknown state database; preserve it for inspection")
        for table, columns in expected.items():
            actual = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
            if actual != columns:
                raise SafetyError("incompatible journal schema; preserve it for inspection")
        identities = self.db.execute("SELECT id FROM installation").fetchall()
        if len(identities) != 1:
            raise SafetyError(
                "journal installation identity is unavailable; preserve it for inspection"
            )
        try:
            uuid.UUID(identities[0][0])
        except (ValueError, TypeError, AttributeError):
            raise SafetyError(
                "invalid journal installation identity; preserve it for inspection"
            ) from None

    def close(self):
        if hasattr(self, "db"):
            self.db.close()
            del self.db
        if getattr(self, "lock_fd", None) is not None:
            os.close(self.lock_fd)
            self.lock_fd = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.release_lease()
        self.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")

    def event(self, kind, body):
        self.db.execute(
            "INSERT INTO events(utc,kind,body) VALUES (?,?,?)",
            (time.time(), kind, public_json(body)),
        )

    def heartbeat(self, now=None):
        now = time.time() if now is None else now
        with self.transaction():
            other = self.db.execute(
                "SELECT owner FROM lease WHERE owner!=? AND expires>?", (self.owner, now)
            ).fetchone()
            if other:
                raise SafetyError("another active lease protects the operation")
            self.db.execute("DELETE FROM lease WHERE expires<=?", (now,))
            self.db.execute("INSERT OR REPLACE INTO lease VALUES (?,?)", (self.owner, now + 120))

    def release_lease(self):
        if hasattr(self, "db") and hasattr(self, "owner"):
            self.db.execute("DELETE FROM lease WHERE owner=?", (self.owner,))

    def reserve(self, *, node, vmid, pool, config_digest, now=None):
        if vmid != 9000 or not node or not pool or len(config_digest) != 64:
            raise SafetyError("invalid first-build allocation")
        now = time.time() if now is None else now
        result = dict(
            resource=str(uuid.uuid4()),
            installation=self.installation,
            run=str(uuid.uuid4()),
            nonce=str(uuid.uuid4()),
            node=node,
            vmid=vmid,
            pool=pool,
            role="build",
            created=now,
            expires=now + 6 * 3600,
            state="reserved",
            config_digest=config_digest,
        )
        with self.transaction():
            if self.db.execute("SELECT 1 FROM resources WHERE vmid=?", (vmid,)).fetchone():
                raise SafetyError("VMID already reserved; resume its existing journal")
            self.db.execute(
                "INSERT INTO resources VALUES "
                "(:resource,:installation,:run,:nonce,:node,:vmid,:pool,:role,"
                ":created,:expires,:state,:config_digest)",
                result,
            )
        return result

    def resource(self):
        row = self.db.execute("SELECT * FROM resources WHERE vmid=9000").fetchone()
        if not row:
            raise SafetyError("build resource has not been reserved")
        return dict(row)

    def pending(self):
        rows = self.db.execute(
            "SELECT * FROM operations WHERE status IN ('intent','uncertain','running') "
            "ORDER BY created"
        ).fetchall()
        return [dict(row) for row in rows]

    def resource_state(self, state, evidence):
        if state not in (
            "created",
            "imported",
            "isolated",
            "network-verified",
            "running",
            "stopped",
            "retained",
            "deleted",
        ):
            raise SafetyError("invalid supervised resource state")
        with self.transaction():
            self.event(
                "resource-state",
                {"resource": self.resource()["resource"], "state": state, "evidence": evidence},
            )
            self.db.execute("UPDATE resources SET state=? WHERE vmid=9000", (state,))

    def intent(self, label, method, path, desired, actor, resource=None):
        public_json({"label": label, "method": method, "path": path, "actor": actor})
        encoded = public_json(desired)
        with self.transaction():
            if self.pending():
                raise SafetyError("unresolved operation must be reconciled before any mutation")
            if self.db.execute("SELECT 1 FROM operations WHERE label=?", (label,)).fetchone():
                raise SafetyError("operation already attempted; inspect its durable result")
            operation = dict(
                id=str(uuid.uuid4()),
                resource=resource,
                label=label,
                method=method,
                path=path,
                desired=encoded,
                actor=actor,
                created=time.time(),
                status="intent",
            )
            self.db.execute(
                "INSERT INTO operations"
                "(id,resource,label,method,path,desired,actor,created,status) "
                "VALUES (:id,:resource,:label,:method,:path,:desired,:actor,:created,:status)",
                operation,
            )
        return operation["id"]

    def operation(self, opid):
        row = self.db.execute("SELECT * FROM operations WHERE id=?", (opid,)).fetchone()
        if not row:
            raise SafetyError("unknown operation")
        return dict(row)

    def mutation_evidence(self, opid):
        """Read only this operation's request observations; never infer old provenance."""
        operation = self.operation(opid)
        matched = {"api-request-start": [], "api-request-end": []}
        for row in self.db.execute(
            "SELECT kind,body FROM events WHERE kind IN ('api-request-start','api-request-end') "
            "ORDER BY id"
        ):
            body = json.loads(row["body"])
            if body.get("operation") == opid and body.get("method") != "GET":
                if (
                    body.get("method") != operation["method"]
                    or body.get("path") != operation["path"]
                ):
                    raise SafetyError(
                        "conflicting mutation request evidence; retain for reconciliation"
                    )
                matched[row["kind"]].append(body)
        starts, ends = matched["api-request-start"], matched["api-request-end"]
        if len(starts) != 1 or len(ends) != 1:
            raise SafetyError(
                "request provenance is unavailable; explicit operator evidence required"
            )
        start, end = starts[0], ends[0]
        if any(
            start.get(key) != end.get(key) or start.get(key) is None
            for key in (
                "request",
                "timing_context",
                "started_utc_epoch",
                "started_monotonic_seconds",
            )
        ):
            raise SafetyError("conflicting request provenance; retain for reconciliation")
        return start, end

    def outcome_evidence(self, opid):
        """Summarize recorded task proof without treating a controller status as a PVE result."""
        operation = self.operation(opid)
        outcomes, sources = set(), set()
        for row in self.db.execute(
            "SELECT kind,body FROM events WHERE kind IN "
            "('task-observation','task-terminal','upid-attribution') ORDER BY id"
        ):
            body = json.loads(row["body"])
            if body.get("operation") != opid or body.get("upid") != operation["upid"]:
                continue
            if row["kind"] == "upid-attribution":
                sources.add(body.get("source", "unrecorded"))
                continue
            exitstatus = (
                body.get("status")
                if row["kind"] == "task-terminal"
                else body.get("exitstatus")
                if body.get("status") == "stopped"
                else None
            )
            if isinstance(exitstatus, str) and exitstatus.strip():
                outcomes.add("succeeded" if exitstatus == "OK" else "failed")
        return {
            "task_outcome": next(iter(outcomes))
            if len(outcomes) == 1
            else "conflicting"
            if outcomes
            else "unknown",
            "upid_sources": sorted(sources) if sources else ["unrecorded"],
        }

    def update(
        self, opid, status, *, upid=None, result=None, upid_source="unrecorded", request=None
    ):
        if status not in (*PENDING, "complete", "failed"):
            raise SafetyError("invalid operation status")
        if upid_source not in (
            "unrecorded",
            "mutation-response",
            "task-listing",
            "operator-supplied",
        ):
            raise SafetyError("invalid UPID evidence source")
        encoded = public_json(result) if result is not None else None
        with self.transaction():
            previous = self.operation(opid)
            if previous["status"] in ("complete", "failed"):
                raise SafetyError("terminal operation evidence cannot be rewritten")
            if previous["upid"] and upid and previous["upid"] != upid:
                raise SafetyError("operation task identity changed")
            self.event(
                "operation-transition",
                {
                    "schema_version": 1,
                    "operation": opid,
                    "previous_status": previous["status"],
                    "status": status,
                    "source": upid_source,
                    "evidence": result,
                },
            )
            if upid:
                self.event(
                    "upid-attribution",
                    {
                        "schema_version": 1,
                        "operation": opid,
                        "upid": upid,
                        "source": upid_source,
                        "request": request,
                    },
                )
            self.db.execute(
                "UPDATE operations SET status=?,upid=COALESCE(?,upid),"
                "result=COALESCE(?,result) WHERE id=?",
                (status, upid, encoded, opid),
            )

    def record_volumes(self, resource, opid, volumes):
        op = self.operation(opid)
        if op["resource"] != resource["resource"] or op["status"] != "complete":
            raise SafetyError("volume provenance requires this resource's completed operation")
        with self.transaction():
            for volume in volumes:
                if not isinstance(volume, str) or ":" not in volume:
                    raise SafetyError("invalid volume identity")
                self.db.execute(
                    "INSERT OR IGNORE INTO volumes VALUES (?,?,?)",
                    (resource["resource"], volume, opid),
                )

    def check_cleanup(self, live, *, tasks, volumes, now=None, expiry_only=False):
        now = time.time() if now is None else now
        resource = self.resource()
        require_owner(resource, live)
        if tasks or self.pending() or live.get("lock"):
            raise SafetyError("active or unresolved tasks protect the resource")
        lease_sql = (
            "SELECT 1 FROM lease WHERE expires>?"
            if expiry_only
            else "SELECT 1 FROM lease WHERE expires>? AND owner!=?"
        )
        lease_args = (now,) if expiry_only else (now, self.owner)
        if self.db.execute(lease_sql, lease_args).fetchone():
            raise SafetyError("active lease protects the resource")
        if expiry_only and now <= resource["expires"]:
            raise SafetyError("expiry does not yet permit cleanup")
        recorded = {
            row[0]
            for row in self.db.execute(
                "SELECT volume FROM volumes WHERE resource=?", (resource["resource"],)
            )
        }
        if set(volumes) != recorded:
            raise SafetyError("live and recorded volumes differ; quarantine")
        if live.get("status") != "stopped":
            raise SafetyError("stop and reconcile the owned VM before deletion")
        return resource
