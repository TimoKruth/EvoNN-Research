"""Read-only, engine-import-free validation of current engine evidence artifacts."""

from collections import Counter
import hashlib
import json
import math
from .artifact_io import read_verified_artifact
from .canonical import canonical_sha256
from .catalog import get_benchmark, load_parity_pack
from .dataset_cache import verify_split_cache
from .benchmarks import resolve_data_root
from .export_reader import read_document
from .rng import derive_stream, StreamName

MANDATORY_TELEMETRY = {
    "prism": ("family_distribution", "archive_occupancy", "operator_success", "inheritance", "generations"),
    "topograph": ("topology_size", "novelty_metrics", "operator_success", "inheritance", "species", "generations"),
}


def artifact_json(bundle, name):
    refs = {r.path: r for r in bundle.summary.artifact_digests}
    if name not in refs:
        raise ValueError(f"missing checksum-bound engine artifact: {name}")
    return json.loads(read_verified_artifact(bundle.root, refs[name], max_bytes=128 * 1024**2))


def validate_engine_bundle(bundle, *, verify_cache=False):
    manifest = bundle.manifest
    system = manifest.system.value
    if system not in MANDATORY_TELEMETRY:
        return
    telemetry = artifact_json(bundle, "engine_telemetry.json")
    missing = [key for key in MANDATORY_TELEMETRY[system] if key not in telemetry]
    if not isinstance(telemetry, dict) or telemetry.get("system") != system or missing:
        raise ValueError(f"mandatory engine telemetry missing or foreign: {missing}")
    pack = load_parity_pack(manifest.pack_id)
    if any(not isinstance(telemetry[key], dict) for key in MANDATORY_TELEMETRY[system]):
        raise ValueError("mandatory telemetry must contain structured mappings")
    if set(telemetry["generations"]) != set(pack.benchmarks):
        raise ValueError("engine telemetry does not cover the complete benchmark pack")
    config = artifact_json(bundle, manifest.config_snapshot.path)
    ledger = artifact_json(bundle, "attempts.json")
    state = artifact_json(bundle, "state.json")
    data = artifact_json(bundle, "dataset_provenance.json")
    if config != state["config"] or (
        config["system"],
        config["pack"],
        config["total"],
        config["seed"],
        config["git_commit"],
    ) != (system, manifest.pack_id, manifest.accounting.evaluation_count, manifest.seed, manifest.git_commit):
        raise ValueError("engine source/config/checkpoint provenance disagreement")
    if config["backend"] != manifest.runtime.backend.value or config["source_sha256"] is None:
        raise ValueError("engine backend/source fingerprint missing or inconsistent")
    topology = manifest.runtime.worker_topology
    supervisors = 1 if system == "topograph" else 0
    if (
        (config["training_worker_count"], config["supervisor_count"], config["evaluation_process_count"])
        != (1, supervisors, 1 + supervisors)
        or topology.worker_count != 1
        or topology.process_count != 1
    ):
        raise ValueError("training/supervisor process disclosure disagreement")
    if len(config["source_sha256"]) != 64:
        raise ValueError("invalid source fingerprint")
    if ledger["accounting"] != manifest.accounting.model_dump(mode="json") or ledger["attempts"] != state["attempts"]:
        raise ValueError("engine ledger/checkpoint/accounting disagreement")
    attempts = ledger["attempts"]
    data_bytes = read_verified_artifact(
        bundle.root,
        next(ref for ref in bundle.summary.artifact_digests if ref.path == "dataset_provenance.json"),
        max_bytes=16 * 1024**2,
    )
    if state["dataset_sha256"] != hashlib.sha256(data_bytes).hexdigest():
        raise ValueError("checkpoint dataset digest disagrees with exported provenance")
    for benchmark, generation in telemetry["generations"].items():
        search = state["search"]["benchmarks"][benchmark]
        if type(generation) is not int or generation < 0 or generation != search["generation"]:
            raise ValueError("invalid engine generation telemetry")
        if system == "prism":
            distribution = telemetry["family_distribution"][benchmark]
            if (
                not isinstance(distribution, dict)
                or any(type(v) is not int or v <= 0 for v in distribution.values())
                or distribution != dict(Counter(g["family"] for g in search["population"]))
            ):
                raise ValueError("family distribution disagrees with population")
            expected = {
                "family": len(search["niches"]),
                "pareto": len(search["pareto"]),
                "elite": int(search["elite"] is not None),
            }
            if telemetry["archive_occupancy"][benchmark] != expected:
                raise ValueError("archive occupancy disagrees with checkpoint")
        else:
            descriptors = telemetry["topology_size"][benchmark]
            if (
                not isinstance(descriptors, list)
                or len(descriptors) != len(search["population"])
                or any(
                    not isinstance(v, list)
                    or len(v) != 5
                    or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in v)
                    for v in descriptors
                )
            ):
                raise ValueError("invalid topology descriptor telemetry")
            novelty = telemetry["novelty_metrics"][benchmark]
            if (
                not isinstance(novelty, dict)
                or type(novelty["archive_size"]) is not int
                or novelty["archive_size"] != len(search["novelty"])
                or type(novelty["weight"]) not in (int, float)
                or not 0 <= novelty["weight"] <= 1
            ):
                raise ValueError("invalid novelty telemetry")
            if telemetry["species"][benchmark] != search["species"]:
                raise ValueError("species telemetry differs from checkpoint")
    expected_operators = state["search"]["operator_stats"] if system == "prism" else state["search"]["scheduler"]
    if telemetry["operator_success"] != expected_operators:
        raise ValueError("operator telemetry differs from checkpoint")
    prefix = ledger["resumed_attempt_prefix"]
    if type(prefix) is not int or not 0 <= prefix <= len(attempts) or state["completed"] != len(attempts):
        raise ValueError("invalid engine resume prefix")
    for attempt in attempts:
        if (
            type(attempt["charged"]) is not int
            or attempt["charged"] not in (0, 1)
            or type(attempt["invalid"]) is not int
            or attempt["invalid"] not in (0, 1)
        ):
            raise ValueError("attempt counters must be exact zero/one integers")
    if manifest.accounting.cached_evaluations != manifest.accounting.resumed_evaluations:
        raise ValueError("engine has no non-resume evaluation cache credits")
    if manifest.accounting.failed_evaluations != sum(
        a["charged"] for a in attempts[prefix:] if a["status"] == "failed"
    ) or manifest.accounting.invalid_evaluations != sum(a["invalid"] for a in attempts[prefix:]):
        raise ValueError("engine failed/invalid accounting mismatch")
    if telemetry["inheritance"] != {
        "uses": sum(a["inheritance"]["mode"] != "none" for a in attempts),
        "saved_epochs": sum(a["inherited_epoch_savings"] for a in attempts),
    }:
        raise ValueError("inheritance telemetry differs from ledger")
    if sum(a["charged"] for a in attempts[:prefix]) != manifest.accounting.resumed_evaluations:
        raise ValueError("engine resume prefix charge mismatch")
    if sum(a["charged"] for a in attempts[prefix:]) != manifest.accounting.actual_evaluations:
        raise ValueError("engine fresh charge mismatch")
    records = {(r.benchmark_id, r.outcome_id): r for r in bundle.results.records}
    seen = set()
    ordinal = {}
    for index, attempt in enumerate(attempts):
        key = (attempt["benchmark_id"], attempt["outcome_id"])
        if key in seen or key not in records:
            raise ValueError("duplicate or absent engine attempt")
        seen.add(key)
        record = records[key]
        charge = attempt["charged"] if index >= prefix else 0
        if (
            record.evaluation_count != charge
            or record.status.value != attempt["status"]
            or record.reason != attempt["reason"]
        ):
            raise ValueError("engine record differs from attempt")
        current = ordinal[attempt["benchmark_id"]] if attempt["benchmark_id"] in ordinal else 0
        expected_seed = int(
            canonical_sha256(
                {
                    "stream": str(derive_stream(manifest.seed, StreamName.INIT)),
                    "benchmark": attempt["benchmark_id"],
                    "attempt": current,
                },
                schema_version="evonn-engine-init/v1",
                digest_field=None,
            )[:8],
            16,
        )
        ordinal[attempt["benchmark_id"]] = current + 1
        if (
            expected_seed != attempt["model_seed"]
            or attempt["backend"] != manifest.runtime.backend.value
            or attempt["backend_version"] != manifest.runtime.backend_version
        ):
            raise ValueError("engine attempt RNG/backend mismatch")
        mode = attempt["inheritance"]["mode"]
        if mode not in {"none", "exact", "partial"}:
            raise ValueError("invalid inheritance mode")
        if attempt["allocated_epochs"] != max(
            1, math.ceil(attempt["full_epochs"] * {"none": 1, "exact": 0.3, "partial": 0.6}[mode])
        ):
            raise ValueError("inheritance ratio differs from declared training policy")
        if attempt["status"] == "ok":
            if attempt["charged"] != 1 or record.metric.value != attempt["metric_value"]:
                raise ValueError("engine successful metric/charge mismatch")
            quality = -attempt["metric_value"] if record.metric.direction.value == "min" else attempt["metric_value"]
            if quality != attempt["score"]:
                raise ValueError("native metric and evolutionary fitness disagree")
            for field in ("parameter_count", "train_seconds", "model_bytes", "peak_memory_bytes"):
                measured = record.model_dump(mode="json")[field]
                expected_value = attempt[field] if field in attempt else None
                if measured["value"] != expected_value or measured["provenance"] != (
                    "measured" if expected_value is not None else "unavailable"
                ):
                    raise ValueError("engine ledger/result measurement mismatch")
            if not all(
                math.isfinite(attempt[k]) and attempt[k] >= 0
                for k in ("latency_seconds", "train_seconds", "model_bytes", "packed_bytes_estimate")
            ):
                raise ValueError("engine measurements absent/nonfinite")
            if not 1 <= attempt["epochs"] <= attempt["allocated_epochs"] <= attempt["full_epochs"]:
                raise ValueError("engine epoch accounting invalid")
            if attempt["inherited_epoch_savings"] != attempt["full_epochs"] - attempt["allocated_epochs"]:
                raise ValueError("engine inheritance saving mismatch")
    if any(r.status.value != "skipped" for key, r in records.items() if key not in seen):
        raise ValueError("unaccounted engine result")
    payload = read_document(resolve_data_root(), "runtime/tier1_core_v1.json")
    runtime = json.loads(payload)
    if config["dataset_versions"] != runtime["versions"]:
        raise ValueError("engine dataset version drift")
    if {item["benchmark_id"] for item in data} != set(pack.benchmarks) or len(data) != len(pack.benchmarks):
        raise ValueError("engine dataset provenance does not cover pack exactly")
    for item in data:
        definition = get_benchmark(item["benchmark_id"])
        expected = canonical_sha256(
            definition.model_dump(mode="json"), schema_version="evonn.catalog.benchmark/v1", digest_field=None
        )
        if (
            item["definition_sha256"] != expected
            or item["runtime_manifest_sha256"] != hashlib.sha256(payload).hexdigest()
            or item["seed"] != manifest.seed
            or item["split_policy"] != runtime["split_policy"]
        ):
            raise ValueError("engine dataset/split provenance mismatch")
        binding = runtime["benchmarks"][definition.id]
        generated = binding["loader"].startswith("make_")
        if item["raw_reference_sha256"] != binding["reference_raw_sha256"] or item["raw_reference_match"] != (
            item["raw_sha256"] == binding["reference_raw_sha256"]
        ):
            raise ValueError("raw data reference binding differs")
        if not generated and item["raw_sha256"] != binding["reference_raw_sha256"]:
            raise ValueError("raw data differs from reviewed reference")
        if manifest.seed == 42 and item["split_sha256"] != binding["reference_split_sha256"]:
            raise ValueError("seed-42 split differs from reviewed reference")
        if verify_cache:
            portable = {**item, "cache_directory": str(bundle.root / "datasets" / definition.id)}
            references = {ref.path: ref for ref in bundle.summary.artifact_digests}
            for artifact in item["cache_artifacts"]:
                name = "datasets/" + definition.id + "/" + artifact["path"]
                if name not in references or references[name].sha256 != artifact["sha256"]:
                    raise ValueError("portable dataset cache absent or unbound")
            verify_split_cache(
                portable,
                feature_count=math.prod(definition.input_shape),
                regression=definition.task_kind.value == "regression",
            )
    if manifest.runtime.backend.value == "numpy_fallback" and not any(
        flag.code == "portability_only" for flag in bundle.summary.fairness_flags
    ):
        raise ValueError("NumPy engine evidence must be marked portability_only")
