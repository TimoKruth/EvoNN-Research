"""Preparatory WP-0.10a evidence; no production benchmark or engine claim."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys

import duckdb
import pytest

from evonn_shared.budgets import BudgetAccounting
from evonn_shared.checkpoints import load_latest_checkpoint
from evonn_shared.run_store import open_run_store


RUNNER = Path(__file__).with_name("reference_runner.py")


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("reference_runner_fixture", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def invoke(root, *args):
    return subprocess.run(
        [sys.executable, str(RUNNER), str(root), *map(str, args)],
        capture_output=True, text=True, timeout=30,
    )


def tree_bytes(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def rows(root):
    with open_run_store(root, root.name) as store:
        return store.evaluations()


@pytest.mark.parametrize("boundary", ["row", "stage", "payload", "manifest"])
@pytest.mark.parametrize("step", [1, 3, 6])
def test_resume_equals_uninterrupted(tmp_path, runner, boundary, step):
    baseline = runner.initialize(tmp_path / "baseline", budget=6)
    interrupted = runner.initialize(tmp_path / "interrupted", budget=6)
    complete = invoke(baseline)
    assert complete.returncode == 0, complete.stderr
    assert complete.stdout.splitlines() == [f"evaluate:{index}" for index in range(6)]
    killed = invoke(interrupted, "--crash-at", boundary, "--crash-step", step)
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    assert killed.stdout.splitlines() == [
        *[f"evaluate:{index}" for index in range(step)], f"crash:{boundary}:{step}"
    ]

    # Do not open a writer on the killed run here: the resumed child must
    # itself exercise stale-lock and DuckDB WAL recovery.
    before = rows(baseline)[:step]
    _, checkpoint = load_latest_checkpoint(interrupted / "checkpoints")
    assert json.loads(checkpoint)["completed"] == (step if boundary == "manifest" else step - 1)

    resumed = invoke(interrupted)
    assert resumed.returncode == 0, resumed.stderr
    assert resumed.stdout.splitlines() == [f"evaluate:{index}" for index in range(step, 6)]
    assert rows(interrupted) == rows(baseline)
    assert rows(interrupted)[:step] == before
    assert load_latest_checkpoint(interrupted / "checkpoints")[1] == load_latest_checkpoint(
        baseline / "checkpoints"
    )[1]
    accounting = BudgetAccounting.model_validate_json((interrupted / "summary.json").read_bytes())
    assert accounting.actual_evaluations == 6 - step
    assert accounting.cached_evaluations == accounting.resumed_evaluations == step
    assert accounting.resumed_from_run_id == interrupted.name
    assert not accounting.partial_run


def test_partial_and_repeated_resume_do_not_double_count(tmp_path, runner):
    root = runner.initialize(tmp_path / "partial", budget=6)
    first = runner.run(root, stop_after=2)
    second = runner.run(root, stop_after=5)
    third = runner.run(root)
    again = runner.run(root)
    assert [a.actual_evaluations for a in (first, second, third, again)] == [2, 3, 1, 0]
    assert [a.resumed_evaluations for a in (first, second, third, again)] == [0, 2, 5, 6]
    assert [a.partial_run for a in (first, second, third, again)] == [True, True, False, False]
    assert first.resumed_from_run_id is None
    assert sum(a.actual_evaluations for a in (first, second, third, again)) == 6
    assert len(rows(root)) == 6


def test_zero_budget_performs_no_evaluation(tmp_path, runner):
    root = runner.initialize(tmp_path / "empty", budget=0)
    accounting = runner.run(root)
    assert accounting.actual_evaluations == accounting.cached_evaluations == 0
    assert not accounting.partial_run
    assert rows(root) == ()


def test_changed_budget_is_rejected_before_continuation(tmp_path, runner):
    root = runner.initialize(tmp_path / "budget", budget=6)
    runner.run(root, stop_after=2)
    config = json.loads((root / "config.yaml").read_bytes())
    config["budget"] = 7
    (root / "config.yaml").write_text(json.dumps(config))
    before = tree_bytes(root)
    with pytest.raises(ValueError, match="configuration"):
        runner.run(root)
    assert tree_bytes(root) == before


@pytest.mark.parametrize("stop", [-1, 7, True])
def test_invalid_stop_cannot_overrun_budget(tmp_path, runner, stop):
    root = runner.initialize(tmp_path / "budget", budget=6)
    before = tree_bytes(root)
    with pytest.raises(ValueError, match="budget"):
        runner.run(root, stop_after=stop)
    assert tree_bytes(root) == before


def test_protected_label_capability_boundary(tmp_path, runner):
    root = runner.initialize(tmp_path / "protected", budget=2)

    def leak(view):
        return view.protected_labels[0]

    with pytest.raises(AttributeError):
        runner.run(root, selector=leak)
    assert rows(root) == ()
    seen = []

    def inspect(view):
        assert not hasattr(view, "__dict__")
        assert not hasattr(view, "protected_labels")
        seen.append(view.features)
        return runner.select_candidate(view)

    runner.run(root, selector=inspect)
    assert len(seen) == 2


def test_selection_is_unchanged_when_only_protected_labels_change(tmp_path, runner):
    traces = []
    results = []
    for name, labels in [("left", (0, 1)), ("right", (1, 0))]:
        root = runner.initialize(tmp_path / name, budget=2)
        trace = []

        def select(view):
            candidate = runner.select_candidate(view)
            trace.append(candidate)
            return candidate

        runner.run(root, selector=select, protected_labels=labels)
        traces.append(trace)
        results.append([row.metric_value for row in rows(root)])
    assert traces[0] == traces[1]
    assert results[0] != results[1]


def test_export_is_read_only(tmp_path, runner, monkeypatch):
    root = runner.initialize(tmp_path / "source", budget=3)
    runner.run(root)
    before = tree_bytes(root)
    connect = duckdb.connect
    opens = []

    def read_only(*args, **kwargs):
        opens.append(kwargs)
        assert kwargs["read_only"] is True
        connection = connect(*args, **kwargs)
        with pytest.raises(duckdb.InvalidInputException, match="read-only"):
            connection.execute("DELETE FROM evaluations")
        return connection

    monkeypatch.setattr(runner.duckdb, "connect", read_only)
    destination = tmp_path / "diagnostic.json"
    runner.export_diagnostic(root, destination)
    assert opens == [{"read_only": True}]
    assert tree_bytes(root) == before
    exported = json.loads(destination.read_bytes())
    assert exported["evidence_class"] == "synthetic_contract_preparation"
    assert len(exported["evaluations"]) == 3
    assert exported["checkpoint_sha256"] == hashlib.sha256(
        load_latest_checkpoint(root / "checkpoints")[1]
    ).hexdigest()
    assert exported["source_bytes"]["provenance"] == "measured"
    assert exported["source_bytes"]["value"] == sum(
        path.stat().st_size for path in root.rglob("*") if path.is_file()
    )


@pytest.mark.parametrize("alias", [False, True])
def test_export_destination_cannot_modify_source(tmp_path, runner, alias):
    root = runner.initialize(tmp_path / "source", budget=1)
    runner.run(root)
    destination_root = root
    if alias:
        destination_root = tmp_path / "alias"
        destination_root.symlink_to(root, target_is_directory=True)
    before = tree_bytes(root)
    with pytest.raises(ValueError, match="outside"):
        runner.export_diagnostic(root, destination_root / "summary.json")
    assert tree_bytes(root) == before
