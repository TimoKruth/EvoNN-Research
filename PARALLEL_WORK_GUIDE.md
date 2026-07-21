---
document_kind: guide
status: current
authoritative: false
---

# Parallel Work Guide

This is a non-authoritative operating guide. `CONSOLIDATED_PLAN.md`, the pinned specifications, and the program charter remain the governing sources. If this guide drifts from them, those sources win.

## Level 1 — Lab and Product repositories

The Lab and Product repositories can develop in parallel and independently. Product foundations do not wait for Lab progress, and neither repository imports the other's code; real artifact influence waits for Lab I1 and Product I2. Only after both producer and consumer conformance pass may the first real crossing be registered. Before then, fixtures and co-signed schemas allow parallel build without authorizing real Lab-derived influence on Product behavior.

## Level 2 — Lab phase lanes

Lab phases remain sequential: Gate B0, then Phases 0 through 7. Inside each phase, Lane A and Lane B may work in parallel only after the phase interfaces are jointly frozen. The operating rhythm is:

**freeze interfaces → parallel lanes → cross-review → joint integration → joint gate**

| Phase | Lane A | Lane B | Joint work |
|---|---|---|---|
| 0 | WP-0.2, 0.3, 0.4, 0.5 | WP-0.1, 0.6, 0.7, 0.8, 0.9 | WP-0.10 integrity gate + phase exit |
| 1 | WP-1.1, 1.2, 1.7, 1.8 | WP-1.3, 1.4, 1.5, 1.6 | phase-exit fair-matrix run |
| 2 | WP-2.1–2.4 | WP-2.5–2.9 | WP-2.10 + exit cohort |
| 3 | WP-3.1, 3.4 | WP-3.2, 3.3 | WP-3.5 + phase exit |
| 4 | WP-4.1–4.4 | WP-4.5, 4.6, 4.7 | WP-4.8 + exit cohort |
| 5 | WP-5.1, 5.2 | WP-5.3 | WP-5.4 transfer proof campaign |
| 6 | WP-6.1, 6.2 | WP-6.3, 6.4 | WP-6.5 portfolio statuses + WP-6.6 L-SCI |
| 7 | WP-7.1, 7.2 | WP-7.3, 7.4 | WP-7.5 release governance + phase exit |

Lane ownership, branch naming, interface-change review, cross-review, and joint-integration rules are defined in `CONSOLIDATED_PLAN.md` and are not redefined here.

## Joint and nonparallel points

The following remain joint decisions or nonparallel integration points: B0, Foundation Integrity Gate, phase exits, transfer proof, L-SCI, portfolio status, and release governance. A lane cannot close any of these unilaterally.

## Current authorization state

Gate B0 is closed. The authoritative repository is pinned, the Linux/NumPy and
macOS/MLX hosted bootstrap probes are preserved and validated offline, and the
joint B0 integration record is checked in.

Closure does not itself authorize immediate parallel implementation. The first
safe parallel point remains Phase 0, and no Phase 0 lane branch may begin before
both lanes jointly freeze and record:

- the canonical-encoding/digest API;
- the export model shapes;
- the catalog-loader signatures.

After that freeze, Phase 0 may split exactly as recorded above. Lane A owns
WP-0.2 through WP-0.5; Lane B owns WP-0.1 and WP-0.6 through WP-0.9; WP-0.10 and
the phase exit remain joint.
