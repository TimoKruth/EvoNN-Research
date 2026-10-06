# Stratograph temporal research implementation — September 21

The September 16 qualification is the motivation, not evidence for the new
implementation. Its trained v2 Stratograph reaches mean digits accuracy 97.92%
and diabetes MSE 2684.8 at core@256, while delayed-copy perplexities of 9.122 and
5.610 expose a temporal weakness. The 28/30 comparison remains incomplete, and
its historical producer, results and missing Primordia slots remain unchanged.
See [the original findings](../qualification-20260916/findings.md).

## Implemented alternatives

An explicit v3 execution policy adds learned causal attention with relative-lag
bias, dilated depthwise convolution, and a learned hybrid. Token embeddings use
direct differentiable lookups. Independent switches cover cell RMS normalization,
gated residual paths, learned graph merges, linear readout, dropout, initial
checkpoint selection and selective weight decay. Representation-aware niches
and optional temporal/representation mutation retain protected exploration.
Shared calls share all parameters; clones receive independent compatible copies.
Partial inheritance retains compatible embeddings and resets incompatible heads.

The eleven named presets include an exact v2 control, temporal-only arms,
stabilized prefix, combined alternatives, fresh-initialization and dropout
controls, and an evolving policy. The Compare configuration generator emits
separate full-roster specifications, requires explicit packs/budgets/seeds, and
does not launch or freeze a campaign. All existing resource caps remain binding.
See [settings and commands](../../EvoNN-Stratograph/README.md#version-3-temporal-research).

## Validation scope

**980 targeted tests passed:** 99 Stratograph/preset/import-boundary tests and
881 shared/campaign tests. The [validation receipt](validation.json) binds the
source hashes; [Stratograph logs](stratograph-tests.txt) and
[shared/campaign logs](shared-campaign-tests.txt) retain the final summaries.
Ruff, the repository import audit and `uv lock --check` also passed.

The accompanying validation receipt and test logs record the final checks against
a fixed local source snapshot. That snapshot avoids interference from simultaneous
changes to other engines in the shared workspace. An earlier workspace-wide
legacy resume test correctly rejected a changing source fingerprint; its failed
attempts were not treated as completed execution evidence.

Tests cover finite-difference gradients on NumPy and MLX, causal prefixes under
future-token perturbations, explicit distant-lag selection, learned synthetic
distant-token recall, clone and partial inheritance, v2 numerical equivalence,
search mutation, initial-checkpoint retention, policy roundtrips, complete
process-isolated fits, forced crash/resume, portable export validation, tamper
rejection and saved-winner replay. V3 runtime tests execute 24 charged fits per
backend over the four-task Tier-B core pack. These are implementation tests,
not an engine comparison or a scientific performance claim.

## Remaining evidence

No new scientific comparison was started. Select arms, check fresh seeds, freeze
the producer/protocol and run Prism, Topograph, Stratograph, Primordia and
Contenders on every declared combination. Preserve all failed slots and negative
results. Analyze delayed copy separately from real text; measure image/tabular
retention, fit-count costs and training time. V3 superiority, broader
generalization, speedups and transfer benefits remain unestablished.
