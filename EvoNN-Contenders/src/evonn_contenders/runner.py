"""Bounded fixed-pool execution, durable accounting and portable exports."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

from evonn_shared.artifact_io import (
    create_artifact_directory, publish_artifact, publish_artifact_directory, read_verified_artifact,
)
from evonn_shared.canonical import canonical_sha256
from evonn_shared.runtime_host import host_fields
from evonn_shared.active_catalog import get_benchmark, load_parity_pack
from evonn_shared.exports import Manifest, Results, RunSummary, write_export
from evonn_shared.rng import StreamName, derive_stream
from evonn_shared.run_store import STORE_FILENAME, open_run_reader, open_run_store
from evonn_shared.run_workspace import create_run_workspace, write_report
from evonn_shared.telemetry import ArtifactReference
from evonn_shared.runtime_budget import execution_budget

from .config import benchmark_group, load_pools, resolve_pool
from .datasets import shared_root


SEMANTICS = "one contender fit/eval attempt; failed started fits count, invalid pre-fit configurations and optional skips do not"


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _measurement(value, provenance="measured"):
    return {"value": value, "provenance": provenance if value is not None else "unavailable"}


def _record(definition, outcome: str, result: dict) -> dict:
    return {
        "benchmark_id": definition.id, "outcome_id": outcome, "task_kind": definition.task_kind.value,
        "metric": {"name": definition.primary_metric.name, "direction": definition.primary_metric.direction.value,
                   "value": result["score"] if result["status"] == "ok" else None},
        "status": result["status"], "reason": result["reason"], "evaluation_count": result["charged"],
        **{field: _measurement(result[field] if field in result else None)
           for field in ("parameter_count", "train_seconds", "model_bytes", "peak_memory_bytes")},
    }


def _worker(request: dict, directory: Path, deadline: float, fit_timeout: float) -> dict:
    request_path, output_path = directory / "request.json", directory / "result.json"
    publish_artifact(request_path, json_bytes(request))
    env = dict(os.environ)
    env.update({name: "1" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                       "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")})
    remaining = min(fit_timeout, deadline - time.monotonic())
    if remaining <= 0:
        return {"status": "skipped", "reason": "run wall-clock limit reached before fit", "charged": 0, "invalid": 0}
    try:
        process = subprocess.run([sys.executable, "-m", "evonn_contenders.worker", str(request_path), str(output_path)],
                                 env=env, capture_output=True, timeout=remaining, check=False)
        publish_artifact(directory / "worker.log", process.stdout + process.stderr)
        if process.returncode != 0:
            return {"status": "failed", "reason": f"worker exited with code {process.returncode}; see run logs",
                    "charged": int(Path(request["attempt_started"]).is_file()), "invalid": 0}
        return json.loads(output_path.read_text())
    except subprocess.TimeoutExpired as error:
        publish_artifact(directory / "worker.log", (error.stdout or b"") + (error.stderr or b""))
        return {"status": "failed", "reason": "isolated worker exceeded its time limit",
                "charged": int(Path(request["attempt_started"]).is_file()), "invalid": 0}


def _prepare(request: dict, directory: Path, deadline: float) -> dict:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ValueError("run wall-clock limit reached before data preparation")
    request_path, output = directory / "request.json", directory / "result.json"
    publish_artifact(request_path, json_bytes(request))
    try:
        process = subprocess.run([sys.executable, "-m", "evonn_contenders.prepare", str(request_path), str(output)],
                                 capture_output=True, timeout=remaining, check=False)
    except subprocess.TimeoutExpired as error:
        publish_artifact(directory / "prepare.log", (error.stdout or b"") + (error.stderr or b""))
        raise ValueError("dataset preparation/optional probing exceeded run time limit") from error
    publish_artifact(directory / "prepare.log", process.stdout + process.stderr)
    if process.returncode:
        raise ValueError(f"dataset worker exited {process.returncode}")
    result = json.loads(output.read_text())
    if result["status"] != "ok":
        raise ValueError(result["reason"])
    return result


def run_contenders(*, pack_name: str, budget: int | None, seed: int, output_parent: Path,
                   cache_root: Path, pools_path: Path | None = None, timeout: float = 1800.0,
                   fit_timeout: float = 180.0, enhanced: bool = False) -> Path:
    if not math.isfinite(timeout) or not math.isfinite(fit_timeout) or not 0 < timeout <= 1800 or not 0 < fit_timeout <= 1800:
        raise ValueError("Phase 1 run and fit time limits must be in (0, 1800] seconds")
    root = shared_root()
    pack = load_parity_pack(pack_name, shared_root=root)
    total = pack.budget_policy.evaluation_count if budget is None else budget
    if type(total) is not int or total < 1 or total % len(pack.benchmarks):
        raise ValueError("evaluation budget must be positive and divisible by benchmark count")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer in [0, 2**32)")
    config, pool_digest = load_pools(pools_path)
    definitions = [get_benchmark(name, shared_root=root) for name in pack.benchmarks]
    pools = {definition.id: resolve_pool(config, definition) for definition in definitions}
    try:
        git_root = str(Path(__file__).resolve().parents[3])
        git_commit = subprocess.check_output(["git", "-C", git_root, "rev-parse", "HEAD"],
                                             text=True, stderr=subprocess.PIPE).strip()
        code_dirty = bool(subprocess.check_output(["git", "-C", git_root, "status", "--porcelain"],
                                                 stderr=subprocess.PIPE).strip())
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError("Contenders requires an accessible Git checkout for exact code provenance") from error
    started, clock_start = _utc(), time.monotonic()
    deadline = clock_start + timeout
    identifier = "contenders_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:12]
    workspace = create_run_workspace(create_artifact_directory(output_parent), identifier)
    attempts_root = create_artifact_directory(workspace.root / "attempts")
    device = platform.system().lower() + "_" + platform.machine() + "_cpu"
    runtime = {"backend": "sklearn_contender", "backend_version": importlib.metadata.version("scikit-learn") + "; CPU fixed-pool orchestration; per-attempt backend versions in attempts.json",
               "device_class": device, "precision_mode": "float32 inputs; estimator-native arithmetic",
               "worker_topology": {"worker_count": 1, "process_count": 1, "threads_per_worker": 1},
               "host_fingerprint": hashlib.sha256(json_bytes(host_fields())).hexdigest()}
    declaration = execution_budget(pack, total, timeout, device)
    snapshot = {"schema_version": "1.0.0", "benchmark_pack": {"pack_name": pack_name}, "budget": declaration,
                "seed": seed, "pool_sha256": pool_digest, "pools": config, "enhanced": enhanced,
                "fit_timeout_seconds": fit_timeout, "runtime": runtime, "evaluation_semantics": SEMANTICS,
                "initialization_stream": str(derive_stream(seed, StreamName.INIT)),
                "dataset_versions": {name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-learn", "pandas", "openml")},
                "git_commit": git_commit, "code_dirty": code_dirty}
    publish_artifact(workspace.config_path, json_bytes(snapshot))
    records, attempts, provenance = [], [], []
    retained_models = {}
    with open_run_store(workspace.root, identifier, create=True) as store:
        for definition in definitions:
            required, optional = pools[definition.id]
            directory = create_artifact_directory(attempts_root / (definition.id + "_prepare"))
            try:
                prepared = _prepare({"benchmark": definition.id, "seed": seed, "cache_root": str(cache_root.absolute()),
                    "shared_root": str(root), "optional": {name: config["models"][name] for name in optional},
                    "enhanced": enhanced}, directory, deadline)
                provenance.append(prepared["provenance"])
            except (ValueError, OSError) as error:
                result = {"status": "failed", "reason": f"dataset/preflight unavailable: {error}", "charged": 0, "invalid": 0}
                records.append(_record(definition, "dataset_unavailable", result))
                attempts.append({"benchmark_id": definition.id, "contender_id": None, **result})
                continue
            available = [*required, *prepared["available_optional"]]
            optional_results = prepared["optional_results"]
            attempted_names = set()
            for index in range(total // len(definitions)):
                name = available[index % len(available)]
                outcome = f"{name}_r{index // len(available):04d}"
                model_config = config["models"][name]
                model_seed = int(canonical_sha256({"stream": str(derive_stream(seed, StreamName.INIT)),
                    "benchmark": definition.id, "outcome": outcome}, schema_version="evonn-contender-init-v1", digest_field=None)[:8], 16)
                directory = create_artifact_directory(attempts_root / f"{definition.id}_{outcome}")
                request = {"model": model_config["model"], "parameters": model_config["parameters"],
                           "model_seed": model_seed, "task": definition.task_kind.value,
                           "metric": definition.primary_metric.name, "input_shape": list(definition.input_shape),
                           "output_dim": definition.output_dim, "data": prepared["provenance"],
                           "model_output": str(directory / "model.pkl"), "attempt_started": str(directory / "started")}
                result = _worker(request, directory, deadline, fit_timeout)
                record = _record(definition, outcome, result)
                records.append(record)
                attempts.append({"benchmark_id": definition.id, "outcome_id": outcome, "contender_id": name,
                                 "group": benchmark_group(definition), "family": model_config["model"], "model_seed": model_seed,
                                 "parameters": model_config["parameters"], **result})
                attempted_names.add(name)
                if result["status"] == "ok":
                    store.append_evaluation(definition.id, outcome, definition.primary_metric.name, result["score"])
                    prior = retained_models[definition.id] if definition.id in retained_models else None
                    better = prior is None or (result["score"] > prior[0] if definition.primary_metric.direction.value == "max" else result["score"] < prior[0])
                    if prior is not None and result["score"] == prior[0]:
                        better = outcome < prior[3]
                    if better:
                        retained_models[definition.id] = (result["score"], directory, result["model_artifact"], outcome)
            for name in [*required, *optional]:
                if name not in attempted_names:
                    result = optional_results[name] if name in optional_results else {
                        "status": "skipped", "reason": "required contender not reached within budget", "charged": 0, "invalid": 0}
                    records.append(_record(definition, name + "_not_run", result))
                    attempts.append({"benchmark_id": definition.id, "contender_id": name, **result})
        records.sort(key=lambda record: (record["benchmark_id"], record["outcome_id"]))
        actual = sum(record["evaluation_count"] for record in records)
        accounting = {"evaluation_count": total, "actual_evaluations": actual, "cached_evaluations": 0,
                      "failed_evaluations": sum(record["evaluation_count"] for record in records if record["status"] == "failed"),
                      "invalid_evaluations": sum(attempt["invalid"] for attempt in attempts),
                      "resumed_from_run_id": None, "resumed_evaluations": 0, "partial_run": actual < total,
                      "evaluation_semantics": SEMANTICS}
        status = "failed" if any(record["status"] == "failed" for record in records) else ("cancelled" if actual < total else "completed")
        reason = None if status == "completed" else "See explicit attempt ledger and accounting for failed, invalid or unexecuted work."
        for attempt in attempts:
            if "model_artifact" in attempt:
                attempt["worker_model_sha256"] = attempt.pop("model_artifact")["sha256"]
        ledger = {"schema_version": "1.0.0", "attempts": attempts, "accounting": accounting,
                  "model_retention": "best successful model per benchmark; other serialized sizes are measurements, not promised export artifacts"}
        references = []
        for name, data in [("attempts.json", ledger), ("dataset_provenance.json", provenance)]:
            payload = json_bytes(data)
            reference = publish_artifact(workspace.root / name, payload)
            store.record_artifact(reference.path, len(payload), reference.sha256)
            references.append(reference)
        for benchmark, (_, directory, reference_data, outcome) in sorted(retained_models.items()):
            reference = ArtifactReference(**reference_data)
            payload = read_verified_artifact(directory, reference)
            filename = f"model_{benchmark}_{outcome}.pkl"
            copied = publish_artifact(workspace.root / filename, payload)
            store.record_artifact(filename, len(payload), copied.sha256)
            references.append(copied)
        for key, value in {"status": status, "accounting": json.dumps(accounting, sort_keys=True),
                           "floor_scope": "required and optional skips visible in attempts.json; no scientific qualification"}.items():
            store.set_metadata(key, value)
        write_report(workspace, store)
        store.verify_evaluation_chain()
    ended = _utc()
    timing = {"started_at": started, "ended_at": ended, "latest_checkpoint_at": None,
              "elapsed_seconds": (datetime.fromisoformat(ended.replace("Z", "+00:00")) - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()}
    publish_artifact(workspace.state_path, json_bytes({"run_id": identifier, "status": status, "accounting": accounting}))
    publish_artifact(workspace.summary_path, json_bytes({"run_id": identifier, "status": status, "accounting": accounting,
                                                      "standard_export": "symbiosis", "timing": timing}))
    with open_run_reader(workspace.root, identifier) as reader:
        assert len(reader.evaluations()) == sum(record["status"] == "ok" for record in records)
        for filename in ("config.yaml", "report.md", STORE_FILENAME, "state.json"):
            payload = (workspace.root / filename).read_bytes()
            references.append(ArtifactReference(path=filename, sha256=hashlib.sha256(payload).hexdigest()))
        seeding = {"seeding_enabled": False, "seeding_ladder": "none", "seed_source_system": None,
                   "seed_source_run_id": None, "seed_artifact_path": None, "seed_target_family": None,
                   "seed_selected_family": None, "seed_rank": None, "seed_overlap_policy": "unknown",
                   "seed_cost_accounting": None, "seed_source_evaluations": None}
        common = {"schema_version": "1.0.0", "system": "contenders", "run_id": identifier, "pack_id": pack_name,
                  "seed": seed, "budget": declaration, "accounting": accounting, "runtime": runtime, "seeding": seeding}
        counts = Counter(record["status"] for record in records)
        coverage = {"benchmark_count": len(definitions), "result_count": len(records),
                    **{status_name: counts[status_name] for status_name in ("ok", "failed", "skipped", "unsupported")}}
        best = []
        for definition in sorted(definitions, key=lambda item: item.id):
            candidates = [record for record in records if record["benchmark_id"] == definition.id and record["status"] == "ok"]
            if candidates:
                choose = max if definition.primary_metric.direction.value == "max" else min
                winner = choose(candidates, key=lambda record: record["metric"]["value"])
                best.append({"benchmark_id": definition.id, "outcome_id": winner["outcome_id"],
                             "metric_name": definition.primary_metric.name, "direction": definition.primary_metric.direction.value,
                             "value": winner["metric"]["value"]})
        by_path = {reference.path: reference for reference in references}
        manifest = Manifest.model_validate_json(json.dumps({**common, "run_class": "smoke" if total <= 16 else "local",
            "status": status, "status_reason": reason, "lab_spec_version": "2026.07", "git_commit": git_commit,
            "timing": timing, "config_snapshot": by_path["config.yaml"].model_dump(mode="json"),
            "report_markdown": by_path["report.md"].model_dump(mode="json"),
            "artifacts": [by_path[path].model_dump(mode="json") for path in sorted(by_path) if path not in ("config.yaml", "report.md")]}))
        results = Results.model_validate_json(json.dumps({**common, "records": records, "coverage": coverage}))
        summary = RunSummary.model_validate_json(json.dumps({**common, "status": status, "status_reason": reason,
            "timing": timing, "coverage": coverage, "best_per_benchmark": best, "aggregates": [],
            "fairness_flags": [{"code": "contract_evidence_only", "severity": "warning", "benchmark_ids": sorted(pack.benchmarks),
                                "message": "Contender runtime evidence; qualification requires separate audit and repeatability."}],
            "artifact_digests": [by_path[path].model_dump(mode="json") for path in sorted(by_path)]}))
        staging = workspace.root / ("export_staging_" + uuid.uuid4().hex)
        write_export(staging, manifest, results, summary)
        for path, reference in by_path.items():
            publish_artifact(staging / path, read_verified_artifact(workspace.root, reference))
        publish_artifact_directory(staging, workspace.root / "symbiosis")
    return workspace.root / "symbiosis"
