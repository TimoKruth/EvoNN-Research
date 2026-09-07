"""Two actual isolated fits through the memory-bounded spawn evaluator."""

from dataclasses import asdict
from pathlib import Path
import os
import numpy as np

from evonn_shared.artifact_io import create_artifact_directory
from evonn_shared.catalog import get_benchmark
from evonn_shared.datasets import load_dataset
from evonn_shared.runtime_io import source_identity
from topograph.genome import Innovations, seed_genome
from topograph.search import Search
from topograph.training import TrainConfig
from topograph.parallel import Evaluator


def test_two_spawn_workers_train_and_return_in_submission_order(tmp_path):
    definition = get_benchmark("iris_classification")
    dataset = load_dataset(definition.id, seed=42, cache_root=tmp_path / "cache")
    genome = seed_genome(Innovations())
    backend = os.environ.get("EVONN_TEST_BACKEND", "numpy_fallback")
    model = Search([definition], seed=42).compile(genome, definition, backend=backend, device="cpu", seed=42)
    request = {
        "benchmark": definition.id,
        "shared_root": str(Path(__file__).resolve().parents[2] / "shared-benchmarks"),
        "genome": genome.model_dump(mode="json"),
        "backend": backend,
        "device": "cpu",
        "model_seed": 42,
        "data": dataset.provenance,
        "weights": {k: v.tolist() for k, v in model.weights.items()},
        "buffers": {k: [np.asarray(a).tolist() for a in v] for k, v in model.buffers.items()},
        "training": asdict(TrainConfig(epochs=1, timeout=15)),
        "source_sha256": source_identity(),
    }
    evaluator = Evaluator(
        data_bytes=1024 * 1024, snapshot_bytes=1024 * 1024, cpu_budget=2, memory_bytes=4 * 1024**3, job_count=2
    )
    results = evaluator.evaluate_many(
        [
            {
                "request": {**request, "model_seed": seed},
                "directory": create_artifact_directory(tmp_path / str(seed)),
                "timeout": 25,
            }
            for seed in (42, 43)
        ]
    )
    assert evaluator.worker_count == 2
    assert all(r["status"] == "ok" and r["weights_changed"] and r["charged"] == 1 for r in results)
    import json

    assert results == [json.loads((tmp_path / str(seed) / "result.json").read_text()) for seed in (42, 43)]
