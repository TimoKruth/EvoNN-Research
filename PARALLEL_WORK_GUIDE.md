---
document_kind: guide
status: current
authoritative: false
---

# Parallel Work Guide — Compatibility Reference

Current workflow and lane ownership are consolidated in
[the execution plan](CONSOLIDATED_PLAN.md#parallel-execution-and-integration).
Use [README](README.md#development-workflow) for PR mechanics and
[project history](PROJECT_HISTORY.md) for completed integration evidence.

Gate B0 is closed. The v2 canonical merge has been verified; Phase 0 implementation
has begun and its maintenance series is integrated. WP-0.10 and the Phase 0 exit
remain joint. The exact authorization block below is retained because the
standalone freeze validator requires this canonical path and matching marker.
It records the active freeze status. The v3 canonical merge is verified below. Authorization becomes effective
when this separate attestation is merged. Phase 0 acceptance remains separate.

<!-- phase0-interface-freeze:begin -->
```yaml
freeze_id: phase0-interface-freeze-v3
governance_record: governance/phase0-interface-freeze.yaml
approved_commit: 0ece535d8b68c8701a17e404baa25dd6b20be52e
approved_tree: 1a65a5b343d43674025458718697dea923fb2d6e
digests:
  canonical_digest_rng: 1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc
  export_models: f4199dccbab802edd8f6c671286dca8005434ef54b50a0f678e62399784a5c72
  catalog_loaders: f123d29b3c29464aa947e271c0b26ed74278eb528322a5fb808b3679b4a86fe5
reviews:
  - reviews/2026-09-07-phase0-lane-a-producer-v3-review.md
  - reviews/2026-09-07-phase0-lane-b-consumer-v3-review.md
status: merged_verified
lane_authorization: true
canonical_merge_commit: 322834900aa99a267b78b789a733e96ac205dd04
verified_at: 2026-09-07T15:49:25Z
lane_branch_creation: authorized
authorization_effective_after: separate authorization attestation is merged
joint_boundary: WP-0.10 and the Phase 0 exit remain joint
```
<!-- phase0-interface-freeze:end -->
