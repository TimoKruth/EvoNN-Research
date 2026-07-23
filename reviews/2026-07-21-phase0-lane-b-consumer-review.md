---
document_kind: review
status: delivered
authoritative: false
subject: phase0-frozen-surface-aprime-lane-b-consumer-review
reviewed_ref: b720ea6461c970e3875f8ef735e3e63cf680b660
reviewer: phase0-lane-b-consumer-aprime-reviewer-20260721
verdict: approved
---

# Lane B Consumer Review — Frozen Surface A-prime

## Independence

This is an entirely fresh Lane B consumer review of exact Frozen Surface A-prime `b720ea6461c970e3875f8ef735e3e63cf680b660`. I did not read, search for, quote, or rely on any Lane A draft or output. I independently inspected the exact frozen objects, recomputed all three file-set digests from replacement-disabled Git blobs, reviewed all three surfaces, ran the required commands, and performed independent adversarial probes.

## Immutable target and object verification

Replacement-disabled Git, with `GIT_REPLACE_REF_BASE`, `GIT_GRAFT_FILE`, and `GIT_SHALLOW_FILE` unset, established:

- A-prime: `b720ea6461c970e3875f8ef735e3e63cf680b660` (`commit`)
- exact tree: `f1c5742c2581d270af05714b5ef8514c3f49d996` (`tree`)
- sole parent: `25882c03da8e3af25eb15b9b6ee04059e827ed43` (`commit`)
- canonical Phase 0 base: `b22316d3dea7e0f01ee8aa359f4786897b0680ba` (`commit`)
- canonical base is an ancestor of A-prime: yes (`git merge-base --is-ancestor`, exit 0)
- full-object disambiguation count for A-prime: exactly 1
- shallow repository: false; shallow file absent
- graft file: absent
- replacement refs: absent

A full replacement-disabled recursive tree parse contained 209 entries. The declared frozen sets contain 38 memberships and 36 unique paths. Every declared set was unique and UTF-8-byte sorted; every unique frozen path was a valid unambiguous repository-relative UTF-8 path occurring exactly once as `100644 blob`. There were no missing paths, trees, gitlinks, symlinks, executable blobs, or other modes. Every working-tree counterpart was independently verified by `lstat` to be a regular, non-symlink, non-executable file with bytes exactly equal to its A-prime blob.

## Independent digest recomputation

Method: `canonical-sha256-file-set-v1`. For each UTF-8-byte-sorted path I read the exact replacement-disabled A-prime blob, computed its raw SHA-256, emitted `<blob-sha256><two spaces><repository-relative path><LF>`, concatenated the records, and SHA-256-hashed the concatenation. Mutable working-tree bytes were not used for digest computation.

| Surface | Records | Record bytes | Blob bytes | Digest |
|---|---:|---:|---:|---|
| `canonical_digest_rng` | 6 | 637 | 36,116 | `1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc` |
| `export_models` | 16 | 1,790 | 174,065 | `b18bcdcc8fd8e4cbb6d9dfb1f82c0d998a1f3fedce927991d79388139c2275fc` |
| `catalog_loaders` | 16 | 2,143 | 105,875 | `81cf090ba61b1bfb1bdbf4a5e74c9fe46bfe34f36dcc5c44f72cd4f5cb33edc5` |

The independently computed triple exactly matches the required triple.

## Normative sources reviewed

- `claude-spec/01-system-architecture.md`
- `claude-spec/02-shared-benchmarks.md`
- `CONSOLIDATED_PLAN.md`, Phase 0 WP-0.6 through WP-0.10 and the interface-freeze boundary

## Exact required commands and results

Focused command, run from exact repository root:

```bash
uv run --locked --all-packages --group dev pytest -q \
  EvoNN-Shared/tests/test_catalog.py \
  EvoNN-Shared/tests/test_canonical.py \
  EvoNN-Shared/tests/test_exports.py \
  tests/contracts/test_phase0_shared_interfaces.py
```

Result: exit 0; `304 passed in 3.29s`.

Contract command, run from exact repository root:

```bash
scripts/ci/phase0-contract-checks.sh
```

Result: exit 0; lock resolved 23 packages, Ruff reported `All checks passed!`, and pytest reported `462 passed in 3.37s`.

The contract script covers the ordered frozen public APIs and all focused Shared models/tests. The root installed-context contract imported the exact ordered `__all__` surfaces from isolated installed contexts for all seven Python packages. Both `.github/workflows/linux-trust.yml` (`ubuntu-latest`) and `.github/workflows/macos-engines.yml` (`macos-15`) run this exact Phase 0 contract script after locked workspace synchronization.

## Lane B adversarial probes

An independent temporary-directory harness exercised public models/loaders rather than relying only on committed tests:

- A complete spec-shaped `BenchmarkPack` with top-level `symmetry`, `modalities`, `expected_local_runtime_class`, `minimum_contenders`, `suitability`, and strict-boolean `full_fidelity_local_safe` validated.
- Both exact boolean states validated; string and integer pseudo-booleans were rejected.
- Omitting each of the 11 mandatory pack fields was rejected.
- The obsolete nested `budget_policy.symmetry` shape with no top-level `symmetry` was rejected.
- Depth- and node-limit payloads were injected separately into benchmark definitions, the canonical registry, and pack YAML. Across 16 applicable public-API calls (`get_benchmark`, `list_benchmarks`, `resolve_pack_path`, and `load_parity_pack`), every failure was exact `InvalidCatalogYamlError` with exact `yaml.composer.ComposerError` cause; no bare `RecursionError` escaped.
- Injected `MemoryError`, `KeyboardInterrupt`, and `SystemExit` were exercised across all four public APIs. All 12 calls preserved the exact original exception type.

## Per-surface review

### Catalog loaders and benchmark packs

Approved with no finding. The frozen model matches the required benchmark and pack declarations: strict schema version `1.0.0`, explicit metric direction and ceiling policy, required contenders, runtime class, complete top-level pack admission declarations, exact symmetry vocabulary, deterministic collection rules, and strict no-extra/frozen Pydantic behavior. Committed canonical and fallback pack fixtures carry the complete repaired shape.

Root selection is explicit argument, then `EVONN_SHARED_BENCHMARKS_DIR`, then repository default via `benchmarks.resolve_data_root()`. Canonical definitions win over fallbacks; merged discovery and diagnostics are UTF-8 deterministic; duplicate fallback identities and definitions fail closed. The canonical append-only registry is required, exact, sorted, digest-bound, and cross-checked against discovered definitions.

Filesystem access is descriptor-relative and no-follow for roots, intermediate directories, and files. Inputs are required to be concrete `Path` values; files must be regular; size, alias, duplicate-key, unsupported-value, depth, and node limits fail with stable public taxonomy. Descriptor cleanup preserves primary exceptions, avoids unsafe close retries, and closes all opened fallbacks. `resolve_pack_path` returns a validated lexical path while `load_parity_pack` performs a fresh safe read, so a later replacement is not trusted.

Production remains intentionally unpopulated: `shared-benchmarks/catalog/canonical_ids.yaml` is exactly `schema_version: 1.0.0\nentries: []\n`, the production catalog contains no benchmark definition, and `shared-benchmarks/suites/parity/` contains no YAML pack. No fabricated production Tier A population is implied.

### Canonical identity, digests, and RNG

Approved with no finding. The canonical surface provides typed, schema-domain-bound deterministic JSON bytes; normalized UTF-8 map ordering; NFC normalization; signed-64-bit integer and finite binary64 float rules; volatile-field and absolute-path rejection; top-level digest-field omission; and exact raw-byte SHA-256. The golden vector independently locks bytes and digests. RNG derivation has the exact closed ten-stream enum, validates the unsigned 256-bit root-seed domain, and derives scheduling-independent 128-bit seeds through an explicit versioned domain.

These contracts are usable by future checkpoint and integrity consumers without importing engine internals or relying on host paths, timestamps, hash iteration order, or process scheduling.

### Export, budget, and telemetry models

Approved with no finding. Public names and ordering are frozen by the integrated contract test. Export documents use strict schema version `1.0.0`, frozen/strict/no-extra models, complete budget/accounting/runtime/seeding echoes, visible failed/skipped/unsupported outcomes, measurement provenance, deterministic ordering, cross-file equality checks, derived-best verification, and manifest/summary artifact-union verification. Fixtures and exact golden bytes lock consumer parsing and deterministic serialization.

`write_export` validates all models and cross-file relations before filesystem mutation, serializes deterministic bytes, uses exact file and staging modes, writes and fsyncs complete files, publishes by native exclusive rename without clobbering, fsyncs the containing directory, and preserves primary failure semantics during cleanup. These interfaces are suitable inputs for later `RunWorkspace` fixtures, but do not claim that `RunWorkspace` exists.

## Capability, inventory, and cross-lane assessment

Exact A-prime contains 8 backend capability manifests. All 9 capability `implemented` values are exact `false`. All 24 `scientific`, `portability`, and `producer_conformance` evidence values are exact `false`.

The three frozen surfaces are mutually usable: catalog consumers can use canonical identity for definition/integrity digests; future storage/checkpoint consumers can use canonical raw/structured digests; pack and export models share strict canonical identifiers, ladder tiers, task kinds, metric directions, systems, budgets, and telemetry without engine-runtime coupling. I found no cross-lane mismatch, omitted binding requirement, or frozen-correctness defect.

## Deferred scope and non-claims

This approval is an interface freeze only. It does not claim implementation or validation of `RunStore`, `RunWorkspace`, atomic checkpoints, resume integrity, LM cache validation, production Tier A benchmark or pack population, contender training, Compare orchestration, or any engine training/search runtime. Those remain deferred Phase 0 or later work.

## Findings and final decision

Critical: 0. Important: 0. Specification/frozen-correctness: 0. Minor: 0.

**Decision: approved.** Exact Frozen Surface A-prime `b720ea6461c970e3875f8ef735e3e63cf680b660` is approved from the Lane B consumer perspective.

**Amendment invalidation:** any later byte or mode change to any frozen path automatically invalidates this approval and both reciprocal approvals; approval then requires a new repaired candidate and entirely fresh reciprocal reviews.
