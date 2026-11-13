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
export commands were run locally. The first implementation was initially unpushed;
subsequent verified hosted execution is recorded below.

## Initial publication attempt, 13 November 2026

Verified public repository `erdosl/rehearsal`, authenticated account `erdosl`,
unprotected default branch `main` and no applicable branch rules/PR requirement.
Fetched remote main at `2f763cceb61c8c2becaff0a05d84ff0f20ddddaf`; no incoming
commits. The four outgoing commits include the prerequisite investigation review
`f092acb` and reviewed milestones `7a99ede`, `efc4411`, `5160da3`. Inspected outgoing
content for credential material, private keys, backups, binary/runtime state and
raw evidence; none was found. LICENSE is unchanged.

GitHub rejected the normal fast-forward push with **GH007**, protecting a private
commit email. Nothing was published and no Actions run exists from this attempt.
This was a publication blocker, not a failed CI job. History and account/repository
settings were left unchanged pending an explicit operator decision. See
GitHub's [email-privacy push policy](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/blocking-command-line-pushes-that-expose-your-personal-email-address).

## Verified hosted execution, 13 November 2026

The user explicitly authorized replacing only their private author/committer email
in unpublished commits. GitHub's API for the signed published initial commit
[`2f763cc`](https://github.com/erdosl/rehearsal/commit/2f763cceb61c8c2becaff0a05d84ff0f20ddddaf)
provided `104799996+erdosl@users.noreply.github.com`, with the author mapped to
authenticated account `erdosl`, ID 104799996. The address was read from that account
evidence, not constructed. Set repository-local `user.email` to that value; global
configuration and GitHub privacy/settings were unchanged.

Fetched remote history before rewriting. Only the five commits after published
`2f763cc` were rewritten; no other contributor identity changed. Their trees,
messages, ordering and author/committer dates were compared equal. Four commits
had email fields replaced; the final documentation commit already had the correct
email and changed only because its parent changed. No squash or published rewrite.

| Original local commit | Published replacement |
| --- | --- |
| `f092acb298867b6c8ee72e38c2c165a267e14782` | `e9405c78363e196baec2afd6814dca2f10c078a7` |
| `7a99ede4859b5e23fa2739c4e3c09b77f82421eb` | `7a158be9e11760abf529073329a5ff12b759dac5` |
| `efc44118e1655f5164d16a0d05a286a4b4cf6f8c` | `1c88764299636773c21791b62aa24c5ccedd93cf` |
| `5160da374ee6e7182f41a7f7b65503dab4b6b6c1` | `10e5f30bdd415013ae1bad7e69d311fdb6673e2f` |
| `39bc5dd3a0879e7077f2a7f9a6297504391032a9` | `d73652c87921af007b99192d2de7525898369671` |

The local-only backup is `refs/backup/gh007-before-20261113T214536Z`; it was not
pushed. Full mapping/tree verification and downloaded evidence are retained under
`dev01:~/.local/state/rehearsal-email-publication-20261113T214536Z-54437250/`.
The outgoing commit objects and trees were scanned for the private address without
printing it. Content remained unchanged; no local suite rerun was needed for the
metadata rewrite. Normal fast-forward publication succeeded, with no force push
or branch-protection bypass.

Hosted [run 43513561091](https://github.com/erdosl/rehearsal/actions/runs/43513561091)
was triggered by push on exact SHA
**`d73652c87921af007b99192d2de7525898369671`**:

- [Offline checks](https://github.com/erdosl/rehearsal/actions/runs/43513561091/job/132189623499)
  passed unit, lint/format, dependency and package smoke checks on hosted Ubuntu 24.04.
- [Docker recovery](https://github.com/erdosl/rehearsal/actions/runs/43513561091/job/132189624214)
  passed both real integration cases. Successful recovery verified all 100 orders,
  schema, restored API, target selection and distinct canary (101 records afterward).
  Its measured exercise recovery duration was 9.732937 seconds, within the existing
  restore-readiness-to-verification/canary boundaries; this is not a production RTO.
- The negative case retained 100 rows but detected exactly one changed customer
  field; recovered-data verification failed as intended before the canary. Its test
  passed. Both run reports mark owned cleanup complete, their cleanup phases passed,
  and the separate `Reconcile owned cleanup` step completed successfully.

Downloaded both artifact ZIPs, matched their API SHA-256 digests and inspected
every member and JSON field. They contain **only** `offline.json`,
`docker-checks.json` and `recovery.json`, conforming to the exporter allowlist.
No backup, manifest, credential, environment dump, raw report or raw diagnostic
text was included. Backup metadata is 4,588 bytes plus SHA-256 for each run;
`backups_uploaded` is false. API expiry is approximately seven days after creation,
consistent with `retention-days: 7`. Evidence does not prove lab connectivity,
guest boot/recovery or behavior after runner destruction.
