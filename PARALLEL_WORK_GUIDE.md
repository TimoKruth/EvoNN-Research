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

Gate B0 is closed. The canonical merge has been verified; Phase 0 implementation
has begun and its maintenance series is integrated. WP-0.10 and the Phase 0 exit
remain joint. The exact authorization block below is retained because the
standalone freeze validator requires this canonical path and matching marker.
It records the historical authorization, not today's task list.

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
