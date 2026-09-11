"""Local projection identities, optional information paths and learned shared cells."""
import hashlib
import json
import numpy as np

from .genome import order
from .operators import OPERATORS
from .research import ResearchPolicy
from .tensors import Backend


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class ResearchHierarchy:
    def __init__(self, genome, input_shape, output_dim, modality, task, *, backend='numpy_fallback', device='cpu', seed=0):
        self.genome = genome
        self.policy = ResearchPolicy.model_validate(genome.execution)
        self.evaluator_fidelity = self.policy.fidelity
        self.backend = Backend(backend, device)
        self.input_shape, self.output_dim = tuple(input_shape), output_dim
        self.modality, self.task = modality, task
        self.token_input = task == 'language_modeling'
        if output_dim < 1 or not input_shape or any(int(size) < 1 for size in input_shape):
            raise ValueError('positive input/output dimensions required')
        self.cells = {cell.id: cell for cell in genome.cells}
        self.executors = {node.id: self.cells[node.cell_id] for node in genome.macro_nodes}
        self.ordered, self.incoming, _ = order(genome.macro_nodes, genome.macro_edges, genome.output)
        self.weights, self.fixed, self.buffers, self.parameter_signatures = {}, {}, {}, {}
        dummy = np.zeros((1, *input_shape), dtype=np.float32)
        width = self._graph({}, dummy, initialize=True).shape[-1]
        rng = np.random.default_rng(seed)
        hidden = self.policy.head_width
        self.weights.update({
            'head.w': (rng.normal(size=(width, hidden)) / np.sqrt(width)).astype(np.float32),
            'head.b': np.zeros(hidden, dtype=np.float32),
            'readout.w': (rng.normal(size=(hidden, output_dim)) / np.sqrt(hidden)).astype(np.float32),
            'readout.b': np.zeros(output_dim, dtype=np.float32),
        })
        self.feature_signature = self.representation_signature()

    @property
    def parameter_count(self):
        return sum(value.size for value in self.weights.values())

    def _project(self, value, width, cell, node, parameters, initialize, *, merge=False):
        label = 'macro_merge' if merge else node.id
        signature = digest([node.projection_seed, label, value.shape[-1], width])
        key = f'cell.{cell.parameter_id}.{label}.{value.shape[-1]}.{width}'
        target = self.weights if self.policy.evaluator == 'trainable' else self.fixed
        if initialize and key not in target:
            rng = np.random.default_rng(int(signature[:8], 16))
            target[key] = (rng.normal(size=(value.shape[-1], width)) / np.sqrt(value.shape[-1])).astype(np.float32)
            self.parameter_signatures[key] = signature
        matrix = self.backend.array(target[key]) if initialize or self.policy.evaluator == 'proxy' else parameters[key]
        return value @ matrix

    def _input(self, inputs):
        x = np.asarray(inputs, dtype=np.float32)
        if self.token_input:
            if x.ndim != 2 or not np.isfinite(x).all() or not np.equal(x, np.floor(x)).all() or np.any(x < 0) or np.any(x >= self.output_dim):
                raise ValueError('LM requires causal integer token sequences within vocabulary')
            x = np.eye(self.output_dim, dtype=np.float32)[x.astype(np.int64)]
        else:
            x = x.reshape((len(x), -1))
        return self.backend.array(x)

    def _graph(self, parameters, inputs, *, initialize=False):
        b = self.backend
        x = self._input(inputs)
        values = {}
        for name in self.ordered:
            cell = self.executors[name]
            parents = [values[parent] for parent in self.incoming[name]] or [x]
            source = parents[0] if len(parents) == 1 else sum(
                self._project(parent, cell.nodes[0].width, cell, cell.nodes[0], parameters, initialize, merge=True)
                for parent in parents) / len(parents)
            ordered, incoming, _ = order(cell.nodes, cell.edges, cell.output)
            nodes = {node.id: node for node in cell.nodes}
            local = {}
            for node_id in ordered:
                node = nodes[node_id]
                inputs_here = [local[parent] for parent in incoming[node_id]] or [source]
                merged = sum(self._project(parent, node.width, cell, node, parameters, initialize)
                             for parent in inputs_here) / len(inputs_here)
                activated = b.activate(merged, node.activation)
                value = OPERATORS[node.primitive](b, activated, merged)
                if self.policy.residual:
                    skip = sum(parent if parent.shape[-1] == node.width else
                               self._project(parent, node.width, cell, node, parameters, initialize)
                               for parent in inputs_here) / len(inputs_here)
                    value = (value + skip) * (2 ** -.5)
                local[node_id] = value
            values[name] = local[cell.output]
        if self.policy.readout == 'all':
            return b.concatenate([values[name] for name in self.ordered])
        if self.policy.readout == 'input_final':
            return b.concatenate([x, values[self.genome.output]])
        return values[self.genome.output]

    def representation_signature(self, remapping=None):
        """Hash the executed expression, including learned parameter bindings.

        Expanding shared calls makes an inherited clone equivalent to its source,
        while independent specialized cells retain distinct learned bindings.
        """
        remapping = remapping or {}
        x = (digest(['input', self.input_shape, self.output_dim, self.task]),
             self.output_dim if self.token_input else int(np.prod(self.input_shape)))
        def projected(parent, width, cell, node, merge=False):
            label = 'macro_merge' if merge else node.id
            key = f'cell.{cell.parameter_id}.{label}.{parent[1]}.{width}'
            binding = (remapping[key] if key in remapping else key) if self.policy.evaluator == 'trainable' else digest([node.projection_seed, label, parent[1], width])
            return digest(['project', binding, parent[0], width])
        values = {}
        for name in self.ordered:
            cell = self.executors[name]
            parents = [values[parent] for parent in self.incoming[name]] or [x]
            source = parents[0] if len(parents) == 1 else (digest([projected(parent, cell.nodes[0].width, cell, cell.nodes[0], True) for parent in parents]), cell.nodes[0].width)
            ordered, incoming, _ = order(cell.nodes, cell.edges, cell.output)
            nodes, local = {n.id: n for n in cell.nodes}, {}
            for identity in ordered:
                node = nodes[identity]
                inputs = [local[parent] for parent in incoming[identity]] or [source]
                merged = [projected(parent, node.width, cell, node) for parent in inputs]
                skip = [parent[0] if parent[1] == node.width else projected(parent, node.width, cell, node) for parent in inputs] if self.policy.residual else []
                local[identity] = (digest([node.activation, node.primitive, merged, skip]), node.width)
            values[name] = local[cell.output]
        outputs = ([values[name] for name in self.ordered] if self.policy.readout == 'all' else
                   [x, values[self.genome.output]] if self.policy.readout == 'input_final' else [values[self.genome.output]])
        return digest([outputs, self.policy.normalization, self.policy.head_width, self.output_dim])

    def prepare_features(self, inputs):
        """Fit only on standardized training inputs; freeze buffers for replay."""
        if self.policy.normalization == 'train_standard':
            if getattr(self, 'reuse_feature_statistics', False) and 'hierarchy_standard_v2' in self.buffers:
                return
            values = self.features(inputs, normalized=False)
            # A single per-channel statistic across examples/tokens. No validation
            # data, position-specific statistics or inference-batch fitting.
            axes = tuple(range(values.ndim - 1))
            mean, std = values.mean(axis=axes), np.maximum(values.std(axis=axes), 1e-5)
            self.buffers['hierarchy_standard_v2'] = (mean.astype(np.float32), std.astype(np.float32))

    def _normalize(self, value):
        if self.policy.normalization == 'rms':
            return value / ((value * value).mean(axis=-1, keepdims=True) + 1e-5) ** .5
        if self.policy.normalization == 'train_standard':
            if 'hierarchy_standard_v2' not in self.buffers:
                raise ValueError('missing training-only hierarchy normalization buffers')
            mean, std = self.buffers['hierarchy_standard_v2']
            if mean.shape != (value.shape[-1],) or std.shape != mean.shape or not np.isfinite(mean).all() or not np.isfinite(std).all() or np.any(std < 1e-5):
                raise ValueError('invalid hierarchy normalization buffers')
            return (value - self.backend.array(mean)) / self.backend.array(std)
        return value

    def features(self, inputs, *, normalized=False):
        value = self._graph({key: self.backend.array(v) for key, v in self.weights.items()}, inputs)
        return self.backend.numpy(self._normalize(value) if normalized else value)

    def forward(self, parameters, inputs, *, training=False, seed=0):
        b = self.backend
        features = self._normalize(self._graph(parameters, b.numpy(inputs)))
        hidden = b.activate(features @ parameters['head.w'] + parameters['head.b'], 'gelu')
        return hidden @ parameters['readout.w'] + parameters['readout.b']
