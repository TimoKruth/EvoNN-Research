# EvoNN Topograph

See the central [capability table](../README.md#current-capabilities) and
[execution plan](../CONSOLIDATED_PLAN.md) for this package’s current scope.
Run `scripts/ci/topograph-checks.sh` from the repository root.

The Phase 4 text path predicts one next byte from a fixed preceding context.
A one-hot context feeds the trainable quantized DAG; all context tokens precede
the scored target. Replay recomputes perplexity. This is a window-conditioned
DAG, not a per-position causal Transformer implementation.
