# 03 — Budget Contract And Accounting

A run is only fairly comparable when its resource envelope is explicit. This
chapter defines the minimum budget vocabulary (the contract) and how exported
runs count work (the accounting policy). The goal is not to force identical
internals across systems — it is to make resource claims legible enough to
audit.

> If a run cannot say what it was allowed to spend, it must not be used for a
> strong comparative claim.

## Required Budget Fields (The Contract)

Every comparable run MUST declare:

1. **Evaluation budget** — candidate evaluations allowed. Report total and
   any staged breakdown (e.g. promotion-stage evaluations).
2. **Wall-clock budget** — target elapsed-time budget and actual runtime.
3. **Training-step / optimization budget** — learning work per candidate in
   the system's natural unit (epochs, optimizer steps, tokens, batches,
   proxy-fit iterations) — explicit, whatever the unit.
4. **Hardware envelope** — device class, CPU count used, accelerator type,
   memory ceiling target if enforced, worker count. Especially important for
   Apple Silicon local-first work.
5. **Model/artifact-size budget** — parameter cap, byte cap, memory
   footprint target, latency band; declared caps and measured outcomes.
6. **Benchmark-surface budget** — pack ID, benchmark count, ladder tier, any
   reductions/subsets/filtered views.
7. **Fidelity regime** — how cheap vs expensive evaluation is staged
   (proxy-only; staged proxy→medium→full; reduced-then-full dataset; cheap
   motif score then promoted task score). Promotion rules MUST be explicit.

Human-readable **run classes** (`smoke`, `local`, `overnight`, `weekend`,
`special-study`) wrap real numbers; they never replace them.

## Accounting Semantics (The Policy)

Every compare-visible export distinguishes **declared comparable budget**,
**actual counted work**, and **non-comparable or separately tracked work**,
via these fields:

| Field | Meaning | Rules |
|---|---|---|
| `evaluation_count` | declared comparable budget envelope | what Compare checks against pack/lane policy |
| `actual_evaluations` | evaluation attempts charged to this run | failures that consumed budget still count; may be lower than declared for partial runs |
| `cached_evaluations` | results satisfied from cache/prior persisted state | must never masquerade as fresh spend; flag if fairness-material |
| `failed_evaluations` | attempts that consumed budget and failed | failures are not free; keep visible |
| `invalid_evaluations` | candidates rejected before full evaluation | always reported; whether they count toward fair budget is package policy, but never hidden |
| `resumed_from_run_id`, `resumed_evaluations` | continuation provenance | inherited counted work stays auditable |
| `partial_run` | stopped before declared budget completed | partial runs must not look complete |
| `evaluation_semantics` | one-sentence statement of what one counted evaluation means | e.g. "one evolved candidate trained/evaluated on the requested benchmark surface"; "one contender fit/eval pass per contender in the fixed pool" |

Compare behavior: warn when accounting fields are missing; distinguish
declared budget from actual counted work; keep resumed/cached/partial runs
explainable in trend artifacts; refuse to call a comparison fair when
accounting semantics are missing or mismatched.

## Required Reporting Fields

Every comparison-intended export MUST expose or derivably imply: system name,
run ID, pack ID, benchmark tier, total evaluations (staged breakdown if
applicable), wall time, worker count, declared hardware class, declared
budget caps, actual/cached/failed/invalid evaluation counts, resumed-run
provenance, partial-run status, the `evaluation_semantics` statement,
measured artifacts (params, bytes, latency, memory) when supported, and the
seeding regime + provenance (below).

## Rules For Fair Comparison

A comparison is fair only when:

- pack identity matches
- benchmark reduction policy matches
- budget vocabulary is reported on all sides
- contender vs evolutionary evaluation-semantics differences are disclosed
- staged fidelity differences are disclosed, not hidden

Contender budget note: for Contenders, "budget" means contender evaluations
(fit/eval passes), not evolutionary candidate evaluations. This difference is
legitimate but MUST be disclosed via `evaluation_semantics`.

## Rules For Transfer-Aware Runs

If a run consumes prior motif banks, archives, or seed lineages it MUST
report: which prior artifact was used; whether the prior was learned on
overlapping benchmark families; whether the run is a fair comparison, a
transfer study, or an internal acceleration experiment; whether the path is
`direct` or `staged`; the immediate upstream system and run ID; the target
family the seed was selected for; and the ranked seed choice actually
consumed. Hidden prior knowledge masquerading as fresh search is the failure
mode this exists to prevent.

Required seeding metadata fields (null/unknown rather than silently omitted):

```
seeding_enabled
seeding_ladder            # none | direct | staged
seed_source_system        # primordia | stratograph | topograph | prism | null
seed_source_run_id
seed_artifact_path
seed_target_family
seed_selected_family
seed_rank
seed_overlap_policy       # benchmark-disjoint | benchmark-overlapping | family-overlapping | unknown
```

Seed-cost accounting modes (ch. 11 details): `free_prior`, `charged_prior`,
`reported_prior`. Budget-matched transfer gains may only be claimed under
`charged_prior`.

## Budget ↔ Lane Reference Table

| Lane | Pack | Budgets |
|---|---|---|
| Tier A contract | `tier_a_contract` | 16, 64 |
| Trusted daily | `tier1_core` | 64, 256, 1000 |
| Tier B compact | `tier_b_core` | 64, 256, 1000 |
| Tier B expanded | `tier_b_core_v2` | 96, 384, 768, 1536 (cumulative: 98/392/784/1568) |
| Tier C | `tier_c_architecture_sensitive` | 128, 512, 1024, 2048 (cumulative: 132/528/1056/2112; mid-budget study points 154/264/374/484) |
| Tier D | `tier_d_broad_shared` | 200, 400, 800, 1600 (cumulative: 216/432/864/1728) |
