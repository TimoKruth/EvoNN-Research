"""Versioned variation registry with explicit applicability and actual effects."""

from copy import deepcopy
import math
from .genome import OPERATORS, ExpertGene, GateConfig, ConvLayerGene
from .genome_v2 import GenomeV2, LayerV2, ConnectionV2


def execution_topology(genome):
    active = {n.innovation for n in genome.active_layers()}
    return (
        tuple(sorted(active)),
        tuple(
            sorted(
                (e.source, e.target)
                for e in genome.connections
                if e.enabled and e.target in active and (e.source == -1 or e.source in active)
            )
        ),
    )


CORE = (
    "split",
    "skip",
    "branch",
    "disable_edge",
    "enable_edge",
    "disable_node",
    "enable_node",
    "operator",
    "width",
    "precision",
    "activation",
    "lr",
)
BROAD = (
    "sparsity",
    "heads",
    "activation_precision",
    "normalization",
    "merge",
    "experts",
    "gate",
    "convolution",
    "weight_decay",
    "adapter",
    "adapter_width",
    "adapter_heads",
    "widen",
)


def adapters(definition):
    options = ["flat"]
    if definition.task_kind.value == "language_modeling" and definition.input_modality.value == "text":
        options.append("token_attention")
    if definition.input_modality.value == "image" and len(definition.input_shape) == 2:
        options.append("spatial")
    return options


def widths(node, broad=True):
    values = range(4, 257) if broad else (8, 16, 32, 64)
    return [
        w
        for w in values
        if w != node.width
        and (node.operator != "spatial" or math.isqrt(w) ** 2 == w)
        and (node.operator not in ("attention_lite", "transformer_lite") or w % (4 * node.heads) == 0)
    ]


def edit(genome, rng, innovations, operator, definition, *, broad=False):
    """Return None when inapplicable. Never relabel an LR change as a structural edit."""
    data = deepcopy(genome.model_dump(mode="json"))
    nodes, edges = data["layers"], data["connections"]
    active = {n.innovation for n in genome.active_layers()}
    live = [n for n in nodes if n["innovation"] in active]
    preservation = None

    def field(name, values, candidates=live):
        choices = [(n, v) for n in candidates for v in values(n) if n[name] != v]
        if not choices:
            return False
        n, value = rng.choice(choices)
        n[name] = value
        return True

    def toggle(collection, enabling, valid=None):
        choices = []
        for i, item in enumerate(collection):
            if item["enabled"] == enabling or (valid and not valid(item)):
                continue
            item["enabled"] = enabling
            try:
                candidate = GenomeV2.model_validate(data)
                if execution_topology(candidate) != execution_topology(genome):
                    choices.append(i)
            except ValueError:
                pass
            item["enabled"] = not enabling
        if not choices:
            return False
        collection[rng.choice(choices)]["enabled"] = enabling
        return True

    if operator in ("split", "branch"):
        if len(nodes) >= 32 or len(edges) > 126:
            return None
        available = [
            e for e in edges if e["enabled"] and e["target"] in active and (e["source"] == -1 or e["source"] in active)
        ]
        edge = rng.choice(available)
        target = next(n for n in nodes if n["innovation"] == edge["target"])
        orders = {n["innovation"]: n["order"] for n in nodes}
        before = orders[edge["source"]] if edge["source"] != -1 else min(orders.values()) - 1
        identity = innovations.obtain(f"v2:{operator}:{edge['innovation']}:{genome.genome_id}")
        nodes.append(
            LayerV2(innovation=identity, order=(before + target["order"]) / 2, width=target["width"]).model_dump()
        )
        if operator == "split":
            edge["enabled"] = False
        else:
            target["merge_reference_count"] = target["merge_reference_count"] or sum(
                e["enabled"] and e["target"] == target["innovation"] for e in edges
            )
            preservation = "zero_gated_branch"
        for suffix, source, dest in (("in", edge["source"], identity), ("out", identity, edge["target"])):
            edges.append(
                ConnectionV2(
                    innovation=innovations.obtain(f"v2:{identity}:{suffix}"),
                    source=source,
                    target=dest,
                    scale=0 if operator == "branch" and suffix == "out" else 1,
                    trainable_scale=operator == "branch" and suffix == "out",
                ).model_dump()
            )
    elif operator == "skip":
        pairs = {(e["source"], e["target"]) for e in edges}
        choices = [
            (s, n["innovation"])
            for n in live
            for s in [-1, *[v["innovation"] for v in live if v["order"] < n["order"]]]
            if (s, n["innovation"]) not in pairs
        ]
        if not choices or len(edges) >= 128:
            return None
        source, target = rng.choice(choices)
        edges.append(
            ConnectionV2(
                innovation=innovations.obtain(f"v2:edge:{source}:{target}"), source=source, target=target
            ).model_dump()
        )
    elif operator in ("enable_edge", "disable_edge"):
        if not toggle(edges, operator == "enable_edge"):
            return None
    elif operator in ("enable_node", "disable_node"):
        if not toggle(nodes, operator == "enable_node", lambda n: n["innovation"] != genome.output):
            return None
    elif operator == "operator":
        node = rng.choice(live)
        node["operator"] = rng.choice([op for op in OPERATORS if op != node["operator"]])
        if node["operator"] in ("spatial", "attention_lite", "transformer_lite"):
            node.update(width=16, heads=1)
        data["convolutions"] = [c for c in data["convolutions"] if c["layer"] != node["innovation"]]
    elif operator in ("width", "widen"):
        candidates = (
            live
            if operator == "width"
            else [
                n
                for n in live
                if n["operator"] == "dense"
                and n["normalization"] == "none"
                and n["weight_bits"] == 16
                and n["activation_bits"] == 32
            ]
        )
        if not field(
            "width",
            lambda n: [w for w in widths(LayerV2.model_validate(n), broad) if operator != "widen" or w > n["width"]],
            candidates,
        ):
            return None
        preservation = "zero_pad_widen" if operator == "widen" else None
    elif operator == "precision":
        field("weight_bits", lambda n: (1.58, 4, 8, 16))
    elif operator == "activation":
        field(
            "activation",
            lambda n: ("relu", "gelu", "tanh", "silu", "identity") if broad else ("relu", "gelu", "tanh", "silu"),
        )
    elif operator == "sparsity":
        if not field(
            "sparsity", lambda n: (0, 0.1, 0.25, 0.5, 0.75, 0.9), [n for n in live if n["operator"] == "sparse_dense"]
        ):
            return None
    elif operator == "heads":
        if not field(
            "heads",
            lambda n: [h for h in (1, 2, 4) if n["width"] % (4 * h) == 0],
            [n for n in live if n["operator"] in ("attention_lite", "transformer_lite")],
        ):
            return None
    elif operator == "activation_precision":
        field("activation_bits", lambda n: (8, 16, 32))
    elif operator == "normalization":
        field("normalization", lambda n: ("layer", "rms", "none"))
    elif operator == "merge":
        node = rng.choice(live)
        node.update(
            merge=rng.choice([m for m in ("sqrt_sum", "sum", "mean") if m != node["merge"]]), merge_reference_count=None
        )
    elif operator == "experts":
        choices = ["add"] if not data["experts"] else ["add", "remove", "width"]
        choice = rng.choice(choices)
        if choice == "add":
            # This is the existing graph's finite resource envelope, not a quality exclusion.
            if len(data["experts"]) >= 8:
                return None
            identity = innovations.obtain(f"v2:expert:{genome.genome_id}")
            data["experts"].append(ExpertGene(innovation=identity, width=rng.randint(4, 256)).model_dump())
            data["gate"] = data["gate"] or GateConfig().model_dump()
        elif choice == "remove":
            data["experts"].pop(rng.randrange(len(data["experts"])))
            if not data["experts"]:
                data["gate"] = None
            else:
                data["gate"]["top_k"] = min(data["gate"]["top_k"], len(data["experts"]))
        else:
            expert = rng.choice(data["experts"])
            expert["width"] = rng.choice([v for v in range(4, 257) if v != expert["width"]])
    elif operator == "gate":
        if not data["gate"]:
            return None
        choices = [("temperature", t) for t in (0.25, 0.5, 1, 2, 5, 10) if t != data["gate"]["temperature"]]
        choices += [("top_k", k) for k in (1, 2) if k <= len(data["experts"]) and k != data["gate"]["top_k"]]
        key, value = rng.choice(choices)
        data["gate"][key] = value
    elif operator == "convolution":
        candidates = [n for n in live if n["operator"] == "spatial"]
        if not candidates:
            return None
        node = rng.choice(candidates)
        previous = next((c for c in data["convolutions"] if c["layer"] == node["innovation"]), None)
        data["convolutions"] = [c for c in data["convolutions"] if c["layer"] != node["innovation"]]
        data["convolutions"].append(
            ConvLayerGene(
                layer=node["innovation"], kernel_size=3 if previous and previous["kernel_size"] == 5 else 5
            ).model_dump()
        )
    elif operator == "adapter":
        choices = [v for v in adapters(definition) if v != genome.input_adapter]
        if not choices:
            return None
        data["input_adapter"] = rng.choice(choices)
    elif operator in ("adapter_width", "adapter_heads"):
        if genome.input_adapter == "flat" or (
            operator == "adapter_heads" and genome.input_adapter != "token_attention"
        ):
            return None
        name = operator
        choices = range(4, 257) if name == "adapter_width" else (1, 2, 4)
        choices = [
            v
            for v in choices
            if v != data[name]
            and (v % data["adapter_heads"] == 0 if name == "adapter_width" else data["adapter_width"] % v == 0)
        ]
        if not choices:
            return None
        data[name] = rng.choice(choices)
    elif operator in ("lr", "weight_decay"):
        key = "learning_rate" if operator == "lr" else "weight_decay"
        values = (1e-5, 0.0001, 0.001, 0.003, 0.01, 0.03, 0.1) if operator == "lr" else (0, 0.0001, 0.001, 0.01, 0.1)
        data[key] = rng.choice([v for v in values if v != data[key]])
    else:
        raise ValueError("unregistered mutation")
    try:
        child = GenomeV2.model_validate(data)
    except ValueError:
        return None
    if child.genome_id == genome.genome_id:
        return None
    return child, {
        "requested": operator,
        "actual": operator,
        "topology_changed": execution_topology(child) != execution_topology(genome),
        "preservation": preservation,
    }


def crossover(a, b, rng, innovations):
    """Import a complete compatible donor branch, without losing the primary backbone."""
    if a.genome_id == b.genome_id:
        return a, "self"
    donor = b.active_layers()
    if len(a.layers) + len(donor) > 32:
        return a, "node_limit"
    data = a.model_dump(mode="json")
    mapping = {n.innovation: innovations.obtain(f"v2:cross:{a.genome_id}:{b.genome_id}:{n.innovation}") for n in donor}
    output_order = next(n.order for n in a.layers if n.innovation == a.output)
    for i, node in enumerate(donor):
        data["layers"].append(
            {
                **node.model_dump(),
                "innovation": mapping[node.innovation],
                "order": output_order - 1 + (i + 1) / (len(donor) + 1),
            }
        )
    for edge in b.connections:
        if not edge.enabled or edge.target not in mapping or (edge.source != -1 and edge.source not in mapping):
            continue
        source = -1 if edge.source == -1 else mapping[edge.source]
        target = mapping[edge.target]
        data["connections"].append(
            {
                **edge.model_dump(),
                "innovation": innovations.obtain(f"v2:cross_edge:{source}:{target}"),
                "source": source,
                "target": target,
            }
        )
    source = mapping[b.output]
    data["connections"].append(
        ConnectionV2(
            innovation=innovations.obtain(f"v2:cross_out:{source}:{a.output}"), source=source, target=a.output
        ).model_dump()
    )
    data["convolutions"] += [
        {**c.model_dump(), "layer": mapping[c.layer]} for c in b.convolutions if c.layer in mapping
    ]
    try:
        return GenomeV2.model_validate(data), "branch_import"
    except ValueError:
        return a, "incompatible"


def reachability_catalog():
    return {
        "version": "topograph.variation/v2",
        "registered": list(CORE + BROAD),
        "reserved": {
            "convolution.depthwise": "single-channel latent spatial operator; no distinct depthwise semantics"
        },
        "resource_limits": {"layers": 32, "connections": 128, "width": 256, "experts": 8},
        "future_primitives": "Add a versioned gene, executor, mutation registration and semantic/replay tests; no quality blacklist.",
    }
