"""Read-only output-quality levels L0–L3, with explicit measurement gaps."""
from pathlib import Path

from evonn_shared.export_reader import read_document, read_export, validate_canonical_results
from evonn_shared.exports import Manifest, Results


def classify(root: Path, *, propagated: bool = False) -> dict:
    result = {"path": str(root), "run_id": None, "level": "L0", "gaps": []}
    try:
        manifest = Manifest.model_validate_json(read_document(root, "manifest.json"))
        records = Results.model_validate_json(read_document(root, "results.json"))
        for name in ("system", "run_id", "pack_id", "seed", "budget", "accounting", "runtime", "seeding"):
            if manifest.model_dump(mode="json")[name] != records.model_dump(mode="json")[name]:
                raise ValueError(f"manifest/results {name} mismatch")
        result.update(run_id=manifest.run_id, level="L1")
        validate_canonical_results(manifest, records)
        bundle = read_export(root)
        result["level"] = "L2"
    except (ValueError, OSError) as error:
        result["gaps"].append(str(error))
        return result
    if manifest.timing.elapsed_seconds <= 0:
        result["gaps"].append("positive elapsed time required for throughput")
    if not propagated:
        result["gaps"].append("runtime, cache, failure and skip diagnostics not yet verified in trend rows")
    if not result["gaps"]:
        result["level"] = "L3"
    result["gaps"].extend(sorted({f"{field} unavailable for some successful outcomes" for field in
        ("parameter_count", "train_seconds", "model_bytes", "peak_memory_bytes")
        if any(record.status.value == "ok" and record.model_dump(mode="json")[field]["value"] is None for record in bundle.results.records)}))
    result["next_level"] = "L4 requires multi-seed effect sizes and decision support (Phase 3)" if result["level"] == "L3" else "L3 measurement propagation"
    return result
