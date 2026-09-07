# EvoNN Research Lab

Research workspace for four independent evolutionary neural-search engines,
portable contender baselines, and a file-based comparison/evidence layer.
This repository is the foundation rebuild; the predecessor is
`TimoKruth/EvoNN` (locally `../Evo Neural Nets`).

## Current capabilities

As of 2026-09-06, Gate B0 is closed and Phase 0 is in progress.
`EvoNN-Shared` implements canonical identities, deterministic RNG streams,
budget/telemetry/export contracts, catalog loading, checkpoint publication,
LM-cache validation, and per-run DuckDB storage/reporting.

Compare, Contenders, Prism, Topograph, Stratograph, and Primordia remain
package skeletons. The production catalog on the base `main` revision is
empty. There is no runnable training/search pipeline or scientific result in
this rebuild. Passing bootstrap probes does not qualify an engine backend.

[`CONSOLIDATED_PLAN.md`](CONSOLIDATED_PLAN.md) is the only active execution
plan. Its dated maintenance section distinguishes implemented work, local
verification, and outstanding hosted/review acceptance. The pinned
[`claude-spec/`](claude-spec/README.md) governs the Lab;
[`PROGRAM_CHARTER.md`](PROGRAM_CHARTER.md) describes the separate Product and
interop tracks. Product specifications here do not imply Product code exists.

## Local verification

Use Python 3.13 and the repository's CI-pinned uv version (`0.5.13`).
Linux and macOS are the supported workspace platforms; MLX is installed only
on Apple Silicon macOS.

```sh
uv sync --all-packages --group dev --locked
uv run --locked --all-packages --group dev pytest -q EvoNN-Shared/tests shared-benchmarks/tests tests/contracts
uv run --locked --all-packages --group dev ruff check .
```

Each package has an independently invocable `scripts/ci/*-checks.sh` script.
`scripts/ci/foundation-checks.sh` is the shared Linux/macOS entry point: it
checks the full Shared package and root contract consumer in one selection,
with a lock check, Ruff and installed package identity verification.
`scripts/ci/b0-policy-checks.sh` checks governance, dependency/import boundaries,
capability claims, and their integration tests; it needs full Git history and
takes longer than the focused suite. The complete `pytest` run additionally
tests the check scripts themselves, including a nested policy run.

Both hosted lanes run the complete foundation suite, including all persistence
and synthetic reference tests, followed by their platform-specific package
checks. Required job names remain stable. Full lanes run for every PR, main
push and manual dispatch; unopened feature branches need manual dispatch.

## Run-directory assumptions

Use application-owned directories on a local filesystem with functioning
POSIX advisory locks and atomic rename/fsync semantics. Run-directory paths
must not traverse symbolic links (including system aliases such as `/tmp`
on macOS; use the actual directory path). Windows/network-filesystem behavior
is not qualified by these checks.

Evaluation inserts and their hash/count records commit in one transaction;
existing evidence is verified before a writer is returned. File/lock/DB/WAL
symlinks are refused, mutable storage hardlinks are refused, and report
replacement is atomic. Verification reads already-opened artifact descriptors.

`open_run_reader(directory, run_id)` provides verified read-only access to a
clean store. It holds a shared lock and a read-only transaction, exposes no
writer methods, and leaves source files unchanged. It refuses missing lock/DB
files and existing WALs; explicit writer recovery must happen before a reader
can consume an interrupted store. Multiple readers may coexist, not a writer.

DuckDB opens a pathname, not a caller-supplied descriptor. These controls
therefore do not sandbox another process with the same filesystem permissions
that replaces run directories concurrently. A hash chain and its tip in the
same database detect inconsistent edits, not a coordinated rewrite of both;
independent evidence anchoring belongs to the later evidence-registry work.
Do not automatically repair damaged evidence on open. Failed schema creation
can leave an empty database file; preserve it for diagnosis and use a fresh run
directory. A post-publication report directory-fsync failure is reported as
uncertain durability, even though the new report is already visible.

## Development

Work on feature branches and merge through reviewed pull requests. Frozen
contract changes follow the existing amendment process. The next functional
milestone is the Phase 0 reference-runner integrity proof, followed by
Contenders and Compare after joint Phase 0 acceptance.
