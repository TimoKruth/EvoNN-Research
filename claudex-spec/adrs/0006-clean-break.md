# ADR-0006 — Clean Break from Legacy Artifacts and Commands

**Status:** Accepted

## Decision

The new EvoNN does not read or preserve previous commands, configs, databases, runs, manifests, or models as part of v1.

Prior systems are design evidence only.

## Consequences

- No ambiguity-preserving compatibility layer.
- Legacy inputs receive a stable unsupported-format error.
- New schemas can be strict and coherent.
- Migration tooling may be designed later as a separate product, not hidden ingestion.
