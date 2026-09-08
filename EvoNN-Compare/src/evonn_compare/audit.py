"""Evidence-based benchmark admission; contract readiness is distinct from decisions."""
from copy import deepcopy
import hashlib
import json
import math

from evonn_shared.artifact_io import read_verified_artifact
from evonn_shared.benchmarks import resolve_data_root
from evonn_shared.canonical import canonical_sha256
from evonn_shared.active_catalog import get_benchmark, load_parity_pack
from evonn_shared.export_reader import read_document
from evonn_shared.dataset_cache import verify_split_cache
from evonn_shared.rng import derive_stream, StreamName
from evonn_shared.runtime_catalog import runtime_manifest as read_runtime_manifest


def artifact_json(bundle, name: str):
    references = {item.path: item for item in bundle.summary.artifact_digests}
    if name not in references:
        raise ValueError(f"missing checksum-bound evidence artifact: {name}")
    return json.loads(read_verified_artifact(bundle.root, references[name], max_bytes=16 * 1024 * 1024))


def benchmark_audit(pack_name: str, bundles: list, *, decision_grade: bool = False,
                    dashboard_present: bool = False, output_levels: dict | None = None, cache_roots: dict | None = None) -> dict:
    pack = load_parity_pack(pack_name)
    definitions = [get_benchmark(name) for name in pack.benchmarks]
    blockers, warnings, runs = [], [], []
    floor = {definition.id: {"successful": set(), "enhanced": set(), "enhanced_seeds": {}, "weak": [], "cache": False} for definition in definitions}
    runtime_payload = read_document(resolve_data_root(), "runtime/tier1_core_v1.json")
    runtime_hash = hashlib.sha256(runtime_payload).hexdigest()
    runtime_manifest = json.loads(runtime_payload)
    for bundle in bundles:
        manifest = bundle.manifest
        if manifest.pack_id != pack_name or manifest.system.value != "contenders":
            continue
        candidate_floor = deepcopy(floor)
        try:
            config = artifact_json(bundle, manifest.config_snapshot.path)
            ledger = artifact_json(bundle, "attempts.json")
            datasets = artifact_json(bundle, "dataset_provenance.json")
            if config["dataset_versions"] != runtime_manifest["versions"]:
                raise ValueError("dataset package versions differ from reviewed runtime")
            if config["git_commit"] != manifest.git_commit or config["seed"] != manifest.seed:
                raise ValueError("config/export provenance differs")
            if ledger["accounting"] != manifest.accounting.model_dump(mode="json"):
                raise ValueError("attempt ledger/accounting mismatch")
            exported = {(record.benchmark_id, record.outcome_id): record for record in bundle.results.records}
            charged = 0
            seen_attempts = set()
            for attempt in ledger["attempts"]:
                charged += attempt["charged"]
                outcome = attempt["outcome_id"] if "outcome_id" in attempt else (
                    attempt["contender_id"] + "_not_run" if attempt["contender_id"] is not None else "dataset_unavailable")
                key = (attempt["benchmark_id"], outcome)
                if key in seen_attempts:
                    raise ValueError("duplicate attempt identity")
                seen_attempts.add(key)
                if key not in exported:
                    raise ValueError("attempt absent from exported results")
                record = exported[key]
                if (record.status.value != attempt["status"] or record.evaluation_count != attempt["charged"]
                        or record.reason != attempt["reason"]):
                    raise ValueError("attempt status/reason/charge differs from exported result")
                if attempt["status"] != "ok":
                    continue
                if key not in exported or exported[key].status.value != "ok" or exported[key].metric.value != attempt["score"]:
                    raise ValueError("successful floor attempt is absent from exported results")
                if exported[key].evaluation_count != attempt["charged"] or attempt["charged"] != 1:
                    raise ValueError("successful floor fit must be charged once")
                name = attempt["contender_id"]
                model = config["pools"]["models"][name]
                if attempt["family"] != model["model"] or attempt["parameters"] != model["parameters"]:
                    raise ValueError("attempt and configured contender disagree")
                backend = attempt["backend"]
                expected_package = {"xgboost": "xgboost", "lightgbm": "lightgbm", "catboost": "catboost", "cnn_small": "torch", "transformer_lm_tiny": "torch"}
                package = expected_package[model["model"]] if model["model"] in expected_package else "scikit-learn"
                if backend["package"] != package or backend["device"] != "cpu" or not backend["version"]:
                    raise ValueError("attempt backend provenance differs from CPU model protocol")
                if package == "scikit-learn" and backend["version"] != runtime_manifest["versions"]["scikit-learn"]:
                    raise ValueError("attempt sklearn version differs from reviewed runtime")
                model_seed = int(canonical_sha256({"stream": str(derive_stream(manifest.seed, StreamName.INIT)),
                    "benchmark": attempt["benchmark_id"], "outcome": outcome}, schema_version="evonn-contender-init-v1", digest_field=None)[:8], 16)
                if attempt["model_seed"] != model_seed:
                    raise ValueError("attempt initialization seed provenance differs")
                state = candidate_floor[attempt["benchmark_id"]]
                if "extra" in model:
                    state["enhanced"].add(name)
                    strength_key = canonical_sha256({"name": name, "configuration": model, "backend": backend,
                        "runtime": manifest.runtime.model_dump(mode="json"), "git_commit": manifest.git_commit,
                        "budget": manifest.budget.model_dump(mode="json")}, schema_version="evonn-enhanced-repeat-v1", digest_field=None)
                    if strength_key not in state["enhanced_seeds"]:
                        state["enhanced_seeds"][strength_key] = set()
                    state["enhanced_seeds"][strength_key].add(manifest.seed)
                else:
                    state["successful"].add(name)
                parameters = model["parameters"]
                if "extra" not in model and parameters and name != "hist_gb_leaf63":
                    state["weak"].append(f"{name}: custom parameters require independent adequacy assessment")
                for parameter, minimum in (("n_estimators", 64), ("max_iter", 100)):
                    if parameter in parameters and parameters[parameter] < minimum:
                        state["weak"].append(f"{name}: reduced {parameter}")
                expected_model = "hist_gb" if name == "hist_gb_leaf63" else name
                if model["model"] != expected_model:
                    state["weak"].append(f"{name}: replaced floor implementation")
            if seen_attempts != set(exported):
                raise ValueError("ledger does not cover every exported outcome exactly once")
            if charged != manifest.accounting.actual_evaluations:
                raise ValueError("attempt ledger charged total differs")
            seen = set()
            for dataset in datasets:
                name = dataset["benchmark_id"]
                if name in seen or name not in floor:
                    raise ValueError("duplicate or foreign dataset provenance")
                seen.add(name)
                runtime_payload,runtime_manifest=read_runtime_manifest(name)
                runtime_hash=hashlib.sha256(runtime_payload).hexdigest()
                definition = get_benchmark(name)
                if dataset["definition_sha256"] != canonical_sha256(definition.model_dump(mode="json"), schema_version="evonn.catalog.benchmark/v1", digest_field=None):
                    raise ValueError("dataset definition provenance differs")
                if dataset["runtime_manifest_sha256"] != runtime_hash or dataset["split_policy"] != runtime_manifest["split_policy"]:
                    raise ValueError("runtime/split policy provenance differs")
                if dataset["seed"] != manifest.seed:
                    raise ValueError("dataset seed differs from run")
                if len(dataset["cache_artifacts"]) != 4 or {item["path"] for item in dataset["cache_artifacts"]} != {
                    "x_train.npy", "y_train.npy", "x_validation.npy", "y_validation.npy"}:
                    raise ValueError("four distinct split cache artifacts required")
                binding = runtime_manifest["benchmarks"][name]
                if dataset["definition_sha256"] != binding["definition_sha256"]:
                    raise ValueError("dataset definition differs from pinned runtime")
                if not binding["loader"].startswith("make_") and dataset["raw_sha256"] != binding["reference_raw_sha256"]:
                    raise ValueError("raw dataset reference differs")
                checked_dataset = dataset
                if cache_roots is not None:
                    original = dataset["cache_directory"]
                    if original not in cache_roots:
                        raise ValueError("transport is missing an exact dataset-cache root")
                    checked_dataset = {**dataset, "cache_directory": str(cache_roots[original])}
                digest = verify_split_cache(checked_dataset, feature_count=math.prod(definition.input_shape), regression=definition.task_kind.value == "regression")
                if manifest.seed == 42 and digest != binding["reference_split_sha256"]:
                    raise ValueError("reference split differs from reviewed runtime")
                candidate_floor[name]["cache"] = True
            if seen != set(pack.benchmarks):
                raise ValueError("every admitted run requires complete checked dataset provenance")
            if manifest.status.value == "completed" and not manifest.accounting.partial_run and not bundle.results.coverage.failed:
                runs.append({"budget": manifest.accounting.evaluation_count, "seed": manifest.seed,
                             "run_id": manifest.run_id, "dirty": config["code_dirty"],
                             "envelope_sha256": canonical_sha256(manifest.budget.model_dump(mode="json"), schema_version="evonn-compare-envelope-v1", digest_field=None),
                             "protocol_sha256": canonical_sha256({"pools": config["pools"], "dataset_versions": config["dataset_versions"],
                                 "git_commit": manifest.git_commit, "runtime": manifest.runtime.model_dump(mode="json"),
                                 "enhanced": config["enhanced"], "fit_timeout_seconds": config["fit_timeout_seconds"]},
                                 schema_version="evonn-admission-protocol-v1", digest_field=None)})
            floor = candidate_floor
        except (ValueError, OSError, KeyError, TypeError) as error:
            blockers.append(f"{manifest.run_id}: {error}")
    labels = []
    for definition in definitions:
        state = floor[definition.id]
        missing = sorted(set(definition.required_contenders) - state["successful"])
        if missing:
            blockers.append(f"{definition.id}: missing required floor results: {', '.join(missing)}")
        if not state["cache"]:
            blockers.append(f"{definition.id}: checked runtime/cache evidence missing")
        if not definition.required_contenders or not definition.runtime_class:
            blockers.append(f"{definition.id}: floor/runtime metadata missing")
        if state["weak"]:
            label = "weak_floor"
            blockers.append(f"{definition.id}: weakened floor: {', '.join(state['weak'])}")
        elif missing:
            label = "weak_floor"
        elif state["enhanced"]:
            # Enhanced fit alone is not reproducibility proof of a strong floor.
            label = "strong_floor" if any(len(seeds) >= 2 for seeds in state["enhanced_seeds"].values()) else "acceptable_floor"
        else:
            label = "missing_enhanced_pressure"
            warnings.append(f"{definition.id}: optional enhanced pressure absent")
        labels.append({"benchmark": definition.id, "adequacy": label, "required": list(definition.required_contenders),
                       "successful": sorted(state["successful"]), "enhanced": sorted(state["enhanced"]),
                       "missing": missing, "cache_verified": state["cache"], "runtime_class": definition.runtime_class,
                       "ceiling": definition.ceiling.model_dump(mode="json")})
    budgets = sorted({run["budget"] for run in runs})
    low_groups = {}
    for run in runs:
        if budgets and run["budget"] == budgets[0]:
            key = (run["protocol_sha256"], run["envelope_sha256"])
            if key not in low_groups:
                low_groups[key] = set()
            low_groups[key].add(run["seed"])
    admitted_ids = set()
    for key, seeds in low_groups.items():
        if len(seeds) >= 2 and any(run["budget"] > budgets[0] and run["protocol_sha256"] == key[0] for run in runs):
            admitted_ids.update(run["run_id"] for run in runs if run["protocol_sha256"] == key[0]
                                and (run["budget"] > budgets[0] or run["envelope_sha256"] == key[1]))
    repeated = bool(admitted_ids)
    if decision_grade:
        if not repeated:
            blockers.append("requires two independent low-budget seeds and one clean mid-budget run")
        if any(run["dirty"] for run in runs):
            blockers.append("uncommitted runtime code cannot support decision-grade admission")
        if not dashboard_present:
            blockers.append("required dashboard evidence is missing")
        if not output_levels or any((output_levels[run["run_id"]] if run["run_id"] in output_levels else "L0") < "L3" for run in runs):
            blockers.append("measurable L3 output required for all admission runs")
    return {"schema_version": "1.0.0", "pack": pack_name,
            "scope": "decision_grade" if decision_grade else "phase1_contract",
            "status": "blocked" if blockers else "passed", "blocker_count": len(set(blockers)),
            "blockers": sorted(set(blockers)), "warnings": sorted(set(warnings)), "benchmarks": labels,
            "budgets": budgets, "repeatability": "low_and_mid_repeated" if repeated else "incomplete",
            "clean_runs": runs, "admitted_run_ids": sorted(admitted_ids), "extended_coverage_complete": False, "scientific_qualification": False,
            "note": "Runtime admission is separate from the immutable planned catalog snapshot; Tier A does not establish broad capability."}


def apply_admission(acceptance: dict, audit: dict, *, extended_complete: bool = False) -> dict:
    result = dict(acceptance)
    case = result["case"]
    admitted = {run["run_id"] for run in audit["clean_runs"]
                if run["budget"] == case["budget"] and run["seed"] == case["seed"] and run["run_id"] in audit["admitted_run_ids"]}
    bound = audit["pack"] == case["pack"] and bool(result["contender_run_ids"]) and set(result["contender_run_ids"]) <= admitted
    if (bound and result["operating_state"] == "contract-fair" and not result["engine_only"]
            and audit["scope"] == "decision_grade" and audit["status"] == "passed"):
        result["operating_state"] = "trusted-extended" if extended_complete and audit["extended_coverage_complete"] else "trusted-core"
        result["external_floor_claim"] = True
        result["repeatability_state"] = audit["repeatability"]
    return result
