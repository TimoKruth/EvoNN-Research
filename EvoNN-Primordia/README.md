# EvoNN Primordia

Primitive-first search trains dense, gated, sparse and residual circuits with
replace/mean/product merges. The package-local NumPy/MLX compiler, loader and
search have no sibling-engine imports. See [duplication notes](DUPLICATION_NOTES.md).

New runs default to **`breadth_v2`**, an experimental exploration policy. Its
quality and runtime benefit have not been established by a new comparison.
The September 9–11 results describe the preserved **`legacy_v1`** policy.

The v2 search retains quality leaders, behaviorally different candidates, recent
lineages, a score-independent reservoir (including failed candidates), and a
quality/work-cost Pareto front. After independent founders, recurring proposal
slots select quality, novelty, young, reservoir, fresh, patient, fresh-retrain,
and cost candidates. Patient slots retry reservoir candidates without early
stopping; fresh-retrain slots evaluate an elite architecture from new weights.
These scheduled slots are finite-budget opportunities, not guarantees that every
candidate survives or every possible solution is found. Reservoir eviction never
bans a representation or operator from future restarts/mutations.

All candidates may use the configured epoch budget regardless of arrival time or
inheritance. Ordinary early stopping follows validation progress after at least
`min(epochs, 4)` epochs; patient slots use the full budget. Copied weights alone
never reduce training allocation. Every new fit, including retries, is charged;
actual optimizer updates, training time and learning curves remain recorded.

Genome **v2** adds branching/reused subcircuit outputs, mutable sparse offsets,
causal lag processing alongside the legacy prefix mean, identity growth, motif
duplication and removal. Identity growth preserves the function when parent
weights are inherited; arbitrary width or graph changes do not claim this.
`--max-width` (default 48, supported 2–256) and `--max-depth` (default 8, supported
1–32) freeze an explicit envelope for the run, equally for all modalities.
Changing the envelope requires a new run; larger future formats remain possible.
The 2-million-parameter fit guard, 256-proposal/1,800-second run caps and cache
limits remain. Resource failures are recorded separately in exploration telemetry.
They are not scientific evidence that an architecture cannot work.

```sh
uv run --package evonn-primordia evonn-primordia run --config EvoNN-Primordia/configs/smoke.yaml
uv run --package evonn-primordia evonn-primordia run --pack tier1_core --budget 64 --backend mlx_native --search-policy breadth_v2 --max-width 64 --max-depth 12
uv run --package evonn-primordia evonn-primordia run --resume <run-directory>
uv run --package evonn-primordia evonn-primordia replay <run-directory>
```

`--search-policy legacy_v1` retains the previous search and training rules:
image/LM width 12/depth 2, other tasks width 24/depth 4, family epoch caps,
late-slot and inheritance discounts, and forced cheapening. Historical v1 genome
serialization, identity and numerical execution remain unchanged. Old exports
can be replayed; source-pinned historical runs must still resume with their
original producer. No source/config drift exception was introduced.

Exports contain `primitive_bank.json`, `seed_candidates.json`,
`search_leaders.json` and a Markdown bank. Seeds bind their v1/v2 genome encoding,
source, data split, score and spent budget. Translation targets remain Prism,
Topograph and Stratograph; native ingestion and transfer gains remain unproven.
`inspect` reconstructs missing bank views from verified export-bound trials.
Exploration telemetry reports lane usage, structural changes, retention sizes,
behavioral diversity, envelope-boundary proposals and resource failures.
Descendant improvement counts are bounded-lineage diagnostics, not causal credit.

Any scientific before/after comparison must include all four engines plus
Contenders on every declared benchmark/budget/seed combination. Compare both
proposal counts and actual compute; v2 intentionally permits more training work.
Protected test data remain outside search and these implementation checks.

## Opt-in v3 research arms

The September 21 implementation targets the latest [qualification findings](../reports/qualification-20260916/findings.md):
competitive regression and language scores at low recorded training cost, weaker
image accuracy, and useful language gains at the larger fit budget. Those two-seed
observations motivate these changes; they do not establish a mechanism or a v3 gain.
The historical 28/30 qualification remains incomplete. The breadth loader repair
is already present and covered by separate parity tests.

Four independent controls keep ablations reproducible:

| Flag | Values and behavior |
| --- | --- |
| `--architecture-policy` | `v2` (default); `attention_v3`, `convolution_v3`, `multiscale_v3` for fixed language families; `conv_flat_v3`, `conv_pool_v3` for fixed image families; `temporal_v3`, `spatial_v3` for family search; `expressive_v3` enables all v3 modalities |
| `--optimization-policy` | `v2` (default); `stable_v3` uses starting-checkpoint selection, longer minimum/patience, classification-only 0.05 label smoothing and cosine scheduling; `steady_v3` substitutes a constant post-warmup learning rate |
| `--proposal-policy` | `v2` (default); `progress_v3` adds elite continuation, recent learning-progress revisits and primitive recombination, retaining novelty, youth, reservoir, fresh, patient, cold-retrain and cost slots |
| `--inheritance-policy` | `enabled` (default), or `disabled` for fresh initialization throughout search |

Genome **v3** adds trainable single-head causal attention with relative-distance
biases; depthwise causal filters with mutable dilation; multiscale lag filters;
shared trainable 3×3 image projections with position-preserving readouts, either
unpooled or following 2×2 average pooling; RMS normalization, residual updates,
input-to-output skip readouts, and deterministic training-only dropout. Spatial
circuits use channel-last images. New founders deliberately cover larger widths
and more than one depth within the same explicit envelope. All learned operations
run and differentiate on NumPy and MLX. Token embeddings and v3 cross-entropy use
indexed gathers, avoiding vocabulary-sized one-hot intermediates.

Architecture-only arms retain v2 training/search controls. Fixed-family arms keep
the declared mixer or spatial stem through mutations. Language-only and image-only
arms retain v2 genomes for other modalities. These arms isolate a representation
package, including its founder/normalization choices, not a single tensor operation.

Stable training measures the initial validation loss and may return epoch 0 if
all trained checkpoints are worse. Every optimizer update and fit is still charged.
Validation NLL remains unsmoothed. Equal-accuracy cached models may advance when
validation loss improves; a lower score cannot replace the cache leader. V3
inheritance copies only matching tensor shapes with compatible roles; changed
widths start fresh. Appended identity nodes preserve the inherited function.
Search, cache metadata, policies and RNG state survive crash/resume. Exports retain
selected epochs, curves, proposal lanes and versioned genome/bank identities.
Historical v1/v2 genome bytes and execution remain supported; legacy controls
reject v3 research settings.

Thirteen ready-to-run presets live in [configs/research_v3](configs/research_v3):
`control`, `attention`, `temporal_convolution`, `multiscale`, `spatial_flat`,
`spatial_pool`, `representations`, `stable_training`, `steady_training`,
`progress_search`, `full`, `full_steady`, and `full_cold`.

```sh
uv run evonn-primordia run --config EvoNN-Primordia/configs/research_v3/full.yaml
```

For later comparisons, generate all-engine campaign specifications without fits
(select fresh seeds and a bounded subset of arms before execution):

```sh
uv run --all-packages python -m evonn_primordia.experiments .artifacts/primordia-v3-specs \
  --seeds 1901 1902 --budgets 128 256 --arms control attention spatial_pool full
uv run evonn-compare campaign plan --workspace .artifacts/primordia-v3-control \
  --spec .artifacts/primordia-v3-specs/control.json --cache .artifacts/data-cache
```

Repeat preparation for each selected arm from the same clean, locked producer.
Use `--pack language_breadth_v1` for separate breadth specifications. Every arm
includes Prism, Topograph, Stratograph, Primordia and Contenders on every case;
failures leave that arm incomplete. Generation does not qualify or launch a study.
Compare actual training work as well as fit counts, retain the original controls,
and confirm any nomination on independent seeds. `full_cold` is an end-to-end
search ablation: changed scores can change later proposals, so it is not a matched
finalist warm/cold comparison. No v3 scientific superiority claim is made.

The [implementation receipt](../governance/primordia-v3-implementation-20260921.json)
records NumPy/MLX numerical checks, real worker/export/replay and forced-kill
recovery tests, existing v2 regressions, and the tested source hashes. These are
CPU correctness checks, not a runtime speed benchmark or GPU qualification.

## Primordia-only confidence study — September 21

The user's subsequent request explicitly narrows this study to Primordia. The
usual all-engine requirement remains the default for other comparisons. The new
`primordia_variants_v1` campaign scope accepts only Primordia with an explicit
policy and rejects unrelated engine settings.

`evonn_compare.primordia_study` prepares all 13 current presets on 16 paired
seeds (23101–23116), both `tier_b_core_v2` and `language_breadth_v1`, 256 fits
per pack/run and 12 maximum epochs. This is **416 comparison runs / 106,496
fit attempts**. A separate seed (23191), 64 fits and two epochs qualify all
26 preset/pack combinations first, exercising the recurring search lanes.
Including qualification: **442 runs / 108,160 fit attempts**. Runs execute
serially on one pinned MLX CPU host; per-run and per-fit caps remain 1,740 and
120 seconds. Preparation starts no training, including qualification.

Every unordered pair of presets is compared on six predeclared endpoints:
core digits, diabetes and Shakespeare, breadth Shakespeare context 64 and Aesop,
and delayed copy as a separate synthetic-memory endpoint. All 468 comparisons
share one Holm correction family. Analysis retains paired seeds, exact 65,536
sign assignments, pointwise 95% bootstrap intervals, and approximate simultaneous
95% intervals from 20,000 joint seed resamples. The sign-flip test assumes
symmetric paired effects under the null. Materiality is 0.5 accuracy percentage
points, a 1.02 before/after ratio for regression/real text, and 1.05 for delayed
copy. A supported material gain needs both corrected significance and a
simultaneous interval beyond its margin; otherwise the result can be inconclusive.
Zero-variance estimates cannot establish material superiority from the bootstrap.
Sixteen seeds allow useful inference but do not guarantee adequate power.

Banknote and the breadth bridge remain descriptive sentinels. No aggregate mixes
synthetic memory with language or declares an overall champion. Runtime and
optimizer work are reported separately; different training effort is not treated
as matched compute. Validation-selected winners are not protected-test evidence.
Failed/missing slots keep the study incomplete, with no partial-matrix inference
or automatic replacement. Qualification and every saved-winner replay must pass.
The study freezes source, dependencies, host, data, preset order, seeds and
interpretation before execution; source changes require a new study.

From a clean frozen producer, the supported commands are:

```sh
python -m evonn_compare.primordia_study prepare STUDY --cache CACHE
python -m evonn_compare.primordia_study preflight STUDY
python -m evonn_compare.primordia_study run STUDY                # qualification, then comparison
python -m evonn_compare.primordia_study run STUDY --phase qualification
python -m evonn_compare.primordia_study pause STUDY              # current bounded run finishes
python -m evonn_compare.primordia_study resume STUDY
python -m evonn_compare.primordia_study report STUDY
```

`--max-runs N` bounds a launch session without changing any run's declared budget.
Resuming preserves completed evidence and replays; it does not retrain completed
slots. Separate campaign and controller locks prevent duplicate dispatch.

### Time-budget amendment after the first comparison seed

The September 21 launch exhausted the original 1,740-second run cap at 248/256
successful attempts in `full_steady` on language breadth, seed 23101. The user
requested a fix and resume. The continuation at
`.artifacts/primordia-only-20260921/amendment-20260921` retains all 26 qualifications
and 22 completed comparisons. It records the original exhausted run and its cost,
and restarts that slot once under the amended protocol. All 394 unfinished slots
receive the same 36,000-second cumulative safety allowance, dispatched in sessions
of at most 1,740 seconds. Session pauses retain checkpoints and do not renew the
total allowance or shorten a fit to squeeze it into the session.

`evonn_compare.primordia_continuation` binds both producer revisions, inherited
results, the original protocol, and the amended campaign manifests. Fit counts,
seeds, epochs, models and statistical hypotheses are unchanged. The original
study remains incomplete; the continuation report labels the differing safety
caps and separately accounts for the original 248 attempts. Use its `study.sh`
launcher for preflight, pause, resume and report. The frozen original producer
must not be edited or relaunched alongside the continuation.

## Results-based standard and experimental portfolios — October 4

The completed 416-run study supports image and language improvements from the
`full_steady` combination. See the [results and simultaneous confidence intervals](../reports/primordia-confidence-20261004/README.md).
Digits validation accuracy averaged 99.67% versus control's 97.24%; the three
natural-language endpoints and delayed copy also passed the study's corrected
material-gain gates. Regression remains inconclusive. Standard took 3.74 times
the total recorded training seconds of control; this is a quality-oriented choice,
not an equal-time efficiency claim or an all-engine winner.

Bare fresh CLI runs now use `standard` (exactly `full_steady`). Explicit configs,
any explicit research/search policy, campaign controls and saved resumes keep
their old default behavior. Low-level `RunConfig`, `Search` and `run_engine` defaults
remain the v2 control. To select the new behavior explicitly:

```sh
uv run evonn-primordia run --preset standard --pack tier_b_core_v2 --budget 64 --backend mlx_native
uv run evonn-primordia run --preset control --pack tier_b_core_v2 --budget 64 --backend mlx_native
uv run evonn-primordia run --preset portfolio --pack language_breadth_v1 --budget 64 --backend mlx_native
uv run evonn-primordia run --preset portfolio_stable --pack language_breadth_v1 --budget 64 --backend mlx_native
uv run evonn-primordia run --resume PATH_TO_SAVED_RUN
```

`--preset` supports all 13 original arm names plus `standard`, `portfolio` and
`portfolio_stable`. Size, epochs, budget, seed and backend can accompany a preset.
For custom policy combinations use individual flags or a config file instead;
presets cannot accompany those policy flags, a config file or a resume. Config
files for the three new names are under `configs/`. Saved runs record concrete
policies, so future preset changes cannot alter their replay.

The experimental portfolio rotates **convolution → attention → multiscale**
for language founders and subsequent fresh proposals, and **conv_pool → conv_flat**
for images. Rotation counters are independent for each benchmark and survive
checkpoints. Mutation stays within those model families. Tabular representations
remain v2. This routing uses task/modality metadata, never benchmark names or
held-out scores. Population sizes as small as two still receive every family
through recurring fresh opportunities. Failed attempts remain charged/reported;
they do not erase allocation history. Family attempt counts and fresh-proposal
counts are exported and checked against the ledger, including queued proposals.

`portfolio` retains steady_v3 training; `portfolio_stable` uses stable_v3/cosine
training. Both retain progress_v3 search and inheritance. Neither portfolio has
been compared scientifically yet; they preserve separate opportunities because
attention solved delayed copy while convolution/multiscale improved natural text.
To generate reviewable follow-up specs without launching training:

```sh
uv run python -m evonn_primordia.experiments .artifacts/primordia-followup-specs \
  --pack tier_b_core_v2 --budgets 128 256 --seeds 24001 24002 24003 24004 \
  --arms control standard portfolio portfolio_stable
```

Every generated arm includes Prism, Topograph, Stratograph, Primordia and Contenders.
The example seed count is an operational example, not a confidence/power guarantee.
Freeze an appropriate fresh-seed protocol before a new scientific comparison.
