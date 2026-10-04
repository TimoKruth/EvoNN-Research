"""Opt-in representation proposals; every choice is frozen in the genome."""
from .genome import Primitive, PrimitiveGenome, fresh_genome, mutate_broad
from evonn_shared.primordia_policy import uses_v3, portfolio_families


def admits_v3(policy, definition):
    return uses_v3(policy, definition.task_kind.value, definition.input_modality.value)


def _pin_family(genome, policy, definition):
    data = genome.model_dump()
    if admits_v3(policy, definition):
        if policy in {"attention_v3", "convolution_v3", "multiscale_v3"}:
            data['temporal_mode'] = policy.removesuffix('_v3')
        elif policy in {"conv_flat_v3", "conv_pool_v3"}:
            data['spatial_mode'] = policy.removesuffix('_v3')
        elif policy == 'portfolio_v4':
            families = portfolio_families(definition.task_kind.value, definition.input_modality.value)
            field = 'temporal_mode' if definition.task_kind.value == 'language_modeling' else 'spatial_mode'
            if data[field] not in families:
                data[field] = families[0]
    return PrimitiveGenome.model_validate(data)


def fresh_research(rng, definition, policy, *, max_width, max_depth, founder=None, portfolio_index=None):
    genome = fresh_genome(rng, max_width=max_width, max_depth=max_depth, founder=founder)
    if not admits_v3(policy, definition):
        return genome
    index = rng.randrange(4) if founder is None else founder
    data = genome.model_dump()
    data.update(version=3, width=min(max_width, (16, 24, 32, 48)[index % 4]),
                primitives=tuple(Primitive(operator="residual" if i % 2 == 0 else "gate", activation="gelu")
                                 for i in range(min(max_depth, 1 + index % 3))),
                normalization="rms", readout="skip" if index % 2 else "last",
                dropout=0. if founder is not None else rng.choice([0., .1, .2]),
                temporal_mode="prefix_mean", temporal_lag=1)
    if founder is None and rng.random() < .25:
        data.update(width=genome.width, primitives=genome.primitives)
    if definition.task_kind.value == "language_modeling":
        data.update(temporal_mode=("attention", "convolution", "multiscale", "lag")[index % 4],
                    temporal_dilation=rng.choice([1, 2, 4, 8]), temporal_lag=rng.randint(1, 32))
    if definition.input_modality.value == "image":
        data["spatial_mode"] = ("conv_flat", "conv_pool", "flatten", "conv_pool")[index % 4]
    if policy == 'portfolio_v4':
        families = portfolio_families(definition.task_kind.value, definition.input_modality.value)
        field = 'temporal_mode' if definition.task_kind.value == 'language_modeling' else 'spatial_mode'
        slot = index if portfolio_index is None else portfolio_index
        data[field] = families[slot % len(families)]
    return _pin_family(PrimitiveGenome.model_validate(data), policy, definition)


def mutate_research(genome, rng, definition, policy, *, max_width, max_depth):
    if not admits_v3(policy, definition) or rng.random() < .55:
        child, operation = mutate_broad(genome, rng, max_width=max_width, max_depth=max_depth)
        return _pin_family(child, policy, definition), operation
    choices = dict(normalization=["none", "rms"], readout=["last", "skip"], dropout=[0., .1, .2])
    if definition.task_kind.value == "language_modeling":
        choices.update(temporal_mode=["prefix_mean", "lag", "attention", "convolution", "multiscale"],
                       temporal_dilation=[1, 2, 4, 8, 16, 32])
    if definition.input_modality.value == "image":
        choices["spatial_mode"] = ["flatten", "conv_flat", "conv_pool"]
    if policy == 'portfolio_v4':
        field = 'temporal_mode' if definition.task_kind.value == 'language_modeling' else 'spatial_mode'
        choices[field] = list(portfolio_families(definition.task_kind.value, definition.input_modality.value))
    key = rng.choice(list(choices))
    data = genome.model_dump()
    data.update(version=3)
    data[key] = rng.choice([value for value in choices[key] if value != genome.model_dump()[key]])
    return _pin_family(PrimitiveGenome.model_validate(data), policy, definition), key


def recombine(left, right, rng):
    """Exchange primitive functions while retaining the recipient's valid graph."""
    data = left.model_dump()
    nodes = list(left.primitives)
    index = rng.randrange(len(nodes))
    nodes[index] = rng.choice(right.primitives)
    data['primitives'] = tuple(nodes)
    return PrimitiveGenome.model_validate(data)
