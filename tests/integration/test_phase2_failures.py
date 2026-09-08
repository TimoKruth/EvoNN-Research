"""Coordinator failure accounting and bounded transport, without optimizer work."""

from concurrent.futures.process import BrokenProcessPool
import json
from pathlib import Path

import numpy as np
import pytest
from prism import run as prism_run
from prism.search import Search as PrismSearch
from prism.config import RunConfig as PrismConfig
from topograph import run as topograph_run
from topograph.search import Search as TopographSearch
from topograph.config import RunConfig as TopographConfig
from stratograph import run as stratograph_run
from stratograph.search import Search as StratographSearch
from evonn_primordia import run as primordia_run
from evonn_primordia.search import Search as PrimordiaSearch
from evonn_shared.runtime_journal import load_runtime_checkpoint
from evonn_shared.datasets import load_dataset
from evonn_shared.runtime_io import encode_snapshot, terminal_worker_failure, encode
from evonn_shared.weight_cache import WeightCache


@pytest.fixture
def prepared(tmp_path):
    from evonn_shared.catalog import load_parity_pack

    return {
        name: load_dataset(name, seed=42, cache_root=tmp_path / "cache").provenance
        for name in load_parity_pack("tier1_core_smoke").benchmarks
    }


@pytest.mark.parametrize(
    "runtime,search,failure",
    [
        (runtime, search, failure)
        for runtime, search in [(prism_run, PrismSearch), (topograph_run, TopographSearch), (stratograph_run, StratographSearch), (primordia_run, PrimordiaSearch)]
        for failure in (
            ["oversized", "transport", "timeout", "broken_pool"]
            if runtime is topograph_run
            else ["oversized", "transport", "timeout"]
        )
    ],
)
def test_failed_candidate_advances_once_and_preserves_charge(tmp_path, monkeypatch, prepared, runtime, search, failure):
    def dispatch(directory):
        (directory / "started").write_bytes(b"fit\n")
        if failure == "broken_pool":
            raise BrokenProcessPool("supervisor stopped")
        if failure == "timeout":
            raise TimeoutError("supervisor deadline")
        raise TypeError("post-start transport fault")

    def process(system, verb, request, directory, timeout, **options):
        if verb == "_prepare":
            return {"status": "ok", "provenance": prepared[request["benchmark"]]}
        dispatch(directory)

    monkeypatch.setattr(runtime, "_process", process)
    if runtime is topograph_run:
        monkeypatch.setattr(runtime.Evaluator, "evaluate_many", lambda self, jobs: dispatch(jobs[0]["directory"]))
    if failure == "oversized":

        class Oversized:
            parameter_count = 2_000_001

        monkeypatch.setattr(search, "compile", lambda *args, **kwargs: Oversized())
    root = runtime.run_engine(
        search, pack_name="tier1_core_smoke", budget=8, output_parent=tmp_path / "runs", stop_after=1
    )
    state = json.loads(load_runtime_checkpoint(root / "checkpoints")[1])
    assert Path(state["config"]["cache"]).is_absolute()  # API None default resolves normally.
    first = state["attempts"][0]
    expected = (0, 1) if failure == "oversized" else (1, 0)
    assert (first["charged"], first["invalid"]) == expected
    runtime.run_engine(search, pack_name="tier1_core_smoke", budget=8, resume=root, stop_after=2)
    resumed = json.loads(load_runtime_checkpoint(root / "checkpoints")[1])
    assert resumed["completed"] == 2 and resumed["attempts"][0] == first
    assert [(a["charged"], a["invalid"]) for a in resumed["attempts"]] == [expected, expected]
    assert resumed["tip"] != state["tip"]


@pytest.mark.parametrize(
    "config,runtime,search", [(PrismConfig, prism_run, PrismSearch), (TopographConfig, topograph_run, TopographSearch)]
)
def test_engine_budget_cap_rejects_before_workspace_creation(tmp_path, config, runtime, search):
    with pytest.raises(ValueError):
        config(budget=264)
    with pytest.raises(ValueError, match="256"):
        runtime.run_engine(search, budget=264, output_parent=tmp_path / "runs")
    assert not (tmp_path / "runs").exists()


def test_snapshot_guard_and_weight_cache_restoration(monkeypatch):
    from evonn_shared import runtime_io

    assert encode_snapshot({"completed": 1}) == encode({"completed": 1})
    monkeypatch.setattr(runtime_io, "encode", lambda value: b"x" * (128 * 1024**2 + 1))
    with pytest.raises(ValueError, match="128 MiB"):
        encode_snapshot({})
    cache = WeightCache(capacity=2)
    for identity in ("a", "b", "c", "c"):
        cache.put("ns", identity, "topology", "family", {"w": np.ones((3, 4))})
        assert cache.entry_bytes + max(0, len(cache.entries) - 1) + 2 == len(
            json.dumps(cache.state(), separators=(",", ":")).encode()
        )
    restored = WeightCache(capacity=1, state=cache.state())
    assert len(restored.entries) == 1 and next(iter(restored.entries)) == "ns:c"
    restored.put("ns", "large", "topology", "family", {"w": np.ones((9_000_000,))})
    assert len(json.dumps(restored.state(), separators=(",", ":")).encode()) <= 32 * 1024**2


def test_terminal_failure_fences_late_child(tmp_path, monkeypatch):
    from evonn_shared import engine_cli

    result = terminal_worker_failure(tmp_path, "supervisor died", 1)
    assert result["charged"] == 0 and result["invalid"] == 0
    (tmp_path / "request.json").write_text("{}")

    def forbidden(*args):
        pytest.fail("late worker must not fit after terminal failure")

    engine_cli.main(
        PrismSearch,
        None,
        None,
        forbidden,
        None,
        None,
        ["_worker", str(tmp_path / "request.json"), str(tmp_path / "result.json")],
    )
    assert not (tmp_path / "started").exists()


@pytest.mark.parametrize("module", ["prism.cli", "topograph.cli"])
def test_malformed_yaml_reports_without_traceback(tmp_path, module):
    import subprocess
    import sys

    config = tmp_path / "invalid.yaml"
    config.write_text("epochs: [unterminated")
    result = subprocess.run(
        [sys.executable, "-m", module, "run", "--config", str(config)], capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 1 and "invalid config YAML" in result.stderr and "Traceback" not in result.stderr


@pytest.mark.parametrize("previous", [None, [], {}, {"training": None}, {"training": {}}])
def test_pending_request_without_training_reports_drift(tmp_path, previous):
    from evonn_shared.runtime_io import _process

    (tmp_path / "request.json").write_text(json.dumps(previous))
    with pytest.raises(ValueError, match="pending worker request differs"):
        _process("prism", "_worker", {"training": {"timeout": 1}}, tmp_path, 1)
    assert not (tmp_path / "started").exists()


@pytest.mark.parametrize("published", [True, False])
def test_timeout_preserves_durable_result_and_recovery(tmp_path, monkeypatch, published):
    from evonn_shared import runtime_io
    import subprocess

    result = {"status": "ok", "charged": 1, "invalid": 0, "score": 0.7}

    def expired(*args, **kwargs):
        (tmp_path / "started").write_bytes(b"fit\n")
        if published:
            (tmp_path / "result.json").write_text(json.dumps(result))
        raise subprocess.TimeoutExpired("worker", 1)

    monkeypatch.setattr(runtime_io.subprocess, "run", expired)
    first = runtime_io._process("prism", "_worker", {}, tmp_path, 1)
    assert first["charged"] == 1 and first["invalid"] == 0
    assert first["status"] == ("ok" if published else "failed")
    monkeypatch.setattr(runtime_io.subprocess, "run", lambda *a, **k: pytest.fail("recovery must not dispatch again"))
    assert runtime_io._process("prism", "_worker", {}, tmp_path, 1) == first
