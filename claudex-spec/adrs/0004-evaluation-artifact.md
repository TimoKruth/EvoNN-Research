# ADR-0004 — One Canonical Evaluation Artifact

**Status:** Accepted

## Decision

Fitness, metrics, resources, checkpoint, weights, failure status, budget, dataset/split/preprocessing identity, seeds, and backend identity for one candidate attempt are owned by one immutable `EvaluationArtifact`.

Reporting/export MUST NOT retrain a candidate or infer a metric from unrelated fitness.

## Consequences

- Consistent selection and reporting.
- Precise budget accounting.
- Larger but auditable artifact model.
- Engines must adapt their internal outputs to the shared artifact.
