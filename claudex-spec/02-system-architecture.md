# 02 — System Architecture

## 1. Architectural style

EvoNN MUST use a modular monorepo with explicit package boundaries and isolated worker processes. It MUST NOT begin as a multi-service distributed platform, but its executor protocol MUST permit future remote workers without changing domain contracts.

## 2. Layers

### 2.1 Product layer

- Web frontend
- Local API/control application
- CLI
- Project and policy services

### 2.2 Control layer

- Plan compiler
- Portfolio planner
- Durable job state machine
- Resource scheduler
- Worker supervisor
- Evidence and model selection service

### 2.3 Shared contract layer

- identity and version types
- configuration schemas
- dataset/task/metric registries
- budget and resource envelopes
- evaluation artifacts
- events and diagnostics
- model bundle manifests

### 2.4 Search layer

Distinct packages for:

- classical/pretrained contenders;
- family search;
- topology search;
- hierarchy search;
- primitive/motif search;
- adaptation/compression search;
- ensemble/routing synthesis.

No engine package may import another engine's internal search representation or coordinator.

### 2.5 Runtime layer

- MLX backend
- Linux production backend
- PyTorch interoperability backend
- preprocessing runtime
- training/evaluation runtime
- measurement and export capability probes

### 2.6 Data and storage layer

- transactional metadata database
- per-run analytical evidence database
- content-addressed artifact store
- verified download/cache store
- immutable native bundle store

## 3. Bounded components

| Component | Owns | Must not own |
|---|---|---|
| API/control application | authentication context, commands, queries, transactions | model training |
| Plan compiler | config resolution and validation | dynamic runtime scheduling |
| Portfolio planner | strategy selection and budget allocation | engine internals |
| Job orchestrator | state transitions, retries, cancellation | candidate scoring semantics |
| Scheduler | resource admission and worker assignment | scientific selection |
| Worker runtime | one isolated task attempt | global job state |
| Engine adapter | engine lifecycle and candidate proposals | shared metric authority |
| Training evaluator | training-data capability, model build/adaptation, training metrics, resources | test labels or confirmatory scoring |
| Validation evaluator | frozen validation capability, selection metrics, calibration candidates | optimizer updates or test labels |
| Final-refit evaluator | frozen selected structure/policy, train+validation capability, predeclared refit | candidate selection, policy changes, test inputs/labels |
| Confirmatory test evaluator | frozen-model inference and test-label scoring | training, adaptation, candidate selection, partial feedback |
| Evidence service | immutable comparisons and recommendation inputs | test-label release to search code |
| Artifact service | digest store, verification, retention | semantic invention |
| Export service | bundle materialization and conversion | training missing models |

## 4. Dependency rules

ARCH-001: Shared contracts MUST be dependency-light and MUST NOT import engines, Web code, or scheduler code.  
ARCH-002: Engines MAY depend on contracts, runtime protocols, and their own internals only.  
ARCH-003: The portfolio planner MUST communicate with engines through versioned adapter protocols.  
ARCH-004: Web and CLI MUST invoke the same application command handlers.  
ARCH-005: Workers MUST report events and artifacts; they MUST NOT write arbitrary control database rows.  
ARCH-006: Test-label access MUST exist only in a confirmatory evaluator process/capability that cannot train, adapt, calibrate, select, or return per-example/partial feedback to search components.  
ARCH-007: Exporters MUST open source evidence and model artifacts read-only.  
ARCH-008: Runtime backends MUST advertise capabilities instead of silently emulating unsupported operations.

## 5. Primary data flow

1. User command creates or modifies a draft.
2. Plan compiler resolves exact schemas, registries, assets, constraints, and capabilities.
3. Portfolio planner creates stages, probes, strategies, and budget partitions.
4. Job orchestrator commits the immutable plan and schedules tasks.
5. Scheduler assigns resource-qualified tasks to isolated workers.
6. Training/validation workers materialize only their phase-authorized inputs, execute one attempt, stage artifacts by digest, and emit immutable events.
7. Orchestrator transactionally commits the verified publication and attempt outcome, then schedules dependent work.
8. Evidence service derives candidate and job views from immutable artifacts.
9. User explicitly selects and freezes a candidate plus finalization policy.
10. Any refit/calibration occurs without test capability; afterward a separate confirmatory evaluator receives only the frozen model, test inputs, and test labels, and returns aggregate predeclared results.
11. Export service creates verified deployment artifacts from committed model/evidence artifacts.

## 6. Command/query separation

Mutations MUST pass through application commands with optimistic concurrency and explicit transactions. Monitoring and reporting SHOULD use read models derived from append-only events and durable state. Read endpoints MUST NOT initialize or migrate databases.

## 7. Isolation model

V1 uses one trusted local administrative domain, but candidate execution is not trusted to mutate control state. Workers MUST run in separate processes with:

- dedicated working directories;
- explicit resource limits;
- sanitized environment variables;
- network policy;
- bounded file access;
- separate stdout/stderr capture;
- controlled artifact publication;
- process-tree termination on cancel;
- no inherited database write handles.

Ray MAY provide scheduling and resource admission, but it is not a security boundary. OS process/container controls MUST provide isolation where hostile or externally sourced code could execute.

## 8. Future extension boundary

A future remote executor MAY implement the same task lease, capability advertisement, artifact, heartbeat, event, cancellation, and result protocols. No v1 product feature may require multi-host consensus or remote object storage.
