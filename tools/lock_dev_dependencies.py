"""Render a hashed dependency lock from a fresh directory of pip-downloaded wheels.

Resolution/download is deliberately separate. This script performs no network
access and rejects duplicate distributions rather than choosing stale wheels.
"""

import argparse
import hashlib
import platform
import re
from email import message_from_bytes
from pathlib import Path
from zipfile import ZipFile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheels", type=Path)
    parser.add_argument("--source", default="requirements-dev.in")
    parser.add_argument("--scope", default="Runtime and development/build dependencies")
    args = parser.parse_args()
    entries = {}
    for wheel in sorted(args.wheels.glob("*.whl")):
        with ZipFile(wheel) as archive:
            metadata_files = [
                n
                for n in archive.namelist()
                if n.count("/") == 1 and n.endswith(".dist-info/METADATA")
            ]
            if len(metadata_files) != 1:
                parser.error("wheel must have exactly one distribution metadata file")
            metadata = message_from_bytes(archive.read(metadata_files[0]))
        name = re.sub(r"[-_.]+", "-", metadata["Name"]).lower()
        if name in entries:
            parser.error("duplicate distribution; use a fresh wheel directory")
        with wheel.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        entries[name] = f"{name}=={metadata['Version']} --hash=sha256:{digest}"
    if not entries:
        parser.error("no wheels found")
    print(f"# Generated from {args.source} by tools/lock_dev_dependencies.py.")
    print(
        f"# Wheel hashes for Python {platform.python_version()}, "
        f"{platform.system()} {platform.machine()}. {args.scope}."
    )
    print("\n".join(entries[name] for name in sorted(entries)))


if __name__ == "__main__":
    main()
