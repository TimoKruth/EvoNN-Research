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
