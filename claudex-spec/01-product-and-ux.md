# 01 — Product and User Experience

## 1. Canonical product objects

- **Project:** durable container for objective, dataset versions, defaults, jobs, evidence, models, and exports.
- **Dataset version:** immutable, fingerprinted data contract and split policy.
- **Plan:** resolved proposal describing search portfolio, budget, constraints, network access, and resources.
- **Job:** immutable execution record for search, finalization, evaluation, or export verification.
- **Candidate:** one model specification evaluated under one identity and policy.
- **Evaluation artifact:** immutable result of one candidate × benchmark/split × fidelity × seed attempt.
- **Model version:** explicitly selected or finalized candidate with immutable lineage.
- **Export:** immutable deployment artifact derived from a model version.

## 2. Product requirements

| ID | Requirement |
|---|---|
| PRD-001 | Web and CLI MUST operate on the same durable objects and effective configuration. |
| PRD-002 | A Web or CLI action MUST become visible through the other interface without manual synchronization. |
| PRD-003 | Automatic mode MUST not require users to understand engine names or search operators. |
| PRD-004 | Expert mode MUST expose the fully resolved portfolio and permit disabling or constraining eligible strategies. |
| PRD-005 | Expert-disabled strategies MUST NOT be silently re-enabled. |
| PRD-006 | Every job MUST freeze an immutable base envelope containing dataset, split, metrics, initial budget, constraints, network policy, runtime capabilities, and software environment before execution. Effective budget changes occur only through separate append-only amendment objects. |
| PRD-007 | Retry, resume, clone, amend, pause, cancel, finalize, and export MUST have distinct semantics. |
| PRD-008 | A job that completes execution without a feasible candidate MUST be presented as execution-complete but model-selection-unsuccessful. |
| PRD-009 | Model recommendation MUST remain separate from explicit user selection. |
| PRD-010 | Selecting a candidate with unknown or violated hard constraints MUST require an explicit override reason. |
| PRD-011 | Finalization MUST create a new auditable job when refitting, calibration, compression, or test evaluation is required. |
| PRD-012 | Destructive operations MUST state the affected objects and retained lineage before confirmation. |
| PRD-013 | A budget amendment MUST NOT mutate the base envelope; the effective budget is the deterministic fold of the base budget plus ordered valid amendments, each with its own digest. |

## 3. Required user journeys

### 3.1 Guided Web journey

1. Create project and modeling objective.
2. Add local or policy-approved remote data.
3. Inspect inferred modality, schema, target, groups, time fields, and risks.
4. Resolve blocking validation findings.
5. Finalize immutable dataset version and protected splits.
6. Select budget preset or exact limits and deployment constraints.
7. Review automatic portfolio plan and online access.
8. Start job and monitor live progress.
9. Compare feasible candidates and recommendation.
10. Explicitly select candidate.
11. Finalize and perform evaluator-controlled test scoring.
12. Export and verify native bundle; optionally export Core ML.

UX-001: This journey MUST be completable without CLI or expert controls.

### 3.2 Reproducible CLI journey

The CLI MUST support the same path non-interactively with structured JSON output, explicit identifiers, idempotency protection, and no prompts when all decisions are supplied.

### 3.3 Multimodal journey

The product MUST expose join coverage, duplicate IDs, unmatched records, modality availability, timing alignment, and the impact of missing-modality policy on candidate eligibility.

### 3.4 Failure recovery journey

A worker failure MUST leave unrelated work running, preserve the failed attempt and diagnostics, and offer only state-valid recovery actions.

## 4. Job lifecycle

User-visible states:

`draft → validating → queued → running → pausing → paused → resuming → running`

Terminal outcomes:

`completed | failed | cancelled | invalidated | abandoned`

`interrupted` is a non-terminal reconciliation state. `resumed_nondeterministically` is a repeatability annotation on a resumed attempt/job, not a lifecycle state.

Rules:

- state transitions MUST be serialized and append-only;
- `completed` MUST NOT imply a feasible or selected model;
- `paused` MUST mean a verified resumable checkpoint exists;
- `interrupted` MUST be reconciled after startup into `paused` with a verified resume point, `failed`, or `abandoned`;
- cancellation MUST stop new scheduling and preserve valid completed evidence;
- closing the browser or terminal watcher MUST NOT cancel a job.

## 5. CLI taxonomy

The executable name is `evonn`.

```text
evonn project create|list|show|update|archive|restore|delete
evonn dataset add|inspect|validate|finalize|list|show|diff|remove
evonn plan create|show|validate|diff
evonn job run|list|show|watch|events|logs|pause|resume|cancel|retry|clone|amend-budget
evonn worker list|show|drain|activate|stop
evonn evidence leaderboard|compare|report|audit
evonn model list|show|select|finalize|export|verify|predict
evonn policy network show|set|check
evonn doctor
evonn version
evonn completion
```

CLI-001: Acceptance-critical commands MUST support `--json`.  
CLI-002: Read-only commands MUST NOT mutate state.  
CLI-003: Mutating commands MUST return created or changed object IDs.  
CLI-004: Non-interactive mode MUST fail instead of accepting unsafe defaults.  
CLI-005: Watching interruption MUST NOT cancel the watched job.  
CLI-006: Secrets and protected paths MUST be redacted.  
CLI-007: Output MUST remain usable without color, animation, hyperlinks, or cursor control.

## 6. Web information architecture

Required areas:

- Projects
- Dataset registry and onboarding
- Plans
- Jobs and live monitoring
- Candidate evidence and comparison
- Selected models
- Exports and verification
- Workers and host resources
- Policies and settings
- Diagnostics and system information

The default job page MUST answer:

1. What is happening?
2. What has been learned?
3. What budget remains?
4. Are hard constraints being met?
5. Is user action required?

## 7. Accessibility

The Web application MUST meet WCAG 2.2 AA for acceptance-critical flows. It MUST support keyboard-only operation, visible focus, non-color status cues, labeled forms, controlled live regions, reduced motion, 200% zoom, accessible tables for decision-relevant charts, and stable focus during live updates.

## 8. Error contract

Every actionable error MUST include:

- stable error code;
- concise summary;
- affected object/operation;
- category;
- likely cause when known;
- whether durable state was created;
- whether retry is safe;
- concrete recovery action;
- diagnostic reference.

Raw stack traces MUST NOT replace user-facing errors. Diagnostic traces MAY be retained with redaction.
