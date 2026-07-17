# 17 — Roadmap, Horizons, And Build Phases

EvoNN grows in ordered horizons, not by sprawl. This chapter merges the
vision horizons, the execution horizons of the consolidated plan, and the
hard-remainder workstreams into one buildable roadmap for the greenfield
implementation.

## Strategic Horizons

### Horizon 1 — Trustworthy umbrella
Make the comparative substrate trustworthy on local hardware: shared
benchmark ladder; normalized budget contracts; common telemetry/reporting;
workspace coherence; documented roles and boundaries; a repeatable
automation loop (pull latest, run bounded smoke tests after each small
improvement, record whether tiny-budget runs improve or regress over time);
a Linux-capable execution path for compare-grade validation.

### Horizon 2 — Primitive-first search
Add the bottom-up layer: primitive/microcircuit evolution; cheap motif
discovery packs (Tier A/B); motif export formats that can seed later
systems; explicit boundary between low-level discovery and higher-level
search.

### Horizon 3 — Transfer and cumulative search
Stop starting from near-zero: motif memory; archive reuse;
benchmark-family priors; transfer-aware seeding across systems; explicit
direct-vs-staged ladder comparison; run labeling so transfer policy stays
auditable in Compare.

### Horizon 3.5 — Portable compare execution
Serious compare-style validation on Linux as well as Apple hardware:
backend/runtime separation; Linux smoke/regression/small-budget compare
runs; explicit runtime metadata; portability defined as comparable evidence,
not bitwise-identical floats.

### Horizon 4 — Harder benchmark classes
Stronger multi-domain packs; harder sequence and code-like tasks;
system-level evaluation surfaces; eventually frontier-style tasks under
reduced or staged budgets (Tier E admission machinery, ch. 02).

## Execution Horizons (Standing Operating Goals)

1. **Keep the evidence loop boring** — recurring compare runs routine,
   interpretable, cheap; benchmark audits green for decision packs;
   contender-floor reports present; last 10–20 full runs visible from the
   dashboard; important runs stored durably, not only in `.tmp`.
2. **Budget truth and output parity** — all engines at L3 on Tier A and the
   trusted lane; wall-clock/backend/device/eval-per-sec/cache/failure
   metadata in trend rows; downgrade reasons visible; no silent
   undercounting.
3. **Benchmark ladder and contender floor** — expand diversity only where
   honest comparison is possible; Tier C exploratory until its promotion
   gates (two clean 512 runs, one clean 1024); Tier D broad and separate;
   stronger floors only when reproducible.
4. **Engine advancement** — improve each engine without duplicating
   substrate or erasing identity (per-engine priorities in ch. 07–10).
5. **Native transfer/seeding proof** — the ch. 11 protocol end-to-end.
6. **Performance optimization** — only after measurement is stable:
   baseline → one change per branch → identical remeasure → accept / scrap /
   inconclusive, with before/after artifacts in every optimization PR.

## Build Phases For The Greenfield Implementation

### Phase 0 — Workspace and contracts
uv workspace; `evonn_shared` (contract models, budget/telemetry/seeding
models, run identity, JSON writers, LM cache validation);
`shared-benchmarks` skeleton with Tier A + tier1_core benchmarks and audit
metadata; CI scripts and both CI lanes.
Exit: contracts import everywhere; Tier A packs audit green; the
**Foundation Integrity Gate** passes — tests for named RNG stream
derivation, uninterrupted-vs-resumed equivalence, atomic checksummed
checkpoint publication, immutable canonical evaluation records, pure
read-only export, and honest measurement-vs-proxy labeling. No trusted
evidence claim may precede this gate; wherever NEAT terminology is used
later, genuine speciation behavior is part of the same integrity bar.

### Phase 1 — Contenders + Compare core
Contender zoo (required floors) with exports; Compare `fair-matrix`,
`compare`, `workspace-report`, `benchmark-audit`, trend artifacts, lane
acceptance, static dashboard; smoke + local presets.
Exit: contenders-only fair-matrix at `tier1_core@64` produces
`contract-fair` artifacts and a dashboard.

### Phase 2 — First two engines
Prism (full ch. 07) and Topograph (full ch. 08 minus QD extras); both L3 at
Tier A and `tier1_core@64`; `output-quality` command classifying L-levels.
Exit: four-way (2 engines + contenders + parity checks) `trusted-core` runs
with repeated seeds.

### Phase 3 — Evidence registry and L4 statistics
`evidence promote/report/validate`; registry rows per ch. 12; repeated-seed
groups, decision labels, minimum-seed gates; dashboard last-N backed by the
registry; research decision gate documented and enforced in PR flow.
Exit: a before/after engine PR is judged from registry-backed evidence.

### Phase 4 — Stratograph + Primordia
Stratograph (ch. 09: hierarchy genome, compiler, proxy evaluator, ablation
harness, motif mining); Primordia (ch. 10: primitive lane, banks, seed
export); both participating in fair-matrix at L3; Tier B packs and presets.
Exit: five-system Tier B `trusted-extended` cohort with 3 seeds.

### Phase 5 — Transfer proof
Seed artifact schema; Primordia export; Topograph native consumption
(`unseeded`/`seeded`/`staged_seeded`); `seeded-compare` and
`transfer-regimes`; the ch. 11 validation sequence; classification of the
result.
Exit: one auditable native transfer outcome (gain / regression / no_gain /
inconclusive) in the registry.

### Phase 6 — QD, portfolio, and hardening
Descriptor schema; Topograph descriptor exports + archive report; one QD
experiment vs baseline at equal budget; Stratograph LM-flatline diagnostic +
ablations; first evidence-backed portfolio status for every engine; Tier C
hardening runs; Tier D lanes; Tier E candidate audit file (admission only).
Exit: engine roles are evidence-backed, not aspirational.

### Phase 7 — Performance frontier and Observatory
`performance-baseline` workflow in routine use; one optimization branch at a
time; Observatory web UI over registry + workspaces; automation loop
(tiny-budget trend detection) running on a schedule.
Exit: repeatable performance-improvement process; explorable evidence UI.

## Standing Decision Flow After Each Evidence Cohort

Use the newest promoted evidence to choose the next emphasis among:
seed-source quality; target-engine seed consumption; contender pressure;
budget-scaling/search efficiency; performance optimization. Rules of thumb
from the parent project's evidence: engine-only Tier C cohorts are the
default parity loop after search changes; contender-including cohorts are
for floor claims; do not broaden benchmarks while the floor gap dominates;
repeat any promising signal across ≥2–3 seeds before steering architecture
decisions; treat mixed slices as `inconclusive/mixed` and keep the promoted
evidence for audit.

## Definition Of Done (Program-Level)

- Evidence registry makes promoted runs durable and auditable.
- Repeated-run statistical summaries are required for advancement claims.
- At least one transfer/seeding path has a valid outcome classification.
- Tier C is promoted with repeated evidence or explicitly exploratory with
  known blockers.
- Tier D stays broad-lane separated unless repeated evidence supports more.
- Tier E candidates exist with admission reports and no trust shortcuts.
- Every engine has an evidence-backed portfolio status.
- Performance work follows baseline/change/remeasure/accept-or-scrap.
- At least one engine beats or ties the required contender floor on a
  meaningful non-smoke subset under repeated evidence — or the program
  honestly reports that it does not, and why that is still knowledge.
