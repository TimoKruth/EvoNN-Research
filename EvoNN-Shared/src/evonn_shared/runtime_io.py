"""Bounded engine run boundary with durable result-before-row recovery.

Search and compilation are supplied explicitly by each engine. Shared owns only
execution, receipts, storage, and frozen export contracts. No engine imports another.
"""

from collections import Counter
from contextlib import contextmanager
import fcntl
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import uuid
from .artifact_io import create_artifact_directory, publish_artifact, publish_artifact_directory, read_verified_artifact
from .canonical import canonical_sha256
from .datasets import load_dataset
from .export_reader import read_document, read_export
from ._run_io import open_directory, open_regular_at
from .exports import Manifest, Results, RunSummary, write_export
from .rng import StreamName, derive_stream
from .run_store import STORE_FILENAME
from .runtime_budget import execution_budget
from .telemetry import ArtifactReference

SEMANTICS = "one started architecture fit/eval; failed started fits charged; invalid pre-fit proposals uncharged; committed prior work is resumed, inheritance still charges its new fit"


def encode(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode()


def encode_snapshot(value):
    payload = encode(value)
    if len(payload) > 128 * 1024**2:
        raise ValueError("checkpoint or transaction exceeds supported 128 MiB transport limit")
    return payload


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def derived(path, payload):
    temporary = path.with_name(".view_" + uuid.uuid4().hex)
    publish_artifact(temporary, payload)
    os.replace(temporary, path)


def source_identity():
    root = Path(__file__).resolve().parents[3]
    files = [root / "uv.lock", root / "pyproject.toml"]
    for package in sorted(root.glob("EvoNN-*")):
        if package.is_dir():
            files.extend(sorted((package / "src").rglob("*.py")))
            files.append(package / "pyproject.toml")
    return hashlib.sha256(
        encode({str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files})
    ).hexdigest()


def code_identity():
    root = Path(__file__).resolve().parents[3]
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "-C", str(root), "status", "--porcelain"]).strip())
    return commit, dirty


def init_seed(seed, benchmark, index):
    return int(
        canonical_sha256(
            {"stream": str(derive_stream(seed, StreamName.INIT)), "benchmark": benchmark, "attempt": index},
            schema_version="evonn-engine-init/v1",
            digest_field=None,
        )[:8],
        16,
    )


def _crash(boundary, step, requested, requested_step):
    if requested == boundary and requested_step == step:
        os.kill(os.getpid(), signal.SIGKILL)


@contextmanager
def boundary_ownership(directory, name=".boundary.lock", timeout=0):
    try:
        publish_artifact(directory / name, b"")
    except FileExistsError:
        pass
    with open_directory(directory) as parent, open_regular_at(parent, name, exclusive=True) as fd:
        end = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= end:
                    raise ValueError("run or worker still has an active owner")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)


def terminal_worker_failure(directory, reason, timeout):
    """Close a failed dispatch under the worker lock, fencing delayed children."""
    with boundary_ownership(directory, ".worker.lock", timeout=max(0.001, timeout)):
        if (directory / "result.json").exists():
            return json.loads(read_document(directory, "result.json"))
        result = {"status": "failed", "reason": reason, "charged": int((directory / "started").is_file()), "invalid": 0}
        publish_artifact(directory / "result.json", encode(result))
        return result


def _process(system, verb, request, directory, timeout):
    request_path = directory / "request.json"
    if request_path.exists():
        previous = json.loads(read_document(directory, request_path.name, limit=128 * 1024**2))
        expected = json.loads(encode(request))
        if "training" in expected:
            expected["training"]["timeout"] = previous["training"]["timeout"]
        if previous != expected:
            raise ValueError("pending worker request differs from checkpoint-derived plan")
    else:
        publish_artifact(request_path, encode(request))
    with boundary_ownership(directory, ".worker.lock", timeout=max(0.001, timeout)):
        if (directory / "result.json").exists():
            return json.loads(read_document(directory, "result.json"))
        if (directory / "started").exists():
            return {
                "status": "failed",
                "reason": "started worker ended without a durable result; not silently retrained",
                "charged": 1,
                "invalid": 0,
            }
    output = directory / "result.json"
    env = dict(os.environ)
    env.update(
        {
            name: "1"
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        }
    )
    try:
        process = subprocess.run(
            [sys.executable, "-m", system + ".cli", verb, str(directory / "request.json"), str(output)],
            env=env,
            capture_output=True,
            timeout=max(0.001, timeout),
            check=False,
        )
        derived(directory / "worker.log", process.stdout + process.stderr)
        if process.returncode and not output.exists():
            raise ValueError(f"worker exited {process.returncode}; see {directory.name}/worker.log")
        return json.loads(read_document(directory, "result.json"))
    except subprocess.TimeoutExpired as error:
        derived(directory / "worker.log", (error.stdout or b"") + (error.stderr or b""))
        return {
            "status": "failed",
            "reason": "isolated worker wall-clock cap exceeded",
            "charged": int((directory / "started").is_file()),
            "invalid": 0,
        }


def prepare_worker(request, output):
    dataset = load_dataset(
        request["benchmark"], seed=request["seed"], cache_root=Path(request["cache"]), root=Path(request["shared_root"])
    )
    publish_artifact(output, encode({"status": "ok", "provenance": dataset.provenance}))


def vars_free_training(config):
    return {
        "epochs": config.epochs,
        "batch_size": config.batch_size,
        "learning_rate": config.learning_rate,
        "weight_decay": config.weight_decay,
        "clip_norm": config.clip_norm,
        "patience": config.patience,
        "warmup_fraction": config.warmup_fraction,
        "schedule": config.schedule,
        "timeout": config.timeout,
    }


def export_run(workspace, state, definitions, pack, selection, device_class, inherited):
    configuration, attempts = state["config"], state["attempts"]
    directory = workspace.root / (
        "symbiosis" if state["completed"] == configuration["total"] else f"symbiosis_step_{state['completed']}"
    )
    if directory.exists():
        read_export(directory)
        if read_document(directory, "state.json", limit=128 * 1024**2) != encode(state):
            raise ValueError("existing export differs from authoritative state")
        return directory
    actual = sum(a["charged"] for a in attempts[inherited:])
    cached = sum(a["charged"] for a in attempts[:inherited])
    total = configuration["total"]
    accounting = {
        "evaluation_count": total,
        "actual_evaluations": actual,
        "cached_evaluations": cached,
        "failed_evaluations": sum(a["charged"] for a in attempts[inherited:] if a["status"] == "failed"),
        "invalid_evaluations": sum(a["invalid"] for a in attempts[inherited:]),
        "resumed_from_run_id": workspace.run_id if cached else None,
        "resumed_evaluations": cached,
        "partial_run": actual + cached < total,
        "evaluation_semantics": SEMANTICS,
    }
    status = (
        "completed"
        if actual + cached == total and all(a["status"] == "ok" for a in attempts)
        else "failed"
        if any(a["status"] == "failed" for a in attempts)
        else "cancelled"
    )
    reason = None if status == "completed" else "See attempt ledger for incomplete/failed work."
    runtime = {
        "backend": configuration["backend"],
        "backend_version": selection.version,
        "device_class": device_class,
        "precision_mode": "float32 latent; per-layer QAT in genome"
        if configuration["system"] == "topograph"
        else "float32",
        "worker_topology": {
            "worker_count": configuration["training_worker_count"],
            "process_count": configuration["training_worker_count"],
            "threads_per_worker": 1,
        },
        "host_fingerprint": hashlib.sha256(
            encode(
                {
                    "host": platform.node(),
                    "machine": platform.machine(),
                    "system": platform.system(),
                    "processor": platform.processor(),
                }
            )
        ).hexdigest(),
    }
    seeding = {
        "seeding_enabled": False,
        "seeding_ladder": "none",
        "seed_source_system": None,
        "seed_source_run_id": None,
        "seed_artifact_path": None,
        "seed_target_family": None,
        "seed_selected_family": None,
        "seed_rank": None,
        "seed_overlap_policy": "unknown",
        "seed_cost_accounting": None,
        "seed_source_evaluations": None,
    }
    common = {
        "schema_version": "1.0.0",
        "system": configuration["system"],
        "run_id": workspace.run_id,
        "pack_id": pack.pack_name,
        "seed": configuration["seed"],
        "budget": execution_budget(pack, total, configuration["timeout"], device_class),
        "accounting": accounting,
        "runtime": runtime,
        "seeding": seeding,
    }
    by_id = {d.id: d for d in definitions}
    records = []
    for index, attempt in enumerate(attempts):
        definition = by_id[attempt["benchmark_id"]]
        records.append(
            {
                "benchmark_id": definition.id,
                "outcome_id": attempt["outcome_id"],
                "task_kind": definition.task_kind.value,
                "metric": {
                    "name": definition.primary_metric.name,
                    "direction": definition.primary_metric.direction.value,
                    "value": attempt["metric_value"] if attempt["status"] == "ok" else None,
                },
                "status": attempt["status"],
                "reason": attempt["reason"],
                "evaluation_count": attempt["charged"] if index >= inherited else 0,
                **{
                    name: {
                        "value": attempt[name] if name in attempt else None,
                        "provenance": "measured" if name in attempt else "unavailable",
                    }
                    for name in ("parameter_count", "train_seconds", "model_bytes", "peak_memory_bytes")
                },
            }
        )
    for definition in definitions:
        if not any(a["benchmark_id"] == definition.id for a in attempts):
            records.append(
                {
                    "benchmark_id": definition.id,
                    "outcome_id": "not_reached",
                    "task_kind": definition.task_kind.value,
                    "metric": {
                        "name": definition.primary_metric.name,
                        "direction": definition.primary_metric.direction.value,
                        "value": None,
                    },
                    "status": "skipped",
                    "reason": "wall-clock boundary reached",
                    "evaluation_count": 0,
                    **{
                        name: {"value": None, "provenance": "unavailable"}
                        for name in ("parameter_count", "train_seconds", "model_bytes", "peak_memory_bytes")
                    },
                }
            )
    records.sort(key=lambda r: (r["benchmark_id"], r["outcome_id"]))
    counts = Counter(r["status"] for r in records)
    coverage = {
        "benchmark_count": len(definitions),
        "result_count": len(records),
        **{k: counts[k] for k in ("ok", "failed", "skipped", "unsupported")},
    }
    ended = utc()
    timing = {
        "started_at": state["started"],
        "ended_at": ended,
        "latest_checkpoint_at": ended,
        "elapsed_seconds": (
            datetime.fromisoformat(ended.replace("Z", "+00:00"))
            - datetime.fromisoformat(state["started"].replace("Z", "+00:00"))
        ).total_seconds(),
    }
    ledger = {
        "schema_version": "1.0.0",
        "attempts": attempts,
        "accounting": accounting,
        "resumed_attempt_prefix": inherited,
    }
    derived(workspace.root / "attempts.json", encode(ledger))
    best = []
    for definition in sorted(definitions, key=lambda d: d.id):
        candidates = [r for r in records if r["benchmark_id"] == definition.id and r["status"] == "ok"]
        if candidates:
            choose = min if definition.primary_metric.direction.value == "min" else max
            winner = choose(candidates, key=lambda r: r["metric"]["value"])
            best.append(
                {
                    "benchmark_id": definition.id,
                    "outcome_id": winner["outcome_id"],
                    "metric_name": definition.primary_metric.name,
                    "direction": definition.primary_metric.direction.value,
                    "value": winner["metric"]["value"],
                }
            )
            attempt = next(a for a in attempts if a["outcome_id"] == winner["outcome_id"])
            payload = read_verified_artifact(
                workspace.root / attempt["directory"], ArtifactReference(**attempt["model_artifact"])
            )
            derived(workspace.root / ("model_" + definition.id + ".npz"), payload)
            derived(
                workspace.root / ("model_" + definition.id + ".json"),
                encode(
                    {
                        "genome": attempt["genome"],
                        "buffers": attempt["buffers"],
                        "preprocessing": attempt["preprocessing"],
                        "backend": runtime,
                    }
                ),
            )
    dataset_names = []
    provenance = json.loads(read_document(workspace.root, "dataset_provenance.json"))
    for item in provenance:
        cache_path = create_artifact_directory(workspace.root / "datasets" / item["benchmark_id"])
        for artifact in item["cache_artifacts"]:
            ref = ArtifactReference(path=artifact["path"], sha256=artifact["sha256"])
            payload = read_verified_artifact(Path(item["cache_directory"]), ref, size_bytes=artifact["size_bytes"])
            derived(cache_path / ref.path, payload)
            dataset_names.append("datasets/" + item["benchmark_id"] + "/" + ref.path)
    names = [
        "config.yaml",
        "state.json",
        "report.md",
        STORE_FILENAME,
        "engine_telemetry.json",
        "attempts.json",
        "dataset_provenance.json",
    ]
    names += dataset_names
    names += ["model_" + b["benchmark_id"] + suffix for b in best for suffix in (".npz", ".json")]
    references = {
        name: ArtifactReference(
            path=name, sha256=hashlib.sha256(read_document(workspace.root, name, limit=256 * 1024**2)).hexdigest()
        )
        for name in names
    }
    flag = "portability_only" if configuration["backend"] == "numpy_fallback" else "runtime_evidence_only"
    manifest = Manifest.model_validate_json(
        encode(
            {
                **common,
                "run_class": "smoke" if total <= 16 else "local",
                "status": status,
                "status_reason": reason,
                "lab_spec_version": "2026.07",
                "git_commit": configuration["git_commit"],
                "timing": timing,
                "config_snapshot": references["config.yaml"].model_dump(),
                "report_markdown": references["report.md"].model_dump(),
                "artifacts": [
                    ref.model_dump()
                    for name, ref in sorted(references.items())
                    if name not in ("config.yaml", "report.md")
                ],
            }
        )
    )
    results = Results.model_validate_json(encode({**common, "records": records, "coverage": coverage}))
    summary = RunSummary.model_validate_json(
        encode(
            {
                **common,
                "status": status,
                "status_reason": reason,
                "timing": timing,
                "coverage": coverage,
                "best_per_benchmark": best,
                "aggregates": [],
                "fairness_flags": [
                    {
                        "code": flag,
                        "severity": "warning",
                        "benchmark_ids": sorted(by_id),
                        "message": "Real architecture training and contract evidence; scientific qualification is separate.",
                    }
                ],
                "artifact_digests": [ref.model_dump() for _, ref in sorted(references.items())],
            }
        )
    )
    staging = workspace.root / ("export_" + uuid.uuid4().hex)
    write_export(staging, manifest, results, summary)
    for name, ref in references.items():
        create_artifact_directory((staging / name).parent)
        publish_artifact(staging / name, read_verified_artifact(workspace.root, ref, max_bytes=256 * 1024**2))
    publish_artifact_directory(staging, directory)
    return directory
