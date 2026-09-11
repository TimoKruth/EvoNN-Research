"""Bounded tiny circuits; every primitive and merge has an executable meaning."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_serializer, model_validator
from evonn_shared.canonical import canonical_sha256


class Primitive(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    operator: Literal['dense', 'gate', 'sparse', 'residual', 'identity'] = 'dense'
    activation: Literal['relu', 'tanh', 'gelu', 'silu'] = 'tanh'
    merge: Literal['replace', 'mean', 'product'] = 'replace'


class PrimitiveGenome(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    width: int = Field(default=8, ge=2, le=256, strict=True)
    primitives: tuple[Primitive, ...] = Field(min_length=1, max_length=32)
    learning_rate: float = Field(default=.006, gt=0, le=.1)
    weight_decay: float = Field(default=.001, ge=0, le=.1)
    version: Literal[1, 2] = 1
    # Node i consumes earlier states 0..i; state 0 is the input projection.
    # Empty wiring means the original sequential circuit. Reusing a state
    # fans out the same computed subcircuit, without copying its weights.
    sources: tuple[tuple[StrictInt, ...], ...] = ()
    sparse_offsets: tuple[StrictInt, ...] = (0, 1)
    temporal_mode: Literal['prefix_mean', 'lag'] = 'prefix_mean'
    temporal_lag: int = Field(default=1, ge=1, le=32, strict=True)

    @model_validator(mode='before')
    @classmethod
    def strict_version(cls, value):
        if isinstance(value, dict) and 'version' in value and type(value['version']) is not int:
            raise ValueError('genome version must be an integer')
        return value

    @model_validator(mode='after')
    def validate_structure(self):
        if self.version == 1:
            if (self.width > 24 or len(self.primitives) > 4 or self.sources
                    or self.sparse_offsets != (0, 1) or self.temporal_mode != 'prefix_mean'
                    or self.temporal_lag != 1 or any(p.operator == 'identity' for p in self.primitives)):
                raise ValueError('v1 genome cannot encode v2 features')
        if self.sources:
            if len(self.sources) != len(self.primitives):
                raise ValueError('one source list required per primitive')
            for i, refs in enumerate(self.sources):
                if (not refs or len(set(refs)) != len(refs)
                        or any(type(r) is not int or not 0 <= r <= i for r in refs)):
                    raise ValueError('sources must be unique earlier states; cycles are forbidden')
            reachable = {len(self.primitives)}
            for i in reversed(range(len(self.primitives))):
                if i + 1 in reachable:
                    reachable.update(self.sources[i])
            if reachable != set(range(len(self.primitives) + 1)):
                raise ValueError('all primitives must reach the output')
        if (not self.sparse_offsets or len(self.sparse_offsets) > 256
                or len(set(self.sparse_offsets)) != len(self.sparse_offsets)
                or any(type(v) is not int or not 0 <= v < 256 for v in self.sparse_offsets)):
            raise ValueError('sparse offsets must be unique integers in [0,256)')
        return self

    @model_serializer(mode='wrap')
    def serialize(self, handler):
        data = handler(self)
        if self.version == 1:
            for key in ('version', 'sources', 'sparse_offsets', 'temporal_mode', 'temporal_lag'):
                if key in data:
                    del data[key]
        return data

    @property
    def genome_id(self):
        return canonical_sha256(self.model_dump(mode='json'), schema_version=self.encoding, digest_field=None)

    @property
    def encoding(self):
        return f'primordia.primitive/v{self.version}'

    @property
    def family(self):
        return '+'.join(sorted({p.operator for p in self.primitives}))


def caps(task, modality, slot=0):
    expensive = task == 'language_modeling' or modality == 'image'
    return dict(width=12 if expensive else 24, depth=2 if expensive else 4,
                epochs=min(4 if expensive else 8, 3 if slot >= 16 else 1000))


def clamp(genome, task, modality):
    if genome.version == 2:
        return genome
    limit = caps(task, modality)
    return PrimitiveGenome.model_validate({**genome.model_dump(), 'width': min(genome.width, limit['width']),
                                          'primitives': genome.primitives[:limit['depth']]})


def seed_genome(index, task, modality):
    operator = ('dense', 'gate', 'sparse', 'residual')[index % 4]
    return clamp(PrimitiveGenome(width=4 + 2 * (index % 5), primitives=(Primitive(operator=operator),)), task, modality)


def mutate(genome, rng, *, task, modality, cheap=False):
    data = genome.model_dump()
    nodes = list(genome.primitives)
    if cheap:
        data['width'] = max(2, genome.width // 2)
        nodes = nodes[:max(1, len(nodes) - 1)]
        operation = 'cheapen'
    else:
        operation = rng.choice(['operator', 'activation', 'merge', 'width', 'grow', 'prune'])
        index = rng.randrange(len(nodes))
        if operation in ('operator', 'activation', 'merge'):
            choices = {'operator': ['dense', 'gate', 'sparse', 'residual'],
                       'activation': ['relu', 'tanh', 'gelu', 'silu'], 'merge': ['replace', 'mean', 'product']}
            nodes[index] = Primitive.model_validate({**nodes[index].model_dump(), operation: rng.choice(choices[operation])})
        elif operation == 'width':
            data['width'] = max(2, min(24, genome.width + rng.choice([-2, 2])))
        elif operation == 'grow' and len(nodes) < 4:
            nodes.append(Primitive(operator=rng.choice(['dense', 'gate', 'sparse', 'residual'])))
        elif operation == 'prune' and len(nodes) > 1:
            del nodes[-1]
    data['primitives'] = tuple(nodes)
    data['learning_rate'] = min(.03, max(.0005, genome.learning_rate * rng.uniform(.8, 1.2)))
    return clamp(PrimitiveGenome.model_validate(data), task, modality), operation


def fresh_genome(rng, *, max_width=48, max_depth=8, founder=None):
    """Broad restart distribution; every admitted width/depth has positive support."""
    operators = ['dense', 'gate', 'sparse', 'residual']
    width = rng.randint(2, max_width) if rng.random() < .25 else rng.randint(2, min(12, max_width))
    depth = rng.randint(1, max_depth) if rng.random() < .25 else 1
    nodes = tuple(Primitive(operator=rng.choice(operators), activation=rng.choice(['tanh', 'relu', 'gelu', 'silu']))
                  for _ in range(depth))
    if founder is not None:
        width, nodes = min(max_width, 4 + 2 * (founder % 5)), (Primitive(operator=operators[founder % 4]),)
    return PrimitiveGenome(version=2, width=width, primitives=nodes,
                           learning_rate=10 ** rng.uniform(-3.3, -1.6),
                           weight_decay=rng.choice([0., .0001, .001, .01]),
                           temporal_mode=rng.choice(['prefix_mean', 'lag']), temporal_lag=rng.randint(1, 8))


BREADTH_OPERATORS = ('operator', 'activation', 'merge', 'width', 'grow', 'prune', 'cheapen',
                     'rewire', 'sparsity', 'temporal', 'motif', 'hyperparameter')


def mutate_broad(genome, rng, *, max_width=48, max_depth=8, operation=None):
    """No score-based operator veto; bounded envelopes are explicit run settings."""
    operation = operation or rng.choice(BREADTH_OPERATORS)
    if operation not in BREADTH_OPERATORS:
        raise ValueError('unknown breadth mutation')
    data = genome.model_dump()
    data['version'] = 2
    nodes = list(genome.primitives)
    sources = list(genome.sources or tuple((i,) for i in range(len(nodes))))
    index = rng.randrange(len(nodes))
    if operation in ('operator', 'activation', 'merge'):
        choices = {'operator': ['dense', 'gate', 'sparse', 'residual', 'identity'],
                   'activation': ['relu', 'tanh', 'gelu', 'silu'], 'merge': ['replace', 'mean', 'product']}
        old = nodes[index].model_dump()[operation]
        nodes[index] = Primitive.model_validate({**nodes[index].model_dump(),
                                                 operation: rng.choice([v for v in choices[operation] if v != old])})
    elif operation == 'width':
        data['width'] = rng.choice([w for w in range(2, max_width + 1) if w != genome.width]) if max_width > 2 else 2
    elif operation == 'grow' and len(nodes) < max_depth:
        # Identity insertion preserves the complete function with inherited weights.
        nodes.append(Primitive(operator='identity'))
        sources.append((len(nodes) - 1,))
    elif operation == 'motif' and len(nodes) < max_depth:
        count = rng.randint(1, min(len(nodes), max_depth - len(nodes)))
        end, start = len(nodes), len(nodes) - count
        block = nodes[start:end]
        wiring = sources[start:end]
        nodes.extend(block)
        sources.extend(tuple(ref + count if ref >= start else ref for ref in refs) for refs in wiring)
    elif operation in ('prune', 'cheapen'):
        if operation == 'cheapen':
            data['width'] = max(2, genome.width // 2)
        if len(nodes) > 1:
            nodes = nodes[:-1]
            sources = sources[:-1]
    elif operation == 'rewire' and index > 0:
        sources[index] = tuple(sorted(rng.sample(range(index + 1), rng.randint(1, index + 1))))
    elif operation == 'sparsity':
        offsets = set(genome.sparse_offsets)
        offset = rng.randrange(genome.width)
        offsets.symmetric_difference_update({offset})
        data['sparse_offsets'] = tuple(sorted(offsets or {offset}))
    elif operation == 'temporal':
        data['temporal_mode'] = rng.choice(['prefix_mean', 'lag'])
        data['temporal_lag'] = rng.randint(1, 32)
    else:
        data['weight_decay'] = rng.choice([0., .0001, .001, .01, .1])
    # Keep every retained node executable after rewiring, motif copying or pruning.
    reachable = {len(nodes)}
    for i in reversed(range(len(nodes))):
        if i + 1 in reachable:
            reachable.update(sources[i])
    sources[-1] = tuple(sorted(set(sources[-1]) | (set(range(len(nodes))) - reachable)))
    data['primitives'], data['sources'] = tuple(nodes), tuple(sources)
    data['learning_rate'] = min(.03, max(.0005, genome.learning_rate * rng.uniform(.8, 1.2)))
    return PrimitiveGenome.model_validate(data), operation
