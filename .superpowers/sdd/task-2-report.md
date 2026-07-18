# Task 2 Report — Install plan and provenance controls

## Implementation summary

- Renamed root `LAB_PLAN.md` to the sole active `CONSOLIDATED_PLAN.md` and added machine-readable execution-plan frontmatter preserving Revision 2.
- Clarified B0.3/B0.4 and the Phase 0 exit around seven importable Python skeletons versus the tested data-only `shared-benchmarks/` skeleton, including the future independently invocable `scripts/ci/benchmarks-checks.sh` and `evonn_shared.benchmarks` loader boundary.
- Removed the stale Immediate Next Action to install/rename the already-installed consolidated plan.
- Added a provisional, fail-closed authority pin for the complete `claude-spec/` tree, `PROGRAM_CHARTER.md`, and `claudex-spec/19-research-interop.md` at source commit `2c622528ac31f9e86d3fd9e03fab3279b3819d72`.
- Added independently anchored Git object IDs, declared versions, deterministic import time, and checked-in SHA-256 content digests. Directory digesting uses the documented `canonical-sha256-tree-v1` procedure and a shared `(relative_path, content)` digest core for Git and worktree adapters.
- Added structured specification-upgrade and traceability controls. Traceability records `CONSOLIDATED_PLAN.md` as the installed plan while preserving the pinned charter bytes and treating its `LAB_PLAN.md` wording as historical pre-bootstrap source wording.
- Added machine-readable B0 status showing B0.1/B0.6 locally satisfied and B0.2 open solely because no authoritative remote is configured.
- Added fail-closed plan/provenance/status validation and policy tests, including configured-remote matching before B0.2 can close, unknown-state rejection, source-drift rejection, plan-like document classification, archive rules, and Product-only consumer acceptance authority.
- Did not create workspace/package skeletons, import-boundary implementation, CI, or Phase 0 export placeholders.

## Files changed

- `LAB_PLAN.md` → `CONSOLIDATED_PLAN.md`
- `governance/authority-provenance.yaml`
- `governance/b0-status.yaml`
- `governance/SPEC_UPGRADE_PROCESS.md`
- `governance/SPEC_TRACEABILITY.md`
- `scripts/policy/validate_repository_governance.py`
- `tests/policy/test_repository_governance.py`
- `.superpowers/sdd/task-2-report.md`

## TDD RED

Tests were created before production/config/document changes.

Command:

```text
python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py
```

Output:

```text
FFFFFFFFFFFF                                                             [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:28: AssertionError: authority provenance manifest is not installed
/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/pathlib.py:1110: FileNotFoundError: [Errno 2] No such file or directory: '/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/governance/SPEC_UPGRADE_PROCESS.md'
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:18: AssertionError: repository governance validator is not installed
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_repository_governance_policy_passes
FAILED tests/policy/test_repository_governance.py::test_only_consolidated_plan_is_active_and_root_plan_names_are_allowlisted
FAILED tests/policy/test_repository_governance.py::test_plan_scanner_excludes_pinned_and_archive_trees_but_checks_owned_docs
FAILED tests/policy/test_repository_governance.py::test_plan_scanner_does_not_classify_governance_or_research_prose_as_plans
FAILED tests/policy/test_repository_governance.py::test_archived_project_plans_must_be_explicitly_non_authoritative
FAILED tests/policy/test_repository_governance.py::test_provenance_manifest_pins_required_sources_and_exact_bytes
FAILED tests/policy/test_repository_governance.py::test_local_only_authority_keeps_b02_open_and_requires_null_url
FAILED tests/policy/test_repository_governance.py::test_real_remote_can_close_b02_without_changing_source_pin_or_digest
FAILED tests/policy/test_repository_governance.py::test_source_change_without_provenance_update_fails
FAILED tests/policy/test_repository_governance.py::test_only_product_interop_has_consumer_acceptance_authority
FAILED tests/policy/test_repository_governance.py::test_upgrade_and_traceability_documents_state_required_controls
FAILED tests/policy/test_repository_governance.py::test_consolidated_plan_frontmatter_and_b03_match_normative_specification
12 failed in 0.04s
```

Expected reason: all requested production controls were absent—the validator, provenance/status artifacts, governance documents, and installed consolidated plan had not yet been created.

### Review-driven RED regressions

After the first green implementation, fail-closed edge cases were added before their fixes.

Command:

```text
python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py::test_plan_scanner_excludes_pinned_and_archive_trees_but_checks_owned_docs
```

Output:

```text
F                                                                        [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:64: AssertionError: assert [PosixPath('p...ple/PLAN.md')] == [PosixPath('p...ple/PLAN.md')]
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_plan_scanner_excludes_pinned_and_archive_trees_but_checks_owned_docs
1 failed in 0.04s
```

Expected reason: contradictory explicit metadata and prose-based active-plan declarations were not yet both classified fail-closed.

Command:

```text
python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py
```

Output:

```text
...FF..FFF..FF                                                           [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:78: AttributeError: module 'repository_governance' has no attribute 'validate_plan_metadata'
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:95: AttributeError: module 'repository_governance' has no attribute 'validate_plan_metadata'
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:134: AssertionError: assert ('b0_2_status' not in {'authority_state': 'local-only/provisional', 'b0_2_open_reason': 'authoritative_remote_url_absent', 'b0_2_status': 'open', 'digest_method': 'canonical-sha256-tree-v1', ...})
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:175: TypeError: validate_b0_status() takes 2 positional arguments but 3 were given
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:188: TypeError: validate_b0_status() takes 2 positional arguments but 3 were given
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:234: KeyError: 'upgrade_policy'
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:266: KeyError: 'b0_repository_model'
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_unclassified_plan_like_project_docs_fail_closed
FAILED tests/policy/test_repository_governance.py::test_plan_scanner_does_not_classify_governance_or_research_prose_as_plans
FAILED tests/policy/test_repository_governance.py::test_local_only_authority_keeps_b02_open_and_requires_null_url
FAILED tests/policy/test_repository_governance.py::test_configured_real_remote_can_close_b02_without_changing_source_pin_or_digest
FAILED tests/policy/test_repository_governance.py::test_unknown_inconsistent_or_unconfigured_remote_authority_fails_closed
FAILED tests/policy/test_repository_governance.py::test_upgrade_and_traceability_controls_are_machine_readable
FAILED tests/policy/test_repository_governance.py::test_consolidated_plan_frontmatter_matches_normative_b0_repository_model
7 failed, 7 passed in 0.95s
```

Expected reason: the new tests preceded implementation of plan-candidate metadata validation, sole-source B0 status, configured-remote authentication, structured governance metadata, and the machine-readable B0 repository model.

## GREEN and final verification

Focused policy suite:

```text
$ python3 -m pytest -q tests/policy/test_repository_governance.py
..............                                                           [100%]
14 passed in 1.55s
```

Direct fail-closed validator:

```text
$ python3 scripts/policy/validate_repository_governance.py
Repository governance policy: PASS
```

Syntax/compile validation:

```text
$ python3 -m py_compile scripts/policy/validate_repository_governance.py tests/policy/test_repository_governance.py
```

Output: no output; exit status 0.

Complete currently available suite:

```text
$ python3 -m pytest -q
..............                                                           [100%]
14 passed in 1.78s
```

Diff formatting:

```text
$ git diff --check
```

Output: no output; exit status 0.

Scope guard:

```text
$ test ! -e LAB_PLAN.md && ! find . -name manifest.json -o -name results.json -o -name summary.json | grep -q .
```

Output: no output; exit status 0.

## Self-review

- Confirmed work is on `agent/b0-bootstrap`, not `main`.
- Confirmed `CONSOLIDATED_PLAN.md` is the only active execution plan and root plan filenames are allowlisted.
- Confirmed project-owned plan-like files fail closed without valid execution-plan metadata; pinned specification trees are excluded from prose detection and archive plans are separately required to be non-authoritative.
- Confirmed the validator retains an independent trust anchor for the exact initial commit, declared versions, Git object types/IDs, digests, scopes, paths, and consumer-acceptance policy; the manifest cannot self-authorize changed bytes.
- Confirmed each pinned authority's Git object and SHA-256 digest recomputes from source-commit bytes and matches the checked-out source bytes.
- Confirmed `governance/b0-status.yaml` is the sole B0 gate-status source; duplicate B0.2 status fields in provenance fail validation.
- Confirmed local-only state requires null upstream URLs and keeps B0.2 open. Remote closure requires the explicit `remote-pinned` state, authoritative-remote entries, HTTPS/SSH identities matching a configured Git remote, and a closed status with no open reason.
- Confirmed only `claudex-spec/19-research-interop.md` carries consumer acceptance authority and structured traceability requires both I1 and Product-owned I2 before Product influence.
- Confirmed `PROGRAM_CHARTER.md` remains byte-identical to its mandatory pinned blob. Its historical `LAB_PLAN.md` wording is mapped to installed `CONSOLIDATED_PLAN.md` in structured traceability instead of mutating authority content.
- Confirmed B0.3/B0.4 and the Phase 0 exit distinguish Python import validation from data-only layout/loader validation and retain a dedicated future benchmark check script.
- Confirmed no workspace skeletons, CI, import-boundary implementation, or Phase 0 export placeholders were added.
- No additional correctness findings remained after the review-driven regression fixes.

## Concerns

- Expected and fail-closed: B0.2 remains formally open because this checkout has no configured authoritative remote. No URL was invented.
- This pre-bootstrap policy suite uses the available `pytest` and PyYAML environment. Dependency pinning belongs to the later workspace bootstrap task and was intentionally not introduced here.

## Post-review fixes

### Implementation changes

Addressed every Critical, Important, and requested Minor reviewer finding without expanding beyond Task 2:

- Hardened remote identity normalization to reject `file:`, `file://`, filesystem paths, Windows drive paths, localhost names, loopback addresses, unspecified addresses, and link-local addresses. SCP-style identities now require a syntactically valid SSH host/path, and B0.2 still requires normalized identity equality with a configured Git remote.
- Changed provenance parsing to validate every source-list element before lookup construction, reject non-mapping entries, reject empty/non-string IDs, reject duplicate IDs without overwriting, and retain required-field validation for incomplete duplicates. Working-tree digest validation now also fails closed on non-mapping source entries.
- Broadened archive candidate recognition for versioned/completed plan and checklist names such as `OLD_PLAN_v2.md` and `IMPLEMENTATION_CHECKLIST_DONE.md`, while excluding analysis names such as `LAB_PLAN_CRITIQUE.md`, `EXECUTION_PLAN_OBSERVATIONS.md`, and `PLANNING_NOTES.md` unless explicit execution-plan metadata says otherwise.
- Strengthened execution-plan heading detection so a heading must end in `Execution Plan`; research headings such as `# Execution plan observations` are not classified as plans, while `# Alternate Execution Plan` plus active status still fails closed without metadata.
- Added fail-closed B0 status identity/shape validation for `document_kind`, `gate`, top-level status, `items` mapping, all required item mappings/statuses, B0.2 `open_reason`, and top-level/B0.2 status consistency.

### Files changed by review fixes

- `scripts/policy/validate_repository_governance.py`
- `tests/policy/test_repository_governance.py`
- `.superpowers/sdd/task-2-report.md`

### Review regression RED commands and exact output

Critical local/file transport regression:

```text
$ python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py::test_local_or_file_git_remotes_cannot_close_b02
F...FF                                                                   [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:262: assert False
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:262: assert False
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:262: assert False
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_local_or_file_git_remotes_cannot_close_b02[file:/tmp/evonn.git]
FAILED tests/policy/test_repository_governance.py::test_local_or_file_git_remotes_cannot_close_b02[localhost:/tmp/evonn.git]
FAILED tests/policy/test_repository_governance.py::test_local_or_file_git_remotes_cannot_close_b02[127.0.0.1:/tmp/evonn.git]
3 failed, 3 passed in 0.32s
```

Expected reason: `file:/...`, localhost SCP syntax, and loopback SCP syntax normalized as acceptable configured remotes.

Malformed/duplicate provenance regression:

```text
$ python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py::test_provenance_rejects_non_mapping_duplicate_and_incomplete_entries
F                                                                        [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/scripts/policy/validate_repository_governance.py:221: AttributeError: 'str' object has no attribute 'get'
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_provenance_rejects_non_mapping_duplicate_and_incomplete_entries
1 failed in 0.10s
```

Expected reason: source entries were filtered/collapsed into a dictionary before every list element was validated, and digest validation assumed mappings.

Archive candidate regression:

```text
$ python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py::test_versioned_and_completed_archive_plan_names_require_metadata_without_false_positives
F                                                                        [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:130: assert False
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_versioned_and_completed_archive_plan_names_require_metadata_without_false_positives
1 failed in 0.02s
```

Expected reason: archive recognition only matched names ending immediately in `PLAN.md` or `CHECKLIST.md`.

Research-log heading regression:

```text
$ python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py::test_execution_plan_observation_heading_is_not_an_active_plan
F                                                                        [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:102: AssertionError: assert [PosixPath('r...rvations.md')] == []
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_execution_plan_observation_heading_is_not_an_active_plan
1 failed in 0.02s
```

Expected reason: the heading matcher accepted any heading containing `execution plan`, including observation logs.

B0 status schema regression:

```text
$ python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py::test_b0_status_identity_and_required_item_shape_fail_closed
F                                                                        [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:189: AssertionError: assert []
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_b0_status_identity_and_required_item_shape_fail_closed
1 failed in 0.03s
```

Expected reason: the validator did not yet authenticate the status artifact identity or required schema.

### Review regression GREEN commands and exact output

```text
$ python3 -m pytest -q tests/policy/test_repository_governance.py::test_local_or_file_git_remotes_cannot_close_b02
......                                                                   [100%]
6 passed in 0.39s

$ python3 -m pytest -q tests/policy/test_repository_governance.py::test_provenance_rejects_non_mapping_duplicate_and_incomplete_entries
.                                                                        [100%]
1 passed in 0.56s

$ python3 -m pytest -q tests/policy/test_repository_governance.py::test_versioned_and_completed_archive_plan_names_require_metadata_without_false_positives
.                                                                        [100%]
1 passed in 0.02s

$ python3 -m pytest -q tests/policy/test_repository_governance.py::test_execution_plan_observation_heading_is_not_an_active_plan
.                                                                        [100%]
1 passed in 0.02s

$ python3 -m pytest -q tests/policy/test_repository_governance.py::test_b0_status_identity_and_required_item_shape_fail_closed
.                                                                        [100%]
1 passed in 0.03s
```

### Post-review final verification

Focused governance suite:

```text
$ python3 -m pytest -q tests/policy/test_repository_governance.py
........................                                                 [100%]
24 passed in 3.65s
```

Complete currently available suite:

```text
$ python3 -m pytest -q
........................                                                 [100%]
24 passed in 3.46s
```

Direct validator:

```text
$ python3 scripts/policy/validate_repository_governance.py
Repository governance policy: PASS
```

Compile validation:

```text
$ python3 -m py_compile scripts/policy/validate_repository_governance.py tests/policy/test_repository_governance.py
```

Output: no output; exit status 0.

Diff validation:

```text
$ git diff --check
```

Output: no output; exit status 0.

### Post-review self-review

- Confirmed every listed local transport fails even when the same value is configured as a Git remote; configured HTTPS authority remains accepted.
- Confirmed non-mapping and duplicate provenance entries produce validation errors rather than exceptions or silent overwrite, and incomplete duplicates receive required-field errors.
- Confirmed both named archive regressions require explicit `authoritative: false` metadata and the named critique/observation/planning false positives remain ignored.
- Confirmed a research observation heading is not active-plan evidence, while the existing unclassified alternate-plan regression still fails closed.
- Confirmed malformed status identity, gate, item container, missing required item, and non-mapping item all fail closed without exceptions.
- Confirmed the direct repository validator remains green and no Task 3 workspace, CI, or package scope was added.

## Re-review fixes

### Implementation changes

- Expanded `governance/b0-status.yaml` to represent exactly B0.1 through B0.6. B0.3/B0.4/B0.5 are explicitly `open` with `open_reason: unimplemented`; B0.1/B0.6 retain `locally_satisfied`; B0.2 retains its remote-only open reason.
- Decoupled overall Gate B0 state from B0.2. The validator now derives top-level `closed` only when all six item statuses are `closed`; every partial state, including B0.2 closed while B0.3–B0.5 remain open, requires top-level `open`.
- Added exact six-ID validation and per-item state/reason validation. The remote-closure fixture now closes only B0.2 and correctly leaves overall B0 open; an all-six-closed future state is also validated.
- Added untyped research-log semantics for recognized research directories and observation/log names. Plan-like names such as `research/EXECUTION_PLAN_OBSERVATIONS.md` and root `EXECUTION_PLAN_OBSERVATIONS.md` are non-plan logs without execution-plan metadata, while explicit execution-plan metadata in a research path is still discovered and validated.
- Preserved fail-closed classification for actual root/package plan-like documents such as `packages/example/ALT_PLAN.md`.

### Files changed by re-review fixes

- `governance/b0-status.yaml`
- `scripts/policy/validate_repository_governance.py`
- `tests/policy/test_repository_governance.py`
- `.superpowers/sdd/task-2-report.md`

### Re-review RED commands and exact output

Complete six-item and derived Gate B0 status regression:

```text
$ python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py::test_local_only_authority_keeps_b02_open_and_requires_null_url tests/policy/test_repository_governance.py::test_overall_b0_closes_only_when_all_six_items_are_closed
FF                                                                       [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:196: AssertionError: assert {'B0.1', 'B0.2', 'B0.6'} == {'B0.1', 'B0....B0.5', 'B0.6'}
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:286: AssertionError: assert []
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_local_only_authority_keeps_b02_open_and_requires_null_url
FAILED tests/policy/test_repository_governance.py::test_overall_b0_closes_only_when_all_six_items_are_closed
2 failed in 1.04s
```

Expected reason: the checked-in status omitted B0.3–B0.5, and the validator incorrectly accepted top-level `closed` when only B0.2 was closed.

Research path/name regression:

```text
$ python3 -m pytest -q --tb=line tests/policy/test_repository_governance.py::test_research_plan_like_paths_and_names_are_logs_unless_explicitly_typed
F                                                                        [100%]
=================================== FAILURES ===================================
/Users/timokruth/Projekte/EvoNN/.claude/worktrees/lab-plan-implementation/tests/policy/test_repository_governance.py:112: AssertionError: assert [PosixPath('E...RVATIONS.md')] == []
=========================== short test summary info ============================
FAILED tests/policy/test_repository_governance.py::test_research_plan_like_paths_and_names_are_logs_unless_explicitly_typed
1 failed in 0.02s
```

Expected reason: `PLAN_LIKE_NAME` classified observation-log filenames as plans regardless of research path/name semantics.

### Re-review GREEN commands and exact output

```text
$ python3 -m pytest -q tests/policy/test_repository_governance.py::test_local_only_authority_keeps_b02_open_and_requires_null_url tests/policy/test_repository_governance.py::test_overall_b0_closes_only_when_all_six_items_are_closed
..                                                                       [100%]
2 passed in 0.83s

$ python3 -m pytest -q tests/policy/test_repository_governance.py::test_research_plan_like_paths_and_names_are_logs_unless_explicitly_typed
.                                                                        [100%]
1 passed in 0.02s
```

### Re-review final verification

Focused governance suite:

```text
$ python3 -m pytest -q tests/policy/test_repository_governance.py
..........................                                               [100%]
26 passed in 2.64s
```

Complete currently available suite:

```text
$ python3 -m pytest -q
..........................                                               [100%]
26 passed in 3.54s
```

Direct validator:

```text
$ python3 scripts/policy/validate_repository_governance.py
Repository governance policy: PASS
```

Compile validation:

```text
$ python3 -m py_compile scripts/policy/validate_repository_governance.py tests/policy/test_repository_governance.py
```

Output: no output; exit status 0.

Diff validation:

```text
$ git diff --check
```

Output: no output; exit status 0.

### Re-review self-review

- Confirmed the checked-in status contains exactly B0.1–B0.6 and directly records B0.3/B0.4/B0.5 as open/unimplemented.
- Confirmed closing B0.2 against a configured authoritative remote leaves top-level B0 open while any other item remains non-closed.
- Confirmed top-level B0 closed is rejected for partial item closure and accepted only when all six items are closed.
- Confirmed untyped research-path and observation-name documents are excluded from plan classification, including root filename allowlisting, while explicit execution-plan metadata remains active in research paths.
- Confirmed the existing package-level unclassified plan regression remains fail-closed.
- Confirmed no Task 3 workspace, package, import-boundary, or CI implementation was added.
