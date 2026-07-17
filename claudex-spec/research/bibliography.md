# Technology Research Bibliography

Primary sources consulted for the July 2026 technology decisions.

## Runtime and deployment

- MLX install documentation: https://ml-explore.github.io/mlx/build/html/install.html
- MLX package: https://pypi.org/project/mlx/
- PyTorch local installation: https://docs.pytorch.org/get-started/locally/
- PyTorch release policy: https://github.com/pytorch/pytorch/blob/main/RELEASE.md
- ONNX Runtime execution providers: https://onnxruntime.ai/docs/execution-providers/
- ONNX Runtime architecture: https://onnxruntime.ai/docs/reference/high-level-design.html
- ONNX Runtime Core ML provider: https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html
- Core ML Tools PyTorch conversion: https://apple.github.io/coremltools/docs-guides/source/convert-pytorch.html
- ExecuTorch desktop platforms: https://docs.pytorch.org/executorch/stable/platforms-desktop.html

## Search and orchestration

- Ray Tune: https://docs.ray.io/en/latest/tune.html
- Ray resources: https://docs.ray.io/en/latest/ray-core/scheduling/resources.html
- Ray Tune schedulers: https://docs.ray.io/en/latest/tune-schedulers.html
- Ray security: https://docs.ray.io/en/latest/ray-security/index.html
- Optuna distributed optimization: https://optuna.readthedocs.io/en/stable/tutorial/10_key_features/004_distributed.html
- pymoo: https://pymoo.org/index.html
- pymoo algorithms: https://pymoo.org/algorithms/list.html
- Transformers PEFT integration: https://huggingface.co/docs/transformers/en/peft
- PEFT checkpoint format: https://huggingface.co/docs/peft/main/developer_guides/checkpoint

## Schemas and persistence

- Pydantic strict mode: https://docs.pydantic.dev/latest/concepts/strict_mode/
- SQLAlchemy transactions: https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- SQLite WAL: https://www.sqlite.org/wal.html
- SQLite synchronous: https://www.sqlite.org/pragma.html#pragma_synchronous
- PostgreSQL MVCC: https://www.postgresql.org/docs/current/mvcc.html
- DuckDB concurrency: https://duckdb.org/docs/current/connect/concurrency
- Alembic autogenerate: https://alembic.sqlalchemy.org/en/latest/autogenerate.html

## Artifacts and provenance

- ORAS artifacts: https://oras.land/docs/concepts/artifact/
- OCI artifact guidance: https://github.com/opencontainers/image-spec/blob/main/artifacts-guidance.md
- Hugging Face cache: https://huggingface.co/docs/huggingface_hub/main/en/guides/manage-cache
- Hugging Face downloads: https://huggingface.co/docs/huggingface_hub/en/guides/download
- Safetensors: https://huggingface.co/docs/safetensors/main/index
- Scikit-learn persistence guidance: https://scikit-learn.org/stable/model_persistence.html
- Hugging Face pickle security: https://huggingface.co/docs/hub/security-pickle
- MLflow pickle-free models: https://mlflow.org/docs/latest/ml/tracking/pickle-free-models/

## Product stack and quality

- FastAPI workers: https://fastapi.tiangolo.com/deployment/server-workers/
- Vite: https://vite.dev/guide/
- Typer: https://typer.tiangolo.com/
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
- structlog: https://www.structlog.org/en/stable/
- Prometheus instrumentation: https://prometheus.io/docs/practices/instrumentation/
- Playwright Python: https://playwright.dev/python/docs/intro
- PyInstaller: https://pyinstaller.org/en/stable/index.html

## Research caveat

Sources are time-sensitive. The implementation MUST revalidate current versions, licenses, Python 3.13 wheel availability, platform requirements, and security advisories before pinning dependencies.
