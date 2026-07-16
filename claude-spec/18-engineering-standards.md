# 18 — Engineering Standards

## Git And PR Policy

- Never work directly on `main`; never push directly to `main`.
- Issue-specific branches: `agent/<issue>-<slug>` or `user/<issue>-<slug>`.
- One git worktree per issue when multiple efforts need isolation.
- Merge through PR review only.
- Engine-advancement PRs must complete the decision-gate evidence summary
  (ch. 05): one decision category; workspace trend report + dashboard paths;
  exact case IDs and run IDs; dashboard slices reviewed; lane
  operating/accounting/repeatability states. Reviewers must never have to
  reconstruct a claim from chat or shell history.
- Before a PR: run the relevant package checks from the repo root; for
  shared-surface changes run all five Linux-safe lane scripts; for
  Prism/Topograph runtime changes also run the macOS package checks.
- Commit hygiene in mixed workspaces: stage explicit paths, never blind
  `git add -A` (the autoresearch-in-monorepo rule generalizes).

## Testing Expectations

- Per-package `tests/` with pytest; ruff clean.
- Every engine keeps a tiny end-to-end CLI smoke test with a checked-in
  tiny config (the `tiny_smoke` pattern) so `evolve → inspect → report →
  export` is exercised in CI.
- Contract tests pin export shapes (manifest/results/summary) and registry
  row schemas; synthetic fixtures cover ceiling ties, missing runs, backend
  drift, mixed-budget ambiguity (ch. 12).
- Behavior-affecting refactors happen only where tests pin behavior first.
- Known-flaky tests (e.g. MoE gradient-flow history) are documented and
  deselected explicitly, never silently skipped.
- Policy tests are legitimate: e.g. a test asserting no competing active
  plan files can reappear.

## Documentation Policy

Planning hierarchy (exactly one active execution plan):

- `VISION.md` (root) + package `VISION.md` — research framing only, never
  execution checklists.
- `CONSOLIDATED_PLAN.md` — the single active execution plan; new branch
  planning is a short PR checklist or a small section here.
- `HARD_REMAINDER_PLAN.md` — companion backlog for hard unfinished work;
  items promote into the consolidated plan only with an owner, validation
  lane, acceptance criteria, and expected evidence artifact.
- Contracts and gates: `BENCHMARK_LADDER.md`, `BUDGET_CONTRACT.md`,
  `BUDGET_ACCOUNTING_POLICY.md`, `TELEMETRY_SPEC.md`,
  `RESEARCH_DECISION_GATE.md`.
- Operational entry points: root `README.md`, `MONOREPO.md`, package
  READMEs.
- Per-package `ARCHITECTURE_RULES.md` — the distinctness rules (own genome/
  compiler/operators/telemetry; shared boundary intentional, shared core
  not; standalone possible; comparable outside, different inside).
- Research logs: package `RESEARCH_NOTES.md` / `CHANGELOG.md` recording
  work, commands run, findings, and bottlenecks per dated entry.

Do not keep: competing root planning files; stale plan hierarchies;
package-local bootstrap plans that only record history; deprecated-project
plans as active guidance. If docs and code disagree, code is truth and docs
get fixed.

## Evidence And Claims Discipline

- Claims link fair-matrix artifacts, trend rows, dashboard slices, and exact
  run workspaces (canonical paths printed by the CLI, not paraphrased).
- A lane is never just "trusted" — name the operating state.
- Store claim-supporting runs durably (promote to the registry), not only in
  `.tmp`.
- Do not commit raw workspaces; keep promoted summaries and registry rows
  compact and auditable.

## Config Conventions

- All run configs are Pydantic-validated YAML with a snapshot written into
  the run directory.
- Named official-lane configs are checked in per engine
  (`smoke`, `tier1_core_eval64/256/1000`, `tier_b_core_eval256/1000`, …).
- New feature flags default to off-or-better-default with the previous
  behavior restorable by config (the Track B compatibility discipline).
- Env-var overrides for shared asset locations are documented per package.

## Operational Safety Rules

- Never run two processes writing to the same DuckDB file; per-run DBs make
  parallel runs safe by construction.
- Long runs are resumable (`--resume` / `state.json`); interruption is a
  normal lifecycle event with telemetry, not an error state.
- Runtime envelopes are part of proof design: scale a new proof from one
  seed × one budget within an agreed wall-clock envelope before running the
  full seed × budget matrix.

## Quality Scorecards

Each engine maintains a quality scorecard / baseline matrix documenting:
official-lane run status, benchmark completeness, artifact paths, and known
caveats (e.g. LM caveats), refreshed when lanes change. These documents are
operational truth for "what currently works," distinct from vision docs.
