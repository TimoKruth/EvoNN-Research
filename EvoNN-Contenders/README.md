# EvoNN-Contenders

Fixed CPU baseline pools with bounded subprocess fits and the shared export
contract. Required scikit-learn models cover tabular, synthetic and flattened
image tasks; n-gram models cover language-model fixtures. Optional `boosted`
and `torch` extras are never required and missing pressure is explicit.

From the workspace root:

```bash
uv sync --all-packages --group dev --locked
uv run evonn-contenders run --official-lane smoke --seed 42 \
  --output .artifacts/contenders --cache .artifacts/dataset-cache \
  --timeout 1200 --fit-timeout 180
```

`run` also accepts `--pack`, `--budget`, `--pools` and `--enhanced`. Official
lane configurations resolve shared pack names; a missing future pack is an
error. The eight runtime loaders reproduce pinned legacy source, split and
dtype semantics. Their additive runtime manifest preserves the frozen
`planned` catalog snapshot. Actual consumed cache bytes are checksum-verified.

Each started fit/evaluation consumes one evaluation, including failed fits.
Invalid parameters and optional skips do not. Seeds, CPU placement and thread
limits belong to the protocol; model configuration cannot override them.
Dataset loading, optional dependency probing and fits run in bounded child
processes. Export finalization follows the execution deadline.

A canonical run contains configuration, state, diagnostic summary, report,
`metrics.duckdb`, attempt logs and checkpoint directory. `symbiosis/` is the
portable three-document export with checksum-bound evidence and the best
serialized model per benchmark. Compare never loads serialized models.
Per-attempt telemetry reports the actual model backend/version, fit duration,
serialized size and isolated process peak memory; absent measurements stay
unavailable. Run IDs are unique; existing evidence is never overwritten.

Smoke @16 does not cover all 25 canonical minimum floors. Scientific or lane
qualification requires separate Compare audit and repeated evidence. See the
[project plan](../CONSOLIDATED_PLAN.md) for current phase status.
