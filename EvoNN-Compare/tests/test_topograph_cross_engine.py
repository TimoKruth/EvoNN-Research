from contextlib import nullcontext
from copy import deepcopy
import json

import pytest

from evonn_shared.active_catalog import get_benchmark, load_parity_pack
from evonn_compare import topograph_cross_engine as t


def rows():
    result = []
    for arm in t.SYSTEMS:
        for seed in t.SEEDS["comparison"]:
            for pack in t.PACKS:
                metrics = {}
                for name in load_parity_pack(pack).benchmarks:
                    direction = get_benchmark(name).primary_metric.direction.value
                    metrics[name] = (1.1 if direction == "max" else .8) if arm == "topograph" else 1.
                if "delayed_copy_lm" in metrics and arm == "topograph":
                    metrics["delayed_copy_lm"] = 2.
                result.append(dict(arm=arm, seed=seed, pack=pack, budget=128, metrics=metrics, failed_attempts=0))
    return result


def test_all_systems_every_cell_and_matched_envelopes():
    matrix = t.matrix()
    assert len(matrix) == 34
    assert sum(len(r["spec"]["systems"]) for r in matrix) == 170
    assert sum(r["spec"]["budgets"][0] * 5 for r in matrix) == 20640
    assert set(t.SEEDS["qualification"]).isdisjoint(t.SEEDS["comparison"])
    for row in matrix:
        spec = t.c.CampaignSpec.model_validate(row["spec"])
        assert set(spec.systems) == set(t.SYSTEMS)
        assert spec.comparison_scope == "all_engines"
        assert spec.topograph_research == t.TopographResearchPolicy(adapters="mixer")
        assert spec.timeout == 1740 and spec.fit_timeout == 120
        for case, engine in t.c.slots(spec):
            command = t.command_for(spec, case, engine, "/out", "/cache")
            assert command[command.index("--budget") + 1] == str(case.budget)
            assert command[command.index("--timeout") + 1] == "1740.0"
            if engine == "topograph":
                assert json.loads(command[command.index("--research-options") + 1])["adapters"] == "mixer"


def test_aggregate_win_cannot_hide_memory_regression():
    contrasts = t.inference(rows())
    assert len(contrasts) == 8
    for row in contrasts:
        assert row["holm_pvalue"] >= row["pvalue"]
        assert row["inference"]["n"] == 16
        assert row["decision"] == ("confirmed_gain" if row["endpoint"] == "aggregate" else "confirmed_regression")


@pytest.mark.parametrize("damage", ["missing_engine", "duplicate", "missing_memory", "failure", "wrong_budget"])
def test_incomplete_evidence_blocks_inference(damage):
    data = rows()
    if damage == "missing_engine":
        data = [r for r in data if r["arm"] != "stratograph"]
    elif damage == "duplicate":
        data.append(deepcopy(data[0]))
    elif damage == "missing_memory":
        next(r for r in data if r["pack"] == t.PACKS[1])["metrics"].pop("delayed_copy_lm")
    elif damage == "failure":
        data[0]["failed_attempts"] = 1
    else:
        data[0]["budget"] = 64
    with pytest.raises(ValueError):
        t.inference(data)


def setup_run(tmp_path, monkeypatch, completed):
    matrix = t.matrix()
    plan = dict(rows=matrix)
    monkeypatch.setattr(t.c, "lease", lambda *args: nullcontext(1))
    monkeypatch.setattr(t, "preflight", lambda *args, **kw: plan)
    monkeypatch.setattr(t, "saved_receipt", lambda path, system:
                        {} if (str(path.relative_to(tmp_path)), system) in completed else None)
    return matrix


def test_qualification_failure_blocks_every_main_dispatch(tmp_path, monkeypatch):
    complete = {(r["campaign"], a) for r in t.matrix() if r["stage"] == "qualification" for a in t.SYSTEMS}
    setup_run(tmp_path, monkeypatch, complete)
    monkeypatch.setattr(t, "dispatch", lambda *args: pytest.fail("main dispatch before qualification"))
    def failed_gate(*args):
        raise ValueError("qualification invalid")
    monkeypatch.setattr(t, "collect", failed_gate)
    with pytest.raises(ValueError, match="qualification invalid"):
        t.run(tmp_path)
    assert json.loads((tmp_path / "status.json").read_text())["status"] == "failed"


def test_pause_does_not_dispatch_or_discard_completions(tmp_path, monkeypatch):
    first = t.matrix()[0]
    setup_run(tmp_path, monkeypatch, {(first["campaign"], first["spec"]["systems"][0])})
    monkeypatch.setattr(t, "dispatch", lambda *args: pytest.fail("dispatch while paused"))
    (tmp_path / "PAUSE").touch()
    result = t.run(tmp_path)
    assert result["status"] == "paused" and result["completed"] == 1


def test_failure_stops_without_skipping_engine(tmp_path, monkeypatch):
    setup_run(tmp_path, monkeypatch, set())
    calls = []
    def fail(*args):
        calls.append(args)
        raise ValueError("retained failed fit")
    monkeypatch.setattr(t, "dispatch", fail)
    with pytest.raises(ValueError, match="retained failed fit"):
        t.run(tmp_path)
    assert len(calls) == 1
    assert json.loads((tmp_path / "status.json").read_text())["completed"] == 0


def test_failed_checkpoint_cannot_be_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(t, "load_runtime_checkpoint", lambda *args:
                        (None, json.dumps(dict(completed=2, attempts=[dict(status="failed")]))))
    with pytest.raises(ValueError, match="no automatic retry"):
        t.checkpoint_progress(tmp_path)
