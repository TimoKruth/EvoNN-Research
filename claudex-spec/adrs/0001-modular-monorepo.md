# ADR-0001 — Modular Monorepo with Distinct Search Engines

**Status:** Accepted

## Context

The predecessor ecosystem demonstrated value from family, topology, hierarchy, and primitive search, but also accumulated repository, contract, and orchestration drift. A universal engine would erase useful inductive biases; a local microservice platform would add premature operations cost.

## Decision

Use one `uv` monorepo containing a shared product/control substrate and separate engine packages. Engines communicate through versioned contracts and MUST NOT import one another's internal search representations.

Compute runs in isolated worker processes. A future remote executor may implement the same protocol.

## Consequences

- One product and release process.
- Strong package boundary enforcement is mandatory.
- Cross-engine transfer requires typed artifacts/converters.
- No multi-host control plane in v1.
