# 16 — Traceability, Risk Register, and Glossary

## 1. Requirement families

| Prefix | Area |
|---|---|
| CHARTER | Mission and immutable principles |
| PRD / UX / CLI | Product behavior and interfaces |
| ARCH | Architecture boundaries |
| DOM / CFG | Domain identities and configuration |
| DATA | Data, governance, splits, preprocessing |
| PORT / SEARCH | Portfolio and engine behavior |
| TRAIN / EVAL / BUD / REPRO | Training, metrics, budgets, reproducibility |
| STORE | Persistence and artifacts |
| RUNTIME | Backend and portability |
| OBS | Events/logs/metrics/UI truth |
| DEP | Export and inference |
| SEC | Security/privacy/supply chain |
| TEST | Conformance and release |

Implementation work MUST link code, tests, migrations, and acceptance evidence to relevant requirement IDs.

## 2. High-level traceability

| Goal | Primary documents | Acceptance evidence |
|---|---|---|
| Guided data-to-model product | 01, 10, 11 | Web and CLI end-to-end tests |
| Broad multimodal support | 04, 05, 06 | modality/task conformance fixtures |
| Automatic search portfolio | 05 | plan/execution/reallocation evidence |
| Scientific isolation | 04, 06 | test-label capability and leakage tests |
| One-host many workers | 02, 07 | concurrency, fault-containment, recovery tests |
| MLX Mac + Linux decision grade | 09, 13 | backend qualification matrix |
| Verified deployment | 08, 11 | bundle tamper and parity tests |
| Local/open/security posture | 12, 14 | security review, offline flow, SBOM |

## 3. Risk register

| Risk | Impact | Required mitigation |
|---|---|---|
| Broad multimodal v1 becomes unimplementable | schedule/quality | staged roadmap; conformance per modality; no placeholder support claims |
| Test leakage through caches or hybrid transfer | invalid models | capability isolation, audit events, provenance labels, fresh holdouts |
| Foundation-model pretraining overlaps test data | overstated evidence | contamination policy, source/cutoff recording, claim qualification |
| Cross-backend numerical drift | inconsistent selection | capability matrix, golden tests, tolerance quarantine |
| Ray assumed to be sandbox | code/data compromise | OS isolation, trusted-network limits, no arbitrary plugins |
| SQLite writer bottleneck | stalled control plane | single writer, batching, load spike, optional PostgreSQL profile |
| DuckDB concurrent writer misuse | corruption/locks | one per-run writer lease; readers read-only |
| Unsafe downloaded model serialization | RCE | safetensors/skops, no untrusted pickle, quarantine |
| Core ML conversion overpromised | deployment failure | capability gate and mandatory parity |
| Raw heterogeneous metrics averaged | wrong selection | registry-defined utility and explicit weighting |
| Resume not equivalent | irreproducible evidence | atomic checkpoints, RNG and scheduler state, equivalence tests |
| Prior/pretraining treated as free | unfair claims | explicit prior-cost classes and scope-limited claims |
| Automatic planner hides decisions | low trust | frozen plans, rationale events, expert override |
| Evidence becomes stale after code changes | wrong portfolio role | code-range compatibility and automatic stale markers |
| License/privacy ambiguity | legal/privacy harm | fail closed, component-level notices, governance events |
| Local Web exposed beyond loopback | unauthorized access | loopback default, auth, host/origin/CSRF/CORS controls |

## 4. Glossary

- **Artifact:** immutable content-addressed blob or manifest produced or consumed by EvoNN.
- **Backend:** numerical runtime implementation such as MLX or PyTorch.
- **Benchmark:** versioned dataset/task/metric/evaluation protocol.
- **Candidate:** immutable proposed model/training/external-asset specification.
- **Capability:** explicit supported operation under exact backend/platform conditions.
- **Decision-grade:** evidence eligible for product or scientific claims after all required gates pass.
- **Engine:** one model-discovery strategy with its own representation and policy.
- **Evaluation artifact:** complete immutable truth for one attempted candidate execution.
- **Fidelity:** declared approximation level of an evaluation.
- **Hard constraint:** requirement that must be satisfied for ordinary recommendation.
- **Native bundle:** canonical self-contained EvoNN inference package.
- **Portfolio planner:** component that selects and allocates budget across strategies.
- **Prior:** external or previously discovered information supplied to a candidate/search.
- **Promoted evidence:** durable validated evidence used for portfolio or product decisions.
- **Root seed:** job seed from which named deterministic RNG streams derive.
- **Split artifact:** immutable sample-role assignment and split-generation record.
- **Utility:** normalized higher-is-better benchmark-specific value used for aggregation.
- **Worker lease:** time-bounded authorization for one worker attempt to commit results.

## 5. Open implementation validations, not open requirements

The product requirements are fixed by this suite. The following must be validated during implementation without weakening them:

- exact pinned frontend/component/chart libraries;
- exact MLX Linux qualification surface;
- Core ML conversion coverage for MLX-native candidates;
- whether SQLite remains sufficient at measured event volume;
- whether optional MLflow/DVC adds enough value to justify inclusion;
- desktop packaging mechanism after the `uv` workflow is stable.
