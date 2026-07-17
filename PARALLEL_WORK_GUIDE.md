# Parallel Work Guide — Who Can Build What, When

**Audience:** any agent joining this program. Read this first; details live
in `PROGRAM_CHARTER.md` (program level) and `LAB_PLAN.md` (Lab level).

## The One-Minute Version

There are **two levels of parallelism**:

1. **Program level:** the Lab (research platform, claude-spec) and the
   Product (claudex-spec) are separate repos that never share code. They
   can be built fully in parallel, forever. The only coordination is the
   interop boundary: schemas first, conformance on each side, then real
   artifacts flow.
2. **Lab level:** inside the Lab, work runs in **phases that are strictly
   sequential** (0 → 7), but **each phase splits into two parallel lanes
   (A and B)** with a joint integration step at the end.

The rhythm inside every Lab phase:

```
freeze interfaces → work in parallel (A ∥ B) → cross-review each other
→ integrate jointly → pass the exit gate together → next phase
```

## Program Level: What Is Parallel Across The Two Projects

| | Parallel? | Why |
|---|---|---|
| Lab development ∥ Product development | ✅ always | separate repos, zero code sharing, typed-artifact boundary only |
| Lab research ∥ Product foundations (contracts, persistence, data governance, web) | ✅ always | Product existence never waits on Lab progress |
| Interop schema/fixture work (I0) | ✅ both sides, once co-signed | each side builds its half against shared fixtures |
| **Real Lab artifacts influencing the Product** | ⛔ sequential | requires **I1** (Lab producer conformance) **and** **I2** (Product consumer conformance) first; first real crossing = I3 |
| Product adopting a Lab engine | ⛔ gated + optional | only after I3, via dossier + revalidation; never blocks Product progress |

**Rule of the boundary:** Lab evidence is prior information for the
Product, never proof. Product rejections flow back to the Lab as
reverse-dossiers. Neither side ever blocks the other.

## Lab Level: What Is Sequential

**The phases themselves.** Each phase builds the ground the next one
stands on — do not start a phase before the previous exit gate passed:

```
B0 → Phase 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7
```

- **B0** pins the specs and creates skeletons (joint, small).
- **Phase 0** contracts + integrity — everything depends on these.
- **Phase 1** trust layer (Contenders + Compare) **before** any engine —
  engines must not define their own favorable comparison system.
- **Phase 2** first engines need the trust layer to be measured.
- **Phase 3** evidence/statistics need real engine output to aggregate.
- **Phase 4** second engine cohort needs the evidence layer to be judged.
- **Phase 5** transfer proof needs Primordia (seeds) + Topograph (consumer)
  + the registry (classification).
- **Phase 6** QD/portfolio/L-SCI need everything above as evidence base.
- **Phase 7** hardening + Observatory need stable reporting surfaces.

**Always joint (never parallel):** B0 bootstrap; the Foundation Integrity
Gate; every phase exit decision; the transfer proof campaign (5.4); the
L-SCI closure (6.6); portfolio statuses (6.5); release governance (7.5);
interop gate evaluations.

## Lab Level: What Is Parallel (The Lane Table)

Within each phase, Lane A and Lane B own disjoint packages/modules:

| Phase | Lane A | Lane B | Joint |
|---|---|---|---|
| 0 | contract/budget/telemetry models, identity + RNG | tooling/CI, checkpoints, RunStore, benchmarks, LM cache | integrity gate |
| 1 | Contenders + audit/quality analyzers | Compare orchestration, trends, dashboard | exit fair-matrix |
| 2 | **Prism** (whole engine) | **Topograph** (whole engine) | integration + telemetry conformance |
| 3 | evidence registry + dashboard/L4 | report vocabularies + statistics | PR policy checker |
| 4 | **Stratograph** (whole engine) | **Primordia** + Tier B packs | integration + CLI conformance |
| 5 | seed schema + Topograph consumption | transfer surfaces + campaign manifest | the proof campaign |
| 6 | QD, MAP-Elites, deferred hardware scope | LM diagnostic, tier hardening | portfolio + L-SCI |
| 7 | performance workflow + optimization | Observatory + automation loop | release governance |
| I (from Ph. 3) | versioning + dossier schema | fixtures + producer conformance | reverse-dossiers, I0/I1 |

The engine phases (2 and 4) are the cleanest splits: the
"engines-never-import-engines" rule means the lanes have **zero shared
interfaces by design**.

## The Six Lane Rules (Short Form)

1. **Ownership** — touch only your lane's packages/modules for the phase.
   A file collision between lanes is a process defect.
2. **Interface freeze** — co-sign the phase's cross-lane
   types/CLIs/schemas at phase start; mid-phase changes need a joint
   mini-review.
3. **Branches** — `agent/p<N>-lane-<a|b>-<slug>`; integrate on
   `agent/p<N>-integrate`.
4. **Cross-review** — your work merges only through a PR reviewed by the
   *other* lane's agent, checked against the pinned spec and the WP
   requirements. Review for real; you are accountable for what you
   approve.
5. **Joint integration** — merge both lanes, run full CI on both hosts +
   integrity suite + cross-cutting suites + exit commands, fix defects
   pairwise, *then* evaluate the exit gate together.
6. **Fallback** — one agent alone runs the lanes sequentially (A then B);
   the integration step still runs unchanged.

## Practical Starting Points

- **Two agents on the Lab:** do B0 together, then take Lane A and Lane B
  of Phase 0 (`LAB_PLAN.md` → "Lane split & sync" blocks per phase).
- **One agent on the Lab, one on the Product:** the Lab agent follows
  `LAB_PLAN.md`; the Product agent follows `claudex-spec/15` Horizons 0–2
  in a new repo. Coordinate only on Workstream C (interop schemas) —
  co-sign the dossier/fixture schemas when both sides reach them.
- **Never do:** import code across the Lab/Product boundary; start a Lab
  phase before the prior exit gate; let one lane's agent approve their
  own work; treat Lab evidence as Product proof.
