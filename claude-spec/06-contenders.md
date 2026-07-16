# 06 — Contenders: The Baseline Discipline Layer

`EvoNN-Contenders` maintains a configurable zoo of strong non-evolutionary
models and exports their results in the same comparison shape used
everywhere else. Its purpose is to keep the rest of EvoNN honest: if an
evolutionary system cannot beat serious fixed baselines on shared packs, the
result is informative even when disappointing.

Contenders is deliberately **not** a second general framework.

## Contender Groups

| Group | Required floor (dependency-light) | Optional enhanced pressure |
|---|---|---|
| `tabular` | tree ensembles, MLPs, logistic regression, SVM (scikit-learn) | `xgboost`, `lightgbm`, `catboost` (extra: `boosted`) |
| `synthetic` | strong subset of tabular contenders + SVM | boosted trees |
| `image` | flat-feature MLP / tree baselines | `cnn_small` (extra: `torch`) |
| `language_modeling` | n-gram baselines | `transformer_lm_tiny` (extra: `torch`) |

Rules:

- **Required contenders MUST be dependency-light and reliable.** They install
  and run everywhere the trust lane runs (Linux CI included).
- **Optional enhanced contenders** may add pressure but can never be required
  for benchmark-complete status. When skipped (extras not installed), the
  export records the skip so Compare surfaces it in lane trust summaries —
  missing enhanced pressure is visible in claims, never silent.
- Contender pools are editable in YAML config; official lanes resolve
  benchmarks via `benchmark_pack.pack_name`, never hard-coded lists.
- Contender strength MUST NOT be reduced to make engines look better.

## Floor Adequacy Labels

Every benchmark carries a per-benchmark contender adequacy label, maintained
by audit tooling:

- `strong_floor` — enhanced-level pressure present and reproducible
- `acceptable_floor` — required floor adequate for decision-grade use
- `weak_floor` — floor exists but is not meaningful pressure; blocks
  decision-grade promotion
- `missing_enhanced_pressure` — required floor fine, but claims on this
  benchmark should note absent optional pressure

Every benchmark MUST have at least one required contender result before pack
promotion. EvoNN wins must be interpretable as wins over a reasonable floor.

## Budget Semantics

For contenders, one counted evaluation is one contender fit/eval pass per
contender in the fixed pool (declared via `evaluation_semantics`). Contender
results and evolutionary results disclose these different semantics; Compare
budget-matches at the envelope level and keeps the difference visible.

## Export And Lanes

Contenders exports the standard `manifest.json` + `results.json` +
`summary.json` (system = `contenders`). Official lane configs exist for at
least: smoke (`@16`), `tier1_core@64/256/1000`, `tier_b_core@256/1000`, and
each ladder lane the platform promotes.

## Growth Direction

Contenders should grow into a broad but controlled opponent set: classical
tabular; boosted trees; image; lightweight LM; sequence baselines; future
task-specific baselines for harder benchmark classes (Tier E admission will
demand them). Eventually it MAY host adapters that let sibling EvoNN systems
participate as normalized contender-style references under fixed mini-budgets
— normalized pressure, not a framework merger.

## Legacy External-Contender Harness (Resurrection Candidate)

The ancestral Track A validated against external NAS/AutoML systems —
Ray Tune, NNI, AutoGluon, TabPFN, XGBoost, LightGBM, FLAML — via an
equal-budget comparison harness (`compare <contender> --pack <p>
--trial-budget <n>`). This harness is worth resurrecting as an optional
Contenders extra once the internal floor is stable: external-tool pressure is
the strongest possible answer to "would a practitioner just use AutoGluon?".
Requirements if resurrected: equal-budget protocol, same export contract,
optional heavy dependencies isolated behind extras, results labeled as a
separate external-pressure lane.
