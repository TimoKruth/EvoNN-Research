---
document_kind: review
status: delivered
authoritative: false
subject: phase0-frozen-surface-a-prime-lane-a-producer-review
reviewed_ref: b720ea6461c970e3875f8ef735e3e63cf680b660
reviewer: phase0-lane-a-producer-aprime-reviewer-20260721
verdict: approved
---

# Lane A Producer Review — Frozen Surface A-prime

## Independence

This is an entirely fresh Lane A reciprocal review of exact Frozen Surface A-prime `b720ea6461c970e3875f8ef735e3e63cf680b660`. I did not read, search for, quote, or rely on any Lane B draft or output. I independently inspected the frozen implementation, tests, fixtures, and governing requirements; independently recomputed every digest from replacement-disabled Git blob bytes; and ran the required commands. The repository-root `pwd` was verified as exactly `/Users/timokruth/Projekte/EvoNN` immediately before this ignored draft was written.

## Exact target, topology, and ambiguity checks

- A-prime commit: `b720ea6461c970e3875f8ef735e3e63cf680b660` (`commit`)
- Exact tree: `f1c5742c2581d270af05714b5ef8514c3f49d996` (`tree`)
- Sole parent: `25882c03da8e3af25eb15b9b6ee04059e827ed43` (`commit`)
- Canonical Phase 0 base: `b22316d3dea7e0f01ee8aa359f4786897b0680ba` (`commit`)
- Replacement-disabled `merge-base --is-ancestor` from the canonical base to A-prime: exit 0.
- Repository shallow state: `false`; graft file absent; `GIT_REPLACE_REF_BASE`, `GIT_GRAFT_FILE`, and `GIT_SHALLOW_FILE` unset; replacement-ref count 0.
- Full replacement-disabled recursive tree parsing found every declared membership exactly once, with canonical non-malformed UTF-8 repository-relative paths and no duplicate/ambiguous frozen path.
- All 38 set memberships resolve to 36 unique entries; every entry is exactly mode `100644`, type `blob`.
- Every working-tree counterpart is a regular non-symlink, non-executable file whose bytes exactly equal the A-prime blob.
- Final HEAD, tree, parent line, ancestry, frozen modes/bytes, and tracked index/worktree cleanliness were reverified after all test and probe commands.

## Independent digest recomputation

Method: `canonical-sha256-file-set-v1`. For each UTF-8-byte-sorted path, I read the exact replacement-disabled A-prime blob, computed its raw SHA-256, emitted `<blob-sha256><two ASCII spaces><repo-relative path><LF>`, concatenated those records, and SHA-256 hashed the concatenation. No working-tree bytes or prior report digest values were used as digest inputs.

| Surface | Records | Concatenated bytes | Independently computed digest |
|---|---:|---:|---|
| `canonical_digest_rng` | 6 | 637 | `1806b230d6d218154898f5db8eae4089ffda07bfdf8c395d3523946a2f9fb7bc` |
| `export_models` | 16 | 1790 | `b18bcdcc8fd8e4cbb6d9dfb1f82c0d998a1f3fedce927991d79388139c2275fc` |
| `catalog_loaders` | 16 | 2143 | `81cf090ba61b1bfb1bdbf4a5e74c9fe46bfe34f36dcc5c44f72cd4f5cb33edc5` |

The independently computed triple exactly matches the required triple.

## Requirements reviewed

Primary Lane A normative sources:

- `claude-spec/03-budget-and-fairness.md`
- `claude-spec/04-telemetry-and-artifacts.md`
- `CONSOLIDATED_PLAN.md`, Phase 0 WP-0.2 through WP-0.10 and the interface-freeze boundary

For the required cross-lane pack assessment, I also inspected the pack and admission requirements in `claude-spec/02-shared-benchmarks.md`.

## Exact required commands and results

Focused command:

```bash
uv run --locked --all-packages --group dev pytest -q \
  EvoNN-Shared/tests/test_canonical.py \
  EvoNN-Shared/tests/test_rng.py \
  EvoNN-Shared/tests/test_budgets.py \
  EvoNN-Shared/tests/test_telemetry.py \
  EvoNN-Shared/tests/test_exports.py \
  EvoNN-Shared/tests/test_catalog.py \
  tests/contracts/test_phase0_shared_interfaces.py
```

Result: exit 0; `462 passed in 3.32s`.

Contract command:

```bash
scripts/ci/phase0-contract-checks.sh
```

Result: exit 0; lock check resolved 23 packages, Ruff reported `All checks passed!`, and pytest reported `462 passed in 3.33s`.

The root contract tests exercised the exact ordered public `__all__` surfaces and all seven isolated installed package contexts. The exact frozen public signatures were inspected for canonical encoding/digest, RNG derivation, export publication, and all four catalog loaders. Export and catalog schema versions are strictly `1.0.0`. Both `.github/workflows/linux-trust.yml` and `.github/workflows/macos-engines.yml` invoke `scripts/ci/phase0-contract-checks.sh`.

## Surface findings

### Canonical identity and RNG producer semantics

No findings. The typed canonical encoding binds the schema domain, normalizes Unicode to NFC, sorts mapping keys by UTF-8 bytes, gives stable explicit encodings to supported scalar/container types, normalizes negative zero, rejects non-finite floats and out-of-range integers, forbids volatile timestamp fields and absolute/drive-qualified path fields, and implements top-level digest-field omission without dropping nested fields. Golden vectors and cross-process hash-seed tests lock exact bytes and digests. RNG derivation accepts only exact unsigned 256-bit integer roots and the closed ten-member `StreamName` enum, domain-separates the derivation, and returns deterministic scheduling-independent 128-bit stream seeds with independent golden vectors.

### Budget, telemetry, and export producer completeness

No findings. The models are strict, frozen, extra-forbid contracts. `BudgetDeclaration` covers all seven required budget categories; `BudgetAccounting` exposes all nine accounting fields and enforces nonnegative counts, actual/cached envelope limits, failure accounting, resume consistency, and exact partial-run state. Telemetry covers runtime/backend/device/worker metadata, explicit measurement provenance, complete seeding provenance and cost modes, visible failed/skipped/unsupported outcomes, coverage, best results, aggregates, fairness flags, and artifact references.

The three export documents carry strict schema versions and validate internal and cross-file identity, budget, accounting, runtime, seeding, status, timing, coverage, best-result derivation, and artifact-union echoes. Result records cannot silently drop declared benchmark coverage, and per-record evaluation counts must sum to actual evaluations. Serialization is deterministic JSON with sorted keys, compact separators, UTF-8, finite numbers, and one terminal LF; committed goldens and independently pinned raw SHA-256 values pass across mapping insertion order and `PYTHONHASHSEED` changes.

`write_export` validates before filesystem mutation, uses exact models, creates private `0700` staging and `0600` files, loops over short writes, fsyncs every file and the staging directory, performs native exclusive no-replace directory publication on Linux/macOS, fsyncs the parent after publication, refuses existing or raced destinations, and preserves the primary exception while recording cleanup failures. Pre-publication failures leave no destination and clean only verified owned staging; post-publication durability/close failures raise while preserving the complete published directory. The focused suite covers collision, symlink, ownership/mode, descriptor-reuse, identity-swap, cleanup, and no-clobber failure semantics.

Fixtures and goldens cover valid manifest/results/summary documents and reject wrong-schema, B0 capability, and Product evaluation shapes. No producer-side frozen correctness or cross-file usability defect was found.

### Catalog/loaders and producer-side pack usability

No findings. Producer code can now truthfully declare the complete spec-shaped `BenchmarkPack` with mandatory top-level `symmetry`, `modalities`, `expected_local_runtime_class`, `minimum_contenders`, `suitability`, and strict-boolean `full_fidelity_local_safe`, while retaining benchmark IDs, ladder tier, and divisible evaluation policy. Canonical and fallback fixtures load with all declarations intact. Omission of every mandatory pack field rejects; the obsolete nested-symmetry form rejects; invalid ordering/duplicates/literals and string/integer pseudo-booleans reject. This repair does not weaken or alter canonical identity, RNG, budget, telemetry, or export producer semantics.

Catalog access preserves explicit-root, environment-root, then repository-default precedence; canonical definitions win over fallbacks; merged discovery is deterministic; canonical registry membership and structured-definition digests are validated; duplicate definitions and unknown pack references fail with stable distinct errors. Access is descriptor-relative, no-follow, regular-file-only, size-bounded, and cleanup-aware.

The corrected YAML path bounds input at 1 MiB, 64 collection levels, and 10,000 composed nodes; aliases and duplicate mapping keys are rejected. Focused tests cover excessive depth and node count through benchmark, canonical-registry, and pack public APIs. These failures emerge as exact `InvalidCatalogYamlError` caused by `yaml.composer.ComposerError`, not bare `RecursionError`; `MemoryError`, `KeyboardInterrupt`, and `SystemExit` remain distinct. A supplementary direct public-API probe of the complete pack shape, mandatory/legacy rejection, strict boolean handling, and hostile benchmark/registry/pack depth behavior also passed.

Production remains honest and deferred: exact A-prime contains the byte-exact empty canonical registry `schema_version: 1.0.0\nentries: []\n` and zero production parity YAML packs. No Tier A population or fabricated production pack was introduced.

## Capability, CI, and cross-lane assessment

Exact A-prime contains 8 backend capability manifests. All 9 capability `implemented` booleans are false, and all 24 scientific, portability, and producer-conformance evidence booleans are false. The Linux and macOS hosted workflows both run the frozen Phase 0 contract script. The public API ordering, signatures, strict schemas, fixtures/goldens, seven installed package contexts, empty production registry, and no fabricated pack are mutually usable by the future consumer lane without overstating implementation or evidence.

## Deferred scope and non-claims

This approval freezes interfaces only. It does not claim implementation or proof of RunStore/RunWorkspace, checkpoints, resume integrity, LM cache validation, production Tier A benchmark population, contender training, Compare orchestration/auditing, or any engine training/runtime. It creates no scientific, portability, or producer-conformance evidence claim.

## Amendment invalidation

Any later byte or mode change to any path in any of the three frozen sets invalidates this approval automatically and requires a new repair/candidate and reciprocal-review cycle.

## Final decision

Approved. Unresolved findings: Critical 0, Important 0, Minor 0, specification 0, frozen-correctness 0.
