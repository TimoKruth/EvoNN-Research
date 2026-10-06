# EvoNN Stratograph

Crossover-first macrographs route through reusable cell graphs. Search can clone,
specialize, grow, prune, rewire and reuse successful cell programs. Task profiles,
bounded niches and lineage are checkpointed. Each package owns its compiler and
runtime; [duplication notes](DUPLICATION_NOTES.md) explain common numerical code.

## Quality-first standard

Fresh CLI runs, new `RunConfig` objects and direct `run_engine` calls now use
the exact **evolving** v3 preset from the completed
[eleven-preset study](../governance/stratograph-results-20260930.md). It improved
core, real text and delayed-copy memory versus v2 across 16 paired seeds, with
Holm-adjusted confidence tests. Real-text symmetric gain was +20.24%
[19.42%, 21.07%]. This is a within-engine validation result, not a claim of
superiority over other engines or an established unique best preset.

The standard keeps hybrid temporal mixing, learned embeddings, RMS cell
normalization, gated residuals, learned merges, readout skips, compatible weight
inheritance and diverse search. Representation and temporal choices can evolve.
Dropout remains zero and every fit receives the full epoch allocation; combining
the dropout arm with evolving would be a new, untested policy.

Defaults are **128 fits, 12 epochs, population 4**, native MLX on Apple Silicon
CPU (NumPy portability execution elsewhere), a **600-second per-fit cap** and
an **81,240-second total safety cap**. The total cap covers 128 full fit allowances
plus overhead; it is not an expected runtime. Budgets and caps remain explicitly
overridable. The tested evolving arm used roughly twice v2's language training
time; quality is preferred over the cheaper attention alternative.

```sh
uv run evonn-stratograph run --pack language_breadth_v1
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/standard.yaml
uv run evonn-stratograph run --preset attention --pack language_breadth_v1
uv run evonn-stratograph run --preset hybrid_dropout --pack language_breadth_v1
uv run evonn-stratograph run --preset legacy --budget 64 --timeout 1200 --fit-timeout 120
```

`--preset standard` aliases `evolving`; all eleven study names and `legacy` are
available. Presets select the model/search policy, while allocation flags remain
independent. Do not combine `--preset` with `--config`, `--research` or `--resume`.
YAML can specify the full `research` object; explicit `research: null` or
`--research null` selects legacy. Omission in a new configuration selects evolving.
The historical smoke/core YAML files explicitly retain legacy; `standard.yaml`
is the new native quality configuration.

Resume restores the saved policy, backend and allocation, including historical
runs without `research`. Explicit mismatches are rejected, and unchanged-producer
requirements still apply. Genome/policy defaults used to decode historical
artifacts are unchanged. Newly prepared Compare campaigns freeze the standard
policy when `stratograph_research` is omitted; explicit null selects legacy and
existing manifests retain their recorded semantics. Campaign budgets, backends
and time caps remain the campaign's explicit matched settings.

The legacy evaluator is `hierarchy_features_trained_head`: deterministic cell
projections plus a trained GELU head. MLX trains that head; this does not establish
end-to-end learned hierarchy sharing or transfer performance.

```sh
uv run --package evonn-stratograph evonn-stratograph run --config EvoNN-Stratograph/configs/smoke.yaml
uv run --package evonn-stratograph evonn-stratograph run --pack tier1_core --budget 64 --backend mlx_native --variant shared
uv run --package evonn-stratograph evonn-stratograph run --resume <run-directory>
uv run --package evonn-stratograph evonn-stratograph replay <run-directory>
uv run --package evonn-stratograph evonn-stratograph motifs analyze <run-directory>
uv run --package evonn-stratograph evonn-stratograph ablate --pack tier_a_contract --budget 16 --seeds 42 --backend mlx_native --timeout 1800
```

The five variants are `shared`, `flat`, `unshared`, `no-clone` and
`no-motif-bias`. Compare them at identical pack, budget, seed and runtime; keep
variant metadata. `ablate-matrix --budgets 16 64 --seeds 42 43` uses the same
five variants; `--timeout` caps the entire batch at 30 minutes. Each batch keeps
a resumable-run directory and a verified `ablation.json` index; incomplete
batches retain their completed exports and never claim a full comparison.
`motif_analysis.json` contains winner-conditioned programs,
structural descriptors and lineage. `lm_diagnostics.json` keeps proxy/flatline
limitations explicit. Both artifacts are checksum-bound and semantically checked.

Runs cap 256 proposals and 24 hours. NumPy is portability-only; the large
five-system repeated Tier-B campaign remains a separate authorized decision.

## Explicit version 2 research execution

Explicit v2 policies remain available for comparison. Saved configurations
without `research` keep v1 genomes, projection functions, search and training
allocation on resume; fresh configurations without it now select the standard
above. Historical saved winners remain replayable. Resuming a run still
requires its unchanged producer; replay compatibility does not waive source-drift
checks or authorize resuming an old run on new code.

```sh
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/research_v2.yaml
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/trainable_v2.yaml
uv run evonn-stratograph run --pack tier1_core_smoke --budget 16 \
  --research '{"version":2,"evaluator":"trainable","normalization":"rms"}'
```

The presets use NumPy portability execution. Select `--backend mlx_native` for
native execution on Apple Silicon. These commands perform bounded research fits;
passing them establishes execution, not scientific superiority. Individual runs
accept an explicit total timeout up to 24 hours. These older YAML examples retain
their explicit small allocations and caps; the standard uses the allowances above.
Model-publication and weight-cache limits remain unchanged.
The `ablate` batch command retains its separate 30-minute total cap.

`research` is an explicit portable policy, stored in configuration, checkpoint and
comparison fingerprints. CLI JSON and YAML accept the same fields. `--resume`
restores it and rejects explicit mismatches. The evaluator is fixed per run:

| Setting | Choices and meaning |
| --- | --- |
| `evaluator` | `proxy`: fixed projections with a trained head, fidelity `hierarchy_features_trained_head_v2`; `trainable`: shared differentiable cell matrices and head, fidelity `end_to_end_hierarchy_v2` |
| `normalization` | `train_standard` (default): per-channel statistics fitted only on training inputs; `rms`: differentiable per-example/per-token channel RMS; `none`: retained experimental alternative |
| `readout` | `final`, `all` macro outputs, or `input_final` concatenation |
| `residual` | Optional input-preserving cell paths where dimensions match; projected adapters otherwise |
| `head_width` | Initial head width, 4–64 |
| `evolve_representation` | Default true: normalization, readout, residual paths and head width can evolve; false freezes them for controlled ablations |
| `inheritance` | `compatible` (default): copy matching projection identities and only representation-compatible heads; `fresh`: no inheritance; `head_diagnostic`: permit same-shape head copying across representations for a controlled diagnostic |
| `selection` | `diverse` (default): protected rotating exploration/revisit slots; `quality`: explicit control ablation |
| `screen_epochs` | Default 0 gives every fit the full configured epochs; positive values screen offspring, with full allocation for archive revisits. Must not exceed `epochs`. |
| `archive_size` | 8–128, default 32; bounded niche and reservoir capacity |
| `max_macro_nodes`, `max_cell_nodes`, `max_width` | Explicit execution envelope within the current codec's 8 macro nodes, 6 nodes per cell and width 64 |

For `train_standard`, statistics are fitted for a fresh representation using
the current hierarchy and training data, then held fixed during optimization and
saved in `hierarchy_standard_v2` buffers. In trainable execution these are initial
feature statistics, not continuously updated estimates. Compatible inheritance
retains these buffers within the same dataset/split namespace so a learned clone
preserves the parent function. RMS normalization remains
an alternative. Inference never fits statistics to validation, test or batch data.

Projection seeds live on nodes. Activation changes preserve unrelated matrices;
`projection-randomize` is a separate operator. Learned clones receive independent
parameter arrays initialized from compatible parent arrays. Shared calls reference
the same parameters and aggregate their gradients. Mutated feature representations
receive fresh heads under compatible inheritance. V2 never reduces epochs merely
because weights were inherited, and it allows the entire allocated epoch window
without the legacy early-stop patience cutoff.

Shared search seeds both one-node and deeper macrographs. It can expand, contract,
collapse, add/remove edges, clone, specialize, share, change primitives, randomize
projections, grow/prune cells, adjust all integer widths in the envelope, and
change optimization settings. Reproduction includes mutation-only offspring.
The variant exclusions remain explicit ablation controls, not conclusions about
which architecture families are worthwhile.

Diverse selection rotates through quality, niche, novelty, fresh, quality,
random revisit, niche, uncertain revisit, fresh, novelty, promising revisit and
reservoir-parent slots. The cycle continues across generations and resumes;
short budgets may end before every slot has executed. Uncertain revisits use low
observation count as a sampling proxy, not a calibrated uncertainty estimate.
Novelty uses normalized prediction signatures on training examples. Niche eviction
is independent of absolute quality, and a bounded reservoir retains low-scoring
candidates. Archived candidates can reproduce or receive another charged fit.
Every revisit is a new fit with its own initialization stream and accounting;
inherited training is not a free evaluation or a pristine from-scratch replicate.

`research_diagnostics.json` records actual selection counts, reachable structures,
optimizer updates, measured training seconds, repeat outcomes and observed
screen/full ranking reversals. Insufficient repeated pairs remain unavailable.
The export consumer reconstructs these diagnostics from the attempt ledger.
Winner-conditioned motifs remain separately labeled; reproduction can draw cell
programs from the broader archive pool.

The primitive registry in `src/stratograph/operators.py` exposes pure,
shape-preserving, causal differentiable programs. Every registered name is
available to primitive mutation and fresh cell growth. `identity` bypasses the
activation after projection; it is not an identity of the whole cell. Adding a
primitive requires explicit source/version changes and tests for shapes,
gradients, causality and replay; dynamic registrations must also exist in worker
source. New operations are never inferred to be impossible merely because they
are absent from today's codec. Larger resource envelopes require a versioned
codec/runtime extension and new qualification, not edits to frozen evidence.

## Scientific breadth and qualification

Weak performance changes sampling priority; it does not permanently remove a
supported primitive or architecture family. Keep the exploration allocation,
archive revisitation and extensible grammar. Maintain executable validity and
resource bounds, record failures, and retain negative evidence with its context.
Finite runs cannot guarantee visiting every supported possibility.

For a campaign, set `stratograph_research` in the Compare campaign specification
to the same policy object. Research campaigns require Prism, Topograph,
Stratograph, Primordia and Contenders on every declared combination. Plan separate
matched all-engine reference and intervention campaigns; retain the original
Stratograph producer/results. Freeze `evolve_representation: false` to isolate
normalization/readout interventions, and compare `inheritance: fresh` against
`compatible` at identical allocations. Qualify the trained hierarchy separately
from the proxy, then test combined policies on fresh seeds. Existing protected
splits stay reserved for the separately frozen generalization protocol.

## Version 3 temporal research

The [September 16 qualification findings](../reports/qualification-20260916/findings.md)
show that the trained v2 hierarchy substantially changes the old proxy picture:
core@256 averages 97.92% digits accuracy and 2684.8 diabetes MSE. Delayed-copy
perplexities of 9.122 and 5.610, versus much stronger attention baselines, motivate
the new temporal alternatives. These are two-seed descriptive observations in an
incomplete 28/30 comparison; they do not isolate a cause or establish v3 gains.

V3 uses `research.version: 3`, `evaluator: trainable`, and exported
fidelity `end_to_end_hierarchy_v3`. It retains the schema-2 graph container with
an explicitly versioned execution policy. V1/v2 policy decoding, serialization,
genome identities and numerical execution are preserved. Frozen runs still
require their original producer for resume.

```sh
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/attention_v3.yaml --backend mlx_native
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/dilated_v3.yaml --backend mlx_native
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/hybrid_v3.yaml --backend mlx_native
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/evolving_v3.yaml --backend mlx_native
```

These are individual implementation runs. Scientific comparisons must include
all four engines and Contenders in every arm. Runtime, fit, memory and graph-size
limits are unchanged; larger temporal models can exhaust a fit timeout.

| V3 setting | Alternatives and behavior |
| --- | --- |
| `temporal` | `prefix` retains prefix averaging; `attention` uses learned causal Q/K/V/output matrices; `dilated` uses learned depthwise taps at lags 0, 1, 2, 4, … up to context length; `hybrid` learns a per-channel mixture of attention and convolution |
| `position` | `relative` learns an attention bias for each causal lag; `sinusoidal` adds fixed position encodings; `none` is the order-information control. Relative bias affects attention only. |
| `embedding_width` | 0 retains one-hot inputs; 1–64 uses a learned token embedding lookup (default 32). Non-language inputs retain their existing preprocessing. |
| `cell_normalization` | `rms` normalizes each projected cell input before the nonlinear branch; `none` disables it. Readout `normalization` remains a separate setting. |
| `residual_mode` | `gated` adds a learned sigmoid-gated branch to the input/adapter path, initialized with gate logit -2; `legacy` uses v2's `residual` setting. |
| `merge` | `learned` learns softmax weights over graph parents, initialized uniformly; `mean` retains equal averaging. Shared calls with the same parent count share merge parameters. |
| `readout_skip` | Adds a zero-initialized learned linear path from hierarchy features to logits, alongside the nonlinear head. |
| `select_initial` | Keeps the initial/inherited checkpoint eligible for validation selection while still charging and executing the allocated fit. |
| `weight_decay_scope` | `matrices` excludes biases, gates and relative-position vectors from decay; `all` retains v2 behavior. |
| `dropout` | Optional inverted feature dropout during training, 0–0.5; explicit fit RNG, disabled at inference. Default 0. |
| `niche_policy` | `representation` distinguishes temporal mode, readout, width bucket and primitive set in addition to graph structure; `structure` is the v2 control. |
| `evolve_temporal` | Allows temporal mode, embedding width and position mutations. Default false keeps experimental arms fixed. |

`evolve_representation` additionally permits v3 cell normalization, residual-mode,
merge and linear-readout mutations. The three fixed presets freeze both kinds of
representation mutation; `evolving_v3.yaml` enables both. Optimizer and graph
mutations, protected exploration and charged archive revisits remain available.
Temporal operators replace the `sequence` primitive in language cells; graphs
without that primitive do not execute a temporal mixer. Sharing and cloning cover
all new parameters, and changed representations cannot silently inherit heads.

Attempt ledgers and `research_diagnostics.json` retain per-epoch training and
validation losses, maximum gradient norms, initial loss, selected epoch, actual
temporal modes, and embedding changes. Selecting epoch zero is explicit and does
not erase the updates or time spent trying to improve it. Validation remains the
selection split; protected tests are unused.

To create separate, unexecuted comparison specifications for later use:

```sh
uv run --all-packages python -m evonn_compare.hierarchy_configs \
  --output .artifacts/stratograph-v3-specs \
  --packs tier_b_core_v2 language_breadth_v1 --budgets 64 128 --seeds 1601 1602 \
  --arms v2_reference attention dilated hybrid evolving
```

The generator supports eleven named arms: `v2_reference`, `v3_control`,
`attention_only`, `dilated_only`, `stabilized_prefix`, `attention`, `dilated`,
`hybrid`, `hybrid_fresh`, `hybrid_dropout`, and `evolving`. `v3_control` disables
the new mechanisms and has a numerical-equivalence test against v2.
The `_only` arms isolate temporal mechanisms; `stabilized_prefix` tests the
combined representation/training changes without a new temporal mixer.
Every emitted specification contains Prism, Topograph, Stratograph, Primordia and
Contenders, with identical declared seeds/budgets across arms. It neither freezes
a scientific protocol nor trains models, and refuses to overwrite a directory.
Seed freshness must be checked against the evidence registry before execution.
Use the existing Compare `campaign plan --spec <file> --workspace <new-dir>
--cache <cache-dir>`, `campaign preflight <new-dir>` and `campaign run <new-dir>`
workflow from a clean committed producer. A failed engine keeps that comparison
incomplete. Keep delayed-copy and real-text quality panels separate, and retain
both fit-count and measured-training-time costs.

Implementation checks cover native/portable gradients, causal masking, learned
distant-token recall, clone inheritance, legacy equivalence, crash recovery,
export validation and winner replay. Repeated all-engine scientific qualification
of v3 remains pending; no new superiority or transfer claim is made.

## Explicitly authorized within-Stratograph study

The user separately authorized an eleven-preset comparison on September 21.
[Its protocol](../governance/stratograph-only-study-20260921.md) specifies paired
seeds, qualification gates, confidence intervals, Holm correction and failure
retention. `python -m evonn_compare.stratograph_study` supplies preparation,
preflight, bounded execution/resume and analysis for that within-engine scope.
Its `prepare` command creates verified datasets and freezes every configuration;
it performs no model fits. Ordinary all-engine campaign admission is unchanged.
Use the pinned producer launcher recorded in the
[preparation receipt](../governance/stratograph-only-preparation-20260921.json), so ongoing
workspace edits cannot change the planned comparison.

After the original run-cap failure, the user authorized the
[recorded continuation](../governance/stratograph-only-continuation-20260921.md).
Its active launcher is
`.artifacts/stratograph-only-continuation-20260921/resume.sh`; use its `preflight`
or `analyze` command for the amended study. The original failed study and its
launcher remain historical evidence. The continuation reuses verified full-epoch
runs and applies a 30-minute safety cap to unfinished cells while preserving the
frozen engine and statistical plan.

That continuation subsequently exhausted its cap on `hybrid`. The active
[budget-based continuation](../governance/stratograph-only-budget-resume-20260921.md)
retains 39 completed runs and both failed runs. It uses a separate producer whose
only engine changes allow longer total runs. Remaining 128-fit cells receive a
5½-hour ceiling, derived from the full fit budget and existing two-minute fit
limit plus overhead. Current operations use
`.artifacts/stratograph-only-budget-resume-20260921/resume.sh`.

The September 22 [numerical continuation](../governance/stratograph-stability-resume-20260922.md)
is now active after a finite-loss backward overflow at 87 completed runs.
It retains those results and uses a separately frozen producer that retries only
nonfinite backward gradients in host float64 before the existing clipping and
float32 optimizer update. Recovery stays inside the original fit deadline and is
reported in `gradient_recovery`; ordinary finite updates and inference are
unchanged. Current operations use
`.artifacts/stratograph-stability-resume-20260922/resume.sh`.

After that continuation reached 105 completions, an evolving Aesop fit exceeded
its two-minute fit allowance. The user-authorized
[fit-time amendment](../governance/stratograph-fit-resume-20260922.md) retains those
completed runs and grants every unfinished fit ten minutes. Total run allowances
cover all declared fits plus overhead; model settings and fit budgets remain
unchanged. Current operations use
`.artifacts/stratograph-fit-resume-20260922/resume.sh`.

The study completed all 374 runs and final validation on September 30. The
[results](../governance/stratograph-results-20260930.md) support the user-requested
quality-first promotion of evolving described above. Frozen producers, protocols,
exports and the other ten presets remain available and unchanged.
