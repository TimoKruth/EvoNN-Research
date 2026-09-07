"""Bounded serializable weight snapshots, isolated by complete evaluation namespace."""

from collections import OrderedDict
import json
import numpy as np


class WeightCache:
    def __init__(self, capacity=8, state=None):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("positive cache capacity required")
        self.capacity = capacity
        self.entries = OrderedDict(state or [])

    def put(self, namespace, identity, topology, family, weights, buffers=None):
        key = namespace + ":" + identity
        if key in self.entries:
            del self.entries[key]
        self.entries[key] = {
            "namespace": namespace,
            "identity": identity,
            "topology": topology,
            "family": family,
            "buffers": {k: [np.asarray(a).tolist() for a in v] for k, v in (buffers or {}).items()},
            "weights": {k: np.asarray(v, dtype=np.float32).tolist() for k, v in weights.items()},
        }
        while (
            len(self.entries) > self.capacity
            or len(json.dumps(list(self.entries.items()), separators=(",", ":"))) > 32 * 1024**2
        ):
            self.entries.popitem(last=False)

    def inherit(
        self, model, *, namespace, identity, topology, family, parents=(), compatible_groups=(), allow_partial=True
    ):
        candidates = [(key, item) for key, item in self.entries.items() if item["namespace"] == namespace]

        def priority(pair):
            _, item = pair
            return (
                item["identity"] == identity,
                (len(parents) - parents.index(item["identity"])) if item["identity"] in parents else 0,
                item["family"] == family,
                item["topology"] == topology,
                item["family"] in compatible_groups,
            )

        candidates.sort(key=priority, reverse=True)
        for key, item in candidates:
            exact = item["identity"] == identity
            compatible = item["topology"] == topology or item["family"] in compatible_groups or item["family"] == family
            if not exact and (not allow_partial or not compatible):
                continue
            copied = 0
            for name, value in model.weights.items():
                if name not in item["weights"]:
                    continue
                old = np.asarray(item["weights"][name], dtype=np.float32)
                if old.shape == value.shape:
                    model.weights[name] = old.copy()
                    copied += old.size
                elif not exact and old.ndim == value.ndim:
                    selection = tuple(slice(0, min(a, b)) for a, b in zip(old.shape, value.shape))
                    model.weights[name][selection] = old[selection]
                    copied += old[selection].size
            if copied:
                if exact:
                    model.buffers = {
                        k: tuple(np.asarray(a, dtype=np.float32) for a in v) for k, v in item["buffers"].items()
                    }
                self.entries.move_to_end(key)
                return {
                    "mode": "exact" if exact and copied == model.parameter_count else "partial",
                    "source": item["identity"],
                    "copied_parameters": copied,
                }
        return {"mode": "none", "source": None, "copied_parameters": 0}

    def state(self):
        return list(self.entries.items())
