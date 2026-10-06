# EvoNN Prism

See the central [capability table](../README.md#current-capabilities) and
[execution plan](../CONSOLIDATED_PLAN.md) for this package’s current scope.
Run `scripts/ci/prism-checks.sh` from the repository root.

Prism's experimental `open` policy adds archive reproduction, protected lineages,
coverage-aware training and mixed block composition. `--variant legacy` retains
the previous search/training policy. See the central
[Prism policy documentation](../README.md#prism-exploration-policies) for ablations,
initialization controls, optimizer choices and the read-only research report.

The opt-in [frontier experiments](../README.md#prism-frontier-experiments-september-21)
add separate search, representation, regularization, averaging and calibrated
selection variants; `frontier_v2` combines them. `open` remains the default.
Use `configs/frontier_research.yaml` as a run template or the documented all-system
specification generator to prepare later comparisons.

The completed confidence study motivates three additional hypotheses:
`routed_v3`, `lean_v3` and `aligned_v3`. They route by task kind, preserve the
original controls, and include accuracy-aligned classification checkpoint selection.
See the [results and implementation](../reports/prism-confidence-20260921/results-20261006.md)
and [run/compare commands](../README.md#prism-post-study-candidates-october-6).
Templates live in `configs/*_v3.yaml`. Default promotion awaits fresh confirmation.
