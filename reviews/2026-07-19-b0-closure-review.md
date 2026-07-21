---
document_kind: review
status: delivered
authoritative: false
subject: gate_b0_closure
reviewed_ref: b0/close-gate pre-evidence closure diff
reviewer: independent lane counterpart
verdict: approve
---

# Gate B0 Closure Review

## Review scope and frozen revisions

This review compared the complete `b0/close-gate` preparatory diff against
`origin/main` using frozen Git objects. The reviewed branch revision was
`2d8db62e7a52ad3c0dc628e8197f5b26cd75eeb2`; the comparison base and hosted
workflow-tested revision was
`f68856f0c2fdf0ebc73671264b5a3ab0cff3b224`.

The reciprocal historical review covered these exact commits:

- `ca424270ffc9cd9c2eecf3382c63840cc44b381a`
- `cc067143fd3143eaba490c4dcc9f3765db1d70f2`
- `25b44ab1ff1e9cd268a5144cef1727cc98b1defb`

## Reciprocal review conclusions

### R4 — self-contained policy regression

Approved. At `ca424270ffc9cd9c2eecf3382c63840cc44b381a`,
`test_local_probe_parent_symlink_escape_is_rejected` writes its own placeholder
artifact and no longer reads a gitignored `.artifacts/` file. The regression is
self-contained and works in a clean clone.

### R5 — frozen evidence revision and descendant safety

Approved. The validator finds the latest committed
`governance/b0-report.json` revision reachable from `HEAD`, requires that
single-parent evidence revision to be the direct child of the evaluated
commit, restricts its diff to the exact evidence-only paths, reads evidence
bytes from that Git tree, and verifies the recorded SHA-256 digests against
those frozen bytes. Later working-tree changes do not rewrite historical
claims. Regression coverage confirms validation on ordinary descendants and
merge tips.

### R6 — local parent allowance without weakening hosted binding

Approved. Local runtime-probe validation accepts only the executing `HEAD` or
its first parent `HEAD^`, which supports the two-commit evidence discipline.
Hosted validation remains strictly bound to `GITHUB_SHA`; the local-parent
allowance is not used in hosted mode.

### Evidence-only child `cc06714`

Approved. `cc067143fd3143eaba490c4dcc9f3765db1d70f2` is the direct child of
`ca424270ffc9cd9c2eecf3382c63840cc44b381a` and changed only
`.superpowers/sdd/task-6-report.md`, `governance/b0-report.json`, and
`governance/b0-status.yaml`, the then-required evidence paths. Its report
records `ca424270ffc9cd9c2eecf3382c63840cc44b381a` and tree
`9dfdc567456a5788d5524169c1f7522ad88d52f1`; all 31 checked-in-evidence
digests recompute from the frozen `cc06714` Git tree. B0.2 remained open with
`authoritative_remote_url_absent`, B0.5 remained open with
`hosted_ci_not_executed`, and `parallel_handoff_ready` remained false.

### R7 — internal-tree exclusion and practical R5 validation

Approved. `25b44ab1ff1e9cd268a5144cef1727cc98b1defb` excludes `.git`, `.claude`,
`.superpowers`, `.venv`, and `.pytest_cache` from the lockfile-uniqueness scan.
It did not require frozen B0 report regeneration. Its successful validation as
a later descendant is practical confirmation that R5 no longer anchors frozen
evidence to the moving checkout.

## Independent closure audit

The complete `origin/main...2d8db62e7a52ad3c0dc628e8197f5b26cd75eeb2`
diff was reviewed across governance, validator, tests, hosted artifacts,
process documentation, the consolidated plan, and the parallel-work guide.

1. **Provenance truthfulness and authority pins:** approved. The transition is
   only from provisional/local authority to the canonical remote URL
   `https://github.com/TimoKruth/EvoNN-Research.git`. The source commits,
   declared versions, import times, Git object identities, roles, ownership,
   and SHA-256 content digests are unchanged and remain validator-pinned.
2. **Exact hosted artifact bytes:** approved. The Linux and macOS blobs are
   byte-identical to their initial checked-in revisions, with SHA-256 values
   `f17ca8a8f35538d72c6a7585ef013a7e1f5d50484fcc08d85ac672745d371c00`
   and `147e5c54a75bb9090eb3e94e06fe9c9f656ca751df12fdb5fc8950bf4398e157`.
3. **Workflow/run/attempt/URL binding:** approved. The schema and validator bind
   each platform to its exact workflow name, run ID, attempt `1`, canonical run
   URL, push event, `main` branch, successful conclusion, host, backend, and
   artifact identity. Linux is run `29658842317`; macOS is run `29658842318`.
4. **Closed schema and anti-fabrication:** approved. Schema `2.0.0` has exact
   required field sets at the report and hosted-entry levels, rejects missing
   and unknown fields, and preserves at least the prior schema `1.0.0` blanket
   hosted-field prohibition by rejecting fabricated top-level hosted claims as
   unknown fields.
5. **Artifact paths and Git modes:** approved. Paths must be normalized UTF-8
   repository-relative paths. Verification uses `--no-replace-objects`, checks
   every Git-tree component, rejects symlink/submodule/non-directory modes, and
   accepts only regular blob modes `100644` or `100755` at the final path.
6. **Historical manifest digests:** approved. Recomputing the Stratograph and
   Prism manifest bytes at
   `f68856f0c2fdf0ebc73671264b5a3ab0cff3b224` yields respectively
   `14513f116dd53bfd2fd9fa4345593185589b3aee297b57bac32f37dac45c6aa9`
   and `5719a3843c8106193c126084cad2837dc3111cb9a795bb08a2cf129b52e7113c`,
   exactly matching the hosted artifacts.
7. **Hard-coded hosted revision scope:** approved. Code, design, and plan
   explicitly identify
   `f68856f0c2fdf0ebc73671264b5a3ab0cff3b224` as a B0-closure-specific
   hosted-evidence pin, not reusable runtime, workflow, branch, or future-gate
   policy.
8. **Distinct revision identities:** approved. The final report will evaluate
   Commit A and its tree, while the hosted entries separately and truthfully
   identify `f68856f0c2fdf0ebc73671264b5a3ab0cff3b224` as the revision actually
   tested by GitHub Actions.
9. **R5 merge and descendant behavior:** approved as described above and
   covered by clean-clone descendant and merge-tip regressions.
10. **R6 local and hosted behavior:** approved as described above; local accepts
    `HEAD`/`HEAD^`, hosted accepts only `GITHUB_SHA`.
11. **Plan/guide/process consistency:** approved. The documents consistently
    preserve the two-commit closure sequence, separate Commit A from the hosted
    tested commit, retain joint Phase 0 interface freeze as the next transition,
    and describe the remote-pinning change as a provenance-state transition
    rather than a source upgrade.
12. **Clean-clone behavior:** approved. Governance validation and representative
    R4/R5/schema-2 closure regressions pass in a `--no-local` clone with the
    canonical remote identity and no ignored local artifacts.
13. **Full Git history in hosted workflows:** approved. Both
    `.github/workflows/linux-trust.yml` and
    `.github/workflows/macos-engines.yml` retain `fetch-depth: 0`.

## Findings

No required findings were found in the reviewed closure diff. Consequently,
no finding-specific fix commits were necessary and no required work is deferred
to Commit B.

## Verification commands

Focused reciprocal and closure verification included:

```bash
git show --check ca424270ffc9cd9c2eecf3382c63840cc44b381a
git diff ca424270ffc9cd9c2eecf3382c63840cc44b381a^ ca424270ffc9cd9c2eecf3382c63840cc44b381a
git show --check cc067143fd3143eaba490c4dcc9f3765db1d70f2
git diff cc067143fd3143eaba490c4dcc9f3765db1d70f2^ cc067143fd3143eaba490c4dcc9f3765db1d70f2
test "$(git rev-parse cc067143fd3143eaba490c4dcc9f3765db1d70f2^)" = "ca424270ffc9cd9c2eecf3382c63840cc44b381a"
git show --check 25b44ab1ff1e9cd268a5144cef1727cc98b1defb
git diff 25b44ab1ff1e9cd268a5144cef1727cc98b1defb^ 25b44ab1ff1e9cd268a5144cef1727cc98b1defb
uv run --locked --group dev pytest -q \
  tests/policy/test_repository_governance.py \
  tests/policy/test_b0_integration_report.py \
  tests/policy/test_b0_ci_bootstrap.py
```

The complete Commit A verification set is:

```bash
uv lock --check
uv sync --all-packages --group dev --locked
uv run --locked --group dev pytest -q
uv run --locked --group dev ruff check .
uv run --locked --group dev python scripts/policy/validate_import_boundaries.py
python3 scripts/policy/validate_repository_governance.py
uv run --locked --group dev python scripts/policy/validate_backend_capabilities.py
scripts/ci/b0-policy-checks.sh

REPO=/Users/timokruth/Projekte/EvoNN
for script in \
  shared-checks.sh benchmarks-checks.sh compare-checks.sh contenders-checks.sh \
  prism-checks.sh topograph-checks.sh stratograph-checks.sh primordia-checks.sh
do
  (cd /tmp && "$REPO/scripts/ci/$script")
done

uv run --locked --group dev pytest -q \
  tests/policy/test_repository_governance.py \
  tests/policy/test_b0_integration_report.py \
  tests/policy/test_b0_ci_bootstrap.py
git diff --check
git status --short
```

## Approval

The reciprocal reviews R4–R7 and the independent complete-diff audit are
approved. The hosted artifacts qualify only bootstrap runtime/portability
contract behavior; they are not scientific evidence, backend qualification,
numerical-equivalence evidence, performance evidence, or general portability
evidence. There are no unresolved required findings. Commit B may be created
only as Commit A's direct child and must carry the final schema `2.0.0`
evidence transition without changing the reviewed preparatory implementation.

## Evidence-only attempt and transition-test repair

The first evidence-only closure attempt,
`dffce38d598c1636f9be2c289ff6baa233d19d04`, was blocked by five full-suite
failures in transition-sensitive policy tests. It did not establish a completed
Commit B. The approved test-only repair lineage was
`6a4d78d8dd94ed0b7d1835020ec2caa334b7f1d0`,
`d4a8d2800483f8810d392b4c3d1fdc467081e2bb`, and
`ee3979a341aec1ff5568237cecc00787eb2e5757`, transplanted before the evidence
transition as `60cb04d153d77e0bced397ac0ac3beb12e1ef355`,
`dce856b598cbe606d1ab6b893677c0ad7f6c8cb4`, and
`85d17e61b46e1fe5960a8794381f1235c53bc445`.

Review reproduced and permanently repaired four additional test gaps:

1. A frozen-status regression could false-pass by falling back to the moving
   checkout status; it now commits an explicitly open frozen status and proves
   the frozen and live bytes differ.
2. The schema mutation helper did not traverse `verification.summary`; it now
   validates that nested closed mapping directly.
3. The checked-in-evidence digest regression did not prove every digest was
   checked; it now corrupts every recorded digest and requires a path-specific
   SHA-256 error for every entry.
4. The historical `closure_pending` fixture derived identity from the moving
   current `evaluated_commit`; it now loads and asserts the frozen historical
   status at `B0_REPORT_LEGACY_REVISION`.

The added regressions produced meaningful RED failures against their respective
pre-fix revisions for the intended missing checks. GREEN verification covered
the schema-2 closed state, the frozen schema-1 open transition, first-parent
merge carrying, and later schema-2 reattestation. It included 249 changed-module
tests and the B0 policy suite with 451 passed and 2 deselected, plus Ruff, diff,
and clean-status checks. Task 31's formal verdict was **Spec compliance: PASS**
and **Task quality: APPROVED**.

The repair changed only
`tests/policy/test_b0_integration_report.py` and
`tests/policy/test_repository_governance.py`. It did not weaken or modify any
production validator, governance content, or evidence content. All reciprocal
review conclusions and the B0-only hosted-revision pin conclusion above remain
unchanged. Commit B has not been recreated or completed by this repair.
