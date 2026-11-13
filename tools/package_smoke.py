"""Build in a fresh staging copy and smoke-test the installed wheel without network."""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from zipfile import ZipFile


def checked(args, **kwargs):
    result = subprocess.run(args, capture_output=True, timeout=120, **kwargs)
    if result.returncode:
        raise RuntimeError("package smoke command failed; no raw diagnostics exported")


def main():
    project = Path(__file__).resolve().parents[1]
    staging = Path(tempfile.mkdtemp(prefix="rehearsal-package-"))
    source = staging / "source"
    source.mkdir()
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=project,
        capture_output=True,
        check=True,
    ).stdout
    for name in listing.split(b"\0"):
        if not name:
            continue
        relative = Path(name.decode())
        original = project / relative
        if original.is_file() and not original.is_symlink():
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, destination)
    checked(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(staging / "dist"),
            str(source),
        ]
    )
    wheel = next((staging / "dist").glob("*.whl"))
    with ZipFile(wheel) as archive:
        for relative in (
            "rehearsal_orders/schema.sql",
            "rehearsal_exercise/images.toml",
            "rehearsal_exercise/runner.py",
            "rehearsal_orders/domain.py",
        ):
            if archive.read(relative) != (project / "src" / relative).read_bytes():
                raise RuntimeError("packaged resource mismatch")
    with tarfile.open(next((staging / "dist").glob("*.tar.gz"))) as archive:
        for required in (".dockerignore", "docker/orders.Dockerfile", "tests/conftest.py"):
            if not any(name.endswith("/" + required) for name in archive.getnames()):
                raise RuntimeError("source archive resource missing")
    installed = staging / "installed"
    checked(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--target",
            str(installed),
            str(wheel),
        ]
    )
    env = {**os.environ, "PYTHONPATH": str(installed)}
    checked(
        [
            sys.executable,
            "-c",
            "import rehearsal_exercise; assert 'installed' in rehearsal_exercise.__file__",
        ],
        cwd=staging,
        env=env,
    )
    checked([sys.executable, "-m", "rehearsal_exercise", "--help"], cwd=staging, env=env)
    checked(
        [
            sys.executable,
            "-m",
            "rehearsal",
            "inventory",
            "--config",
            str(project / "examples/rehearsal.toml"),
            "--backend",
            "fixture",
            "--format",
            "json",
        ],
        cwd=staging,
        env=env,
    )
    print(json.dumps({"package_smoke": "passed", "artifacts": str(staging / "dist")}))


if __name__ == "__main__":
    main()
