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
