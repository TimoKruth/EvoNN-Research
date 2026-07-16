# 12 — Evidence Registry, Statistics, And Portfolio Decisions

Single-run wins and dashboard rankings are not scientific claims. This
chapter defines durable research memory (the evidence registry), the L4
statistical decision layer, and the rules for engine portfolio decisions.

## The Evidence Registry

A canonical, compact, append-only store of promoted comparison runs at repo
root `evidence/`. It is not a dump for every local `.tmp` run — promote only
runs that support a decision, a PR, or a durable research claim.

```
evidence/
├── index.jsonl              # append-only registry rows
├── registry_manifest.json
├── evidence_report.json     # rebuilt aggregate view
├── evidence_report.md
├── runs/<run_id>/…          # copied compact summaries (--copy-artifacts)
└── README.md                # retention, promotion, review rules
```

CLI: `evonn-compare evidence promote <workspace-or-summary> --registry
evidence --label <stable-cohort-label> [--copy-artifacts]`, plus
`evidence report` and `evidence validate [--require-artifacts]`.

### Registry row fields

`run_id`; timestamp; git commit; branch; pack; preset; budget; seed; backend
class; host/runtime fingerprint; systems included; contender-floor state;
output-quality level; lane trust state; budget-accounting state; summary
checksum; source paths; copied registry paths; task families; per-system
score summaries; dashboard/report paths; decision status ∈ {`exploratory`,
`candidate`, `promoted`, `rejected`, `superseded`}.

### Rules

- Rows are immutable after promotion except a supersession marker. Never
  hand-edit rows; add new rows for new evidence.
- Labels stay stable so before/after cohorts are comparable
  (e.g. `tier-c-floor-gap-after`).
- Large raw workspaces stay out of git; keep compact summaries only.
- `evidence validate --require-artifacts` MUST be green before registry
  evidence is cited in a PR; stale/missing artifacts are reported explicitly.
- The dashboard rebuilds its last-N history from registry rows, not from
  incidental `.tmp` directories.
- Single-seed evidence is exploratory unless the report says the
  repeated-seed gate is satisfied.
- A new engineer must be able to see why a claim was accepted or rejected
  without rerunning the suite.

## The L4 Statistical Decision Layer

Purpose: move promoted lanes from L3 measurable to L4 decision-grade —
preventing overclaiming from noisy small runs. Conservative by design; the
goal is not p-value theater.

### Minimum repeated-run gates

| Tier | Gate for promoted claims |
|---|---|
| A | 3 seeds |
| B | 3 seeds at local budget; 2 at overnight |
| C | 3 seeds at local budget; 2 at overnight, before decision-grade promotion |
| D | broad-lane only unless 3 clean repeated runs exist |

### Statistical summaries (computed over repeated runs)

per-system rank distribution; per-benchmark score distribution; per-budget
improvement slope; contender-floor margin distribution; ceiling-tie
exclusion; effect size against the best required contender; non-parametric
rank tests (Wilcoxon/Friedman-style) where enough benchmarks/runs exist;
bootstrap confidence intervals on deltas.

### Decision labels

Within-cohort and before/after cohorts get exactly one of:
`clear_gain`, `likely_gain`, `no_material_change`, `regression`,
`inconclusive`, `needs_more_runs` — plus the aggregation-level labels the
report emits for grouped runs (`blocked`, `inconclusive`,
`no_material_change`, `gain`). "Not enough evidence" is a first-class state;
uncertain comparisons are never silently ranked.

### Requirements

- Dashboard distinguishes "currently best observed" from "decision-grade
  improvement."
- Benchmark saturation (ceiling ties) never inflates win claims.
- Repeated-run variance visible for every promoted comparison.
- Engine-advancement PRs include before/after evidence bundles with
  statistical decision labels.
- Test fixtures cover ceiling ties, missing runs, backend drift, and
  mixed-budget ambiguity.

## Diagnostics The Report Must Emit

- **Minimum-seed blockers** per group (which claims lack the seed gate).
- **Transfer proof state** per promoted run: portable-contract vs
  native-proof, seed sources, boundaries; whether anything is
  native-transfer claim ready.
- **LM flatline diagnostics** from promoted LM rows (a system scoring flat
  across LM budgets is flagged, feeding Stratograph's diagnostic work).
- **Engine role labels** (first-pass, from promoted evidence groups and
  benchmark-family leads): `leader_candidate`, `challenger`, `specialist`,
  `seed_source_specialist`, `watch`.

## Engine Portfolio Rules

Portfolio sprawl is expensive; every engine must eventually satisfy one
evidence-backed status:

`reference` | `challenger` | `specialist` | `seed_source` | `baseline_only`
| `archive_candidate`

Decision rules:

- Keep as **challenger** when it has repeated wins or near-wins on at least
  one meaningful lane, the wins are not only smoke/ceiling ties, and it
  yields distinct failure-mode insight or transfer value.
- Move to **specialist** when strong on a modality or budget class but weak
  overall, and the specialization is stable across repeated runs.
- Move to **seed_source** when it improves another engine more reliably than
  it wins directly.
- **Merge shared pieces** when two engines duplicate benchmark, artifact,
  budget, or report logic that is not search-core identity. Do NOT merge
  search-core logic, scientifically meaningful differences, or anything that
  makes failure modes harder to understand.
- **Archive** when an engine cannot beat/tie contenders or improve another
  engine after its planned advancement branch, maintenance cost exceeds
  evidence value, or it duplicates another engine without measurable
  advantage. Archiving preserves artifacts and lessons.

Process requirements: every engine has a current portfolio status in
dashboard/docs; status changes require evidence links; the project does not
keep investing equally in every engine by default.

## Correct Use Of Engine-Only Vs Contender-Including Evidence

- **Engine-only** cohorts (contenders excluded) drive parity, convergence/
  specialization, and portfolio decisions.
- **Contender-including** cohorts drive external performance claims.
- Never claim broad EvoNN superiority from engine-only runs; never read
  portfolio balance from contender-dominated full-system tables alone.

## Runtime Telemetry As Mandatory Evidence

Any claim that an engine improved MUST report whether quality gains cost more
runtime than they are worth: wall-clock, evaluations/sec, seconds per
successful candidate, score-per-second, and family runtime allocation are
part of trend rows, dashboards, and registry reports. Quality bought blindly
with wall-clock is a tradeoff to be declared, not a win.
