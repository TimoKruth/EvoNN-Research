---
document_kind: review
status: delivered
authoritative: false
subject: gate_b0_cross_review_addendum
reviewed_ref: agent/b0-bootstrap @ 5f00384
reviewer: lane-counterpart (Claude, planning agent)
verdict: approve_with_joint_fixes_applied
---

# Gate B0 Cross-Review Addendum — follow-up commits `68fd1cf` + `5f00384`

Delta review of the two follow-up commits against the R1–R3 findings in
`reviews/2026-07-18-b0-cross-review.md`, re-verified independently in a
detached worktree.

## Follow-up verification

- **R1 resolved and verified.** The MLX allowance is now the data-driven
  `ALLOWED_EXTERNAL_MODULE_ATTRIBUTE_CALLS = {("mlx.core", "eval")}` with
  static import-alias verification and shadowing/rebinding detection.
  Empirically probed: a representative Phase 2 training step with multiple
  `mx.eval(...)` calls and literal `getattr` passes; `from mlx.core import
  eval`, alias rebinding, and value acquisition all fail closed.
- **R2 resolved.** The research log now documents the full reserved-name
  policy (all six categories), the literal-`getattr` rule, the narrow
  `importlib.metadata` surface, and a five-step reviewed-exception process.
- **R3 anticipated by the author** (a policy test asserts the branch guide
  wins the merge conflict); resolution applied at integration.

## New findings (found in delta review, fixed jointly)

Both fixes were authored by the reviewer on `agent/b0-joint-fixes`
because Gate B0 is joint work and the implementing agent was unavailable;
they require reciprocal review by the implementing agent on return.

### R4 — policy test depended on gitignored generated artifacts

`test_local_probe_parent_symlink_escape_is_rejected` copied
`.artifacts/b0/local/numpy/b0-runtime-probe.json` — a gitignored,
generated file. The test passed only in the authoring worktree and failed
on any fresh checkout; both hosted workflows run this suite **before**
probe generation, so the first hosted run (the evidence intended to close
B0.5) would have failed. Fixed by making the test self-contained (it
writes a placeholder artifact; the assertion exercises only the
symlink-escape rejection).

### R5 — report verification was anchored to HEAD/working tree, blocking merge and all future development

`validate_b0_report` required `HEAD^ == evaluated_commit` and verified
`checked_in_evidence` digests against the working tree. Consequences,
confirmed empirically by merge simulation: governance validation fails on
`main` after the (R3-resolved) merge, and — since both workflows trigger
on every push — the check could only ever pass on an evidence-tip commit;
the first Phase 0 commit would also have gone red. The root defect:
historical claims verified against the moving HEAD instead of the
revisions the claims are about.

Fixed by anchoring verification to the committed evidence-only revision
(`git log -1 HEAD -- governance/b0-report.json`): the evidence commit
must be the direct parent of the evaluated commit's recording, its diff
must remain evidence-only, the working-tree report must match its
committed revision, and digests are verified against the evidence
commit's tree via `git cat-file`. The report now stays verifiable on
merge commits and on every descendant; a regression test validates the
report from a clean clone with a later development commit on top.

### R6 — local probe validation was anchored to the executing HEAD

`runtime_probe.py validate --execution-mode local` required the probe's
`repository_commit` to equal the current checkout HEAD. The two-commit
discipline generates local probes at the implementation commit and
validates them from its evidence-only child, so the pinned 22-command
verification set could never all pass at any single commit (the
governance validator demanded the evidence tip while probe validation
demanded the implementation commit). Fixed: local-mode validation accepts
the executing HEAD or its first parent; hosted-mode validation remains
strictly bound to `GITHUB_SHA`. A regression test covers accepted parent
and rejected foreign commits.

## Evidence regeneration

Following the branch's own two-commit discipline, the joint fixes are an
implementation commit followed by a regenerated evidence-only commit
(fresh local probes, updated `evaluated_commit`/digests). Gate B0 status
is unchanged: open on B0.2 (`authoritative_remote_url_absent`) and B0.5
(`hosted_ci_not_executed`).

### R7 — lockfile-uniqueness test scanned internal trees (post-merge finding)

`test_single_root_lockfile_is_current` rglobbed the whole repository for
`uv.lock` files excluding only `.git`, so any linked worktree under
`.claude/worktrees/` (which this project's own tooling creates) broke the
test. Fixed by excluding the same internal trees the governance validator
already ignores. Under the R5 anchored-verification semantics this fix
needed no evidence regeneration — the first practical confirmation that
later development no longer invalidates the frozen B0 evidence.
