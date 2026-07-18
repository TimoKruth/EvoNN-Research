# Task 3 Report — Workspace Package Skeletons

## Status

DONE. Gate B0.3 is closed with local executable evidence. Overall Gate B0 remains open: B0.2, B0.4, and B0.5 remain open.

## Implementation summary

- Added one Python `>=3.13` uv workspace at the repository root with exactly seven Python members, one root `uv.lock`, Linux/Darwin resolution environments, a `dev` dependency group (`pytest`, `PyYAML`, `ruff`), pytest importlib collection, and ruff configuration.
- Added seven hatchling-backed `src/`-layout distributions with the exact required distribution/import names. Each has a minimal identity export, an installed-package import test, a non-authoritative B0 config marker, a truthful skeleton README, and a capability manifest.
- Added the data-only `shared-benchmarks/` skeleton with preserved empty directories and no package metadata or import markers.
- Added `evonn_shared.benchmarks.resolve_data_root` and `validate_data_skeleton`; validation checks required B0 paths and rejects package markers or runtime Python outside the allowed data-skeleton test.
- Added eight independently executable check scripts. A shared shell helper centralizes repository-root resolution and locked uv invocations; every named script performs focused ruff, pytest, and import/data-layout validation.
- Added root contract tests covering workspace membership, package metadata/import identity, benchmark resolution/invariants, marker rejection, all eight manifests, behavioral execution of all eight scripts from another current directory, and lockfile currency.
- Updated the validated B0 state to close B0.3 only. No Task 4 import-policy suite, Task 5 CI workflow, MLX dependency/probe, or runtime qualification was added.

## TDD evidence

### RED — workspace contract before package/production files

Command:

```sh
uvx --python 3.13 --from pytest pytest -q --tb=line tests/policy/test_workspace_skeletons.py
```

Exact result summary and failure causes:

```text
FFFFFFFFFFFFF                                                            [100%]
=================================== FAILURES ===================================
E   FileNotFoundError: [Errno 2] No such file or directory: '.../pyproject.toml'
E   FileNotFoundError: [Errno 2] No such file or directory: '.../EvoNN-Shared/pyproject.toml'
E   FileNotFoundError: [Errno 2] No such file or directory: '.../EvoNN-Compare/pyproject.toml'
E   FileNotFoundError: [Errno 2] No such file or directory: '.../EvoNN-Contenders/pyproject.toml'
E   FileNotFoundError: [Errno 2] No such file or directory: '.../EvoNN-Prism/pyproject.toml'
E   FileNotFoundError: [Errno 2] No such file or directory: '.../EvoNN-Topograph/pyproject.toml'
E   FileNotFoundError: [Errno 2] No such file or directory: '.../EvoNN-Stratograph/pyproject.toml'
E   FileNotFoundError: [Errno 2] No such file or directory: '.../EvoNN-Primordia/pyproject.toml'
E   ModuleNotFoundError: No module named 'evonn_shared'
E   ModuleNotFoundError: No module named 'evonn_shared'
E   FileNotFoundError: [Errno 2] No such file or directory: '.../EvoNN-Shared/backend-capabilities.json'
E   AssertionError: assert set() == {'benchmarks-checks.sh', ...}
E   AssertionError: assert [] == [PosixPath('.../uv.lock')]
=========================== short test summary info ============================
FAILED tests/policy/test_workspace_skeletons.py::test_root_is_python_313_uv_workspace_with_exact_members
FAILED tests/policy/test_workspace_skeletons.py::test_package_metadata_and_installed_import_identity[EvoNN-Shared-package0]
FAILED tests/policy/test_workspace_skeletons.py::test_package_metadata_and_installed_import_identity[EvoNN-Compare-package1]
FAILED tests/policy/test_workspace_skeletons.py::test_package_metadata_and_installed_import_identity[EvoNN-Contenders-package2]
FAILED tests/policy/test_workspace_skeletons.py::test_package_metadata_and_installed_import_identity[EvoNN-Prism-package3]
FAILED tests/policy/test_workspace_skeletons.py::test_package_metadata_and_installed_import_identity[EvoNN-Topograph-package4]
FAILED tests/policy/test_workspace_skeletons.py::test_package_metadata_and_installed_import_identity[EvoNN-Stratograph-package5]
FAILED tests/policy/test_workspace_skeletons.py::test_package_metadata_and_installed_import_identity[EvoNN-Primordia-package6]
FAILED tests/policy/test_workspace_skeletons.py::test_shared_benchmarks_resolves_and_validates_data_only_layout
FAILED tests/policy/test_workspace_skeletons.py::test_shared_benchmarks_rejects_python_package_markers
FAILED tests/policy/test_workspace_skeletons.py::test_all_backend_manifests_are_truthful_b0_declarations
FAILED tests/policy/test_workspace_skeletons.py::test_all_named_check_scripts_execute_real_locked_checks_from_another_directory
FAILED tests/policy/test_workspace_skeletons.py::test_single_root_lockfile_is_current
13 failed in 0.05s
```

The failures were expected and were caused by the absent workspace, packages, data helper/skeleton, manifests, scripts, and lockfile.

### Intermediate defect found by the contract test

The first implementation run exposed that uv 0.5.13 resolves `--group dev` relative to a selected `--package`; the root-only group was therefore unavailable in package-selected script runs:

```text
...........F.                                                            [100%]
benchmarks-checks.sh failed
stderr:
Resolved 15 packages in 5ms
error: Group `dev` is not defined in the project's `dependency-group` table
1 failed, 12 passed in 0.46s
```

The scripts were corrected to use current workspace-wide `uv run --all-packages --group dev --locked` semantics while keeping the checks focused on one package/data skeleton.

### GREEN — workspace contract

Command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_workspace_skeletons.py
```

Exact output:

```text
.............                                                            [100%]
13 passed in 5.34s
```

### RED/GREEN — B0.3 state transition

Before editing `governance/b0-status.yaml`, the updated governance expectation failed exactly because B0.3 was still open:

```text
F                                                                        [100%]
FAILED tests/policy/test_repository_governance.py::test_local_only_authority_keeps_b02_open_and_requires_null_url
1 failed in 0.77s
```

After the status update, the complete suite passed (see final verification).

## Required verification

All commands ran from the repository root unless noted.

### Root lock check

```sh
uv lock --check
```

```text
Resolved 15 packages in 5ms
```

Result: PASS.

### Locked all-package sync with the current dependency group convention

```sh
uv sync --all-packages --group dev --locked
```

```text
Resolved 15 packages in 5ms
Audited 14 packages in 0.26ms
```

Result: PASS.

### Complete pytest suite

```sh
uv run --locked --group dev pytest -q
```

```text
...............................................                          [100%]
47 passed in 4.44s
```

Result: PASS.

### Complete ruff check

```sh
uv run --locked --group dev ruff check .
```

```text
All checks passed!
```

Result: PASS.

## Explicit installed-package import verification

Commands:

```sh
uv run --locked --package evonn-shared python -c "import evonn_shared; assert evonn_shared.SYSTEM == 'shared' and evonn_shared.__version__ == '0.0.0'"
uv run --locked --package evonn-compare python -c "import evonn_compare; assert evonn_compare.SYSTEM == 'compare' and evonn_compare.__version__ == '0.0.0'"
uv run --locked --package evonn-contenders python -c "import evonn_contenders; assert evonn_contenders.SYSTEM == 'contenders' and evonn_contenders.__version__ == '0.0.0'"
uv run --locked --package evonn-prism python -c "import prism; assert prism.SYSTEM == 'prism' and prism.__version__ == '0.0.0'"
uv run --locked --package evonn-topograph python -c "import topograph; assert topograph.SYSTEM == 'topograph' and topograph.__version__ == '0.0.0'"
uv run --locked --package evonn-stratograph python -c "import stratograph; assert stratograph.SYSTEM == 'stratograph' and stratograph.__version__ == '0.0.0'"
uv run --locked --package evonn-primordia python -c "import evonn_primordia; assert evonn_primordia.SYSTEM == 'primordia' and evonn_primordia.__version__ == '0.0.0'"
```

Exact aggregate output:

```text
all seven package imports: PASS
```

Each command exited 0.

## Eight independently invocable check scripts

All scripts were launched by absolute path while the current directory was `/tmp`, proving repository-root resolution.

### `scripts/ci/shared-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### `scripts/ci/benchmarks-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### `scripts/ci/contenders-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### `scripts/ci/compare-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### `scripts/ci/prism-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### `scripts/ci/topograph-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### `scripts/ci/stratograph-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### `scripts/ci/primordia-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

All eight scripts exited 0, are executable, use the root lock, and perform real ruff + pytest + import/data validation.

## Files changed

Root/tooling/governance:

- `.gitignore`
- `pyproject.toml`
- `uv.lock`
- `governance/b0-status.yaml`
- `tests/policy/test_repository_governance.py`
- `tests/policy/test_workspace_skeletons.py`

For each of `EvoNN-Shared`, `EvoNN-Compare`, `EvoNN-Contenders`, `EvoNN-Prism`, `EvoNN-Topograph`, `EvoNN-Stratograph`, and `EvoNN-Primordia`:

- `pyproject.toml`
- `README.md`
- `configs/README.md`
- `backend-capabilities.json`
- `src/<required-module>/__init__.py`
- `tests/test_import.py`

Additional Shared helper:

- `EvoNN-Shared/src/evonn_shared/benchmarks.py`

Data-only skeleton:

- `shared-benchmarks/README.md`
- `shared-benchmarks/backend-capabilities.json`
- `shared-benchmarks/catalog/.gitkeep`
- `shared-benchmarks/suites/parity/.gitkeep`
- `shared-benchmarks/lm_cache/.gitkeep`
- `shared-benchmarks/migration/.gitkeep`
- `shared-benchmarks/tests/test_skeleton.py`

Check scripts:

- `scripts/ci/_common.sh`
- `scripts/ci/shared-checks.sh`
- `scripts/ci/benchmarks-checks.sh`
- `scripts/ci/contenders-checks.sh`
- `scripts/ci/compare-checks.sh`
- `scripts/ci/prism-checks.sh`
- `scripts/ci/topograph-checks.sh`
- `scripts/ci/stratograph-checks.sh`
- `scripts/ci/primordia-checks.sh`

Report:

- `.superpowers/sdd/task-3-report.md`

## Self-review

- `git diff --check`: PASS; no whitespace errors.
- Confirmed exactly seven `[tool.uv.workspace]` members and no `shared-benchmarks` workspace member.
- Confirmed a single root `uv.lock` and no package-local lockfiles.
- Confirmed Shared has no EvoNN dependency; every other skeleton depends only on `evonn-shared` via `{ workspace = true }`.
- Confirmed no engine-to-engine dependencies/imports and no engine/search/genome/runtime implementation was introduced.
- Confirmed `shared-benchmarks/` has no `pyproject.toml`, `__init__.py`, setup metadata, or runtime Python file; only its required test is Python.
- Confirmed all manifests parse as JSON, use schema version `1.0.0`, mark every declared execution capability `implemented: false`, and explicitly deny scientific, portability, and producer-conformance evidence.
- Confirmed MLX is not in dependency resolution and is named as deferred to Task 5; NumPy and scikit-learn execution are likewise not claimed or installed.
- Confirmed B0.3 alone transitioned to closed; top-level B0 and B0.2/B0.4/B0.5 remain open.
- Confirmed no workflow, hosted-CI claim, runtime probe, `b0-policy-checks.sh`, import-direction test suite, benchmark schema/loader, CLI, or scientific behavior was added.

## Concerns

None. The installed local uv is 0.5.13, and the implemented workspace/dependency-group commands were executed successfully with it; the metadata also follows the current documented uv workspace model requested by the brief.

## Review-fix addendum

A post-implementation review found two mandatory contract gaps and one small check-script interface issue. They were corrected with a fresh TDD cycle without expanding into Task 4 or Task 5.

### Review-fix RED

Tests were added first for malformed required path types, the exact eight-manifest contract, and use of the distribution argument by the shared package-check helper.

Command:

```sh
uv run --locked --group dev pytest -q --tb=short shared-benchmarks/tests/test_skeleton.py tests/policy/test_workspace_skeletons.py::test_all_backend_manifests_match_the_exact_truthful_b0_contract tests/policy/test_workspace_skeletons.py::test_package_check_helper_rejects_unknown_distribution_identity
```

Exact output:

```text
.FFFF                                                                    [100%]
=================================== FAILURES ===================================
_____________ test_required_directory_replaced_by_file_is_rejected _____________
shared-benchmarks/tests/test_skeleton.py:20: in test_required_directory_replaced_by_file_is_rejected
    with pytest.raises(ValueError, match="Required shared benchmark directory is not a directory: catalog"):
E   Failed: DID NOT RAISE ValueError
_____________ test_required_file_replaced_by_directory_is_rejected _____________
shared-benchmarks/tests/test_skeleton.py:30: in test_required_file_replaced_by_directory_is_rejected
    with pytest.raises(ValueError, match="Required shared benchmark file is not a file: README.md"):
E   Failed: DID NOT RAISE ValueError
_______ test_all_backend_manifests_match_the_exact_truthful_b0_contract ________
tests/policy/test_workspace_skeletons.py:175: in test_all_backend_manifests_match_the_exact_truthful_b0_contract
    assert manifest == expected, relative_path
E   AssertionError: EvoNN-Contenders/backend-capabilities.json
E   assert {'schema_vers...', ...}], ...} == {'schema_vers...', ...}], ...}
E     Differing items:
E     {'capabilities': [{'id': 'sklearn_contender', 'platforms': ['darwin', 'linux'], 'implemented': False, 'dependency': 'scikit-learn (not declared until runtime implementation)', ...}]} != {'capabilities': [{'id': 'sklearn_contender', 'platforms': ['darwin', 'linux'], 'implemented': False, 'dependency': 'scikit-learn', ...}]}
_______ test_package_check_helper_rejects_unknown_distribution_identity ________
tests/policy/test_workspace_skeletons.py:194: in test_package_check_helper_rejects_unknown_distribution_identity
    assert result.returncode != 0
E   assert 0 != 0
=========================== short test summary info ============================
FAILED shared-benchmarks/tests/test_skeleton.py::test_required_directory_replaced_by_file_is_rejected
FAILED shared-benchmarks/tests/test_skeleton.py::test_required_file_replaced_by_directory_is_rejected
FAILED tests/policy/test_workspace_skeletons.py::test_all_backend_manifests_match_the_exact_truthful_b0_contract
FAILED tests/policy/test_workspace_skeletons.py::test_package_check_helper_rejects_unknown_distribution_identity
4 failed, 1 passed in 0.37s
```

These failures demonstrated all three review findings: `exists()` accepted wrong path types, manifests did not expose the exact separated `dependency`/`dependency_condition` contract, and the shell helper ignored its distribution argument.

### Review-fix implementation

- `validate_data_skeleton` now requires `is_dir()` for every required directory and `is_file()` for every required file, with separate, path-specific errors.
- Data-local tests now replace `catalog/` with a file and `README.md` with a directory and verify clear rejection messages.
- The policy contract now maps all eight manifest paths to exact complete JSON values: schema, system, runtime role, capability IDs, platforms, implemented state, dependency, dependency condition, and false evidence claims.
- Engine and Contenders manifests now separate package names (`mlx`, `numpy`, `scikit-learn`) from truthful `dependency_condition` declarations.
- `run_python_package_checks` now uses `importlib.metadata.version(distribution)` and requires it to equal the imported module version. A behavioral test proves an unknown distribution is rejected.
- B0.3 remains closed because the corrected contract and all verification lanes pass; B0.2/B0.4/B0.5 and overall B0 remain open.

Files changed by the review fix:

- `EvoNN-Shared/src/evonn_shared/benchmarks.py`
- `shared-benchmarks/tests/test_skeleton.py`
- `tests/policy/test_workspace_skeletons.py`
- `scripts/ci/_common.sh`
- `EvoNN-Contenders/backend-capabilities.json`
- `EvoNN-Prism/backend-capabilities.json`
- `EvoNN-Topograph/backend-capabilities.json`
- `EvoNN-Stratograph/backend-capabilities.json`
- `EvoNN-Primordia/backend-capabilities.json`
- `.superpowers/sdd/task-3-report.md`

### Review-fix GREEN

Command:

```sh
uv run --locked --group dev pytest -q --tb=short shared-benchmarks/tests/test_skeleton.py tests/policy/test_workspace_skeletons.py::test_all_backend_manifests_match_the_exact_truthful_b0_contract tests/policy/test_workspace_skeletons.py::test_package_check_helper_rejects_unknown_distribution_identity
```

Exact output:

```text
.....                                                                    [100%]
5 passed in 0.42s
```

### Review-fix final verification

```text
== uv lock --check ==
Resolved 15 packages in 6ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 5ms
Audited 14 packages in 0.27ms

== uv run --locked --group dev pytest -q ==
..................................................                       [100%]
50 passed in 6.12s

== uv run --locked --group dev ruff check . ==
All checks passed!

== explicit package imports ==
all seven distribution/module identities: PASS

== shared-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== benchmarks-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
...                                                                      [100%]
3 passed in 0.02s

== contenders-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== compare-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== prism-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s

== topograph-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s

== stratograph-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s

== primordia-checks.sh ==
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

Final review-fix result: PASS with no concerns.
