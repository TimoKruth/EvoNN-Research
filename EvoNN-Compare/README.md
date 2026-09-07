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
as a sibling directory before starting fresh. Named `--preset` aliases require
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
