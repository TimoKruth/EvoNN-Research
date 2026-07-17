# 14 — Technology Decisions

## 1. Decision policy

Technology choices are provisional implementation decisions until their mandatory validation spikes pass. Product requirements remain authoritative; a failed spike changes the technology/ADR, not the product contract, unless the user explicitly revises the specification. Every dependency MUST remain behind a domain boundary and MUST be replaceable without changing canonical artifacts.

Research was performed against authoritative sources in July 2026. Version-specific claims MUST be revalidated before implementation and release.

## 2. Selected stack

| Area | Decision | Status |
|---|---|---|
| Language/tooling | Python 3.13+, `uv` workspace | provisionally selected |
| Schemas/config | Pydantic 2 with deliberate strictness | provisionally selected |
| Transactional persistence | SQLAlchemy 2 | provisionally selected |
| Local metadata DB | SQLite WAL, `synchronous=FULL`, single writer | provisionally selected |
| Higher-concurrency profile | PostgreSQL | optional supported profile |
| Migrations | Alembic with reviewed generated candidates | provisionally selected |
| Analytical evidence | one DuckDB per run/job | provisionally selected |
| Apple runtime | MLX | mandatory |
| Linux/interoperability | qualified MLX and PyTorch backends | provisionally selected |
| Trial/resource scheduler | Ray Tune/Core behind EvoNN protocol | selected with security caveat |
| Evolutionary optimization | EvoNN engine logic; pymoo optional algorithm provider | selected boundary |
| Lightweight HPO | Optuna optional with durable storage | optional |
| Pretrained/adapters | Hugging Face Transformers + PEFT | provisionally selected |
| Artifact store | local content-addressed filesystem store | provisionally selected |
| Registry distribution | OCI/ORAS | optional |
| Tensor serialization | safetensors where applicable | provisionally selected |
| Classical serialization | skops/declarative formats where applicable | provisionally selected |
| Web API | FastAPI | selected, validate current compatibility |
| Frontend | React + TypeScript + Vite | selected, validate current versions |
| Server-state UI | TanStack Query; Router/Table where beneficial | selected/provisional |
| Accessible primitives | Radix-style accessible primitives; vendored/custom design system | provisional |
| Data visualization | Apache ECharts for interactive views with table equivalents | provisional |
| CLI | Typer | provisionally selected |
| Logging | structlog-style structured JSON over standard logging | selected/provisional |
| Telemetry | OpenTelemetry local-first; optional Prometheus export | selected/provisional |
| Tests | pytest, Hypothesis, Playwright | provisionally selected |
| Quality | Ruff, Pyright or strict mypy | provisionally selected |
| Packaging | `uv` install/tool workflow first; native desktop packaging deferred | provisionally selected |
| Supply chain | lockfiles, pip-audit, SBOM, signing | selected policy |

## 3. Runtime rationale

MLX is the required Apple Silicon execution layer and currently provides documented macOS support plus Linux CPU/CUDA packages. Package availability does not prove backend parity; capability qualification remains mandatory.

PyTorch is retained for its broader pretrained, Linux, conversion, and deployment ecosystem. EvoNN does not hide both behind a fake lowest-common-denominator tensor API; engines/evaluators target declared backend capabilities.

## 4. Scheduler rationale

Ray Tune provides resource-aware trials, ASHA/HyperBand, PBT, multi-GPU, and future multi-node growth. EvoNN MUST keep domain state, evolutionary policy, and artifacts independent of Ray. Ray assumes trusted cluster/network conditions and is not the sandbox.

Optuna is useful for simpler studies but isolated multi-process workers require durable shared storage, not in-memory storage.

## 5. Optimization rationale

pymoo offers mature multi/many-objective and constrained algorithms. It MAY supply optimization algorithms, but EvoNN owns mixed candidate representations, repair, lineage, evaluation, checkpointing, scheduling, and hybrid semantics.

Its exact pinned license and project commercial wording MUST be reviewed and documented.

## 6. Persistence rationale

SQLite WAL permits readers with one writer and is appropriate for the one-host local product when writes are funneled through one control process. `synchronous=FULL` is chosen for durable command acknowledgement.

PostgreSQL becomes appropriate if the product profile introduces higher write concurrency or remote database access.

DuckDB is retained for bulk per-run analytics, not coordination or many small multi-process transactions. One process owns an active file; the UI/reporting layers consume query responses or immutable snapshots rather than opening a concurrently written database.

## 7. Artifact rationale

Digest-addressed local storage is the required baseline. OCI/ORAS is optional for publication, replication, signatures, and SBOM/referrer relationships. Tags are mutable aliases; digests are identities.

Hugging Face downloads MUST resolve to commit hashes and file hashes. Cache layout is an efficiency mechanism, not authenticity or experiment lineage.

## 8. Deployment rationale

The guaranteed artifact is the runtime-native bundle. ONNX Runtime, ExecuTorch, and Core ML are capability-tested derived targets. ONNX Runtime's Core ML provider status and arbitrary MLX export coverage do not justify a universal conversion promise.

## 9. Rejected or deferred choices

- Universal cross-framework tensor abstraction: rejected.
- One universal genome: rejected.
- Microservice architecture for v1: rejected.
- MLflow as mandatory core registry: rejected pending demonstrated value beyond native metadata/evidence.
- DVC as mandatory data registry: rejected pending demonstrated need; content-addressed local data lineage is core.
- Mandatory PostgreSQL: rejected for default local profile.
- Mandatory OCI registry: rejected.
- PyInstaller/Briefcase/Tauri desktop shell: deferred until core install/update requirements are proven.
- Public plugin execution: rejected for v1 security scope.

## 10. Mandatory validation spikes

Before implementation freezes versions, run spikes for:

1. representative MLX Mac and MLX/PyTorch Linux operator/training parity;
2. Ray process/resource behavior on Apple unified memory and Linux GPUs;
3. MLX and PyTorch native bundle safe loading;
4. direct PyTorch→Core ML conversion and representative MLX paths;
5. SQLite single-writer throughput under expected event volume;
6. DuckDB read-only dashboard access during active writes;
7. frontend accessibility and live-table performance;
8. archive/download hardening and safe model acquisition;
9. Python 3.13 wheel availability for all pinned dependencies.
