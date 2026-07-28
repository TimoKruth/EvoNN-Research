# Shared Benchmarks

This directory is the repository's data-only home for benchmark catalog YAML,
parity suites, language-model cache data, and migration records. It is not a
Python package. Frozen catalog models and descriptor-safe loaders live in
`evonn_shared.catalog`; runtime path resolution and layout validation live in
`evonn_shared.benchmarks`.

The Phase 0 catalog contains eight immutable Tier A identities and three parity
packs: `tier1_core`, `tier1_core_smoke`, and `tier_a_contract`. Every production
definition is intentionally `planned` and tagged `catalog_only`: this repository
does not yet implement the dataset loaders or training runtime needed to claim
that a benchmark is executable. Pack validation proves catalog integrity only,
not benchmark results or scientific evidence.

Migration provenance and field mappings are recorded under `migration/`. The
canonical registry binds each definition to its frozen-model digest; it must be
updated through the catalog identity algorithm rather than a raw file hash.

## LM cache manifests

`lm_cache/` holds one manifest per real language-modeling cache, named
`<cache_id>.yaml`. The manifest is version controlled; the byte-level payload it
describes is warmed locally and never checked in. `evonn_shared.lm_cache`
verifies a warmed payload against its manifest — existence, size, and SHA-256 —
before any LM claim may cite it.

```yaml
schema_version: "1.0.0"
cache_id: tinystories_lm
benchmark_ids:
  - tinystories_lm
artifacts:
  - path: train.bin
    size_bytes: 1280
    sha256: 0000000000000000000000000000000000000000000000000000000000000000
```

Artifact paths are relative to the payload root, UTF-8 sorted, and unique. The
payload root defaults to this directory and is overridden by
`EVONN_LM_CACHE_DIR`.
