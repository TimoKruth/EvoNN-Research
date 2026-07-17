# 15 — Implementation Roadmap

This roadmap defines dependency order, not calendar promises. Each horizon ends with an executable product increment and conformance evidence.

## Horizon 0 — Foundations and spikes

- Verify technology decisions and licenses.
- Establish monorepo/package boundaries.
- Define canonical IDs, strict schemas, events, and error taxonomy.
- Implement metadata DB/migrations and content store.
- Prove MLX Mac and Linux backend skeletons.
- Prove isolated task execution and cancellation.
- Establish CI on Linux and Apple Silicon.

Exit gate: a versioned no-op job can be created through CLI/API, executed by a worker, persisted transactionally, resumed after restart, and inspected read-only.

## Horizon 1 — Data product and protected evaluation

- Dataset descriptors, acquisition, hostile-archive defenses.
- Tabular/image/text/audio/time-series ingestion.
- Stable sample IDs, splits, preprocessing graph.
- Task/metric registries and golden vectors.
- Physical test-label capability separation.
- Dataset Web and CLI flows.

Exit gate: representative datasets produce immutable versions, protected splits, validation reports, and deterministic materializations on Mac and Linux.

## Horizon 2 — Baselines and unified evaluation artifacts

- Classical contenders.
- Simple MLX/PyTorch neural baselines.
- Evaluation artifact and per-run DuckDB.
- Budget/resource measurement.
- Evidence leaderboard and recommendation skeleton.

Exit gate: the product selects and exports a baseline model without evolutionary search.

## Horizon 3 — Automatic portfolio MVP

- Portfolio planning/probes/allocation.
- Family engine.
- Pretrained/PEFT engine.
- Ray-backed resource scheduling.
- Multi-fidelity/promotion.
- Live Web job monitoring and full CLI flow.

Exit gate: automatic mode completes end to end for representative tabular, image, text, and time-series tasks.

## Horizon 4 — Topology, hierarchy, motifs, and QD

- Topology engine with correct innovation/speciation.
- Hierarchy/cell engine.
- Primitive/motif engine.
- Typed transfer artifacts.
- QD/MAP-Elites and multi-objective archives.
- Portfolio governance and evidence promotion.

Exit gate: engines remain independent but can participate in one portfolio and exchange validated artifacts.

## Horizon 5 — Broad multimodal and hybrid synthesis

- Joined multimodal data and fusion candidates.
- Audio and compact causal LM workflows.
- Ensemble/routing/cascade engine.
- Distillation/compression engine.
- Strong overlap/contamination checks for external models.

Exit gate: every required v1 modality/task class has at least one complete automatic workflow and deployment bundle.

## Horizon 6 — Deployment hardening

- Native bundle verifier.
- Core ML capability planning, conversion, parity.
- Optional ONNX/ExecuTorch targets.
- Quantization, size/latency/memory constraints.
- Model cards, licenses, SBOM, signatures.

Exit gate: release-gate models independently run from clean bundles on supported targets.

## Horizon 7 — Product hardening and v1 release

- Accessibility completion.
- Fault injection and crash recovery.
- Security review and supply-chain gates.
- Performance/scale envelopes.
- Documentation and onboarding.
- Scheduled scientific qualification campaigns.

Exit gate: all v1 MUST requirements and acceptance criteria have linked evidence.

## Deferred horizons

- remote/multi-host executor;
- stable public Python SDK;
- remote service API;
- hosted collaboration;
- plugin marketplace;
- enterprise identity/multi-tenancy;
- automated production deployment.
