"""Run CI checks with fixed diagnostics; publish only structured check outcomes."""

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path


def check(name, args, timeout):
    with subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True
    ) as process:
        try:
            process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGINT)
            try:
                process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
            print(name + ": timeout")
            return False
        print(name + (": passed" if process.returncode == 0 else ": failed"))
        return process.returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("offline", "docker"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    python = sys.executable
    if args.kind == "offline":
        commands = [
            ("unit", [python, "-m", "pytest", "-q", "-m", "not docker"], 300),
            ("lint", [python, "-m", "ruff", "check", "src", "tests", "tools"], 60),
            ("format", [python, "-m", "ruff", "format", "--check", "src", "tests", "tools"], 60),
            ("dependencies", [python, "-m", "pip", "check"], 60),
            ("package", [python, "tools/package_smoke.py"], 180),
        ]
    else:
        if args.root is None or args.root.exists() or os.environ.get("REHEARSAL_LIVE") != "1":
            parser.error("Docker checks require a new --root and REHEARSAL_LIVE=1")
        commands = [
            (
                "recovery",
                [
                    python,
                    "-m",
                    "pytest",
                    "-q",
                    "--docker-exercise",
                    "-m",
                    "docker",
                    "--basetemp",
                    str(args.root),
                    "tests/test_exercise_docker.py",
                ],
                900,
            )
        ]
    results = {name: check(name, command, timeout) for name, command, timeout in commands}
    data = {"kind": args.kind, "checks": results, "passed": all(results.values())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as stream:
            stream.write(f"## {args.kind} checks\n\n")
            for name, passed in results.items():
                stream.write(f"- {name}: {'passed' if passed else 'failed'}\n")
            stream.write("\nLocal commands ran on this runner; no lab connectivity is used.\n")
    return 0 if data["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
