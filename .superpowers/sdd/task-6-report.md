# Task 6 Report — Integrate and Review Gate B0

## Status

Local Gate B0 integration is complete and verified. Gate B0 remains truthfully **open** because two external requirements are unavailable in this worktree:

- **B0.2:** `authoritative_remote_url_absent`
- **B0.5:** `hosted_ci_not_executed`

`parallel_handoff_ready` remains `false`; Phase 0 was not started, expanded, or authorized.

## Commit relationship

Task 6 uses the required reproducible two-commit relationship:

1. **Implementation commit:** `90fd14e70bf3944aef6a603d5e473a6fc490a6b1`
   - Tree: `3c0e0fe5155edc26a2cba1248caff8247fc1f0c5`
   - Contains the plan/status integration, non-authoritative guide, report validator, and tests.
2. **Evidence-only child commit:** the direct child containing `governance/b0-report.json` and this Task 6 report.

The machine-readable report evaluates the exact implementation commit/tree above, avoiding a self-referential report-commit identity.

## Implemented artifacts

### Machine-readable Gate B0 report

Created `governance/b0-report.json` with:

- schema version `1.0.0` and report kind `gate_b0_integration`;
- UTC evaluation timestamp and exact evaluated commit/tree;
- overall state `open`;
- exact B0.1–B0.6 states, reasons, and evidence paths consistent with `governance/b0-status.yaml`;
- exact blockers for B0.2 and B0.5;
- fresh local NumPy and MLX probe metadata, paths, digests, backend versions, actual Darwin/arm64 host labels, and explicit local/bootstrap-only classification;
- both workflow paths, exact runners, Python/uv versions, and immutable action pins;
- all 22 required local verification commands with a 22-pass/0-fail summary;
- `parallel_handoff_ready: false` and exact blockers `[B0.2, B0.5]`;
- the required next transition: close both blockers, rerun joint integration, then jointly freeze Phase 0 interfaces before lane branches begin;
- no hosted run ID, URL, attempt, or hosted artifact evidence claim.

The existing repository-governance validator now validates the report and fails closed for:

- false `closed` or parallel-ready claims;
- fabricated hosted-evidence fields;
- report/status state or reason drift;
- wrong/missing evaluated commit/tree identity;
- a non-evidence-only commit relationship;
- wrong workflow runners or action pins;
- incomplete or failed verification declarations;
- missing, unsafe, symlinked, or digest-mismatched checked-in evidence;
- self-referential report digests;
- malformed local probe declarations;
- present local probes with digest, commit, backend/version, host, manifest, or local-placeholder inconsistencies.

Local probe artifacts are explicitly optional. Their absence in a fresh clone is accepted while the gate remains open; when present, their recorded SHA-256 and internal contract are recomputed and validated.

### Consolidated plan status

Updated only the Gate B0 and Immediate Next Actions portions of `CONSOLIDATED_PLAN.md`:

- B0.1, B0.3, B0.4, and B0.6 are checked complete;
- B0.2 remains unchecked with `authoritative_remote_url_absent`;
- B0.5 remains unchecked with `hosted_ci_not_executed`;
- Gate B0 exit is explicitly open and Phase 0 cannot begin;
- next actions are now: create authoritative remote; update provenance/close B0.2; run both hosted workflows and collect uploaded artifacts/close B0.5; rerun joint integration; then freeze Phase 0 interfaces and split lanes.

No pinned authority source under `claude-spec/`, `PROGRAM_CHARTER.md`, or `claudex-spec/19-research-interop.md` was modified.

### Parallel-work guide

Created `PARALLEL_WORK_GUIDE.md` with machine-readable frontmatter:

```yaml
document_kind: guide
status: current
authoritative: false
```

It records:

- independent Lab/Product repository work and the I1+I2 real-influence boundary;
- fixture/co-signed-schema parallelism before real influence;
- sequential Lab phases with two parallel lanes inside each phase;
- the rhythm `freeze interfaces → parallel lanes → cross-review → joint integration → joint gate`;
- exact Lane A, Lane B, and joint assignments for Phases 0–7;
- joint points including B0, Foundation Integrity Gate, phase exits, transfer proof, L-SCI, portfolio status, and release governance;
- current B0.2/B0.5 blockers and the prohibition on the first lane split;
- Phase 0 as the first safe parallel point only after B0 closure and joint freezing of the canonical digest API, export shapes, and catalog-loader signatures.

Governance tests prove the guide is not a second execution plan; `CONSOLIDATED_PLAN.md` remains the sole active plan.

### Governance status consistency

Updated `governance/b0-status.yaml` evidence text and timestamp to reference `governance/b0-report.json` and the current local verification. The exact six-item model and overall open state remain intact. B0.2 and B0.5 were not closed.

## TDD evidence

The `superpowers:test-driven-development` skill was invoked before editing.

### Initial RED

Tests were added first in `tests/policy/test_b0_integration_report.py`.

Command:

```sh
uv run --locked --group dev pytest -q --tb=short tests/policy/test_b0_integration_report.py
```

Output summary:

```text
FFFFFF                                                                   [100%]
6 failed in 1.04s
```

Expected failures proved:

- `PARALLEL_WORK_GUIDE.md` was absent;
- Gate B0 plan items were still unchecked;
- `governance/b0-report.json` was absent for all report/validator cases.

### Guide/plan GREEN and expected pre-report RED

After the guide and plan updates:

```text
..                                                                       [100%]
2 passed in 0.08s
```

The direct governance validator then failed for exactly the intentionally missing evidence report:

```text
ERROR: cannot load B0 integration report: [Errno 2] No such file or directory: '.../governance/b0-report.json'
```

This was the expected state before the implementation commit and fresh probe generation.

### Report GREEN

After generating the machine-readable report against the implementation commit:

```sh
uv run --locked --group dev pytest -q tests/policy/test_b0_integration_report.py
```

```text
......                                                                   [100%]
6 passed in 0.24s
```

### Integration regression RED and fix

The workflow-policy self-test exposed three strict syntactic policy violations in the new validator because variable keys were passed to mapping `.get(...)`:

```text
....F.                                                                   [100%]
1 failed, 5 passed in 0.75s
```

The import-boundary diagnostics identified the three exact variable-key call sites. They were replaced with membership-plus-subscription forms, preserving the repository's strict production-language policy. After the fix:

```text
......                                                                   [100%]
6 passed in 12.28s
```

The implementation commit was amended, and both local probes and the report were regenerated against the final implementation identity.

## Fresh local runtime evidence

Both artifacts were regenerated after the final implementation commit `90fd14e70bf3944aef6a603d5e473a6fc490a6b1`; no stale Task 5 artifact was reused.

### NumPy bootstrap/portability probe

Commands:

```sh
uv run --locked --all-packages --group dev python scripts/ci/runtime_probe.py generate \
  --backend numpy \
  --system stratograph \
  --manifest EvoNN-Stratograph/backend-capabilities.json \
  --output .artifacts/b0/local/numpy/b0-runtime-probe.json \
  --execution-mode local
uv run --locked --all-packages --group dev python scripts/ci/runtime_probe.py validate \
  --input .artifacts/b0/local/numpy/b0-runtime-probe.json \
  --execution-mode local \
  --expected-backend numpy
```

Output:

```text
Runtime probe: PASS (numpy_fallback 2.5.1, .artifacts/b0/local/numpy/b0-runtime-probe.json)
Runtime probe validation: PASS (numpy)
```

- Path: `.artifacts/b0/local/numpy/b0-runtime-probe.json`
- SHA-256: `8027e75cba28476042119acd3693f0fdf13ff30a2b8a17de4cae752f37343f45`
- Backend/version: NumPy `2.5.1`
- Actual host: Darwin `26.5.1`, arm64
- Embedded commit: `90fd14e70bf3944aef6a603d5e473a6fc490a6b1`
- Classification: local bootstrap/contract evidence only; not hosted, scientific, or backend qualification evidence

### MLX native bootstrap probe

Commands:

```sh
uv run --locked --all-packages --group dev python scripts/ci/runtime_probe.py generate \
  --backend mlx \
  --system prism \
  --manifest EvoNN-Prism/backend-capabilities.json \
  --output .artifacts/b0/local/mlx/b0-runtime-probe.json \
  --execution-mode local
uv run --locked --all-packages --group dev python scripts/ci/runtime_probe.py validate \
  --input .artifacts/b0/local/mlx/b0-runtime-probe.json \
  --execution-mode local \
  --expected-backend mlx
```

Output:

```text
Runtime probe: PASS (mlx_native 0.32.0, .artifacts/b0/local/mlx/b0-runtime-probe.json)
Runtime probe validation: PASS (mlx)
```

- Path: `.artifacts/b0/local/mlx/b0-runtime-probe.json`
- SHA-256: `973b7ff0fdc01dd39bcb40110a71b4cd6e87e0427c22351f42c6f662104ad3f5`
- Backend/version: MLX `0.32.0`
- Actual host: Darwin `26.5.1`, arm64
- Embedded commit: `90fd14e70bf3944aef6a603d5e473a6fc490a6b1`
- Classification: local bootstrap/contract evidence only; not hosted, scientific, or backend qualification evidence

## Full verification

All commands ran from the repository root unless explicitly marked `/tmp`.

### Lock and synchronized workspace

```sh
uv lock --check
uv sync --all-packages --group dev --locked
```

```text
Resolved 18 packages in 7ms
Resolved 18 packages in 6ms
Audited 17 packages in 0.30ms
```

Result: PASS.

### Complete pytest suite

```sh
uv run --locked --group dev pytest -q
```

```text
........................................................................ [ 30%]
........................................................................ [ 60%]
........................................................................ [ 91%]
.....................                                                    [100%]
237 passed in 28.33s
```

Result: PASS.

### Complete Ruff check

```sh
uv run --locked --group dev ruff check .
```

```text
All checks passed!
```

Result: PASS.

### Import-boundary policy

```sh
uv run --locked --group dev python scripts/policy/validate_import_boundaries.py
```

```text
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)
```

Result: PASS.

### Repository-governance policy

```sh
python3 scripts/policy/validate_repository_governance.py
```

```text
Repository governance policy: PASS
```

Result: PASS.

### Backend-capability policy

```sh
uv run --locked --group dev python scripts/policy/validate_backend_capabilities.py
```

```text
Backend capability policy: PASS (8 manifests, 4 dual-backend engine declarations)
```

Result: PASS.

### Aggregate B0 policy checks

```sh
scripts/ci/b0-policy-checks.sh
```

```text
Resolved 18 packages in 6ms
Repository governance policy: PASS
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)
Backend capability policy: PASS (8 manifests, 4 dual-backend engine declarations)
........................................................................ [ 32%]
........................................................................ [ 64%]
........................................................................ [ 96%]
.......                                                                  [100%]
223 passed, 2 deselected in 12.50s
```

Result: PASS. The two intentional deselections are the recursive policy-script self-test and all-eight-script matrix; both ran separately in the complete suite/explicit matrix.

### Workflow YAML contracts and immutable pins

```sh
uv run --locked --group dev pytest -q tests/policy/test_b0_ci_bootstrap.py
```

```text
......                                                                   [100%]
6 passed in 12.28s
```

Result: PASS. Both workflow runners, lane splits, Python/uv versions, action order, and immutable action pins were validated.

### Eight package/data scripts from `/tmp`

Each script was invoked by absolute path with `/tmp` as current directory.

```text
== shared-checks.sh ==
Resolved 18 packages in 8ms
All checks passed!
1 passed in 0.01s

== benchmarks-checks.sh ==
Resolved 18 packages in 6ms
All checks passed!
5 passed in 1.16s

== compare-checks.sh ==
Resolved 18 packages in 6ms
All checks passed!
1 passed in 0.01s

== contenders-checks.sh ==
Resolved 18 packages in 7ms
All checks passed!
1 passed in 0.01s

== prism-checks.sh ==
Resolved 18 packages in 5ms
All checks passed!
1 passed in 0.01s

== topograph-checks.sh ==
Resolved 18 packages in 20ms
All checks passed!
1 passed in 0.01s

== stratograph-checks.sh ==
Resolved 18 packages in 7ms
All checks passed!
1 passed in 0.01s

== primordia-checks.sh ==
Resolved 18 packages in 6ms
All checks passed!
1 passed in 0.01s
```

Result: all eight PASS.

### Diff validation

```sh
git diff --check
```

Output: no output; exit status 0. Result: PASS.

## Workflow contracts recorded, not hosted execution claims

The report records only immutable workflow contracts:

- Linux: `.github/workflows/linux-trust.yml`, `ubuntu-latest`
- macOS: `.github/workflows/macos-engines.yml`, `macos-15`
- `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd`
- `astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990`
- `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`
- uv `0.5.13`, Python `3.13`

No hosted workflow executed in this no-remote environment. No hosted run ID, URL, attempt, uploaded artifact, or parallel-ready claim was created.

## Files changed

Implementation commit:

- `CONSOLIDATED_PLAN.md`
- `PARALLEL_WORK_GUIDE.md`
- `governance/b0-status.yaml`
- `scripts/policy/validate_repository_governance.py`
- `tests/policy/test_b0_integration_report.py`
- `tests/policy/test_repository_governance.py`

Evidence-only child commit:

- `governance/b0-report.json`
- `.superpowers/sdd/task-6-report.md`

Ignored local evidence regenerated but not committed:

- `.artifacts/b0/local/numpy/b0-runtime-probe.json`
- `.artifacts/b0/local/mlx/b0-runtime-probe.json`

## Self-review

- Confirmed branch remains `agent/b0-bootstrap`; no switch, rename, or push occurred.
- Confirmed no Git remote is configured, so B0.2 cannot close.
- Confirmed no hosted workflow evidence exists, so B0.5 cannot close.
- Confirmed B0.1/B0.3/B0.4/B0.6 are complete in the consolidated plan while the exact six-item governance status remains overall open.
- Confirmed report item states/reasons match `governance/b0-status.yaml` exactly.
- Confirmed every referenced checked-in evidence digest is recomputed; the report excludes its own digest.
- Confirmed local artifact absence is accepted, while present artifacts are digest- and contract-validated.
- Confirmed the guide is non-authoritative and the single-active-plan validator still finds only `CONSOLIDATED_PLAN.md`.
- Confirmed pinned authority sources are unchanged.
- Confirmed the workflow section records contracts only, not hosted execution.
- Confirmed `parallel_handoff_ready` is false with exact blockers `[B0.2, B0.5]`.
- Confirmed Phase 0 and WP-0.1 were not started or expanded.
- Confirmed the next permitted transition is joint: close B0.2 and B0.5, rerun B0 integration, freeze Phase 0 interfaces, then split lanes.

## Exact remaining blockers

1. **B0.2 — `authoritative_remote_url_absent`**
   - No authoritative repository remote URL is configured.
   - Required action: create the authoritative remote, update provenance with matching authoritative URLs, and rerun validation before closing B0.2.
2. **B0.5 — `hosted_ci_not_executed`**
   - Neither hosted GitHub Actions workflow has executed, and no uploaded hosted artifacts have been collected.
   - Required action: run both hosted workflows after remote creation, validate and collect their uploaded runtime artifacts, and only then close B0.5.

Until both close and joint integration passes, Gate B0 remains open and the first Phase 0 lane split is not authorized.

## Merge-time instruction from cross-review

The delivered cross-review records a future `PARALLEL_WORK_GUIDE.md` add/add conflict with main. At merge time, the branch version must win because it is non-authoritative, front-mattered, and references `CONSOLIDATED_PLAN.md`; main's stale version references `LAB_PLAN.md`. Fold in main-only material only if it is genuinely load-bearing. Do not merge or rebase during Task 6; this is an instruction for the later integration owner.

## Cross-review follow-up

The delivered review is preserved byte-for-byte at `reviews/2026-07-18-b0-cross-review.md` (SHA-256 `39afa085164b24e186fcbfd5ec6eaf80c6f44c968a11984f7280917377ecb258`). Its R1–R3 findings and the coordinator's report-hardening findings were addressed without changing Gate B0 closure state.

### Follow-up two-commit relationship

1. Follow-up implementation/docs/review commit: `68fd1cf9cec7949e799e5da42a2c4c3b87b742ab`.
2. Evidence-only direct child: the commit containing the regenerated `governance/b0-report.json`, refreshed `governance/b0-status.yaml`, and this appended report section.

The regenerated report evaluates implementation tree `6be06429ba8baeebbc797451b993e67a9cbc4a09`. The validator now requires the evaluated implementation commit to be exactly `HEAD^`, rejects equality with `HEAD`, and requires the evidence-only diff to be exactly the three paths above.

### R1 — principled static external API allowance

The one-file/one-node `_run_mlx_operation` exception was deleted. `scripts/policy/validate_import_boundaries.py` now exposes the canonical data-driven set:

```text
ALLOWED_EXTERNAL_MODULE_ATTRIBUTE_CALLS = frozenset({("mlx.core", "eval")})
```

For each production file, the policy resolves exact static imports of the configured external module, records the imported receiver and lexical scope, and permits the reserved attribute only when it is the direct function of a call on that receiver. Module imports may serve nested scopes; function-local imports serve only that lexical scope. Any alias rebinding or shadowing anywhere in the file disables the allowance. Attribute acquisition as a value remains banned.

Coverage proves multiple legitimate calls and these import forms:

- `import mlx.core as mx`; `mx.eval(...)`;
- `from mlx import core as mx`; `mx.eval(...)`;
- `from mlx import core`; `core.eval(...)`;
- `import mlx.core`; `mlx.core.eval(...)`.

Adversarial coverage rejects no import, fake/neighbor modules, NumPy aliases, indirect aliases, assignment/parameter shadowing, cross-scope use of a function-local import, attribute acquisition, `from mlx.core import eval`, and Python `eval`.

### R2 — strict-subset documentation

`research/logs/2026-07-18-dynamic-import-policy.md` now documents the implemented syntax-only subset in full: reserved provider/execution/reflection/namespace/loader/plugin spellings; `globals`/`locals`/`vars`; dunder namespace and loader paths; operator helpers; narrowed `importlib.metadata`; literal-safe reflection and mapping forms; spelling-based strictness; the canonical external-call allowance; alias shadowing; and the required reviewed-exception process.

### R3 — merge instruction

The branch `PARALLEL_WORK_GUIDE.md` must win the expected future add/add conflict with main. It is the valid non-authoritative guide and references `CONSOLIDATED_PLAN.md`; main's stale file references `LAB_PLAN.md`. No merge or rebase was performed.

### Report validator hardening

- The B0 report schema is recursively closed at the top level and for repository, blocker, B0 item, local probe, workflow, verification summary, and verification-command objects. Unknown fields such as `hosted_evidence` fail at any nested level.
- Optional local artifacts remain optional when absent. Before reading a present artifact, every existing path component is checked for symlinks and resolved containment under the repository root; parent-symlink escapes fail closed.
- Hosted-key semantic checks remain in addition to the closed schema.
- The implementation/evidence relationship is strictly a direct-parent relationship with an exact three-file evidence-only diff.

### Follow-up TDD RED evidence

External API and documentation RED command:

```sh
uv run --locked --group dev pytest -q --tb=short tests/policy/test_import_boundaries.py \
  -k 'external_api_call_allowance or static_mlx_core_eval or runtime_probe_allows_multiple_legitimate or mlx_eval_allowance_rejects or research_log_records'
```

```text
FFFFFF..........F                                                        [100%]
7 failed, 10 passed, 138 deselected in 0.96s
```

Failures were the missing canonical set, all four legitimate engine import/call forms, multiple runtime-probe calls, and incomplete research-log documentation.

Report/review hardening RED command:

```sh
uv run --locked --group dev pytest -q --tb=short tests/policy/test_b0_integration_report.py \
  -k 'schema_rejects_unknown or direct_parent_not_head or parent_symlink_escape or cross_review'
```

```text
FFFF                                                                     [100%]
4 failed, 6 deselected in 1.28s
```

Failures proved unknown fields were not schema-rejected, `evaluated_commit == HEAD` was accepted, parent-symlink escape was followed, and the delivered review was not yet preserved.

A further cross-scope regression was added after the initial implementation:

```text
......F....                                                              [100%]
1 failed, 10 passed in 1.14s
```

It proved a function-local `mlx.core` import incorrectly authorized a same-spelled receiver in a different function.

### Follow-up GREEN evidence

```text
external API focused: 17 passed, 139 deselected in 2.74s
strict policy documentation: 1 passed in 0.01s
report schema/direct-parent/symlink: 3 passed, 7 deselected in 0.54s
durable review/merge instruction: 1 passed in 0.02s
complete import-boundary suite: 156 passed in 17.32s
complete runtime-probe suite: 19 passed in 0.13s
pre-evidence report follow-ups: 9 passed, 1 deselected in 0.84s
ruff: All checks passed
```

The pre-evidence direct governance run then failed only for the deliberately stale report relationship/digests, proving regeneration was required before the evidence-only child.

### Regenerated local probes

Both probes were regenerated at follow-up implementation commit `68fd1cf9cec7949e799e5da42a2c4c3b87b742ab`:

- NumPy 2.5.1, Darwin arm64: `4bdf295dccb51e41f1be1151064655df12bb90e6ef589f1d3f31c47b2db40d71`
- MLX 0.32.0, Darwin arm64: `f0a8fb25a135a43ffb586d10b81d19d8a73d433ed706a41772b788b71dd2ed27`

Both remain `bootstrap_probe_only` local contract evidence. No hosted evidence was created.

### Follow-up final verification

Final post-commit verification output is appended below after creating the evidence-only child. Gate B0 remains open on B0.2/B0.5, `parallel_handoff_ready` remains false, and Phase 0 remains unstarted.

#### Final lock and sync

```text
uv lock --check
Resolved 18 packages in 5ms

uv sync --all-packages --group dev --locked
Resolved 18 packages in 6ms
Audited 17 packages in 0.28ms
```

#### Final full suite and policies

```text
uv run --locked --group dev pytest -q
249 passed in 60.78s

uv run --locked --group dev ruff check .
All checks passed!

uv run --locked --group dev python scripts/policy/validate_import_boundaries.py
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

python3 scripts/policy/validate_repository_governance.py
Repository governance policy: PASS

uv run --locked --group dev python scripts/policy/validate_backend_capabilities.py
Backend capability policy: PASS (8 manifests, 4 dual-backend engine declarations)

scripts/ci/b0-policy-checks.sh
235 passed, 2 deselected in 24.09s
```

#### Final focused report/workflow contracts

```text
uv run --locked --group dev pytest -q \
  tests/policy/test_b0_integration_report.py \
  tests/policy/test_b0_ci_bootstrap.py
16 passed in 26.80s
```

#### Final eight-script matrix from `/tmp`

```text
shared-checks.sh: 1 passed
benchmarks-checks.sh: 5 passed
compare-checks.sh: 1 passed
contenders-checks.sh: 1 passed
prism-checks.sh: 1 passed
topograph-checks.sh: 1 passed
stratograph-checks.sh: 1 passed
primordia-checks.sh: 1 passed
```

Every script also reported `All checks passed!` and resolved the same 18-package lock.

#### Final evidence relationship and state

- Evidence child: the commit containing this appended section, direct parent `68fd1cf9cec7949e799e5da42a2c4c3b87b742ab`.
- Exact evidence-only diff: `.superpowers/sdd/task-6-report.md`, `governance/b0-report.json`, `governance/b0-status.yaml`.
- `git diff --check`: no output, exit 0.
- Working tree: clean on `agent/b0-bootstrap` before this report-only amend.
- No remote configured and no push performed.
- Exact blockers remain B0.2 `authoritative_remote_url_absent` and B0.5 `hosted_ci_not_executed`.
- Gate B0 remains open, parallel handoff remains false, and Phase 0 remains unstarted.
