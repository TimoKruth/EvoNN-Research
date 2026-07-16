# 13 — Runtime Portability And Hardware Truth

Apple Silicon / MLX is the local-first truth path; Linux is required for CI,
portability, and independent validation. The hard part is preventing mixed
backend evidence from becoming misleading.

## Backend Model

| Capability class | Meaning |
|---|---|
| `mlx_native` | full MLX runtime; the scientific truth path for engine training claims |
| `numpy_fallback` | deterministic NumPy execution; smoke, regression, and compare-grade small-budget validation |
| `sklearn_contender` | contender fits via scikit-learn (always portable) |
| `torch_optional` | optional torch-based contenders (cnn_small, transformer_lm_tiny) |
| `unsupported` | declared, visible non-support |

Every engine declares its backend capabilities. Every run/export records the
backend actually used, backend version, device class, precision mode, and
worker topology (ch. 04 manifest runtime block). MLX is a
platform-conditional dependency so all packages install cleanly on non-Darwin
hosts.

## Portability Requirements

- Every engine MUST have a Linux-capable execution path good enough for
  smoke tests, regression tests, and compare-grade small-budget studies
  under the same benchmark packs and export contracts. Full scientific
  comparison must not depend on MLX being importable on the validation host.
- Search semantics survive backend change; numeric identity does not.
  **Reproducibility is defined as comparable evidence under shared budgets,
  not bitwise-identical floating point across platforms.**
- Audit engines for hidden MLX assumptions; backend detection is explicit.

## Honesty Rules For Mixed Backends

- Backend metadata is **required** for decision-grade artifacts.
- Dashboards filter by backend class and hardware fingerprint.
- Comparison cohorts warn when backend/hardware changes across budgets or
  seeds; backend drift between budgets must not silently create trend claims.
- Decision-grade claims MUST NOT mix MLX and fallback results unless
  explicitly classified as portability evidence.
- Linux fallback results are never presented as equivalent to MLX-native
  evidence.

## CI Matrix

Linux GitHub Actions — the **trusted recurring lane** (runs on every PR
touching shared surface):

| Lane role | Package → script |
|---|---|
| Core trust | `EvoNN-Shared` → `scripts/ci/shared-checks.sh`; `EvoNN-Compare` → `compare-checks.sh` |
| Challenger floor | `EvoNN-Contenders` → `contenders-checks.sh` |
| Secondary challengers | `EvoNN-Primordia` → `primordia-checks.sh`; `EvoNN-Stratograph` → `stratograph-checks.sh` |

macOS GitHub Actions — MLX truth paths:

- `EvoNN-Prism` → `prism-checks.sh`
- `EvoNN-Topograph` → `topograph-checks.sh`

Local review expectation: run the five Linux-safe scripts before PRs touching
shared substrate, docs, or trust-lane workflow; run the macOS package checks
when Prism/Topograph runtime behavior changes.

## Performance Work Under Portability

Candidate optimization areas (each via the baseline → one change → remeasure
→ accept/scrap loop, ch. 17 Workstream 6):

- MLX backend: batch candidate evaluation where shapes allow; reduce CPU/GPU
  transfer churn; cache compiled/evaluable graph fragments; shape bucketing
  for repeated structures; backend timing sections inside artifacts.
- NumPy fallback: vectorize evaluation hot paths; avoid repeated dataset
  conversion; shared evaluator cache; parallelize only at benchmark/system
  boundaries unless deterministic candidate-level parallelism is proven.
- Search-loop: early-reject structurally invalid candidates; multi-fidelity
  screening with honest budget labels; candidate deduplication with explicit
  cache accounting; archive-guided mutation to avoid repeated dead zones.
- Dashboard/reporting: precompute large aggregates; avoid re-reading full
  artifacts per dashboard open; compact index files for last-N views.

Per-branch measurement set: Tier A @ 16 & 64; Tier B @ 96 & 384; one Tier C
local run if compiler/evaluator/runtime logic changed; ≥2 seeds if search
behavior changed; backend metadata + host fingerprint. Metrics: wall-clock;
candidates evaluated; valid/invalid ratio; cache hit rate; backend vs
orchestration time; per-benchmark latency; peak memory; metric-quality delta;
contender-floor margin delta.
