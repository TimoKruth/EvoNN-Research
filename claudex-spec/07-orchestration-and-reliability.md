# 07 — Orchestration, Workers, and Reliability

## 1. Durable state machine

The control plane MUST own job state. Workers report leases, heartbeats, events, checkpoints, and outcomes; they MUST NOT decide durable global transitions.

Required entities:

- job
- stage
- task
- task attempt
- worker
- resource lease
- artifact publication
- checkpoint
- command/idempotency record

## 2. Task states

`planned | ready | leased | preparing | running | checkpointing | completed | pruned | retry_wait | failed | interrupted | cancelled | invalid`

Every transition MUST be persisted transactionally with expected prior version. Stale transitions MUST be rejected.

### Outcome aggregation

- An attempt terminal outcome updates its task only if the attempt holds the current lease.
- An `ok` or `budget_exhausted_valid` attempt may complete a task when the task policy accepts valid partial-budget evidence.
- `pruned`, `ineligible`, `unsupported`, and `skipped` complete an optional task with the same explicit non-success outcome; they complete a required task only if the frozen plan declares that outcome acceptable.
- A task is ordinarily `completed` only after one accepted successful/valid terminal attempt and artifact commit; its retained outcome remains more specific than the generic state.
- A task is `failed` after its retry policy is exhausted; earlier failed attempts remain history.
- A job is `completed` when all required tasks are completed or predeclared optional tasks have terminal non-blocking outcomes.
- A job is `failed` when any required task is irrecoverably failed or a job-level invariant fails.
- A job is `cancelled` only after cancellation is serialized and all running leases are terminal/revoked.
- `invalidated` is a post-hoc evidence state caused by leakage, integrity, governance, or contract failure; it does not erase the prior execution history.
- `abandoned` is an operator decision to stop reconciling an interrupted job without asserting ordinary cancellation or failure.

## 3. Scheduler

The scheduler MUST support:

- CPU, memory, accelerator, accelerator-memory, disk, and custom logical resources;
- host-wide and per-job concurrency;
- task priority and fairness;
- resource reservations;
- affinity/anti-affinity;
- worker capability matching;
- cancellation and draining;
- retry backoff;
- prevention of oversubscription.

Ray Tune/Ray Core MAY implement resource scheduling, but EvoNN domain state and evolutionary logic MUST remain independent and replaceable.

## 4. Worker protocol

Workers MUST:

1. advertise capabilities and liveness;
2. acquire a time-bounded task lease;
3. create an isolated workspace;
4. materialize only declared artifacts;
5. enforce resource/network policy;
6. emit heartbeats and structured progress;
7. checkpoint at declared boundaries;
8. publish artifacts to temporary locations;
9. verify and atomically commit artifacts;
10. report one terminal outcome;
11. clean process trees and temporary state.

Lost leases MUST prevent late workers from overwriting newer attempts.

## 5. Isolation

Each attempt MUST have:

- separate process group;
- separate working directory;
- explicit environment allowlist;
- no control database credentials beyond a constrained reporter endpoint;
- filesystem path confinement;
- network policy;
- bounded CPU/memory/file descriptors/processes;
- stdout/stderr capture with redaction;
- controlled signals and termination grace period.

Untrusted dataset/model code MUST NOT execute in the ordinary worker trust boundary. Where unavoidable, stronger sandboxing or explicit user trust approval is required.

## 6. Retry policy

Retries are allowed only for reason codes marked retryable. A retry MUST create a new attempt and retain prior artifacts/diagnostics.

Retrying with changed scientific settings creates a new candidate or job, not another identical attempt.

Automatic retry policy MUST specify:

- reason classes;
- maximum attempts;
- backoff;
- resource adjustment rules;
- checkpoint reuse;
- budget charging;
- non-idempotent exclusions.

## 7. Pause, resume, and cancel

- Pause is accepted only when a verified checkpoint can be produced.
- Cancel stops new scheduling immediately and terminates running attempts according to policy.
- Completed artifacts racing with cancellation are accepted only if their lease and commit precede the serialized cancellation boundary.
- Resume restores exact plan and checkpoint identity.
- Force kill MUST preserve the last valid checkpoint and mark in-flight artifacts incomplete.

## 8. Atomic generation/search checkpoints

An engine checkpoint MUST include:

- engine state and phase;
- candidate population/archive identities;
- innovation or lineage counters;
- optimizer/portfolio state;
- complete RNG states;
- budget counters;
- benchmark rotation/sample state;
- semantic caches or references;
- previous-checkpoint digest;
- checksum.

Checkpoint files/manifests MUST first be staged, fully written, checksummed, and atomically published under immutable digests. A single metadata transaction then makes the new checkpoint authoritative, updates state/counters, and writes its outbox event. Until that transaction commits, the previous checkpoint remains authoritative; published-but-unreferenced content is safe orphan data reclaimed by reconciliation. Previous valid checkpoints SHOULD be retained.

## 9. Writer leases and database policy

- One logical control-plane writer service owns local metadata writes.
- A per-run analytical database has one owning evidence process and writer lease.
- During active writes, inspectors, dashboards, reports, and exporters query through that owner or immutable snapshots; they do not open the live file independently.
- Stable/final snapshots may be opened read-only by other processes.
- Same-run concurrent owners/writers fail immediately.
- Leases include host, PID/process identity, attempt, acquisition/expiry, and recovery token.

## 10. Crash recovery

Startup reconciliation MUST:

1. verify metadata database integrity;
2. inspect active worker/lease liveness;
3. mark orphaned attempts interrupted;
4. verify checkpoints and artifacts;
5. reconcile task/job states;
6. resume eligible work only after policy checks;
7. surface operator-required actions.

Recovery point objective: no more than one uncommitted candidate batch. Completed committed evaluation artifacts MUST survive process or host restart.

## 11. Resource exhaustion

OOM, disk-full, file-descriptor exhaustion, process limit, and timeout MUST have distinct reason codes. The product MUST not silently reduce input data, model size, precision, or concurrency and represent the retry as equivalent.

## 12. Reliability targets

- Durable command acknowledgement: state survives process restart.
- State transition visibility: under normal local load, within 5 seconds in UI.
- Artifact finalization: atomic complete/incomplete distinction.
- Job recovery: deterministic classification after restart.
- Worker fault containment: one worker failure does not corrupt unrelated state.
- No two writers to the same DuckDB file.
