"""Additive genome contract. V1 identities and executable semantics stay frozen."""

from typing import Literal
from pydantic import Field, model_validator
from evonn_shared.canonical import canonical_sha256
from .genome import Genome, LayerGene, ConnectionGene


class LayerV2(LayerGene):
    activation: Literal["relu", "gelu", "tanh", "silu", "identity"] = "relu"
    normalization: Literal["layer", "rms", "none"] = "layer"
    merge: Literal["sqrt_sum", "sum", "mean"] = "sqrt_sum"
    # A zero-gated branch preserves the old sum normalization at insertion.
    merge_reference_count: int | None = Field(default=None, ge=1, le=128)


class ConnectionV2(ConnectionGene):
    scale: float = Field(default=1, ge=-8, le=8)
    trainable_scale: bool = False


class GenomeV2(Genome):
    schema_version: Literal[2] = 2
    layers: tuple[LayerV2, ...]
    connections: tuple[ConnectionV2, ...]
    input_adapter: Literal["flat", "token_attention", "spatial"] = "flat"
    adapter_width: int = Field(default=16, ge=4, le=256)
    adapter_heads: Literal[1, 2, 4] = 1

    @model_validator(mode="after")
    def adapter_dimensions(self):
        if self.adapter_width % self.adapter_heads:
            raise ValueError("adapter width must divide evenly into heads")
        if any(c.depthwise for c in self.convolutions):
            raise ValueError("depthwise is reserved until a distinct multi-channel executor is registered")
        return self

    @property
    def genome_id(self):
        data = self.model_dump(mode="json")
        for key in ("layers", "connections", "experts"):
            data[key] = sorted(data[key], key=lambda v: v["innovation"])
        data["convolutions"] = sorted(data["convolutions"], key=lambda v: v["layer"])
        return canonical_sha256(data, schema_version="topograph.genome/v2", digest_field=None)


def parse_genome(data):
    return (GenomeV2 if data.get("schema_version") == 2 else Genome).model_validate(data)
