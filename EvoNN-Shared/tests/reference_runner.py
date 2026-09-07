"""Test-only deterministic persistence consumer for WP-0.10a preparation.

This synthetic no-op is neither an engine nor an admitted benchmark. It uses
real RunStore transactions and checkpoint publication, but its diagnostic
JSON is deliberately not a production symbiosis export. The label boundary
restricts the selector's supplied capabilities; it is not a Python sandbox.

Every candidate, including an invalid one, consumes a budget slot under this
fixture's explicit policy. Failed/invalid observations use distinct metric
names, not fabricated successful scores. CLI ``evaluate:`` lines trace fresh
candidate attempts, including those rejected before full evaluation. Recovery
proves no recharge after a durable row; kills before that row are not covered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal

import duckdb

from evonn_shared.budgets import BudgetAccounting
from evonn_shared.checkpoints import CheckpointPublication, load_latest_checkpoint, publish_checkpoint
from evonn_shared.rng import StreamName, derive_stream
from evonn_shared.run_store import STORE_FILENAME, open_run_store
from evonn_shared.run_workspace import create_run_workspace, open_run_workspace, write_report
from evonn_shared.telemetry import IntegerMeasurement, MeasurementProvenance


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


class SearchView:
    """Selection receives only public features, never the scoring labels."""

    __slots__ = ("features",)

    def __init__(self, features):
        self.features = features


class SyntheticEvaluationFailure(Exception):
    """Only this deliberately injected evaluator failure is a known outcome."""


def evaluate_candidate(candidate, label, *, fail=False):
    if fail:
        raise SyntheticEvaluationFailure("injected synthetic evaluation failure")
    return float(candidate == label)


def select_candidate(view):
    position, stream = view.features
    return (position + stream) % 2


def initialize(root, *, budget, outcomes=None):
    if type(budget) is not int or budget < 0:
        raise ValueError("budget must be a nonnegative integer")
    if outcomes is None:
        outcomes = ("success",) * budget
    if (type(outcomes) not in (tuple, list) or len(outcomes) != budget
            or any(type(value) is not str or value not in ("success", "failed", "invalid") for value in outcomes)):
        raise ValueError("outcomes must declare one known outcome per budget slot")
    workspace = create_run_workspace(root.parent, root.name)
    config = {
        "budget": budget, "root_seed": 19, "outcomes": list(outcomes),
        "attempt_policy": "all_candidates_charged_including_invalid_v1",
    }
    workspace.config_path.write_bytes(encode(config))  # JSON is also valid YAML.
    state = {"config": config, "completed": 0, "score_sum": 0.0, "tip": "0" * 64}
    publish_checkpoint(workspace.checkpoint_directory, workspace.run_id, "step_0", encode(state))
    workspace.state_path.write_bytes(encode(state))
    with open_run_store(root, workspace.run_id, create=True):
        pass
    return root


def crash_if_requested(boundary, step, crash_at, crash_step):
    if (boundary, step) == (crash_at, crash_step):
        print(f"crash:{boundary}:{step}", flush=True)
        os.kill(os.getpid(), signal.SIGKILL)


def run(root, *, stop_after=None, crash_at=None, crash_step=3,
        selector=select_candidate, protected_labels=(0, 1)):
    workspace = open_run_workspace(root)
    config = json.loads(workspace.config_path.read_bytes())
    _, payload = load_latest_checkpoint(workspace.checkpoint_directory)
    state = json.loads(payload)
    if state["config"] != config:
        raise ValueError("configuration differs from the authoritative checkpoint")
    budget = config["budget"]
    target = budget if stop_after is None else stop_after
    if type(target) is not int or not state["completed"] <= target <= budget:
        raise ValueError("stop boundary lies outside the remaining budget")
    if not protected_labels:
        raise ValueError("the synthetic evaluator needs scoring labels")
    stream = derive_stream(config["root_seed"], StreamName.SEARCH)

    with open_run_store(root, workspace.run_id) as store:
        persisted = store.evaluations()
        inherited = len(persisted)
        completed = state["completed"]
        # Append commits before checkpoint publication. Only one row may be
        # ahead; recover that row instead of charging/evaluating it twice.
        if not completed <= inherited <= min(completed + 1, budget):
            raise ValueError("database and checkpoint progress disagree")
        prefix = persisted[:completed]
        expected_tip = prefix[-1].row_sha256 if prefix else "0" * 64
        if state["tip"] != expected_tip or state["score_sum"] != sum(row.metric_value for row in prefix):
            raise ValueError("checkpoint does not describe the persisted prefix")
        if target < inherited:
            raise ValueError("stop boundary precedes already committed work")
        actual = failed = invalid = 0
        for index in range(completed, target):
            step = index + 1
            if index < inherited:
                row = persisted[index]
            else:
                candidate = selector(SearchView((index, stream)))
                outcome = config["outcomes"][index]
                if outcome == "invalid":
                    candidate = None  # Deliberately inject a pre-evaluation rejection.
                if type(candidate) is not int or candidate not in (0, 1):
                    metric, score = "invalid_attempt", 0.0
                    invalid += 1
                else:
                    try:
                        score = evaluate_candidate(
                            candidate, protected_labels[index % len(protected_labels)], fail=outcome == "failed"
                        )
                        metric = "agreement"
                    except SyntheticEvaluationFailure:
                        metric, score = "failed_attempt", 0.0
                        failed += 1
                # All candidates cost one slot under this fixture's explicit
                # policy. Failure/invalid rows are evidence, not valid scores.
                row = store.append_evaluation("synthetic_reference", "noop_reference", metric, score)
                actual += 1
            crash_if_requested("row", step, crash_at, crash_step)
            state = {
                "config": config,
                "completed": step,
                "score_sum": state["score_sum"] + row.metric_value,
                "tip": row.row_sha256,
            }
            publication = CheckpointPublication(
                workspace.checkpoint_directory, workspace.run_id, f"step_{step}", encode(state)
            )
            publication.stage()
            crash_if_requested("stage", step, crash_at, crash_step)
            publication.commit_payload()
            crash_if_requested("payload", step, crash_at, crash_step)
            publication.commit_manifest()
            crash_if_requested("manifest", step, crash_at, crash_step)

        accounting = BudgetAccounting(
            evaluation_count=budget,
            actual_evaluations=actual,
            cached_evaluations=inherited,
            failed_evaluations=failed,
            invalid_evaluations=invalid,
            resumed_from_run_id=workspace.run_id if inherited else None,
            resumed_evaluations=inherited,
            partial_run=actual + inherited < budget,
            evaluation_semantics=(
                "Each synthetic candidate costs one slot including failed/invalid attempts; "
                "failure/invalid counters describe fresh work and prior attempts are cached on continuation."
            ),
        )
        # These derived views are rebuilt after resume; the manifest and row
        # chain, not a possibly interrupted view write, establish authority.
        workspace.state_path.write_bytes(encode(state))
        workspace.summary_path.write_bytes(accounting.model_dump_json().encode() + b"\n")
        write_report(workspace, store)
    return accounting


def export_diagnostic(root, destination):
    """Read a closed fixture through DuckDB's enforced read-only connection."""
    if destination.resolve().is_relative_to(root.resolve()):
        raise ValueError("diagnostic export must be outside the source workspace")
    workspace = open_run_workspace(root)
    workspace.validate()
    _, payload = load_latest_checkpoint(workspace.checkpoint_directory)
    accounting = BudgetAccounting.model_validate_json(workspace.summary_path.read_bytes())
    with duckdb.connect(str(root / STORE_FILENAME), read_only=True) as connection:
        cursor = connection.execute(
            "SELECT sequence, benchmark_id, contender_id, metric_name, metric_value, "
            "previous_sha256, row_sha256 FROM evaluations ORDER BY sequence"
        )
        names = [column[0] for column in cursor.description]
        evaluations = [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]
    measured = IntegerMeasurement.model_validate({
        "value": sum(path.stat().st_size for path in root.rglob("*") if path.is_file()),
        "provenance": MeasurementProvenance.MEASURED,
    })
    diagnostic = {
        "evidence_class": "synthetic_contract_preparation",
        "attempt_totals": {
            "success": sum(row["metric_name"] == "agreement" for row in evaluations),
            "failed": sum(row["metric_name"] == "failed_attempt" for row in evaluations),
            "invalid": sum(row["metric_name"] == "invalid_attempt" for row in evaluations),
        },
        "checkpoint_sha256": hashlib.sha256(payload).hexdigest(),
        "state": json.loads(payload),
        "accounting": accounting.model_dump(mode="json"),
        "evaluations": evaluations,
        "source_bytes": measured.model_dump(mode="json"),
    }
    with destination.open("xb") as output:
        output.write(encode(diagnostic))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--crash-at", choices=("row", "stage", "payload", "manifest"))
    parser.add_argument("--crash-step", type=int, default=3)
    options = parser.parse_args()

    def traced_selection(view):
        print(f"evaluate:{view.features[0]}", flush=True)
        return select_candidate(view)

    run(options.root, crash_at=options.crash_at, crash_step=options.crash_step, selector=traced_selection)
