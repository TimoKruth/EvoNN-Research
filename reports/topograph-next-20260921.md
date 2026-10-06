# Topograph next implementation — September 21, 2026

Implemented experimental improvements and independent controls requested after the
latest comparison results. The default remains `legacy`; activate `next` explicitly.
No new comparative quality, generalization, speed or engine-promotion claim is made.

## Evidence motivating the changes

The [September 16 qualification findings](qualification-20260916/findings.md)
report Topograph core-128 → core-256 diabetes MSE 2845.3 → 2618.6 and Shakespeare
perplexity 18.546 → 17.146, accompanied by 3.68× recorded training time. The
regression improvement comes from one of two seeds. Topograph's selected language
artifacts are much larger than Prism's. These are selected validation observations,
not protected-test or causal evidence.

The later September 16 readiness qualification completed a separate 30/30 contract
matrix, with 480 fits and 96 native replays. It did not run the planned 60-run
language-baseline diagnostic or replace the historical 28/30 qualification. Its
local record is `.artifacts/follow-up-readiness-20260916/readiness.json`.
The previously landed checkpoint optimization is retained; this change focuses on
Topograph's model execution, training and search rather than changing checkpoint
integrity or frozen evidence.

## Implemented hypotheses

- **Final-query attention:** `token_query` uses the existing token-attention
  parameterization and computes its consumed final query only. Outputs and gradients
  agree on both backends. The attention matrix is linear in context length; the
  evolved DAG remains unchanged. This is an algebraic optimization, not a measured
  end-to-end speedup claim.
- **Positional mixer:** `token_mixer` learns head-specific distributions over
  historical positions and projected values, with a last-token residual. Its
  embedding, position, mixing and projection parameters receive gradients. This
  supplies a distinct temporal hypothesis for later delayed-copy/real-text testing.
- **Coverage of representations:** diverse founders rotate the compact adapters,
  original attention and flat input. Query-only, mixer-only and legacy-adapter
  switches are available; tabular/image adapter choices remain task compatible.
- **Progress-aware training:** recent selected validation improvement in the actual
  inherited source grants the full allowance; otherwise copied-fraction discounts
  apply. Full/coverage controls, protected allocations and explicit cold starts
  remain available. All fits and ancestral work stay charged and auditable.
- **Size-aware search:** within a species, select smaller models within a configurable
  quality tolerance. Local width/LR proposals, lower configurable branch-crossover
  probability and a configurable parameter cap limit uncontrolled model growth.
  Broad mutations, quality-only selection and the previous cap are separate controls.
- **Regularization and evaluation:** training-only label smoothing, matrix-only
  decay, configurable unprotected patience and bounded language validation batches.
  Export/replay use unsmoothed metrics. Nontext validation preserves full-batch
  semantics because its existing quantizer can depend on batch-wide ranges.
- **Attribution:** selected epoch including epoch zero, initial validation loss,
  training/validation curves, exact source-progress accounting, frozen policy in
  state/telemetry/exports, campaign adoption checks and separate policy fingerprints.
  Incompatible adapter changes do not inherit input projections or adapter weights.

At the same width-16 seed DAG on the 64-context Shakespeare definition, exact
parameter arithmetic gives flat **266,512**, original attention / final-query
attention **10,768**, and mixer **10,320** parameters. Original attention was
already compact; final-query attention reduces its execution work, not its parameter
count. These are constructed model sizes, not comparison winners or equal-quality
measurements. Stored FP32 size, packed estimates, peak memory and runtime remain
distinct quantities.

## Verification

- **102 tests passed** across the complete Topograph suite and Compare's Topograph
  policy tests, including NumPy and native MLX gradients/training, all existing
  operators, unchanged legacy identity/execution, deterministic search resume,
  no-inheritance controls, size-aware selection and generated-input validation.
- Six subprocess export checks completed **160 charged fits**, with **40 saved
  winner replays** (24 native / 16 portable). They include crash/resume and policy
  tamper rejection, plus separate native core exports for query and mixer adapters.
  These are contract tests, not an engine comparison.
- **219 integration/policy tests passed** across campaign handling, comparison,
  import-boundary validation and isolated worker imports. The final workspace
  import-boundary validator also passes.
- Ruff, lock consistency, installed package identity and whitespace checks pass
  for the modified Topograph/policy surfaces.

Runtime tests used immutable temporary source snapshots because other engine
implementations were being edited concurrently. Final verification isolates the
Topograph changes against the committed baseline; shared-policy validation remains
independent of Topograph’s runtime allocation implementation. Local logs and snapshot metadata
are in `.artifacts/topograph-next-20260921/`; source/test hashes are recorded in
`governance/topograph-next-implementation-20260921.json`. Hosted CI is not claimed.

## Comparing later

Run `uv run python -m topograph.experiments --output <fresh-directory>` to write
14 editable run/campaign arms: `open`, `next`, query, mixer, legacy adapters, full
training, coverage training, quality selection, broad mutation, cold starts, no
smoothing, all-parameter decay, wider cap and more crossover. These inputs do not
register or launch a study. Campaign templates include all four engines and
Contenders on every declared combination. Review seed disjointness, baseline
adequacy, bounded host feasibility and core/breadth coverage before freezing a
scientific protocol. Search trajectories can diverge after any intervention;
these are policy comparisons, not matched-finalist causal experiments.

Open questions include whether positional mixing generalizes, whether size-aware
selection gives useful measured-compute trade-offs, and whether smoothing or longer
allocation helps Topograph's real-text/regression outcomes. Optimizer moments
still reset per fit; no transfer proof, universal improvement or exhaustive search
of all possible architectures is asserted.
