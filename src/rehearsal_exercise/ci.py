"""Best-effort owned cleanup and an allowlisted public CI evidence projection."""

import argparse
import json
import math
import os
import re
from pathlib import Path
from uuid import UUID

from rehearsal_exercise.docker import Docker
from rehearsal_exercise.evidence import Evidence, ExerciseError, atomic_json, locked_root
from rehearsal_exercise.runner import remove_credentials

CHECKS = {
    "source_data",
    "source_schema",
    "source_api",
    "restore_data",
    "restore_schema",
    "restore_api",
    "restore_target_selection",
    "post_restore_canary",
    "source_preserved_until_cleanup",
}
PHASES = {
    "created",
    "preflight",
    "image_preparation",
    "source_preparation",
    "seed",
    "quiesce",
    "backup",
    "source_shutdown",
    "target_preparation",
    "restore",
    "recovered_data_verification",
    "restored_application",
    "post_restore_write_read",
    "cleanup",
    "finished",
    "cleanup_pending",
}


def number(value):
    return (
        value
        if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 86400
        else None
    )


def public_run(data):
    """Never copy free text, paths, raw schemas/events, records or connection details."""
    run = str(UUID(data["run"]))
    result = {
        "run": run,
        "outcome": data["outcome"]
        if data["outcome"] in ("passed", "failed", "errored", "cancelled", "incomplete")
        else "incomplete",
        "cleanup": "complete" if data.get("cleanup") == "complete" else "pending",
        "fault": data.get("fault")
        if data.get("fault") in ("none", "changed-record")
        else "unavailable",
        "failure_phase": data.get("failure_phase") if data.get("failure_phase") in PHASES else None,
        "checks": {},
        "recovery": {
            "complete": data.get("recovery", {}).get("complete") is True,
            "duration_seconds": number(data.get("recovery", {}).get("duration_seconds")),
        },
        "phases": [],
        "backups_uploaded": False,
    }
    for key in CHECKS:
        check = data.get("checks", {}).get(key)
        if isinstance(check, dict):
            result["checks"][key] = {"passed": check.get("passed") is True}
            for field in ("expected_count", "actual_count"):
                if type(check.get(field)) is int and 0 <= check[field] <= 10000:
                    result["checks"][key][field] = check[field]
            for field in ("missing", "extra", "changed"):
                if isinstance(check.get(field), (dict, list)):
                    result["checks"][key][field + "_count"] = len(check[field])
    for phase in data.get("phases", []):
        if phase.get("name") in PHASES:
            result["phases"].append(
                {
                    "name": phase["name"],
                    "passed": phase.get("status") == "passed",
                    "duration_seconds": number(phase.get("duration_seconds")),
                }
            )
    backup = data.get("backup", {})
    if type(backup.get("bytes")) is int and 0 <= backup["bytes"] <= 16 * 1024**2:
        result["backup_bytes"] = backup["bytes"]
    if isinstance(backup.get("sha256"), str) and re.fullmatch("[0-9a-f]{64}", backup["sha256"]):
        result["backup_sha256"] = backup["sha256"]
    return result


def evidence_roots(root):
    if not root.exists():
        return
    for child in sorted(root.iterdir()):
        if (
            not child.is_symlink()
            and child.is_dir()
            and child.name.startswith("test_real_local_recovery_")
        ):
            candidate = child / "evidence"
            if candidate.is_dir() and not candidate.is_symlink():
                yield candidate


def cleanup(root):
    complete = True
    for parent in evidence_roots(root):
        with locked_root(parent, create=False):
            for directory in parent.iterdir():
                if not directory.is_dir() or directory.is_symlink():
                    continue
                evidence = Evidence(parent, directory.name)
                if evidence.data["outcome"] == "incomplete":
                    evidence.data.update(outcome="cancelled", failure="CI execution interrupted")
                complete = Docker(evidence).cleanup() and complete
                remove_credentials(evidence)
                evidence.publish()
    return complete


def export(root, output):
    runs = []
    for parent in evidence_roots(root):
        for directory in sorted(parent.iterdir()):
            path = directory / "report.json"
            if directory.is_symlink() or path.is_symlink() or not path.is_file():
                continue
            runs.append(public_run(json.loads(path.read_text())))
    result = {"format_version": 1, "kind": "docker", "runs": runs, "backups_uploaded": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(output, result)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as stream:
            stream.write("\n## Recovery evidence\n\n")
            for run in runs:
                stream.write(f"- {run['run']}: {run['outcome']}; cleanup {run['cleanup']}\n")
            stream.write(
                "\nThe altered-record case is expected to fail verification. "
                "Backups and raw diagnostics are excluded.\n"
            )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("cleanup", "export"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.command == "cleanup" and (not args.live or os.environ.get("REHEARSAL_LIVE") != "1"):
        parser.error("cleanup requires --live and REHEARSAL_LIVE=1")
    try:
        if args.command == "cleanup":
            return 0 if cleanup(args.root) else 1
        if args.output is None:
            parser.error("export requires --output")
        export(args.root, args.output)
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ExerciseError):
        print('{"error":"CI evidence or cleanup unavailable; inspect local state"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
