"""Crash consistency, corruption rejection and history storage scaling."""
from copy import deepcopy
import json

import pytest

from evonn_shared.checkpoints import publish_checkpoint
from evonn_shared.runtime_journal import (JournalPublication, apply_delta, delta, encode,
    load_runtime_checkpoint, load_transaction, publish_initial, publish_transaction)


def initial():
    return {"completed": 0, "attempts": [], "config": {"seed": 42}, "tip": "0" * 64,
            "search": {"rng": 0, "archive": [], "weights": [0.0] * 128}}


def advance(state):
    value = deepcopy(state)
    value["completed"] += 1
    step = value["completed"]
    value["attempts"].append({"id": step, "charged": 1, "model": "x" * 2048})
    value["search"]["rng"] = step
    value["search"]["archive"] = list(range(max(0, step - 4), step))
    value["search"]["weights"][step % 128] = float(step)
    value["tip"] = f"{step:064x}"
    return value


def commit(root, previous, state):
    p = JournalPublication(root, "run_test", f"step_{state['completed']}", state, previous=previous)
    p.stage()
    p.commit_payload()
    p.commit_manifest()


def test_roundtrip_periodic_snapshots_and_linear_history_storage(tmp_path):
    state = initial()
    publish_initial(tmp_path, "run_test", "step_0", state)
    sizes = []
    for step in range(1, 257):
        next_state = advance(state)
        transaction = tmp_path / f"transaction_{step}.json"
        publish_transaction(transaction, state, next_state)
        assert load_transaction(transaction, state)["state"] == next_state
        commit(tmp_path, state, next_state)
        state = next_state
        if step in (16, 128, 256):
            assert json.loads(load_runtime_checkpoint(tmp_path)[1]) == state
            sizes.append(sum(p.stat().st_size for p in tmp_path.iterdir()))
    assert sizes[2] < 2.2 * sizes[1]
    assert sizes[2] < 256 * len(encode(state)) / 10
    snapshot = json.loads((tmp_path / "step_256.ckpt").read_bytes())
    assert "attempts" not in snapshot["snapshot"]


@pytest.mark.parametrize("boundary", ["stage", "payload", "manifest"])
def test_commit_boundary_and_orphan_adoption(tmp_path, boundary):
    before, after = initial(), advance(initial())
    publish_initial(tmp_path, "run_test", "step_0", before)
    p = JournalPublication(tmp_path, "run_test", "step_1", after, previous=before)
    p.stage()
    if boundary != "stage":
        p.commit_payload()
    if boundary == "manifest":
        p.commit_manifest()
    assert json.loads(load_runtime_checkpoint(tmp_path)[1]) == (after if boundary == "manifest" else before)
    if boundary != "manifest":
        commit(tmp_path, before, after)
        assert json.loads(load_runtime_checkpoint(tmp_path)[1]) == after


def test_legacy_anchor_and_mutated_predecessor_rejected(tmp_path):
    before = initial()
    publish_checkpoint(tmp_path, "run_test", "step_0", encode(before))
    wrong = deepcopy(before)
    wrong["search"]["rng"] = 33
    with pytest.raises(ValueError, match="committed logical"):
        commit(tmp_path, wrong, advance(wrong))
    after = advance(before)
    commit(tmp_path, before, after)
    assert json.loads(load_runtime_checkpoint(tmp_path)[1]) == after
    (tmp_path / "step_0.ckpt").write_bytes(encode(wrong))
    with pytest.raises(ValueError, match="mismatch"):
        load_runtime_checkpoint(tmp_path)


def test_pending_transaction_tampering_and_progress_rejected(tmp_path):
    before, after = initial(), advance(initial())
    path = tmp_path / "transaction.json"
    publish_transaction(path, before, after)
    value = json.loads(path.read_bytes())
    value["attempt"]["charged"] = 0
    path.write_bytes(encode(value))
    with pytest.raises(ValueError, match="hash mismatch"):
        load_transaction(path, before)
    after["completed"] += 1
    with pytest.raises(ValueError, match="attempt count"):
        publish_transaction(tmp_path / "bad.json", before, after)


def test_delta_deletions_append_and_replacements():
    before = {"a": {"x": [1, 2], "gone": 2}, "b": [1, 2], "c": None}
    after = {"a": {"x": [1, 2, 3], "new": False}, "b": [5], "c": {"z": 1}}
    assert apply_delta(before, delta(before, after)) == after
    assert before["a"]["x"] == [1, 2]
    with pytest.raises(ValueError, match="delta"):
        apply_delta(before, {"dict": {}, "remove": ["absent"]})


@pytest.mark.parametrize("before,after", [(1, 1.0), (1, True), (0.0, -0.0), ({"x": [1]}, {"x": [1.0]})])
def test_canonical_numeric_types_survive_journal(tmp_path, before, after):
    old = initial()
    old["search"]["value"] = before
    new = advance(old)
    new["search"]["value"] = after
    publish_initial(tmp_path, "run_test", "step_0", old)
    commit(tmp_path, old, new)
    assert load_runtime_checkpoint(tmp_path)[1] == encode(new)


@pytest.mark.parametrize("value", [[], {}, None, {"format": "bad"}])
def test_malformed_transactions_fail_closed(tmp_path, value):
    path = tmp_path / "bad.json"
    path.write_bytes(encode(value))
    with pytest.raises(ValueError):
        load_transaction(path, initial())


def test_real_weight_cache_eviction_and_reordering_stays_incremental():
    import numpy as np
    from evonn_shared.weight_cache import WeightCache
    cache = WeightCache(16)
    for index in range(16):
        cache.put("bench", str(index), "shape", "family", {"w": np.full(4096, index, dtype=np.float32)})
    before = json.loads(encode(cache.state()))
    cache.put("bench", "16", "shape", "family", {"w": np.ones(4096, dtype=np.float32)})
    after = json.loads(encode(cache.state()))
    changes = delta(before, after)
    assert apply_delta(before, changes) == after
    assert len(encode(changes)) < len(encode(after)) / 8
