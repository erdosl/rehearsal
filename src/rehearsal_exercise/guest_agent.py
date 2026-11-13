"""Fixed operations inside a prepared disposable guest; no VM lifecycle commands."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

from rehearsal_exercise.evidence import atomic_json

LIMIT = 16 * 1024**2
LEASE_ROOT = Path("/var/lib/rehearsal/exercise")
APP_UNIT = "rehearsal-orders.service"
DB_UNIT = "postgresql@18-main.service"
ENVIRONMENT = {
    "PGHOST": "127.0.0.1",
    "PGPORT": "5432",
    "PGDATABASE": "orders",
    "PGUSER": "order_app",
    "ORDER_PASSWORD_FILE": "/etc/rehearsal/order-password",
}


def command(args, data=None):
    result = subprocess.run(
        args,
        input=data,
        capture_output=True,
        timeout=60,
        env={
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LANG": "C.UTF-8",
        },
    )
    if result.returncode:
        raise RuntimeError("guest command failed")
    return result.stdout


def active(unit):
    # systemctl show succeeds for inactive services; do not treat arbitrary errors as stopped.
    return command(["systemctl", "show", unit, "--property=ActiveState", "--value"]).strip()


def app_target_valid():
    import shlex

    values = dict(
        item.split("=", 1)
        for item in shlex.split(
            command(
                [
                    "systemctl",
                    "show",
                    APP_UNIT,
                    "--property=Environment",
                    "--value",
                ]
            ).decode()
        )
    )
    if any(values.get(key) != value for key, value in ENVIRONMENT.items()):
        return False
    for field in ("DropInPaths", "EnvironmentFiles"):
        if command(["systemctl", "show", APP_UNIT, f"--property={field}", "--value"]).strip():
            return False
    if (
        command(["systemctl", "show", APP_UNIT, "--property=NeedDaemonReload", "--value"]).strip()
        != b"no"
    ):
        return False
    unset = (
        command(["systemctl", "show", APP_UNIT, "--property=UnsetEnvironment", "--value"])
        .decode()
        .split()
    )
    return {"PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"} <= set(unset)


@contextlib.contextmanager
def lease(root, owner, operation):
    # A dedicated directory owned by the SSH account is prepared separately, never auto-created.
    info = root.lstat()
    if root.is_symlink() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("untrusted lease directory")
    with (root / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = root / "owner.json"
        if operation == "claim":
            if path.exists() or path.is_symlink():
                raise RuntimeError("guest already leased; no overwrite or expiry inference")
            atomic_json(path, owner)
        elif operation not in ("probe", "receipt"):
            if path.is_symlink() or json.loads(path.read_text()) != owner:
                raise RuntimeError("guest lease ownership mismatch")
        yield
        if operation == "release":
            if active(APP_UNIT) != b"inactive" or active(DB_UNIT) != b"inactive":
                raise RuntimeError("services must be stopped before releasing lease")
            path.unlink()


def transfer_bytes(data, checksum):
    if len(data) > LIMIT or hashlib.sha256(data).hexdigest() != checksum:
        raise RuntimeError("archive transfer checksum mismatch")
    return data


def release_fingerprint(path):
    # The retained wheel alone is not proof that the running modules match that release.
    with ZipFile(path) as archive:
        for name in archive.namelist():
            package, _, relative = name.partition("/")
            if package in ("rehearsal_orders", "rehearsal_exercise") and name.endswith(
                (".py", ".sql", ".toml")
            ):
                if files(package).joinpath(relative).read_bytes() != archive.read(name):
                    raise RuntimeError("installed release differs from approved wheel")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def perform(operation, data, checksum=None):
    postgres = ["sudo", "-n", "-u", "postgres", "--"]
    if operation == "probe":
        return json.dumps(
            {
                "machine_id": Path("/etc/machine-id").read_text().strip(),
                "release_sha256": release_fingerprint(
                    Path("/opt/rehearsal/artifacts/rehearsal.whl")
                ),
                "app_target_valid": app_target_valid(),
                "app_state": active(APP_UNIT).decode(),
                "database_state": active(DB_UNIT).decode(),
                "lease_owner": json.loads((LEASE_ROOT / "owner.json").read_text())
                if (LEASE_ROOT / "owner.json").exists()
                else None,
            }
        ).encode()
    if operation in ("claim", "release"):
        return b"{}"
    if operation == "sql":
        return command(
            postgres
            + [
                "psql",
                "-h",
                "/var/run/postgresql",
                "-p",
                "5432",
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-At",
                "-U",
                "postgres",
                "-d",
                "orders",
            ],
            data,
        )
    if operation in ("dump-version", "restore-version"):
        return command(["pg_dump" if operation == "dump-version" else "pg_restore", "--version"])
    if operation == "versions":
        import platform

        import psycopg

        return json.dumps(
            {
                "python": platform.python_version(),
                "psycopg": psycopg.__version__,
                "libpq": psycopg.pq.version(),
            }
        ).encode()
    if operation == "dump":
        archive = command(
            postgres
            + [
                "pg_dump",
                "-h",
                "/var/run/postgresql",
                "-p",
                "5432",
                "-U",
                "postgres",
                "-d",
                "orders",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
            ]
        )
        if len(archive) > LIMIT:
            raise RuntimeError("archive exceeds transfer limit")
        return (
            json.dumps(
                {"sha256": hashlib.sha256(archive).hexdigest(), "bytes": len(archive)}
            ).encode()
            + b"\n"
            + archive
        )
    if operation in ("restore", "list"):
        transfer_bytes(data, checksum)
        if operation == "list":
            return command(["pg_restore", "--list"], data)
        command(
            postgres
            + [
                "pg_restore",
                "-h",
                "/var/run/postgresql",
                "-p",
                "5432",
                "-U",
                "postgres",
                "-d",
                "orders",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-privileges",
            ],
            data,
        )
        return json.dumps({"sha256": checksum, "bytes": len(data)}).encode()
    if operation in ("app-start", "app-stop", "db-stop"):
        if operation == "app-start" and not app_target_valid():
            raise RuntimeError("application target is not pinned to guest loopback")
        unit = DB_UNIT if operation == "db-stop" else APP_UNIT
        command(["sudo", "-n", "systemctl", "start" if operation == "app-start" else "stop", unit])
        return b"{}"
    if operation == "http":
        from rehearsal_exercise.http_client import request

        requests = json.loads(data)
        if not isinstance(requests, list) or len(requests) > 110:
            raise RuntimeError("bounded HTTP batch required")
        return json.dumps([request(**item) for item in requests]).encode()
    raise RuntimeError("unsupported guest operation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=(
            "probe",
            "receipt",
            "claim",
            "release",
            "sql",
            "dump-version",
            "restore-version",
            "versions",
            "dump",
            "list",
            "restore",
            "app-start",
            "app-stop",
            "db-stop",
            "http",
        ),
    )
    parser.add_argument("--run", required=True)
    parser.add_argument("--installation", required=True)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--sha256")
    parser.add_argument("--request")
    args = parser.parse_args()
    try:
        owner = {key: str(UUID(getattr(args, key))) for key in ("run", "installation", "resource")}
        data = sys.stdin.buffer.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise RuntimeError("input exceeds limit")
        with lease(LEASE_ROOT, owner, args.operation):
            receipt = (
                LEASE_ROOT / ("request-" + str(UUID(args.request)) + ".json")
                if args.request
                else None
            )
            if args.operation == "receipt":
                recorded = json.loads(receipt.read_text())
                if recorded["owner"] != owner:
                    raise RuntimeError("receipt ownership mismatch")
                result = json.dumps(recorded).encode()
            else:
                if receipt:
                    if receipt.exists() or receipt.is_symlink():
                        raise RuntimeError("request already attempted; inspect receipt")
                    recorded = {
                        "owner": owner,
                        "operation": args.operation,
                        "input_sha256": hashlib.sha256(data).hexdigest(),
                        "status": "intent",
                    }
                    atomic_json(receipt, recorded)
                try:
                    result = perform(args.operation, data, args.sha256)
                except Exception:
                    if receipt:
                        atomic_json(receipt, recorded | {"status": "failed"})
                    raise
        if args.operation != "receipt" and receipt:
            atomic_json(receipt, recorded | {"status": "complete"})
        sys.stdout.buffer.write(result)
        return 0
    except Exception:
        print("guest operation failed; no raw diagnostic exported", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
