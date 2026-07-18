# Task 5 Report — Dual-host CI bootstrap and runtime evidence

## Status

IMPLEMENTED and locally verified on `agent/b0-bootstrap`.

Gate B0.5 remains truthfully `open` with `open_reason: hosted_ci_not_executed`. The repository has no configured remote, so no hosted GitHub Actions run IDs or hosted artifacts exist. B0.2 also remains open, and overall B0 remains open.

## Implemented scope

- Added production GitHub Actions workflows:
  - `.github/workflows/linux-trust.yml`
  - `.github/workflows/macos-engines.yml`
- Added pinned Python 3.13/uv 0.5.13 locked bootstrap on both hosts.
- Added exact host split:
  - Linux: Shared, shared-benchmarks, Compare, Contenders, Stratograph, Primordia; NumPy probe; MLX absence check.
  - macOS 15 arm64: Prism, Topograph; MLX presence check and MLX probe.
- Added `scripts/ci/runtime_probe.py` with real NumPy and MLX sum-of-squares operations, atomic JSON output, current-run provenance validation, package import/version validation, manifest digest validation, and fail-closed behavior.
- Added `scripts/policy/validate_backend_capabilities.py` for all eight manifests and package metadata.
- Added canonical dependency-light backend/package contract data in `EvoNN-Shared/src/evonn_shared/backend_contract.py` and reused it from validators, probe tooling, and tests.
- Added executable `scripts/ci/b0-policy-checks.sh`, sourcing `_common.sh`, resolving the repository from any current directory, and running all root policy/CI tests except the explicitly marked recursive self-test and eight-script cross-host local matrix.
- Added focused policy, workflow, contract, and runtime tests.
- Added NumPy and Darwin/arm64-marked MLX dependencies to all four engine packages and regenerated the single root `uv.lock`.
- Kept Contenders without scikit-learn.
- Updated B0 governance truthfully without closing B0.2 or B0.5.
- Added `.artifacts/` to `.gitignore`; machine-specific local artifacts remain uncommitted.

## Hosted workflow pins and runner contracts

Both workflows use immutable action SHAs:

- `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd` (`v6.0.2`)
- `astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990` (`v8.3.2`)
- `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02` (`v4.6.2`)

Exact runners:

- Linux trust lane: `ubuntu-latest`
- macOS engine lane: `macos-15`

Both install Python 3.13, configure uv `0.5.13`, run `uv sync --all-packages --group dev --locked`, execute common policies, run only their explicit host-lane scripts, generate and validate a real runtime probe, and upload a named runtime artifact.

## Dependency and marker proof

Every engine package now declares exactly:

```toml
dependencies = [
    "evonn-shared",
    "numpy>=2.1,<3",
    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
]
```

`uv.lock` was regenerated with uv 0.5.13 and resolves 18 packages. Relevant lock entries preserve:

```text
mlx marker = "platform_machine == 'arm64' and sys_platform == 'darwin'"
numpy marker = "sys_platform == 'darwin' or sys_platform == 'linux'"
mlx specifier = ">=0.25,<1"
numpy specifier = ">=2.1,<3"
```

Local locked versions exercised:

- NumPy `2.5.1`
- MLX `0.32.0`
- MLX Metal `0.32.0`

The Linux workflow synchronizes the all-package lock and then fails if `uv pip show mlx` succeeds. The macOS workflow fails unless both `uname -m` and Python `platform.machine()` report `arm64`, and it requires `uv pip show mlx` to succeed.

All four engine capability manifests now state the real NumPy dependency and the exact Darwin/arm64 MLX condition while retaining `implemented: false` and all evidence claims false. Contenders remains unimplemented and has no scikit-learn dependency.

## Runtime probe contract

Each generated probe contains:

- schema/probe kind and full repository commit;
- local placeholders or exact hosted workflow name/run ID/attempt;
- start/end UTC timestamps that bracket the numerical operation;
- pass status;
- OS name/version, kernel, architecture, and host logical CPU count;
- Python implementation/version and uv version;
- selected package/system and validated identities for all seven workspace distributions/modules/versions;
- exercised backend class/distribution/version;
- device and precision mode;
- actual topology `single_process` with exact worker count `1`;
- SHA-256 hostname fingerprint without exposing the hostname;
- repository-relative capability manifest path and SHA-256 digest;
- `qualification: bootstrap_probe_only`;
- `evidence.class: contract` and an explicit non-scientific/non-qualification statement;
- a validated sum-of-squares result over `[1.0, 2.0, 3.0]`, expected/actual `14.0`.

Generation removes stale output first, imports and validates all declared workspace packages, executes a real backend operation, validates the exact result, captures end time afterward, and only then atomically publishes JSON. MLX executes `mx.eval(result)` before extracting the scalar.

Validation rejects missing fields, incorrect host/Python/uv data, current-commit mismatch, current hosted-workflow metadata mismatch, manifest escape/symlink/digest mismatch, any manifest path other than the selected system's exact canonical `PACKAGE_BY_SYSTEM[system].manifest_path`, backend/platform mismatch, fake hosted metadata in local mode, malformed systems, non-integer/boolean/non-one worker counts, package identity drift, and unproved numerical results.

## Task 4 strict production-language policy

The strict primitive prohibition remains enabled over every shipped Python script. Task 5 required the external MLX API method `mlx.core.eval`, which shares a spelling with Python's forbidden dynamic-execution primitive.

The validator precomputes exactly one approved AST node and exempts only that node identity. Approval requires all of the following simultaneously:

- exact path `scripts/ci/runtime_probe.py`;
- exactly one top-level function named `_run_mlx_operation`;
- exactly one direct local `import mlx.core as mx` in that function;
- exactly one `mx.eval` call in the entire file;
- that call must be a direct statement in `_run_mlx_operation`;
- exact shape `mx.eval(result)` with one positional `Name("result")` and no keywords.

Any second `mx.eval`, a different function/file, an alias, changed/missing import, different argument, extra argument, keyword argument, or moved/nested call yields no approved node and therefore fails under the unchanged reserved-primitive rule. Python `eval` remains forbidden everywhere, including the runtime probe. No whole-file exemption, path-only exemption, alias-wide exception, or general weakening was added.

## TDD evidence

### Initial RED — workflows, validator, and probe absent

After adding tests first, the corrected focused RED command was:

```sh
uv run --locked --group dev pytest -q \
  tests/policy/test_b0_ci_bootstrap.py::test_linux_workflow_has_exact_trust_lane_contract \
  tests/policy/test_backend_capabilities.py::test_all_capability_manifests_match_package_metadata \
  tests/ci/test_runtime_probe.py::test_probe_write_is_deterministic_complete_atomic_and_hostname_safe
```

Result:

```text
FFF                                                                      [100%]
3 failed in 0.06s
```

The failures were the expected missing workflow, missing backend validator, and missing runtime probe implementation.

### MLX strict-policy RED

Before the exact call-site treatment, the MLX static evaluation regression failed:

```text
F                                                                        [100%]
1 failed in 0.12s
```

The policy reported `eval from mlx.core`. The final implementation instead uses `mx.eval` and permits only the exact runtime-probe call site.

### uv output parsing RED

The first real CLI execution exposed uv 0.5.13 build metadata:

```text
RuntimeError: unexpected uv version output: 'uv 0.5.13 (c456bae5e 2024-12-27)'
```

A parser regression was added first:

```text
F                                                                        [100%]
AttributeError: module 'scripts.ci.runtime_probe' has no attribute 'parse_uv_version'
```

After implementation:

```text
.                                                                        [100%]
1 passed in 0.01s
```

### Review-driven RED

Before fixing the independent review findings, focused regressions produced:

```text
FFFFFFFFFF                                                               [100%]
10 failed in 0.27s
```

These failures covered:

- complete nonrecursive B0 test discovery;
- missing canonical backend contract;
- overly broad MLX eval treatment;
- timestamps not bracketing execution;
- hosted provenance not bound to the current environment;
- missing package import/version exercise;
- invalid and boolean worker counts.

### Blocking re-review RED

The coordinator's blocking re-review received new tests before implementation.

The MLX structural-drift selection produced:

```text
.FFFFF.F.                                                                [100%]
6 failed, 3 passed, 139 deselected in 0.50s
```

The failures proved that path-only approval incorrectly accepted a second `mx.eval`, changed arguments, changed import alias, and a renamed function.

The canonical-manifest selection produced:

```text
FFF                                                                      [100%]
3 failed, 164 deselected in 0.90s
```

The failures proved generation and validation accepted a copied in-repository manifest with matching system/content/digest, and accepted a symlink to the canonical manifest.

### Final focused GREEN

```sh
uv run --locked --group dev pytest -q \
  tests/policy/test_b0_ci_bootstrap.py \
  tests/policy/test_backend_contract.py \
  tests/policy/test_backend_capabilities.py \
  tests/ci/test_runtime_probe.py
```

```text
...............................                                          [100%]
31 passed in 12.29s
```

The complete strict import-boundary suite also passed:

```text
........................................................................ [ 48%]
........................................................................ [ 97%]
....                                                                     [100%]
148 passed in 7.48s
```

## Review findings fixed

The final review cycle found and fixed all concrete issues:

1. B0 policy CI now discovers `tests/policy` and `tests/ci` instead of using a brittle legacy file list.
2. The recursive B0 self-test and cross-host all-eight-script matrix are explicitly marked and excluded only inside `b0-policy-checks.sh`; the full local suite still runs both.
3. Common B0 policy execution no longer indirectly violates the hosted lane split.
4. The exact set of all `*-checks.sh` files remains governed; unknown/misspelled scripts fail the test.
5. `b0-policy-checks.sh` sources `_common.sh` rather than duplicating repository-root bootstrap logic.
6. Probe package/system labels are backed by real imports and distribution/module/version checks for all seven packages.
7. Backend/package/manifest constants are centralized in the Shared-owned canonical contract module.
8. The MLX exception is a precomputed single AST node identity requiring the exact function, local import, call count, direct statement, argument, and keyword shape; every structural drift fails closed.
9. Timestamps now bracket the numerical operation and result validation.
10. Hosted commit/workflow/run/attempt data are compared with the current GitHub environment.
11. Actual worker count is `1`; host logical CPU capacity is recorded separately.
12. Boolean worker counts are rejected using exact integer type validation.
13. Malformed non-string system data returns a deterministic diagnostic rather than a traceback.
14. Unrequested verification-skill documentation was removed; only the requested Task 5 report is added.
15. Probe generation and validation now require the selected system's exact canonical manifest path and reject copied manifests, noncanonical paths, symlinks, and escapes even when bytes/digests match.

## Local runtime evidence

These are honest local Apple Silicon runs. Both record the actual Darwin host; the NumPy run uses local workflow placeholders and Linux-equivalent backend/bootstrap semantics but does not pretend the host is Linux.

### NumPy portability/bootstrap probe

Command:

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

Absolute path:

`/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/.artifacts/b0/local/numpy/b0-runtime-probe.json`

SHA-256:

`57aaeafdb03b9705bed5d0863131b9aeea59198d1fa9e6b4a7387afc97f6c677`

### MLX native bootstrap probe

Command:

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

Absolute path:

`/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/.artifacts/b0/local/mlx/b0-runtime-probe.json`

SHA-256:

`08b057a3f0450b80e9bd0b5caa1828ca9a4da98f880c2013534e5cb76ee4f3bf`

Both local artifacts record:

- actual host `Darwin`, `arm64`;
- local workflow placeholders only;
- repository HEAD at probe time `e28818c0d43605142172c048d25241ceef78fb9a` while Task 5 changes were still uncommitted;
- contract/bootstrap evidence only, not hosted or scientific qualification.

### Fail-closed CLI observation

Validating the NumPy artifact as MLX produced:

```text
Runtime probe validation: FAIL (1 violations)
ERROR: backend does not match expected backend mlx
exit=1
```

## Required verification

Final exact matrix:

### `uv lock --check`

```text
Resolved 18 packages in 6ms
```

PASS.

### `uv sync --all-packages --group dev --locked`

```text
Resolved 18 packages in 6ms
Audited 17 packages in 0.55ms
```

PASS.

### `uv run --locked --group dev pytest -q`

```text
........................................................................ [ 31%]
........................................................................ [ 62%]
........................................................................ [ 93%]
...............                                                          [100%]
231 passed in 25.92s
```

PASS.

### `uv run --locked --group dev ruff check .`

```text
All checks passed!
```

PASS.

### `uv run --locked --group dev python scripts/policy/validate_import_boundaries.py`

```text
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)
```

PASS.

### `python3 scripts/policy/validate_repository_governance.py`

```text
Repository governance policy: PASS
```

PASS.

### `uv run --locked --group dev python scripts/policy/validate_backend_capabilities.py`

```text
Backend capability policy: PASS (8 manifests, 4 dual-backend engine declarations)
```

PASS.

### `scripts/ci/b0-policy-checks.sh`

```text
Resolved 18 packages in 5ms
Repository governance policy: PASS
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)
Backend capability policy: PASS (8 manifests, 4 dual-backend engine declarations)
........................................................................ [ 33%]
........................................................................ [ 66%]
........................................................................ [ 99%]
.                                                                        [100%]
217 passed, 2 deselected in 11.82s
```

PASS. The two deselections are intentionally the recursive B0 script self-test and the all-eight-script cross-host local matrix; both run in the complete local pytest suite.

## All eight existing check scripts from outside the repository

Each absolute script path was launched with current directory `/tmp`.

### `shared-checks.sh`

```text
Resolved 18 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### `benchmarks-checks.sh`

```text
Resolved 18 packages in 5ms
All checks passed!
.....                                                                    [100%]
5 passed in 0.83s
```

### `compare-checks.sh`

```text
Resolved 18 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### `contenders-checks.sh`

```text
Resolved 18 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### `prism-checks.sh`

```text
Resolved 18 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### `topograph-checks.sh`

```text
Resolved 18 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### `stratograph-checks.sh`

```text
Resolved 18 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### `primordia-checks.sh`

```text
Resolved 18 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

All eight passed.

## Governance state

`governance/b0-status.yaml` now records:

- overall B0: `open`;
- B0.2: `open`, `authoritative_remote_url_absent`;
- B0.3: `closed`;
- B0.4: `closed`;
- B0.5: `open`, `hosted_ci_not_executed`;
- B0.5 evidence explicitly distinguishes implemented workflows and honest local probes from absent hosted execution/artifacts.

No hosted run ID, attempt, URL, artifact, or qualification claim was fabricated.

## Files changed

- `.gitignore`
- `.github/workflows/linux-trust.yml`
- `.github/workflows/macos-engines.yml`
- `pyproject.toml`
- `uv.lock`
- `EvoNN-Shared/src/evonn_shared/backend_contract.py`
- `EvoNN-Prism/pyproject.toml`
- `EvoNN-Prism/backend-capabilities.json`
- `EvoNN-Topograph/pyproject.toml`
- `EvoNN-Topograph/backend-capabilities.json`
- `EvoNN-Stratograph/pyproject.toml`
- `EvoNN-Stratograph/backend-capabilities.json`
- `EvoNN-Primordia/pyproject.toml`
- `EvoNN-Primordia/backend-capabilities.json`
- `governance/b0-status.yaml`
- `scripts/ci/b0-policy-checks.sh`
- `scripts/ci/runtime_probe.py`
- `scripts/policy/validate_backend_capabilities.py`
- `scripts/policy/validate_import_boundaries.py`
- `tests/ci/test_runtime_probe.py`
- `tests/policy/test_b0_ci_bootstrap.py`
- `tests/policy/test_backend_capabilities.py`
- `tests/policy/test_backend_contract.py`
- `tests/policy/test_import_boundaries.py`
- `tests/policy/test_repository_governance.py`
- `tests/policy/test_workspace_skeletons.py`
- `.superpowers/sdd/task-5-report.md`

## Self-review

- Confirmed branch remains `agent/b0-bootstrap`.
- Confirmed no remote is configured and nothing was pushed.
- Confirmed both workflows contain real operations, exact immutable action pins, exact runners, pinned uv, Python 3.13, locked all-package sync, explicit host splits, real probe generation/validation, and immutable artifact upload actions.
- Confirmed Linux checks installed-environment MLX absence and macOS requires arm64 plus installed MLX.
- Confirmed one root lockfile and no package-local lockfiles.
- Confirmed canonical backend constants eliminate drift between package metadata, manifests, validator, runtime probe, and tests.
- Confirmed all seven package identities are imported and version-validated before backend execution.
- Confirmed probe generation cannot retain a stale passed artifact after an operation failure.
- Confirmed start/end ordering brackets the operation in a deterministic regression.
- Confirmed hosted validation binds commit and workflow metadata to the current environment.
- Confirmed exact worker count and boolean rejection.
- Confirmed the Task 4 primitive ban exempts only the single precomputed AST attribute node matching the exact `_run_mlx_operation` import/call/count/argument structure.
- Confirmed generation and validation require each system's exact canonical manifest path and reject copied manifests and symlinks even when target bytes match.
- Confirmed the B0 policy script cannot recurse and cannot indirectly defeat the hosted lane split.
- Confirmed `git diff --check` is clean.

## Concerns / remaining work

- B0.5 cannot close until the repository is hosted and both workflows execute successfully with collected uploaded artifacts.
- B0.2 remains open until a real authoritative remote URL exists.
- Local artifacts are intentionally ignored and machine-specific; their commit field records the real pre-commit HEAD used during local validation, not the later Task 5 commit.
- These probes establish bootstrap/runtime contract evidence only. They do not qualify scientific correctness, backend conformance, performance, or Phase 0 exports.
