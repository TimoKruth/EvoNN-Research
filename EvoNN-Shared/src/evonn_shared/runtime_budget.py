"""Comparable execution envelope; model-specific work remains in attempt telemetry."""


MAX_ENGINE_EVALUATIONS = 256


def execution_budget(pack, total, timeout, device):
    return {
        "evaluation": {"total": total, "stages": [{"name": "full", "evaluations": total}]},
        "wall_clock": {"target_seconds": float(timeout)},
        "training": {
            "unit": "bounded fit/eval passes; model-specific iteration limits in config and attempt telemetry",
            "per_candidate": 1.0,
            "total_cap": float(total),
        },
        "hardware": {
            "device_class": device,
            "cpu_count": 1,
            "accelerator_type": None,
            "memory_ceiling_bytes": None,
            "worker_count": 1,
        },
        "model_artifact": {
            "parameter_cap": None,
            "model_bytes_cap": 256 * 1024 * 1024,
            "memory_target_bytes": None,
            "latency_target_seconds": None,
        },
        "benchmark_surface": {
            "pack_id": pack.pack_name,
            "benchmark_count": len(pack.benchmarks),
            "ladder_tier": pack.ladder_tier.value,
            "reductions": [],
            "subsets": [],
        },
        "fidelity": {
            "regime": "full benchmark splits; bounded system-specific training",
            "stages": [{"name": "full", "description": "historical full train/validation split"}],
            "promotion_rule": "none; explicit training allocation and inheritance in attempt ledger",
        },
    }
