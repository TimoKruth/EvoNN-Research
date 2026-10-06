"""Opt-in proposal operators for the September 2026 Prism experiments.

No benchmark IDs or observed winning genomes are encoded here. Every family
keeps a protected rotation; local proposals supplement the broad search space.
"""

import math

from .genome import ModelGenome, GROUPS, changed, mutate


def representation_gene(genome):
    genes = {"mlp": "input_skip", "conv2d": "readout", "attention": "pre_norm"}
    group = GROUPS[genome.family]
    return genes[group] if group in genes else None


def represent(genome, *, toggle=False):
    """Change only the new architecture gene, retaining the old seed envelope."""
    field = representation_gene(genome)
    if field == "input_skip":
        return changed(genome, input_skip=not genome.input_skip if toggle else True)
    if field == "readout":
        return changed(genome, readout="mean" if toggle and genome.readout != "mean" else "spatial_pyramid")
    if field == "pre_norm":
        enabled = not genome.pre_norm if toggle else True
        norm = genome.norm_type if not enabled or genome.norm_type in {"layer", "rms"} else "layer"
        return changed(genome, pre_norm=enabled, norm_type=norm)
    return genome


def founder(family, rng, *, representation=False):
    """Independent, varied training and depth settings, within existing bounds."""
    values = dict(family=family, hidden_layers=(rng.choice((16, 32, 64)),) * rng.choice((1, 2, 3)),
                  activation=rng.choice(("relu", "gelu", "silu")),
                  learning_rate=rng.choice((.001, .003, .006)),
                  weight_decay=rng.choice((0., .001, .01)),
                  norm_type=rng.choice(("none", "layer", "rms")))
    if family == "composite":
        values["blocks"] = rng.choice((
            [{"kind": "dense"}, {"kind": "gated", "skip_from": 0}],
            [{"kind": "attention"}, {"kind": "conv1d", "skip_from": 0}],
            [{"kind": "state_space"}, {"kind": "attention", "skip_from": 0}],
        ))
    genome = ModelGenome(**values)
    return represent(genome) if representation else genome


def refine(genome, rng, allowed, *, task, representation, stats):
    """Benchmark/family-conditioned local steps, retaining a nonzero operator floor."""
    operators = ["lr", "weight_decay", "dropout", "activation", "depth", "norm"]
    operators.append("embedding" if genome.family == "composite" else "width")
    if representation:
        if GROUPS[genome.family] == "mlp":
            operators.append("input_skip")
        elif GROUPS[genome.family] == "conv2d":
            operators.append("readout")
        elif GROUPS[genome.family] == "attention":
            operators.append("pre_norm")
    # Composite hidden_layers is inactive. Its depth is changed through block edits.
    if genome.family == "composite":
        operators.remove("depth")
        operators += ["block_add", "block_remove", "block_kind", "block_rewire"]
    weights = [.25 + (stats["local_" + op] if "local_" + op in stats else {}).get("ema", .5) for op in operators]
    operator = rng.choices(operators, weights=weights, k=1)[0]
    values = {}
    if operator == "lr":
        values["learning_rate"] = min(.1, max(1e-5, genome.learning_rate * rng.choice((.5, .8, 1.25, 2))))
    elif operator == "weight_decay":
        values["weight_decay"] = rng.choice((0., .0001, .001, .003, .01, .03, .1))
    elif operator == "dropout":
        values["dropout"] = min(.3, max(0., genome.dropout + rng.choice((-.05, .05, .1))))
    elif operator == "width":
        widths = list(genome.hidden_layers)
        index = rng.randrange(len(widths))
        widths[index] = min(256, max(4, int(widths[index] * rng.choice((.5, .75, 1.25, 1.5)))))
        values["hidden_layers"] = widths
    elif operator == "embedding":
        multiple = genome.num_heads * (2 if genome.position_encoding == "rope" else 1)
        width = genome.embedding_dim * rng.choice((.5, .75, 1.25, 1.5))
        values["embedding_dim"] = min(256, max(multiple, math.ceil(width / multiple) * multiple, 4))
    elif operator == "input_skip":
        values["input_skip"] = not genome.input_skip
    elif operator == "readout":
        values["readout"] = "mean" if genome.readout == "spatial_pyramid" else "spatial_pyramid"
    elif operator == "pre_norm":
        values.update(pre_norm=not genome.pre_norm)
        if values["pre_norm"] and genome.norm_type not in {"layer", "rms"}:
            values["norm_type"] = "layer"
    else:
        child, actual = mutate(genome, rng, allowed, operator=operator, task=task, broad=True, family_locked=True)
        return child, "local_" + actual
    child = changed(genome, **values)
    if child == genome:
        child, operator = mutate(genome, rng, allowed, operator="lr", task=task, broad=True, family_locked=True)
    return child, "local_" + operator
