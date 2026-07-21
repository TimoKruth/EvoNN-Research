---
authoritative: false
status: archived
---

# Gate B0 Closure Design

## Status

Approved design for closing Gate B0 through one reviewed pull request using the repository's existing implementation-commit plus evidence-only-commit discipline.

## Context

Gate B0 is currently open only because B0.2 lacks checked-in authoritative remote provenance and B0.5 lacks checked-in hosted runtime evidence. The authoritative repository now exists at `https://github.com/TimoKruth/EvoNN-Research.git`.

The shallow-checkout defect in the first hosted runs was fixed and merged through PR #1. The resulting merged `main` revision is:

- commit: `f68856f0c2fdf0ebc73671264b5a3ab0cff3b224`
- Linux workflow run: `29658842317`
- macOS workflow run: `29658842318`

Both post-merge workflows succeeded. Their uploaded runtime probes were downloaded and validated against the workflow identity, tested commit, backend, host architecture, numerical operation, and capability-manifest digest.

Authoritative hosted evidence:

| Lane | Run URL | Artifact name | Artifact SHA-256 |
| --- | --- | --- | --- |
| Linux / NumPy | `https://github.com/TimoKruth/EvoNN-Research/actions/runs/29658842317` | `b0-linux-runtime-probe` | `f17ca8a8f35538d72c6a7585ef013a7e1f5d50484fcc08d85ac672745d371c00` |
| macOS / MLX | `https://github.com/TimoKruth/EvoNN-Research/actions/runs/29658842318` | `b0-macos-runtime-probe` | `147e5c54a75bb9090eb3e94e06fe9c9f656ca751df12fdb5fc8950bf4398e157` |

GitHub Actions artifacts are retention-bound. Gate evidence must remain verifiable in a clean clone after those downloads expire.

## Goals

1. Close B0.2 without changing already verified governing-source bytes or pins.
2. Preserve the exact hosted Linux and macOS runtime probes in the repository.
3. Evolve the B0 report from its intentionally pre-hosting schema to a closed-state schema.
4. Validate hosted evidence offline and fail closed for fabrication, drift, or mismatches.
5. Rerun and record joint Gate B0 integration.
6. Close all six B0 items and authorize the Phase 0 interface-freeze transition.
7. Preserve validation on merge commits and later descendant commits.

## Non-goals

- The hosted probes do not qualify scientific results, backend performance, numerical equivalence, or portability beyond the bootstrap contract.
- The validator will not depend on live GitHub APIs or continued artifact availability.
- Governing-source commits, Git object IDs, import timestamps, declared versions, and content digests will not change.
- Phase 0 implementation or lane splitting is outside this pull request.

## Selected Architecture

The closure uses B0 report schema `2.0.0` with structured hosted runtime evidence. The two exact probe JSON files are committed under `governance/evidence/b0/hosted/`. The main B0 report remains the single authoritative integration record and gains a mandatory `hosted_runtime_probes` section.

A separate hosted-evidence manifest is not introduced because it would add another schema and cross-file consistency surface without serving another consumer. Merely listing unstructured artifact paths is rejected because it would not enforce run identity, backend pairing, tested commit, or platform identity.

## Commit Discipline

### Commit A: evaluated closure implementation

The branch may contain preparatory design and implementation commits. Commit A means the final pre-evidence revision after independent review, required fixes, and the checked-in review record. Commit B must be its direct child.

Commit A contains all closure inputs and policy changes:

- `governance/evidence/b0/hosted/linux-runtime-probe.json`
- `governance/evidence/b0/hosted/macos-runtime-probe.json`
- remote-pinned authority provenance
- schema `2.0.0` validator changes
- hosted-evidence validation
- plan and process updates
- regression tests
- independent review record
- any fixes required by review

The exact hosted probe bytes come from post-merge runs `29658842317` and `29658842318` at commit `f68856f0c2fdf0ebc73671264b5a3ab0cff3b224`.

### Commit B: evidence-only integration record

Commit B is the direct child of Commit A and changes exactly:

- `governance/b0-report.json`
- `governance/b0-status.yaml`
- `.superpowers/sdd/task-6-report.md`

The report records Commit A as `repository.evaluated_commit` and its tree as `repository.evaluated_tree`. The hosted evidence entries separately record `f68856f0c2fdf0ebc73671264b5a3ab0cff3b224` as the revision exercised by GitHub Actions. This distinction is mandatory: the report must not claim that hosted CI ran against closure code written after those runs.

The existing descendant-safe rule remains: validation locates the committed evidence-only revision reachable from `HEAD`, verifies that its direct parent is the evaluated implementation commit, and computes checked-in evidence digests from the frozen evidence revision rather than the moving working tree.

## Authority Provenance Transition

`governance/authority-provenance.yaml` changes as follows:

- document status: `active`
- authority state: `remote-pinned`
- each source origin state: `authoritative-remote`
- each source upstream URL: `https://github.com/TimoKruth/EvoNN-Research.git`

The validator already normalizes HTTPS and SSH Git identities, so this canonical HTTPS URL must match the configured SSH `origin` identity.

The following fields remain byte-for-byte unchanged for all three sources:

- `source_commit`
- `declared_version`
- `imported_at`
- `git_object_type`
- `git_object_id`
- `content_digest`
- authority roles and consumer-acceptance ownership

A change to any pinned source byte or digest would instead constitute a source upgrade and is outside this closure.

## B0 Report Schema 2.0.0

The report retains its existing repository, items, workflows, local probes, checked-in evidence, verification, and transition sections. It adds a required ordered `hosted_runtime_probes` array.

The order is fixed:

1. Linux / NumPy / Stratograph
2. macOS / MLX / Prism

Each hosted entry has a closed schema containing:

- `backend`
- `backend_version`
- `system`
- `manifest_path`
- `artifact_name`
- `artifact_path`
- `sha256`
- `repository_commit`
- `workflow_name`
- `run_id`
- `run_attempt`
- `run_url`
- `event`
- `branch`
- `host_os`
- `host_architecture`
- `execution_scope`
- `evidence_scope`
- `qualification`
- `conclusion`

Canonical values include:

- `execution_scope: hosted`
- `evidence_scope: hosted_bootstrap`
- `qualification: bootstrap_probe_only`
- `conclusion: success`
- `event: push`
- `branch: main`

Run IDs and attempts remain strings to match the runtime-probe JSON representation.

## Hosted Evidence Validation

The governance validator adds a dedicated hosted-probe validator following the existing local-probe pattern.

It requires exactly two entries and rejects missing, extra, unknown, duplicate, or reordered entries. For each entry it:

1. Requires a normalized repository-relative artifact path.
2. Rejects absolute paths, parent traversal, symbolic links, non-files, and repository escapes.
3. Reads the committed artifact from the frozen evidence revision.
4. Recomputes and compares SHA-256.
5. Parses a JSON object with runtime-probe schema `1.0.0` and kind `b0_runtime_backend_bootstrap`.
6. Requires `status: passed` and `qualification: bootstrap_probe_only`.
7. Matches workflow name, run ID, attempt, backend distribution/version, system, host OS/architecture, tested commit, and manifest path to the report entry.
8. Requires the numerical operation to be validated and its actual value to equal its expected value.
9. Resolves the capability manifest at the recorded tested commit and recomputes its SHA-256, rather than using moving `HEAD` bytes.
10. Requires both hosted probes to target the same full commit ID.
11. Requires that shared commit to equal `f68856f0c2fdf0ebc73671264b5a3ab0cff3b224` for this closure record.
12. Requires distinct canonical run IDs and exact repository run URLs.
13. Requires Linux to bind to the NumPy fallback on x86_64 Linux and macOS to bind to native MLX on arm64 Darwin.

Validation is offline. The run URLs are provenance links and are checked for exact repository/run identity, but no policy check depends on GitHub availability.

The committed artifact paths are included in B0.5 `evidence_paths` and the report's `checked_in_evidence` digest map. The report must not contain its own digest.

## Gate State Transition

The final `governance/b0-status.yaml` and report state are synchronized:

- B0.1: `closed`
- B0.2: `closed`
- B0.3: `closed`
- B0.4: `closed`
- B0.5: `closed`
- B0.6: `closed`
- top-level B0: `closed`
- blockers: empty mapping
- `parallel_handoff_ready: true`
- `parallel_handoff_blockers: []`

B0.2 evidence cites the remote-pinned provenance, upgrade process, traceability, and integration report.

B0.5 evidence cites both workflow definitions, the runtime-probe implementation, both committed hosted probes, their run metadata, and the integration report.

B0.1 and B0.6 move from `locally_satisfied` to `closed` only after the final joint integration verification and independent review are recorded.

The next transition states that the team must jointly freeze Phase 0 interfaces before creating Lane A and Lane B implementation branches.

## Plan and Process Updates

`CONSOLIDATED_PLAN.md` will:

- check B0.2 and B0.5;
- replace obsolete blocker text with the concrete authority URL, run IDs, tested commit, and committed evidence paths;
- state that Gate B0 is closed;
- preserve the bootstrap-only evidence qualification;
- replace the completed immediate actions with the Phase 0 interface-freeze and lane-start sequence.

`governance/SPEC_UPGRADE_PROCESS.md` will retain the general B0.2 rule and add a concise closure record identifying the reviewed remote-pinning transition without treating it as a source-byte upgrade.

`PARALLEL_WORK_GUIDE.md` and every active status text that still claims B0.2/B0.5 are open will be updated consistently. The guide remains non-authoritative but is part of the checked-in B0.6 evidence surface.

## Independent Review

Before Commit B is generated, the functional closure diff receives an independent code and governance review. Required fixes are applied, and the final checked-in review record becomes part of Commit A. Final verification runs against Commit A's complete tree, including that record. Because repository publication uses one GitHub identity, the review is preserved under `reviews/`, following the existing cross-review pattern.

The review covers:

- provenance truthfulness;
- hosted evidence/run binding;
- schema closure and fail-closed behavior;
- Git commit anchoring;
- artifact path safety;
- manifest digest recomputation;
- plan/status/report consistency;
- clean-clone and descendant behavior.

All required findings are fixed before final evidence generation. The review record is referenced by B0.6 and included in `checked_in_evidence`.

## Test Strategy

Regression tests cover:

- the valid checked-in schema `2.0.0` closure;
- exact hosted probe order and count;
- missing, extra, duplicate, or unknown fields;
- tampered artifact bytes and recorded digests;
- wrong workflow name, run ID, attempt, URL, event, branch, or conclusion;
- wrong backend, system, host, or tested commit;
- Linux/macOS evidence swaps;
- unpassed or non-bootstrap probe claims;
- numerical operation mismatch;
- capability-manifest digest mismatch at the historical tested commit;
- unsafe paths, symlink components, and repository escapes;
- remote-pinned authority with unchanged source pins and normalized HTTPS/SSH identity;
- rejection of unconfigured, local, file, loopback, or inconsistent remote identities;
- rejection of top-level closure while any item remains non-closed;
- exact evidence-only commit paths and direct-parent relationship;
- clean-clone validation;
- validation on commits descended from the evidence-only revision;
- both workflows retaining `fetch-depth: 0`.

Tests that currently require B0.2/B0.5 to remain open or forbid all hosted fields will be replaced with transition-aware closed-state tests. Fabricated or partial hosted evidence remains explicitly rejected.

## Verification and Delivery Sequence

1. Implement the validator, committed probes, tests, provenance, plan, and process changes in one or more preparatory commits.
2. Run focused red/green tests while implementing each validator behavior.
3. Run the full pinned local verification set over the functional diff.
4. Perform independent review and apply every required fix.
5. Add the final checked-in review record and finalize Commit A as the exact evaluated implementation revision.
6. Run the full pinned verification set against Commit A.
7. Regenerate fresh local NumPy and MLX probes against exact Commit A.
8. Generate Commit B with final status, report, and task report only.
9. Rerun the complete verification set at Commit B.
10. Push the branch and open a reviewed pull request.
11. Require both Linux and macOS PR workflows to pass.
12. Review and merge through GitHub without pushing directly to `main`.
13. Confirm post-merge policy checks remain valid on the merge commit.
14. Begin Phase 0 only with the joint interface-freeze step defined by the consolidated plan.

Any failed invariant keeps Gate B0 open. There is no fallback to metadata-only evidence, mutable external artifacts, or live-network validation.
