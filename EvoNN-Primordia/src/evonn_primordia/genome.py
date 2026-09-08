"""Bounded tiny circuits; every primitive and merge has an executable meaning."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from evonn_shared.canonical import canonical_sha256


class Primitive(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    operator: Literal['dense', 'gate', 'sparse', 'residual'] = 'dense'
    activation: Literal['relu', 'tanh', 'gelu', 'silu'] = 'tanh'
    merge: Literal['replace', 'mean', 'product'] = 'replace'


class PrimitiveGenome(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, allow_inf_nan=False)
    width: int = Field(default=8, ge=2, le=24, strict=True)
    primitives: tuple[Primitive, ...] = Field(min_length=1, max_length=4)
    learning_rate: float = Field(default=.006, gt=0, le=.1)
    weight_decay: float = Field(default=.001, ge=0, le=.1)

    @property
    def genome_id(self):
        return canonical_sha256(self.model_dump(mode='json'), schema_version='primordia.primitive/v1', digest_field=None)

    @property
    def family(self):
        return '+'.join(sorted({p.operator for p in self.primitives}))


def caps(task, modality, slot=0):
    expensive = task == 'language_modeling' or modality == 'image'
    return dict(width=12 if expensive else 24, depth=2 if expensive else 4,
                epochs=min(4 if expensive else 8, 3 if slot >= 16 else 1000))


def clamp(genome, task, modality):
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
