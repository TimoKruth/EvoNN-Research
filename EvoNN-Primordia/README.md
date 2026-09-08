# EvoNN Primordia

Primitive-first search trains tiny dense, gated, sparse and residual circuits,
with explicit replace/mean/product merges. LM features combine each token with
a causal prefix mean before the primitive circuit. Its package-local NumPy/MLX runtime,
dataset loader and archive search have no sibling-engine imports. See
[duplication notes](DUPLICATION_NOTES.md) for shared numerical ancestry.

Image/LM circuits cap width 12 and depth 2; other tasks cap width 24/depth 4.
Image/LM fits cap 4 epochs, other fits 8; slots 16 onward cap 3. Weak expensive
parents receive cheaper offspring. Selection cost is the deterministic proxy
`parameter_count × optimizer_updates`; measured seconds remain in the ledger and
reports. This keeps host scheduling noise out of reproduction and resume. Every
new fit is charged despite inheritance.

```sh
uv run --package evonn-primordia evonn-primordia run --config EvoNN-Primordia/configs/smoke.yaml
uv run --package evonn-primordia evonn-primordia run --pack tier1_core --budget 64 --backend mlx_native
uv run --package evonn-primordia evonn-primordia run --resume <run-directory>
uv run --package evonn-primordia evonn-primordia inspect <run-directory>
uv run --package evonn-primordia evonn-primordia replay <run-directory>
```

Exports contain `primitive_bank.json`, `seed_candidates.json`,
`search_leaders.json` and a compact Markdown bank. Seeds bind genotype, source
revision/runtime, validation score, data split, spent source budget and target
translation instructions. Compatibility is declared for Prism, Topograph and
Stratograph; native ingestion and transfer benefit remain Phase 5 work.

`inspect` reconstructs missing local bank views from verified export-bound
`best_results.json` and `trial_records.json`; changed reconstruction inputs fail.
Family leaders retain each benchmark representative instead of ranking
incompatible metric scales. Runs cap 256 proposals / 1,800 seconds; NumPy
results remain portability-only.
