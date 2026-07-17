# 13 — Testing, Conformance, and Release Gates

## 1. Test strategy

The suite MUST combine:

- unit tests;
- property-based tests;
- contract/schema tests;
- migration tests;
- integration tests;
- engine/runtime tests;
- deterministic resume tests;
- fault-injection tests;
- security tests;
- Web/API/CLI end-to-end tests;
- scientific acceptance campaigns;
- deployment parity tests.

Test counts in prose are non-authoritative; CI artifacts are authoritative.

TEST-001: Every applicable capitalized requirement MUST map to at least one test, inspection, analysis, or signed evidence item before release.  
TEST-002: Machine-readable traceability MUST identify requirement/section parent, schema or validator, acceptance criterion, and release evidence.  
TEST-003: A passing unit test alone is insufficient for requirements that specify runtime, recovery, security, accessibility, or scientific behavior.  
TEST-004: Waived SHOULD requirements MUST include owner, rationale, user impact, and expiry/review date.

## 2. Unit and property testing

Property-based tests MUST cover:

- graph/genome repair and validity;
- content-addressed identity stability;
- mutation/crossover invariants;
- split stability and no overlap;
- schema round-trips;
- state-machine legal transitions;
- budget accounting conservation;
- artifact path safety;
- metric edge cases;
- idempotency and duplicate events.

## 3. Contract conformance

Golden fixtures MUST include valid and invalid:

- configs;
- dataset/benchmark descriptors;
- splits;
- task/metric entries;
- candidate specs;
- evaluation artifacts;
- checkpoints;
- native bundles;
- backend capability manifests.

Unknown fields, version mismatch, missing provenance, nonfinite values, invalid states, corrupt digests, and unsafe paths MUST be exercised.

## 4. Data/leakage tests

Fixtures MUST cover duplicates, transformed copies, shared entities, temporal leakage, geographic leakage, target proxies, global preprocessing, shared caches, foundation-model overlap, multimodal mismatch, unseen categories, empty/singleton partitions, and repeated test queries.

Physical test-label isolation MUST be exercised end to end.

## 5. Runtime qualification

Each supported host/backend matrix entry requires:

- installation/import tests;
- operator golden tests;
- gradient/training tests;
- task/modality smoke training;
- deterministic/statistical repeat tests;
- serialization tests;
- cross-backend parity where claimed;
- memory/latency measurement sanity;
- OOM/timeout failure semantics.

## 6. Resume and crash consistency

Tests MUST compare uninterrupted and resumed runs under deterministic profiles. Fault injection MUST cover process kill, worker loss, checkpoint interruption, database rollback, disk full, corrupt checkpoint, stale lease, duplicate event, and host restart reconciliation.

## 7. Web/CLI/API

- API schema and error envelope tests;
- Web/CLI configuration equivalence;
- Playwright browser tests on supported engines;
- keyboard and accessibility tests;
- stale mutation/conflict tests;
- live reconnect and event-gap tests;
- non-interactive CLI and JSON stability;
- local security tests for CSRF/CORS/host/path access.

## 8. Deployment

Every release-gate modality requires:

- native bundle creation;
- bundle tamper detection;
- independent inference;
- preprocessing parity;
- safe loading;
- compatible and incompatible Core ML cases;
- numerical parity and failure labeling;
- offline dependency behavior.

## 9. Scientific quality gates

A search-engine advancement cannot merge based only on unit tests. It MUST include:

- exact code and registry versions;
- baseline and contender comparisons;
- finite budgets and accounting;
- repeated seeds when claim scope requires;
- effect size/uncertainty;
- failure and missingness report;
- runtime/resource effect;
- evidence bundle and explicit decision category.

## 10. CI lanes

### Portable Linux lane

Schemas, metadata, orchestration, CLI/API/Web, security, data contracts, classical models, and qualified Linux runtimes.

### Apple Silicon MLX lane

MLX engines, training, deterministic profiles, Core ML conversion, and native bundle verification.

### Cross-platform conformance lane

Shared golden candidates/data and tolerance comparison.

### Scheduled scientific lane

Representative portfolio campaigns with promoted evidence, not required on every commit.

## 11. Quality tools

The implementation SHOULD use uv, Ruff, Pyright or strict mypy, pytest, Hypothesis, Playwright, coverage reporting, dependency audit, SBOM generation, and secret/static security scanning.

## 12. Release gate

A release is acceptable only when:

1. all applicable MUST requirements have passing evidence;
2. all schemas and migrations are validated;
3. supported platform matrix is green;
4. deterministic resume and crash recovery pass;
5. Web and CLI core journeys pass;
6. security and supply-chain gates pass;
7. native bundles pass for all gate modalities;
8. Core ML includes positive and negative cases;
9. accessibility receives automated and manual review;
10. known limitations and quarantines are published;
11. no hidden legacy compatibility was introduced;
12. release artifacts and SBOM are signed or otherwise integrity-verifiable.
