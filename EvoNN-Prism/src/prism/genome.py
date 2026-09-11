"""Deeply immutable content-addressed family genomes and validated variation."""

from random import Random
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from evonn_shared.canonical import canonical_sha256

# Explicit versioned extension boundary: add a constructor in composition.py
# and qualify its shape/gradient/causality semantics before adding a kind here.
BLOCK_KINDS = ("dense", "sparse", "gated", "conv1d", "conv2d", "gru", "attention", "state_space")


class BlockGene(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: str = "dense"
    skip_from: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def known_kind(self):
        if self.kind not in BLOCK_KINDS:
            raise ValueError("unknown composition block")
        return self

FAMILIES = {
    "mlp": ("tabular", "image", "sequence"),
    "sparse_mlp": ("tabular", "image", "sequence"),
    "moe_mlp": ("tabular",),
    "conv2d": ("image",),
    "lite_conv2d": ("image",),
    "conv1d": ("sequence",),
    "lite_conv1d": ("sequence",),
    "gru": ("sequence",),
    "embedding": ("text",),
    "attention": ("text", "sequence"),
    "sparse_attention": ("text", "sequence"),
    "state_space": ("sequence", "text"),
    "sparse_state_space": ("sequence", "text"),
    "gated_state_space": ("sequence", "text"),
    "causal_transformer": ("text", "sequence"),
    "composite": ("tabular", "image", "sequence", "text"),
}
GROUPS = {
    name: group
    for group, names in {
        "mlp": ("mlp", "sparse_mlp", "moe_mlp"),
        "conv2d": ("conv2d", "lite_conv2d"),
        "conv1d": ("conv1d", "lite_conv1d"),
        "attention": ("attention", "sparse_attention", "causal_transformer"),
        "state_space": ("state_space", "sparse_state_space", "gated_state_space"),
        "gru": ("gru",),
        "embedding": ("embedding",),
        "composite": ("composite",),
    }.items()
    for name in names
}


class ModelGenome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    family: str = "mlp"
    hidden_layers: tuple[int, ...] = (16,)
    activation: Literal["relu", "gelu", "tanh", "silu"] = "relu"
    dropout: float = Field(default=0, ge=0, le=0.3)
    residual: bool = False
    activation_sparsity: float = Field(default=0.25, ge=0, lt=1)
    learning_rate: float = Field(default=0.003, ge=1e-5, le=0.1)
    kernel_size: Literal[3, 5] = 3
    embedding_dim: int = Field(default=16, ge=4, le=256)
    num_heads: Literal[1, 2, 4, 8] = 2
    norm_type: Literal["none", "layer", "rms", "batch"] = "layer"
    weight_decay: float = Field(default=0.01, ge=0, le=0.1)
    num_experts: Literal[2, 4, 8] = 2
    moe_top_k: Literal[1, 2] = 1
    position_encoding: Literal["none", "sinusoidal", "rope"] = "sinusoidal"
    kv_heads: Literal[1, 2, 4, 8] = 1
    ffn_ratio: Literal[1, 2, 4] = 2
    blocks: tuple[BlockGene, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def migrate(cls, value):
        if isinstance(value, dict) and value.get("family") == "composite" and "blocks" not in value:
            value = {**value, "blocks": [{"kind": "dense"}, {"kind": "gated", "skip_from": 0}]}
        if isinstance(value, dict) and "layer_norm" in value:
            value = dict(value)
            old = value.pop("layer_norm")
            if type(old) is not bool:
                raise ValueError("legacy layer_norm must be boolean")
            value.setdefault("norm_type", "layer" if old else "none")
        return value

    @model_validator(mode="after")
    def validate_architecture(self):
        if self.family not in FAMILIES or not 1 <= len(self.hidden_layers) <= 6:
            raise ValueError("unknown family or invalid depth")
        if any(type(w) is not int or not 4 <= w <= 256 for w in self.hidden_layers):
            raise ValueError("width must be an integer in [4,256]")
        if self.embedding_dim % self.num_heads or self.num_heads % self.kv_heads:
            raise ValueError("attention head dimensions must divide exactly")
        if self.position_encoding == "rope" and self.embedding_dim // self.num_heads % 2:
            raise ValueError("RoPE requires even head dimension")
        if self.residual and GROUPS[self.family] != "mlp":
            raise ValueError("residual flag applies to MLP families only")
        if self.family == "composite":
            if not 1 <= len(self.blocks) <= 6:
                raise ValueError("composition requires 1 to 6 blocks")
            for i, block in enumerate(self.blocks):
                if block.skip_from is not None and block.skip_from > i:
                    raise ValueError("skip must reference input or an earlier block; cycles are forbidden")
        elif self.blocks:
            raise ValueError("blocks require the composite family")
        return self

    @property
    def genome_id(self):
        data = self.model_dump(mode="json")
        if not self.blocks:
            del data["blocks"]  # Preserve all historical family genome identities.
        return canonical_sha256(data, schema_version="prism.genome/v2" if self.blocks else "prism.genome/v1", digest_field=None)


def compatible_families(modality, task="classification"):
    names = [name for name, supported in FAMILIES.items() if modality in supported]
    if task == "language_modeling":
        names = [
            name
            for name in names
            if name
            in {
                "embedding",
                "attention",
                "sparse_attention",
                "causal_transformer",
                "state_space",
                "sparse_state_space",
                "gated_state_space",
                "composite",
            }
        ]
    return sorted(names)


def changed(genome, **updates):
    return ModelGenome.model_validate({**genome.model_dump(), **updates})


def mutate(genome, rng: Random, allowed, operator=None, task="classification", *, broad=False, family_locked=False):
    operators = [
        "family",
        "width",
        "depth",
        "activation",
        "lr",
        "norm",
        "dropout",
        "morph_widen",
        "morph_deepen",
        "weight_decay",
    ]
    if GROUPS[genome.family] == "mlp":
        operators += ["residual"]
    if "sparse" in genome.family:
        operators += ["sparsity"]
    if "conv" in genome.family:
        operators += ["kernel"]
    if genome.family == "moe_mlp":
        operators += ["experts", "top_k"]
    if GROUPS[genome.family] == "attention":
        operators += ["position", "embedding", "heads", "kv_heads", "ffn_ratio"]
    if broad and genome.family == "composite":
        operators = ["family", "activation", "lr", "norm", "dropout", "weight_decay", "sparsity",
                     "embedding", "heads", "kv_heads", "position", "ffn_ratio", "kernel",
                     "block_add", "block_remove", "block_kind", "block_rewire"]
    elif broad and genome.family in {"embedding", "gru", "state_space", "sparse_state_space", "gated_state_space"}:
        operators += ["embedding"]
    if family_locked:
        operators.remove("family")
        if operator == "family":
            raise ValueError("protected mutation cannot switch family")
    if operator is None:
        operator = rng.choice(operators)
    morph_eligible = (
        genome.family == "mlp"
        and genome.activation == "relu"
        and genome.norm_type == "none"
        and genome.dropout == 0
        and not genome.residual
    )
    if operator == "morph_widen" and (not morph_eligible or max(genome.hidden_layers) >= 256):
        operator = "width"
    if operator == "morph_deepen" and (not morph_eligible or len(genome.hidden_layers) >= 6):
        operator = "depth"
    updates = {}

    def other(current, choices):
        return rng.choice([v for v in choices if v != current])

    widths = list(genome.hidden_layers)
    if operator == "family" and len(allowed) > 1:
        updates = {"family": other(genome.family, allowed), "residual": False}
        updates["blocks"] = ([{"kind": "dense"}, {"kind": "gated", "skip_from": 0}]
                             if updates["family"] == "composite" else [])
    elif operator in {"width", "morph_widen"}:
        i = rng.randrange(len(widths))
        widths[i] = min(256, widths[i] + 4) if operator == "morph_widen" else other(widths[i], [8, 16, 32, 64])
        if broad and operator == "width":
            widths[i] = other(genome.hidden_layers[i], range(4, 257))
        updates["hidden_layers"] = widths
    elif operator in {"depth", "morph_deepen"}:
        if broad and operator == "depth" and len(widths) > 1 and (len(widths) == 6 or rng.random() < .5):
            del widths[rng.randrange(len(widths))]
        elif len(widths) < 6:
            widths.append(widths[-1])
        else:
            del widths[-1]
        updates["hidden_layers"] = widths
    elif operator == "activation":
        updates["activation"] = other(genome.activation, ["relu", "gelu", "tanh", "silu"])
    elif operator == "lr":
        updates["learning_rate"] = 10 ** rng.uniform(-5, -1) if broad else other(genome.learning_rate, [0.001, 0.003, 0.01])
    elif operator == "norm":
        updates["norm_type"] = other(
            genome.norm_type,
            ["none", "layer", "rms"] if task == "language_modeling" else ["none", "layer", "rms", "batch"],
        )
    elif operator == "dropout":
        updates["dropout"] = rng.uniform(0, .3) if broad else other(genome.dropout, [0, 0.1, 0.3])
    elif operator == "weight_decay":
        updates["weight_decay"] = rng.uniform(0, .1) if broad else other(genome.weight_decay, [0, 0.001, 0.01, 0.1])
    elif operator == "residual":
        updates["residual"] = not genome.residual
    elif operator == "heads":
        choices = [
            h
            for h in (1, 2, 4, 8)
            if genome.embedding_dim % h == 0
            and h % genome.kv_heads == 0
            and (genome.position_encoding != "rope" or genome.embedding_dim // h % 2 == 0)
        ]
        if len(choices) > 1:
            updates["num_heads"] = other(genome.num_heads, choices)
    elif operator == "kv_heads":
        choices = [h for h in (1, 2, 4, 8) if genome.num_heads % h == 0]
        if len(choices) > 1:
            updates["kv_heads"] = other(genome.kv_heads, choices)
    elif operator == "ffn_ratio":
        updates["ffn_ratio"] = other(genome.ffn_ratio, [1, 2, 4])
    elif operator == "sparsity":
        updates["activation_sparsity"] = rng.random() if broad else other(genome.activation_sparsity, [0.25, 0.5, 0.75])
    elif operator == "kernel":
        updates["kernel_size"] = other(genome.kernel_size, [3, 5])
    elif operator == "experts":
        updates["num_experts"] = other(genome.num_experts, [2, 4, 8])
    elif operator == "top_k":
        updates["moe_top_k"] = other(genome.moe_top_k, [1, 2])
    elif operator == "position":
        choices = ["none", "sinusoidal"]
        if genome.embedding_dim // genome.num_heads % 2 == 0:
            choices.append("rope")
        updates["position_encoding"] = other(genome.position_encoding, choices)
    elif operator == "embedding":
        choices = [d for d in range(4, 257) if d % genome.num_heads == 0
                   and (genome.position_encoding != "rope" or (d // genome.num_heads) % 2 == 0)]
        updates["embedding_dim"] = other(genome.embedding_dim, choices if broad else [16, 32, 64])
    elif operator.startswith("block_") and genome.family == "composite":
        blocks = [b.model_dump() for b in genome.blocks]
        kinds = [k for k in BLOCK_KINDS if k != "conv2d" or "conv2d" in allowed]
        if operator == "block_add" and len(blocks) < 6:
            index = rng.randrange(len(blocks) + 1)
            for block in blocks[index:]:
                if block["skip_from"] is not None and block["skip_from"] > index:
                    block["skip_from"] += 1
            blocks.insert(index, {"kind": rng.choice(kinds), "skip_from": None})
        elif operator == "block_remove" and len(blocks) > 1:
            index = rng.randrange(len(blocks))
            del blocks[index]
            for block in blocks:
                if block["skip_from"] == index + 1:
                    block["skip_from"] = None
                elif block["skip_from"] is not None and block["skip_from"] > index + 1:
                    block["skip_from"] -= 1
        elif operator == "block_rewire":
            index = rng.randrange(len(blocks))
            blocks[index]["skip_from"] = other(blocks[index]["skip_from"], [None, *range(index + 1)])
        else:
            operator = "block_kind"
            index = rng.randrange(len(blocks))
            blocks[index]["kind"] = other(blocks[index]["kind"], kinds)
        updates["blocks"] = blocks
    child = changed(genome, **updates)
    if child.genome_id == genome.genome_id:
        child = changed(genome, learning_rate=other(genome.learning_rate, [0.001, 0.003, 0.01]))
        if broad:
            operator = "lr"
    if task == "language_modeling" and child.norm_type == "batch":
        child = changed(child, norm_type="layer")
    return child, operator


def crossover(a, b, rng: Random, mode="uniform", *, task="classification", broad=False):
    if mode not in {"uniform", "splice"}:
        raise ValueError("unknown crossover mode")
    data = a.model_dump()
    if mode == "splice":
        split = rng.randrange(len(a.hidden_layers) + 1)
        data["hidden_layers"] = (a.hidden_layers[:split] + b.hidden_layers[split:])[:6] or a.hidden_layers
    else:
        for key in ("activation", "dropout", "learning_rate", "weight_decay", "norm_type"):
            if rng.random() < 0.5:
                data[key] = b.model_dump()[key]
        if GROUPS[a.family] == GROUPS[b.family]:
            for key in ("family", "hidden_layers", "kernel_size", "activation_sparsity", "num_experts", "moe_top_k"):
                if rng.random() < 0.5:
                    data[key] = b.model_dump()[key]
            if broad and rng.random() < .5:
                for key in ("embedding_dim", "num_heads", "kv_heads", "position_encoding", "ffn_ratio"):
                    data[key] = b.model_dump()[key]
    if a.family == b.family == "composite":
        split = rng.randrange(min(len(a.blocks), len(b.blocks)) + 1)
        data["blocks"] = [block.model_dump() for block in (a.blocks[:split] + b.blocks[split:])[:6]]
        for i, block in enumerate(data["blocks"]):
            if block["skip_from"] is not None and block["skip_from"] > i:
                block["skip_from"] = None
    data["residual"] = data["residual"] and GROUPS[data["family"]] == "mlp"
    if task == "language_modeling" and data["norm_type"] == "batch":
        data["norm_type"] = "layer"
    return ModelGenome.model_validate(data)
