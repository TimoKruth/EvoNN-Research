from types import SimpleNamespace
import json

import pytest
from stratograph import commands
from stratograph.config import RunConfig


def prepared(monkeypatch):
    calls = []

    def run(search, **config):
        calls.append(config)
        return config["output_parent"] / config["variant"]

    monkeypatch.setattr(commands, "run_engine", run)
    monkeypatch.setattr(
        commands,
        "read_export",
        lambda path: SimpleNamespace(
            manifest=SimpleNamespace(status=SimpleNamespace(value="completed"), run_id=path.name, git_commit="a" * 40),
            results=SimpleNamespace(coverage=SimpleNamespace(failed=0, unsupported=0)),
        ),
    )
    monkeypatch.setattr(commands, "validate_engine_bundle", lambda *args, **kwargs: None)
    monkeypatch.setattr(commands, "artifact_json", lambda *args: {"local_winners": {}})
    return calls


def test_ablation_preserves_matched_caps_and_publishes_complete_index(tmp_path, monkeypatch):
    calls = prepared(monkeypatch)
    path = commands.ablation(
        configs=[RunConfig(budget=8, timeout=20)], output=tmp_path, cache=tmp_path / "cache", timeout=100
    )
    result = json.loads(path.read_text())
    assert result["status"] == "completed" and len(result["cases"]) == 5
    assert [call["variant"] for call in calls] == list(commands.VARIANTS)
    settings = [{key: value for key, value in call.items() if key != "variant"} for call in calls]
    assert all(setting == settings[0] for setting in settings)
    assert all(call["timeout"] == 20 for call in calls)
    assert result["decision_grade"] is False


def test_ablation_stops_before_shrinking_a_later_variants_budget(tmp_path, monkeypatch):
    calls = prepared(monkeypatch)
    clock = [0.0]
    original = commands.run_engine

    def run(*args, **kwargs):
        result = original(*args, **kwargs)
        clock[0] = 81.0
        return result

    monkeypatch.setattr(commands, "run_engine", run)
    monkeypatch.setattr(commands.time, "monotonic", lambda: clock[0])
    with pytest.raises(TimeoutError):
        commands.ablation(
            configs=[RunConfig(budget=8, timeout=20)], output=tmp_path, cache=tmp_path / "cache", timeout=100
        )
    assert len(calls) == 1 and calls[0]["timeout"] == 20
    result = json.loads(next(tmp_path.glob("ablation_*/ablation.json")).read_text())
    assert result["status"] == "incomplete" and len(result["cases"]) == 1
