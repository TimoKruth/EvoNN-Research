# Workspace consolidation — October 6, 2026

The cleanup inventory covers 41 obsolete external EvoNN checkouts. Forty were
retired to `.artifacts/retired-checkouts-20261006`; the JEPA checkout remains until
its retained commits are merged. Every archived checkout has a byte-verified
source snapshot, file hashes, original status and uncommitted patch. Standalone
repositories also have verified all-ref Git bundles; shared worktree history is
pinned under `refs/archive/cleanup-20261006/` and bundled in the archive root.
All benchmark outputs, failed attempts and historical evidence remain retained.
Only redundant root environments, tool caches and Git checkout metadata were
removed. Thirty archive links were repaired. Seven obsolete launchd jobs for
completed or blocked historical studies were unloaded and their definitions
archived. No historical training was resumed or declared complete by cleanup.

The substantive uncommitted Topograph mixer and Stratograph temporal/default,
study-controller, recovery and result work is committed in this integration.
The three previously unmerged JEPA commits are merged with their full history,
including the repeated exploratory analysis. JEPA stays opt-in and does not
change engine defaults. Prism finalization was merged independently in PR #43; this consolidation preserves
that implementation and its evidence.
The predecessor `Evo Neural Nets` and unrelated projects remain untouched.

The dirty September 11 validation checkouts are intermediate snapshots, not new
features to restore over current code. Final-check runtime files match current
or historical main blobs; earlier qualification snapshots preserve superseded
iterations. The unused v3 audit branch differs from the subsequently accepted
canonical freeze, so its exact proposal is archived without rewriting frozen
governance. The overnight script has an expired September 7 deadline and is
archived rather than reactivated. See [inventory and exact source hashes](inventory.json).

## Release contract

The exact before/after revisions run Prism, Topograph, Stratograph, Primordia and
Contenders on `tier_b_core_v2`, budget 16, seed 24606 and two epochs: ten completed
runs / 160 fits. After PR #43 merged, the refreshed registry retains all 68 main records and the
ten earlier consolidation records, then appends ten runs against the combined
revisions, for 88 records. The earlier release archives remain unchanged. The four-engine paired analysis is `contract_validation` and returns
**needs more seeds**. Operational defaults intentionally differ; this small
single-seed check cannot establish a scientific gain. Frozen study results and
their original limitations remain authoritative. The source declaration pins
both the registry snapshot and complete dependency transport by SHA-256 and size.

Recovery tests compare deterministic search state, ancestry, metrics and journal
tips while excluding independently measured `train_seconds` from exact equality.
Each exported timing ledger still passes the full evidence validator. Both CI
lanes execute the retained JEPA pilot and analysis integration tests.
