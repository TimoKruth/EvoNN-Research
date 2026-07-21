---
document_kind: governance_process
status: active
authoritative: true
upgrade_policy:
  review_vehicle: pull_request
  review_required: true
  required_evidence:
    - source_diff
    - new_provenance
    - traceability_impact
    - supersession_statement
    - policy_test_results
  forbidden_references:
    - floating_branch
    - floating_tag
    - latest
  pin_update: atomic_with_validator_trust_anchor
---

# Specification Upgrade Process

The governing-source pin is immutable until changed by a reviewed pull request. A source upgrade must never use a floating branch, floating tag, `latest`, or any other reference whose bytes can change without a new review.

## Required Upgrade Pull Request

Every upgrade requires one reviewed pull request containing all of the following:

1. The source diff from the currently pinned commit to the proposed exact commit.
2. New provenance for every changed authority entry: exact source commit, declared version, UTC import time, Git object type and ID, and checked-in SHA-256 digest.
3. A traceability impact assessment covering requirements, work packages, gates, interop mappings, and any implementation or test changes.
4. A supersession statement linking the new entry to the authority entry it replaces, or explicitly stating that no entry is superseded.
5. Policy-test results showing the provenance, working-tree digest, active-plan, archive, and B0 status validators pass.

The pull request must be reviewed against `claude-spec/`, `PROGRAM_CHARTER.md`, and `claudex-spec/19-research-interop.md`. Product consumer acceptance remains Product-owned and cannot be changed by a Lab-only approval.

## Deterministic Digest Procedure

File authorities use SHA-256 over the exact blob bytes at the pinned commit.

Directory authorities use `canonical-sha256-tree-v1`:

1. Enumerate every file below the directory at the pinned commit.
2. Convert each path to its directory-relative POSIX path and sort entries by the UTF-8 bytes of that path.
3. For each entry, compute the lowercase SHA-256 hex digest of the exact blob bytes.
4. Append one UTF-8 manifest line per entry: `<blob-sha256><two spaces><relative-path><LF>`.
5. Compute SHA-256 over the complete manifest bytes. The resulting lowercase hex value is the directory content digest.

The policy validator repeats the same procedure against both the pinned commit and the checked-out authority bytes. Any source-byte change without matching provenance fails closed.

## Closing B0.2

B0.2 stays open while the authority state is `local-only/provisional` and every `upstream_url` is null. Once a real authoritative remote exists, a reviewed pull request may set the remote URLs, change the authority state, and close B0.2 without changing the already verified source commit, Git object IDs, or content digests. If the remote's authoritative bytes differ, that is a source upgrade and the full process above applies.

## Gate B0 Remote-Pinning Closure Record

Gate B0.2 was closed through the reviewed B0 closure pull request by changing
the authority document from `local-only/provisional` to `remote-pinned` and
setting every authority entry to
`https://github.com/TimoKruth/EvoNN-Research.git`.

This transition did not change governing-source bytes, source commits,
declared versions, import timestamps, Git object types or IDs, content
digests, authority roles, consumer-acceptance ownership, or supersession
state. It is therefore a provenance-state transition, not a source upgrade.
Any future change to the pinned bytes or identities remains subject to the
full upgrade process above.
