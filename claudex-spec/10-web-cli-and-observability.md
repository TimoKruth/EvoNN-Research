# 10 — Web Application, CLI, and Observability

## 1. Local application model

The Web application is a local control plane served by the EvoNN API process. It has execution authority through application commands; read views MUST remain derived from durable state and MUST NOT infer completion from file presence alone.

## 2. API behavior

- Versioned JSON APIs for all Web operations.
- Server-sent events or WebSocket stream for ordered live events.
- Optimistic concurrency/version tokens on mutations.
- Idempotency keys on creation commands.
- Stable machine error envelopes.
- Local authentication/session policy as defined in the security specification.
- OpenAPI generation from strict schemas.

The API MUST not expose arbitrary filesystem paths or raw database query endpoints.

## 3. Frontend requirements

Required views:

- project overview;
- dataset onboarding and validation;
- plan builder/review;
- live jobs;
- workers/resources;
- candidate leaderboard and side-by-side comparison;
- evidence reports;
- model selection/finalization;
- export verification;
- policies/settings;
- diagnostics.

Live updates MUST preserve focus, sorting, filters, and reading position. Charts MUST have tabular/text equivalents.

## 4. CLI contract

The CLI MUST use the same command handlers and schemas as the Web API. Human output is concise; JSON output is stable within a major version.

Exit status classes MUST distinguish:

- usage/configuration;
- policy denial;
- state conflict;
- job execution failure;
- partial success;
- internal product defect.

## 5. Structured events

Required event domains:

- project/dataset/plan lifecycle;
- job/task/attempt state;
- worker/lease/resource state;
- candidate proposal and lineage;
- evaluation progress/outcome;
- budget consumption/amendment;
- policy decision/network request;
- artifact publication/verification;
- model selection/finalization;
- export/conversion/parity;
- security/audit events.

Events MUST be sufficient to prove what data and labels each process accessed.

## 6. Logging

Logs MUST be structured JSON internally and include correlation IDs. User-visible projections may be human-friendly.

OBS-001: Logs MUST include job/task/attempt/worker/candidate identifiers where applicable.  
OBS-002: Secrets, signed URLs, raw sensitive fields, and home-directory prefixes MUST be redacted.  
OBS-003: Exceptions MUST retain sanitized type/message and a diagnostic trace reference.  
OBS-004: Silent broad exception suppression is forbidden.  
OBS-005: Log retention and export classification MUST be explicit.

## 7. Metrics and traces

The product SHOULD expose local OpenTelemetry-compatible traces and metrics for:

- command latency;
- queue time;
- worker utilization;
- task duration;
- candidate/evaluation throughput;
- retries/failures;
- cache hits;
- artifact bytes;
- database transactions;
- API/UI event lag;
- resource usage.

Prometheus export MAY be optional. Telemetry MUST remain local by default.

## 8. Dashboard truth model

Status MUST derive from explicit state artifacts, not heuristics such as a nonempty log or existing manifest. Corrupt, absent, incomplete, stale, unsupported, and failed data MUST remain distinguishable.

## 9. Accessibility

Acceptance-critical Web flows MUST meet WCAG 2.2 AA, including keyboard-only operation, focus management, labels/errors, contrast, reduced motion, 200% reflow, accessible live regions, and equivalents for charts.

## 10. Diagnostic bundle

Users SHOULD be able to generate an inspectable diagnostic bundle containing product/version/host information, redacted logs, state summaries, schema versions, and integrity findings. It MUST exclude datasets, model weights, credentials, and private paths unless explicitly opted in.
