# EvoNN Research Lab

Research workspace for four independent evolutionary neural-search engines,
portable contender baselines and a file-based comparison/evidence layer.
This repository is the foundation rebuild; its predecessor is
`TimoKruth/EvoNN` (locally `../Evo Neural Nets`).

## Read these three documents

| Document | Purpose |
| --- | --- |
| **[README.md](README.md)** | What works, package boundaries, installation, verification and operating constraints. |
| **[CONSOLIDATED_PLAN.md](CONSOLIDATED_PLAN.md)** | The sole execution plan: priorities, dependencies, work packages and acceptance criteria. |
| **[PROJECT_HISTORY.md](PROJECT_HISTORY.md)** | Completed work, durable decisions, review outcomes and exact evidence references. |

Update these files in place. Historical specifications and proof records are
reference material; their role and locations are indexed in project history.
Package READMEs are short navigation links, not separate status reports or plans.

## Current capabilities

**Verified baseline: 2026-09-08.** Gate B0 and Phase 0 contract acceptance are
closed. The [acceptance receipt](governance/phase0-acceptance.json) binds the
canonical catalog authorization and successful Linux/macOS CI evidence.
Exact integrations and review decisions are recorded in project history.

| Component | Implemented | Remaining |
| --- | --- | --- |
| Shared | Canonical identities/RNG, strict budgets/telemetry/three-file exports, catalog/pack loaders, checkpoints, LM-cache validation, transactional DuckDB/workspace and verified read-only access | Producer interoperability and future contract extensions |
| Shared benchmarks | Eight frozen definitions plus two additive runtime definitions, four packs, verified tabular/image/real-text caches | Repeated Tier-B scientific qualification and optional enhanced pressure |
| Reference fixtures | Real kill/resume, failed/invalid accounting, seed/label binding, read-only diagnostics and hosted integrity reports | Broader scientific qualification and future producer interoperability |
| Contenders + Compare | Fixed CPU pools, bounded isolated fits, complete verified exports, case/budget audit, append-only trends, L0–L3 quality, append-only evidence registry, paired-seed L4 analysis and evidence dashboard | Scientific acceptance, targeted confirmation and native transfer |
| Prism + Topograph | Package-local MLX/NumPy models including real next-token LM, bounded search, inheritance, atomic resume, portable exports and Compare ingestion | Targeted confirmation, stronger baselines and native transfer evidence |
| Stratograph | Legacy proxy plus opt-in v2 normalized proxy/trainable shared cells, protected exploration, charged revisits, resume/replay | Repeated v2 scientific qualification and transfer evidence |
| Primordia | Trained circuits, versioned exploration/retention and training policy, extensible v2 graph/temporal genomes, verified motif/seed bank | Scientific qualification of breadth_v2, native cross-engine ingestion and proven transfer gains |

The [Phase 4 receipt](governance/phase4-runtime-evidence.json) records **13 short
qualification runs / 304 real fits**: both new engines on Tier A/core@64, five
Stratograph variants and all five systems on Tier-B@16. All exports are L3;
80 trained winners replay. Tier-B contract audit passes with zero blockers.
That short qualification remains single-seed evidence. The completed comparison
below supplies repeated low/mid-budget observations; neither receipt establishes
a broad superiority or transfer claim.
Historical Stratograph evidence uses deterministic hierarchy features with a trained head.
The [opt-in v2 research implementation](EvoNN-Stratograph/README.md#explicit-version-2-research-execution)
adds normalized/local projections, breadth-preserving search, charged archive
revisits and a separately labeled trainable shared hierarchy. Scientific
qualification of v2 is pending; legacy defaults and historical evidence remain.
[Phase 1](governance/phase1-runtime-evidence.json),
[Phase 2](governance/phase2-runtime-evidence.json) and
[Phase 3](governance/phase3-runtime-evidence.json) retain their scoped evidence.

All four engine runtimes accept at most **256 proposals**. Prism permits up to
12 hours per run and 30 minutes per fit as explicit safety allowances.
Each committed checkpoint appends one attempt and a state delta; every 16 steps
it includes a compact search-state snapshot. Weight-cache changes are keyed, so
LRU reordering does not rewrite all weights. The **128 MiB** publication guard
and **32 MiB** cache remain. Search traces and integrity hashing can still grow
with history. The [performance receipt](governance/performance-runtime-evidence.json)
qualifies native Tier-B budgets 64/128 on seed 42: 13 short runs, 848 fits,
48 replayed neural winners and zero failed fits. The 128-fit runs take 49–158
seconds on the recorded host. Limits are unchanged.

The [completed Tier-B comparison](governance/tier-b-comparison-20260909.json)
covers **30 runs / 2,880 successful fits**, budgets 64/128 and seeds 42/43/44,
in 78 minutes. Its decision-grade benchmark-admission audit passes with zero
blockers; all exports are L3. [Results and scope](PROJECT_HISTORY.md#tier-b-comparison--2026-09-09)
show Prism leading language modeling, Primordia offering the lowest runtime,
Topograph showing a regression signal and Stratograph needing a proxy diagnostic.
The explicit follow-up now gives all 24 declared contrasts L4 evidence quality.
These remain validation-set observations from three seeds, with no automatic
engine promotion or transfer proof. The original failed producer remains preserved.

The [eight-seed confirmation](governance/tier-b-confirmation-results-20260910.json)
finished on **2026-09-10**: **48 runs / 4,608 successful fits**, no failures or
repairs. The protocol file remains an immutable pre-execution snapshot; the
result receipt records current completion. All five frozen contrasts reach L4;
128 saved native winners replay.
**Prism's bounded LM advantage is confirmed** against the tiny Transformer and
required floor (mean perplexity 16.11 versus 36.96 / 33.65; Holm p=0.0391).
**Topograph's regression advantage is not confirmed** (CatBoost comparison Holm
p=0.2344; required-floor p=1.0). **Primordia's joint tabular-quality/runtime
criterion passes narrowly**: its quality interval stays above the -3% tolerance,
and paired full-pack runtime is 28.5% lower than Prism@64 (95% interval
25.9–31.6% lower). This does not establish image/LM parity or protected-test
performance. [Next actions](CONSOLIDATED_PLAN.md#immediate-next-actions) retain
the Stratograph proxy work and scoped generalization validation.

New Primordia runs now default to the experimental `breadth_v2` policy:
independent founders, recurring exploration/revival slots, full training envelopes
without inheritance discounts, and configurable graph size across modalities.
The [Primordia README](EvoNN-Primordia/README.md) documents its v2 genome and
`legacy_v1` control. All completed measurements below retain their frozen legacy
producer; the new policy has no demonstrated quality/runtime gain yet.

Primordia's owned loader supports the experimental language breadth pack,
including pinned Aesop byte ranges and seeded delayed-copy examples. It applies
the same source checksums, train/validation splits and cache verification as the
shared loader. This is dataset-runtime support, not scientific qualification;
historical failed breadth runs and their frozen producer remain unchanged.

The guardian for that completed confirmation is in terminal `complete` state.
The [all-engine comparison](governance/all-engines-high-budget-20260910.json)
completed on **2026-09-10**, with final exports verified at **23:18 CEST** and
analysis completed on September 11: all **80 runs / 15,360 fits**, no failed fits,
Prism, Topograph, Stratograph, Primordia and Contenders at **128/256 fits** on
seeds **53–60**. The original clean producer `../EvoNN-all-engines-20260910`
remains pinned to `e1d005a`; hostname interruptions did not replace any results.

The [result receipt](governance/all-engines-high-budget-results-20260911.json) records all four predeclared contrasts against
the required contender floor at 256: **Prism, Topograph and Primordia pass the
aggregate gain criterion; Stratograph is materially below the floor**. Each
Holm-adjusted p-value is **0.03125**. Symmetric aggregate effects and CI95:
Prism **+28.88% [28.07, 29.66]**, Topograph **+8.04% [6.32, 9.98]**,
Primordia **+5.05% [3.29, 6.85]**, Stratograph **-31.81% [-35.82, -27.73]**.
These are not accuracy-point improvements. Banknote is excluded from Prism and
Topograph averages because both arms reach its ceiling on every seed; other
panels retain four tasks. No per-task or engine-to-engine significance is claimed.

Descriptive validation means at **256 total fits** (eight seeds):

| System | Banknote accuracy | Digits accuracy | Diabetes MSE ↓ | Text perplexity ↓ | Mean run seconds |
|---|---:|---:|---:|---:|---:|
| Prism | 100.00% | 98.47% | 2712.2 | 14.96 | 265.6 |
| Topograph | 100.00% | 97.88% | 2847.6 | 27.74 | 524.0 |
| Stratograph | 78.36% | 33.99% | 3484.3 | 30.42 | 192.3 |
| Primordia | 99.32% | 92.88% | 3035.8 | 25.45 | 115.7 |
| Contenders: best full-pool outcome | 100.00% | 98.96% | 2892.7 | 33.67 | 597.0 |

The full-pool row differs from the primary required-floor reference. At 256,
that floor averages 100% banknote, 98.75% digits, 3002.3 MSE and 33.67 perplexity.
Doubling Prism's budget improves perplexity from 16.03 to 14.96 and MSE from
2850.3 to 2712.2; its observed paired runtime ratio is 2.48. Stratograph digits
improve from 29.76% to 33.99%, leaving a large deficit in the frozen shared proxy.
All budget scaling and timings are descriptive, with changing host load and
backend differences retained as limitations. All **256 trained-winner replays**
from 64 native runs passed. The protected text test remains unused; no automatic
engine, portfolio or Phase-4 promotion follows. Guardian state is `complete` at
`.artifacts/all-engines-guardian-20260910/status.json`.

For a fast read-only snapshot, use the project skill
[read-evonn-status](.agents/skills/read-evonn-status/SKILL.md), or run
`.venv/bin/python .agents/skills/read-evonn-status/scripts/status.py --project .`.
It discovers the current guardian, follows replacement targets, and reports
journaled progress, active engines, hostname drift and monitoring health without
loading models or revalidating exports.

New runs identify the machine with a versioned SHA-256 token derived from the
OS-provided machine ID (`IOPlatformUUID` on macOS, machine-id on Linux, MachineGuid
on Windows), plus OS and architecture fields. Campaign checks and all five
systems' exports use this identity; DHCP, network changes and hostname renames
do not change it. Missing machine IDs fail explicitly rather than falling back
to a hostname. Raw identifiers are not stored. Historical producers and their
frozen hostname-based identities remain unchanged, including the completed
September 10 comparison. Re-executing its original preflight still requires its
frozen hostname; new comparisons no longer require that hostname setting.

An independent LaunchAgent checks this guardian and its current training target
every hour, including failures repaired between checks. It sends macOS
notifications only for problems and records results in
`.artifacts/all-engines-hourly-20260910/status.json` and `history.jsonl`.
It checks scheduler availability, stale status, stalled progress and the final
completion receipt; bounded repair and validation periods are allowed.
Install for another guardian with `automation/install-training-healthcheck.py
--guardian-root <guardian-state> --state-root <new-hourly-state>
--install-scheduler`. Both monitors use pinned runtime copies and load at login;
hourly checks require the Mac awake and the user session active. Notification
visibility depends on macOS notification settings; these are local alerts, not
messages in this chat. The hourly checker does not launch or modify training.

For an active campaign the guardian checks the dedicated supervisor every 60
seconds; interruption triggers bounded Codex repair in an isolated clone.
Verified unchanged runs resume through the campaign journal. Producer changes
or unresumable attempts require a fresh full comparison, retaining superseded
evidence. Frozen seeds, budgets, baselines, data and admission gates remain
binding; completion requires validated exports, not just process exit.

The reusable entry point is `automation/install-training-guardian.py` with
`--producer`, `--base`, `--state-root` and `--protocol`, first `--dry-run`, then
`--install-scheduler`. Runtime snapshots, repair decisions and logs are stored in
the supplied state directory. For the completed all-engine campaign it is
`.artifacts/all-engines-guardian-20260910`: inspect `status.json`, `control.json` and
`history.jsonl`; `repairs/` contains individual Codex transcripts and fixes.
Create a `PAUSE` file there to prevent new dispatches/repairs (an active bounded
run finishes). Remove it to continue. Three failed repairs for the same error,
or twelve total attempts, open a circuit breaker and issue a local notification;
credentials/physical intervention cannot be repaired automatically. After fixing
the cause, under `guardian.lock`, change `control.json` mode to `repair`, clear
`failure_counts`, set `repairs` and `next_attempt_at` to zero, and remove `PAUSE`.
Do not edit runtime control while a repair or training invocation is active.
The LaunchAgent loads at user login and needs this Mac awake, Codex authenticated
and network available. No email, remote messages or automatic GitHub changes.

Run a verified short preset and rebuild its dashboard:

```sh
uv run evonn-compare fair-matrix --workspace .artifacts/compare --preset local \
  --systems prism topograph stratograph primordia contenders
uv run evonn-compare workspace-report .artifacts/compare
```

`--preset smoke` uses 16 fits; `local` uses 64. Runs accumulate. Each system
run stays below 30 minutes; no overnight/weekend preset is admitted.

Checkpoint recovery reuses canonical JSON bytes for unchanged private state
within each replay, while retaining every artifact and logical-state hash check.
The format and publication boundaries are unchanged. The
[checkpoint replay benchmark](reports/checkpoint-json-20260916/report.md)
records byte compatibility, resume tests and measured performance on a retained
256-attempt checkpoint.

## Prism exploration policies

The September 11 Prism implementation adds an experimental `open` policy for
new runs. It preserves every previous family and its historical genome identity.
This is implementation progress; the completed comparison above continues to
refer to its frozen producer, and no new superiority claim follows.

| `--variant` | Search and training behavior |
| --- | --- |
| `legacy` | Previous family roster, mutation choices, tournament reproduction and epoch discounts |
| `archive` | Adds rotating family opportunities, three-step protected lineages, family/descriptor archive parents, random retention and fresh starts |
| `training` | Adds transfer-coverage allocation, full allowances for protected candidates and still-improving sources, and the starting checkpoint as a selection candidate |
| `broad` | Adds wider and reversible mutations, attention-configuration crossover and mixed block composition |
| `open` | Combines archive, training and broader proposal policies; default for new Prism runs |

Protected lineages retain development opportunities even when their scores are
weak. Archive storage is bounded and evictions never create blacklists. The
mixed genome supports dense, sparse, gated, convolutional, recurrent, attention
and state-space blocks, plus acyclic skip edges. Text convolution is causal;
spatial convolution requires image input. The constructor boundary is documented
in `prism/composition.py`; new operators require shape, gradient and causality
qualification. Current parameter, depth, cache, fit-count and time limits remain
operational bounds, not conclusions about excluded larger models.

`--inheritance-policy disabled` provides a fresh-initialization search control.
Because changed scores can change later proposals, this control alone is **not**
a matched-finalist architecture comparison. `finalist-config` emits a complete
run configuration with the exported winners frozen per benchmark:

```sh
uv run evonn-prism finalist-config <symbiosis-export> > finalist-config.json
```

This command performs no fits. Its `fixed_genomes` mode keeps candidates constant
despite subsequent scores and grants the full declared epoch allowance to both
warm and cold controls. Use the same generated configuration, changing only
`inheritance_policy` to compare them in complete all-engine campaigns. Warm
weights accumulate within the new run; weights from the source export are not
imported. Discovery cost is separately disclosed as `reported_prior`, including
source run/manifest identity and a digest binding the finalist genomes. All new
fits are charged. Per-fit allowances and initialization streams match; cumulative
ancestral training differs and is reported. This diagnostic does not establish
a charged-prior search or transfer gain.

`--optimizer-policy continue` optionally restores Adam moments and the bias
correction step only for exact, weight-bound snapshots. Each fit still uses its
declared schedule and batch stream; this is not uninterrupted-training replay.
Partial transfers reset optimizer state. Optimizer snapshots share the existing
32 MiB cache bound. `--optimizer-backend native` keeps optimizer arrays on MLX
when using that backend; the default remains `numpy`. A small MLX-CPU probe found
the native optimizer slower on a tiny model, so no general speedup is claimed.

Attempts record proposal origin and parents, changed fields, cumulative ancestral
optimizer work, per-epoch losses, selected epoch, allocation reason and phase
timings. Architecture counts exclude optimizer genes and unused settings;
behavior descriptors supplement them. Repeated genomes are reported separately
from new proposals. To inspect an existing export without training:

```sh
uv run evonn-prism research-report <run-directory-or-symbiosis-export>
```

`EvoNN-Prism/configs/open_research.yaml` is an explicit bounded run configuration.
Campaign specifications can freeze a `prism_research` object with `variant`,
`inheritance_policy`, `optimizer_policy`, `optimizer_backend`, and optional
`fixed_genomes`/`prior_discovery`; campaign
adoption rejects mismatched policies and the comparison fingerprint separates
these controls. An explicit Prism research campaign requires all four engines
and Contenders. Run each declared control/variant with that complete roster.

The additive `language_breadth_v1` pack retains the original Shakespeare task
and adds 64-byte Shakespeare contexts, a separately pinned Aesop corpus, and a
64-token delayed-copy diagnostic. New real-text tasks use 4,096 training and 768
validation contexts. Raw text is split before windows; the final 15% remains
unused. The Aesop source wrapper is excluded by a pinned byte range. The generated
memory task has independently generated examples and a seeded 80/20 split.
These tasks are experimental, **not admitted as full-fidelity local-safe**;
their runtime and baseline adequacy still require qualification. The existing
tabular/image pack and all frozen definitions remain available unchanged.

The [September 16 readiness audit](reports/readiness-20260916/report.md) records
the loader repair, retained-baseline generalization gaps and checkpoint replay
profile. To repeat either read-only audit, use the frozen producer's Python
environment and a fresh output path:

```sh
<producer>/.venv/bin/python scripts/research/audit_language_baselines.py \
  <producer>/.artifacts/qualification <new-output>/language-baselines.json
<producer>/.venv/bin/python EvoNN-Shared/tests/profile_checkpoint_read.py \
  <completed-run>/checkpoints <new-output>/checkpoint-profile.json
```

The model audit deserializes retained local models: use only trusted run
artifacts. Neither audit fits models or evaluates protected test data. The
checkpoint profiler adds instrumentation overhead and cannot measure an
optimization speedup by itself.

Campaigns can also freeze `primordia_research` with `search_policy`, `max_width`
and `max_depth`. New plans record its defaults explicitly and require the full
engine roster. Adoption and repeated-seed grouping bind these controls and the
derived training policy; frozen historical configurations retain their original
identities. Within-cohort and before/after reports keep every declared contrast
in the Holm correction, including unavailable tests.

### Prism frontier experiments (September 21)

The [latest qualification findings](reports/qualification-20260916/findings.md)
motivate opt-in improvements: Prism's regression winners plateau between 128/256
fits, image quality trails the contender pool, and language quality is promising.
These two-seed observations motivate hypotheses, not mechanism attribution.
`open` remains the default and all earlier controls remain available.

| `--variant` | Addition to `open` |
| --- | --- |
| `search_v2` | Diverse independent founders; benchmark/family-conditioned local mutations; quality-archive reproduction; replace plateaued continuation slots with local alternatives, retaining periodic continuation and protected family rotation |
| `representation_v2` | Global-plus-four-cell spatial readouts for CNNs; zero-initialized linear input skips for MLP families; pre-normalized attention residual blocks. The original architecture choices remain reachable |
| `regularized_v2` | Training-only label smoothing (0.05 classification, 0.02 LM); weight decay on matrices, leaving bias and other vectors unpenalized |
| `averaged_v2` | Per-update exponential weight averaging (decay 0.9); select between raw and averaged validation checkpoints |
| `calibrated_v2` | Select regression checkpoints by the final calibrated MSE; calibration coefficients use training labels only |
| `frontier_v2` | Combine all five additions |

The representation-only arm retains the original founder training settings;
the search-only arm uses original representations. Later adaptive proposals can
diverge with scores. Fixed-genome controls remain available for matched training
diagnostics. Existing `inheritance_policy`, `optimizer_policy` and
`optimizer_backend` switches compose with every new variant.

Validation cross-entropy/perplexity remains unsmoothed. Averaging restarts from
each fit's initialization, includes all its optimizer updates, and publishes a
single selected model. If averaged weights win, Adam continuation resets because
the raw optimizer moments do not describe those weights. Averaged candidates use
the current training-only normalization buffers; no extra batch-statistics
recalibration is performed. Averaging and calibrated selection add validation
work inside the measured fit time and timeout, without extra optimizer updates.
They can overfit validation selection or cost more time; no quality/speedup claim
is established by implementation tests.

The new architecture fields are `readout: spatial_pyramid`, `input_skip: true`
and `pre_norm: true`. Nonneutral fields use the v3 genome identity; neutral defaults
retain historical identities. Model export/replay, cache bounds and the 256-fit limit continue to apply. Per-attempt records and `research-report`
expose proposal origins, selected raw/averaged weights, selection metric, epoch
allowances and completed work.

`EvoNN-Prism/configs/frontier_research.yaml` is a single-run configuration template.
For later comparisons, generate matched campaign specs from an explicit base spec
with the desired pack, budgets, seeds and complete system roster:

```sh
uv run --all-packages python -m evonn_compare.prism_frontier \
  --base-spec <all-system-campaign.json> --output <new-spec-directory>
```

This writes seven specs (`open` plus the six experimental variants), performs no
fits or data preparation, and refuses to overwrite a directory. `--variants`
selects a subset of Prism policies; every emitted arm retains **all four engines
and Contenders** on the same declared cells. Other engine and optimizer policies
are copied unchanged. Use the campaign planning/preflight/run commands below for
each spec in a separate workspace and a frozen source checkout. Compare quality,
failure rates, diversity, optimizer work and measured time; fresh confirmation
and baseline adequacy gates still apply. The old incomplete Q comparison is not
repaired or superseded by these implementation checks.

### Prism post-study candidates (October 6)

The [completed eleven-variant study](reports/prism-confidence-20260921/results-20261006.md)
contains all 1,012 runs. No universal winner passed the frozen confidence rule;
`open` remains the default. Three new, opt-in hypotheses separate promising
regression/image behavior from language behavior:

- `routed_v3`: frontier_v2 for classification/regression; broad for language modeling.
- `lean_v3`: that routing with smoothing, matrix-only decay and averaging disabled.
- `aligned_v3`: lean plus classification checkpoints selected by validation accuracy,
  with unsmoothed cross-entropy breaking ties. Regression uses calibrated MSE.

Routing uses task kind only. Resolved per-task policies are exported, validated and
restored on resume. All original variants and frozen evidence remain available.
Use `EvoNN-Prism/configs/aligned_v3.yaml` (or `routed_v3.yaml` / `lean_v3.yaml`)
with `python -m prism.cli run --config <path>`; these are experimental candidates,
not established improvements over open.

Prepare matched follow-up specifications without running training:

```sh
.venv/bin/python -m evonn_compare.prism_followup \
  --base-spec <all-engine-spec.json> --output <new-spec-directory>
```

This emits open, broad, frontier_v2 and the three new variants; `--variants`
selects a subset. It requires fresh seeds outside 21600–21630 and preserves
Prism, Topograph, Stratograph, Primordia and Contenders on every declared cell.
The old Prism-only exception does not cover these new candidates. Freeze
confirmation contrasts and qualify time allowances before starting a new study.

## Campaign planning and recovery

The user-authorized [Prism-only version study](reports/prism-confidence-20260921/protocol.md)
is a scoped exception: all eleven Prism variants, 30 paired seeds, frozen
all-pair inference and a qualification gate. It uses
`python -m evonn_compare.prism_confidence` and the explicit
`prism_version_study: user-requested-20260921` campaign field. The protocol lists
prepared paths and exact start/pause/resume commands. Preparation runs no study
fits. The [September 21 recovery note](reports/prism-confidence-20260921/recovery.md)
records the separate replacement following a v2 export-validator mismatch and
the [subsequent budget continuation](reports/prism-confidence-20260921/budget-continuation.md)
records the cumulative-cap repair. The [September 22 per-fit continuation](reports/prism-confidence-20260921/fit-continuation.md)
records the load-sensitive fit timeout repair. The [September 23 size continuation](reports/prism-confidence-20260921/size-continuation.md)
provides current paths after an oversized proposal was rejected before training. All-system generators and their normal roster
checks remain unchanged.

Every new comparison must run **all four engines: Prism, Topograph, Stratograph
and Primordia**, on each declared benchmark/budget/seed combination, with
Contenders as additional baselines. This also applies to focused confirmation
and generalization comparisons. Report every engine; weaknesses or execution
failures do not justify omitting one. Failed or missing engine runs make the
comparison incomplete. Historical frozen protocols remain unchanged.

Create a JSON specification, for example `.artifacts/campaign-spec.json`:

```json
{
  "pack": "tier_b_core_v2",
  "budgets": [16],
  "seeds": [42],
  "systems": ["contenders", "prism", "topograph", "stratograph", "primordia"],
  "backend": "mlx_native",
  "epochs": 12,
  "timeout": 300,
  "fit_timeout": 90
}
```

```sh
uv run --no-sync evonn-compare campaign plan \
  --workspace .artifacts/campaign --spec .artifacts/campaign-spec.json \
  --cache .artifacts/dataset-cache
uv run --no-sync evonn-compare campaign preflight .artifacts/campaign
uv run --no-sync evonn-compare campaign run .artifacts/campaign --max-runs 2
uv run --no-sync evonn-compare campaign resume .artifacts/campaign
```

Planning may download and prepare data, but performs no model fits. It freezes
matrix, code commit, benchmark/pool definitions, environment, host, data hashes
and training settings in `campaign.json`. It requires a clean source checkout;
keep that checkout and environment unchanged until the campaign is finished.
Preflight only reads and validates those inputs, probes the requested backend
and checks free space (1 GiB by default). It neither downloads nor trains.
Use a new workspace if planning is interrupted or settings change.

For an explicitly requested macOS training job launched through `launchd`, use
`ProcessType = Standard` (the default), with `KeepAlive = false`. `Background`
and `Adaptive` without an active XPC transaction throttle worker startup and
journal work substantially. Keep the computer awake with `caffeinate -i -m`
around the bounded command. Preserve the launch configuration beside the run;
changing execution priority or source requires a newly planned campaign.

`run` and `resume` share the same recovery path. Each invocation is capped at
30 minutes and pauses before a slot whose full time allowance no longer fits;
it never reduces later slots' configured budgets. Stable case/system slots,
a durable dispatch journal and a worker-inherited lock prevent overlapping
execution. Completed exports are revalidated and adopted, even if their original
completion receipt was lost. Resuming a finished campaign starts zero new runs.
Incomplete native runs resume their committed state; incomplete Contenders runs
stop for inspection because that engine has no resumable fit contract.

The four native engines also keep a durable invocation clock: clean pauses do
not charge offline time, while an unclosed invocation conservatively charges
elapsed wall time through recovery. Clock rollback and broken journals block
resume. Campaign completion reports execution status only; repeated-seed
scientific conclusions still require the registry's separate analysis gate.

## Topograph research modes

Topograph's FP16 quantizer saturates finite values to the representable range
before casting, while retaining the straight-through gradient. This prevents
finite image activations above 65,504 from becoming infinite validation losses.
Nonfinite inputs still fail the training checks. This numerical fix requires a
fresh producer and comparison; frozen historical runs retain their original code.

Topograph has an explicit additive `--variant` option. The default `legacy`
preserves the historical search and genome identities. `mechanics` introduces
truthful mutation attribution, reversible graph edits, branch crossover,
independently sampled founder precision and corrected niche allocation.
`training`, `archive`, and `broad` each add one policy group to those mechanics;
`open` combines them. Compare each group against `mechanics` when isolating its
effect. These are implemented experimental policies, not established quality gains.

- `training`: actual-parent weight transfer across topology changes, copied-fraction
  training allowances, full allowances for protected candidates, and recorded
  cumulative ancestral work without double counting. Fresh starts remain possible.
  Zero-gated branch insertion and restricted zero-padding widening include measured
  output-drift probes; a finite probe is not a proof for all inputs. Optimizer state
  resets at every fit and is disclosed. Learning curves and training-only behavior
  probes accompany every successful v2 fit.
- `archive`: retain every evaluated genome inside the existing 256-attempt run
  envelope, with structural and behavioral cell leaders, a quality/parameter Pareto
  view and a quality-independent reservoir. One slot per generation cycles through
  diversity, uncertain continuation, reservoir, immigrant and fresh-winner control.
  Other slots reproduce niches; any niche deferred by the exploration slot is
  recorded and remains recoverable from the archive. With population four, each
  exploration source is scheduled once per 20 evaluations after initialization;
  short runs can end before a full cycle. Weight eviction does not erase genomes.
- `broad`: expose all valid widths through 256, attention heads, activation precision,
  sparsity, normalization, merge policies, experts/gates, convolution kernels,
  optimizer hyperparameters and optional trainable token/spatial adapters. Flat
  DAG operators stay eligible. The single-channel legacy `depthwise` flag is explicitly
  reserved until it has distinct executor semantics. Parameter shape estimates
  reject oversized variations before allocation, with resource reasons recorded.

The operator scheduler has task-local immediate and small heuristic descendant
credit, uniform exploration support and rotating operator opportunities. Archives
use several descriptor views plus an independent reservoir; learned descriptors and
cross-run seed ingestion remain separate future work. A finite representation and
budget do not guarantee discovery of every possible solution.

Run the short implementation preset explicitly:

```sh
uv run evonn-topograph run --config EvoNN-Topograph/configs/research_open.yaml
```

Use `--backend numpy_fallback` for portability checks. Both paths keep hard fit
timeouts, isolated workers, replay and checkpoint integrity. Versioned policy is
frozen into run configuration; resume rejects a different variant. Legacy
`benchmark_pooling`/`novelty_weight` scalars cannot be mixed with these task-local
research policies. `runtime_profile.json` records compile/inheritance, serialization,
worker, search, snapshot and checkpoint timing. Nested durations are identified;
missing post-crash timing is explicit. Profiling does not claim a speedup.

New campaign specifications can set `"topograph_variant": "open"` (or another
declared mode). Such specifications require Prism, Topograph, Stratograph,
Primordia and Contenders; campaign adoption rejects a mismatched Topograph policy.
No scientific campaign, protected-test access or engine promotion follows from
this implementation. Qualification and further comparisons follow
[the consolidated plan](CONSOLIDATED_PLAN.md#immediate-next-actions).

## Bounded engine operation

```sh
uv run evonn-prism evolve --config EvoNN-Prism/configs/tiny_smoke.yaml
uv run evonn-topograph evolve --config EvoNN-Topograph/configs/tiny_smoke.yaml
uv run evonn-prism evolve --resume <run-directory>
uv run evonn-prism replay <run-directory>
uv run evonn-compare fair-matrix --workspace .artifacts/phase2-native \
  --preset local --systems contenders prism topograph --seeds 42 43 44 \
  --engine-backend mlx_native --engine-epochs 12 --timeout 1200 --fit-timeout 120
```

All four engines expose `evolve`/`run`, `inspect`, `report`, `replay`, `benchmarks`,
`warm-cache` and `symbiosis-export`. Configurations and resumes reject option,
source, dependency and data drift. The tiny presets perform real fits on all
eight smoke benchmarks. NumPy executes the actual architecture and produces
`portability_only` evidence; keep its cohorts separate from native MLX runs.
The native command is a bounded acceptance cohort, not a long research campaign.
Each engine invocation and individual fit have hard limits of at most 1,800 seconds.

Exports bundle checksum-bound data, trained weights, normalization buffers,
regression calibration, attempts and engine telemetry. `replay` reconstructs
held-out metrics without the producer's cache path. Packed low-bit sizes are
estimates; serialized weights and process memory are measured separately.
Topograph's default hardware budget admits one simultaneous training worker;
its runtime worker topology describes that fit worker. One additional pool
supervisor performs no training. The configuration records training, supervisor
and total evaluation process counts explicitly. Optional benchmark pooling uses
within-benchmark quality ranks; novelty weight defaults to zero. MAP-Elites,
full deployment objectives and statistical superiority remain later-phase work.
Compare keeps immutable case evidence at `contract-fair`; a separate
`benchmark-audit --decision-grade` result governs trusted floor admission. A
green audit does not rewrite the original case labels or append-only rows.

The Phase 4 runtime adds `tier_b_core_v2`: OpenML banknote authentication,
small digit images, diabetes regression and a real Shakespeare byte next-token
benchmark. The text source is pinned to an immutable [char-rnn snapshot](https://github.com/karpathy/char-rnn/blob/370cbcd448eb7daf32f21a6be560b70e0b33c4e3/data/tinyshakespeare/input.txt).
Raw text is split before context creation; the final 15% is protected and unused.
The bounded profile samples at most 1,536 training and 384 validation contexts.
The historical catalog and runtime identities remain immutable; active runtime
consumers use the additive extension through `evonn_shared.active_catalog`.
Package READMEs document [Stratograph](EvoNN-Stratograph/README.md) and
[Primordia](EvoNN-Primordia/README.md). The completed repeated comparison remains
scoped to this bounded profile; broader and native transfer claims need further evidence.

Run the verified Tier-B tiny profile across all five systems:

```sh
uv run --locked --all-packages evonn-compare fair-matrix \
  --workspace .artifacts/tier-b-tiny --preset tier_b_tiny \
  --systems contenders prism topograph stratograph primordia --seeds 42 \
  --engine-backend mlx_native --engine-epochs 12 --timeout 300 --fit-timeout 90
```

The preset selects 16 evaluations per system. Each invocation caps five minutes;
this command starts a short qualification, not the larger repeated campaign.

## Architecture and authority

The seven uv workspace packages are Shared, Contenders, Compare, Prism,
Topograph, Stratograph and Primordia. `shared-benchmarks/` is data only;
`evonn_shared.catalog` and `evonn_shared.benchmarks` implement its resolution.
Engines remain independent. Compare invokes system CLIs and consume file
exports; Shared contains infrastructure rather than an engine core.

The pinned [Lab specification](claude-spec/README.md) is normative;
[PROGRAM_CHARTER.md](PROGRAM_CHARTER.md) defines Lab/Product boundaries.
[Product interop](claudex-spec/19-research-interop.md) is retained for the consumer
boundary. The remaining Product specifications live in an exact historical
[Git snapshot](claudex-spec/README.md), outside the Lab working documentation. Real Lab
artifacts may influence Product only after Lab I1 and Product I2 pass.
Source changes follow [SPEC_UPGRADE_PROCESS](governance/SPEC_UPGRADE_PROCESS.md);
[traceability](governance/SPEC_TRACEABILITY.md) identifies the authority roles.

## Installation and local verification

Use Python 3.13 and CI-pinned uv `0.5.13`. Supported workspace platforms are
Linux and macOS; MLX installs only on Apple Silicon macOS. From the repo root:

```sh
uv sync --all-packages --group dev --locked
scripts/ci/foundation-checks.sh
scripts/ci/benchmarks-checks.sh
```

The foundation entry point checks the complete Shared package and root
contracts once, plus lock consistency, Ruff and installed package identity.
For a focused reference check:

```sh
uv run --locked --all-packages --group dev pytest -q EvoNN-Shared/tests/test_reference_runner.py
```

For repository policy and freeze verification:

```sh
scripts/ci/b0-policy-checks.sh
```

This checks authority, freeze, import/dependency and capability rules plus
integration tests. Use a full-history clone with canonical `origin`; an archive
or shallow checkout cannot verify the historical Git evidence. The standalone
freeze validator also rejects Git worktrees: it requires a real repository-root
`.git` directory. Plan/guide validation binds committed bytes, so commit documentation candidates before
running the final governance check. The B0 integration suite takes substantially
longer than focused tests; measured timings are in project history.

Each package also has an independently callable `scripts/ci/*-checks.sh`.
Run the scripts relevant to the change; both hosted jobs run the full foundation
suite and their platform-specific checks. A full `pytest` invocation additionally
runs recursive script self-tests and the complete local script matrix.

## Synthetic integrity evidence

The test-only reference runner uses real persistence and checkpoints. Generate
and validate a fresh report of eight SIGKILL/resume cases (failed and invalid
attempts at four durable boundaries):

```sh
uv run --locked --all-packages --group dev python EvoNN-Shared/tests/integrity_probe.py \
  --work-root .artifacts/reference-integrity/runs \
  --output .artifacts/reference-integrity/report.json
uv run --locked --all-packages --group dev python EvoNN-Shared/tests/integrity_probe.py \
  --validate .artifacts/reference-integrity/report.json
```

Work/output paths must be fresh; existing evidence is never overwritten.
The report compares row/checkpoint hashes, fresh/inherited accounting, selector
traces and source digests around read-only export. It records host metadata and
`synthetic_contract_preparation`. Validation proves internal consistency, not
authenticity. Hosted provenance comes from the GitHub run and tested commit.
Each hosted lane uploads only the report as `b0-linux-synthetic-integrity` or
`b0-macos-synthetic-integrity`, with missing-file failure enabled.

This evidence contributes to the accepted Phase 0 contract gate; it does not
admit executable datasets, qualify an engine or prove scientific performance. Kills before durable row commit and general engine
failure recovery are outside this proof. The diagnostic JSON is not the regular
`manifest.json` / `results.json` / `summary.json` export contract.

## Run-directory assumptions

Use application-owned local directories with working POSIX advisory locks and
atomic rename/fsync semantics. Paths must not traverse symlinks, including
macOS aliases such as `/tmp`; resolve the actual directory. Windows and network
filesystems are not qualified.

Evaluation rows and their hash/count tip commit in one transaction. Existing
records are verified before returning a writer. File/lock/DB/WAL symlinks and
mutable-storage hardlinks are rejected; artifact reads use opened descriptors.
Reports replace atomically; new evidence publication refuses overwrites.

`open_run_reader(directory, run_id)` holds a shared lock and read-only
transaction, verifies identity/schema/row chain, exposes no writer operations,
and preserves source bytes. It rejects missing lock/DB files and existing WALs;
explicit writer recovery precedes reading an interrupted store. Readers may
coexist with readers, not a writer. Corrupt evidence is never silently repaired.

DuckDB opens pathnames, so these controls do not sandbox a process with equal
filesystem privileges replacing directories concurrently. A hash chain and tip
inside one database detect inconsistent edits, not a coordinated rewrite.
Registry receipts bind source and consumer identities; current artifact validation remains required for new claims. Failed schema
creation may leave an empty database; preserve it for diagnosis. A directory
fsync failure after publication means uncertain durability even when a complete
new file is visible; do not delete published evidence as a pretend rollback.

## Benchmark and LM-cache storage

Benchmark definitions live in `shared-benchmarks/catalog/`; packs live in
`shared-benchmarks/suites/parity/`. Eight planned definitions and three packs
are accepted under freeze v3. Additive runtime definitions live in
`shared-benchmarks/extensions/phase4/`; `evonn_shared.active_catalog` resolves
both generations without rewriting frozen identities. Scientific admission is
scoped by the runtime receipts. Canonical
IDs preserve data/split/metric meaning; changes follow WP-0.1b/0.8.

`shared-benchmarks/lm_cache/` holds versioned `<cache_id>.yaml` manifests;
payload bytes are warmed locally and are not committed. Shared validates file
existence, size and SHA-256 before use. Manifest artifact paths are relative,
UTF-8 sorted and unique. `EVONN_LM_CACHE_DIR` overrides the payload root. Example
shape only, not an admitted cache or valid content digest:

```yaml
schema_version: "1.0.0"
cache_id: tinystories_lm
benchmark_ids: [tinystories_lm]
artifacts:
  - path: train.bin
    size_bytes: 1280
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
```

## Development workflow

Work on feature branches and use reviewed PRs. GitHub currently requires **zero
approving reviews**, with last-push approval disabled. Linux/macOS checks,
up-to-date branches, resolved review conversations and admin enforcement remain
required; force pushes/deletion of main stay disabled. Substantive review and
the separate frozen-interface amendment evidence remain part of development.

For stacked PRs, merge a parent, retarget its child to main, synchronize and
validate the exact new head before merging. A successful CodeRabbit status can
represent a skipped review: inspect selected files, actionable threads and
summary warnings. Docstring coverage is distinct from code findings.
The plan owns lane assignments and phase acceptance; no second workflow plan
is needed. Stage explicit paths and preserve unrelated local work.

## License

Copyright (C) 2026 Timo Kruth and contributors.

Unless otherwise indicated, original code and documentation are licensed under
GNU GPL version 3 only (`GPL-3.0-only`); see [LICENSE](LICENSE). Each workspace
package carries its own copy for distribution. The software comes without
warranty. Dependencies, datasets and model weights retain their own licenses.

### Language baseline follow-up operations

The immediate follow-up is a descriptive language-baseline screen: **60 runs /
3,840 fit attempts**, all four engines plus Contenders in every arm, breadth
budget 64 and seeds 1421/1422. Six versioned pools vary Transformer epochs
(2/5/10 versus 20) or n-gram smoothing (0.1/0.01 versus 1.0). Native policies
and 12-epoch envelopes stay fixed. Experimental pools do not inherit floor
admission. The fixed selection/coverage rules live in
`evonn_compare.baseline_study.POLICY`; independent confirmation is still needed.

From a clean, locked producer checkout, first prepare and execute the separate
30-slot implementation qualification (seed 1431, budget 16, two native epochs).
This checks all six arms/all five systems, actual baseline updates and 96 saved
native winners. Preparation of the research run requires its completed receipt:

```sh
.venv/bin/python -m evonn_compare.baseline_study prepare .artifacts/baseline-qualification --qualification --cache .artifacts/data-cache
.venv/bin/python -m evonn_compare.baseline_study run .artifacts/baseline-qualification
.venv/bin/python -m evonn_compare.baseline_study prepare .artifacts/baseline-follow-up --qualification-workspace .artifacts/baseline-qualification --cache .artifacts/data-cache
.venv/bin/python -m evonn_compare.baseline_study preflight .artifacts/baseline-follow-up
```

Preparation and preflight do not train. When launch is authorized, use `run`
with that workspace. `pause` requests a stop between slots; `resume` clears the
pause and revalidates frozen source/data/dependencies before continuing. `report`
verifies coverage and reports incomplete evidence explicitly. Failed Contenders
slots are retained and require diagnosis; they are never automatically replaced.
A second controller is excluded by the study lock. Native interrupted slots
use the existing integrity-checked campaign checkpoint recovery.

The old qualification remains 28/30. Its historical planning/recovery scripts
are retained with explicit integrity checks under `EvoNN-Compare/tests/research_archive/`, with recovery
regressions retained. Their original byte-exact versions remain in the historical commits and frozen producer.
The archived planner now resolves the repository from its moved location; its
original protocol document retains the command valid at the time it was frozen.
These are archival fixtures for the prior producer;
use the module above for this new follow-up. Historical receipts and results
have not been relabeled as complete.

### Primordia v3 research implementation — September 21

Primordia now offers opt-in trainable causal attention, dilated/multiscale temporal
filters, spatial image circuits, normalized residual/skip circuits, safer continued
training and progress-based search. Thirteen presets separate representation,
optimizer schedule, search and inheritance alternatives. Defaults remain the v2
control. See [Primordia's research controls](EvoNN-Primordia/README.md#opt-in-v3-research-arms)
for exact semantics and the generator for complete all-engine comparison specs.
This implements hypotheses from the September 16 results; it does not establish
new quality/runtime gains or close the historical incomplete qualification.


### Prepared Primordia-only confidence comparison

The September 21 user instruction explicitly requests Primordia only, overriding
the usual all-engine roster for this one study. The
[Primordia study runner](EvoNN-Primordia/README.md#primordia-only-confidence-study--september-21)
freezes 13 presets × 16 matched seeds × core/breadth packs, with a separate
qualification phase, replay-gated completion and multiplicity-corrected paired
inference. Preparation does not start training. Other research campaigns retain
the all-engine default and its validation guard.

The completed amended study is at `.artifacts/primordia-only-20260921`, with
416/416 comparisons and 26/26 qualifications. See the
[October 4 findings and implementation](reports/primordia-confidence-20261004/README.md).
Bare fresh Primordia CLI runs now select `standard`, the tested `full_steady`
combination. All 13 original presets remain selectable; `portfolio` and
`portfolio_stable` are new experimental alternatives requiring fresh confirmation.
Explicit configs/campaign policies and saved resumes retain their prior defaults.

The active Primordia time-budget continuation is recorded in
`.artifacts/primordia-only-20260921/active-study.json`. The existing `study.sh`
launcher now forwards to the amended `study-v2` protocol and `producer-v2`.
It preserves 22 completed comparisons and all 26 qualifications, resumes long
runs across bounded sessions, and dispatches the scheduled seed directly. The
original exhausted run and its 248 attempts remain preserved and separately
accounted for; the original frozen study remains incomplete.
