# 11 — Seeding Ladders And Transfer Proof

Transfer and seeding policy is a **first-class research topic**, not a
convenience feature. The central cumulative-search claim — discovered
structure from one system can improve another system under fair measurement —
must be proven or falsified at the native engine level, never assumed from
metadata.

## The Two Ladders

EvoNN implements **both** inheritance ladders explicitly and compares them;
neither is assumed correct in advance.

### Ladder A — Direct primitive seeding
`Primordia → Stratograph`, `Primordia → Topograph`, `Primordia → Prism`.
Tests whether low-level primitive priors are already rich enough to improve
all higher systems directly. Questions: do motifs help every abstraction
immediately? which packages benefit from direct low-level priors? does
direct seeding accelerate search enough to justify the coupling?

### Ladder B — Staged seeding
`Primordia → Stratograph → Topograph → Prism`.
Tests whether discoveries should be translated upward through each successive
abstraction. Questions: is hierarchy the right first consumer of primitive
motifs? does topology benefit more from hierarchical priors than raw
primitive priors? is Prism stronger inheriting already-structured
topology-level knowledge?

Stratograph explicitly holds two roles: direct consumer (Ladder A) and
intermediate translator (Ladder B). Topograph must keep the two seeding
stories separable — labeled source, preserved unseeded baseline, direct and
staged as comparable experimental regimes.

Umbrella policy: implement both ladders; label every run with its ladder;
keep non-seeded baselines; compare direct vs staged vs none under shared
packs and budgets; preserve package distinctness so gains are attributable.
If direct helps everything, that is evidence; if staged wins, that is
evidence; measure instead of settling rhetorically.

## Seed Artifact Contract

A seed artifact MUST contain:

- source engine and version
- source benchmark/pack/budget/seed
- source backend and hardware metadata
- candidate genotype or motif encoding
- descriptor vector
- quality score and metric direction
- novelty/diversity descriptor
- budget cost already spent
- contamination policy
- compatible target engines
- target ingestion instructions
- checksum

The schema lives in `evonn_shared` with strict target-engine compatibility
validation. Artifacts are gated (validated) before consumption.

## Target Engine Behavior

Every seed-consuming engine supports three modes:

- `unseeded` — normal run (mandatory control)
- `seeded` — initialize or bias search with the seed artifact
- `staged_seeded` — consume the seed after a warmup budget fraction

Seed consumption MUST demonstrably change initialization or search bias —
plumbing that ingests metadata without changing behavior is not transfer.

## Budget Accounting For Seeds

- `free_prior` — seed treated as external prior; target budget unchanged
- `charged_prior` — source budget included in the total comparison budget
- `reported_prior` — target budget unchanged; source cost displayed and
  excluded from direct budget-matched claims

Default for first research runs: `reported_prior`. A budget-matched transfer
gain may only be claimed once it also holds under `charged_prior`.

## Canonical First Path: `Primordia → Topograph`

Chosen because Primordia's role is cheap motif discovery, Topograph's is
structural search, the structural relationship is direct, and a failed result
is still informative (motifs not yet transferable in current form).
`Primordia → Prism` is second, after signal appears or Prism gains a native
seed-consumption path.

## Portable Vs Native Proof (Critical Distinction)

- **Portable proof**: Compare-orchestrated lanes (`seeded-compare`,
  `transfer-regimes`) that materialize seed artifacts, run the target in
  `none`/`direct`/`staged` regimes on identical pack/budget/seed, and write
  regime-vs-control verdicts. This validates *contracts and plumbing* on a
  host-portable boundary. It is explicitly marked portable-contract evidence.
- **Native proof**: the target engine's real (MLX) runtime consumes the seed
  and changes outcomes under repeated controlled runs. Only native proof can
  support a research transfer claim; the registry records which state each
  promoted artifact reached.

`transfer-regimes` behavior: resolve pack/budget into a workspace-local
compare pack; run Primordia once per seed to materialize direct seed
artifacts; gate artifacts; run Topograph in all three regimes on the same
pack/budget/seed; build a compare-owned staged artifact from the direct run
(so staged is auditable before native staged support exists); write per-seed
regime-vs-control reports + multi-seed aggregate; refresh trends/dashboard.
Regimes stay separate by construction; verdicts are written against the
no-seed control, never a collapsed "seeded" bucket.

## Validation Sequence

```
tier_b_core_v2 @ 96, 3 seeds          # first controlled lanes
tier_b_core_v2 @ 384, 2 seeds         # if local signal appears
tier_c_architecture_sensitive @ 128   # exploratory only
```

Same pack, budget, seed, backend class, and contender-floor context across
regimes. Move to Tier C only after Tier B shows a non-noisy signal.

## Interpretation Rules

- Every transfer result is classified: `gain`, `regression`, `no_gain`, or
  `inconclusive`.
- Seeded and unseeded results stay separate in trends and dashboards —
  transfer claims never fold into normal leaderboard totals.
- Seed provenance is visible in manifests, summaries, trend rows, and
  dashboard (full ch. 03 seeding field set).
- If transfer fails, the artifact explains whether failure came from seed
  quality, target ingestion, benchmark mismatch, or budget accounting.
- Missing ladder metadata ⇒ the run is **transfer-opaque** and excluded from
  clean comparison.
- No transfer success claim until provenance, budget truth, and repeated
  evidence all show in the registry surfaces.

## Acceptance Criteria

- Seeded and unseeded runs reproducible from one command each.
- Target engine demonstrably consumes seed artifacts (native path).
- Result classified with repeated evidence; classification informs whether
  the next investment goes to seed-source quality, target-engine
  consumption, contender pressure, budget-scaling, or performance work.

## Ancestral Precedent (Why This Can Work)

The Symbiosis S3 gate (ch. 16) proved cross-system mechanism transfer once:
multi-fidelity training + residual mutations imported from Track A into
Track B produced a 65% median improvement on `friedman1_regression`,
measured in isolation, surviving both parent baselines, with clean
attribution. That protocol — isolate one mechanism, A/B at matched budget,
require ≥5% relative improvement surviving both baselines, demand clear
attribution — is the template every native transfer proof follows.
