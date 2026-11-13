# Changelog

## Unreleased — 13 November 2026 offline evidence review

These source changes are **not deployed** and have **not been validated through
a live nested start**. Deployed inventory 0.2.0 and the controller sidecar remain
unchanged. No lab requests, infrastructure changes, credential renewal or live
controller-state edits were performed. The recorded bootstrap expiry has passed.

- Add append-only operation/request correlation, UTC and local monotonic timing,
  HTTP status, safe transport categories and explicit UPID provenance.
- Recover a response UPID retained before a crash without repeating the mutation;
  preserve leases and use a fresh timing context after restart. Require bounded
  request evidence for task discovery; reject mismatched tasks and later unrelated
  tasks. Missing or conflicting evidence requires operator reconciliation.
- Preserve confirmed task failures when log retrieval fails. Missing task history
  or exit status remains uncertain. Offline status separates controller state
  from task-outcome evidence; current resource state never proves historical task
  success. Operator terminal resolutions require an explicit result/reason and
  append an auditable transition.
- Restrict requests to the configured API origin, stream responses with a size
  limit, retain HTTP status on partial-body transport failures, and remove unsafe
  transport exception context. Redact credential fields, recognizable credential
  text and private-key log groups; reject credential-bearing mutation metadata
  before journaling.
- Validate existing version-1 journal shape and installation identity before
  initialization writes. Preserve historical rows and provenance gaps; reject
  incompatible journals without automatic repair or identity replacement.
- Retain the [supplied investigation handoff](docs/investigation-2026-11-13.md),
  separating reported fault evidence from hypotheses and unverified remedies.

Validation: **272 network-blocked tests passed**, plus Ruff lint/format,
dependency checks, fixture CLI checks and wheel/source builds from a staged copy.
Source archives include the test network guard and referenced examples; generated
packages remain outside the repository. See [development validation](docs/development.md#tests-and-packaging) and
the [evidence contract](docs/supervised-build.md#offline-request-evidence-13-november-2026).
Live nested validation remains blocked by the unresolved host fault and requires
a separate explicit operator decision. Local evidence is protected diagnostic
data; arbitrary unlabelled external text is not a safe public report format.
