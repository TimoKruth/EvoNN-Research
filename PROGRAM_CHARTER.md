# EvoNN Program Charter — Two Tracks, One Boundary

**Status:** Program charter — non-executable governance document
**Date:** 2026-07-17 (rev. 2, after claudex-side review)
**Sources:** `claude-spec/` (Lab), `claudex-spec/` (Product),
interop contract (`claude-spec/19` + `claudex-spec/19`)

This charter defines relationships, workstreams, boundaries, and program
gates. It is **not** an execution plan and creates no work packages. The
Lab's execution work lives in its single consolidated plan (seeded from
`LAB_PLAN.md`, per `claude-spec/18` documentation policy); the Product
repository will own its own execution plan. Where this charter and a
normative specification disagree, the specification wins.

## The Shape Of The Program

Two systems, developed **in parallel and independently**, connected only by
the versioned interop boundary:

- **Workstream A — the Lab** (claude-spec): the scientific research
  platform. The program's priority track: it starts first, carries most
  early effort, and delivers research value on its own.
- **Workstream B — the Product** (claudex-spec): the local model-building
  product, in its own repository. Its foundations (contracts, persistence,
  data governance, worker isolation) may proceed at any time; nothing in
  this charter blocks Product existence on Lab progress.
- **Workstream C — Interop**: a first-class cross-cutting workstream with
  its own deliverables and gates. What is gated is not Product work but
  **real Lab-derived influence on the Product**: real imports begin only
  when producer conformance (I1) and consumer conformance (I2) both pass.

```
Workstream A (Lab):      Phase 0 ─ 1 ─ 2 ─ 3 ─ 4 ─ 5 ─ 6 ─ 7 ─► continuous research
                                          │                └─ L-SCI (scientific conclusion)
Workstream C (Interop):  I0 ── I1 ── I2 ── I3 ── I4 (repeatable)
                                          ▲
Workstream B (Product):  Horizon 0 ─ 1 ─ 2 ─ 3 ─ 4 ─ 5 ─ 6 ─ 7 ─► P-V1
```

Rule of the program: **the boundary is the only coupling.** Either track can
pause, pivot, or refactor internally without breaking the other. No shared
runtime, no shared genome, no code imports across the boundary — ever.

---

## Workstream A — The Lab (claude-spec)

Phase structure is normative from `claude-spec/17` (Phases 0–7); this
charter does not re-cut it. Summary of the dependency chain:

0. Workspace and contracts
1. Contenders + Compare core
2. First two engines (Prism, Topograph)
3. Evidence registry and statistical decision layer
4. Stratograph + Primordia
5. Native transfer proof
6. Quality-diversity, portfolio decisions, tier hardening
7. Performance frontier, Observatory, scheduled automation loop

Charter-level additions to the Lab track:

- **Foundation Integrity Gate (in Phase 0, enforced before any trusted
  evidence):** tests exist and pass for named RNG stream derivation;
  uninterrupted-vs-resumed run equivalence; atomic, checksummed checkpoint
  publication; immutable canonical evaluation records; pure read-only
  export; honest distinction between measurements and proxies; and genuine
  speciation behavior wherever NEAT terminology is used. These are
  scientific-integrity requirements native to the Lab — the "no Lab
  redesign for Product convenience" rule below explicitly does not apply
  to them.
- **Gate L-SCI — Lab scientific conclusion** (separate from any interop
  gate): the contender floor is qualified and non-weak, and either at
  least one engine beats or ties it on a meaningful non-smoke subset under
  repeated evidence, or a promoted, evidence-backed negative conclusion
  explains why none does — with portfolio consequences recorded. L-SCI is
  the Lab's definition-of-done question (`claude-spec/17`); publishing
  readiness (I1) never substitutes for it.

After Phase 7 the Lab runs as a continuous research program; it never
"finishes."

---

## Workstream B — The Product (claudex-spec)

Horizon structure is normative from `claudex-spec/15` (Horizons 0–7); this
charter does not re-cut it, and in particular it does not defer to late
stages what the roadmap places early: worker isolation and cancellation are
Horizon 0; dataset Web/CLI flows and hostile-archive defenses are
Horizon 1; live Web job monitoring and the full CLI flow are Horizon 3;
accessibility, security review, fault injection, and release qualification
are the Horizon 7 hardening phase.

Charter-level clarifications:

- **v1 means full conformance.** claudex v1 is exactly the complete core
  contract, charter problem surface, mandatory strategy branches, and
  conformance matrix of `claudex-spec` (README §core contract, 00-charter,
  18-v1-conformance-matrix). No program gate may shrink it. Program gates
  control **ordering and timing only**.
- **The early narrow slice is a technical preview (v0.x), not v1.** As a
  program decision (recorded here, not attributed to prior consensus), the
  first end-to-end vertical slice targets **tabular + image**: they have
  the strongest existing Lab benchmark coverage and contender floors, the
  cheapest local fixtures, and they exercise both classical and neural
  paths. Evidence that would change this selection: a primary user need in
  another modality, or a spike showing the bundle/verification path is
  better proven elsewhere. Text and time-series remain part of the
  automatic-portfolio milestone (Horizon 3) per the unchanged normative
  roadmap.
- **Selection semantics are never blurred.** The product produces a
  recommendation and feasible candidate set; the user explicitly selects
  or records an override; finalization and confirmatory evaluation run as
  auditable jobs; export then performs read-only materialization and
  independent verification.
- **Runtime qualification is evidence, not CI green.** Decision-grade
  Linux, qualified backends, deterministic materialization, and capability
  metadata are proven per `claudex-spec/09`, not inferred from successful
  imports.

---

## Workstream C — Interop

A concrete workstream with deliverables on both sides, governed by the
ch. 19 pair. Channels IC-1…IC-6 (benchmarks, seeds/motifs, mechanisms,
engines, evidence-as-priors, protocols); full trust ladder
`observed → imported → revalidating → adopted | rejected | stale` with
automatic staleness; retained rejected/stale records; append-only interop
registry.

Deliverables:

1. Export-contract versions and changelogs (Lab)
2. Mechanism-dossier schema, validator, and worked examples (Lab)
3. Canonical-ID mapping registry, fail-closed (both)
4. Versioned converters with loss reports (Product)
5. Golden fixtures — valid, invalid, corrupt, and old-version — exercised
   bidirectionally (both)
6. Append-only interop registry (Product)
7. Trust-ladder and automatic-staleness machinery (Product)
8. Reverse-dossier generation (Product) and backlog ingestion (Lab)
9. INTEROP traceability and acceptance evidence (Product — the INTEROP
   family in `claudex-spec/schemas/traceability.yaml` currently has no
   acceptance IDs; assigning them is a prerequisite for I2)

Fixtures and real artifacts are both required and test different things:
golden fixtures prove deterministic contract behavior, old-version
compatibility, corruption rejection, loss reporting, and fail-closed
semantics; real artifacts prove ecosystem compatibility. Neither
substitutes for the other.

**Adoption is an evidence bundle, not a label.** An import reaches
`adopted` only per `claudex-spec/19` §4: schema-valid dossier; exact source
versions and digests; compatible converter; adapter conformance green;
declared contamination status; qualified backend; repeated Product-native
evidence at declared budgets with no protected-test access; a decision
label; and a **scoped** status (e.g. `adopted:tabular:linux-cpu`), never a
global one.

**Lab-engine adoption is optional (IC-4 is MAY).** Product progress never
depends on adopting a Lab engine; the Product provides its mandatory
strategy coverage natively. An adoption campaign that ends in a
well-evidenced *rejection* counts as successful interop execution.

---

## Program Gates

| Gate | Meaning | Verified by |
|---|---|---|
| **I0** — Contract frozen enough for fixtures | Export/import schemas versioned; golden fixtures available | schema versions published; fixture suite exists |
| **I1** — Producer conformance | Lab emits valid, digest-addressed, provenance-complete artifacts (incl. mechanism dossiers) | Lab export validation green against fixtures |
| **I2** — Consumer conformance | Product accepts valid fixtures and fails closed on invalid/unmapped/corrupt/old-version inputs | reference-consumer qualification suite green; INTEROP acceptance IDs assigned |
| **I3** — Real import authorized | Representative real Lab artifacts cross the boundary | first real dossiers registered end-to-end |
| **I4** — Adoption campaign complete (repeatable) | A Lab import is adopted, rejected, or classified inconclusive with Product-native evidence | campaign evidence bundle in interop registry |
| **L-SCI** — Lab scientific conclusion | Contender-floor question answered positively or negatively with repeated evidence | promoted evidence + recorded portfolio consequences |
| **P-V1** — Product v1 | Every mandatory Product requirement has linked evidence | claudex acceptance + conformance matrix complete |

These gates deliberately separate five things the previous revision of this
document conflated: *Lab publishes* (I1), *Product can consume* (I2),
*Product adopts* (I4), *Lab succeeds scientifically* (L-SCI), and *Product
conforms as v1* (P-V1).

## Non-Goals Of This Charter

- No calendar estimates — all gates are dependency- and evidence-exited.
- No merged codebase, shared runtime, or common genome.
- No Lab redesign for Product convenience (integrity fixes excepted, as
  defined above); no Product scope reduction by program gate.
- No execution-level work breakdown — that belongs to the two tracks'
  own plans.

## Next Step

`LAB_PLAN.md` — the detailed execution plan for Workstream A, which becomes
the Lab repository's single consolidated plan at bootstrap.
