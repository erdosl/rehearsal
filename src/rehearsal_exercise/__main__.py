"""Explicit local Docker recovery commands. This CLI never reads lab configuration."""

import argparse
import json
import os
import signal
from pathlib import Path
from uuid import uuid4

from rehearsal_exercise.docker import Docker
from rehearsal_exercise.evidence import Evidence, ExerciseError, locked_root
from rehearsal_exercise.runner import perform_run, phase, remove_credentials


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifacts", type=Path, default=Path.home() / ".local/state/rehearsal-exercise"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "run", help="new exercise; old run IDs are never resumed or overwritten"
    )
    run.add_argument("--run-id", default=None)
    run.add_argument("--live", action="store_true", help="explicit local Docker opt-in")
    run.add_argument("--project", type=Path, default=Path.cwd())
    run.add_argument(
        "--fault",
        choices=("none", "missing-record", "changed-record", "corrupt-backup"),
        default="none",
    )
    status = commands.add_parser("status", help="read retained evidence without contacting Docker")
    status.add_argument("run_id")
    cleanup = commands.add_parser(
        "cleanup", help="reconcile and remove only exact journalled owned resources"
    )
    cleanup.add_argument("run_id")
    cleanup.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if args.command != "status" and (not args.live or os.environ.get("REHEARSAL_LIVE") != "1"):
        parser.error("local Docker mutations require --live AND REHEARSAL_LIVE=1")
    os.umask(0o077)
    signal.signal(signal.SIGTERM, interrupted)
    try:
        with locked_root(args.artifacts, create=args.command == "run") as root:
            if args.command == "run":
                evidence = perform_run(root, args.run_id or str(uuid4()), args.project, args.fault)
            else:
                evidence = Evidence(root, args.run_id)
                if args.command == "cleanup":
                    # Cleanup never changes a previous exercise failure into a pass. A hard-killed
                    # process retains incomplete timing; cleanup is the only supported continuation.
                    if evidence.data["outcome"] == "incomplete":
                        evidence.data.update(
                            outcome="cancelled",
                            failure="interrupted run; timing and phases incomplete",
                        )
                    with phase(evidence, "manual_cleanup"):
                        Docker(evidence).cleanup()
                    remove_credentials(evidence)
                    evidence.publish()
            print(
                json.dumps(
                    {
                        "run": evidence.data["run"],
                        "outcome": evidence.data["outcome"],
                        "cleanup": evidence.data["cleanup"],
                        "report": str(evidence.directory / "report.json"),
                        "failure": evidence.data.get("failure"),
                    },
                    indent=2,
                )
            )
            return (
                0
                if evidence.data["outcome"] == "passed" and evidence.data["cleanup"] == "complete"
                else 1
            )
    except ExerciseError as error:
        print(json.dumps({"error": str(error)}))
        return 2
    except (OSError, ValueError, KeyError):
        print('{"error":"local evidence unavailable or invalid; preserve it for inspection"}')
        return 2
    except KeyboardInterrupt:
        print('{"error":"interrupted; inspect retained state and use cleanup"}')
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
