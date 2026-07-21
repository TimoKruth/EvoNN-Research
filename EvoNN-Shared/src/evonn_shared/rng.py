"""Scheduling-independent deterministic RNG stream derivation."""

from __future__ import annotations

from enum import StrEnum
import hashlib

from .canonical import CanonicalIdentityError

_RNG_STREAM_DOMAIN = b"evonn-rng-stream/v1\0"


class StreamName(StrEnum):
    SEARCH = "search"
    DATA = "data"
    SPLIT = "split"
    INIT = "init"
    ORDER = "order"
    AUGMENTATION = "augmentation"
    MUTATION = "mutation"
    BENCHMARK_SAMPLING = "benchmark_sampling"
    WORKER = "worker"
    STATS = "stats"


class InvalidRootSeedError(CanonicalIdentityError):
    code = "invalid_root_seed"


class InvalidStreamNameError(CanonicalIdentityError):
    code = "invalid_stream_name"


def derive_stream(root_seed: int, name: StreamName) -> int:
    """Derive one stable unsigned 128-bit stream seed from the root seed."""

    if isinstance(root_seed, bool) or not isinstance(root_seed, int) or not 0 <= root_seed < 2**256:
        raise InvalidRootSeedError(
            "root_seed must be an integer in the range 0 <= root_seed < 2**256"
        )
    if not isinstance(name, StreamName):
        raise InvalidStreamNameError("name must be a StreamName member")

    payload = (
        _RNG_STREAM_DOMAIN
        + root_seed.to_bytes(32, "big")
        + b"\0"
        + name.value.encode("ascii")
    )
    return int.from_bytes(hashlib.sha256(payload).digest()[:16], "big")


__all__ = [
    "InvalidRootSeedError",
    "InvalidStreamNameError",
    "StreamName",
    "derive_stream",
]
