"""Read-only, engine-import-free validation of current engine evidence artifacts."""

from collections import Counter
import hashlib
import json
import math
from .artifact_io import read_verified_artifact
from .canonical import canonical_sha256
from .active_catalog import get_benchmark, load_parity_pack
from .dataset_cache import verify_split_cache
from .benchmarks import resolve_data_root
from .export_reader import read_document
from .rng import derive_stream, StreamName
from .runtime_catalog import runtime_manifest as read_runtime_manifest
from .runtime_budget import MAX_ENGINE_EVALUATIONS

MANDATORY_TELEMETRY = {
    "stratograph": ("hierarchy", "occupied_niches", "operator_success", "inheritance", "generations"),
    "primordia": ("primitive_usage", "archive_size", "operator_success", "inheritance", "generations"),
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
    if type(config["total"]) is not int or not 1 <= config["total"] <= MAX_ENGINE_EVALUATIONS:
        raise ValueError("engine evaluation budget exceeds supported bounded history")
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
    mode = config.get("evaluation_mode")
    if mode is not None and (system != "topograph" or mode != "isolated-serial/v1"):
        raise ValueError("unsupported engine evaluation mode")
    supervisors = 1 if system == "topograph" and mode is None else 0
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
        elif system == "topograph":
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
        elif system == "stratograph":
            if telemetry["occupied_niches"][benchmark] != len(search["niches"]):
                raise ValueError("hierarchy niches differ from checkpoint")
            counts = dict(Counter(node["primitive"] for genome in search["population"] for cell in genome["cells"] for node in cell["nodes"]))
            if telemetry["motif_frequency"][benchmark] != counts or telemetry["lineage"][benchmark] != search["lineage"]:
                raise ValueError("hierarchy motif/lineage differs from checkpoint")
            if len(telemetry["hierarchy"][benchmark]) != len(search["population"]):
                raise ValueError("hierarchy descriptors do not cover population")
        elif system == "primordia":
            counts = dict(Counter(node["operator"] for item in search["archive"] for node in item["genome"]["primitives"]))
            if telemetry["primitive_usage"][benchmark] != counts or telemetry["archive_size"][benchmark] != len(search["archive"]) or telemetry["lineage"][benchmark] != search["lineage"]:
                raise ValueError("primitive bank telemetry differs from checkpoint")
    if system in {"stratograph", "primordia"}:
        expected_fidelity = "hierarchy_features_trained_head" if system == "stratograph" else "end_to_end_primitive"
        if config.get("evaluator_fidelity") != expected_fidelity or telemetry.get("evaluator_fidelity") != expected_fidelity:
            raise ValueError("engine evaluator fidelity missing or inconsistent")
        if system == "stratograph":
            _validate_hierarchy_artifacts(bundle, config, attempts, state, telemetry)
        else:
            _validate_primitive_artifacts(bundle, config, attempts, data)
    expected_operators = state["search"]["scheduler"] if system == "topograph" else state["search"]["operator_stats"]
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
        if system == "primordia":
            definition = get_benchmark(attempt["benchmark_id"])
            expensive = definition.task_kind.value == "language_modeling" or definition.input_modality.value == "image"
            maximum = min(4 if expensive else 8, 3 if current >= 16 else 1000)
            if attempt["full_epochs"] > maximum or attempt["genome"]["width"] > (12 if expensive else 24) or len(attempt["genome"]["primitives"]) > (2 if expensive else 4):
                raise ValueError("primitive training or architecture cap exceeded")
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
        payload,runtime=read_runtime_manifest(item["benchmark_id"])
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
        if expected != binding["definition_sha256"]:
            raise ValueError("current dataset definition differs from pinned runtime")
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


def _validate_primitive_artifacts(bundle, config, attempts, data):
    """Recompute the complete bank envelope from ledger evidence, without engine imports."""
    from .seed_artifact import SeedArtifact
    manifest=bundle.manifest
    grouped={}
    for row in attempts:
        key=(row["benchmark_id"],row["genome_id"])
        if row["status"]=="ok" and (key not in grouped or grouped[key]["score"]<row["score"]):
            grouped[key]=row
    ranked=sorted(grouped.values(),key=lambda row:(row["benchmark_id"],-row["score"],row["genome_id"]))
    payloads=artifact_json(bundle,"seed_candidates.json")
    if not isinstance(payloads,list) or len(payloads)!=len(ranked):
        raise ValueError("seed bank does not cover successful unique candidates exactly")
    bindings={item["benchmark_id"]:item for item in data}
    entries=[]
    leaders={}
    families={}
    for payload,row in zip(payloads,ranked,strict=True):
        seed=SeedArtifact.model_validate(payload)
        definition=get_benchmark(row["benchmark_id"])
        genome=row["genome"]
        descriptors=dict(width=float(genome["width"]),depth=float(len(genome["primitives"])),
            gates=float(sum(p["operator"]=="gate" for p in genome["primitives"])),
            sparse=float(sum(p["operator"]=="sparse" for p in genome["primitives"])))
        expected_source=dict(engine="primordia",version=config["engine_version"],commit=manifest.git_commit,
            code_dirty=config["code_dirty"],run_id=manifest.run_id,candidate_id=row["genome_id"],
            benchmark=definition.id,pack=manifest.pack_id,seed=manifest.seed,
            budget_spent=sum(a["charged"] for a in attempts),runtime=manifest.runtime.model_dump(mode="json"))
        if seed.source.model_dump(mode="json")!=expected_source or seed.encoding!={"format":"primordia.primitive/v1","genome":genome}:
            raise ValueError("seed source/genome differs from ledger")
        if seed.quality.model_dump()!=dict(metric=definition.primary_metric.name,direction=definition.primary_metric.direction.value,value=float(row["metric_value"])) or seed.descriptors!=descriptors:
            raise ValueError("seed quality/descriptors differ from ledger")
        provenance=bindings[definition.id]
        if seed.contamination.raw_sha256!=provenance["raw_sha256"] or seed.contamination.split_sha256!=provenance["split_sha256"] or seed.diversity!={"operator_types":float(len({p["operator"] for p in genome["primitives"]}))}:
            raise ValueError("seed contamination/diversity differs from source")
        if seed.compatible_targets!=["stratograph","topograph","prism"]:
            raise ValueError("primitive export must disclose all supported translation targets")
        entry=dict(benchmark=definition.id,candidate=row["genome_id"],genome=genome,quality=row["metric_value"],
            direction=definition.primary_metric.direction.value,metric=definition.primary_metric.name,descriptors=descriptors,
            rank=1+sum(item["benchmark"]==definition.id for item in entries),transfer_status="unproven",
            selection="validation only; no downstream evidence")
        entries.append(entry)
        if definition.id not in leaders:
            leaders[definition.id]=entry
            family=definition.input_modality.value+":"+definition.task_kind.value
            if family not in families:
                families[family]=[]
            families[family].append(entry)
    expected_bank=dict(schema_version=1,entries=entries,benchmark_coverage=sorted(leaders),
        operator_coverage=dict(Counter(p["operator"] for row in ranked for p in row["genome"]["primitives"])),transfer_status="unproven")
    expected_leaders=dict(benchmarks=leaders,families=families,family_policy="per-benchmark representatives; no cross-metric numeric ranking")
    if artifact_json(bundle,"primitive_bank.json")!=expected_bank or artifact_json(bundle,"search_leaders.json")!=expected_leaders or artifact_json(bundle,"best_results.json")!=leaders:
        raise ValueError("primitive bank/rank/leaders differ from verified trials")
    if artifact_json(bundle,"trial_records.json")!=attempts:
        raise ValueError("primitive bank trial ledger differs")
    expected_context=dict(config=config,run_id=manifest.run_id,runtime=manifest.runtime.model_dump(mode="json"),
        version=config["engine_version"],budget_spent=sum(a["charged"] for a in attempts),data=data,
        definitions={name:get_benchmark(name).model_dump(mode="json") for name in bindings})
    if artifact_json(bundle,"bank_context.json")!=expected_context:
        raise ValueError("primitive reconstruction context differs from export")


def _hierarchy_descriptor(genome):
    def depth(nodes,edges,output):
        incoming={node["id"]:[] for node in nodes}
        if len(incoming)!=len(nodes) or output not in incoming:
            raise ValueError("invalid hierarchy graph identities")
        seen=set()
        for edge in edges:
            pair=(edge["source"],edge["target"])
            if pair in seen or pair[0] not in incoming or pair[1] not in incoming:
                raise ValueError("invalid hierarchy graph edge")
            seen.add(pair)
            incoming[pair[1]].append(pair[0])
        depths={}
        while len(depths)<len(nodes):
            ready=sorted(name for name,parents in incoming.items() if name not in depths and all(p in depths for p in parents))
            if not ready:
                raise ValueError("cyclic hierarchy graph")
            for name in ready:
                depths[name]=1+max((depths[p] for p in incoming[name]),default=0)
        ancestors={output}
        for _ in nodes:
            ancestors.update(p for name in tuple(ancestors) for p in incoming[name])
        if ancestors!=set(incoming):
            raise ValueError("dead hierarchy node")
        return depths[output]
    cells=genome["cells"]
    cell_ids={cell["id"] for cell in cells}
    if len(cell_ids)!=len(cells) or cell_ids!={node["cell_id"] for node in genome["macro_nodes"]}:
        raise ValueError("hierarchy cell-library binding differs")
    values=[depth(cell["nodes"],cell["edges"],cell["output"]) for cell in cells]
    return dict(macro_depth=depth(genome["macro_nodes"],genome["macro_edges"],genome["output"]),
        average_cell_depth=sum(values)/len(values),max_cell_depth=max(values),
        reuse_ratio=1-len(cells)/len(genome["macro_nodes"]),inter_level_connectivity=len(genome["macro_edges"]),
        collapsed=len(genome["macro_nodes"])==1,widths=[node["width"] for cell in cells for node in cell["nodes"]])


def _validate_hierarchy_artifacts(bundle,config,attempts,state,telemetry):
    for benchmark,search in state["search"]["benchmarks"].items():
        if telemetry["hierarchy"][benchmark]!=[_hierarchy_descriptor(g) for g in search["population"]]:
            raise ValueError("hierarchy descriptors differ from checkpoint graphs")
    winners={}
    for row in attempts:
        benchmark=row["benchmark_id"]
        if row["status"]=="ok" and (benchmark not in winners or row["score"]>winners[benchmark]["score"]):
            winners[benchmark]=row
    local={}
    global_counts=Counter()
    for benchmark,row in winners.items():
        genome=row["genome"]
        counts=Counter(hashlib.sha256(json.dumps({key:cell[key] for key in ("nodes","edges","output")},
            sort_keys=True,separators=(",",":")).encode()).hexdigest() for cell in genome["cells"])
        global_counts.update(counts)
        local[benchmark]=dict(candidate=row["genome_id"],quality=row["metric_value"],descriptors=_hierarchy_descriptor(genome),
            programs=dict(counts),cells=genome["cells"],lineage=state["search"]["benchmarks"][benchmark]["lineage"])
    expected=dict(schema_version=1,evaluator_fidelity="hierarchy_features_trained_head",global_frequency=dict(global_counts),
        local_winners=local,variant=config["variant"],
        interpretation="Deterministic cell programs with a trained GELU head; no end-to-end hierarchy or transfer claim.")
    diagnostics=[]
    for name in load_parity_pack(bundle.manifest.pack_id).benchmarks:
        definition=get_benchmark(name)
        if definition.task_kind.value=="language_modeling":
            values=[row["metric_value"] for row in attempts if row["benchmark_id"]==name and row["status"]=="ok"]
            diagnostics.append(dict(benchmark=name,values=values,flatline=len(values)>1 and max(values)-min(values)<1e-8,
                causal_input=True,evaluator_fidelity="hierarchy_features_trained_head",broad_claim_ready=False,
                reason="proxy LM requires repeated real-text native qualification"))
    if artifact_json(bundle,"motif_analysis.json")!=expected or artifact_json(bundle,"lm_diagnostics.json")!=diagnostics:
        raise ValueError("hierarchy motif/LM claims differ from measured winners")
