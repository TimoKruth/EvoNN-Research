---
document_kind: project_history
status: current
authoritative: false
---

# EvoNN Project History

**Consolidated:** 2026-09-07, against main
`646dde2270d540877c7d9165718eb01a5b05b84c`.
This is the compact record of completed work, review decisions and verification.
Current capabilities and commands live in [README](README.md); outstanding work
and acceptance criteria live in [CONSOLIDATED_PLAN](CONSOLIDATED_PLAN.md).
Historical success is scoped to its recorded revision and evidence class.

## Durable decisions

| Decision | Reason and continuing consequence |
| --- | --- |
| Independent Lab and Product, file-based interop | Neither imports the other's runtime. Lab producer I1 alone cannot authorize Product behavior; Product I2 is also required. |
| One uv workspace; seven packages; data-only benchmarks | Shared provides contracts/infrastructure; engines remain distinct and Compare orchestrates files/CLIs. |
| One consolidated execution plan | The July critique identified conflicting plans and false-positive gates. Work packages, priorities and gate criteria now have one owner document. |
| Pinned specifications and historical evidence | Exact Git objects and digests keep B0 and interface decisions reproducible. Moving a current source is not a harmless documentation edit. |
| Strict import-primitive prohibition | The attempted partial Python interpreter could not soundly cover dynamic loading. The permanent production policy rejects specified acquisition forms instead; it is a syntax restriction, not a Python sandbox. The detailed negative result remains a required evidence file. |
| Explicit accounting and evidence classes | Failure, invalid attempts, inherited work, budget coverage and backend classes cannot be silently collapsed into successful scientific results. |
| Local POSIX persistence boundary | Transactions, locks, descriptor reads and atomic publication protect application-owned runs. They do not promise hostile same-privilege isolation or authenticity against coordinated rewrites. |
| GitHub approval count zero (2026-09-07) | The owner removed the redundant multi-account approval step. CI, branch freshness, conversation resolution and substantive review remain; historical amendment evidence is preserved. |
| GPL-3.0-only (2026-09-07, #21) | Root and seven package license files support repository and standalone distribution. Third-party asset licenses remain separate. |

## Specification comparison — July 2026 assessment

The former HTML comparison contrasted a researcher-operated Lab (four engines,
canonical packs, comparative fairness, file exports and MLX scientific runs)
with a practitioner-facing Product (automatic portfolio, user-data/split
controls, isolated evaluators/workers, qualified runtime profiles, Web UX and
verified deployment bundles). Both specifications share explicit accounting,
independent engine lineages, typed artifacts, contender floors and visible
failure/unsupported states. This describes specification scope, not implemented
capability or a measured implementation-cost ratio.

The useful cross-cutting findings became the Lab integrity requirements:
deterministic RNG, resumed/uninterrupted equivalence, atomic checkpoints,
measured/proxy labeling, read-only exports, protected-label boundaries and real
speciation before NEAT claims. The report's old “core and shell” composition
proposal is superseded by the program charter's independent Lab/Product tracks
and versioned artifact boundary; it does not authorize sharing runtime code.

## Bootstrap and interface history — July 2026

The initial plan critique identified missing accounting, reproducibility,
reference integrity, contender adequacy, statistical/transfer bars and interop
acceptance criteria. Revision 2 incorporated these into the phased plan. It did
not certify that the planned implementation already existed.

B0 established remote-pinned authority, the seven package skeletons and data
layout, strict import/dependency policy, two hosted CI lanes and a transition-safe
integration report. The closure-specific hosted evidence tests commit
`f68856f0c2fdf0ebc73671264b5a3ab0cff3b224`: Linux run `29658842317` and macOS
run `29658842318`. Exact probe JSON is retained in
[governance/evidence/b0/hosted](governance/evidence/b0/hosted). It proves
`bootstrap_probe_only` runtime availability, not scientific backend qualification.
The implementation/evidence-commit relationship is preserved in
[the B0 report](governance/b0-report.json) and
[the closure record](.superpowers/sdd/task-6-report.md).

The reviewed Phase 0 producer/consumer contracts were hardened through the
A-double-prime amendment: strict containers, canonical UTC and catalog error
classification. Public symbols/signatures stayed unchanged. Freeze v2 supersedes
v1, preserves its history, and records the exact reviewed surfaces and reciprocal
reviews. Its protected merge is `5a98d9d45c4f2a7bc35bc75f93141473d0769e94`;
[the freeze record](governance/phase0-interface-freeze.yaml) records verified
merge and authorization. Phase 0 implementation subsequently proceeded.

## Maintenance integration — September 2026

All entries below are integrated into the recorded main baseline. Linux and
macOS required checks passed for every merged candidate. Local test counts are
revision-specific focused selections, not additive totals or a new gate.

| PR | Change and local review evidence | Integration commit |
| --- | --- | --- |
| [#10](https://github.com/TimoKruth/EvoNN-Research/pull/10) | Transactional row/tip and schema writes, safe paths and report publication; 97 focused storage/workspace tests. | `e07002a71ec6f705d6525a9ee872123ff5e22d00` |
| [#11](https://github.com/TimoKruth/EvoNN-Research/pull/11) | Scoped immutable Git-read cache and synthetic reference runner; 29 targeted tests plus standalone governance. | `59b865a78e67f3804d8331f052e64036ec2d1490` |
| [#12](https://github.com/TimoKruth/EvoNN-Research/pull/12) | Failed/invalid attempt charging and durable resume reuse; 41 reference tests. | `39912f11a8c7ff1c651a80c31664bf4771ddd749` |
| [#13](https://github.com/TimoKruth/EvoNN-Research/pull/13) | Remove duplicate feature-push CI while retaining PR/main/manual events; 15 workflow tests, one recursive self-test deselected. | `77734f048ed890a4feb122a6a9a60e19ae3fe4a5` |
| [#14](https://github.com/TimoKruth/EvoNN-Research/pull/14) | Shared foundation entry point and complete cross-host selection; 718 foundation and 28 workflow/workspace tests, two recursive/matrix cases deselected. | `86630dfcec47c3ea9514b0a6fce7f1f3e32f481b` |
| [#15](https://github.com/TimoKruth/EvoNN-Research/pull/15) | Verified read-only RunReader, shared ownership and explicit WAL refusal; 14 reader tests. | `9d17b421559d811fb010063a7acf93ff06c7e1f8` |
| [#16](https://github.com/TimoKruth/EvoNN-Research/pull/16) | Diagnostic identity/checkpoint/accounting consistency; 48 reference tests. | `7fd488b1548466185c40e777e734839ceb219876` |
| [#17](https://github.com/TimoKruth/EvoNN-Research/pull/17) | Resume bound to seed and protected-label identity; 60 reference tests. | `e24a524cb8c7c949ad6bad9d76582f8ab842ed51` |
| [#18](https://github.com/TimoKruth/EvoNN-Research/pull/18) | Machine-readable evidence for eight real kill/resume cases; 12 probe tests. | `fe3baaa0235180f8c80c7c5c8ba472e2d2139af7` |
| [#19](https://github.com/TimoKruth/EvoNN-Research/pull/19) | Atomic no-clobber evidence publication; 22 publication/probe tests including concurrent writers and I/O failure paths. | `3b1758167be8e3b47c8242e1fe4fc3ecbc1a0b87` |
| [#20](https://github.com/TimoKruth/EvoNN-Research/pull/20) | Generate, validate and retain explicit synthetic JSON on both hosts; 17 workflow and 773 foundation tests, repository Ruff passed. | `646dde2270d540877c7d9165718eb01a5b05b84c` |
| [#21](https://github.com/TimoKruth/EvoNN-Research/pull/21) | GPL licensing; merged separately during the requested integration pause. | `9916f2265cec29997b29fb08cdd10fea2b952d32` |
| [#22](https://github.com/TimoKruth/EvoNN-Research/pull/22) | CodeRabbit configuration; locally validated against its official schema. | `540ea47889ef8600ded635dee4107343d7573d6d` |

**#11 metadata exception:** GitHub wrote the protected merge to main, then
returned an internal GraphQL error before updating PR metadata. Exact parents,
reviewed tree and ancestry were verified. Fast-forwarding its source branch to
the already-published merge caused GitHub to close the empty PR. GitHub says
closed, not merged; its code is integrated. No dummy merge was created.

**#9 catalog proposal:** closed without merging at the owner's request on
2026-09-07. It altered frozen catalog tests/IDs without the complete replacement
freeze/validator/trust-anchor binding; no production benchmark was admitted.
Its successor requirements are incorporated into WP-0.1b/0.8.

## CodeRabbit review record

- #16 alleged missing over-budget, partial-run and resume-ID invariants. The
  existing `BudgetAccounting` model already enforces these before cross-file
  diagnostic validation. Five end-to-end mutations (over budget, full marked
  partial, partial marked full, cache without resume ID, resume ID without
  cache) were rejected without output or source mutation. The false-positive
  thread was resolved; no duplicate validator was added.
- #22's prior lockfile-exclusion finding was addressed by explicit `uv.lock`
  inclusion, then its thread was resolved. Schema validity alone does not prove
  effective file selection in a hosted review.
- #20's summary reports zero actionable comments and no review threads, with
  minimal merge risk at `267f130cc9910726484aaede932e5c2bed6d75c0`. It also
  contains a docstring warning: 0% coverage against 80%, five analyzed
  functions. This warning was omitted from the original handoff and later
  explicitly reported to the owner.
- The same #20 comment contains a path-filter skip notice using repository
  configuration and a later review section using defaults that lists all five
  changed files. Preserve that distinction; do not equate a green bot status
  with proven full configured coverage. Follow-up is recorded in WP-0.1a.

- During documentation consolidation, [#23's bot notice](https://github.com/TimoKruth/EvoNN-Research/pull/23#issuecomment-5571484447)
  confirmed all 29 changed files were skipped by path filters. No review threads
  were opened. This establishes missing configured coverage for this PR; the
  bot's successful status is not a completed content review. Configuration
  correction and verification are tracked in WP-0.1a.

See [the #20 summary](https://github.com/TimoKruth/EvoNN-Research/pull/20#issuecomment-5570512089)
and [CodeRabbit path-filter documentation](https://docs.coderabbit.ai/configuration/path-instructions).

## Verification of the integrated baseline

Final main's tree is `34704dd7857c9ef03b420e43544048adc56ee699`, verified as the
combination of original reviewed #20 and the reviewed GPL/CodeRabbit baseline.
All recorded integrations, including #11, are ancestors. Lock consistency,
standalone interface-freeze and repository-governance checks passed on the
identical candidate tree. No open PRs/issues remained at the subsequent project
assessment; that is a dated observation, not a permanent repository property.

| Evidence | Recorded result |
| --- | --- |
| [Final main Linux run 34122410854](https://github.com/TimoKruth/EvoNN-Research/actions/runs/34122410854) | Success on `646dde2`. |
| [Final main macOS run 34122410847](https://github.com/TimoKruth/EvoNN-Research/actions/runs/34122410847) | Success on `646dde2`; job execution 19m46s, including 18m46s B0 policies and 35s foundation, plus queue time before the job. |
| Original #20 Linux 34093992521 / macOS 34093992508 | Downloaded synthetic reports independently validated; identical baseline and all eight resumed row/checkpoint hashes across Linux x86_64 and macOS ARM64, Python 3.13.1. Source-directory digests compared within each host. |
| Governance-cache experiment | Same local 39 cases: 108.10s before, 45.87s after, 72.81s on a later version; Git subprocesses 226→160 on the same report. Variable samples are not a hosted speed guarantee; fixture-cloning optimization showed no reliable gain and was not retained. |

Hosted artifact links are retention-bound. B0's authoritative evidence is
checked in; the current synthetic reports are CI contract evidence, not a
promoted scientific registry. This integration closes neither Phase 0 nor its
engine-specific hooks. The empty catalog and catalog/regular-export acceptance
are the remaining functional dependency, as recorded in the plan.

## Document consolidation and retained references

Seven completed archive documents and the HTML specification comparison were
synthesized here; their complete bytes
remain available at the exact pre-consolidation commit linked below. Their
historical instructions and superseded status statements are not current work.
The plan's completed September narrative and local PR-review analysis were also
incorporated here. All later phase requirements and original WP IDs remain in
the sole execution plan.

| Consolidated source | Durable material retained here or in the plan | Exact original |
| --- | --- | --- |
| July 17 specification comparison | Lab/Product differences, shared integrity findings and the superseded core/shell proposal | [Full HTML analysis](https://github.com/TimoKruth/EvoNN-Research/blob/646dde2270d540877c7d9165718eb01a5b05b84c/spec-comparison.html) |
| July 17 Lab-plan critique | Gate/accounting corrections, evidence classes, complete contender/statistical/transfer/interop scope | [Full critique](https://github.com/TimoKruth/EvoNN-Research/blob/646dde2270d540877c7d9165718eb01a5b05b84c/archive/2026-07-17-LAB_PLAN_CRITIQUE.md) |
| B0 task 2 provenance report | Pinned authority, single plan and traceability | [Full report](https://github.com/TimoKruth/EvoNN-Research/blob/646dde2270d540877c7d9165718eb01a5b05b84c/archive/2026-07-17-gate-b0-task-2-provenance-controls-report.md) |
| B0 task 3 workspace report | Seven-package/data-only model and standalone checks | [Full report](https://github.com/TimoKruth/EvoNN-Research/blob/646dde2270d540877c7d9165718eb01a5b05b84c/archive/2026-07-18-gate-b0-task-3-workspace-skeletons-report.md) |
| B0 task 4 import report | Rejected partial-interpreter approach, strict production-language policy and reviewed exceptions | [Full report](https://github.com/TimoKruth/EvoNN-Research/blob/646dde2270d540877c7d9165718eb01a5b05b84c/archive/2026-07-18-gate-b0-task-4-import-boundaries-report.md) |
| B0 task 5 CI report | Cross-host bootstrap and honest qualification limits | [Full report](https://github.com/TimoKruth/EvoNN-Research/blob/646dde2270d540877c7d9165718eb01a5b05b84c/archive/2026-07-18-gate-b0-task-5-ci-bootstrap-report.md) |
| B0 closure design | Immutable implementation/evidence binding and offline hosted validation | [Full design](https://github.com/TimoKruth/EvoNN-Research/blob/646dde2270d540877c7d9165718eb01a5b05b84c/archive/2026-07-19-b0-closure-design.md) |
| B0 closure implementation plan | Completed closure sequence; later actions supersede its historical branch/merge instructions | [Full procedure](https://github.com/TimoKruth/EvoNN-Research/blob/646dde2270d540877c7d9165718eb01a5b05b84c/archive/2026-07-19-b0-closure-implementation-plan.md) |

In a full clone, `git show 646dde2:archive/<original-filename>` retrieves each
archived original without network access; `git show 646dde2:spec-comparison.html`
retrieves the HTML comparison. No Git history is rewritten.

These reference/evidence files intentionally retain their canonical paths:

| Retained surface | Why it is separate |
| --- | --- |
| [claude-spec](claude-spec/README.md), [program charter](PROGRAM_CHARTER.md), [Product interop](claudex-spec/19-research-interop.md) | Pinned normative authority; changing bytes requires a source upgrade, not summary editing. |
| [Product interop reference](claudex-spec/README.md) | Only the consumer contract stays local; the unrelated Product corpus is retrievable at an exact Git revision. |
| [governance](governance/SPEC_TRACEABILITY.md) and [upgrade process](governance/SPEC_UPGRADE_PROCESS.md) | Canonical source roles, transition procedure and machine-checked evidence. |
| [reviews](reviews), [B0 task 6 record](.superpowers/sdd/task-6-report.md), [dynamic-import negative result](research/logs/2026-07-18-dynamic-import-policy.md) | Historical validator/test evidence; their dated statements must not be read as current status. |
| [PARALLEL_WORK_GUIDE.md](PARALLEL_WORK_GUIDE.md) | Short compatibility pointer with the exact freeze marker required by the standalone validator. Lane/workflow content is consolidated in the plan. |
| Package/config READMEs | Local navigation markers pointing to central guidance; no duplicate plans. |

## 2026-09-07 — Reviewed catalog successor (merged #25/#27)

The successor to closed PR #9 reuses the eight metadata definitions and three
packs from exact proposal commit `40b704b49bdec262e9bf60ff456f8eb94a8c0b91`.
This is a fresh candidate based on the consolidated main, not acceptance of #9.
`shared-benchmarks/provenance/tier_a_catalog_v1.json` records ten source blobs
independently fetched from predecessor commit
`3652e0a32a907b51fb26a56fa9650ba258cb9054`; Git blob IDs and SHA-256 were
recomputed from returned bytes. The original field mapping remains retrievable
at `40b704b49bdec262e9bf60ff456f8eb94a8c0b91:shared-benchmarks/migration/2026-07-28-tier-a-catalog-admission.md`.

The predecessor's contender loader uses a two-way train/validation split
(default validation fraction 0.2, seed 42, target stratification for
classification). It supplies no protected third test split; that is a conditional protocol
limitation, not a general Lab Phase 0/1 blocker. Data/cache hashes,
runtime support and contender floors remain unproved. Introducing a protected
third split changes benchmark meaning and must use new canonical IDs; those
choices cannot be silently folded into the eight historical IDs.

This candidate keeps all definitions `planned` and `catalog_only`. Independent
producer/consumer reviews approve `0ece535d8b68c8701a17e404baa25dd6b20be52e`
and its exact source provenance. Binding `170fc9e19db0f7039d2ffd351d01406af16a8f80`
is its direct child. The replacement validator and trust anchor preserve v1/v2
verdicts and reject transient history tampering. Both reviewers separately
approved the binding and three-pack export fixture composition. Protected merge
#25 and the separate verified #27 attestation completed authorization.

Local candidate checks: foundation **773 passed** (25.50s); catalog/interface
contracts **145 passed** (3.09s); inventory **5 passed**; Ruff and diff checks
passed. The unchanged standalone freeze validator rejected exactly the two
intentional frozen changes (`test_catalog.py`, `canonical_ids.yaml`). This is
an expected draft blocker, not a waived policy failure. After the reviewed v3
binding, both governance validators pass. Foundation coverage now passes **776
tests** (27.51s), including three real-pack/unsupported-export fixture cases.
Those fixtures assert schema composition, zero executed evaluations, complete
unsupported visibility and typed three-file roundtrips; they prove no dataset
execution or scientific floor. The producer independently passed all **142**
historical freeze tests and **13** successor/history/guide tests; the consumer
passed **16** targeted tests plus two guide tests on the rebound implementation.

## 2026-09-07 — Remove reference material without current Lab value

Removed 45 unpinned Product reference files (chapters 00–18, ADRs,
research notes, schemas and examples). They neither govern Lab implementation
nor run in its tests. Their complete original is preserved at
[`836cfffc204babab70f8c222b45668df03e04564`](https://github.com/TimoKruth/EvoNN-Research/tree/836cfffc204babab70f8c222b45668df03e04564/claudex-spec).
The Product-owned consumer contract `claudex-spec/19-research-interop.md`
remains byte-identical, as do the Lab specification, charter and authority pins.
This removes local copies, without changing Product scope or its acceptance.

Retention is based on current engineering value. A test demanding an old
filename or phrase is not sufficient justification. Historical review results
and failed experiments should be compactly summarized here; exact original
proof can be verified in Git instead of remaining duplicated in every checkout.
The remaining review/task-report copies currently participate in active
freeze/B0 validation. Their removal requires the bounded evidence-storage
change specified in WP-0.1b, not removal of the underlying integrity checks.

## 2026-09-07 — Phase 0 contract acceptance

PR #25 merged at `322834900aa99a267b78b789a733e96ac205dd04`; #27 carried its
verified authorization onto canonical main. The acceptance receipt records the
exact carrier commit/tree, hosted CI IDs and artifact hashes, plus the complete
WP-0.1–0.10 test map. Both hosted lanes passed 776 foundation tests and all
selected policy/package checks. Actual tested PR checkouts are distinguished
from canonical commits and accepted only with identical trees and ordered
merge parents, verified by checkout logs and fresh artifact downloads.

Independent producer and consumer reviews confirmed the actual freeze and
attestation. CodeRabbit's supplemental-test freeze request (#25) was declined:
normal reviewed consumer tests cannot rewrite the explicitly frozen contracts.
Its HEAD/main authorization concern (#27) was resolved by retaining offline,
ref-independent proposal validation and separately verifying canonical main
before operating on authorization. No premature lane creation occurred.

The acceptance validator binds reviewed receipt bytes to their exact evidence
parent and rejects rewritten, removed, restored or multiply introduced evidence,
unrelated implementation changes during introduction, and premature/malformed
parent checklists. Historical v1/v2 verdicts remain unchanged. No permanent
raw-log archive or new narrative review files are added.

This closes contract foundations only. Catalog entries remain planned metadata;
regular export composition and actual no-op integrity are separate evidence.
Engine-specific resume and Topograph speciation/reproduction are explicitly
pending. No backend is scientifically qualified and no multi-hour training ran.
