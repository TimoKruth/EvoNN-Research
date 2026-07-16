# 01 — System Architecture

## Shape: An Umbrella Monorepo, Not A Merged Runtime

EvoNN is a single git repository organized as a **uv workspace** with one
package per system. It is intentionally an umbrella research stack: packages
share contracts and infrastructure, never search cores.

```
EvoNN/                          # repo root = uv workspace root
├── pyproject.toml              # [tool.uv.workspace] members
├── uv.lock                     # single workspace lock
├── shared-benchmarks/          # benchmark source of truth (data + YAML, not a python package)
│   ├── catalog/                # benchmark YAML definitions
│   ├── suites/                 # suite/pack YAMLs (parity packs under suites/parity/)
│   ├── lm_cache/               # language-modeling dataset caches
│   └── migration/              # normalization/cutover notes
├── EvoNN-Shared/               # python package `evonn_shared`
├── EvoNN-Compare/              # python package `evonn_compare`
├── EvoNN-Contenders/           # python package `evonn_contenders`
├── EvoNN-Prism/                # python package `prism`
├── EvoNN-Topograph/            # python package `topograph`
├── EvoNN-Stratograph/          # python package `stratograph`
├── EvoNN-Primordia/            # python package `evonn_primordia`
├── evidence/                   # promoted evidence registry (ch. 12)
├── scripts/ci/                 # per-package check scripts used locally and in CI
├── .github/workflows/          # Linux trust-lane CI + macOS engine CI
└── docs (root)                 # VISION, plans, contracts (ch. 18 documentation policy)
```

Each package keeps its own `pyproject.toml`, `src/` layout, `tests/`,
`configs/`, and README. The workspace lock lives at the root. All commands run
from the root via `uv run --package <name> …`.

## Package Roles And Allowed Dependencies

```
                    ┌────────────────────┐
                    │  shared-benchmarks │   (data/YAML only)
                    └─────────▲──────────┘
                              │ reads
        ┌─────────────────────┼──────────────────────────┐
        │                     │                          │
┌───────┴───────┐    ┌────────┴────────┐        ┌────────┴────────┐
│  EvoNN-Shared │◄───┤  four engines   │        │ EvoNN-Contenders│
│  (contracts)  │    │ Prism/Topograph/│        │  (baseline zoo) │
└───────▲───────┘    │ Stratograph/    │        └────────▲────────┘
        │            │ Primordia       │                 │
        │            └────────▲────────┘                 │
        │                     │ exports (files, not imports)
        │            ┌────────┴─────────────────────────┐
        └────────────┤           EvoNN-Compare          │
                     │ (orchestration, trust, evidence) │
                     └──────────────────────────────────┘
```

Dependency rules:

- Engines MAY depend on `evonn_shared` and read `shared-benchmarks/`.
- Engines MUST NOT import each other's runtime, compiler, genome, benchmark
  loaders, or export logic. Comparison happens through exported files
  (`manifest.json`, `results.json`, `summary.json`), never through imports.
- Compare MAY invoke engine CLIs and read their exports; it MUST NOT import
  engine search internals.
- Contenders MUST use the same export contract as the engines and MUST NOT
  become a second general framework.
- `evonn_shared` MUST stay dependency-light and engine-agnostic. Its
  non-goals are explicit: no search logic, no genome definitions, no
  engine-specific runtime/compiler code, no mutation/crossover operators.

## Structural Unification Policy

Unify infrastructure where sameness improves trust, parity, and maintenance;
preserve search-core differences where distinctness is the scientific point.

Belongs in the shared substrate (Shared and/or shared-benchmarks):

- benchmark catalog and parity-pack resolution helpers (one shared path
  beneath package-local `get_benchmark` / `list_benchmarks` /
  `resolve_pack_path` / `load_parity_pack` wrappers)
- compare/export contract models; manifest assembly; common `summary.json`
  fields; runtime-metadata defaults; JSON writers
- normalized budget metadata models and run-identity helpers
- telemetry envelope models and seeding-metadata validation
- real-LM cache validation
- report-generation helpers: markdown safety, runtime/budget sections,
  failure-pattern aggregation, compare-facing summary rendering
- run-storage primitives: common `RunStore`/DuckDB schema layers for runs,
  evaluations, artifacts, metadata
- recurring CLI helper patterns (`benchmarks`, `inspect`, export/report)
- **narrow** training preprocessing that is provably not search policy —
  e.g. generic regression target scaling and final affine calibration
  (`evonn_shared.training`)

MUST stay package-local:

- genome and candidate representations
- mutation and crossover logic
- compiler/runtime implementations
- search-loop coordinators and selection pressure
- optimizer/search-policy choices
- abstraction-specific telemetry above the common minimum floor

## The Standalone Rule

Every engine MUST be runnable on its own when given explicit benchmark data,
shared benchmark definitions, or documented pack inputs. Shared substrate is
fine; hidden dependence on sibling package internals is not.

Corollary (**the Primordia lesson**): deliberate duplication is preferred over
accidental coupling. When independence matters more than DRY, copy code into
the package, record the duplication in a dedicated notes file (what was
copied, from where, why), and accept the maintenance cost knowingly. Do not
silently re-couple a package to siblings after independence was chosen.

## Intentional Engine-Specific Branches In Compare

Even after substrate convergence, Compare keeps a small set of per-engine
branches on purpose:

- benchmark/module resolution (engines own native identifiers and loaders)
- config generation and command invocation (different CLIs and prerequisites)
- portable smoke exporters carrying small system-local fields that describe a
  real runtime difference

Debt to eliminate: any Compare-side branch that exists only because shared
contracts/helpers were not adopted yet, or special handling that changes
comparability semantics without reflecting a real engine/runtime difference.

## Technology Stack

| Concern | Choice | Notes |
|---|---|---|
| Language | Python ≥ 3.13 | one interpreter across the workspace |
| Package management | `uv` workspace | root lock; `uv sync --all-packages --extra dev` bootstraps |
| Neural runtime (truth path) | MLX | Apple Silicon native, unified memory |
| Portable runtime (fallback) | NumPy | Linux-capable smoke/regression/compare-grade validation (ch. 13) |
| Validation/config models | Pydantic 2 + YAML | all configs are validated models |
| Metrics storage | DuckDB, per-run | one `metrics.duckdb` per run directory; **never two writers on one file** |
| CLI | Typer | one CLI entry point per package |
| Testing | pytest + ruff | per-package `tests/`, per-package CI scripts |
| Optional baselines | scikit-learn (required floor); xgboost/lightgbm/catboost, torch (optional extras) | ch. 06 |
| Dashboards | static HTML+JSON (Compare); FastAPI+Jinja2+Chart.js (Observatory, ch. 15) | no frontend build step |

## Run Directory Convention

Every engine run gets its own directory (default under the package's `runs/`
or an explicitly passed `--run-dir`):

```
runs/<run_id>/
├── config.yaml            # snapshot of the resolved config
├── metrics.duckdb         # per-run metrics store
├── state.json             # resumable evolution state (engine-specific shape)
├── summary.json           # canonical machine-readable run summary
├── report.md              # human-readable report (rebuildable from artifacts)
├── checkpoints/           # model/weight checkpoints
└── (export)               # symbiosis export adds manifest.json + results.json
```

DuckDB lock policy: per-run DuckDB is mandatory for all new systems; parallel
runs are then safe by construction. Historical global DBs may exist for reads
only.

## Naming Conventions

- Packages: `EvoNN-<Name>` directories; import names as listed above.
- Benchmark-ladder packs: `tier_<letter>_*` (e.g. `tier_b_core_v2`).
- Legacy numeric compare lanes: `tier1_core`, `tier2_evonn_leaning`,
  `tier3_evonn2_leaning` — kept for the trusted recurring lane and symmetry
  classes; MUST NOT be mixed with lettered ladder names (never `tier2_core`).
- Cumulative one-shot packs: suffix `_cumulative`.
- Run classes: `smoke`, `local`, `overnight`, `weekend`, `special-study`.
- Branches: `agent/<issue>-<slug>` or `user/<issue>-<slug>` (ch. 18).
