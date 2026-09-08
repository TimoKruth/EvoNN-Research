# EvoNN Research Lab

Research workspace for four independent evolutionary neural-search engines,
portable contender baselines and a file-based comparison/evidence layer.
This repository is the foundation rebuild; its predecessor is
`TimoKruth/EvoNN` (locally `../Evo Neural Nets`).

## Read these three documents

| Document | Purpose |
| --- | --- |
| **[README.md](README.md)** | What works, package boundaries, installation, verification and operating constraints. |
| **[CONSOLIDATED_PLAN.md](CONSOLIDATED_PLAN.md)** | The sole execution plan: priorities, dependencies, work packages and acceptance criteria. |
| **[PROJECT_HISTORY.md](PROJECT_HISTORY.md)** | Completed work, durable decisions, review outcomes and exact evidence references. |

Update these files in place. Historical specifications and proof records are
reference material; their role and locations are indexed in project history.
Package READMEs are short navigation links, not separate status reports or plans.

## Current capabilities

**Verified baseline: 2026-09-07.** Gate B0 and Phase 0 contract acceptance are
closed. The [acceptance receipt](governance/phase0-acceptance.json) binds the
canonical catalog authorization and successful Linux/macOS CI evidence.
Exact integrations and review decisions are recorded in project history.

| Component | Implemented | Remaining |
| --- | --- | --- |
| Shared | Canonical identities/RNG, strict budgets/telemetry/three-file exports, catalog/pack loaders, checkpoints, LM-cache validation, transactional DuckDB/workspace and verified read-only access | Engine consumers and their evidence |
| Shared benchmarks | Eight immutable planned definitions, three packs, verified historical provenance and budget/export composition | Future image/LM packs and optional enhanced runtime evidence |
| Reference fixtures | Real kill/resume, failed/invalid accounting, seed/label binding, read-only diagnostics and hosted integrity reports | Engine-specific resume/speciation and scientific qualification |
| Contenders + Compare | Fixed CPU pools, bounded isolated fits, complete verified exports, case/budget audit, append-only trends, L0–L3 quality, append-only evidence registry, paired-seed L4 analysis and evidence dashboard | Evolutionary engine comparisons and scientific qualification |
| Prism + Topograph | Package-local MLX/NumPy models, bounded AdamW search, inheritance, atomic resume, portable model exports and Compare ingestion | Larger scientific campaigns; repeated native evidence through registry analysis |
| Stratograph | Hierarchical cell search, trained-head proxy, five ablations, winner motifs, resume/replay | End-to-end hierarchy learning and scientific comparison claims |
| Primordia | Trained primitive circuits, bounded archive/cost policy, verified motif/seed bank | Native cross-engine ingestion and proven transfer gains |

Phase 1 runtime evidence now contains **336 successful fits in five short runs**:
`tier1_core@64` at seeds 42/43/44, core@128 at seed 42, and smoke@16.
Core admission passes with zero blockers and all outputs are L3; smoke remains
insufficient for complete floor coverage. The compact
[runtime receipt](governance/phase1-runtime-evidence.json) binds exact code and
export hashes. [PR #29](https://github.com/TimoKruth/EvoNN-Research/pull/29) and
[PR #30](https://github.com/TimoKruth/EvoNN-Research/pull/30) carry the
implementation and required hosted acceptance checks.
Phase 2 engine runs accept at most **256 proposals** and **30 minutes** per run.
Checkpoints retain full search/attempt snapshots, with a **128 MiB** serialization
guard before publication and a **32 MiB** weight cache. This deliberately bounds
local acceptance work; full-history snapshot writes still grow quadratically.
Larger campaigns require an append-only attempt journal and separate qualification.

Phase 2 acceptance records **896 actual fits in 13 short runs**, all L3:
Contenders/Prism/Topograph on core@64 seeds 42/43/44 and Tier-A@64 seed 42,
plus Contenders core@128. Each run took 100–280 seconds. The recorded verification consumer
reproduces all 64 exported neural winners; core floor admission is `trusted-core`.
The [Phase 2 receipt](governance/phase2-runtime-evidence.json) separates exact
producer and consumer commits. [PR #31](https://github.com/TimoKruth/EvoNN-Research/pull/31)
binds hosted qualification; both required lanes must pass before merge.
Real SIGKILL/resume and delayed-worker tests cover failure recovery.
These are contract and exploratory results; no scientific superiority is claimed.

Run a verified short preset and rebuild its dashboard:

```sh
uv run evonn-compare fair-matrix --workspace .artifacts/compare --preset local
uv run evonn-compare workspace-report .artifacts/compare
```

`--preset smoke` uses 16 fits; `local` uses 64. Runs accumulate. Each system
run stays below 30 minutes; no overnight/weekend preset is admitted.

## Bounded engine operation

```sh
uv run evonn-prism evolve --config EvoNN-Prism/configs/tiny_smoke.yaml
uv run evonn-topograph evolve --config EvoNN-Topograph/configs/tiny_smoke.yaml
uv run evonn-prism evolve --resume <run-directory>
uv run evonn-prism replay <run-directory>
uv run evonn-compare fair-matrix --workspace .artifacts/phase2-native \
  --preset local --systems contenders prism topograph --seeds 42 43 44 \
  --engine-backend mlx_native --engine-epochs 12 --timeout 1200 --fit-timeout 120
```

Both engines expose `evolve`/`run`, `inspect`, `report`, `replay`, `benchmarks`,
`warm-cache` and `symbiosis-export`. Configurations and resumes reject option,
source, dependency and data drift. The tiny presets perform real fits on all
eight smoke benchmarks. NumPy executes the actual architecture and produces
`portability_only` evidence; keep its cohorts separate from native MLX runs.
The native command is a bounded acceptance cohort, not a long research campaign.
Each engine invocation and individual fit have hard limits of at most 1,800 seconds.

Exports bundle checksum-bound data, trained weights, normalization buffers,
regression calibration, attempts and engine telemetry. `replay` reconstructs
held-out metrics without the producer's cache path. Packed low-bit sizes are
estimates; serialized weights and process memory are measured separately.
Topograph's default hardware budget admits one simultaneous training worker;
its runtime worker topology describes that fit worker. One additional pool
supervisor performs no training. The configuration records training, supervisor
and total evaluation process counts explicitly. Optional benchmark pooling uses
within-benchmark quality ranks; novelty weight defaults to zero. MAP-Elites,
full deployment objectives and statistical superiority remain later-phase work.
Compare keeps immutable case evidence at `contract-fair`; a separate
`benchmark-audit --decision-grade` result governs trusted floor admission. A
green audit does not rewrite the original case labels or append-only rows.

## Architecture and authority

The seven uv workspace packages are Shared, Contenders, Compare, Prism,
Topograph, Stratograph and Primordia. `shared-benchmarks/` is data only;
`evonn_shared.catalog` and `evonn_shared.benchmarks` implement its resolution.
Engines remain independent. Compare invokes system CLIs and consume file
exports; Shared contains infrastructure rather than an engine core.

The pinned [Lab specification](claude-spec/README.md) is normative;
[PROGRAM_CHARTER.md](PROGRAM_CHARTER.md) defines Lab/Product boundaries.
[Product interop](claudex-spec/19-research-interop.md) is retained for the consumer
boundary. The remaining Product specifications live in an exact historical
[Git snapshot](claudex-spec/README.md), outside the Lab working documentation. Real Lab
artifacts may influence Product only after Lab I1 and Product I2 pass.
Source changes follow [SPEC_UPGRADE_PROCESS](governance/SPEC_UPGRADE_PROCESS.md);
[traceability](governance/SPEC_TRACEABILITY.md) identifies the authority roles.

## Installation and local verification

Use Python 3.13 and CI-pinned uv `0.5.13`. Supported workspace platforms are
Linux and macOS; MLX installs only on Apple Silicon macOS. From the repo root:

```sh
uv sync --all-packages --group dev --locked
scripts/ci/foundation-checks.sh
scripts/ci/benchmarks-checks.sh
```

The foundation entry point checks the complete Shared package and root
contracts once, plus lock consistency, Ruff and installed package identity.
For a focused reference check:

```sh
uv run --locked --all-packages --group dev pytest -q EvoNN-Shared/tests/test_reference_runner.py
```

For repository policy and freeze verification:

```sh
scripts/ci/b0-policy-checks.sh
```

This checks authority, freeze, import/dependency and capability rules plus
integration tests. Use a full-history clone with canonical `origin`; an archive
or shallow checkout cannot verify the historical Git evidence. The standalone
freeze validator also rejects Git worktrees: it requires a real repository-root
`.git` directory. Plan/guide validation binds committed bytes, so commit documentation candidates before
running the final governance check. The B0 integration suite takes substantially
longer than focused tests; measured timings are in project history.

Each package also has an independently callable `scripts/ci/*-checks.sh`.
Run the scripts relevant to the change; both hosted jobs run the full foundation
suite and their platform-specific checks. A full `pytest` invocation additionally
runs recursive script self-tests and the complete local script matrix.

## Synthetic integrity evidence

The test-only reference runner uses real persistence and checkpoints. Generate
and validate a fresh report of eight SIGKILL/resume cases (failed and invalid
attempts at four durable boundaries):

```sh
uv run --locked --all-packages --group dev python EvoNN-Shared/tests/integrity_probe.py \
  --work-root .artifacts/reference-integrity/runs \
  --output .artifacts/reference-integrity/report.json
uv run --locked --all-packages --group dev python EvoNN-Shared/tests/integrity_probe.py \
  --validate .artifacts/reference-integrity/report.json
```

Work/output paths must be fresh; existing evidence is never overwritten.
The report compares row/checkpoint hashes, fresh/inherited accounting, selector
traces and source digests around read-only export. It records host metadata and
`synthetic_contract_preparation`. Validation proves internal consistency, not
authenticity. Hosted provenance comes from the GitHub run and tested commit.
Each hosted lane uploads only the report as `b0-linux-synthetic-integrity` or
`b0-macos-synthetic-integrity`, with missing-file failure enabled.

This evidence contributes to the accepted Phase 0 contract gate; it does not
admit executable datasets, qualify an engine or prove scientific performance. Kills before durable row commit and general engine
failure recovery are outside this proof. The diagnostic JSON is not the regular
`manifest.json` / `results.json` / `summary.json` export contract.

## Run-directory assumptions

Use application-owned local directories with working POSIX advisory locks and
atomic rename/fsync semantics. Paths must not traverse symlinks, including
macOS aliases such as `/tmp`; resolve the actual directory. Windows and network
filesystems are not qualified.

Evaluation rows and their hash/count tip commit in one transaction. Existing
records are verified before returning a writer. File/lock/DB/WAL symlinks and
mutable-storage hardlinks are rejected; artifact reads use opened descriptors.
Reports replace atomically; new evidence publication refuses overwrites.

`open_run_reader(directory, run_id)` holds a shared lock and read-only
transaction, verifies identity/schema/row chain, exposes no writer operations,
and preserves source bytes. It rejects missing lock/DB files and existing WALs;
explicit writer recovery precedes reading an interrupted store. Readers may
coexist with readers, not a writer. Corrupt evidence is never silently repaired.

DuckDB opens pathnames, so these controls do not sandbox a process with equal
filesystem privileges replacing directories concurrently. A hash chain and tip
inside one database detect inconsistent edits, not a coordinated rewrite.
Registry receipts bind source and consumer identities; current artifact validation remains required for new claims. Failed schema
creation may leave an empty database; preserve it for diagnosis. A directory
fsync failure after publication means uncertain durability even when a complete
new file is visible; do not delete published evidence as a pretend rollback.

## Benchmark and LM-cache storage

Benchmark definitions live in `shared-benchmarks/catalog/`; packs live in
`shared-benchmarks/suites/parity/`. Eight planned definitions and three packs
are accepted as catalog metadata under freeze v3; runtime admission remains
open. Canonical
IDs preserve data/split/metric meaning; changes follow WP-0.1b/0.8.

`shared-benchmarks/lm_cache/` holds versioned `<cache_id>.yaml` manifests;
payload bytes are warmed locally and are not committed. Shared validates file
existence, size and SHA-256 before use. Manifest artifact paths are relative,
UTF-8 sorted and unique. `EVONN_LM_CACHE_DIR` overrides the payload root. Example
shape only, not an admitted cache or valid content digest:

```yaml
schema_version: "1.0.0"
cache_id: tinystories_lm
benchmark_ids: [tinystories_lm]
artifacts:
  - path: train.bin
    size_bytes: 1280
    sha256: "0000000000000000000000000000000000000000000000000000000000000000"
```

## Development workflow

Work on feature branches and use reviewed PRs. GitHub currently requires **zero
approving reviews**, with last-push approval disabled. Linux/macOS checks,
up-to-date branches, resolved review conversations and admin enforcement remain
required; force pushes/deletion of main stay disabled. Substantive review and
the separate frozen-interface amendment evidence remain part of development.

For stacked PRs, merge a parent, retarget its child to main, synchronize and
validate the exact new head before merging. A successful CodeRabbit status can
represent a skipped review: inspect selected files, actionable threads and
summary warnings. Docstring coverage is distinct from code findings.
The plan owns lane assignments and phase acceptance; no second workflow plan
is needed. Stage explicit paths and preserve unrelated local work.

## License

Copyright (C) 2026 Timo Kruth and contributors.

Unless otherwise indicated, original code and documentation are licensed under
GNU GPL version 3 only (`GPL-3.0-only`); see [LICENSE](LICENSE). Each workspace
package carries its own copy for distribution. The software comes without
warranty. Dependencies, datasets and model weights retain their own licenses.

The Phase 4 runtime adds `tier_b_core_v2`: OpenML banknote authentication,
small digit images, diabetes regression and a real Shakespeare byte next-token
benchmark. The text source is pinned to an immutable [char-rnn snapshot](https://github.com/karpathy/char-rnn/blob/370cbcd448eb7daf32f21a6be560b70e0b33c4e3/data/tinyshakespeare/input.txt).
Raw text is split before context creation; the final 15% is protected and unused.
The bounded profile samples at most 1,536 training and 384 validation contexts.
The historical catalog and runtime identities remain immutable; active runtime
consumers use the additive extension through `evonn_shared.active_catalog`.
Package READMEs document [Stratograph](EvoNN-Stratograph/README.md) and
[Primordia](EvoNN-Primordia/README.md). Large repeated comparison and native
transfer claims require subsequent evidence, not these bounded configurations.

`evonn-compare fair-matrix --preset tier_b_tiny` resolves only after its
Phase 4 runtime receipt binds completed L3 short runs. The preset selects
16 evaluations, not the later repeated comparison campaign.
