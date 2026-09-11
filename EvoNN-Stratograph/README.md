# EvoNN Stratograph

Crossover-first macrographs route through reusable cell graphs. Search can clone,
specialize, grow, prune, rewire and reuse successful cell programs. Task profiles,
bounded niches and lineage are checkpointed. Each package owns its compiler and
runtime; [duplication notes](DUPLICATION_NOTES.md) explain common numerical code.

The legacy evaluator is `hierarchy_features_trained_head`: deterministic cell
projections plus a trained GELU head. MLX trains that head; this does not establish
end-to-end learned hierarchy sharing or transfer performance.

```sh
uv run --package evonn-stratograph evonn-stratograph run --config EvoNN-Stratograph/configs/smoke.yaml
uv run --package evonn-stratograph evonn-stratograph run --pack tier1_core --budget 64 --backend mlx_native --variant shared
uv run --package evonn-stratograph evonn-stratograph run --resume <run-directory>
uv run --package evonn-stratograph evonn-stratograph replay <run-directory>
uv run --package evonn-stratograph evonn-stratograph motifs analyze <run-directory>
uv run --package evonn-stratograph evonn-stratograph ablate --pack tier_a_contract --budget 16 --seeds 42 --backend mlx_native --timeout 1800
```

The five variants are `shared`, `flat`, `unshared`, `no-clone` and
`no-motif-bias`. Compare them at identical pack, budget, seed and runtime; keep
variant metadata. `ablate-matrix --budgets 16 64 --seeds 42 43` uses the same
five variants; `--timeout` caps the entire batch at 30 minutes. Each batch keeps
a resumable-run directory and a verified `ablation.json` index; incomplete
batches retain their completed exports and never claim a full comparison.
`motif_analysis.json` contains winner-conditioned programs,
structural descriptors and lineage. `lm_diagnostics.json` keeps proxy/flatline
limitations explicit. Both artifacts are checksum-bound and semantically checked.

Runs cap 256 proposals and 1,800 seconds. NumPy is portability-only; the large
five-system repeated Tier-B campaign remains a separate authorized decision.

## Explicit version 2 research execution

The breadth-preserving upgrade is implemented and opt-in. Existing configurations
without `research` keep v1 genomes, projection functions, search and training
allocation. Historical saved winners remain replayable. Resuming a run still
requires its unchanged producer; replay compatibility does not waive source-drift
checks or authorize resuming an old run on new code.

```sh
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/research_v2.yaml
uv run evonn-stratograph run --config EvoNN-Stratograph/configs/trainable_v2.yaml
uv run evonn-stratograph run --pack tier1_core_smoke --budget 16 \
  --research '{"version":2,"evaluator":"trainable","normalization":"rms"}'
```

The presets use NumPy portability execution. Select `--backend mlx_native` for
native execution on Apple Silicon. These commands perform bounded research fits;
passing them establishes execution, not scientific superiority. All existing
256-proposal, 30-minute, per-fit, model-publication and weight-cache limits remain.

`research` is an explicit portable policy, stored in configuration, checkpoint and
comparison fingerprints. CLI JSON and YAML accept the same fields. `--resume`
restores it and rejects explicit mismatches. The evaluator is fixed per run:

| Setting | Choices and meaning |
| --- | --- |
| `evaluator` | `proxy`: fixed projections with a trained head, fidelity `hierarchy_features_trained_head_v2`; `trainable`: shared differentiable cell matrices and head, fidelity `end_to_end_hierarchy_v2` |
| `normalization` | `train_standard` (default): per-channel statistics fitted only on training inputs; `rms`: differentiable per-example/per-token channel RMS; `none`: retained experimental alternative |
| `readout` | `final`, `all` macro outputs, or `input_final` concatenation |
| `residual` | Optional input-preserving cell paths where dimensions match; projected adapters otherwise |
| `head_width` | Initial head width, 4–64 |
| `evolve_representation` | Default true: normalization, readout, residual paths and head width can evolve; false freezes them for controlled ablations |
| `inheritance` | `compatible` (default): copy matching projection identities and only representation-compatible heads; `fresh`: no inheritance; `head_diagnostic`: permit same-shape head copying across representations for a controlled diagnostic |
| `selection` | `diverse` (default): protected rotating exploration/revisit slots; `quality`: explicit control ablation |
| `screen_epochs` | Default 0 gives every fit the full configured epochs; positive values screen offspring, with full allocation for archive revisits. Must not exceed `epochs`. |
| `archive_size` | 8–128, default 32; bounded niche and reservoir capacity |
| `max_macro_nodes`, `max_cell_nodes`, `max_width` | Explicit execution envelope within the current codec's 8 macro nodes, 6 nodes per cell and width 64 |

For `train_standard`, statistics are fitted for a fresh representation using
the current hierarchy and training data, then held fixed during optimization and
saved in `hierarchy_standard_v2` buffers. In trainable execution these are initial
feature statistics, not continuously updated estimates. Compatible inheritance
retains these buffers within the same dataset/split namespace so a learned clone
preserves the parent function. RMS normalization remains
an alternative. Inference never fits statistics to validation, test or batch data.

Projection seeds live on nodes. Activation changes preserve unrelated matrices;
`projection-randomize` is a separate operator. Learned clones receive independent
parameter arrays initialized from compatible parent arrays. Shared calls reference
the same parameters and aggregate their gradients. Mutated feature representations
receive fresh heads under compatible inheritance. V2 never reduces epochs merely
because weights were inherited, and it allows the entire allocated epoch window
without the legacy early-stop patience cutoff.

Shared search seeds both one-node and deeper macrographs. It can expand, contract,
collapse, add/remove edges, clone, specialize, share, change primitives, randomize
projections, grow/prune cells, adjust all integer widths in the envelope, and
change optimization settings. Reproduction includes mutation-only offspring.
The variant exclusions remain explicit ablation controls, not conclusions about
which architecture families are worthwhile.

Diverse selection rotates through quality, niche, novelty, fresh, quality,
random revisit, niche, uncertain revisit, fresh, novelty, promising revisit and
reservoir-parent slots. The cycle continues across generations and resumes;
short budgets may end before every slot has executed. Uncertain revisits use low
observation count as a sampling proxy, not a calibrated uncertainty estimate.
Novelty uses normalized prediction signatures on training examples. Niche eviction
is independent of absolute quality, and a bounded reservoir retains low-scoring
candidates. Archived candidates can reproduce or receive another charged fit.
Every revisit is a new fit with its own initialization stream and accounting;
inherited training is not a free evaluation or a pristine from-scratch replicate.

`research_diagnostics.json` records actual selection counts, reachable structures,
optimizer updates, measured training seconds, repeat outcomes and observed
screen/full ranking reversals. Insufficient repeated pairs remain unavailable.
The export consumer reconstructs these diagnostics from the attempt ledger.
Winner-conditioned motifs remain separately labeled; reproduction can draw cell
programs from the broader archive pool.

The primitive registry in `src/stratograph/operators.py` exposes pure,
shape-preserving, causal differentiable programs. Every registered name is
available to primitive mutation and fresh cell growth. `identity` bypasses the
activation after projection; it is not an identity of the whole cell. Adding a
primitive requires explicit source/version changes and tests for shapes,
gradients, causality and replay; dynamic registrations must also exist in worker
source. New operations are never inferred to be impossible merely because they
are absent from today's codec. Larger resource envelopes require a versioned
codec/runtime extension and new qualification, not edits to frozen evidence.

## Scientific breadth and qualification

Weak performance changes sampling priority; it does not permanently remove a
supported primitive or architecture family. Keep the exploration allocation,
archive revisitation and extensible grammar. Maintain executable validity and
resource bounds, record failures, and retain negative evidence with its context.
Finite runs cannot guarantee visiting every supported possibility.

For a campaign, set `stratograph_research` in the Compare campaign specification
to the same policy object. Research campaigns require Prism, Topograph,
Stratograph, Primordia and Contenders on every declared combination. Plan separate
matched all-engine reference and intervention campaigns; retain the original
Stratograph producer/results. Freeze `evolve_representation: false` to isolate
normalization/readout interventions, and compare `inheritance: fresh` against
`compatible` at identical allocations. Qualify the trained hierarchy separately
from the proxy, then test combined policies on fresh seeds. Existing protected
splits stay reserved for the separately frozen generalization protocol.
