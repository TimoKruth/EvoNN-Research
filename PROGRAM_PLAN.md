# EvoNN Program Plan — Two Tracks, One Boundary

**Status:** High-level program plan (detailed Track 1 plan follows separately)
**Date:** 2026-07-17
**Sources:** `claude-spec/` (Track 1), `claudex-spec/` (Track 2),
interop contract (`claude-spec/19` + `claudex-spec/19`)

## The Shape Of The Program

Two projects, built in sequence, developed independently, connected only by
the versioned interop boundary:

- **Track 1 — the Lab** (claude-spec): the scientific research platform.
  Four search engines, shared benchmarks, Compare, Contenders, evidence
  loop. Built first; delivers research value on its own.
- **Track 2 — the Product** (claudex-spec): the local model-building
  product. Built second, as its own codebase with its own repo, consuming
  the Lab's discoveries through typed artifacts — never through code
  sharing.

```
Track 1 (Lab):      L1 ──► L2 ──► L3 ──► L4 ──► (continuous research) ──►
                                   │ publishes: benchmarks · seeds ·
                                   │ dossiers · evidence · engines
                                   ▼
Track 2 (Product):            P0 ──► P1 ──► P2 ──► P3 ──► P4 ──►
                                   ▲
                                   └ returns: defect findings · backend
                                     qualification · failed-adoption reports
```

Rule of the program: **the boundary is the only coupling.** Either track can
pause, pivot, or refactor internally without breaking the other.

---

## Track 1 — The Lab (claude-spec)

### L1 · Foundations
Workspace, shared contracts (`evonn_shared`), benchmark catalog with
canonical IDs, Tier A packs, CI lanes.
**Exit:** contracts import everywhere; Tier A audits green.

### L2 · Trust substrate
Contenders (required floors), Compare core (fair-matrix, trends, dashboard,
audits), first two engines (Prism, Topograph) at L3 output quality.
**Exit:** repeated-seed `trusted-core` runs on the daily lane.

### L3 · Full portfolio & evidence memory
Evidence registry + statistical decision layer; Stratograph and Primordia
join; Tier B lanes; research decision gate enforced in PR flow.
**Exit:** a before/after engine change is judged from registry-backed
evidence; five-system Tier B cohort at 3 seeds.

### L4 · Research proof points
Native transfer proof (Primordia → Topograph), quality-diversity
experiments, Tier C/D hardening, first evidence-backed portfolio statuses,
performance-baseline discipline.
**Exit:** one classified transfer outcome; every engine has an
evidence-backed role.

### L5 · Publishing discipline (the intertwine gate)
The ch. 19 export surfaces become routine: versioned seed artifacts,
mechanism dossiers distilled from research notes, append-only canonical ID
registry, commit-stamped evidence rows.
**Exit — Gate G1:** the Lab is consumable. Track 2 may start.

After L5 the Lab runs as a continuous research program (its natural state);
it never "finishes."

---

## Track 2 — The Product (claudex-spec)

Starts at **Gate G1**, in its own repository, so the product consumes real
Lab artifacts from day one instead of fixtures.

### P0 · Spikes & skeleton
Technology validation spikes, monorepo boundaries, identities/schemas/
events, metadata store, worker isolation, CI on both platforms.
**Exit:** a no-op job runs, persists, resumes, and is inspectable.

### P1 · Data governance & protected evaluation
Dataset descriptors, splits, leakage capabilities, task/metric registries,
physical test-label separation.
**Exit:** representative datasets produce protected, reproducible versions.

### P2 · Product spine (deliberately narrow)
Baselines, unified evaluation artifact, budget accounting, selection and a
first verified native bundle — **for a constrained task set (tabular +
image only)**, per the shared warning of both comparisons: prove the spine
before the surface.
**Exit:** the product selects and exports a validated baseline model
end-to-end.

### P3 · Portfolio & first Lab imports
Portfolio planner, then the first imported engines via IC-4 adapters
(Prism-lineage first), seeds via IC-2, mechanisms via IC-3 dossiers —
each walking the trust ladder (imported → revalidating → adopted).
**Exit:** automatic mode completes with at least one adopted Lab engine
competing against product baselines.

### P4 · Broaden & harden
Remaining modalities toward the v1 conformance matrix, remaining strategy
branches, deployment/Core ML gates, web app, security hardening — scope
governed by what P2/P3 evidence justifies, not by the matrix as a quota.
**Exit:** claudex v1 acceptance criteria, at whatever scope was ratified.

---

## The Intertwine (standing, both directions)

Active from Gate G1 onward, governed entirely by the ch. 19 pair:

- **Lab → Product:** benchmarks (IC-1), seeds/motifs (IC-2), mechanism
  dossiers (IC-3), engine graduations (IC-4), evidence-as-priors (IC-5).
  Lab evidence is never product proof — everything revalidates in the
  product harness.
- **Product → Lab:** defect findings, backend qualification data,
  failed-adoption reports — into the Lab's backlog as `product-feedback`.
- **Versioning:** the Lab versions its boundary; the product's converters
  and staleness rules absorb drift. Neither track blocks the other.

## Program-Level Decision Points

| Gate | Question | Decided by |
|---|---|---|
| G1 (end L5) | Is the Lab consumable enough to start the Product? | export surfaces live + registry validation green |
| G2 (during P3) | Which engines graduate first, at what scope? | Lab portfolio statuses + product revalidation evidence |
| G3 (before P4) | How much of the claudex v1 surface is actually justified? | P2/P3 evidence vs conformance matrix |

## Non-Goals Of This Plan

- No calendar estimates — stages are dependency-ordered, gate-exited.
- No merged codebase, shared runtime, or common genome — ever.
- No product work before G1; no Lab redesign for product convenience.

## Next Step

Write the **detailed implementation plan for Track 1** (L1–L5), derived
from claude-spec chapters 17–18, with per-stage work breakdown and
verification.
