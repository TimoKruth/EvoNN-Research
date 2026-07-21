from __future__ import annotations

from enum import StrEnum
import importlib
import json
from pathlib import Path
from typing import Any

import pytest

GOLDEN_PATH = Path(__file__).parent / "golden" / "canonical-v1.json"


def _rng() -> Any:
    return importlib.import_module("evonn_shared.rng")


def _golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def test_stream_name_is_the_exact_closed_ten_member_enum() -> None:
    rng = _rng()

    assert issubclass(rng.StreamName, StrEnum)
    assert {name.name: name.value for name in rng.StreamName} == {
        "SEARCH": "search",
        "DATA": "data",
        "SPLIT": "split",
        "INIT": "init",
        "ORDER": "order",
        "AUGMENTATION": "augmentation",
        "MUTATION": "mutation",
        "BENCHMARK_SAMPLING": "benchmark_sampling",
        "WORKER": "worker",
        "STATS": "stats",
    }


def test_all_ten_streams_match_independent_golden_vectors() -> None:
    rng = _rng()
    golden = _golden()["rng"]

    actual = {name.value: rng.derive_stream(golden["root_seed"], name) for name in rng.StreamName}

    assert actual == golden["streams"]
    assert len(set(actual.values())) == 10
    assert all(0 <= value < 2**128 for value in actual.values())


@pytest.mark.parametrize("root_seed", [0, 2**256 - 1])
def test_root_seed_boundaries_are_accepted(root_seed: int) -> None:
    rng = _rng()

    assert 0 <= rng.derive_stream(root_seed, rng.StreamName.SEARCH) < 2**128


@pytest.mark.parametrize("root_seed", [True, False, -1, 2**256, 1.0, "1", None])
def test_invalid_root_seeds_are_rejected(root_seed: object) -> None:
    rng = _rng()

    with pytest.raises(rng.InvalidRootSeedError) as error:
        rng.derive_stream(root_seed, rng.StreamName.SEARCH)

    assert error.value.code == "invalid_root_seed"
    assert str(error.value) == "root_seed must be an integer in the range 0 <= root_seed < 2**256"


class OtherStream(StrEnum):
    SEARCH = "search"


@pytest.mark.parametrize("name", ["search", OtherStream.SEARCH, 1, None])
def test_only_stream_name_members_are_accepted(name: object) -> None:
    rng = _rng()

    with pytest.raises(rng.InvalidStreamNameError) as error:
        rng.derive_stream(42, name)

    assert error.value.code == "invalid_stream_name"
    assert str(error.value) == "name must be a StreamName member"
