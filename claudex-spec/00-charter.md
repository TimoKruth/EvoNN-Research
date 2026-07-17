# 00 — Product Charter

## 1. Mission

EvoNN MUST make advanced model discovery usable as a trustworthy local product rather than a collection of research scripts. It MUST optimize for the best deployable model for the user's data and constraints while retaining enough scientific rigor to explain, reproduce, challenge, and improve every decision.

## 2. Product identity

EvoNN is:

- an open-source local application;
- a broad multimodal model-building system;
- an automatic portfolio optimizer over heterogeneous model sources;
- a reproducible experiment and evidence system;
- a model selection and deployment preparation product;
- a platform containing multiple distinct search engines behind shared contracts.

EvoNN is not primarily a benchmark leaderboard, a single NAS algorithm, a cloud service, or a universal tensor framework.

## 3. Guiding principles

| ID | Requirement |
|---|---|
| CHARTER-001 | User value MUST be defined by obtaining a validated deployable model, not merely completing a search run. |
| CHARTER-002 | Search strategies MUST remain scientifically distinct internally; shared infrastructure MUST NOT force one universal genome. |
| CHARTER-003 | Automatic behavior MUST be inspectable, reproducible, and overridable by technical practitioners. |
| CHARTER-004 | Data, metrics, budgets, prior knowledge, failure, and deployment constraints MUST be first-class contracts. |
| CHARTER-005 | Raw metric values, normalized utility, search objectives, and product recommendations MUST remain distinct concepts. |
| CHARTER-006 | Test labels MUST remain outside training and selection capabilities until the selected candidate is frozen. |
| CHARTER-007 | Missing, unsupported, skipped, ineligible, failed, interrupted, and invalidated MUST remain distinguishable. |
| CHARTER-008 | Export MUST be a pure, read-only materialization operation; it MUST NOT train, repair, or fabricate missing evidence. |
| CHARTER-009 | Every promoted model MUST be independently verifiable without the search workspace. |
| CHARTER-010 | Platform differences MUST be measured and qualified; Linux MUST NOT be described as decision-grade merely because code imports. |
| CHARTER-011 | Controlled network access MAY occur, but silent data upload and implicit executable downloads MUST NOT occur. |
| CHARTER-012 | Essential product use MUST NOT require paid cloud services. |
| CHARTER-013 | Clean-slate semantics take precedence over backward compatibility. |
| CHARTER-014 | Security, privacy, licensing, and provenance uncertainty MUST fail closed for decision-grade work. |
| CHARTER-015 | The simplest architecture that satisfies product and evidence requirements SHOULD be preferred over premature distributed complexity. |

## 4. Required v1 problem surface

V1 MUST provide end-to-end product workflows for:

- tabular classification and regression;
- image classification and scalar/multilabel prediction;
- text classification, embedding, and compact causal language modeling;
- audio classification and regression;
- sequence classification and regression;
- time-series forecasting;
- declared multimodal combinations with stable sample alignment.

Support means ingestion, validation, training/search, model selection, export, inference verification, Web operation, and CLI operation. Shape-compatible placeholder data does not count as support.

## 5. Model universe

The v1 portfolio MUST implement all strategy branches listed below, although individual branches MAY be ineligible for specific tasks and MUST advertise that ineligibility before execution:

- classical linear, tree, kernel, nearest-neighbor, and probabilistic estimators;
- curated neural architecture families;
- evolved flat computation graphs;
- evolved hierarchical reusable cells;
- evolved primitives and motifs;
- pretrained backbones and foundation models;
- parameter-efficient adapters;
- quantized and compressed variants;
- ensembles, routers, cascades, and mixture systems;
- cross-strategy hybrids.

Every candidate MUST identify its origin, external assets, license, base model, tokenizer or processor, training policy, data access, prior-compute class, resource consumption, and deployment dependencies. Compact causal LM support is bounded by `18-v1-conformance-matrix.md`; registry extensibility does not imply unrestricted generative-media support.

## 6. User and operating model

The primary user is a technical practitioner: data scientist, ML engineer, domain scientist, or NAS practitioner.

V1 MUST provide:

- a first-class local Web application;
- a first-class CLI over the same state;
- guided, automatic, and expert modes;
- one-host multi-worker execution;
- native Apple Silicon execution through MLX;
- decision-grade Linux execution;
- controlled online acquisition;
- native inference bundles and conditional Core ML export.

## 7. Non-goals

V1 does not require:

- compatibility with any prior EvoNN command, schema, run, database, or model artifact;
- multi-host or cloud cluster scheduling;
- a hosted account, billing, telemetry service, or managed inference endpoint;
- a public stable Python SDK;
- a public remote service API;
- arbitrary user-supplied executable plugins;
- automatic production infrastructure provisioning;
- universal Core ML or ONNX conversion;
- reinforcement learning or unrestricted generative media training;
- multi-tenant authorization.

## 8. Definition of success

A v1 release is successful when a technical practitioner can provide supported data, approve task semantics, set a finite budget and constraints, run an automatic portfolio, inspect the evidence, explicitly select a candidate, finalize it without test contamination, export a verified native bundle, and reproduce the decision on a supported host within declared tolerances.
