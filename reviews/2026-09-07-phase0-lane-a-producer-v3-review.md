---
document_kind: review
status: delivered
authoritative: false
subject: phase0-catalog-v3-lane-a-producer-review
reviewed_ref: 0ece535d8b68c8701a17e404baa25dd6b20be52e
reviewer: phase0-lane-a-producer-reviewer-20260907
verdict: approved
---

# Phase 0 Catalog v3 — Independent Lane A Producer Review

## Independence and exact target

I independently reviewed commit `0ece535d8b68c8701a17e404baa25dd6b20be52e`, tree `1a65a5b343d43674025458718697dea923fb2d6e`, against baseline `836cfffc204babab70f8c222b45668df03e04564`. Exact Git blobs and separate full clones supplied the evidence; no other review conclusions were used. Replacement objects were absent and digest reads set `GIT_NO_REPLACE_OBJECTS=1`.

This fresh review supersedes my earlier producer review of `45f3b36f0d771a3f59c8334560074ad7732262ea` because the frozen provenance receipt changed. Scope remains eight **planned metadata definitions** and three pack definitions, not runtime admission, scientific qualification, Phase 0 acceptance or a not-yet-reviewed successor binding.

## Independently recomputed frozen surfaces

Method: `canonical-sha256-file-set-v1`: SHA-256 each exact Git blob, form sorted repository-path lines `<hex>  <path>\n`, then SHA-256 that manifest. Inventories are sorted and duplicate-free.

| Surface | Files | Bytes | Recomputed SHA-256 |
| --- | ---: | ---: | --- |
| `canonical_digest_rng` | 6 | 36,116 | `1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc` |
| `export_models` | 16 | 175,876 | `f4199dccbab802edd8f6c671286dca8005434ef54b50a0f678e62399784a5c72` |
| `catalog_loaders` | 28 | 117,924 | `f123d29b3c29464aa947e271c0b26ed74278eb528322a5fb808b3679b4a86fe5` |

Canonical/RNG and export surfaces remain unchanged. The catalog surface replaces the empty production registry and its inventory assertions, adding eight definitions, three packs and provenance. Existing loader source, strict parsing behavior, public contracts and hostile-input/path/registry tests remain intact. Since the earlier candidate, only the provenance receipt within the frozen set changed.

## Source, compatibility and normative scope

I fetched predecessor commit `3652e0a32a907b51fb26a56fa9650ba258cb9054` directly from `https://github.com/TimoKruth/EvoNN.git` into the independent review clone. All ten source paths in the provenance receipt matched their recorded Git blob IDs and SHA-256 values. The final receipt retains those source records byte-for-byte at the value level.

Each definition matches the predecessor Tier A pack/catalog for canonical identity, task, dimensions, output count, metric/direction, required floor, runtime class and epoch budget. `digits_image` declares 8×8 image metadata corresponding to the historical 64 features and explicit image-shape fallback; no executable reshape or runtime compatibility claim is introduced. Pack order preserves all eight identities. Smoke reduces budget from 64 to 16 without changing datasets; budgets divide by eight and pack floors cover member requirements.

I additionally traced the historical OpenML delegation through `EvoNN-Contenders/src/evonn_contenders/benchmarks/registry.py` (blob `3a43cb5ba272aff751f1a0139489d7c006fa81a2`). Together with recorded `spec.py`, it confirms the disclosed seed 42, validation fraction 0.2, classification target stratification and absent third split.

Lab chapters 02, 03, 06 and 17 and the explicit WP-0.10 capability requirement support the corrected separation in this final candidate:

- Missing dataset loaders and bound data/cache checksums are runtime-readiness gaps.
- Missing executed contender-floor results and benchmark-audit evidence block decision-grade promotion; they do not forbid the first smoke execution needed to obtain that evidence.
- A protected third split is required only by a protocol that declares it, not universally by Lab Phase 0/1. Changing split semantics requires new canonical IDs and provenance.
- Regular export-contract fixtures and the no-op integrity consumer can supply separate evidence. There is no normative requirement to add a synthetic SystemId or manufacture a regular engine export from no-op agreement scores.

The receipt now expresses these distinctions explicitly instead of a flat list of runtime blockers. The plan/history changes are limited to the same correction; they preserve the actual integrity and acceptance requirements. No source authority, runtime implementation or benchmark meaning is changed.

All definitions remain `planned` and `catalog_only`; provenance remains `proposal_not_admitted`. Estimated pack runtime/local-safety metadata and required floor declarations are not measured or executed evidence. Runtime support and decision-grade promotion remain unproved.

## Executed verification and continuity

At final exact candidate `0ece535d8b68c8701a17e404baa25dd6b20be52e`:

- `uv run --locked --all-packages --group dev pytest -q EvoNN-Shared/tests/test_catalog.py tests/contracts/test_phase0_shared_interfaces.py shared-benchmarks/tests/test_catalog_inventory.py`: **150 passed in 8.51s**.
- Independent exact-blob recomputation of all three digests: results above.
- Compared the narrow delta against prior reviewed `45f3b36f0d771a3f59c8334560074ad7732262ea`: exactly plan/history clarification and provenance-scope correction; all source, test, definition and pack bytes unchanged.
- Provenance checks confirmed unchanged ten source receipts and historical split, two actual runtime blockers, separate decision-grade blockers and conditional split limitation.
- `git diff --check` for that narrow delta: passed.

Earlier independent checks at source/test-identical initial candidate `1137d3b18f423d002318c06f891c8106733cee04` remain applicable to unchanged implementation, without being represented as final-commit reruns:

- Locked workspace sync: passed.
- Frozen contracts/catalog selection: **475 passed in 4.84s**.
- `scripts/ci/benchmarks-checks.sh`: lock/Ruff/skeleton passed; **10 tests passed in 0.45s**.
- All Shared tests, shared-benchmark tests and interface contracts: **783 passed in 26.01s**.
- Active v2 standalone validator rejected exactly the intended `test_catalog.py` and `canonical_ids.yaml` changes. The old freeze has not been waived.

## Findings and decision

Critical: 0

Important: 0

Specification: 0

Frozen-correctness: 0

Minor: 0

Approved for this exact planned-metadata producer surface. The amended receipt corrects overly broad blockers while keeping every actual protocol and evidence requirement. The changed catalog digest requires fresh matching consumer evidence and a reviewed successor validator/binding, canonical merge verification and attestation before freeze acceptance. Historical v1/v2 verdicts and frozen meanings must remain protected.
