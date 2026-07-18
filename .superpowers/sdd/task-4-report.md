# Task 4 Report — Enforce Import-Direction Boundaries

## Status

DONE. Gate B0.4 is closed with permanent executable policy evidence. Gate B0 remains open: B0.2 and B0.5 remain open, and B0.3 evidence is unchanged.

## Implementation summary

- Added `scripts/policy/validate_import_boundaries.py`, an importable and directly runnable Python policy validator for the exact seven-member uv workspace.
- The validator authenticates the root workspace member list, rejects missing/extra/duplicate members, and checks each exact distribution, hatch wheel package path, and `src/` import-root identity.
- It parses every member's `project.dependencies`, normalizes PEP 508 names using PEP 503 rules, compares only exact internal distribution identities, and rejects forbidden internal dependency edges without confusing external names containing EvoNN substrings.
- It validates `[tool.uv.sources]` workspace declarations, requiring them to correspond to project dependencies, rejecting non-workspace identities, rejecting forbidden internal source edges, and requiring allowed internal dependencies to use `workspace = true`.
- It parses all production `.py` files under all seven `src/` trees with `ast`, covering both `import` and `from ... import ...` forms.
- It recognizes `importlib.import_module(...)`, `runpy.run_module(...)`, `__import__(...)`, `builtins.__import__(...)`, provider aliases, imported function aliases, and assigned callable aliases. Literal internal targets are checked against the same exact matrix; non-literal dynamic imports fail closed with a path/line diagnostic because their target cannot be validated.
- Literal relative `importlib.import_module` calls resolve both positional and keyword package arguments. Own-package relative imports remain allowed, forbidden package roots fail, and non-literal names/packages fail closed.
- It scans `project.dependencies`, every `project.optional-dependencies` group, root/member `dependency-groups`, and PEP 621 runtime module targets in `project.scripts`, `project.gui-scripts`, and every `project.entry-points.*` group.
- It rejects any workspace `exclude`, checks every list-valued/marker-specific uv workspace-source alternative independently, and rejects symlinked workspace members, package roots, or paths anywhere inside production `src/` trees.
- Diagnostics are aggregated, de-duplicated, byte-order sorted, and include repository-relative file, line, source distribution, forbidden target/edge, and import/dependency form. The CLI emits all violations before returning nonzero.
- Extended the existing canonical `evonn_shared.benchmarks` invariant with `find_data_skeleton_violations`, keeping layout definitions in one place. It rejects symbolic links, `__init__.py`, `pyproject.toml`, `setup.py`, `setup.cfg`, and runtime `.py` outside `shared-benchmarks/tests/`, while allowing test helpers inside that subtree.
- Added `tests/policy/test_import_boundaries.py` with the five mandatory named behavioral cases plus checked-in repository, exact workspace identity, deterministic multi-error diagnostics, and cross-current-directory CLI coverage.
- Updated the existing governance test and `governance/b0-status.yaml` to close B0.4 only. B0.2 and B0.5 remain open, overall B0 remains open, and no Task 5 workflow/probe was added.

## Exact allowed matrix enforced

| Source distribution | Allowed internal targets |
|---|---|
| `evonn-shared` | none |
| `evonn-compare` | `evonn-shared` |
| `evonn-contenders` | `evonn-shared` |
| `evonn-prism` | `evonn-shared` |
| `evonn-topograph` | `evonn-shared` |
| `evonn-stratograph` | `evonn-shared` |
| `evonn-primordia` | `evonn-shared` |

Own-import-root imports remain allowed. Standard-library and external dependencies are outside this internal-edge policy.

## TDD evidence

### RED — tests before validator/production policy

Command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py
```

Exact result summary:

```text
EEEEEEEEF                                                                [100%]
1 failed, 8 errors in 0.10s
```

All eight setup errors failed at the deliberate test fixture assertion:

```text
AssertionError: import boundary validator is not installed
```

The remaining CLI behavioral test failed because the requested executable did not exist:

```text
can't open file '.../scripts/policy/validate_import_boundaries.py': [Errno 2] No such file or directory
```

This was the expected RED state: the behavioral contract existed while the validator was absent.

### Intermediate GREEN defect

The first implementation run produced:

```text
......F..                                                                [100%]
1 failed, 8 passed in 0.25s
```

The data-only test found that `catalog/__init__.py` was reported twice—as both a package marker and a runtime Python file—so the structured invariant was corrected to emit one actionable violation per marker artifact.

A diagnostic capitalization mismatch was then exposed without changing the policy behavior:

```text
......F..                                                                [100%]
1 failed, 8 passed in 0.25s
```

The runtime-file diagnostic was normalized, after which the complete focused suite passed.

### GREEN — focused policy suite

Command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py
```

Exact output:

```text
.........                                                                [100%]
9 passed in 0.26s
```

### B0.4 status transition

The governance expectation was changed before the checked-in status. After B0.4 was changed to `closed` with `open_reason: null` and executable policy evidence, the focused governance suite passed:

```text
..........................                                               [100%]
26 passed in 3.80s
```

## Review-driven TDD hardening

A concurrent cross-file review identified boundary surfaces that required explicit fail-closed coverage. Regression tests were added before their fixes for assigned/provider dynamic aliases, `runpy`, relative dynamic imports, optional/group dependencies, list-valued uv sources, PEP 621 entry points, workspace excludes, and filesystem symlinks.

RED command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py -k 'dynamic_import_aliases or runpy_module_aliases or relative_importlib or pep621_runtime_entry_points or optional_and_group or workspace_exclude or symlink'
```

Exact result:

```text
FFFFFFFFF                                                                [100%]
9 failed, 9 deselected in 0.25s
```

The failures reproduced every reported bypass: only two of five dynamic alias forms were detected; all `runpy` calls were missed; a valid positional relative import was falsely rejected; entry points, optional/group dependencies, workspace excludes, and all symlink cases were missed; and list-valued workspace sources were collapsed rather than checked alternative-by-alternative.

GREEN command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py -k 'dynamic_import_aliases or runpy_module_aliases or relative_importlib or pep621_runtime_entry_points or optional_and_group or workspace_exclude or symlink'
```

Exact output:

```text
.........                                                                [100%]
9 passed, 9 deselected in 0.23s
```

A final keyword-form `runpy.run_module(mod_name=...)` regression was then added. Its RED output was:

```text
F                                                                        [100%]
1 failed in 0.10s
```

The failure showed that the call was rejected as unresolved instead of reporting its literal forbidden edge. After parsing the correct `mod_name` keyword, GREEN was:

```text
.                                                                        [100%]
1 passed in 0.07s
```

## Behavioral policy coverage

The focused tests prove:

- checked-in repository validation returns no diagnostics;
- engine `import sibling` and `from sibling import ...` violations fail;
- Shared cannot import Contenders, Compare, or any engine;
- Compare cannot import engine runtime and therefore remains on the CLI/file-artifact boundary;
- literal `importlib.import_module`, `runpy.run_module`, `__import__`, and `builtins.__import__` violations fail through direct, module-alias, imported-alias, and assigned-alias forms;
- non-literal dynamic imports fail closed with a clear target-not-validatable diagnostic;
- literal relative `importlib.import_module` calls resolve positional/keyword package arguments, allowing own-package relative imports while rejecting forbidden roots;
- forbidden normalized PEP 508 workspace dependencies fail across required, optional, and root/member dependency-group surfaces, including extras, versions, markers, mixed case, and punctuation normalization;
- an external distribution containing an internal name as a substring is not confused with that internal distribution;
- dangling, unknown, and forbidden `workspace = true` sources fail, with every list-valued marker alternative checked independently;
- PEP 621 script, GUI-script, and entry-point runtime module targets obey the same import matrix;
- missing, extra, and duplicate workspace members fail, and workspace `exclude` cannot hide a declared member;
- distribution/import package identity mismatches and symlinked workspace/member/source paths fail;
- `shared-benchmarks/` symlinks, package markers, package metadata, and runtime Python fail while Python under `tests/` remains allowed;
- diagnostics are stable across repeated runs, deterministically sorted, and aggregate multiple violations rather than stopping at the first;
- the CLI resolves the checked-in repository from its script path and accepts an explicit repository root while launched from another current directory.

## Direct CLI runtime observation

Happy path launched from `/tmp`:

```text
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)
```

Final fail-closed probe against a temporary repository containing an optional Prism→Topograph dependency, an assigned dynamic-loader bypass, and a symlinked benchmark directory:

```text
Import boundary policy: FAIL (3 violations)
ERROR: EvoNN-Prism/pyproject.toml:20: evonn-prism: forbidden dependency edge evonn-prism -> evonn-topograph in project.optional-dependencies.forbidden from requirement 'evonn-topograph'
ERROR: EvoNN-Prism/src/prism/assigned_bypass.py:3: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-topograph via importlib.import_module
ERROR: shared-benchmarks/catalog:1: shared-benchmarks: symbolic link found in data-only skeleton
exit=1
```

The probe demonstrated the actual CLI surface from a non-repository current directory, deterministic multi-error output, and a nonzero failure status.

## Required verification

All commands ran from the repository root unless explicitly noted.

### `uv lock --check`

```text
Resolved 15 packages in 5ms
```

Result: PASS.

### `uv sync --all-packages --group dev --locked`

```text
Resolved 15 packages in 5ms
Audited 14 packages in 0.28ms
```

Result: PASS.

### `uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py`

```text
..................                                                       [100%]
18 passed in 0.50s
```

Result: PASS.

### `uv run --locked --group dev pytest -q`

```text
....................................................................     [100%]
68 passed in 6.88s
```

Result: PASS.

### `uv run --locked --group dev ruff check .`

```text
All checks passed!
```

Result: PASS.

### `uv run --locked --group dev python scripts/policy/validate_import_boundaries.py`

```text
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)
```

Result: PASS.

### `python3 scripts/policy/validate_repository_governance.py`

```text
Repository governance policy: PASS
```

Result: PASS.

## All eight existing package/data check scripts

All eight scripts were executed and exited zero.

### `scripts/ci/shared-checks.sh`

```text
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### `scripts/ci/benchmarks-checks.sh`

```text
Resolved 15 packages in 6ms
All checks passed!
...                                                                      [100%]
3 passed in 0.11s
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
Resolved 15 packages in 6ms
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
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### `scripts/ci/stratograph-checks.sh`

```text
Resolved 15 packages in 14ms
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

## Files changed

- `scripts/policy/validate_import_boundaries.py`
- `tests/policy/test_import_boundaries.py`
- `EvoNN-Shared/src/evonn_shared/benchmarks.py`
- `governance/b0-status.yaml`
- `tests/policy/test_repository_governance.py`
- `.superpowers/sdd/task-4-report.md`

## Self-review

- Confirmed `git diff --check` passes with no whitespace errors.
- Confirmed the validator uses one exact package map for member identity, distribution identity, import roots, dependency edges, and source edges.
- Confirmed all production source trees are parsed and syntax/read failures fail closed.
- Confirmed dynamic import targets are not silently skipped across direct, aliased, assigned, builtins, importlib, and runpy forms: recognized literals are checked and recognized non-literals are rejected.
- Confirmed dependency matching uses normalized exact names rather than substring matching across required, optional, and dependency-group surfaces, and entry-point module targets use the same matrix.
- Confirmed workspace excludes and symlinks cannot hide declared members, production imports, or benchmark runtime/package content.
- Confirmed all diagnostics are aggregated and sorted before output, including every workspace-source marker alternative.
- Confirmed the benchmark policy reuses the existing Shared-owned layout invariant rather than defining a conflicting second layout, and retains the brief's broad tests-subtree Python allowance.
- Confirmed the checked-in benchmark tree remains data-only and no real package source was mutated by tests.
- Confirmed B0.4 alone transitioned from open to closed; B0.2/B0.5 and overall B0 remain open, while B0.3 evidence remains intact.
- Confirmed no CI workflow, `b0-policy-checks.sh`, runtime/backend probe, engine algorithm, CLI behavior, export contract, benchmark catalog, MLX/NumPy/scikit-learn dependency, or Phase 0 implementation was added.

## Coordinator review-fix addendum

### Findings addressed

All Critical and Important coordinator findings were reproduced with focused tests before implementation and fixed without expanding into Task 5:

1. Replaced the file-global dynamic-alias collector with a source-ordered binding analyzer. Imports, assignments, deletes, function-local declarations, parameters, class namespaces, branches, and rebinding update or invalidate bindings at the statement where they occur. Function/class analyses use isolated scope state, so inner aliases do not overwrite outer bindings and later rebinding cannot hide an earlier forbidden call.
2. Changed uv source validation to inspect every source alternative. Every internal alternative must be a mapping containing only `workspace = true` and an optional non-empty string marker. Path/URL/Git/malformed/extra-key alternatives fail individually with deterministic alternative indexes and declaration lines.
3. Expanded topology symlink rejection to the root workspace manifest, every member manifest, member roots, `src/`, package roots, all production-source descendants, and the Shared benchmark topology.
4. Enforced exactly one top-level entry in every member `src/`: the package's expected import root. Extra packages, namespace directories, sibling internal roots, files, and top-level modules fail.
5. Added a section/key-aware TOML locator for workspace members/exclude, project/optional/group dependencies, uv source alternatives, hatch package declarations, scripts, GUI scripts, and entry-point groups. Diagnostics now point at the actual declaration rather than an earlier substring match.

### Coordinator-fix RED evidence

Command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py -k 'source_ordered or scopes or mixed_marker or manifest_symlink or exactly_one_expected_top_level or workspace_dependencies_match_allowed_matrix'
```

The first selection intentionally missed the separately named top-level identity test and produced:

```text
FFFFF                                                                    [100%]
5 failed, 18 deselected in 0.16s
```

The failures proved:

- a later `runpy` rebind hid the earlier `importlib` call;
- function/class bindings leaked through the file-global alias map;
- mixed workspace/path marker alternatives were silently accepted;
- a symlinked member `pyproject.toml` was followed;
- a workspace-source diagnostic pointed to dependency line 13 instead of source declaration line 23.

The explicit top-level identity regression was then run:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py::test_src_contains_exactly_one_expected_top_level_import_root
```

```text
F                                                                        [100%]
1 failed in 0.05s
```

It showed that sibling `topograph/`, a namespace-only directory, and `unexpected_module.py` under Prism's `src/` were all accepted.

### Coordinator-fix GREEN evidence

Focused coordinator regressions:

```text
......                                                                   [100%]
6 passed, 17 deselected in 0.15s
```

Complete policy suite:

```text
.......................                                                  [100%]
23 passed in 0.57s
```

### Final required verification after coordinator fixes

```text
== uv lock --check ==
Resolved 15 packages in 6ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 5ms
Audited 14 packages in 0.30ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
.......................                                                  [100%]
23 passed in 0.56s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 98%]
.                                                                        [100%]
73 passed in 7.86s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS
```

### Final eight-script regression matrix

```text
== shared-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== benchmarks-checks.sh ==
Resolved 15 packages in 6ms
All checks passed!
...                                                                      [100%]
3 passed in 0.14s

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
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== topograph-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== stratograph-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== primordia-checks.sh ==
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### Final CLI runtime observation

The hardened CLI was launched from `/tmp` against a synthetic repository containing all coordinator bypass classes. Exact output:

```text
Import boundary policy: FAIL (6 violations)
ERROR: EvoNN-Prism/pyproject.toml:11: evonn-prism: internal dependency 'evonn-shared' must have a matching workspace = true source
ERROR: EvoNN-Prism/pyproject.toml:16: evonn-prism: invalid workspace source alternative for 'evonn-shared' alternative 1; expected only workspace = true and an optional non-empty marker
ERROR: EvoNN-Prism/src/prism/source_order_bypass.py:2: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-topograph via importlib.import_module
ERROR: EvoNN-Prism/src/prism/source_order_bypass.py:4: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-stratograph via runpy.run_module
ERROR: EvoNN-Prism/src/topograph:1: evonn-prism: unexpected top-level src entry; expected only 'prism'
ERROR: EvoNN-Topograph/pyproject.toml:1: evonn-topograph: workspace manifest must not be a symbolic link
exit=1
```

The checked-in repository launched from `/tmp` still produced:

```text
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)
```

## Concerns

None. B0.4 remains honestly closed after all coordinator regressions and the complete verification matrix passed. Task 5 still needs to wire this direct validator into dual-host CI/runtime probes; no Task 5 implementation was added here.
