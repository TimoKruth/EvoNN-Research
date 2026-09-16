"""Canonical bytes for private, replacement-only checkpoint replay states.

This cache must never be used with caller-owned mutable state. Journal recovery
decodes its own objects and replaces changed containers; it never mutates them.
Only the current encoded tree survives a call, so evicted weights are released.
There is no persistent cache or change to the checkpoint format/hash contract.
"""

from dataclasses import dataclass
import hashlib
import json

_BRANCH_CACHE_LIMIT = 256 * 1024


def _plain(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


@dataclass(slots=True)
class _Node:
    value: object
    payload: bytes | None
    children: tuple = ()
    keys: tuple = ()
    size: int = 0

    def __post_init__(self):
        if self.payload is not None:
            self.size = len(self.payload)


def _render(node):
    if node.payload is not None:
        return node.payload
    if type(node.value) is dict:
        return b"{" + b",".join(key + b":" + _render(child) for key, child in zip(node.keys, node.children)) + b"}"
    return b"[" + b",".join(_render(child) for child in node.children) + b"]"


def _branch(item, children, keys=()):
    size = 2 + max(0, len(children) - 1) + sum(child.size for child in children)
    size += sum(len(key) + 1 for key in keys)
    node = _Node(item, None, children, keys, size)
    # Large parents can cheaply join their children's bytes. Retaining every
    # ancestor's full buffer would multiply the memory used by weight arrays.
    if size <= _BRANCH_CACHE_LIMIT:
        node.payload = _render(node)
    return node


def _build(item, previous):
    cached = previous[id(item)] if id(item) in previous else None
    if cached is not None and cached.value is item:
        return cached
    if type(item) is dict and all(type(key) is str for key in item):
        keys = sorted(item)
        children = tuple(_build(item[key], previous) for key in keys)
        return _branch(item, children, tuple(_plain(key) for key in keys))
    if type(item) is list and any(type(child) in (dict, list) for child in item):
        children = tuple(_build(child, previous) for child in item)
        return _branch(item, children)
    # Scalar arrays stay in the C encoder, rather than creating a Python node
    # for every weight. Non-JSON values retain the standard encoder's behavior.
    return _Node(item, _plain(item))


class ReplayEncoder:
    """Reuse byte encodings only for identity-preserved, privately owned nodes."""

    def __init__(self, limit):
        self.limit = limit
        self.root = None

    def encode(self, value):
        if self.root is None or self.root.value is not value:
            previous = {}
            pending = [self.root] if self.root is not None else []
            while pending:
                node = pending[-1]
                del pending[-1]
                if type(node.value) in (dict, list):
                    previous[id(node.value)] = node
                    pending.extend(node.children)

            try:
                self.root = _build(value, previous)
            except RecursionError:
                # Recursive Python assembly has a lower depth ceiling than
                # json.dumps; retain its behavior for deep legacy snapshots.
                self.root = _Node(value, _plain(value))
        if self.root.size + 1 > self.limit:
            raise ValueError("journal record exceeds 128 MiB limit")
        return _render(self.root) + b"\n"

    def digest(self, value):
        return hashlib.sha256(self.encode(value)).hexdigest()
