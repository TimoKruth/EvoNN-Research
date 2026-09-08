Describe the problem and resulting behavior, then the relevant validation.

Engine-advancement PRs require exactly one `evonn-evidence` JSON block, validated
by `evonn-compare evidence decision-gate --registry evidence --body <body.md>`.
Use the registered before/after analysis request and exact run/case IDs; include
workspace paths, canonical registry report/dashboard paths, comparison labels,
all five named dashboard slices, pack/budget/seeds, the operating/accounting/
repeatability states and the single recomputed decision category. The field
contract is `evonn_compare.decision_gate.EvidenceBlock`.

Ordinary infrastructure/documentation PRs need their relevant tests. A registry
citation still requires current artifact validation. No statistical performance
claim follows from a passing implementation test.
