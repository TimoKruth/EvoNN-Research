"""Versioned learned temporal cells; v1/v2 execution is deliberately unchanged.

Attention uses a causal mask and optional learned relative-lag bias. Dilated
depthwise convolution covers powers-of-two lags up to the declared context.
Every shared call uses the same parameter arrays, including gates and mixers.
"""
import numpy as np

from .compiler_v2 import ResearchHierarchy, digest
from .genome import order
from .operators import OPERATORS


class TemporalHierarchy(ResearchHierarchy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.policy.readout_skip:
            width = self.weights['head.w'].shape[0]
            self.weights['skip.w'] = np.zeros((width, self.output_dim), dtype=np.float32)

    def _parameter(self, key, shape, parameters, initialize, seed, *, constant=None):
        signature = digest(['temporal_v3', seed, key.split('.', 2)[-1], shape])
        if initialize and key not in self.weights:
            rng = np.random.default_rng(int(signature[:8], 16))
            self.weights[key] = (np.full(shape, constant, dtype=np.float32) if constant is not None
                                 else (rng.normal(size=shape) / np.sqrt(shape[0])).astype(np.float32))
            self.parameter_signatures[key] = signature
        return self.backend.array(self.weights[key]) if initialize else parameters[key]

    @staticmethod
    def _rms(value):
        return value / ((value * value).mean(axis=-1, keepdims=True) + 1e-5) ** .5

    def _tokens(self, inputs, parameters, initialize):
        if self.token_input:
            inputs = np.asarray(inputs, dtype=np.float32)
            if inputs.shape[1:] != self.input_shape:
                raise ValueError('token context differs from the declared input shape')
            if (not np.isfinite(inputs).all() or not np.equal(inputs, np.floor(inputs)).all()
                    or np.any(inputs < 0) or np.any(inputs >= self.output_dim)):
                raise ValueError('LM requires causal integer token sequences within vocabulary')
            if self.policy.embedding_width:
                embedding = self._parameter('input.embedding', (self.output_dim, self.policy.embedding_width),
                                            parameters, initialize, 0)
                value = self.backend.gather(embedding, inputs.astype(np.int64))
            else:
                value = self._input(inputs)
            if self.policy.position == 'sinusoidal':
                width = value.shape[-1]
                angles = np.arange(value.shape[1])[:, None] / 10000 ** (2 * (np.arange(width) // 2) / width)
                encoding = np.where(np.arange(width) % 2, np.cos(angles), np.sin(angles)).astype(np.float32)
                value = value + self.backend.array(encoding)
            return value
        return self._input(inputs)

    def _temporal(self, value, cell, node, parameters, initialize):
        b, mode = self.backend, self.policy.temporal
        if value.ndim != 3 or mode == 'prefix':
            return OPERATORS['sequence'](b, value, value)
        width, length = value.shape[-1], value.shape[1]
        prefix = f'cell.{cell.parameter_id}.{node.id}.temporal'

        def param(name, shape, constant=None):
            return self._parameter(f'{prefix}.{name}', shape, parameters, initialize,
                                   node.projection_seed, constant=constant)

        outputs = []
        if mode in ('attention', 'hybrid'):
            q, k, v = (value @ param(name, (width, width)) for name in ('q', 'k', 'v'))
            scores = (q @ k.transpose((0, 2, 1))) / np.sqrt(width)
            lag = np.arange(length)[:, None] - np.arange(length)[None, :]
            if self.policy.position == 'relative':
                bias = param('relative_bias', (length,), 0.)
                scores = scores + b.gather(bias, np.maximum(lag, 0))
            scores = scores + b.array(np.where(lag >= 0, 0., -1e9).astype(np.float32))
            outputs.append((b.softmax(scores) @ v) @ param('out', (width, width)))
        if mode in ('dilated', 'hybrid'):
            lags = [0] + [2 ** power for power in range((length - 1).bit_length()) if 2 ** power < length]
            kernel = param('kernel', (len(lags), width))
            mixed = value * kernel[0]
            for index, lag in enumerate(lags[1:], 1):
                zero = b.array(np.zeros((value.shape[0], lag, width), dtype=np.float32))
                shifted = b.concatenate([zero, value[:, :-lag, :]], axis=1)
                mixed = mixed + shifted * kernel[index]
            outputs.append(mixed @ param('conv_out', (width, width)))
        if len(outputs) == 2:
            gate = b.sigmoid(param('hybrid_gate', (width,), 0.))
            return gate * outputs[0] + (1 - gate) * outputs[1]
        return outputs[0]

    def _merge(self, parents, cell, node, parameters, initialize, *, macro=False):
        if len(parents) == 1 and macro:
            return parents[0]
        values = [self._project(parent, node.width, cell, node, parameters, initialize, merge=macro)
                  for parent in parents]
        if self.policy.merge == 'mean' or len(values) == 1:
            return sum(values) / len(values)
        key = f'cell.{cell.parameter_id}.{node.id}.merge_{"macro" if macro else "cell"}.{len(values)}'
        logits = self._parameter(key, (len(values),), parameters, initialize, node.projection_seed, constant=0.)
        weights = self.backend.softmax(logits)
        return sum(value * weights[i] for i, value in enumerate(values))

    def _graph(self, parameters, inputs, *, initialize=False):
        b = self.backend
        x = self._tokens(inputs, parameters, initialize)
        values = {}
        for name in self.ordered:
            cell = self.executors[name]
            parents = [values[parent] for parent in self.incoming[name]] or [x]
            source = self._merge(parents, cell, cell.nodes[0], parameters, initialize, macro=True)
            ordered, incoming, _ = order(cell.nodes, cell.edges, cell.output)
            nodes, local = {node.id: node for node in cell.nodes}, {}
            for identity in ordered:
                node = nodes[identity]
                inputs_here = [local[parent] for parent in incoming[identity]] or [source]
                merged = self._merge(inputs_here, cell, node, parameters, initialize)
                normalized = self._rms(merged) if self.policy.cell_normalization == 'rms' else merged
                activated = b.activate(normalized, node.activation)
                value = (self._temporal(activated, cell, node, parameters, initialize) if node.primitive == 'sequence'
                         else OPERATORS[node.primitive](b, activated, normalized))
                if self.policy.residual_mode == 'gated':
                    key = f'cell.{cell.parameter_id}.{node.id}.residual_gate'
                    gate = b.sigmoid(self._parameter(key, (node.width,), parameters, initialize,
                                                    node.projection_seed, constant=-2.))
                    skip = sum(parent if parent.shape[-1] == node.width else
                               self._project(parent, node.width, cell, node, parameters, initialize)
                               for parent in inputs_here) / len(inputs_here)
                    value = skip + gate * value
                elif self.policy.residual:
                    skip = sum(parent if parent.shape[-1] == node.width else
                               self._project(parent, node.width, cell, node, parameters, initialize)
                               for parent in inputs_here) / len(inputs_here)
                    value = (value + skip) * (2 ** -.5)
                local[identity] = value
            values[name] = local[cell.output]
        if self.policy.readout == 'all':
            return b.concatenate([values[name] for name in self.ordered])
        if self.policy.readout == 'input_final':
            return b.concatenate([x, values[self.genome.output]])
        return values[self.genome.output]

    def representation_signature(self, remapping=None):
        remapping = remapping or {}

        def binding(key):
            return [remapping[key] if key in remapping else key, self.parameter_signatures[key]]

        def projection(parent, cell, node, macro=False):
            label = 'macro_merge' if macro else node.id
            key = f'cell.{cell.parameter_id}.{label}.{parent[1]}.{node.width}'
            return digest(['projection', parent[0], binding(key)])

        def merge(parents, cell, node, macro=False):
            if len(parents) == 1 and macro:
                return parents[0]
            parts = [projection(parent, cell, node, macro) for parent in parents]
            weights = None
            if self.policy.merge == 'learned' and len(parts) > 1:
                key = f'cell.{cell.parameter_id}.{node.id}.merge_{"macro" if macro else "cell"}.{len(parts)}'
                weights = binding(key)
            return digest(['merge', parts, weights]), node.width

        width = (self.policy.embedding_width or self.output_dim) if self.token_input else int(np.prod(self.input_shape))
        embedding = binding('input.embedding') if self.token_input and self.policy.embedding_width else None
        x = digest(['input', self.input_shape, self.output_dim, self.task, embedding, self.policy.position]), width
        values = {}
        for name in self.ordered:
            cell = self.executors[name]
            parents = [values[parent] for parent in self.incoming[name]] or [x]
            source = merge(parents, cell, cell.nodes[0], True)
            ordered, incoming, _ = order(cell.nodes, cell.edges, cell.output)
            nodes, local = {n.id: n for n in cell.nodes}, {}
            for identity in ordered:
                node = nodes[identity]
                inputs = [local[parent] for parent in incoming[identity]] or [source]
                merged = merge(inputs, cell, node)
                prefix = f'cell.{cell.parameter_id}.{node.id}.temporal.'
                temporal = [binding(key) for key in sorted(self.parameter_signatures) if key.startswith(prefix)]
                skip, gate = [], None
                if self.policy.residual_mode == 'gated' or self.policy.residual:
                    skip = [parent[0] if parent[1] == node.width else projection(parent, cell, node) for parent in inputs]
                    if self.policy.residual_mode == 'gated':
                        gate = binding(f'cell.{cell.parameter_id}.{node.id}.residual_gate')
                local[identity] = (digest([merged, node.activation, node.primitive, temporal, skip, gate]), node.width)
            values[name] = local[cell.output]
        outputs = ([values[name] for name in self.ordered] if self.policy.readout == 'all' else
                   [x, values[self.genome.output]] if self.policy.readout == 'input_final' else [values[self.genome.output]])
        fields = ('temporal', 'position', 'cell_normalization', 'residual_mode',
                  'merge', 'readout_skip', 'normalization', 'head_width')
        policy = self.policy.model_dump()
        return digest(['v3', outputs, {key: policy[key] for key in fields}])

    def forward(self, parameters, inputs, *, training=False, seed=0):
        b = self.backend
        features = self._normalize(self._graph(parameters, b.numpy(inputs)))
        if training and self.policy.dropout:
            rng = np.random.default_rng(seed)
            keep = 1 - self.policy.dropout
            features = features * b.array((rng.random(features.shape) < keep).astype(np.float32) / keep)
        hidden = b.activate(features @ parameters['head.w'] + parameters['head.b'], 'gelu')
        logits = hidden @ parameters['readout.w'] + parameters['readout.b']
        if self.policy.readout_skip:
            logits = logits + features @ parameters['skip.w']
        return logits
