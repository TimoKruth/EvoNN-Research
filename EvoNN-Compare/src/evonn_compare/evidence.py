"""Direction-aware winners, cohort-separated statistics and portable trend rows."""
from collections import defaultdict
import math
import json
import statistics

from evonn_shared.catalog import get_benchmark
from evonn_shared.canonical import canonical_sha256


def trend_rows(bundle, case_id: str, acceptance: dict) -> list[dict]:
    manifest = bundle.manifest
    elapsed = manifest.timing.elapsed_seconds
    successes = bundle.results.coverage.ok
    rows = []
    for result in bundle.results.records:
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
            "evaluation_semantics": manifest.accounting.evaluation_semantics,
            "fairness_flags": [flag.model_dump(mode="json") for flag in bundle.summary.fairness_flags],
            "cached_evaluations": manifest.accounting.cached_evaluations,
            "failed_evaluations": manifest.accounting.failed_evaluations,
            "invalid_evaluations": manifest.accounting.invalid_evaluations,
            "actual_evaluations": manifest.accounting.actual_evaluations,
            "train_seconds": result.train_seconds.value, "model_bytes": result.model_bytes.value,
            "parameter_count": result.parameter_count.value, "peak_memory_bytes": result.peak_memory_bytes.value,
            "seeding": manifest.seeding.model_dump(mode="json"), "started_at": manifest.timing.started_at.isoformat()})
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
    for (cohort, case, benchmark), values in sorted(groups.items()):
        ok = [row for row in values if row["status"] == "ok"]
        chosen = []
        if ok:
            value = (max if ok[0]["direction"] == "max" else min)(row["value"] for row in ok)
            chosen = [row for row in ok if row["value"] == value]
        else:
            value = None
        tied = len(chosen) > 1
        ceiling = tied and chosen[0]["ceiling"] is not None and value == chosen[0]["ceiling"]
        output.append({"cohort": cohort, "case_id": case, "benchmark": benchmark, "value": value,
            "winners": [row["engine"] for row in chosen], "tie": tied, "ceiling_tie": ceiling,
            "comparison_available": len(ok) >= 2,
            "case_win": len(ok) >= 2 and not tied and all(row["accounting_state"] == "complete" and row["operating_state"] not in ("exploratory", "reference") for row in ok),
            "superiority_evidence": False, "pack": values[0]["pack"], "budget": values[0]["budget"],
            "failures_or_missing": [{"engine": row["engine"], "status": row["status"], "reason": row["reason"]}
                                    for row in values if row["status"] != "ok"]})
    return output


def aggregates(rows: list[dict]) -> dict:
    best = best_rows(rows)
    groups = defaultdict(list)
    for row in best:
        groups[(row["cohort"], row["pack"], row["budget"], row["benchmark"], row["engine"], row["backend"], row["device"], row["precision"],
                row["operating_state"], row["accounting_state"], json.dumps(row["seeding"], sort_keys=True), row["envelope_sha256"])].append(row)
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
        spread.append({**dict(zip(("cohort", "pack", "budget", "benchmark", "engine", "backend", "device", "precision", "operating_state", "accounting_state", "seeding_regime", "envelope_sha256"), key, strict=True)),
            "task_kind": values[0]["task_kind"], "family": values[0]["family"], "seeds": sorted(by_seed), "n": len(samples), "mean": mean,
            "min": min(samples) if samples else None, "max": max(samples) if samples else None,
            "ci95": [mean-error, mean+error] if error is not None else None,
            "ci_method": "descriptive normal approximation across seed means; no significance claim",
            "gap": None if error is not None else "at least three independent seeds required for interval",
            "failed_or_missing_runs": sum(row["status"] != "ok" for row in values)})
    pairs = []
    match = defaultdict(dict)
    for row in best:
        if row["status"] == "ok" and row["accounting_state"] == "complete" and row["operating_state"] not in ("exploratory", "reference"):
            match[(row["cohort"], row["case_id"], row["benchmark"], row["seed"])][row["engine"]] = row
    for key, engines in sorted(match.items()):
        for left in sorted(engines):
            for right in sorted(engines):
                if left >= right:
                    continue
                a, b = engines[left], engines[right]
                if a["seeding"] != b["seeding"]:
                    continue
                pairs.append({"cohort": key[0], "case_id": key[1], "benchmark": key[2], "seed": key[3],
                    "left": left, "right": right, "raw_delta": a["value"]-b["value"],
                    "advantage_left": (a["value"]-b["value"]) * (1 if a["direction"] == "max" else -1)})
    return {"spread": spread, "pairwise_seed_deltas": pairs, "per_seed": best}
