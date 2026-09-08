# EvoNN Stratograph

Crossover-first macrographs route through reusable cell graphs. Search can clone,
specialize, grow, prune, rewire and reuse successful cell programs. Task profiles,
bounded niches and lineage are checkpointed. Each package owns its compiler and
runtime; [duplication notes](DUPLICATION_NOTES.md) explain common numerical code.

The current evaluator is `hierarchy_features_trained_head`: deterministic cell
projections plus a trained GELU head. MLX trains that head; this does not establish
end-to-end learned hierarchy sharing or transfer performance.

```sh
uv run --package evonn-stratograph evonn-stratograph run --config EvoNN-Stratograph/configs/smoke.yaml
uv run --package evonn-stratograph evonn-stratograph run --pack tier1_core --budget 64 --backend mlx_native --variant shared
uv run --package evonn-stratograph evonn-stratograph run --resume <run-directory>
uv run --package evonn-stratograph evonn-stratograph replay <run-directory>
```

The five variants are `shared`, `flat`, `unshared`, `no-clone` and
`no-motif-bias`. Compare them at identical pack, budget, seed and runtime; keep
variant metadata. `motif_analysis.json` contains winner-conditioned programs,
structural descriptors and lineage. `lm_diagnostics.json` keeps proxy/flatline
limitations explicit. Both artifacts are checksum-bound and semantically checked.

Runs cap 256 proposals and 1,800 seconds. NumPy is portability-only; the large
five-system repeated Tier-B campaign remains a separate authorized decision.
