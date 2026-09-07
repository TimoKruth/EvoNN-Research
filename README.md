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

**Verified baseline: 2026-09-07, main `646dde2`.** Gate B0 is closed; Phase 0
is in progress. The #10–#20 maintenance series is integrated, GPL-3.0-only
licensing (#21) and CodeRabbit configuration (#22) are present. Both final-main
hosted lanes passed. Exact commits and runs are recorded in project history.

| Component | Implemented | Not yet implemented or accepted |
| --- | --- | --- |
| Shared | Canonical identities/RNG, strict budget/telemetry/export contracts, catalog/pack loaders, checkpoints, LM-cache validation, transactional per-run DuckDB, workspace/reporting and verified read-only access | Joint Phase 0 acceptance and catalog-backed reference integration |
| Shared benchmarks | Data layout, schemas/loaders in Shared, immutable-ID validation | Eight planned definitions and three packs are proposed; freeze acceptance and runtime admission remain open |
| Reference fixtures | Real kill/resume tests, failed/invalid budgets, seed/label binding, verified diagnostic export and cross-host JSON evidence | Production three-file export integration; engine/scientific qualification |
| Contenders + Compare | Importable packages, check scripts and capability manifests | Baseline fitting, CLI orchestration, comparison and evidence reports |
| Prism, Topograph, Stratograph, Primordia | Importable packages and runtime bootstrap dependencies/probes | Search/training engines, qualified backends and scientific results |

The next acceptance milestone is Phase 0 completion; its ordered work and
failure conditions are in the consolidated plan. A green bootstrap or synthetic
probe does not establish engine capability or scientific performance.

## Architecture and authority

The seven uv workspace packages are Shared, Contenders, Compare, Prism,
Topograph, Stratograph and Primordia. `shared-benchmarks/` is data only;
`evonn_shared.catalog` and `evonn_shared.benchmarks` implement its resolution.
Engines remain independent. Compare will invoke engine CLIs and consume file
exports; Shared contains infrastructure rather than an engine core.

The pinned [Lab specification](claude-spec/README.md) is normative;
[PROGRAM_CHARTER.md](PROGRAM_CHARTER.md) defines Lab/Product boundaries.
[Product specifications](claudex-spec/README.md) are reference requirements for
the separate Product, not evidence that Product code exists here. Real Lab
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

This does not admit catalog entries, qualify an engine, close Phase 0 or prove
scientific performance. Kills before durable row commit and general engine
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
Independent anchoring belongs to the future evidence registry. Failed schema
creation may leave an empty database; preserve it for diagnosis. A directory
fsync failure after publication means uncertain durability even when a complete
new file is visible; do not delete published evidence as a pretend rollback.

## Benchmark and LM-cache storage

Benchmark definitions live in `shared-benchmarks/catalog/`; packs live in
`shared-benchmarks/suites/parity/`. Eight planned definitions and three packs
are prepared; freeze acceptance and runtime admission remain open. Canonical
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
