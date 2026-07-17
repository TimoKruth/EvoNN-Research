# ADR-0003 — Separate Transactional, Analytical, and Artifact Storage

**Status:** Provisional — accepted only after concurrency, durability, and load spikes pass

## Decision

- SQLite WAL with `synchronous=FULL`, SQLAlchemy 2, and one writer for default local metadata.
- PostgreSQL optional for higher concurrency/remote metadata access.
- One DuckDB file per run for analytical evidence, owned by one process while active; other processes use an owner query interface or immutable snapshots.
- Local digest-addressed artifact store.
- Alembic reviewed migrations.

## Consequences

Coordination does not use DuckDB. Dashboards/exporters use read-only access. Same-run writers require a lease. OCI/ORAS is optional distribution, not local storage authority.
