"""Package-local search coordinator and worker using the shared publication boundary."""

from datetime import datetime, timezone
import hashlib
from concurrent.futures.process import BrokenProcessPool
import importlib.metadata
import io
import json
import math
from pathlib import Path
import platform
import resource
import time
import uuid
import numpy as np
from evonn_shared.artifact_io import create_artifact_directory, publish_artifact, read_verified_artifact
from evonn_shared.active_catalog import get_benchmark, load_parity_pack
from evonn_shared.canonical import canonical_sha256
from evonn_shared.runtime_clock import InvocationClock
from evonn_shared.runtime_journal import (JournalPublication, load_runtime_checkpoint, publish_initial,
                                          load_transaction, publish_transaction, runner_search_snapshot)
from evonn_shared.datasets import shared_root
from evonn_shared.export_reader import read_document
from evonn_shared.rng import StreamName, derive_stream
from evonn_shared.run_workspace import create_run_workspace, open_run_workspace, write_report
from evonn_shared.run_store import open_run_store
from evonn_shared.telemetry import ArtifactReference
from evonn_shared.runtime_budget import MAX_ENGINE_EVALUATIONS
from evonn_shared.runtime_io import (
    encode_snapshot,
    terminal_worker_failure,
    boundary_ownership,
    code_identity,
    source_identity,
    encode,
    utc,
    init_seed,
    _process,
    _crash,
    derived,
    export_run,
    vars_free_training,
)
from .tensors import Backend
from .training import TrainConfig, fit
from .parallel import Evaluator
from .research import policy, allocate_training, runtime_profile


def select_runtime(search_type, genome_type=None, *, variant="legacy"):
    policy(variant)
    if variant != "legacy":
        from .search_v2 import ResearchSearch
        from .genome_v2 import GenomeV2
        return ResearchSearch, GenomeV2
    return search_type, genome_type


def evaluation_worker(request, output, search_type, genome_type):
    worker_start = time.monotonic()
    variant = request.get("variant", "legacy")
    search_type, genome_type = select_runtime(search_type, genome_type, variant=variant)
    if request["source_sha256"] != source_identity():
        raise ValueError("worker source changed since run began")
    definition = get_benchmark(request["benchmark"], shared_root=Path(request["shared_root"]))
    search = search_type([definition], seed=0, **({"variant": variant} if variant != "legacy" else {}))
    try:
        genome = genome_type.model_validate(request["genome"])
        model = search.compile(
            genome, definition, backend=request["backend"], device=request["device"], seed=request["model_seed"]
        )
        if set(request["weights"]) != set(model.weights):
            raise ValueError("weight snapshot keys disagree with compiled model")
        for key, value in request["weights"].items():
            array = np.asarray(value, dtype=np.float32)
            if array.shape != model.weights[key].shape or not np.isfinite(array).all():
                raise ValueError("weight snapshot shape or finite-value mismatch")
            model.weights[key] = array
        model.buffers = {
            k: tuple(np.asarray(v, dtype=np.float32) for v in values) for k, values in request["buffers"].items()
        }
        provenance = request["data"]
        arrays = {}
        for item in provenance["cache_artifacts"]:
            ref = ArtifactReference(path=item["path"], sha256=item["sha256"])
            payload = read_verified_artifact(Path(provenance["cache_directory"]), ref, size_bytes=item["size_bytes"])
            arrays[Path(ref.path).stem] = np.load(io.BytesIO(payload), allow_pickle=False)
        config = TrainConfig(**request["training"])
    except (ValueError, TypeError, OverflowError) as error:
        publish_artifact(
            output,
            encode(
                {"status": "failed", "reason": f"invalid pre-fit configuration: {error}", "charged": 0, "invalid": 1}
            ),
        )
        return
    publish_artifact(output.parent / "started", b"fit\n")
    setup_seconds = time.monotonic() - worker_start
    try:
        fit_start = time.monotonic()
        result = fit(
            model,
            arrays["x_train"],
            arrays["y_train"],
            arrays["x_validation"],
            arrays["y_validation"],
            task=definition.task_kind.value,
            config=config,
            seed=request["model_seed"],
        )
        fit_seconds = time.monotonic() - fit_start
        publication_start = time.monotonic()
        buffer = io.BytesIO()
        np.savez(buffer, **model.weights)
        artifact = publish_artifact(output.parent / "weights.npz", buffer.getvalue())
        packed = sum(v.nbytes for v in model.weights.values())
        if search.system == "topograph":
            packed = model.packed_bytes_estimate
        result.update(
            status="ok",
            reason=None,
            charged=1,
            invalid=0,
            parameter_count=model.parameter_count,
            model_bytes=len(buffer.getvalue()),
            peak_memory_bytes=int(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system() == "Darwin" else 1024)
            ),
            model_artifact=artifact.model_dump(mode="json"),
            packed_bytes_estimate=packed,
            latent_weight_bytes=sum(v.nbytes for v in model.weights.values()),
            buffers={k: [np.asarray(a).tolist() for a in v] for k, v in model.buffers.items()},
        )
        if variant != "legacy":
            result["worker_profile"] = dict(setup_seconds=setup_seconds, fit_seconds=fit_seconds,
                                             model_publication_seconds=time.monotonic()-publication_start)
    except (ValueError, TimeoutError, FloatingPointError, OverflowError) as error:
        result = {"status": "failed", "reason": str(error), "charged": 1, "invalid": 0}
    publish_artifact(output, encode(result))


def run_engine(
    search_type,
    *,
    pack_name="tier1_core",
    budget=64,
    seed=42,
    output_parent=None,
    cache_root=None,
    backend="numpy_fallback",
    device="cpu",
    timeout=1200.0,
    fit_timeout=120.0,
    epochs=12,
    population_size=4,
    resume=None,
    stop_after=None,
    crash_at=None,
    crash_step=1,
    benchmark_pooling=False,
    novelty_weight=0.0,
    variant="legacy",
):
    search_type, _ = select_runtime(search_type, variant=variant)
    research = variant != "legacy"
    search_options = {"variant": variant} if research else {}
    if research and (benchmark_pooling or novelty_weight):
        raise ValueError("research variants use task-local archive selection; legacy pooling/novelty scalars are unavailable")
    if not all(math.isfinite(v) and 0 < v <= 1800 for v in (timeout, fit_timeout)):
        raise ValueError("run and fit limits must be in (0,1800] seconds")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be a 32-bit unsigned integer")
    cache_root = Path(".artifacts/dataset-cache") if cache_root is None else cache_root
    TrainConfig(epochs=epochs, timeout=fit_timeout)
    if type(population_size) is not int or not 2 <= population_size <= 16:
        raise ValueError("population_size must be an integer in [2,16]")
    selection = Backend(backend, device)
    root = shared_root()
    pack = load_parity_pack(pack_name, shared_root=root)
    if type(budget) is not int or not 1 <= budget <= MAX_ENGINE_EVALUATIONS or budget % len(pack.benchmarks):
        raise ValueError("budget must be in [1,256] and divisible across the pack")
    definitions = [get_benchmark(name, shared_root=root) for name in pack.benchmarks]
    commit, dirty = code_identity()
    system = search_type.system
    device_class = platform.system().lower() + "_" + platform.machine() + "_" + device
    configuration = {
        "system": system,
        "pack": pack_name,
        "total": budget,
        "seed": seed,
        "backend": backend,
        "device": device,
        "epochs": epochs,
        "population_size": population_size,
        "benchmark_pooling": benchmark_pooling,
        "novelty_weight": novelty_weight,
        "evaluation_process_count": 1,
        "training_worker_count": 1,
        "supervisor_count": 0,
        "evaluation_mode": "isolated-serial/v1",
        "timeout": timeout,
        "fit_timeout": fit_timeout,
        "git_commit": commit,
        "code_dirty": dirty,
        "source_sha256": source_identity(),
        "cache": str(Path(cache_root).absolute()),
        "shared_root": str(root.absolute()),
        "dataset_versions": {
            name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-learn", "pandas", "openml")
        },
    }
    if research:
        configuration.update(variant=variant, search_policy_version=2, genome_schema="topograph.genome/v2")
    invocation_start = time.monotonic()
    invocation_started = utc()
    deadline = invocation_start + timeout
    if resume is None:
        identifier = system + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:10]
        workspace = create_run_workspace(create_artifact_directory(output_parent), identifier)
        publish_artifact(workspace.config_path, encode(configuration))
        provenance = []
        for definition in definitions:
            directory = create_artifact_directory(workspace.root / ("prepare_" + definition.id))
            prepared = _process(
                system,
                "_prepare",
                {"benchmark": definition.id, "seed": seed, "cache": configuration["cache"], "shared_root": str(root)},
                directory,
                deadline - time.monotonic(),
            )
            if prepared["status"] != "ok":
                raise ValueError("dataset preparation failed")
            provenance.append(prepared["provenance"])
        publish_artifact(workspace.root / "dataset_provenance.json", encode(provenance))
        search = search_type(
            definitions,
            seed=int(derive_stream(seed, StreamName.SEARCH)),
            population_size=population_size,
            benchmark_pooling=benchmark_pooling,
            novelty_weight=novelty_weight,
            **search_options,
        )
        state = {
            "config": configuration,
            "completed": 0,
            "search": search.state(),
            "attempts": [],
            "tip": "0" * 64,
            "started": invocation_started,
            "elapsed": time.monotonic() - invocation_start,
            "dataset_sha256": hashlib.sha256(encode(provenance)).hexdigest(),
        }
        publish_initial(workspace.checkpoint_directory, identifier, "step_0", state)
        with open_run_store(workspace.root, identifier, create=True):
            pass
    else:
        workspace = open_run_workspace(Path(resume))
    with (
        boundary_ownership(workspace.root),
        Evaluator(
            data_bytes=max(
                sum(a["size_bytes"] for a in d["cache_artifacts"])
                for d in json.loads(read_document(workspace.root, "dataset_provenance.json"))
            ),
            snapshot_bytes=8 * 1024**2,
        ) as evaluator,
    ):
        with open_run_store(workspace.root, workspace.run_id) as store:
            _, payload = load_runtime_checkpoint(workspace.checkpoint_directory)
            state = json.loads(payload)
            saved_config = json.loads(read_document(workspace.root, "config.yaml"))
            if saved_config != configuration or state["config"] != configuration:
                raise ValueError("resume configuration/code/dependency drift")
            provenance_payload = read_document(workspace.root, "dataset_provenance.json")
            if hashlib.sha256(provenance_payload).hexdigest() != state["dataset_sha256"]:
                raise ValueError("dataset provenance drift")
            provenance = json.loads(provenance_payload)
            for data in provenance:
                for artifact in data["cache_artifacts"]:
                    read_verified_artifact(
                        Path(data["cache_directory"]),
                        ArtifactReference(path=artifact["path"], sha256=artifact["sha256"]),
                        size_bytes=artifact["size_bytes"],
                    )
            clock = InvocationClock(workspace.root, state["elapsed"],
                                    setup_seconds=max(0, time.monotonic() - invocation_start - (0 if resume else state["elapsed"])))
            deadline = min(deadline, time.monotonic() + max(0, timeout - clock.base))
            inherited = state["completed"] if resume else 0
            target = budget if stop_after is None else stop_after
            if type(target) is not int or not state["completed"] <= target <= budget:
                raise ValueError("stop_after outside remaining attempt range")
            rows = store.evaluations()
            if not state["completed"] <= len(rows) <= state["completed"] + 1:
                raise ValueError("row/checkpoint progress mismatch")
            tip = rows[state["completed"] - 1].row_sha256 if state["completed"] else "0" * 64
            if tip != state["tip"]:
                raise ValueError("checkpoint does not bind committed row prefix")
            search = None
            while state["completed"] < target and time.monotonic() < deadline:
                publication_start = time.monotonic()
                step = state["completed"] + 1
                transaction_path = workspace.root / f"transaction_{step:06d}.json"
                recovering_transaction = transaction_path.exists()
                if transaction_path.exists():
                    transaction = load_transaction(transaction_path, state)
                    search = None  # Rebuild from committed state after transaction recovery.
                    next_state = transaction["state"]
                    inherited = max(inherited, step)
                else:
                    if search is None:
                        search = search_type(definitions, seed=seed, population_size=population_size, state=state["search"], **search_options)
                    counts = {d.id: sum(a["benchmark_id"] == d.id for a in state["attempts"]) for d in definitions}
                    definition = min(definitions, key=lambda d: (counts[d.id], d.id))
                    genome = search.candidate(definition.id)
                    data = next(p for p in provenance if p["benchmark_id"] == definition.id)
                    model_seed = init_seed(seed, definition.id, counts[definition.id])
                    namespace = canonical_sha256(
                        {
                            "benchmark": definition.id,
                            "split": data["split_sha256"],
                            "backend": backend,
                            "version": selection.version,
                            "device": device,
                            "epochs": epochs,
                        },
                        schema_version="evonn-weight-context/v1",
                        digest_field=None,
                    )
                    generation = search.benchmarks[definition.id]["generation"]
                    full_epochs = max(1, math.ceil(epochs * (0.5 if generation == 0 else 1)))
                    proposal = search.proposal(definition.id) if research else None
                    if research and policy(variant)["training"]:
                        full_epochs = epochs
                    allocated = full_epochs
                    inheritance = {"mode": "none", "source": None, "copied_parameters": 0}
                    training_reason = "legacy_discount"
                    compiled_parameters = 0
                    profile = {}
                    directory = create_artifact_directory(workspace.root / f"attempt_{step:06d}")
                    phase_start = time.monotonic()
                    try:
                        if research:
                            from .compiler_v2 import parameter_estimate
                            if parameter_estimate(genome, definition) > 2_000_000:
                                raise ValueError("compiled candidate exceeds local runtime parameter safety cap")
                        model = search.compile(genome, definition, backend=backend, device=device, seed=model_seed)
                        compiled_parameters = model.parameter_count
                        if model.parameter_count > 2_000_000:
                            raise ValueError("compiled candidate exceeds local runtime parameter safety cap")
                        inheritance = search.inherit(model, definition.id, namespace)
                        ratio = {"exact": 0.3, "partial": 0.6, "none": 1.0}[inheritance["mode"]]
                        allocated = max(1, math.ceil(full_epochs * ratio))
                        if research:
                            full_epochs, allocated, training_reason = allocate_training(
                                epochs, generation, inheritance, model.parameter_count,
                                protected=proposal["protected"], variant=variant)
                        profile["compile_inherit_seconds"] = time.monotonic() - phase_start
                        phase_start = time.monotonic()
                        training = TrainConfig(
                            epochs=allocated,
                            learning_rate=genome.learning_rate,
                            weight_decay=genome.weight_decay,
                            timeout=min(fit_timeout, max(0.001, deadline - time.monotonic())),
                        )
                        request = {
                            "benchmark": definition.id,
                            "shared_root": str(root),
                            "genome": genome.model_dump(mode="json"),
                            "backend": backend,
                            "device": device,
                            "model_seed": model_seed,
                            "data": data,
                            "weights": {k: v.tolist() for k, v in model.weights.items()},
                            "buffers": {k: [np.asarray(a).tolist() for a in v] for k, v in model.buffers.items()},
                            "training": {name: value for name, value in vars_free_training(training).items()},
                            "source_sha256": configuration["source_sha256"],
                        }
                        if research:
                            request["variant"] = variant
                            request["training"]["protected"] = proposal["protected"] and policy(variant)["training"]
                        profile["request_seconds"] = time.monotonic() - phase_start
                    except (ValueError, TypeError, OverflowError) as error:
                        result = {
                            "status": "failed",
                            "reason": f"invalid pre-fit candidate: {error}",
                            "charged": 0,
                            "invalid": 1,
                        }
                    else:
                        phase_start = time.monotonic()
                        try:
                            result = evaluator.evaluate_many(
                                [
                                    {
                                        "request": request,
                                        "directory": directory,
                                        "timeout": min(fit_timeout + 10, deadline - time.monotonic()),
                                    }
                                ]
                            )[0]
                        except (
                            ValueError,
                            TypeError,
                            OverflowError,
                            OSError,
                            TimeoutError,
                            BrokenProcessPool,
                        ) as error:
                            result = terminal_worker_failure(directory, str(error), deadline - time.monotonic())
                        profile["worker_roundtrip_seconds"] = time.monotonic() - phase_start
                    _crash("worker", step, crash_at, crash_step)
                    phase_start = time.monotonic()
                    if result["status"] == "ok":
                        ref = ArtifactReference(**result["model_artifact"])
                        archive = np.load(io.BytesIO(read_verified_artifact(directory, ref)), allow_pickle=False)
                        model.weights = {key: archive[key] for key in archive.files}
                        model.buffers = {
                            k: tuple(np.asarray(v) for v in values) for k, values in result["buffers"].items()
                        }
                        search.remember(model, namespace)
                    if system == "topograph":
                        search.progress = step / budget
                    if research:
                        result["outcome_id"] = f"candidate_{step:06d}"
                    search.observe(definition.id, genome, result)
                    profile["search_seconds"] = time.monotonic() - phase_start
                    if result["status"] == "ok":
                        result["metric_value"] = (
                            -result["score"] if definition.primary_metric.direction.value == "min" else result["score"]
                        )
                    attempt = {
                        "benchmark_id": definition.id,
                        "outcome_id": f"candidate_{step:06d}",
                        "genome_id": genome.genome_id,
                        "genome": genome.model_dump(mode="json"),
                        "model_seed": model_seed,
                        "generation": generation,
                        "backend": backend,
                        "backend_version": selection.version,
                        "inheritance": inheritance,
                        "full_epochs": full_epochs,
                        "allocated_epochs": allocated,
                        "inherited_epoch_savings": full_epochs - allocated,
                        "directory": directory.name,
                        **result,
                    }
                    if research:
                        attempt.update(proposal=proposal, training_reason=training_reason, profile=profile,
                                       optimizer_state="reset_each_fit", fidelity="trained_dag/v2",
                                       compiled_parameters=compiled_parameters)
                    snapshot_start = time.monotonic()
                    next_state = {
                        **state,
                        "completed": step,
                        "search": runner_search_snapshot(search),
                        "attempts": state["attempts"] + [attempt],
                        "elapsed": clock.elapsed(),
                    }
                    if research:
                        profile["snapshot_seconds"] = time.monotonic() - snapshot_start
                    publication_start = time.monotonic()
                    publish_transaction(transaction_path, state, next_state)
                    _crash("transaction", step, crash_at, crash_step)
                attempt = next_state["attempts"][-1]
                metric = (
                    get_benchmark(attempt["benchmark_id"], shared_root=root).primary_metric.name
                    if attempt["status"] == "ok"
                    else "failed_attempt"
                )
                value = float(attempt["metric_value"]) if attempt["status"] == "ok" else 0.0
                rows = store.evaluations()
                if len(rows) == state["completed"]:
                    row = store.append_evaluation(attempt["benchmark_id"], attempt["outcome_id"], metric, value)
                else:
                    row = rows[-1]
                    if (row.benchmark_id, row.contender_id, row.metric_name, row.metric_value) != (
                        attempt["benchmark_id"],
                        attempt["outcome_id"],
                        metric,
                        value,
                    ):
                        raise ValueError("pending transaction disagrees with committed row")
                _crash("row", step, crash_at, crash_step)
                next_state["tip"] = row.row_sha256
                publication = JournalPublication(
                    workspace.checkpoint_directory, workspace.run_id, f"step_{step}", next_state, previous=state
                )
                publication.stage()
                _crash("stage", step, crash_at, crash_step)
                publication.commit_payload()
                _crash("payload", step, crash_at, crash_step)
                publication.commit_manifest()
                _crash("manifest", step, crash_at, crash_step)
                state = next_state
                if research:
                    timing_path = workspace.root / f"timing_{step:06d}.json"
                    if not timing_path.exists():
                        publish_artifact(timing_path, encode(dict(attempt=step,
                            checkpoint_seconds=time.monotonic()-publication_start, recovery=recovering_transaction)))
            search = search_type(definitions, seed=seed, population_size=population_size, state=state["search"], **search_options)
            derived(workspace.state_path, encode_snapshot(state))
            status = (
                "completed"
                if state["completed"] == budget and all(a["status"] == "ok" for a in state["attempts"])
                else "failed"
                if any(a["status"] == "failed" for a in state["attempts"])
                else "cancelled"
            )
            store.set_metadata("status", status)
            write_report(workspace, store)
            store.verify_evaluation_chain()
            telemetry = search.telemetry()
            telemetry["inheritance"] = {
                "uses": sum(a["inheritance"]["mode"] != "none" for a in state["attempts"]),
                "saved_epochs": sum(a["inherited_epoch_savings"] for a in state["attempts"]),
            }
            telemetry["target_device"] = device
            if research:
                telemetry["runtime_profile"] = runtime_profile(state["attempts"])
                timings = [json.loads(read_document(p.parent, p.name)) for p in sorted(workspace.root.glob("timing_*.json"))]
                telemetry["runtime_profile"]["checkpoint_publications"] = timings
                telemetry["runtime_profile"]["missing_checkpoint_timings"] = sorted(
                    set(range(1, state["completed"]+1)) - {t["attempt"] for t in timings})
                derived(workspace.root / "runtime_profile.json", encode(telemetry["runtime_profile"]))
            derived(workspace.root / "engine_telemetry.json", encode(telemetry))
            derived(
                workspace.summary_path,
                encode({"run_id": workspace.run_id, "status": status, "completed_attempts": state["completed"]}),
            )
        if stop_after is not None and state["completed"] < budget:
            clock.finish()
            return workspace.root
        exported = export_run(workspace, state, definitions, pack, selection, device_class, inherited,
                              extra_artifacts=("runtime_profile.json",) if research else ())
        clock.finish()
        return exported


def perplexity_from_logits(predicted, targets, backend):
    """Reproduce the positive exported LM metric using the training loss algebra."""
    b = backend
    if targets.ndim == 1 and predicted.ndim == 3:
        predicted = predicted[:, -1, :]
    logits = b.array(predicted).reshape((-1, predicted.shape[-1]))
    shifted = logits - b.array(b.numpy(logits).max(axis=-1, keepdims=True))
    log_probs = shifted - b.log(b.exp(shifted).sum(axis=-1, keepdims=True))
    hot = np.eye(logits.shape[-1], dtype=np.float32)[targets.reshape(-1)]
    loss = -(b.array(hot) * log_probs).sum(axis=-1).mean()
    return math.exp(float(b.numpy(loss)))


def replay_export(root, search_type, genome_type):
    """Reconstruct every retained winner from portable JSON/NPZ and checked data."""
    from evonn_shared.export_reader import read_export
    from evonn_shared.engine_evidence import validate_engine_bundle, artifact_json
    from evonn_shared.training import restore_regression_predictions

    bundle = read_export(root)
    validate_engine_bundle(bundle, verify_cache=True)
    config = artifact_json(bundle, "config.yaml")
    search_type, genome_type = select_runtime(search_type, genome_type, variant=config.get("variant", "legacy"))
    if bundle.manifest.system.value != search_type.system:
        raise ValueError("export belongs to a different engine")
    refs = {ref.path: ref for ref in bundle.summary.artifact_digests}
    checks = []
    for winner in bundle.summary.best_per_benchmark:
        definition = get_benchmark(winner.benchmark_id)
        metadata = artifact_json(bundle, "model_" + definition.id + ".json")
        search = search_type([definition], seed=0)
        model = search.compile(
            genome_type.model_validate(metadata["genome"]),
            definition,
            backend=config["backend"],
            device=config["device"],
            seed=0,
        )
        payload = read_verified_artifact(root, refs["model_" + definition.id + ".npz"])
        arrays = np.load(io.BytesIO(payload), allow_pickle=False)
        if set(arrays.files) != set(model.weights):
            raise ValueError("saved model parameters disagree with compiler")
        model.weights = {key: arrays[key] for key in arrays.files}
        model.buffers = {
            k: tuple(np.asarray(v, dtype=np.float32) for v in values) for k, values in metadata["buffers"].items()
        }
        prefix = "datasets/" + definition.id + "/"
        x = np.load(io.BytesIO(read_verified_artifact(root, refs[prefix + "x_validation.npy"])), allow_pickle=False)
        y = np.load(io.BytesIO(read_verified_artifact(root, refs[prefix + "y_validation.npy"])), allow_pickle=False)
        preprocessing = metadata["preprocessing"]
        x = (
            (x - np.asarray(preprocessing["feature_mean"], dtype=np.float32))
            / np.asarray(preprocessing["feature_std"], dtype=np.float32)
        ).astype(np.float32)
        b = model.backend
        predicted = b.numpy(
            model.forward({k: b.array(v) for k, v in model.weights.items()}, b.array(x), training=False, seed=0)
        )
        if definition.task_kind.value == "regression":
            predicted = restore_regression_predictions(
                predicted, preprocessing["target_mean"], preprocessing["target_std"]
            )
            calibration = preprocessing["calibration"]
            predicted = predicted * calibration["slope"] + calibration["intercept"]
            observed = float(np.mean((predicted.reshape(-1) - y.reshape(-1)) ** 2))
        elif definition.task_kind.value == "language_modeling":
            observed = perplexity_from_logits(predicted, y, b)
        else:
            observed = float(np.mean(predicted.argmax(axis=-1) == y))
        if not math.isclose(observed, winner.value, rel_tol=1e-6, abs_tol=1e-8):
            raise ValueError(f"saved model does not reproduce {definition.id}: {observed} versus {winner.value}")
        checks.append({"benchmark": definition.id, "observed": observed, "exported": winner.value})
    return {"run_id": bundle.manifest.run_id, "status": "passed", "checks": checks}
