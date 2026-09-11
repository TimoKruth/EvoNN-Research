"""Package-local search coordinator and worker using the shared publication boundary."""

from datetime import datetime, timezone
from dataclasses import asdict
import hashlib
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
)
from .tensors import Backend
from .training import TrainConfig, fit
from .research import policy, allocate_training, summarize_attempts, architecture_identity, finalist_seeding
from .genome import ModelGenome


def evaluation_worker(request, output, search_type, genome_type):
    worker_started = time.monotonic()
    if request["source_sha256"] != source_identity():
        raise ValueError("worker source changed since run began")
    definition = get_benchmark(request["benchmark"], shared_root=Path(request["shared_root"]))
    search = search_type([definition], seed=0)
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
        model.optimizer_state = request.get("optimizer_state")
        provenance = request["data"]
        arrays = {}
        for item in provenance["cache_artifacts"]:
            ref = ArtifactReference(path=item["path"], sha256=item["sha256"])
            payload = read_verified_artifact(Path(provenance["cache_directory"]), ref, size_bytes=item["size_bytes"])
            arrays[Path(ref.path).stem] = np.load(io.BytesIO(payload), allow_pickle=False)
        config = TrainConfig(**request["training"])
        preparation_seconds = time.monotonic() - worker_started
    except (ValueError, TypeError, OverflowError) as error:
        publish_artifact(
            output,
            encode(
                {"status": "failed", "reason": f"invalid pre-fit configuration: {error}", "charged": 0, "invalid": 1}
            ),
        )
        return
    publish_artifact(output.parent / "started", b"fit\n")
    try:
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
        buffer = io.BytesIO()
        np.savez(buffer, **model.weights)
        artifact = publish_artifact(output.parent / "weights.npz", buffer.getvalue())
        packed = sum(v.nbytes for v in model.weights.values())
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
            optimizer_state=model.optimizer_state if config.optimizer_policy == "continue" else None,
            worker_preparation_seconds=preparation_seconds,
            worker_publication_seconds=time.monotonic() - worker_started - preparation_seconds - result["train_seconds"],
        )
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
    variant="open",
    inheritance_policy="enabled",
    optimizer_policy="restart",
    optimizer_backend="numpy",
    fixed_genomes=None,
    prior_discovery=None,
    resume=None,
    stop_after=None,
    crash_at=None,
    crash_step=1,
):
    research = policy(variant)
    if inheritance_policy not in {"enabled", "disabled"} or optimizer_policy not in {"restart", "continue"} or optimizer_backend not in {"numpy", "native"}:
        raise ValueError("invalid inheritance or optimizer policy")
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
    if fixed_genomes is not None:
        if not research["training"] or set(fixed_genomes) != set(pack.benchmarks):
            raise ValueError("fixed architectures require training/open variant and the complete benchmark pack")
        fixed_genomes = {key: ModelGenome.model_validate(value).model_dump(mode="json") for key, value in fixed_genomes.items()}
    if prior_discovery is not None:
        if fixed_genomes is None or not isinstance(prior_discovery, dict) or prior_discovery.get("accounting") != "reported_prior":
            raise ValueError("prior discovery must accompany fixed architectures with reported_prior accounting")
        if type(prior_discovery.get("source_fits")) is not int or prior_discovery["source_fits"] < 1:
            raise ValueError("prior discovery requires a positive source fit count")
        if prior_discovery.get("fixed_genomes_sha256") != canonical_sha256(fixed_genomes, schema_version="prism.fixed-genomes/v1", digest_field=None):
            raise ValueError("fixed architectures differ from their discovery provenance")
    seeding = finalist_seeding(prior_discovery)
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
        "variant": variant,
        "inheritance_policy": inheritance_policy,
        "optimizer_policy": optimizer_policy,
        "optimizer_backend": optimizer_backend,
        "fixed_genomes": fixed_genomes,
        "prior_discovery": prior_discovery,
        "evaluation_process_count": 1,
        "training_worker_count": 1,
        "supervisor_count": 0,
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
            definitions, seed=int(derive_stream(seed, StreamName.SEARCH)), population_size=population_size, variant=variant,
            fixed_genomes=fixed_genomes
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
    with boundary_ownership(workspace.root):
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
                step = state["completed"] + 1
                transaction_path = workspace.root / f"transaction_{step:06d}.json"
                if transaction_path.exists():
                    transaction = load_transaction(transaction_path, state)
                    search = None  # Rebuild from committed state after transaction recovery.
                    next_state = transaction["state"]
                    inherited = max(inherited, step)
                else:
                    if search is None:
                        search = search_type(definitions, seed=seed, population_size=population_size, state=state["search"], variant=variant)
                    counts = {d.id: sum(a["benchmark_id"] == d.id for a in state["attempts"]) for d in definitions}
                    definition = min(definitions, key=lambda d: (counts[d.id], d.id))
                    genome = search.candidate(definition.id)
                    proposal = search.proposal(definition.id, genome)
                    proposal_started = time.monotonic()
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
                    full_epochs = epochs
                    allocated = full_epochs
                    allocation_reason = "candidate_not_compiled"
                    compiled_parameters = 0
                    inheritance = {"mode": "none", "source": None, "copied_parameters": 0}
                    full_epochs, allocated, allocation_reason = allocate_training(
                        epochs, generation, inheritance, 0, protected=proposal["protected"], variant=variant)
                    directory = create_artifact_directory(workspace.root / f"attempt_{step:06d}")
                    try:
                        model = search.compile(genome, definition, backend=backend, device=device, seed=model_seed)
                        compiled_parameters = model.parameter_count
                        if model.parameter_count > 2_000_000:
                            raise ValueError("compiled candidate exceeds local runtime parameter safety cap")
                        fresh_proposal = research["archive"] and proposal["origin"] in {"fresh", "initial"}
                        if inheritance_policy == "enabled" and not fresh_proposal:
                            inheritance = search.inherit(model, definition.id, namespace)
                        full_epochs, allocated, allocation_reason = allocate_training(
                            epochs, generation, inheritance, model.parameter_count,
                            protected=proposal["protected"], variant=variant)
                        training = TrainConfig(
                            epochs=allocated,
                            learning_rate=genome.learning_rate,
                            weight_decay=genome.weight_decay,
                            timeout=min(fit_timeout, max(0.001, deadline - time.monotonic())),
                            preserve_initial=research["training"] and inheritance["mode"] != "none",
                            minimum_epochs=allocated if research["training"] and proposal["protected"] else 1,
                            native_optimizer=optimizer_backend == "native",
                            optimizer_policy=optimizer_policy,
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
                            "training": asdict(training),
                            "source_sha256": configuration["source_sha256"],
                            "optimizer_state": getattr(model, "optimizer_state", None) if optimizer_policy == "continue" else None,
                        }
                    except (ValueError, TypeError, OverflowError) as error:
                        result = {
                            "status": "failed",
                            "reason": f"invalid pre-fit candidate: {error}",
                            "charged": 0,
                            "invalid": 1,
                        }
                    else:
                        dispatch_started = time.monotonic()
                        preparation_seconds = dispatch_started - proposal_started
                        try:
                            result = _process(
                                system,
                                "_worker",
                                request,
                                directory,
                                min(fit_timeout + 10, deadline - time.monotonic()),
                            )
                        except (ValueError, TypeError, OverflowError, OSError) as error:
                            result = terminal_worker_failure(directory, str(error), deadline - time.monotonic())
                        result["dispatch_seconds"] = time.monotonic() - dispatch_started
                        result["proposal_preparation_seconds"] = preparation_seconds
                    result["proposal_to_result_seconds"] = time.monotonic() - proposal_started
                    coordinator_started = time.monotonic()
                    _crash("worker", step, crash_at, crash_step)
                    if result["status"] == "ok":
                        ref = ArtifactReference(**result["model_artifact"])
                        archive = np.load(io.BytesIO(read_verified_artifact(directory, ref)), allow_pickle=False)
                        model.weights = {key: archive[key] for key in archive.files}
                        model.buffers = {
                            k: tuple(np.asarray(v) for v in values) for k, values in result["buffers"].items()
                        }
                        model.optimizer_state = result.pop("optimizer_state", None)
                        search.remember(model, namespace)
                    result["inheritance"] = inheritance
                    search.observe(definition.id, genome, result)
                    if result["status"] == "ok":
                        result["metric_value"] = (
                            -result["score"] if definition.primary_metric.direction.value == "min" else result["score"]
                        )
                    attempt = {
                        "benchmark_id": definition.id,
                        "outcome_id": f"candidate_{step:06d}",
                        "genome_id": genome.genome_id,
                        "architecture_id": architecture_identity(genome),
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
                        "proposal": proposal,
                        "allocation_reason": allocation_reason,
                        "compiled_parameter_count": compiled_parameters,
                        "lineage_updates": inheritance.get("source_updates", 0) + result.get("updates", 0),
                        **result,
                    }
                    attempt["coordinator_update_seconds"] = time.monotonic() - coordinator_started
                    next_state = {
                        **state,
                        "completed": step,
                        "search": runner_search_snapshot(search),
                        "attempts": state["attempts"] + [attempt],
                        "elapsed": clock.elapsed(),
                    }
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
            search = search_type(definitions, seed=seed, population_size=population_size, state=state["search"], variant=variant)
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
            telemetry["research"] = summarize_attempts(state["attempts"])
            derived(workspace.root / "engine_telemetry.json", encode(telemetry))
            derived(
                workspace.summary_path,
                encode({"run_id": workspace.run_id, "status": status, "completed_attempts": state["completed"]}),
            )
        if stop_after is not None and state["completed"] < budget:
            clock.finish()
            return workspace.root
        exported = export_run(workspace, state, definitions, pack, selection, device_class, inherited, seeding_override=seeding)
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
