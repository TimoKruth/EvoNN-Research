"""Validated DAG genes and persistent innovation identities."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from evonn_shared.canonical import canonical_sha256

Precision = Literal[1.58, 4, 8, 16]
OPERATORS = ("dense", "sparse_dense", "residual", "attention_lite", "spatial", "transformer_lite")


class Gene(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class LayerGene(Gene):
    innovation: int = Field(ge=0)
    width: int = Field(default=16, ge=4, le=256)
    order: float
    activation: Literal["relu", "gelu", "tanh", "silu"] = "relu"
    weight_bits: Precision = 16
    activation_bits: Literal[8, 16, 32] = 32
    sparsity: float = Field(default=0.25, ge=0, lt=1)
    operator: Literal["dense", "sparse_dense", "residual", "attention_lite", "spatial", "transformer_lite"] = "dense"
    heads: Literal[1, 2, 4] = 1
    enabled: bool = True

    @model_validator(mode="after")
    def dimensions(self):
        if self.operator in {"attention_lite", "transformer_lite"} and self.width % (4 * self.heads):
            raise ValueError("attention width must be divisible by four tokens times heads")
        if self.operator == "spatial" and int(self.width**0.5) ** 2 != self.width:
            raise ValueError("spatial node requires a square feature map")
        return self


class ConnectionGene(Gene):
    innovation: int = Field(ge=0)
    source: int = Field(ge=-1)  # -1 denotes external input, output is explicit Genome.output
    target: int = Field(ge=0)
    enabled: bool = True


class ConvLayerGene(Gene):
    layer: int = Field(ge=0)
    kernel_size: Literal[3, 5] = 3
    depthwise: bool = False


class ExpertGene(Gene):
    innovation: int = Field(ge=0)
    width: int = Field(default=16, ge=4, le=256)


class GateConfig(Gene):
    top_k: Literal[1, 2] = 1
    temperature: float = Field(default=1, gt=0, le=10)


class Genome(Gene):
    layers: tuple[LayerGene, ...]
    connections: tuple[ConnectionGene, ...]
    output: int = Field(ge=0)
    convolutions: tuple[ConvLayerGene, ...] = ()
    experts: tuple[ExpertGene, ...] = ()
    gate: GateConfig | None = None
    learning_rate: float = Field(default=0.003, ge=1e-5, le=0.1)
    weight_decay: float = Field(default=0.01, ge=0, le=0.1)

    @model_validator(mode="after")
    def valid_graph(self):
        nodes = {node.innovation: node for node in self.layers}
        identities = [n.innovation for n in (*self.layers, *self.connections, *self.experts)]
        if (
            not self.layers
            or len(self.layers) > 32
            or len(self.connections) > 128
            or len(set(identities)) != len(identities)
        ):
            raise ValueError("bounded graph and unique innovations required")
        if self.output not in nodes or not nodes[self.output].enabled:
            raise ValueError("enabled output node required")
        pairs = set()
        for edge in self.connections:
            if edge.target not in nodes or (edge.source != -1 and edge.source not in nodes):
                raise ValueError("connection references unknown node")
            if edge.source != -1 and nodes[edge.source].order >= nodes[edge.target].order:
                raise ValueError("edge violates acyclic topological order")
            if (edge.source, edge.target) in pairs:
                raise ValueError("duplicate connection")
            pairs.add((edge.source, edge.target))
        seen = {-1}
        for node in sorted(self.layers, key=lambda n: (n.order, n.innovation)):
            if node.enabled and any(
                e.enabled and e.target == node.innovation and e.source in seen for e in self.connections
            ):
                seen.add(node.innovation)
        if self.output not in seen:
            raise ValueError("output unreachable from input")
        convs = [c.layer for c in self.convolutions]
        if len(set(convs)) != len(convs) or any(i not in nodes or nodes[i].operator != "spatial" for i in convs):
            raise ValueError("convolution metadata must name unique spatial nodes")
        if bool(self.experts) != (self.gate is not None) or (self.gate and self.gate.top_k > len(self.experts)):
            raise ValueError("expert collection and gate must agree")
        return self

    @property
    def genome_id(self):
        data = self.model_dump(mode="json")
        for key in ("layers", "connections", "experts"):
            data[key] = sorted(data[key], key=lambda v: v["innovation"])
        data["convolutions"] = sorted(data["convolutions"], key=lambda v: v["layer"])
        return canonical_sha256(data, schema_version="topograph.genome/v1", digest_field=None)

    def active_layers(self):
        ordered = sorted((n for n in self.layers if n.enabled), key=lambda n: (n.order, n.innovation))
        forward = {-1}
        for node in ordered:
            if any(e.enabled and e.target == node.innovation and e.source in forward for e in self.connections):
                forward.add(node.innovation)
        backward = {self.output}
        for node in reversed(ordered):
            if node.innovation in backward:
                backward.update(e.source for e in self.connections if e.enabled and e.target == node.innovation)
        return tuple(n for n in ordered if n.innovation in forward & backward)


class Innovations:
    def __init__(self, counter=0, registry=None):
        self.counter, self.registry = counter, dict(registry or {})

    def obtain(self, signature):
        if signature not in self.registry:
            self.registry[signature] = self.counter
            self.counter += 1
        return self.registry[signature]

    def state(self):
        return {"counter": self.counter, "registry": dict(self.registry)}


def seed_genome(innovations, *, width=16, operator="dense", bits=16):
    node = innovations.obtain("initial_layer")
    edge = innovations.obtain("initial_input_edge")
    return Genome(
        layers=(LayerGene(innovation=node, order=1, width=width, operator=operator, weight_bits=bits),),
        connections=(ConnectionGene(innovation=edge, source=-1, target=node),),
        output=node,
    )
