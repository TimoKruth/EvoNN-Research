# EvoNN-Compare

File-only orchestration and comparison. Compare invokes participating system
CLIs, validates portable exports through Shared, and rebuilds derived reports
without importing models or rerunning training.

```bash
uv run evonn-compare fair-matrix --workspace .artifacts/compare \
  --pack tier1_core --budgets 64 --seeds 42 --systems contenders \
  --timeout 1200 --fit-timeout 180
uv run evonn-compare workspace-report .artifacts/compare
uv run evonn-compare benchmark-audit --workspace .artifacts/compare --pack tier1_core
uv run evonn-compare output-quality .artifacts/compare
```

`trend-report` supports benchmark, budget and system filters. `dashboard`
rebuilds the static HTML/JSON pair. `compare <export> <export>` inspects an ad
hoc case. Runs accumulate by default. `--reset-workspace` archives the previous workspace
as a sibling directory before starting fresh. The default dataset cache is a
stable sibling `<workspace>.cache`; resets reject older internal cache references
to preserve their auditability. Named `--preset` aliases require
a checked-in runtime evidence binding; unavailable future presets fail.
Source exports and workspace JSONL are
immutable evidence. Interrupted or altered trend records are rejected, never
silently repaired. Case summaries, markdown and the dashboard are derived.

A case binds pack, all seven budget dimensions and seed. Seeding regimes and
prior provenance stay distinct. Exporter blockers, failed/missing outcomes,
optional skips and measurement gaps remain visible. Contract fairness alone
is not a scientific claim. Engine-only cohorts cannot establish an external
floor. The dashboard separates all-system and projects-only views, ceiling
ties, per-seed evidence and descriptive multi-seed intervals.

`benchmark-audit` defaults to **Phase 1 contract readiness**. Add
`--decision-grade` to require repeated low/mid evidence, clean code,
complete floor/cache/runtime provenance and L3 outputs. The frozen catalog's
`planned` status is not silently rewritten. The phase plan and verified exit
status remain in [CONSOLIDATED_PLAN.md](../CONSOLIDATED_PLAN.md).

## Durable evidence and decisions

```bash
uv run evonn-compare evidence promote .artifacts/compare \
  --registry .artifacts/evidence --label before --copy-artifacts
uv run evonn-compare evidence validate --registry .artifacts/evidence --require-artifacts
uv run evonn-compare evidence report --registry .artifacts/evidence \
  --request analysis-request.json --require-artifacts
```

The registry index is append-only and hash-chained under one OS-locked writer.
Repeated promotion of identical label/run evidence is a no-op; conflicting
identities and partial writes fail. `evidence supersede --old <record-id>
--new <record-id> --reason <reason>` records replacement without editing history.
The manifest, JSON/Markdown report and dashboard are rebuildable views.

`--copy-artifacts` retains bounded JSON/config/report files, at most 1 MiB per
file. Large weights, datasets and source workspaces stay external. Copies record
historical validation; `--require-artifacts` rechecks original export bytes,
dataset caches, admission and every score/policy field used in a decision.
Missing or changed external dependencies block new citations. Do not commit a
registry whose required dependencies cannot be supplied to both CI hosts.
Producer branch/preset remain explicitly unrecorded when the exporter did not
capture them. Consumer provenance never substitutes for producer provenance.

An analysis request names before/after labels and exact source revisions, plus
explicit panels with `pack`, `budget`, `engine`, `benchmarks` and `seeds`.
It follows `evonn_compare.statistics.AnalysisRequest`, policy
`paired-seed-relative-v1`; `materiality` defaults to 0.01 symmetric relative
effect and must be chosen before interpreting results. Missing expected cells,
duplicate seed observations, dirty sources and runtime/data drift block L4.
Only the declared code revision may differ; filesystem locations do not define
a scientific protocol. Controls remain comparison context, not target engines.

The independent statistical unit is a matched seed mean over the fixed panel,
using direction-aware `2*(after-before)/(|after|+|before|)` effects; raw benchmark
deltas are retained. Benchmarks saturated across every paired seed are excluded;
a single ceiling tie contributes zero and cannot hide another seed's regression.
Intervals use 4096 deterministic paired-seed bootstrap resamples. Coverage needs
three seeds (two only for Tier B/C overnight). `clear_gain` additionally requires
at least six nonzero seed effects and a two-sided signed-rank permutation test,
with Holm correction across tested panels. Three favorable seeds can produce
`likely_gain`, which does not itself authorize promotion. Equivalence requires
the interval inside the practical-effect band; a nonsignificant test alone is
not equivalence. Small portfolios receive an explicit unavailable Friedman test.

L4 describes evidence quality and may accompany an inconclusive or negative
result. Statistical labels, aggregation labels and the single PR decision
category remain separate. Native, complete floor-backed evidence and clean
Tier-1 results are required for promotion; portability remains separately
labeled. Reports always include runtime costs, transfer readiness, LM flatlines
and provisional engine-role evidence, including unavailable reasons.

Engine-advancement PRs use the JSON evidence block described in the PR template.
`evidence decision-gate --registry evidence --body <pr-body.md>` rechecks exact
run/case IDs, named dashboard slices, lane states and the recomputed category.
Both hosted lanes execute the same checker; ordinary implementation tests do
not establish a performance claim.

For another host, `evidence pack --registry <registry> --archive <bundle.tar.gz>`
creates a complete dependency archive and checksum descriptor. Transfer the
compact registry plus that archive, then run `evidence hydrate --registry
<registry> --archive <bundle.tar.gz> --descriptor <bundle.tar.gz.json>`.
Hydration verifies archive size/hash, exact members, safe regular-file paths,
per-file hashes and all normal source/audit checks. It maps original roots only
at read time; producer paths, export bytes and registry rows remain unchanged.
Caches use the identical numeric-array verifier after exact path resolution.

Hosted CI can hydrate a versioned release asset from this repository when
`evidence/source_bundle.json` supplies `url` and the generated `descriptor`.
The archive remains outside Git. Missing assets, missing mappings and expired
sources block citations explicitly; no fallback to an unrelated local cache is
allowed when relocation is active.
