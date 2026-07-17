# ADR-0002 — MLX-First Apple Runtime with Qualified Linux Backends

**Status:** Provisional — accepted only after runtime qualification spikes pass

## Decision

MLX is mandatory for supported Apple Silicon model tensor execution. Linux is decision-grade through explicitly qualified MLX and/or PyTorch profiles. PyTorch is retained for pretrained models, Linux interoperability, and deployment conversion.

No universal tensor abstraction is promised. Backends expose capabilities and conformance evidence.

## Consequences

- Engines/evaluators target capability protocols.
- Cross-backend conversion creates derived artifact identities.
- Backend/task/operator/precision combinations may be quarantined.
- Native bundles remain guaranteed when optional export targets fail.
