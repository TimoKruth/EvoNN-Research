"""Replay byte compatibility across persistent updates and hostile journals."""

from copy import deepcopy
import hashlib
import gc
import json
import random
import weakref

import pytest

from evonn_shared._journal_encoding import ReplayEncoder
from evonn_shared import _journal_encoding
from evonn_shared.runtime_journal import LIMIT, apply_delta, delta, encode


@pytest.mark.parametrize("branch_cache_limit", [64, 256 * 1024])
def test_canonical_bytes_match_across_replacements_appends_and_evictions(monkeypatch, branch_cache_limit):
    monkeypatch.setattr(_journal_encoding, "_BRANCH_CACHE_LIMIT", branch_cache_limit)
    rng = random.Random(3821)
    state = {
        "attempts": [],
        "cache": [[str(i), {"weights": [rng.random() for _ in range(96)]}] for i in range(8)],
        "numeric": [1, 1.0, True, False, None, -0.0, 0.0, 1e-7, 1e20, 10**50],
        "strings": {"é": '雪\n\t"\\', "surrogate": "\ud800", "\x00": "\u2028"},
    }
    encoder = ReplayEncoder(LIMIT)
    for step in range(64):
        expected = encode(state)
        assert encoder.encode(state) == expected
        assert encoder.digest(state) == hashlib.sha256(expected).hexdigest()
        next_state = deepcopy(state)
        next_state["attempts"].append({"step": step, "score": rng.random()})
        next_state["cache"] = next_state["cache"][1:] + [
            [str(step + 8), {"weights": [rng.random() for _ in range(96)]}]
        ]
        next_state["numeric"] = [1.0 if step % 2 else 1, -0.0 if step % 3 else 0.0]
        if step % 2:
            next_state.pop("optional", None)
        else:
            next_state["optional"] = {"nested": [None, {"v": step}]}
        # Actual replay delta operations preserve unchanged object identities.
        restored = apply_delta(state, delta(state, next_state))
        assert encode(state) == expected  # No mutation behind cached bytes.
        state = restored if step % 16 else json.loads(encode(restored))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_values_still_fail(value):
    with pytest.raises(ValueError):
        ReplayEncoder(LIMIT).encode({"weights": [0.0, value]})


def test_byte_limit_includes_newline_and_applies_to_cached_root():
    state = {"value": "雪"}
    payload = encode(state)
    encoder = ReplayEncoder(len(payload))
    assert encoder.encode(state) == payload
    encoder.limit -= 1
    with pytest.raises(ValueError, match="128 MiB"):
        encoder.encode(state)


def test_deep_legacy_value_retains_standard_encoder_behavior():
    value = None
    for _ in range(400):
        value = [value]
    assert ReplayEncoder(LIMIT).encode(value) == encode(value)


def test_evicted_payload_is_released_without_waiting_for_cycle_collection():
    class Payload(list):
        pass

    encoder = ReplayEncoder(LIMIT)
    value = Payload([1.0] * 128)
    reference = weakref.ref(value)
    enabled = gc.isenabled()
    gc.disable()
    try:
        encoder.encode({"weights": value})
        del value
        encoder.encode({"weights": [2.0] * 128})
        assert reference() is None
    finally:
        if enabled:
            gc.enable()
