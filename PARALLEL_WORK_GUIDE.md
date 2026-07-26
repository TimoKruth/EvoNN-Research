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

The reviewed A-double-prime Phase 0 interfaces are co-signed and durably
recorded by freeze v2, which supersedes the immutable historical v1 record. The
protected freeze pull request merged into canonical `main` as merge commit
`5a98d9d45c4f2a7bc35bc75f93141473d0769e94`, and that
canonical merge has been verified: it is an exact two-parent merge whose first
parent is the recorded canonical base and whose sole feature parent carries the
reviewed freeze, and the merged tree reproduces all three frozen surface
digests.

This attestation records that verification and authorizes lane branch creation.
Authorization becomes effective once this attestation is itself merged into
canonical `main`. No Phase 0 lane or integration branch exists yet.

<!-- phase0-interface-freeze:begin -->
```yaml
freeze_id: phase0-interface-freeze-v2
governance_record: governance/phase0-interface-freeze.yaml
approved_commit: 25352a4bd7c33b73077d9f9be231b2bb1b48109f
approved_tree: 78a72f1a2229d9e94cd78512be0585f08b2a5895
digests:
  canonical_digest_rng: 1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc
  export_models: f4199dccbab802edd8f6c671286dca8005434ef54b50a0f678e62399784a5c72
  catalog_loaders: 3b804f54e14749e3f0ae1bcb06b0b8415f5954a312c3eaf9057001ea4832f2cc
reviews:
  - reviews/2026-07-23-phase0-lane-a-producer-a2-review.md
  - reviews/2026-07-23-phase0-lane-b-consumer-a2-review.md
status: merged_verified
lane_authorization: true
canonical_merge_commit: 5a98d9d45c4f2a7bc35bc75f93141473d0769e94
verified_at: 2026-07-23T07:27:10Z
lane_branch_creation: authorized
authorization_effective_after: separate authorization attestation is merged
joint_boundary: WP-0.10 and the Phase 0 exit remain joint
```
<!-- phase0-interface-freeze:end -->

Once this attestation is merged, Phase 0 may split exactly as recorded above.
Lane A owns WP-0.2 through WP-0.5; Lane B owns WP-0.1 and WP-0.6 through WP-0.9;
WP-0.10 and the Phase 0 exit remain joint.
