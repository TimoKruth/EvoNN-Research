---
document_kind: project_history
status: current
authoritative: false
---

# EvoNN Project History

**Updated:** 2026-09-11. Foundation acceptance is merged through #28;
Phase 1 implementation and runtime evidence are recorded in #29/#30, with
required hosted checks attached to those revisions. Phase2 implementation and
its source-bound acceptance cohort are recorded in #31. Phase 3 is merged in
#32; Phase 4 implementation is bound by its compact runtime receipt.
This is the compact record of completed work, review decisions and verification.
Current capabilities and commands live in [README](README.md); outstanding work
and acceptance criteria live in [CONSOLIDATED_PLAN](CONSOLIDATED_PLAN.md).
Historical success is scoped to its recorded revision and evidence class.

## All-engine higher-budget results evaluated — 2026-09-11

All 80 runs and 15,360 fits completed on the original `e1d005a` producer; final
exports were verified at 23:18 CEST on September 10. One user pause and two
hostname-related preflight blocks caused no result replacement or fit failures.
The [result receipt](governance/all-engines-high-budget-results-20260911.json) binds the unchanged protocol, all input manifests,
the aggregate registry and descriptive scores. All 80 records validated and all
256 trained-winner replays passed. An independent calculation
reproduced all four bootstrap intervals, signed-rank tests (256 exhaustive sign
permutations each) and Holm adjustments.

Prism, Topograph and Primordia pass the predeclared aggregate quality criterion
against the required baseline floor at 256; Stratograph is materially below it.
All four Holm p-values are 0.03125. Per-task scores, full-pool baselines, runtime
and budget scaling remain descriptive. The final protected text split remains
unused and no automatic scientific/engine advancement is authorized. Detailed
scores are in README; next actions remain Stratograph proxy correction and a
separate frozen generalization comparison including all five systems.

## All-engine higher-budget comparison started — 2026-09-10

Following two hostname reversions during pause/resume, future campaign and export
identities now use a versioned hash of the OS machine ID. All four engines and
Contenders share this provider. Renames no longer invalidate a new campaign;
machine changes remain detectable. The status skill handles both schemes.
Historical manifests, exports and the original producer retain their original
hostname identity; no evidence is relabeled or mixed across revisions.

At the user's request, independent hourly oversight was added to the minute
guardian. A separate pinned LaunchAgent checks guardian availability, progress,
repair history and completion evidence, recording local status and issuing macOS
problem notifications. Its state is `.artifacts/all-engines-hourly-20260910`.
The combined guardian and health-check suite passes **27 tests**; the training
producer and frozen protocol are unchanged.

The user explicitly requested higher budgets for all four engines and Contenders.
The [frozen protocol](governance/all-engines-high-budget-20260910.json) declares
128/256 fits, eight fresh seeds 53–60 and all five systems in each case: **80 runs /
15,360 fits**. Four primary engine-vs-required-floor contrasts at 256 use a single
Holm family; other budgets, per-task results and scaling remain descriptive.
The protected text test is unused, and no normalization or other engine change
was introduced into Stratograph for this run. Existing runtime limits remain.

Execution started at **14:47 CEST** in the clean isolated producer
`../EvoNN-all-engines-20260910`, pinned to `e1d005a`. All sixteen manifests passed
preflight and all locked optional baseline libraries imported successfully.
Artifacts and sequential supervisor: `.artifacts/all-engines-high-budget-20260910`
inside that producer. Guardian state lives in this checkout at
`.artifacts/all-engines-guardian-20260910`. It uses the supplied frozen protocol,
supports the 80-run total, and checks the required five-system roster before
accepting any repaired replacement. Eighteen guardian tests and repository
governance/import checks passed. No completed comparison was modified or restarted.

## Eight-seed confirmation results — 2026-09-10

After reviewing this focused confirmation, the user required **all four engines
in every future comparison**. This is now recorded in AGENTS.md, README and the
execution plan, including focused confirmation/generalization comparisons.
Stratograph's omission from the completed run is historical; its results and
frozen protocol are preserved rather than retroactively expanded.

The [unchanged protocol](governance/tier-b-confirmation.json) and
[result receipt](governance/tier-b-confirmation-results-20260910.json) bind the
48-run / 4,608-fit confirmation on fresh seeds 45–52. The producer is the clean
`7da8e76` checkout; training finished at 13:21 CEST after 108m09s, with zero
failed fits, invalid proposals or repairs. The guardian verified completion at
13:22 CEST. All five contrasts reach L4 with no blockers. Thirty-two native runs
replay all **128 saved winners**. Independent extraction agrees with the formal
report, and exhaustive enumeration of 256 sign assignments reproduces all five
signed-rank p-values. No additional training was started for this analysis.

Positive quality effects favor the target. Intervals below are 95% paired-seed
percentile intervals for the symmetric relative effect, not raw score changes.
Holm correction covers all five declared quality comparisons.

| Frozen comparison | Mean effect | CI95 | Holm p | Criterion result |
| --- | ---: | ---: | ---: | --- |
| Prism LM vs tiny Transformer | +77.92% | +69.55% to +85.26% | 0.0391 | Pass |
| Prism LM vs required floor | +70.58% | +67.40% to +73.49% | 0.0391 | Pass |
| Topograph regression vs CatBoost | +4.60% | +1.38% to +8.31% | 0.2344 | Not confirmed |
| Topograph regression vs required floor | +1.07% | -3.17% to +5.61% | 1.0000 | Not confirmed |
| Primordia vs Prism tabular quality @64 | +1.04% | -2.83% to +4.60% | 1.0000 | Predeclared -3% tolerance met |

**Prism:** mean validation perplexity is **16.11**, versus **36.96** for the
frozen tiny Transformer and **33.65** for the required floor. Both margins and
corrected tests pass, and all eight paired seeds favor Prism. This confirms the
bounded validation-surface result, not general Transformer/architecture superiority.

**Topograph:** mean diabetes MSE is **2738.5**, versus **2870.3** for CatBoost
and **2769.6** for the required floor. Its numerical advantage does not satisfy
the complete predeclared significance/margin criteria. It is not a confirmed
regression winner; this is not proof that it is worse either. The best outcome
from the entire expanded contender pool averages MSE 2721.5.

**Primordia:** the separate paired full-pack runtime ratio averages **0.7148**
(CI95 **0.6839–0.7406**): **28.5% less runtime**, with an interval of
25.9–31.6% less, compared with Prism@64. Its mean run takes 31.38s versus 44.13s.
The quality lower bound (-2.831%) clears the -3% tolerance narrowly and the
runtime upper bound clears 0.75, so the **joint predeclared criterion passes**.
Nonsignificance is not used as proof of equivalence; the tolerance test is
explicit. Quality covers banknote/diabetes only. Image accuracy is 88.13% versus
97.12% for Prism@64, and LM perplexity is 28.73 versus 16.58; broader parity is
not supported.

The first report evaluated baseline admission per single-seed campaign and was
blocked. Rebuilding a canonical aggregate workspace let the unchanged admission
rule evaluate all existing low/mid-budget evidence jointly. The blocked report
is retained; no outcome, original campaign manifest or test rule was changed.

Artifacts, the separate 48-record aggregate registry and reproducible extraction scripts
are retained under `.artifacts/confirmation-analysis-20260910`. The receipt
records file hashes and original source paths. Discovery seeds were not pooled,
no missing baseline was substituted, and the protected text test remains unused.
Eight-seed uncertainty and validation selection still limit interpretation;
Phase-4/portfolio/transfer promotion is not automatically authorized.

## Confirmation start and unattended recovery — 2026-09-10

The user authorized the frozen 48-run / 4,608-fit confirmation and subsequently
automatic Codex diagnosis, repair, resume or necessary restart until completion.
Training started at 11:33 CEST in the clean producer `7da8e76`. Only the network
hostname had drifted since planning; sixteen fresh manifests preserve the exact
protocol and datasets, with the unused originals retained. Execution artifacts:
`../EvoNN-confirmation-v2-20260909/.artifacts/confirmation-execution-20260910`.

The repository-owned `automation/` guardian uses launchd minute polling, a
process-inherited lease, bounded repair sessions, local notifications, retry
backoff and a repeated-failure circuit breaker. It leaves the existing supervisor
in control while healthy. Repairs run in dedicated clones; a changed producer
requires a complete replacement cohort and cannot mix old results into it.
Runtime state/logs and pinned automation copies live in
`.artifacts/training-guardian-20260910`. A complete status requires source-bound
validation of every completed export. No original training code or evidence was
changed, and no fault was injected into the live comparison.

Validation: 16 guardian regression tests cover crash/recovery transitions,
final-validation rejection, provenance/path restrictions, retry/pause behavior,
actual child-process timeout and inherited locking, PID-reuse-safe termination,
and an executable CLI repair fixture. A real authenticated Codex invocation also
created a disposable marker through a workspace-write shell tool. Ruff and shell
syntax checks passed. These checks validate the mechanism, not a guarantee that
arbitrary scientific failures, credentials or physical outages can be repaired.

## Comparison follow-up and Stratograph diagnosis — 2026-09-09

The [follow-up receipt](governance/tier-b-comparison-20260909.json) records the
large-state fix, explicit within-cohort inference and bounded diagnostics.
`cohort-report` now evaluates actual engine/floor/budget arms, checks full source,
data, runtime and accounting bindings, and leaves historical registry/trend bytes
unchanged. New observations use `split-clock-v2`; legacy receipts retain their
old interpretation. All 24 declared contrasts reach **L4 evidence quality**,
with no blockers or automatic advancement. The host proof binds immutable
campaign manifests because native and Contenders used different JSON codecs
for the same host. Budget-response checks retain every independent dimension
while allowing the exact fit-derived training-total cap to scale.

A five-variant × three-seed Stratograph @64 ablation completed 960 successful
fits in 13m15s on the preserved original producer. Its shared controls reproduce
all twelve prior benchmark scores exactly. The image results are:

| Variant | Mean validation accuracy |
| --- | ---: |
| Shared | 25.09% |
| Flat | 57.96% |
| Unshared | 24.26% |
| No clone | 25.09% |
| No motif bias | 29.81% |

Flat also raises banknote accuracy from 72.85% to 97.82% and reduces mean
regression MSE from 3542.7 to 2866.7. The feature probe shows image feature
standard deviations shrinking from about 0.95 at the input to 0.0068–0.130
at the hierarchy output, with effective ranks around 5–7. Six fresh-head,
fixed-genome diagnostic fits isolate normalization: using training-only feature
statistics raises mean image accuracy from 23.98% to 44.63%, under identical
initialization/training streams and 12-epoch limits. This supports a scaling
limitation in the current deterministic-feature proxy, but normalization alone
still trails the flat variant and other engines. No Stratograph training or
replay default was silently changed; end-to-end hierarchy learning remains
unproven.

The [confirmation protocol](governance/tier-b-confirmation.json) fixes eight new
seeds 45–52, named neural/boosted floors, effect margins, the joint Primordia
quality/runtime criterion and balanced system order. Six pairs cannot clear
five-way Holm correction at their minimum exact two-sided p-value; eight can.
The campaign is **prepared and paused**, with 16 preflight-passed manifests,
48 planned runs / 4,608 fits, and no dispatch events. Discovery seeds stay
outside confirmation; the protected text test split remains untouched.

Preparing the expanded baseline pool exposed an inherited private sklearn
helper that XGBoost and LightGBM could not use without `_parameter_constraints`.
The correction skips only that unsupported inherited helper, retaining sklearn
constraints, recursive pipeline checks and explicit external validators. The
first failed qualification (60 charged fits, four pre-fit worker crashes) is
preserved. A fresh source-pinned qualification then completes all **64 fits in
203 seconds**, reaches L3 and passes the contract audit, with successful
XGBoost, LightGBM, CatBoost, CNN and Transformer results. The additional model
classes are not assumed to be empirically stronger on every task.

Validation: 115 Compare tests plus two additional multiplicity tests pass;
48 Contenders tests pass with optional dependencies installed. Profiling the
fully revalidated report took 920 seconds under cProfile: 29,076 catalog lookups
consume roughly 96% of cumulative time through repeated YAML parsing. This is
an identified validation bottleneck, not evidence of a measured optimization.
The next implementation should reuse definitions within one validation call
while continuing to detect changed catalog bytes on the next call.

## Tier-B comparison — 2026-09-09

The optimized campaign completed at **00:30 CEST on 2026-09-09**, after
77m36s: **30 runs, 2,880 fits, zero failed fits**. Source producer
`53a8c915ea97120bce062e1c872d7c836769047f` is preserved in its clean clone;
its runtime source digest matches merged #35. The fixed matrix was
`tier_b_core_v2` × budgets 64/128 × seeds 42/43/44 × four native engines plus
Contenders, with 12 maximum epochs, 1500-second runs and 90-second fit limits.
No fitting or tuning was performed during the subsequent analysis.
The [machine-readable analysis](governance/tier-b-comparison-20260909.json)
retains exact run IDs, source/export hashes, per-seed scores, floor identities,
effects, uncertainty, budget response and runtime costs.

**Verification:** all 30 L3 exports passed current artifact validation; 96 neural
benchmark winners reproduced through inference-only replay. The decision-grade
benchmark-admission audit passes with zero blockers and repeated low/mid
coverage. All required contender families are present; optional enhanced
pressure is absent on all four tasks. This admits the bounded benchmark
surface and does not establish scientific qualification or native transfer.

**Quality at 128 fits:** arithmetic means of the three best-per-run validation
scores. Accuracy is higher-is-better; MSE and perplexity are lower-is-better.
The Contenders row uses its best outcome across the whole configured pool;
external margins in the receipt separately use the **best required contender**
for each seed and budget. The two baselines can differ on diabetes.

| System | Banknote accuracy | Digits accuracy | Diabetes MSE | Shakespeare perplexity |
| --- | ---: | ---: | ---: | ---: |
| Stratograph | 73.70% | 25.09% | 3519.8 | 30.69 |
| Primordia | 99.88% | 88.52% | 2661.5 | 25.21 |
| Prism | 100.00% | 97.96% | 2686.9 | 16.32 |
| Topograph | 100.00% | 97.59% | 2590.5 | 30.13 |
| Contenders | 100.00% | 98.61% | 2698.5 | 33.68 |

**Interpretation and provisional research priorities:**

- **Prism:** strongest observed LM engine on every seed at both budgets.
  At 128, perplexity is 46–56% below the required NGram floor per seed. It is
  near the image floor but below it on all three seeds (0.28–0.83 percentage
  points); banknote ceiling ties provide no superiority evidence. Prioritize
  confirmation against a stronger neural LM baseline, not a broad-engine win.
- **Topograph:** lowest mean regression MSE at 128; beats the required floor
  on all three seeds by 1.17–8.13%. Different native engines lead individual
  regression seeds, so this is a specialization signal rather than a proven
  best-regressor claim. Its image/LM quality does not justify replacing Prism
  generally; its runtime remains substantially higher.
- **Primordia:** fastest engine at both budgets, with competitive tabular
  results and a clear image-quality tradeoff. At 128 its image accuracy is
  88.52% versus Prism's 97.96%. Retain it as an efficiency candidate; a
  seed-source role still requires downstream transfer evidence.
- **Stratograph:** weak banknote/image/regression results despite runtime
  comparable to Prism. Digits is exactly unchanged on every seed after budget
  doubling; LM changes only about 0.11%. Diagnose the hierarchy-feature /
  trained-head proxy before spending more fits. This does not refute
  end-to-end hierarchical learning or justify archiving the engine.

**Runtime:** medians of three complete run wall times on the same host.

| System | 64 fits | 128 fits | Fits/s at 128 |
| --- | ---: | ---: | ---: |
| Stratograph | 42.3 s | 86.1 s | 1.49 |
| Primordia | 26.9 s | 49.8 s | 2.57 |
| Prism | 39.9 s | 96.3 s | 1.33 |
| Topograph | 69.8 s | 165.6 s | 0.77 |
| Contenders | 92.2 s | 183.2 s | 0.70 |

The slowest Topograph run completed in 200.3 seconds, far below the unchanged
1500-second cap; these budgets need no timeout increase. Exported run spans
sum to 43.6 minutes, versus 77.6 minutes for the campaign. The remaining 34.0
minutes cover work outside those spans and need separate profiling. Recorded
fit training sums to 8.8 minutes; this is not end-to-end campaign time. Runtime
order was fixed and engine epoch policies differ, so equal fit budgets do not
mean equal compute and the observed ratios are not randomized speed trials.

**Budget response:** doubling fits reduces mean LM perplexity from 18.11→16.32
for Prism and 28.00→25.21 for Primordia, with improvement on all three seeds.
Topograph's mean diabetes MSE improves 2771.2→2590.5, but one seed is unchanged.
Stratograph gains little; its image scores are identical. Contenders' image,
LM and saturated banknote results are unchanged at both budgets. Additional
fits should therefore target specific hypotheses rather than repeat the whole
matrix uniformly.

**Uncertainty and decision:** effects use the existing direction-aware symmetric
relative formula and 4096 deterministic paired-seed bootstrap resamples. One
seed, not one candidate or benchmark row, is the independent unit; fixed-panel
means give each unsaturated benchmark equal weight. Ceiling-saturated tasks are
excluded per comparison. Different exclusions mean these panel effects must
not be ranked against one another. Per-seed values and 95% intervals remain
in the receipt. Three seed units satisfy local coverage but cannot provide the
six nonzero pairs required by the project's signed-rank test. No significant
`clear_gain`, formal portfolio status change, L4 promotion or L-SCI closure is
claimed. The descriptive overall decision is **inconclusive for broad
superiority**, with the task-specific signals above. Validation winners were
selected during search; the protected text test split remains unused. The LM
surface is only 1536 training and 384 validation windows of 16 bytes, and the
floor contains NGrams rather than a neural LM. Generalization to larger text,
other tasks or hosts is untested.

**Reporting defect found during analysis:** the optional clock extraction uses
a 16 MiB state reader, although validated native states may be up to 128 MiB.
All three Topograph128 exports exceed the smaller limit. The exception also
clears already computed protocol fingerprints, incorrectly isolating Topograph
and the external floor in old dashboard rankings. This analysis verifies exact
shared config/runtime policies and all 12 benchmark/seed data bindings directly
and computes a separate analytical view. Original exports, append-only trends
and registry records remain unchanged. Repair and test the reporting path before
claiming a formal within-cohort L4 result; the current L4 request interface only
models same-engine before/after revisions. The plan records the remaining work.

## Native runtime performance — 2026-09-08

The first larger campaign stopped at Topograph after 51 committed fits in its
1500-second allowance. The original source, successful slots, checkpoint and
52nd durable result remain untouched. Background launchd priority throttled
startup and journaling; the next campaign uses Standard priority.

Topograph now sends a serial job directly to the existing isolated fit process,
while multiple jobs retain their supervised pool. Historical process disclosures
remain readable. All four engines avoid eager data-preparation imports, retain
runner-owned search/cache state between fits and avoid redundant journal hashes.
Recovery still validates the predecessor and reconstructs Search after a pending
transaction. Campaign dispatch checks the full time reserve after preflight.

The [performance receipt](governance/performance-runtime-evidence.json) binds
13 native/Contenders qualification runs, 848 successful fits and 48 winner
replays. Native 64-fit timings are 39/27/45/70 seconds for Stratograph/Primordia/
Prism/Topograph; 128-fit timings are 92/49/94/158 seconds. Historical background
comparisons combine code and process-priority changes. Separate three-repetition
probes at equal priority measure about 6x faster native CLI imports. The first
cold Stratograph16 preparation remains slower than its earlier cohort; no
uniform cold-start improvement is claimed.

836 foundation tests, 46 targeted tests and 39 native recovery/integration tests
pass. A 160-step regression checks persistent versus restored search state;
prior 16-fit cohorts and available 64-fit prefixes retain exact architectures,
inheritance, metrics and updates. Two independent reviews found no unresolved
source or qualification blockers. Both hosted lanes gate integration. The
18-record registry's single-seed decision remains `needs more seeds`; no
scientific advancement is claimed. Existing limits remain, and the full
comparison was paused at that checkpoint; its later authorized completion and
analysis are recorded above.

## Bounded campaign control and incremental journals — 2026-09-08

Campaign planning freezes the matrix, clean source, host/environment, pools,
data and budgets; a separate preflight validates them without downloads or fits.
Durable dispatch records, inherited process locks and export validation allow
whole-campaign recovery without rerunning completed slots. Incomplete native
runs resume; incomplete Contenders runs stop for inspection. All four engines
now append attempt/state deltas with compact snapshots every 16 steps and keyed
weight-cache changes. A durable invocation clock prevents lost time after abrupt
termination; clean offline pauses remain free.

Independent reviews corrected budget/variant/pool adoption checks, surviving
worker ownership, canonical numeric delta semantics, bounded journal reads,
transaction hashes, cache eviction deltas and crash-time accounting. Permanent
negative tests retain those checks. The short Tier-B@16 campaign completed all
five systems: 80 fits, L3 exports and 16 replayed neural winners. Pause/resume
started 2, then 3, then 0 runs; the final pass changed no run or event bytes.
The [campaign receipt](governance/campaign-runtime-evidence.json) binds five
pre-change and five post-change exports, source identities and release assets.
Its decision remains `needs more seeds`, with no superiority claim.

831 foundation tests and 86 Compare tests pass. Existing real process-death,
reproduction and accounting cases retain their assertions; required Linux/macOS
checks gate integration. The 256-proposal/30-minute per-run limits remain.
Search traces and integrity hashing still grow with history; compact snapshots
alone do not qualify larger budgets. No multi-hour training was started.

## Phase 4 implementation and short qualification — 2026-09-08

Stratograph now has an independent hierarchical genome, reusable cell compiler,
crossover-first search, bounded niches/lineage, five matched ablations and
verified `motifs analyze`. Its declared fidelity is deterministic hierarchy
features with a trained GELU head; end-to-end hierarchy learning is unproven.
Primordia trains its own small primitive circuits, caps architecture/epochs and
emits strict ranked banks and transfer seeds. Its deterministic selection-cost
proxy is parameter count × optimizer updates; real time remains in the ledger.
Bank reconstruction rejects changes to export-bound source inputs.

The additive Tier-B pack combines OpenML banknote, digits, diabetes and pinned
real Shakespeare text. Raw text is split before context generation; the final
15% remains unused. All four engines train and replay next-token metrics.
Review fixes covered causal prefix inputs, Topograph's batch-dependent activation
quantization, truthful NGram backend/default-smoothing admission, and snapshot
rehydration with immutable analysis inputs and safe directory creation.

The [receipt](governance/phase4-runtime-evidence.json) records 13 L3 qualification
runs / 304 real fits and 80 replayed winners. Both new engines reached Tier A
and core@64; all five systems completed Tier-B@16. The contract audit has zero
blockers; repeated low/mid-budget evidence still blocks scientific admission.
The registry decision is `needs more seeds`, without a paired pre-change Tier-B
baseline or advancement claim. Original producers and consumer are recorded
separately; final Tier-B runs bind the complete reviewed runtime source.

Validation includes 810 foundation tests, 682 policy tests, 185 focused tests,
four unchanged strict process-death/reproduction tests for the new engines and
a real five-variant MLX CLI test (40 additional tiny fits, under three minutes).
Two independent reviewers checked engine numerics/search, artifact semantics and
transport. Raw models/caches and the registry snapshot are checksum-pinned release
assets; Git keeps one compact declaration and receipt. No multi-hour training
or larger repeated comparison campaign was started.

## 2026-09-08 — Phase 3 registry and statistical decisions (#32)

Append-only source-bound registry, paired independent-seed inference, conservative
PR decisions and versioned dependency transport implemented. The
[Phase 3 receipt](governance/phase3-runtime-evidence.json) records 384 short native
Prism evaluations across two unchanged producer revisions: three matched seeds,
L4, no material change. Initial host-fingerprint drift was correctly blocked;
reference measurements were repeated without rewriting old evidence. A fabricated
PR run ID, missing cache relocation and same-shape cache substitution were rejected.
Independent reviews covered registry integrity and statistics; CodeRabbit skipped
automatic review under its repository-star policy. Full source artifacts live in
the versioned release, with checksums and hosted revalidation; no large comparison
campaign was started.

## Phase 2 implementation and acceptance — 2026-09-07

Prism and Topograph now have separate genome/compiler/training/search modules.
Shared owns data preprocessing, cache and persistence infrastructure. The
Contenders dataset loader moved without changing canonical manifest or split
bytes; its original dataset tests moved with it. Current capability declarations
advance independently of immutable B0 bootstrap receipts. At that revision, the active bootstrap
probe used the then-unimplemented Stratograph declaration; real engine tests
now execute separately on Linux NumPy and macOS MLX.

Independent reviews caught and corrected normalization/replay, stable CE,
function-preserving morphology, historical archive retention, champion loss,
novelty/pooling failure handling, supervisor cleanup and export/accounting issues.
Numerical review exercised all families on both backends; 128 independent
morphism cases preserved logits within 4.92e-7. SIGKILL boundary tests cover
worker, transaction, row and checkpoint publication. A separate evolution test
covers reproduction and trained inheritance across resume.

The final cohort completed 13 runs / 896 real fits, each 100–280 seconds: all three
systems on core@64 seeds 42/43/44 and Tier-A@64 seed 42, plus Contenders core@128.
All 13 exports reach L3; core floor admission passes and 64 exported neural winners
replay with the recorded verification consumer. The [receipt](governance/phase2-runtime-evidence.json)
binds producer 1828b28 separately from consumer 7ece4af. Required Linux/macOS checks
on #31 govern the final merged revision; the runs do not establish superiority.

CodeRabbit and independent reviews also corrected invalid-candidate accounting,
malformed YAML/default-cache handling, causal-LM variation and RoPE dimensions,
and comparison groups across runtime/host/training policies. A terminal worker
result under the worker lock fences delayed children after a real supervisor
SIGKILL. Current focused tests pass 113 cases, Shared passes 804, and the native
resume suite passes 4 integration cases. Full snapshots remain deliberately
bounded to 256 proposals / 128 MiB; incremental cache accounting avoids repeatedly
serializing the entire 32 MiB cache. A larger per-run budget requires a separately
qualified append-only journal.

## Phase 1 runtime verification — 2026-09-07

Five real CPU Contenders runs completed 336 fits at unchanged execution commit
`998acfb7193904f8ffce7a9dae364c59af018d07`: core@64 at seeds 42/43/44,
core@128 at seed 42, smoke@16 at seed 42. Each took 41–213 seconds. Core audit
passes with zero blockers and L3 outputs; missing optional enhanced pressure
remains visible. Smoke cannot cover all 25 minimum floors. The
[compact receipt](governance/phase1-runtime-evidence.json) binds original export
hashes, code/tree, runtime presets and the derived audit; raw artifacts stay
local and immutable. These are contract-runtime results, not engine training
or scientific superiority.

Independent producer/consumer reviews found and closed accounting, provenance,
cache, cohort/admission and ingestion issues. CodeRabbit fixes include direct
dependencies, controlled errors, bounded reads, protocol-owned execution and
true held-out model fixtures. Linux confirmed exact consumed reference arrays
for both synthetic generators: platform-dependent discarded Float64
intermediates are diagnostic; consumed arrays still require exact hashes.
No frozen metadata, model strength or numeric tolerance was changed.
Final local verification: 790 foundation/contract tests, 41 Contenders tests,
18 initial Compare tests plus subsequent boundary checks; the final focused
Compare/cache suite passes 28 tests, and model/runner suite passes 38 tests.
Ruff, import boundaries and standalone governance/freeze
validation passed. Actual dashboard rendering and benchmark filtering also
passed; absent engines produce no fabricated wins or pairwise evidence.

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


## Stratograph breadth-preserving v2 — 2026-09-11

Implemented an explicit opt-in `research` policy, leaving absent-policy v1
execution and historical replay intact. V2 adds training-only normalization and
optional information paths, persistent projection/parameter identities, learned
clone equivalence, compatible inheritance without epoch discounts, trainable
shared cells, bidirectional macro edits, full-envelope width mutation, a primitive
registry, protected exploration and charged archive revisits. Representation and
selection controls support focused ablations without deleting experimental paths.
Compare campaigns accept `stratograph_research`, require the full engine roster
for that policy, and bind it into configuration checks and protocol fingerprints.

The isolated implementation check passed 39 package tests, including forced
SIGKILL/transaction recovery and replay after a 128-fit proxy and 32-fit native
trainable run. An earlier combined pass covered 42 package/legacy-process tests;
961 Shared/Compare tests passed. All four winners of the preserved September 10
Stratograph seed-53/budget-128 run replayed successfully. A subsequent ablation
forwarding test and 12 capability/dependency policy tests passed, as did scoped
Ruff, lock and whitespace checks. The current backend capability declaration now
includes opt-in trainable execution without a scientific evidence claim.

Local logs and source hashes are in
`.artifacts/stratograph-v2-validation-20260911/verification.json`. The snapshot
isolates execution from concurrent engine edits; the receipt does not assert a
clean global policy gate. Stratograph has zero remaining import-policy violations;
concurrent other-engine/shared changes still produced repository-wide findings at
verification time. These are implementation checks, not a new scientific
comparison. Repeated all-engine/Contenders qualification, fresh-seed confirmation
and any promotion remain open in CONSOLIDATED_PLAN.md.
