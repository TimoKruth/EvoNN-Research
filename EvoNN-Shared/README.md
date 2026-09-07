# EvoNN Shared

Engine-agnostic contracts and persistence infrastructure for the Phase 0 Lab.

Implemented modules cover canonical identities and named RNG streams,
budget/telemetry/export models, catalog resolution, atomic checkpoints,
byte-level LM-cache validation, DuckDB RunStore, and RunWorkspace/reporting.
There is no search, genome, operator, compiler, or engine runtime implementation.

Run `scripts/ci/shared-checks.sh` from the repository root for the package's
locked dependency, lint, test, and import checks. See the root
[README](../README.md#run-directory-assumptions) for filesystem assumptions
and persistence limitations, and the
[consolidated plan](../CONSOLIDATED_PLAN.md) for outstanding gate acceptance.

Storage hardening uses a small internal `_run_io` module. Existing frozen
catalog/export helpers remain unchanged until the separately planned governance
amendment authorizes their extraction.
