# Public GitHub-hosted checks

[ci.yml](../.github/workflows/ci.yml) runs on `pull_request`, pushes to `main` and
manual `workflow_dispatch`. Both jobs use GitHub-hosted `ubuntu-24.04`, Python
3.12.16/x64 and the hashed development lock. No job uses a lab runner, SSH key,
Proxmox endpoint, repository secret or controller deployment. Fork code executes
only on an ephemeral public runner. There is no `pull_request_target` or privileged
downstream workflow consuming PR artifacts. Checkout credentials are not persisted.

| Job | Checks | Bounds |
| --- | --- | --- |
| Offline | Network-blocked unit suite, Ruff lint/format, `pip check`, staged wheel/sdist build, installed-wheel fixture/entry-point/resource smoke checks | 12 minutes; per-command deadlines |
| Docker recovery | Existing two integration cases: exact recovery and distinct canary; same-count altered-field rejection | 20 minutes; 15-minute test deadline, then best-effort cleanup |

Permissions are `contents: read`; all unspecified `GITHUB_TOKEN` scopes are
disabled. No token is passed to project commands. The workflow serializes runs
per PR/ref without cancelling active runs, and the Docker job has a repository-wide
concurrency group. GitHub permits one running and one pending member per group;
new pending runs can replace older pending runs. This is not a durable queue.

The runner creates only synthetic UUID-scoped Docker resources. Exercise cleanup
runs in `perform_run` on success/failure; a separate `always()` step also reconciles
the exact retained ownership journals and removes credentials. It never prunes.
An active lock, mismatched ownership or unresolved operation blocks deletion.
Cancellation, job timeout or runner destruction can prevent cleanup steps; the
ephemeral runner is the final containment boundary. No lab resource is reachable
through a configured integration path.

## Evidence and summaries

Both jobs write fixed check outcomes to the job summary. Recovery additionally
lists each run UUID, outcome and cleanup status; a failed recovery report for the
altered-record case is expected when that test passes. Check command output is
captured in memory and replaced by fixed pass/fail/timeout diagnostics. Rerun the
underlying command locally to investigate details.

Artifacts expire after **7 days** (subject to repository policy). Upload paths
name only `offline.json`, `docker-checks.json` and `recovery.json` in a dedicated
runner-temporary publication directory. They contain booleans, bounded counts,
known phase names, durations, run UUIDs and backup size/SHA-256. The projection in
`rehearsal_exercise.ci` does not copy arbitrary strings from exercise reports.
Credentials, environment, private paths, records, raw diagnostic text, schema
definitions, full journals and reports are excluded. **No backup or manifest is
uploaded**, even though the exercise seeds only deterministic synthetic orders.
Checksums are metadata, not a recoverable backup. Local complete evidence follows
the [manual retention policy](local-postgres-exercise.md); runner-local evidence
disappears when its runner is destroyed.

## Pins and local verification

Pins were resolved with `git ls-remote` against the action owners' repositories,
and their `action.yml` files were inspected at those exact commits on 13 November
2026. They use the Node 24 action runtime on current hosted Ubuntu runners.

| Action | Release | Full commit |
| --- | --- | --- |
| [checkout](https://github.com/actions/checkout/tree/d23441a48e516b6c34aea4fa41551a30e30af803) | v6.1.0 | `d23441a48e516b6c34aea4fa41551a30e30af803` |
| [setup-python](https://github.com/actions/setup-python/tree/ece7cb06caefa5fff74198d8649806c4678c61a1) | v6.3.0 | `ece7cb06caefa5fff74198d8649806c4678c61a1` |
| [upload-artifact](https://github.com/actions/upload-artifact/tree/b7c566a772e6b6bfb58ed0dc250532a479d7789f) | v6.0.0 | `b7c566a772e6b6bfb58ed0dc250532a479d7789f` |

The design follows GitHub's [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use)
and [concurrency semantics](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
Review release diffs and update pins deliberately; no repository settings were changed.

After the normal venv setup:

```bash
.venv/bin/python tools/ci_checks.py offline --output /tmp/rehearsal-offline.json
REHEARSAL_LIVE=1 .venv/bin/python tools/ci_checks.py docker \
  --root /absolute/new/private/test-root --output /tmp/rehearsal-docker-checks.json
REHEARSAL_LIVE=1 .venv/bin/python -m rehearsal_exercise.ci cleanup --live \
  --root /absolute/new/private/test-root
.venv/bin/python -m rehearsal_exercise.ci export --root /absolute/new/private/test-root \
  --output /tmp/rehearsal-publish/recovery.json
actionlint .github/workflows/ci.yml
```

Use a new test root: pytest replaces its explicit base temporary directory. The
driver refuses an existing root, preserving prior evidence. Local validation used
actionlint **1.7.12**, downloaded from the primary release with its release checksum
verified, without installing a system package. Both underlying jobs and the cleanup/
export commands were run locally. **GitHub-hosted execution remains untested**;
these workflow files have not been pushed and no remote success is claimed.

## Publication attempt, 13 November 2026

Verified public repository `erdosl/rehearsal`, authenticated account `erdosl`,
unprotected default branch `main` and no applicable branch rules/PR requirement.
Fetched remote main at `2f763cceb61c8c2becaff0a05d84ff0f20ddddaf`; no incoming
commits. The four outgoing commits include the prerequisite investigation review
`f092acb` and reviewed milestones `7a99ede`, `efc4411`, `5160da3`. Inspected outgoing
content for credential material, private keys, backups, binary/runtime state and
raw evidence; none was found. LICENSE is unchanged.

GitHub rejected the normal fast-forward push with **GH007**, protecting a private
commit email. Nothing was published and no Actions run exists from this attempt.
This is a publication blocker, not a failed CI job. History and account/repository
settings remain unchanged. Resolving it requires an explicit operator decision;
do not bypass privacy protection or rewrite reviewed commits automatically. See
GitHub's [email-privacy push policy](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/blocking-command-line-pushes-that-expose-your-personal-email-address).

After resolution, push normally, inspect both jobs on the exact resulting SHA,
and download only their metadata artifacts into a new private directory. Verify
the archive member names and allowlisted JSON fields against the exporter, both
recovery outcomes (including expected altered-field failure), and the independent
cleanup step. Record run URLs/tested SHAs; workflow presence or local checks alone
are not remote execution evidence. No remote artifact/cleanup success is claimed
while publication is blocked.
