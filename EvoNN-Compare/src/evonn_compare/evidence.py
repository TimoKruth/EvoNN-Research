"""Direction-aware winners, cohort-separated statistics and portable trend rows."""
from collections import defaultdict
import math
import json
import statistics

from evonn_shared.active_catalog import get_benchmark
from evonn_shared.canonical import canonical_sha256
from .audit import artifact_json


def protocol_fingerprint(bundle):
    """Bind repeated runs to runtime identity and seed-independent engine policy."""
    runtime = bundle.manifest.runtime.model_dump(mode="json")
    policy = {}
    if bundle.manifest.system.value in {"prism", "topograph", "stratograph", "primordia"}:
        config = artifact_json(bundle, bundle.manifest.config_snapshot.path)
        keys = ("source_sha256", "epochs", "population_size", "fit_timeout", "benchmark_pooling", "novelty_weight", "variant", "evaluator_fidelity")
        policy = {key: config[key] for key in keys if key in config}
    return canonical_sha256({"system": bundle.manifest.system.value, "runtime": runtime, "policy": policy},
                            schema_version="evonn-comparison-protocol/v1", digest_field=None)


def comparison_fingerprint(bundle):
    """Bind cross-engine comparisons to shared training policy and execution host."""
    config = artifact_json(bundle, bundle.manifest.config_snapshot.path)
    runtime = bundle.manifest.runtime.model_dump(mode="json")
    return canonical_sha256({
        "runtime": {key: runtime[key] for key in ("backend", "backend_version", "device_class", "host_fingerprint")},
        "policy": {key: config[key] for key in ("source_sha256", "epochs", "population_size", "fit_timeout")},
    }, schema_version="evonn-cross-engine-protocol/v1", digest_field=None)


def compatible_rows(a, b):
    if a["seeding"] != b["seeding"]:
        return False
    if "contenders" in (a["engine"], b["engine"]):
        return True
    return bool(a.get("comparison_fingerprint")) and a.get("comparison_fingerprint") == b.get("comparison_fingerprint")


def comparison_groups(rows):
    """Keep baselines from bridging incompatible engine partitions."""
    engines = [row for row in rows if row["engine"] != "contenders"]
    baselines = [row for row in rows if row["engine"] == "contenders"]
    groups = defaultdict(list)
    for row in engines:
        groups[row.get("comparison_fingerprint") or ("unavailable:" + row["run_id"])].append(row)
    if len(groups) == 1:
        next(iter(groups.values())).extend(baselines)
    elif baselines:
        groups["baseline"] = baselines
    return list(groups.values())


def trend_rows(bundle, case_id: str, acceptance: dict) -> list[dict]:
    manifest = bundle.manifest
    elapsed = manifest.timing.elapsed_seconds
    successes = bundle.results.coverage.ok
    rows = []
    attempts = {}
    if manifest.system.value in {"contenders", "prism", "topograph", "stratograph", "primordia"}:
        try:
            ledger = artifact_json(bundle, "attempts.json")
            attempts = {(item["benchmark_id"], item["outcome_id"]): item for item in ledger["attempts"] if "outcome_id" in item}
        except (OSError, ValueError, KeyError, TypeError):
            pass  # Missing diagnostics remain unavailable; admission is checked separately.
    for result in bundle.results.records:
        key = (result.benchmark_id, result.outcome_id)
        attempt = attempts[key] if key in attempts else {}
        definition = get_benchmark(result.benchmark_id)
        rows.append({"case_id": case_id, "run_id": manifest.run_id, "engine": manifest.system.value,
            "benchmark": result.benchmark_id, "task_kind": result.task_kind.value,
            "family": "synthetic" if "generated" in definition.tags else definition.input_modality.value, "pack": manifest.pack_id,
            "budget": manifest.accounting.evaluation_count, "seed": manifest.seed,
            "outcome_id": result.outcome_id, "status": result.status.value, "reason": result.reason,
            "direction": result.metric.direction.value, "metric": result.metric.name, "value": result.metric.value,
            "ceiling": definition.ceiling.value, "evaluation_count": result.evaluation_count,
            "cohort": acceptance["cohort"], "engine_only": acceptance["engine_only"],
            "operating_state": acceptance["operating_state"], "accounting_state": acceptance["accounting_state"],
            "repeatability_state": acceptance["repeatability_state"], "backend": manifest.runtime.backend.value,
            "device": manifest.runtime.device_class, "precision": manifest.runtime.precision_mode, "host_fingerprint": manifest.runtime.host_fingerprint,
            "wall_clock": elapsed, "evals_per_second": manifest.accounting.actual_evaluations / elapsed if elapsed else None,
            "seconds_per_success": elapsed / successes if successes else None,
            "score_per_second": result.metric.value / elapsed if result.metric.value is not None and elapsed else None,
            "score_per_second_note": "raw metric/time; lower-is-better scores are not utility rates",
            "envelope_sha256": canonical_sha256(manifest.budget.model_dump(mode="json"), schema_version="evonn-compare-envelope-v1", digest_field=None),
            "model_family": attempt["family"] if "family" in attempt else None,
            "model_backend": attempt["backend"] if "backend" in attempt else None,
            "evaluation_semantics": manifest.accounting.evaluation_semantics,
            "fairness_flags": [flag.model_dump(mode="json") for flag in bundle.summary.fairness_flags],
            "cached_evaluations": manifest.accounting.cached_evaluations,
            "failed_evaluations": manifest.accounting.failed_evaluations,
            "invalid_evaluations": manifest.accounting.invalid_evaluations,
            "actual_evaluations": manifest.accounting.actual_evaluations,
            "train_seconds": result.train_seconds.value, "model_bytes": result.model_bytes.value,
            "parameter_count": result.parameter_count.value, "peak_memory_bytes": result.peak_memory_bytes.value,
            "seeding": manifest.seeding.model_dump(mode="json"), "started_at": manifest.timing.started_at.isoformat()})
    if manifest.system.value in {"prism", "topograph", "stratograph", "primordia"}:
        protocol, comparison, active = None, None, None
        try:
            protocol = protocol_fingerprint(bundle)
            comparison = comparison_fingerprint(bundle)
            if any(ref.path == "state.json" for ref in bundle.summary.artifact_digests):
                active = artifact_json(bundle, "state.json")["elapsed"]
        except (ValueError, OSError, KeyError, TypeError):
            protocol, comparison, active = None, None, None  # Invalid evidence remains diagnostic and blocked by admission.
        for row in rows:
            key = (row["benchmark"], row["outcome_id"])
            attempt = attempts[key] if key in attempts else {}
            row["protocol_fingerprint"] = protocol
            row["comparison_fingerprint"] = comparison
            row["backend_version"] = manifest.runtime.backend_version
            row["active_run_seconds"] = active
            row["wall_clock_note"] = "timestamp span includes resume pauses; active_run_seconds is the consumed execution budget"
            row["inheritance"] = attempt["inheritance"] if "inheritance" in attempt else None
            row["latency_seconds"] = attempt["latency_seconds"] if "latency_seconds" in attempt else None
            row["packed_bytes_estimate"] = attempt["packed_bytes_estimate"] if "packed_bytes_estimate" in attempt else None
            row["allocated_epochs"] = attempt["allocated_epochs"] if "allocated_epochs" in attempt else None
            row["model_family"] = attempt["genome"].get("family", attempt["genome"].get("profile", "primitive" if manifest.system.value=="primordia" else "dag")) if "genome" in attempt else None
            row["evidence_class"] = "portability_only" if manifest.runtime.backend.value == "numpy_fallback" else "native_runtime"
    return rows


def best_rows(rows: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[(row["case_id"], row["run_id"], row["benchmark"])].append(row)
    result = []
    for key in sorted(groups):
        values = groups[key]
        successful = [row for row in values if row["status"] == "ok"]
        if successful:
            result.append(sorted(successful, key=lambda row: (
                -row["value"] if row["direction"] == "max" else row["value"], row["outcome_id"]))[0])
        else:
            result.append(sorted(values, key=lambda row: row["outcome_id"])[0])
    return result


def winners(rows: list[dict], *, projects_only: bool = False) -> list[dict]:
    groups = defaultdict(list)
    for row in best_rows(rows):
        if not projects_only or row["engine"] != "contenders":
            groups[(row["cohort"], row["case_id"], row["benchmark"])].append(row)
    output = []
    partitions = [(key, part) for key, values in sorted(groups.items()) for part in comparison_groups(values)]
    for (cohort, case, benchmark), values in partitions:
        ok = [row for row in values if row["status"] == "ok" and row["accounting_state"] == "complete" and row["operating_state"] not in ("exploratory", "reference")]
        chosen = []
        if ok:
            value = (max if ok[0]["direction"] == "max" else min)(row["value"] for row in ok)
            chosen = sorted([row for row in ok if row["value"] == value], key=lambda row: row["engine"])
        else:
            value = None
        tied = len(chosen) > 1
        ceiling = tied and chosen[0]["ceiling"] is not None and value == chosen[0]["ceiling"]
        output.append({"cohort": cohort, "case_id": case, "benchmark": benchmark, "value": value,
            "winners": [row["engine"] for row in chosen], "tie": tied, "ceiling_tie": ceiling,
            "comparison_available": len(ok) >= 2,
            "case_win": len(ok) >= 2 and not tied and all(row["accounting_state"] == "complete" and row["operating_state"] not in ("exploratory", "reference") for row in ok),
            "backend_classes": sorted({row["backend"] for row in values}), "portability_only": any(row["backend"] == "numpy_fallback" for row in values),
            "superiority_evidence": False, "pack": values[0]["pack"], "budget": values[0]["budget"],
            "failures_or_missing": [{"engine": row["engine"], "status": row["status"], "reason": row["reason"]}
                                    for row in values if row["status"] != "ok"]})
    return output


def aggregates(rows: list[dict]) -> dict:
    best = best_rows(rows)
    groups = defaultdict(list)
    for row in best:
        groups[(row["cohort"], row["pack"], row["budget"], row["benchmark"], row["engine"], row["backend"], row["device"], row["precision"],
                row["operating_state"], row["accounting_state"], json.dumps(row["seeding"], sort_keys=True), row["envelope_sha256"], row["host_fingerprint"], row.get("backend_version", "legacy"), (row.get("protocol_fingerprint") or "unavailable"))].append(row)
    spread = []
    for key, values in sorted(groups.items()):
        by_seed = defaultdict(list)
        for row in values:
            if row["status"] == "ok" and row["accounting_state"] == "complete" and row["operating_state"] not in ("exploratory", "reference"):
                by_seed[row["seed"]].append(row["value"])
        samples = [statistics.mean(by_seed[seed]) for seed in sorted(by_seed)]
        mean = statistics.mean(samples) if samples else None
        # Explicit descriptive normal approximation; no inferential confidence at n<3.
        error = 1.96 * statistics.stdev(samples) / math.sqrt(len(samples)) if len(samples) >= 3 else None
        spread.append({**dict(zip(("cohort", "pack", "budget", "benchmark", "engine", "backend", "device", "precision", "operating_state", "accounting_state", "seeding_regime", "envelope_sha256", "host_fingerprint", "backend_version", "protocol_fingerprint"), key, strict=True)),
            "task_kind": values[0]["task_kind"], "family": values[0]["family"], "seeds": sorted(by_seed), "n": len(samples), "mean": mean,
            "min": min(samples) if samples else None, "max": max(samples) if samples else None,
            "ci95": [mean-error, mean+error] if error is not None else None,
            "ci_method": "descriptive normal approximation across seed means; no significance claim",
            "gap": None if error is not None else "at least three independent seeds required for interval",
            "failed_or_missing_runs": sum(row["status"] != "ok" for row in values)})
    pairs = []
    match = defaultdict(list)
    for row in best:
        if row["status"] == "ok" and row["accounting_state"] == "complete" and row["operating_state"] not in ("exploratory", "reference"):
            match[(row["cohort"], row["case_id"], row["benchmark"], row["seed"])].append(row)
    partitions = [(key, part) for key, values in sorted(match.items()) for part in comparison_groups(values)]
    for key, values in partitions:
        engines = {row["engine"]: row for row in values}
        if len(engines) != len(values):
            continue
        for left in sorted(engines):
            for right in sorted(engines):
                if left >= right:
                    continue
                a, b = engines[left], engines[right]
                if not compatible_rows(a, b):
                    continue
                pairs.append({"cohort": key[0], "case_id": key[1], "benchmark": key[2], "seed": key[3],
                    "left": left, "right": right, "left_backend": a["backend"], "right_backend": b["backend"], "portability_only": "numpy_fallback" in (a["backend"], b["backend"]), "raw_delta": a["value"]-b["value"],
                    "advantage_left": (a["value"]-b["value"]) * (1 if a["direction"] == "max" else -1)})
    return {"spread": spread, "pairwise_seed_deltas": pairs, "per_seed": best}
