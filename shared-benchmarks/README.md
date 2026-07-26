# Shared Benchmarks

This B0 skeleton is the repository's data-only home for future benchmark catalog YAML, parity suites, language-model cache data, and migration notes. It is not a Python package and contains no implemented catalog schema or loader.

Runtime resolution and B0 layout validation live in `evonn_shared.benchmarks`.

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
