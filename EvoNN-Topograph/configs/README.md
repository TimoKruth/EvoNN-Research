# Topograph configurations

- `mixer.yaml`: exact confirmed mixer policy, selected for the September 29
  all-engine comparison. Native CPU, 128 fits. Retains the known delayed-copy
  limitation; use `research_next.yaml` or an explicit control for comparisons.
- `tiny_smoke.yaml`: bounded mixer runtime preset.
- `research_open.yaml`: earlier experimental search policies.
- `research_next.yaml`: opt-in compact temporal models and independently switchable
  training, search and regularization hypotheses.

Run with `uv run evonn-topograph run --config <path>`. Generate editable run and
all-five-system campaign arms with
`uv run python -m topograph.experiments --output <fresh-directory>`.
New configs without a variant default to mixer. Select `--preset legacy` for
legacy runs; resume restores the saved policy. Experimental inputs do not grant
scientific qualification.
See [options and limits](../../README.md#topograph-research-modes) and the
[execution plan](../../CONSOLIDATED_PLAN.md).
