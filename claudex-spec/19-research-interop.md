# 19 — Research Interop: Consuming the claude-spec Platform

## 1. Relationship model

The claude-spec research platform ("the Lab") and this product develop in
parallel and independently. The Lab optimizes for comparative research
velocity; the product optimizes for validated deployable models. Neither
system imports the other's code. They interoperate exclusively through
versioned, typed, digest-addressed artifacts under the consumer-driven
contract defined here.

This chapter is the product-side authority for what may be imported, how it
is validated, and when an imported idea may change product behavior. The
Lab-side obligations are specified in `claude-spec/19-product-interop.md`;
the two documents cross-reference but this one governs acceptance.

INTEROP-001: Ideas, mechanisms, engines, benchmarks, seeds, and evidence
MUST enter the product only through the typed channels in this chapter.
Source-code import from the Lab repository MUST NOT occur.

INTEROP-002: Every import MUST be represented by an **import dossier**
recording the Lab specification version, source git commit, artifact
digests, and evidence references. Undocumented imports are prohibited.

INTEROP-003: Lab evidence is prior information only. No imported idea may
reach `adopted` status or change default product behavior without
decision-grade revalidation inside the product's own evaluation harness
(product splits, budgets, backends, and leakage protections).

Rationale for INTEROP-003: the Lab's fairness model is comparative (budget
parity, contender floors); the product's fairness model is statistical
(physical test isolation, contamination, governed splits). Lab results are
produced without the product's leakage protections and therefore carry the
evidential weight of `declared_overlap` prior knowledge, never of native
confirmatory evidence.

## 2. Import channels

### IC-1 — Benchmarks and packs

Lab benchmark definitions and packs MAY be imported as product benchmark
descriptors.

- Identity crosses the boundary through a versioned **canonical ID mapping
  registry**. INTEROP-004: an unmapped Lab benchmark ID MUST fail closed.
- Imported benchmarks MUST pass the product's own dataset governance
  (descriptor, digest, license, split artifact, leakage checks) before any
  decision-grade use. Lab admission (`benchmark-audit`) is advisory input,
  not product admission.
- Ladder-tier metadata (A–E) maps to pack `admission_purpose` and
  `supported claim type`.

### IC-2 — Seeds and motifs

Lab seed artifacts (Primordia seed candidates, motif banks, Stratograph
cell/motif exports) MAY be imported as typed transfer artifacts consumed by
eligible engines.

- The Lab seed-artifact contract (`claude-spec` ch. 11) is accepted as the
  minimum schema; the product converter maps it onto the product transfer
  artifact with `prior_cost_class` preserved (`free_prior` |
  `reported_prior` | `charged_prior`; Lab-external assets map to
  `external_pretraining`).
- INTEROP-005: converters MUST be versioned, MUST label lossy fields, and
  MUST carry golden-fixture tests in both directions.
- Contamination: a seed discovered on a Lab benchmark that maps to a
  benchmark used in a product claim is `declared_overlap` for that claim
  and follows the pack's overlap policy. A seed derived from any
  product-protected validation/test data is ineligible.

### IC-3 — Mechanisms

A **mechanism** is a transferable search or training idea without code:
e.g. regression target calibration, task/dimension-aware seed profiles,
phase-based mutation scheduling, family-aware budget allocation.

- Mechanisms are imported as dossiers (§3) and reimplemented natively under
  product contracts by the owning engine team.
- The dossier MUST state the claimed effect, magnitude, scope
  (tasks/modalities/budgets), and the Lab evidence labels supporting it.
- Reimplementation MUST follow the product's compatibility discipline:
  default off or better-default with prior behavior restorable.

### IC-4 — Engines

A Lab engine lineage MAY graduate into a new portfolio strategy branch.

- The engine MUST implement the engine adapter protocol
  (`describe_capabilities` … `finalize`) and pass adapter conformance.
- It enters the portfolio as `experimental` and is subject to portfolio
  governance; INTEROP-006: its status changes MUST cite product-native
  promoted evidence, not Lab standings.
- Its Lab role label (reference/challenger/specialist/seed_source) is
  recorded as prior information in the dossier.

### IC-5 — Evidence and priors

Rows from the Lab's promoted evidence registry MAY be imported as
**foreign priors** for the portfolio planner.

- Foreign priors MAY influence initial budget allocation, probe ordering,
  and eligibility hints.
- Foreign priors MUST NOT appear in product leaderboards, recommendation
  rationales as native evidence, or any decision-grade claim. They are
  displayed, when shown, with explicit foreign provenance.

### IC-6 — Protocols and gates

Lab methodology artifacts (decision-gate categories, ladder semantics,
statistical protocols) MAY be adopted by specification amendment. They
follow the normal specification change process, with the dossier as the
motivating record.

## 3. Import dossier

One dossier per import, schema-validated, stored in the interop registry:

- `dossier_id`, created timestamp, author;
- `channel`: IC-1 … IC-6;
- `source`: Lab spec version, git commit, artifact digests, evidence
  registry labels, case/run IDs;
- `claim`: one-paragraph statement of the idea and its claimed effect;
- `expected_effect`: metric, direction, magnitude, scope;
- `lab_evidence_grade`: seeds/budgets/lane states behind the claim;
- `risks`: known failure modes, negative results, scope limits (Lab
  negative results MUST be carried, e.g. "broad exploitation slot was
  tried and removed");
- `license_and_provenance`;
- `validation_plan`: the product gates that must pass for adoption;
- `status` (§4) and decision record.

## 4. Trust ladder

Imported ideas move through an explicit status ladder:

`observed → imported → revalidating → adopted | rejected | stale`

- **observed** — noted in the Lab, no product action.
- **imported** — dossier accepted and schema-valid; artifact converted; no
  behavior change.
- **revalidating** — running the validation plan inside the product
  harness as `experimental`.
- **adopted** — product-native decision-grade evidence supports the claim;
  default behavior or portfolio status may change, citing that evidence.
- **rejected** — revalidation failed or was inconclusive after the planned
  attempts; the dossier records why, and a reverse dossier (§6) informs
  the Lab.
- **stale** — INTEROP-007: automatically applied when the upstream source
  version/commit range becomes incompatible or the Lab supersedes the
  evidence; stale dossiers must be re-imported to proceed.

INTEROP-008: rejected and stale outcomes MUST be recorded, not deleted;
failed adoption is evidence.

## 5. Schema alignment

The boundary depends on a small stable shared core. The mapping is
maintained as a versioned conformance document with golden tests.

| Lab concept (claude-spec) | Product concept (claudex-spec) |
|---|---|
| canonical benchmark ID | benchmark descriptor via mapping registry |
| `manifest.json` / `results.json` / `summary.json` | `EvaluationArtifact` (converted, loss-labeled) |
| outcome `ok / failed / skipped / unsupported` | attempt outcomes (same names) |
| `partial_run` with valid work | `budget_exhausted_valid` |
| `invalid_evaluations` | `invalid` |
| budget fields (`evaluation_count`, `actual/cached/failed/invalid`) | budget envelope declared/observed counters |
| seeding fields (`seeding_ladder`, `seed_source_*`, overlap policy) | transfer artifact + prior-cost + contamination fields |
| prior-cost `free/reported/charged` | same, plus `external_pretraining` |
| evidence registry row | foreign-prior record |
| lane states (`contract-fair`…`trusted-extended`) | `lab_evidence_grade` metadata |
| engine portfolio roles | prior role hint in engine dossier |

INTEROP-009: the interop registry (dossiers, mappings, converter versions,
statuses) is append-only and auditable, following the same immutability
rules as the evidence registry.

## 6. Reverse channel (product → Lab)

Interop is bidirectional but asymmetric. The product SHOULD export back to
the Lab, as lightweight reverse dossiers:

- defect findings in shared mechanisms (the "Fix"-list class: RNG seeding,
  checkpoint atomicity, measurement proxies);
- backend qualification results (operator parity, determinism classes)
  that improve the Lab's portability truth;
- statistical protocol improvements;
- failed-adoption reports, so the Lab learns which of its wins did not
  survive product-grade validation — this is among the most valuable
  signals the product can return.

The Lab ingests these through its backlog process; nothing in this section
gives the product authority over Lab internals.

## 7. Worked example

Lab finding: *task/dimension-aware tabular seed profiles improve
Stratograph on high-dimensional tabular benchmarks* (Lab evidence:
repeated Tier C cohorts, seeds 42/43/44).

1. Dossier created (IC-3 mechanism): claim, magnitude, scope = tabular,
   Lab labels cited, risk noted (image/synthetic unaffected; exploitation
   variant known-harmful). Status `imported`.
2. Hierarchy-engine branch reimplements seed profiles natively, default
   off. Status `revalidating`; runs the validation plan on product
   benchmarks with governed splits at two budgets, paired seeds.
3. Product evidence shows a decision-grade gain on tabular tasks →
   `adopted`; profiles become default-on for tabular; portfolio planner
   prior updated; dossier cites the product evidence.
4. Had it failed: `rejected`, reverse dossier to the Lab with the product
   conditions under which the effect vanished.

## 8. Requirements summary

| ID | Requirement |
|---|---|
| INTEROP-001 | Typed channels only; no code imports from the Lab. |
| INTEROP-002 | Every import has a dossier with source version, commit, digests, evidence refs. |
| INTEROP-003 | Lab evidence is prior only; adoption requires product-native decision-grade revalidation. |
| INTEROP-004 | Canonical ID mapping registry is versioned; unmapped IDs fail closed. |
| INTEROP-005 | Converters are versioned, loss-labeled, golden-tested. |
| INTEROP-006 | Imported engines/mechanisms enter as `experimental`; status changes cite product evidence. |
| INTEROP-007 | Upstream incompatibility marks dossiers stale automatically. |
| INTEROP-008 | Rejected/stale outcomes are recorded and fed back upstream. |
| INTEROP-009 | The interop registry is append-only and auditable. |
