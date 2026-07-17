# EvoNN Claudex Specification

**Specification ID:** `claudex-spec`  
**Version:** 1.0.0-draft  
**Status:** Normative design baseline  
**Date:** 2026-07-17  
**Product:** EvoNN — local-first multimodal model discovery and deployment

## Purpose

This suite specifies a clean-slate EvoNN product derived from the strongest ideas, plans, implementations, and lessons in the existing EvoNN research ecosystem. It is not a compatibility specification and does not preserve old commands, schemas, repositories, or ambiguous semantics.

EvoNN is specified as an open-source model-building product for technical practitioners. A user supplies a modeling problem and constraints; EvoNN validates the data, establishes strong baselines, automatically allocates budget across multiple model-discovery strategies, selects a model using protected evidence, and emits a verified native inference bundle plus Core ML output when supported.

## Normative language

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are interpreted as described by RFC 2119 and RFC 8174 when capitalized.

Capitalized normative clauses are binding whether or not they carry an explicit identifier. Explicit identifiers are permanent cross-document anchors; a removed identifier remains reserved and MUST NOT be reassigned. Before implementation freeze, every capitalized clause MUST appear in the machine-readable traceability index or inherit an explicit parent requirement there.

## Document map

| Document | Scope |
|---|---|
| [00-charter.md](00-charter.md) | Mission, principles, scope, non-goals, success definition |
| [01-product-and-ux.md](01-product-and-ux.md) | Product objects, user journeys, Web and CLI behavior |
| [02-system-architecture.md](02-system-architecture.md) | Modular platform architecture and component boundaries |
| [03-domain-and-contracts.md](03-domain-and-contracts.md) | Canonical identities, schemas, lifecycle models, protocol rules |
| [04-data-and-benchmarks.md](04-data-and-benchmarks.md) | Dataset governance, splits, tasks, metrics, leakage prevention |
| [05-search-portfolio.md](05-search-portfolio.md) | Portfolio planner, distinct engines, transfer, adaptation, ensembles |
| [06-training-evaluation-and-budgets.md](06-training-evaluation-and-budgets.md) | Evaluation artifacts, resource accounting, statistics, reproducibility |
| [07-orchestration-and-reliability.md](07-orchestration-and-reliability.md) | Workers, scheduling, transactions, resume, cancellation, crash recovery |
| [08-persistence-and-artifacts.md](08-persistence-and-artifacts.md) | Metadata stores, analytical evidence, content-addressed artifacts, bundles |
| [09-runtime-and-portability.md](09-runtime-and-portability.md) | MLX, Linux, PyTorch interoperability, backend conformance |
| [10-web-cli-and-observability.md](10-web-cli-and-observability.md) | Local Web application, CLI taxonomy, events, logs, metrics, accessibility |
| [11-deployment-and-inference.md](11-deployment-and-inference.md) | Native bundle, Core ML, conversion gates, inference validation |
| [12-security-privacy-and-supply-chain.md](12-security-privacy-and-supply-chain.md) | Network policy, hostile artifacts, safe serialization, SBOM and signing |
| [13-testing-and-release.md](13-testing-and-release.md) | Test pyramid, conformance, scientific gates, release criteria |
| [14-technology-decisions.md](14-technology-decisions.md) | Researched stack choices and validation gates |
| [15-roadmap.md](15-roadmap.md) | Implementation horizons and dependency ordering |
| [16-traceability-risks-glossary.md](16-traceability-risks-glossary.md) | Traceability, major risks, glossary |
| [17-acceptance-criteria.md](17-acceptance-criteria.md) | End-to-end product acceptance matrix |
| [18-v1-conformance-matrix.md](18-v1-conformance-matrix.md) | Mandatory modality/task/backend/engine and host classes |
| [19-research-interop.md](19-research-interop.md) | Typed import channels, dossiers, and trust ladder for consuming the claude-spec research platform |
| [research/source-project-lessons.md](research/source-project-lessons.md) | Preserve/fix/reject mapping from the source ecosystem |
| [research/bibliography.md](research/bibliography.md) | Technology research sources |
| [adrs/](adrs/) | Architecture decisions |
| [schemas/](schemas/) | Normative schema exemplars |
| [examples/](examples/) | Non-normative configuration examples |

## Specification precedence

When documents conflict, precedence is:

1. This README and `00-charter.md`
2. Explicit normative requirements in numbered documents
3. Architecture decision records
4. JSON Schema exemplars
5. Examples and explanatory notes
6. Research notes and bibliography

A future implementation MUST publish its own conformance statement identifying the exact versions of this specification, registries, schemas, and validators it implements.

## Core product contract

EvoNN v1 is conformant only if it can:

1. Onboard and validate representative tabular, image, text, audio, sequence/time-series, language-model, and multimodal tasks.
2. Prevent test and validation leakage through physical capability boundaries, not only conventions.
3. Run an automatic, evidence-driven portfolio across distinct model-discovery strategies.
4. Execute on one macOS or Linux host using isolated workers.
5. Use MLX for supported Apple Silicon model tensor execution and provide decision-grade Linux execution.
6. Preserve exact provenance, budget accounting, failures, retries, and model lineage.
7. Select models under explicit quality, latency, memory, size, export, privacy, and platform constraints.
8. Produce and independently verify a dependency-complete native inference bundle: all required bytes are either embedded or bound to exact locally resolvable content-addressed dependencies, with offline verification.
9. Produce Core ML output only when conversion and numerical parity gates pass.
10. Operate without a paid cloud dependency or mandatory vendor account.
