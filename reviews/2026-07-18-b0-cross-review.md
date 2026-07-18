---
document_kind: review
status: delivered
authoritative: false
subject: gate_b0_cross_review
reviewed_ref: agent/b0-bootstrap @ 3ed735b
reviewer: lane-counterpart (Claude, planning agent)
verdict: approve_with_required_follow_up
---

# Gate B0 Cross-Review — `agent/b0-bootstrap` @ `3ed735b`

Reviewed against: `CONSOLIDATED_PLAN.md` Gate B0, claude-spec/01 (workspace
rules), claude-spec/18 (branch/PR policy), and the agreed B0 decisions
(7 Python skeletons + data-only `shared-benchmarks/`, strict dynamic-import
ban). All checks re-run independently in a detached review worktree:
`b0-policy-checks.sh` green (3 validators PASS, 223 tests passed).

## Verdict

**Approve, with one required follow-up before Phase 0 interface freeze
(R1) and one required merge-time resolution (R3).** Nothing here blocks
closing B0.1/B0.3/B0.4/B0.6; B0.2/B0.5 remain open on the known
no-remote blocker, correctly recorded.

## What is good (and verified)

- **Strict ban replaced the analyzer for real.** The interprocedural
  binding interpreter is gone; the policy is a deterministic AST check.
  The negative result is properly recorded in
  `research/logs/2026-07-18-dynamic-import-policy.md`.
- **Gate bookkeeping is honest.** `b0-status.yaml` / `b0-report.json`
  claim only local evidence, keep B0.2/B0.5 open with truthful reasons,
  and explicitly disclaim scientific/qualification value.
- **Provenance manifest is truthful** (provisional, null upstream URLs,
  git object IDs + sha256 tree digests recorded).
- **Workflows are well-built:** actions pinned by commit SHA, `uv sync
  --locked`, Linux lane proves MLX absence, macOS lane asserts arm64,
  runtime-probe artifacts uploaded fail-closed.
- **Data-only `shared-benchmarks/` is enforced** (no package markers, no
  runtime .py, symlink-rejecting), with the loader helper minimal and
  correctly placed in `evonn_shared.benchmarks` (dependency-light rule
  respected).
- **Plan edits are legitimate:** the rename to `CONSOLIDATED_PLAN.md`
  follows the plan's own installation instruction; checkbox updates match
  evidence; the `b0_repository_model` front-matter records the agreed
  7+data-only model.

## Findings

### R1 (required before Phase 0 freeze) — `eval` attribute ban collides with MLX's core API

`_RESERVED_PRIMITIVE_KINDS` bans any attribute named `eval`, with exactly
one hard-coded AST-shape exception for `_run_mlx_operation` in
`scripts/ci/runtime_probe.py`. Empirically confirmed: a representative
Phase 2 training step in `EvoNN-Prism/src/prism/` fails the policy —

```
forbidden reserved primitive attribute acquisition: eval   # mx.eval(...)
```

`mx.eval(...)` is the canonical MLX lazy-evaluation flush; every MLX
engine will call it pervasively. The current exception mechanism (a
bespoke exact-shape matcher per call site) cannot scale to that.

**Required fix:** a principled, still-sound allowance — e.g. permit the
`eval` attribute when the receiver resolves to the file's `import
mlx.core as mx` (or `import mlx.core`) alias, since `mlx.core.eval` is an
array-evaluation API, not code execution. Alternatively a reviewed
allowlist file (path + symbol + written justification), which the
research log already anticipates. This must land before Phase 0
interfaces freeze so Phase 2 doesn't inherit a policy that fails on its
first real training loop. (Same class of collision will eventually hit
`torch.nn.Module.eval()` in contender extras — the mechanism chosen
should cover that case too.)

### R2 (required documentation alignment) — implemented policy is stricter than the documented policy

The research log and plan text describe banning the dynamic-loading
primitives (`importlib.import_module`, `runpy.run_module`, `__import__`,
`exec`, `eval`). The implementation additionally bans namespace and
reflection primitives: `globals`/`locals`/`vars`, `__dict__`,
`__class__`, `__getattribute__`, `operator.attrgetter`/`itemgetter`/
`methodcaller`, `entry_points`, non-literal `getattr`/`setattr`
arguments, and literal-string subscript reflection. That extra
strictness is defensible (fail-closed, exceptions by review) — but it
must be *documented* strictness. Either record the full reserved-name
policy (and the literal-`getattr`-is-allowed rule) in the research log /
plan, or trim the list to the documented scope. Undocumented policy is
how the next agent loses a day.

### R3 (required at merge) — `PARALLEL_WORK_GUIDE.md` add/add conflict

The branch forked from `2860406`, before main's `f084f3c` added
`PARALLEL_WORK_GUIDE.md`; the branch then added its own different version
of the same path. Merging into main will produce an add/add conflict.
**Recommended resolution: take the branch version** — it is
front-mattered, explicitly non-authoritative, and references
`CONSOLIDATED_PLAN.md` (main's version still points at the now-renamed
`LAB_PLAN.md`). Fold anything missed from main's longer version only if
genuinely load-bearing.

### N1 (note) — process reports committed into the repo

`.superpowers/sdd/task-*-report.md` (~3,900 lines) are committed. The
governance validator ignores that tree, so no policy issue; consider
whether these belong in `research/logs/` (as non-authoritative process
evidence) or out of the repo entirely. No action required for B0.

### N2 (note) — reviewer's scope-creep check: passed

`backend_contract.py` (142 lines) and `benchmarks.py` (72 lines) in
`evonn_shared` are the only real code beyond skeletons. Both are
bootstrap-necessary (backend-capability validation, data-skeleton
validation), declared in the plan front-matter, and contain no search
logic. Phase 0 WPs (esp. WP-0.8/benchmark catalog) must **extend** these
modules, not duplicate them.

## Accountability statement

I re-ran the policy suite and tests myself, read the policy validators,
workflows, probe, governance artifacts, and plan diffs in full, and
adversarially probed the import policy with representative Phase 2 code.
I approve this branch subject to R1–R3 above and accept reviewer
accountability for that approval.
