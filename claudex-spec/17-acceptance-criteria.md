# 17 — Product Acceptance Criteria

## 1. Core workflow

| ID | Criterion |
|---|---|
| ACCEPT-001 | A new user completes the guided Web flow from local tabular dataset to verified native bundle without CLI or expert mode. |
| ACCEPT-002 | An automated script completes project creation, dataset finalization, plan, detached job, evidence, selection, finalization, export, and verification through CLI JSON output. |
| ACCEPT-003 | Equivalent Web and CLI inputs produce the same frozen effective plan digest. |
| ACCEPT-004 | The core workflow operates without vendor account or network access when assets are local. |

## 2. Data and modalities

| ID | Criterion |
|---|---|
| ACCEPT-010 | Representative tabular, image, text, audio, time-series/sequence, compact language-model, and joined multimodal fixtures complete the full product path. |
| ACCEPT-011 | Changed source bytes, target semantics, split policy, join policy, or preprocessing produces a distinct dataset-version digest. |
| ACCEPT-012 | Corrupt, duplicate, unmatched, leaking, privacy-restricted, and license-unknown fixtures fail with correct machine reason codes. |
| ACCEPT-013 | Search workers cannot read protected test labels; an attempted access is denied and audited. |
| ACCEPT-014 | Foundation-model/retrieval overlap metadata changes candidate evidence eligibility as specified. |

## 3. Search portfolio

| ID | Criterion |
|---|---|
| ACCEPT-020 | Automatic mode generates a valid portfolio and rationale for each gate modality/task. |
| ACCEPT-021 | Expert-disabled strategies remain absent from plan and execution. |
| ACCEPT-022 | Strong classical/pretrained baselines receive reserved budget before speculative search dominates. |
| ACCEPT-023 | Adaptive allocation changes are visible and budget-conserving. |
| ACCEPT-024 | No feasible candidate is reported honestly with nearest violations, not a false recommendation. |
| ACCEPT-025 | Transfer artifacts carry source, converter, compatibility, and prior-cost policy. |

## 4. Budgets and evidence

| ID | Criterion |
|---|---|
| ACCEPT-030 | Candidate, optimizer-step, wall-clock, failure, retry, cache, and prior counters reconcile to immutable evaluation artifacts. |
| ACCEPT-031 | Low-fidelity cache entries cannot satisfy high-fidelity tasks. |
| ACCEPT-032 | Heterogeneous raw metrics are never directly averaged in a product recommendation. |
| ACCEPT-033 | Missing and failed runs remain visible in aggregate evidence. |
| ACCEPT-034 | Test evaluation count and access history are present in selected-model evidence. |

## 5. Workers and recovery

| ID | Criterion |
|---|---|
| ACCEPT-040 | Four lightweight isolated attempts run concurrently on a suitable host without sharing mutable workspaces. |
| ACCEPT-041 | Killing one worker leaves unrelated work and committed evidence intact. |
| ACCEPT-042 | Host restart reconciles prior running work into `paused` with a verified resume point, `failed`, or `abandoned`; it MUST NOT leave work indefinitely `interrupted` or invent a nonexistent `resumed` lifecycle state. |
| ACCEPT-043 | Uninterrupted and resumed deterministic fixture runs match the declared equivalence class. |
| ACCEPT-044 | Stale lease results cannot overwrite a newer attempt. |
| ACCEPT-045 | Disk-full/checkpoint-kill faults never create a completed-looking corrupt artifact. |

## 6. Runtime portability

| ID | Criterion |
|---|---|
| ACCEPT-050 | Supported Apple Silicon MLX and Linux backend matrices pass exact operator/task qualification suites. |
| ACCEPT-051 | Cross-backend golden candidates fall within declared tolerances or are quarantined. |
| ACCEPT-052 | Unsupported operator/precision combinations fail during planning or preflight. |
| ACCEPT-053 | Platform performance comparisons share measurement boundaries and environment metadata. |

## 7. Web, CLI, and accessibility

| ID | Criterion |
|---|---|
| ACCEPT-060 | Material durable events appear in a connected Web client within five seconds under normal local load. |
| ACCEPT-061 | Client disconnect/reconnect does not alter execution and restores missed events or reports a gap. |
| ACCEPT-062 | Acceptance-critical Web flows are keyboard-operable and pass WCAG 2.2 AA review. |
| ACCEPT-063 | Decision-relevant charts have accessible tabular/text equivalents. |
| ACCEPT-064 | CLI remains understandable with color, animation, glyphs, hyperlinks, and cursor control disabled. |

## 8. Deployment

| ID | Criterion |
|---|---|
| ACCEPT-070 | Every gate model produces a native bundle containing safe model data, preprocessing, schemas, provenance, evidence, licenses, and checksums. |
| ACCEPT-071 | Tampering or removing any required file causes verification failure. |
| ACCEPT-072 | An embedded verified bundle runs inference in a clean environment without the search workspace; a content-addressed-local bundle runs with only its exact declared local dependencies present and fails deterministically when one is absent. |
| ACCEPT-073 | Compatible Core ML fixture passes conversion and parity; incompatible fixture reports blockers before conversion. |
| ACCEPT-074 | Parity failure cannot be marked verified and does not invalidate the native bundle. |

## 9. Security and privacy

| ID | Criterion |
|---|---|
| ACCEPT-080 | Path traversal, symlink escape, decompression bomb, unsafe pickle, and remote-code fixtures are blocked. |
| ACCEPT-081 | Undeclared worker network request is denied and audited. |
| ACCEPT-082 | Credentials and private paths do not appear in logs, reports, diagnostics, or bundles. |
| ACCEPT-083 | Local Web state-changing endpoints reject CSRF/origin/host violations. |
| ACCEPT-084 | Release produces dependency inventory, SBOM, vulnerability results, license report, and integrity-verifiable artifacts. |

## 10. Clean break

| ID | Criterion |
|---|---|
| ACCEPT-090 | Legacy configs, databases, runs, and models return a stable unsupported-format error and are not silently interpreted. |
| ACCEPT-091 | Public workflows do not depend on predecessor command names or semantics. |
