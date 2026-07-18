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

## Binding-lattice re-review addendum

### Critical reproduced

The coordinator re-review found that conflicting control-flow bindings were collapsed to an ignored unknown value, and that function bodies only saw globals from definition time. Focused tests were written first for branch, try, loop, invocation-time global, pre-invocation rebinding, nested global, and nonlocal behavior.

Initial RED command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py -k 'branch_merge or try_and_loop or global_bindings_available or global_and_nonlocal'
```

Exact output:

```text
FFFF                                                                     [100%]
4 failed, 23 deselected in 0.23s
```

The failures proved that:

- `importlib.import_module` on one `if` branch was erased by `print` on the other;
- try and zero-iteration loop paths lost feasible loader bindings;
- a function defined before its global provider import was not checked when called after the import;
- global/nonlocal writes from called functions were not propagated, causing both missed runtime bindings and stale false-positive bindings.

A pre-invocation rebind regression then demonstrated the inverse definition-time bug:

```text
F                                                                        [100%]
1 failed in 0.09s
```

`provider` was `importlib` when the function was defined but `print` when called; definition-time-only analysis incorrectly reported the function body.

A nested global propagation regression also failed before its fix:

```text
F                                                                        [100%]
1 failed in 0.08s
```

The nested function's `global provider = print` effect was discarded when the outer function returned.

A final loop-`break` regression produced:

```text
F                                                                        [100%]
1 failed in 0.08s
```

The normal loop-`else` outcome overwrote a loader established before `break`; the loop merge was extended to retain the feasible body-without-else outcome.

### Binding-lattice implementation

- Replaced scalar binding states with a lattice value containing a set of feasible known provider/loader/function identities plus an independent unknown-callable flag.
- Control-flow joins now union feasible identities; uncertainty can coexist with a known loader and can no longer erase it.
- Added conservative merges for `if`, `while`, `for`/`async for`, `try`/`try*`/`except`/`else`/`finally`, and with-target rebinding. Loop joins retain zero-iteration, normal-else, and break/early-exit body outcomes so a feasible loader cannot be overwritten by the loop `else` path.
- Function definitions register callable identities. Direct/aliased/branch-possible function calls re-analyze bodies against bindings available at invocation, while declaration scans mask module globals and still catch local imports.
- Top-level and class functions are also checked against final module globals for externally feasible invocation.
- Exact calls propagate module-global and enclosing-function nonlocal effects, including effects made by nested called functions. Possible calls union their effects with the non-call/other-call paths.
- Rebinding before and after calls remains source ordered; an unknown arbitrary callable by itself is not treated as a loader.

Focused lattice GREEN:

```text
.....                                                                    [100%]
5 passed, 23 deselected in 0.23s
```

Complete policy GREEN after the nested-global regression:

```text
.............................                                            [100%]
29 passed in 0.71s
```

### Final required matrix after binding-lattice fix

```text
== uv lock --check ==
Resolved 15 packages in 5ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 5ms
Audited 14 packages in 0.28ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
.............................                                            [100%]
29 passed in 0.71s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 91%]
.......                                                                  [100%]
79 passed in 7.61s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS
```

### Final eight-script matrix after binding-lattice fix

```text
== shared-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s

== benchmarks-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
...                                                                      [100%]
3 passed in 0.14s

== contenders-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== compare-checks.sh ==
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== prism-checks.sh ==
Resolved 15 packages in 5ms
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
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### Final lattice CLI observation

A temporary repository combined the exact branch, try, zero-iteration loop, and invocation-time global bypasses. The CLI returned:

```text
Import boundary policy: FAIL (4 violations)
ERROR: EvoNN-Prism/src/prism/lattice_bypass.py:13: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-stratograph via importlib.import_module
ERROR: EvoNN-Prism/src/prism/lattice_bypass.py:18: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-primordia via importlib.import_module
ERROR: EvoNN-Prism/src/prism/lattice_bypass.py:21: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-topograph via importlib.import_module
ERROR: EvoNN-Prism/src/prism/lattice_bypass.py:6: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-topograph via importlib.import_module
exit=1
```

The checked-in repository launched from `/tmp` still returned the single PASS line.

## Final control-flow re-review addendum

### Remaining gaps reproduced

Focused tests were added before implementation for match joins, intermediate try-prefix exception states, and annotation/default expressions.

Command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py -k 'match_cases or every_feasible_body_prefix or annotations_type_parameters'
```

Exact RED output:

```text
FFF                                                                      [100%]
3 failed, 30 deselected in 0.13s
```

The failures proved:

- match cases were analyzed sequentially, so the `print` case erased the loader case;
- try handlers received only pre-body or fully completed body states, missing the state after loader assignment and before a raising call;
- function parameter, vararg, keyword, return, PEP 695 type-parameter annotations, and lambda defaults were not visited.

The earlier loop-break RED was expanded with exact for/while/async-for and nested-conditional break coverage, including statements after guaranteed break. A straight-line overwrite guard remains green and proves conservative unions are applied only at control-flow joins, not ordinary sequential rebinding.

### Final implementation

- Added match analysis from one pre-match state: the subject is visited once, every guard/case starts from the same state, pattern captures bind unknown only within that case outcome, and all cases plus no-match are unioned.
- Try handlers now receive an outcome from every completed prefix before each potentially raising body statement. `else` runs only on normal body completion and `finally` is applied to every success/handler path.
- Added abrupt statement channels for guaranteed `break`, `continue`, `return`, and `raise`; unreachable trailing statements are not visited.
- Loop analysis retains zero-iteration, normal-else, body, direct break/continue, and nested conditional loop-exit outcomes for `while`, `for`, and `async for`.
- Function exit outcomes are retained separately and unioned with normal completion, preserving global/nonlocal effects before return/raise.
- Function definitions now scan all positional/keyword/vararg/kwarg annotations, return annotations, PEP 695 type parameters, decorators, and defaults. Lambdas scan all defaults and available argument annotations before entering their local scope; annotated assignments scan their annotation expression.

Focused GREEN:

```text
.................................                                        [100%]
33 passed in 0.87s
```

### Final verification matrix

```text
== uv lock --check ==
Resolved 15 packages in 6ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 13ms
Audited 14 packages in 0.62ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
.................................                                        [100%]
33 passed in 0.87s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 86%]
...........                                                              [100%]
83 passed in 6.66s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS
```

### Final eight-script matrix

```text
== shared-checks.sh ==
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s

== benchmarks-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
...                                                                      [100%]
3 passed in 0.16s

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
1 passed in 0.00s

== topograph-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== stratograph-checks.sh ==
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== primordia-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### Final CLI observation

A synthetic repository combined match-case, intermediate try-prefix, abrupt loop, and annotation bypasses. Exact output:

```text
Import boundary policy: FAIL (4 violations)
ERROR: EvoNN-Prism/src/prism/final_flow_bypass.py:16: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-stratograph via importlib.import_module
ERROR: EvoNN-Prism/src/prism/final_flow_bypass.py:23: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-primordia via importlib.import_module
ERROR: EvoNN-Prism/src/prism/final_flow_bypass.py:25: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-topograph via importlib.import_module
ERROR: EvoNN-Prism/src/prism/final_flow_bypass.py:7: evonn-prism: forbidden dynamic import edge evonn-prism -> evonn-topograph via importlib.import_module
exit=1
```

The checked-in repository still emitted the single PASS line when launched from `/tmp`.

## Binding architecture decision — strict primitive prohibition

The user made a binding architecture decision after the interpreter reviews: the path-sensitive/interprocedural dynamic-import analyzer was abandoned as unsound in principle and replaced rather than extended. All interpreter-focused sections above are retained as historical TDD/review evidence only; they no longer describe the checked-in implementation.

### Net simplification

- Deleted `_BindingValue`, `_BindingScope`, local binding collectors, provider/loader/function tables, branch lattices, try-prefix/loop/match/function invocation analysis, and annotation/control-flow special cases.
- Deleted the associated path-sensitive/interprocedural behavioral test sections.
- Retained the proven static workspace, PEP 508 dependency, uv-source, PEP 621 entry-point, topology/symlink, diagnostic-location, exact static import, and benchmark data-boundary checks.
- Final code/test diff for the interpreter replacement: 345 lines added and 1,309 deleted across the validator and policy test file, a net deletion of 964 lines.

### Permanent strict policy

Production code now fails immediately when it acquires a general dynamic-loading or dynamic-execution primitive:

- `import importlib` (including aliases), while specific submodules such as `importlib.metadata` remain allowed;
- `from importlib import import_module` or `*`;
- `import runpy`, `from runpy import run_module`, or `*`;
- `import builtins`, `from builtins import __import__`/`exec`/`eval`, or `*`;
- direct or aliased references to `__import__`, `exec`, or `eval`;
- explicit reflection through `getattr`, `hasattr`, `setattr`, `delattr`, `attrgetter`, or `methodcaller` naming `import_module`, `run_module`, `__import__`, `exec`, or `eval`.

The policy performs no path-sensitive target inference. Wrapper, container, branch, exception, loop, and function cases are rejected at primitive acquisition. Ordinary external static imports, `importlib.metadata`, `from importlib import metadata`, `runpy.run_path`, non-dangerous builtins imports, and platform-optional `try: import mlx; except ImportError:` remain allowed.

Production scope is exact:

- every `.py` under all seven package `src/**` trees;
- every shipped `.py` under `scripts/**`;
- root and package `tests/**` remain outside production scope;
- `scripts/policy/validate_import_boundaries.py` is scanned by the same primitive policy as every other shipped script; there is no whole-file exemption. Only directly inspected benign reflection calls are syntactically distinguished from reflection-helper acquisition;
- static forbidden internal imports are still checked in the validator and every other shipped script.

The abandoned approach and strict replacement are recorded as non-authoritative negative evidence in `research/logs/2026-07-18-dynamic-import-policy.md`. Its frontmatter declares `document_kind: research_log`, `status: completed`, and `authoritative: false`; governance validation confirms it is not an active plan.

### Strict-policy RED evidence

Command:

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py
```

Exact initial RED summary:

```text
.........FFFFFFFFFFFFFFF.FFFFFFF.FFFF.                                   [100%]
26 failed, 12 passed in 0.89s
```

The failures covered provider imports/aliases/star imports, `exec`/`eval`, explicit reflection, wrapper acquisition, shipped-script scope, exact allowlisting, test scope, the missing research log, and CLI aggregation.

A follow-up primitive-reference RED proved that assignment aliases must also be rejected at acquisition:

```text
.F.F.F....                                                               [100%]
3 failed, 7 passed, 31 deselected in 0.60s
```

A final safe-submodule/explicit-subscript RED closed two acquisition gaps: `import importlib.metadata` followed by `importlib.import_module` and `container["import_module"]` reflection.

```text
..........FF                                                             [100%]
2 failed, 10 passed, 31 deselected in 0.43s
```

### Strict-policy GREEN evidence

```text
...........................................                              [100%]
43 passed in 1.42s
```

### Final required verification after replacement

```text
== uv lock --check ==
Resolved 15 packages in 5ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 5ms
Audited 14 packages in 0.22ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
...........................................                              [100%]
43 passed in 1.42s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 7.38s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS
```

### Final eight-script matrix after replacement

```text
== shared-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== benchmarks-checks.sh ==
Resolved 15 packages in 4ms
All checks passed!
...                                                                      [100%]
3 passed in 0.21s

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
1 passed in 0.00s

== topograph-checks.sh ==
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== stratograph-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== primordia-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### Final strict-policy CLI observation

A synthetic repository containing a wrapped `importlib` provider, explicit `run_module` reflection, a safe submodule followed by forbidden attribute acquisition, and an aliased `eval` in a shipped script produced:

```text
Import boundary policy: FAIL (4 violations)
ERROR: EvoNN-Prism/src/prism/provider.py:1: evonn-prism: forbidden dynamic-loading primitive import: importlib
ERROR: EvoNN-Prism/src/prism/reflection.py:1: evonn-prism: forbidden explicit reflection naming dynamic primitive: run_module
ERROR: EvoNN-Prism/src/prism/specific_bypass.py:2: evonn-prism: forbidden dynamic primitive attribute acquisition: import_module
ERROR: scripts/tools/eval_bypass.py:1: repository-scripts: forbidden dynamic execution primitive reference: eval
exit=1
```

A standalone safe `importlib.metadata` plus optional MLX import remains allowed, and the checked-in repository launched from `/tmp` emitted the single PASS line.

## Strict-ban reflection acquisition re-review

### RED evidence

The final strict-ban review reproduced two syntactic gaps: builtin reflection helpers could be aliased/passed as values, and the validator file had a path-wide exemption. Tests were added first for builtin reflection acquisition, aliased `operator.attrgetter`/`methodcaller`, operator star/attribute acquisition, benign direct reflection, exact-validator injection, neighboring names, and nested path variants.

Command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py -k 'reflection_primitive_acquisition or benign_direct_reflection or production_scope_scans'
```

Exact RED output:

```text
FFFFFF.F                                                                 [100%]
7 failed, 1 passed, 42 deselected in 0.33s
```

The benign direct-reflection guard passed; all six acquisition variants and the injected `eval` in the exact validator path failed to produce required diagnostics.

### Implementation

- Builtin `getattr`, `hasattr`, `setattr`, and `delattr` are now forbidden when loaded as values for assignment, containers, arguments, defaults, or aliases.
- Direct calls to those four builtins are inspected syntactically without treating the function name as acquisition: dangerous primitive-name literals fail, while precise benign names remain allowed.
- `from operator import attrgetter`, `methodcaller`, or `*` fails at import, including aliases.
- `operator.attrgetter` and `operator.methodcaller` attribute acquisition fails without tracking aliases or control flow.
- The entire validator-path exemption was deleted. The validator, neighboring scripts, same-basename files, and nested path variants all receive identical import/execution/reflection checks.
- An injected `eval('1 + 1')` in `scripts/policy/validate_import_boundaries.py` now fails; the unmodified validator remains green without any exception.

Focused GREEN:

```text
..................................................                       [100%]
50 passed in 1.65s
```

### Final verification matrix

```text
== uv lock --check ==
Resolved 15 packages in 5ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 5ms
Audited 14 packages in 0.22ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
..................................................                       [100%]
50 passed in 1.65s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 72%]
............................                                             [100%]
100 passed in 7.06s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS
```

### Final eight-script matrix

```text
== shared-checks.sh ==
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== benchmarks-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
...                                                                      [100%]
3 passed in 0.25s

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
1 passed in 0.00s

== topograph-checks.sh ==
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== stratograph-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== primordia-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### CLI observation

A fixture containing `reflect = getattr`, an aliased `operator.attrgetter`, benign direct `getattr`, and an injected `eval` in the exact validator path produced:

```text
Import boundary policy: FAIL (3 violations)
ERROR: EvoNN-Prism/src/prism/operator_alias.py:1: evonn-prism: forbidden dynamic-loading primitive import: attrgetter from operator
ERROR: EvoNN-Prism/src/prism/reflection_alias.py:1: evonn-prism: forbidden reflection primitive acquisition: getattr
ERROR: scripts/policy/validate_import_boundaries.py:972: repository-scripts: forbidden dynamic execution primitive reference: eval
exit=1
```

The benign direct `getattr(container, "safe_name")` produced no diagnostic, and the checked-in repository still emitted the single PASS line from `/tmp`.

## Final strict reflection closure addendum

### RED evidence

Tests were added first for builtin reflection imports, reflection-helper subscripts, computed/parameter attribute names, and the literal-safe direct-call guard.

Command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py -k 'reflection_primitive_acquisition or subscript_reflection or requires_literal_safe or unknown_parameter or benign_direct_reflection'
```

Exact RED output:

```text
FFFF......FFFFFFFFF.                                                     [100%]
13 failed, 7 passed, 43 deselected in 0.73s
```

The safe literal direct-reflection cases and previously closed operator/builtin-value cases remained green. The failures proved that builtin reflection imports, subscript acquisition names, and non-literal direct attribute names were still accepted.

### Implementation

- Added `getattr`, `hasattr`, `setattr`, and `delattr` to forbidden `from builtins import ...` acquisition, including aliases; the existing builtins star prohibition covers all four.
- Expanded strict subscript-name rejection to builtin reflection helpers as well as dynamic-loader/execution and operator reflection names. `globals()["getattr"]`, `__builtins__["hasattr"]`, and arbitrary container subscripts now fail syntactically.
- Direct `getattr`/`hasattr`/`setattr`/`delattr` calls are allowed only when argument position 2 is a literal string not present in the forbidden acquisition/primitive-name set.
- Missing, computed, formatted, parameter-derived, or otherwise non-literal attribute names fail closed with a helper-specific diagnostic.
- Literal safe names remain allowed and no binding/control-flow inference was added.

Focused GREEN:

```text
...............................................................          [100%]
63 passed in 2.06s
```

### Final verification matrix

```text
== uv lock --check ==
Resolved 15 packages in 6ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 5ms
Audited 14 packages in 0.25ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
...............................................................          [100%]
63 passed in 2.06s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 63%]
.........................................                                [100%]
113 passed in 8.30s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS
```

### Final eight-script matrix

```text
== shared-checks.sh ==
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== benchmarks-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
...                                                                      [100%]
3 passed in 0.31s

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
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== topograph-checks.sh ==
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== stratograph-checks.sh ==
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s

== primordia-checks.sh ==
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### CLI observation

A fixture containing a builtin reflection alias import, a subscript-acquired helper, a computed direct-reflection name, and a safe literal direct call produced:

```text
Import boundary policy: FAIL (3 violations)
ERROR: EvoNN-Prism/src/prism/builtin_alias.py:1: evonn-prism: forbidden dynamic-loading primitive import: getattr from builtins
ERROR: EvoNN-Prism/src/prism/computed_name.py:2: evonn-prism: forbidden non-literal reflection: getattr requires a literal safe attribute-name argument
ERROR: EvoNN-Prism/src/prism/subscript_alias.py:1: evonn-prism: forbidden explicit reflection naming dynamic primitive: hasattr
exit=1
```

The safe literal `getattr(container, "safe_name")` produced no diagnostic, and the checked-in repository still emitted the single PASS line from `/tmp`.

## Final finite strict-ban fixes

### RED evidence

Tests were added first for direct `__builtins__` namespace use in package/script production, scripts-tree symlinks, clean scripts topology, and independent diagnostic aggregation after a provider import.

Command:

```sh
uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py -k 'builtins_namespace or scripts_topology or checked_in_scripts_topology or provider_import_does_not'
```

Exact RED output:

```text
FFF.                                                                     [100%]
3 failed, 1 passed, 63 deselected in 0.19s
```

The clean-tree guard passed. Namespace use, both scripts symlinks, and the independent post-import attribute violation were missing.

### Implementation

- Any production `Load` of `__builtins__` now fails immediately, covering module/dict forms, `.get(...)`, helper attributes, `.__dict__`, and related lookups without flow inference.
- Added deterministic scripts topology validation using the existing symlink enumerator. Every symlink at or below `scripts/` fails, including child-directory links that recursive globbing does not descend into and symlinked `.py` files.
- Symlinked scripts and symlink descendants are excluded from Python content scanning after the topology error, so external bytes cannot create misleading extra diagnostics.
- Removed visitor-wide provider-import suppression. Provider import, operator/reflection, eval/exec, and attribute-acquisition nodes now aggregate independently and are de-duplicated only by the existing exact diagnostic set.
- Deleted the unused `_line_containing` and `_workspace_source_alternatives` helpers. No disabled interpreter code or dead replacement remains.
- Static package/dependency/entry-point/topology/data checks and the non-authoritative research log are unchanged.

Focused GREEN:

```text
...................................................................      [100%]
67 passed in 2.36s
```

### Final verification matrix

```text
== uv lock --check ==
Resolved 15 packages in 6ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 5ms
Audited 14 packages in 0.25ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
...................................................................      [100%]
67 passed in 2.36s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 61%]
.............................................                            [100%]
117 passed in 8.35s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS
```

### Final eight-script matrix

```text
== shared-checks.sh ==
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s

== benchmarks-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
...                                                                      [100%]
3 passed in 0.42s

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
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### CLI observation

A fixture combining three independent primitive nodes, direct `__builtins__` namespace use, a symlinked scripts directory containing an eval bypass, and a symlinked Python script produced:

```text
Import boundary policy: FAIL (6 violations)
ERROR: EvoNN-Prism/src/prism/aggregate.py:1: evonn-prism: forbidden dynamic-loading primitive import: importlib
ERROR: EvoNN-Prism/src/prism/aggregate.py:2: evonn-prism: forbidden dynamic execution primitive reference: eval
ERROR: EvoNN-Prism/src/prism/aggregate.py:3: evonn-prism: forbidden dynamic primitive attribute acquisition: import_module
ERROR: EvoNN-Prism/src/prism/builtins_namespace.py:1: evonn-prism: forbidden builtin namespace access: __builtins__
ERROR: scripts/linked-tools:1: repository-scripts: shipped scripts path must not be a symbolic link
ERROR: scripts/linked.py:1: repository-scripts: shipped scripts path must not be a symbolic link
exit=1
```

The external symlink targets were not scanned, and the checked-in repository still emitted the single PASS line from `/tmp`.

## Concerns

None. B0.4 remains honestly closed under the finite strict syntactic policy. No dynamic-import interpreter, whole-file exemption, provider-wide suppression, scripts symlink bypass, or dead helper remains. Task 5 remains intentionally unimplemented.

## Final bounded strict-policy fixes

### Partial-work inspection

The inherited uncommitted diff was limited to `scripts/policy/validate_import_boundaries.py` and `tests/policy/test_import_boundaries.py`. The static `evonn_shared.benchmarks` import, scripts-to-Shared internal edge, importlib-submodule checks, reflection/`__builtins__` acquisition sets, and their tests were consistent with the binding strict syntactic architecture and were retained. The missing pieces were AST-column diagnostic identity/rendering, bare-name handling, and the precise `importlib.metadata` chain exception.

### RED evidence

The first focused run was made before completing the inherited implementation:

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'namespace_and_reflection_attribute_acquisition or importlib_submodules_other_than_metadata or same_line_primitive_diagnostics or bare_dynamic_and_reflection_primitive_names or importlib_metadata_attribute_chain or repository_scripts_may_import_only_evonn_shared'
```

Exact output:

```text
........FFFFFFFF..                                                       [100%]
=========================== short test summary info ============================
FAILED tests/policy/test_import_boundaries.py::test_same_line_primitive_diagnostics_preserve_ast_columns
FAILED tests/policy/test_import_boundaries.py::test_bare_dynamic_and_reflection_primitive_names_are_banned[import_module]
FAILED tests/policy/test_import_boundaries.py::test_bare_dynamic_and_reflection_primitive_names_are_banned[runpy]
FAILED tests/policy/test_import_boundaries.py::test_bare_dynamic_and_reflection_primitive_names_are_banned[run_module]
FAILED tests/policy/test_import_boundaries.py::test_bare_dynamic_and_reflection_primitive_names_are_banned[builtins]
FAILED tests/policy/test_import_boundaries.py::test_bare_dynamic_and_reflection_primitive_names_are_banned[attrgetter]
FAILED tests/policy/test_import_boundaries.py::test_bare_dynamic_and_reflection_primitive_names_are_banned[methodcaller]
FAILED tests/policy/test_import_boundaries.py::test_bare_dynamic_and_reflection_primitive_names_are_banned[importlib]
8 failed, 10 passed, 67 deselected in 0.58s
```

The ten passing cases proved the retained partial work for static loading, scripts boundary, and indirect reflection/namespace bans. The eight failures isolated the unfinished bare-name and same-line diagnostic behavior.

### Implementation

- Removed `importlib.util`-based validator execution of the Shared benchmark invariant and now statically imports `find_data_skeleton_violations` from the installed `evonn_shared` workspace package.
- Repository scripts may statically import `evonn_shared` as their only internal EvoNN target; engine, Compare, and Contenders imports remain forbidden.
- Banned every `importlib` submodule except exact `importlib.metadata`, and added `exec_module` attribute acquisition to the strict primitive set.
- Added bare `Load` bans for `importlib`, `import_module`, `runpy`, `run_module`, `builtins`, `attrgetter`, and `methodcaller` while syntactically exempting exact chains rooted at `importlib.metadata`.
- Added builtin reflection helpers and `__builtins__` to forbidden attribute acquisition, and added `__builtins__` to literal subscript/reflection targets.
- Python AST diagnostics now include one-based AST columns in `file:line:column` rendering and therefore in string identity; metadata/topology/data diagnostics retain the stable default column `1`.
- Updated integration assertions for independent overlapping primitive diagnostics and added the exact `import importlib.metadata; provider = importlib` regression.

### Focused GREEN evidence

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'namespace_and_reflection_attribute_acquisition or importlib_submodules_other_than_metadata or same_line_primitive_diagnostics or bare_dynamic_and_reflection_primitive_names or importlib_metadata or repository_scripts_may_import_only_evonn_shared'
```

Exact output:

```text
...................                                                      [100%]
19 passed, 67 deselected in 0.71s
```

The same-line regression emits two distinct deterministic diagnostics at columns 1 and 12. The complete focused policy suite then passed:

```text
........................................................................ [ 83%]
..............                                                           [100%]
86 passed in 2.79s
```

### Final verification matrix

```text
== uv lock --check ==
Resolved 15 packages in 6ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 5ms
Audited 14 packages in 0.23ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
........................................................................ [ 83%]
..............                                                           [100%]
86 passed in 3.12s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 52%]
................................................................         [100%]
136 passed in 8.63s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS
```

### Eight-script matrix from outside the repository

Each absolute script path was launched with current directory `/tmp`:

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
3 passed in 0.53s
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
1 passed in 0.00s
== topograph-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
== stratograph-checks.sh ==
Resolved 15 packages in 6ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
== primordia-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.01s
```

### Files changed and self-review

- `scripts/policy/validate_import_boundaries.py`
- `tests/policy/test_import_boundaries.py`
- `.superpowers/sdd/task-4-report.md`

Self-review confirmed the implementation remains a bounded syntax-only visitor: no path-sensitive state, alias resolution, control-flow model, interprocedural analysis, exemption, or abstract interpreter was introduced. Static dependency/metadata/topology/data checks are unchanged except for uniform column rendering and the required installed-package benchmark import. `git diff --check` completed with no output.

### Review-found metadata-prefix closure

A focused pre-commit review found that the initial `importlib.metadata` exception returned from every chain rooted at that prefix. Although a forbidden final attribute was checked before the return, a forbidden intermediate attribute followed by a benign suffix could be hidden. Regressions were added before changing the visitor.

RED command:

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'importlib_metadata_prefix_does_not_hide'
```

Exact RED output:

```text
FF.F                                                                     [100%]
=========================== short test summary info ============================
FAILED tests/policy/test_import_boundaries.py::test_importlib_metadata_prefix_does_not_hide_forbidden_outer_attributes[importlib.metadata.exec_module.safe-primitives0]
FAILED tests/policy/test_import_boundaries.py::test_importlib_metadata_prefix_does_not_hide_forbidden_outer_attributes[importlib.metadata.__builtins__.safe-primitives1]
FAILED tests/policy/test_import_boundaries.py::test_importlib_metadata_prefix_does_not_hide_forbidden_outer_attributes[importlib.metadata.__builtins__.__import__-primitives3]
3 failed, 1 passed, 86 deselected in 0.18s
```

The exception was narrowed to the exact `importlib.metadata` prefix node. The visitor now continues recursively through every attribute above that prefix, checking forbidden attributes independently, while suppressing only the otherwise forbidden root `importlib` Name load. The allowed `importlib.metadata.version(...)` chain remains green.

GREEN command:

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'importlib_metadata_prefix_does_not_hide or importlib_metadata_attribute_chain_remains_allowed or importlib_metadata_import_does_not_allow_bare'
```

Exact GREEN output:

```text
......                                                                   [100%]
6 passed, 84 deselected in 0.61s
```

The complete policy suite immediately after the review fix produced:

```text
........................................................................ [ 80%]
..................                                                       [100%]
90 passed in 3.07s
```

### Concerns

None. The validator must be executed in the synchronized workspace environment, as specified by `uv run --locked --group dev`; plain system-Python execution of the import-boundary validator is intentionally not the supported direct-policy command now that it uses the installed workspace package.

## Consolidated final pre-commit review closure

A final multi-angle review identified additional finite syntactic acquisitions within the same user-approved strict subset. Each group received a failing regression before implementation.

### Source-symlink, namespace-map, and loader RED

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'symlinked_package_source_subtrees_are_not_read or namespace_reflection_primitive_names or mapping_lookup_methods or namespace_mapping_lookup_chain or benign_mapping_lookup or metadata_loader_and_spec'
```

Exact RED output:

```text
FF.FFFFFFFFF.F                                                           [100%]
=========================== short test summary info ============================
FAILED tests/policy/test_import_boundaries.py::test_symlinked_package_source_subtrees_are_not_read[EvoNN-Primordia-.]
FAILED tests/policy/test_import_boundaries.py::test_symlinked_package_source_subtrees_are_not_read[EvoNN-Topograph-src]
FAILED tests/policy/test_import_boundaries.py::test_namespace_reflection_primitive_names_are_banned[globals]
FAILED tests/policy/test_import_boundaries.py::test_namespace_reflection_primitive_names_are_banned[locals]
FAILED tests/policy/test_import_boundaries.py::test_namespace_reflection_primitive_names_are_banned[vars]
FAILED tests/policy/test_import_boundaries.py::test_mapping_lookup_methods_reject_literal_dangerous_acquisition_keys[get-__builtins__]
FAILED tests/policy/test_import_boundaries.py::test_mapping_lookup_methods_reject_literal_dangerous_acquisition_keys[__getitem__-__import__]
FAILED tests/policy/test_import_boundaries.py::test_mapping_lookup_methods_reject_literal_dangerous_acquisition_keys[setdefault-eval]
FAILED tests/policy/test_import_boundaries.py::test_mapping_lookup_methods_reject_literal_dangerous_acquisition_keys[pop-import_module]
FAILED tests/policy/test_import_boundaries.py::test_mapping_lookup_methods_reject_literal_dangerous_acquisition_keys[get-hasattr]
FAILED tests/policy/test_import_boundaries.py::test_namespace_mapping_lookup_chain_is_banned
FAILED tests/policy/test_import_boundaries.py::test_importlib_metadata_loader_and_spec_acquisition_are_banned
12 failed, 2 passed, 90 deselected in 0.52s
```

### Metadata plugin RED

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'importlib_metadata_plugin_acquisition'
```

```text
F                                                                        [100%]
=========================== short test summary info ============================
FAILED tests/policy/test_import_boundaries.py::test_importlib_metadata_plugin_acquisition_is_banned
1 failed, 104 deselected in 0.57s
```

### Namespace-dunder and Unicode-column RED

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'builtin_namespace_dunder_import or namespace_getattribute_and_class_reflection or unicode_code_points'
```

```text
FFF                                                                      [100%]
=========================== short test summary info ============================
FAILED tests/policy/test_import_boundaries.py::test_builtin_namespace_dunder_import_is_banned_before_computed_key_use
FAILED tests/policy/test_import_boundaries.py::test_namespace_getattribute_and_class_reflection_are_banned
FAILED tests/policy/test_import_boundaries.py::test_same_line_diagnostic_columns_use_unicode_code_points
3 failed, 105 deselected in 0.29s
```

### Topology, metadata-alias, unbound-lookup, and identity RED

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'shared_benchmark_policy_module or exact_validator_script or metadata_module_alias or reserved_primitive_imports or unbound_namespace_lookup or nested_repeated_same_start or unicode_code_points or builtin_namespace_dunder_import or namespace_getattribute_and_class_reflection'
```

Exact RED summary:

```text
F.....FF.FF.FFFFFFF                                                      [100%]
12 failed, 7 passed, 104 deselected in 1.28s
```

The failures covered the required canonical Shared benchmark policy file, reserved imports from arbitrary modules, unbound `dict` lookup acquisition, nested same-start diagnostic identity, UTF-8 byte-offset conversion, metadata module aliases/acquisition, and the exact validator-only Shared script edge.

### Consolidated implementation

- Package production collection now refuses to follow or read symlinked member roots, `src` roots, package directories, or Python files. Topology diagnostics remain, while external target content cannot add parse/import diagnostics.
- Every validated root must contain exact `EvoNN-Shared/src/evonn_shared/benchmarks.py` as a regular non-symlink file; the ordinary production AST scan parses it without executing target code.
- Only exact `scripts/policy/validate_import_boundaries.py` may import `evonn_shared`; every neighboring shipped script has zero allowed internal EvoNN targets.
- `globals`, `locals`, `vars`, namespace dunders, `__getattribute__`, `dict.get`, `dict.__getitem__`, mapping lookup methods with dangerous literal keys, and operator `getitem`/`itemgetter` acquisition are rejected syntactically. Ordinary bound mapping lookup with safe/nonliteral keys remains allowed.
- One canonical reserved-primitive map now drives bare-name, arbitrary-module `ImportFrom`, attribute, subscript, reflection, loader, namespace, operator, and metadata-plugin checks. It includes `exec_module`, `load_module`, `__loader__`, and `__spec__`.
- The metadata surface no longer permits module aliases or standalone module acquisition. Exact `import importlib.metadata` is useful only as the syntactic prefix of approved direct attributes; direct `version` and `PackageNotFoundError` imports remain allowed. Entry-point APIs, distribution entry-point access, loader/spec acquisition, and syntactically identifiable `.load()` paths are banned.
- Python diagnostics convert AST UTF-8 byte offsets to one-based Unicode code-point columns and include end positions (`file:start-line:start-column-end-line:end-column`). This preserves two `eval` nodes on one line and repeated nested acquisitions sharing the same start position, while metadata/topology diagnostics retain `file:line:1`.

### Consolidated focused GREEN

```sh
uv run --locked --group dev pytest -q --tb=no tests/policy/test_import_boundaries.py -k 'shared_benchmark_policy_module or exact_validator_script or metadata_module_alias or reserved_primitive_imports or unbound_namespace_lookup or nested_repeated_same_start or unicode_code_points or builtin_namespace_dunder_import or namespace_getattribute_and_class_reflection or safe_specific_and_optional_static_imports or bare_dynamic_and_reflection_primitive_names'
```

```text
...............................                                          [100%]
31 passed, 96 deselected in 1.14s
```

The complete policy suite after integration produced:

```text
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 4.29s
```

### Superseding final verification matrix

```text
== uv lock --check ==
Resolved 15 packages in 4ms

== uv sync --all-packages --group dev --locked ==
Resolved 15 packages in 4ms
Audited 14 packages in 0.24ms

== uv run --locked --group dev pytest -q tests/policy/test_import_boundaries.py ==
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 4.37s

== uv run --locked --group dev pytest -q ==
........................................................................ [ 40%]
........................................................................ [ 81%]
.................................                                        [100%]
177 passed in 11.14s

== uv run --locked --group dev ruff check . ==
All checks passed!

== uv run --locked --group dev python scripts/policy/validate_import_boundaries.py ==
Import boundary policy: PASS (7 packages, shared-benchmarks data-only)

== python3 scripts/policy/validate_repository_governance.py ==
Repository governance policy: PASS

== git diff --check ==
(no output; exit 0)
```

### Superseding eight-script matrix from `/tmp`

```text
== shared-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
== benchmarks-checks.sh ==
Resolved 15 packages in 5ms
All checks passed!
...                                                                      [100%]
3 passed in 0.59s
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
Resolved 15 packages in 4ms
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
Resolved 15 packages in 4ms
All checks passed!
.                                                                        [100%]
1 passed in 0.00s
```

### Final concerns

None beyond the intentional execution contract: the validator now uses the trusted installed `evonn_shared` helper and must be run through the synchronized locked workspace command. The validated target repository is inspected statically and its benchmark policy module is never executed.
