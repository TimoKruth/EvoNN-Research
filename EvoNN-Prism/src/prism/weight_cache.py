"""Prism optimizer snapshots share the existing weight-cache byte/entry limits."""

from copy import deepcopy
import json
from evonn_shared.weight_cache import WeightCache


class PrismWeightCache(WeightCache):
    def put(self, namespace, identity, topology, family, weights, buffers=None, optimizer_state=None):
        super().put(namespace, identity, topology, family, weights, buffers)
        key = namespace + ":" + identity
        if optimizer_state is not None and key in self.entries:
            # Replace payloads: committed runner snapshots may share old entries.
            self.entries[key] = {**self.entries[key], "optimizer_state": deepcopy(optimizer_state)}
            self.entry_bytes -= self.sizes[key]
            self.sizes[key] = len(json.dumps([key, self.entries[key]], separators=(",", ":")).encode())
            self.entry_bytes += self.sizes[key]
            self._trim()

    def inherit(self, model, **options):
        result = super().inherit(model, **options)
        model.optimizer_state = None
        if result["mode"] == "exact":
            item = self.entries[options["namespace"] + ":" + result["source"]]
            model.optimizer_state = deepcopy(item.get("optimizer_state"))
        return result
