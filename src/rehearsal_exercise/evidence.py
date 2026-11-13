"""Local, fsynced evidence snapshots and append-only events; no external free text."""

import contextlib
import fcntl
import hashlib
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4


class ExerciseError(RuntimeError):
    """Only fixed, credential-free diagnostics may cross this boundary."""


def utc():
    return datetime.now(UTC).isoformat()


def atomic_json(path, data):
    atomic_text(path, json.dumps(data, sort_keys=True, indent=2) + "\n")


def atomic_text(path, data):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def protected_directory(path, *, create=True):
    if create:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ExerciseError("evidence directory must be owned and mode 0700")


@contextlib.contextmanager
def locked_root(root, *, create=True):
    root = Path(root).absolute()
    protected_directory(root, create=create)
    fd = os.open(root / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ExerciseError(
                "another local exercise or cleanup holds the evidence lock"
            ) from None
        yield root
    finally:
        os.close(fd)


def canonical_run_id(value):
    try:
        parsed = UUID(value)
        if parsed.version != 4 or str(parsed) != value:
            raise ValueError
        return value
    except (ValueError, TypeError, AttributeError):
        raise ExerciseError("run ID must be a canonical UUIDv4") from None


class Evidence:
    def __init__(self, root, run_id, *, create=False):
        self.directory = root / canonical_run_id(run_id)
        installation_file = root / "installation.json"
        if create:
            # Never reuse or overwrite an old run, even when it previously failed.
            try:
                self.directory.mkdir(mode=0o700)
            except FileExistsError:
                raise ExerciseError(
                    "run already exists; inspect/clean it and use a new run ID"
                ) from None
            if not installation_file.exists():
                atomic_json(installation_file, {"installation": str(uuid4())})
            installation = json.loads(installation_file.read_text())["installation"]
            self.data = {
                "format_version": 1,
                "installation": installation,
                "run": run_id,
                "exercise": "local-postgres-logical-restore",
                "created_utc": utc(),
                "outcome": "incomplete",
                "cleanup": "pending",
                "phase": "created",
                "resources": [],
                "phases": [],
                "checks": {},
            }
            self.save()
        else:
            protected_directory(self.directory, create=False)
            self.data = json.loads((self.directory / "state.json").read_text())
            installation = json.loads(installation_file.read_text())["installation"]
            if (
                self.data["run"] != run_id
                or self.data["installation"] != installation
                or self.data["format_version"] != 1
            ):
                raise ExerciseError("evidence identity or format mismatch")

    def save(self):
        atomic_json(self.directory / "state.json", self.data)

    def event(self, kind, **details):
        # Callers supply structured allowlisted data, never raw commands or exceptions.
        with (self.directory / "events.jsonl").open("a") as stream:
            stream.write(json.dumps({"utc": utc(), "kind": kind, **details}, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def report(self):
        atomic_json(self.directory / "report.json", self.data)
        data = self.data
        lines = [
            f"# Local synthetic PostgreSQL exercise {data['run']}",
            f"Outcome: {data['outcome']}; cleanup: {data['cleanup']}",
            f"Phase: {data['phase']}",
            f"Failure: {data.get('failure', 'none')}",
            "",
            "Measured exercise recovery duration: "
            + json.dumps(data.get("recovery", {"complete": False}), sort_keys=True),
            "",
            "Boundaries: immediately before allocating the restore network/volume/instance, "
            "through recovered SQL/schema/API verification and the separate "
            "post-restore write/read.",
            "Image preparation, source preparation, backup and cleanup are outside that interval.",
            "Frozen synthetic writes only; no production RTO/RPO, PITR or incremental "
            "recovery claim.",
            "Backups and manifests remain outside disposable volumes; manual retention, "
            "no sweeper.",
        ]
        atomic_text(self.directory / "report.md", "\n\n".join(lines) + "\n")

    def publish(self):
        self.save()
        self.report()
        index = {}
        for path in self.directory.iterdir():
            if (
                not path.is_file()
                or path.name == "evidence-index.json"
                or path.name.endswith("-credential")
            ):
                continue
            with path.open("rb") as stream:
                checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            index[path.name] = {"bytes": path.stat().st_size, "sha256": checksum}
        atomic_json(self.directory / "evidence-index.json", index)
