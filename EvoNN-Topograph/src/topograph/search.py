"""Innovation-aligned variation with reproduction-changing speciation and EMA scheduling."""

from random import Random
from copy import deepcopy
import numpy as np
from evonn_shared.canonical import canonical_sha256
from evonn_shared.weight_cache import WeightCache
from .genome import Genome, LayerGene, ConnectionGene, Innovations, seed_genome, OPERATORS
from .compiler import compile_genome


def tuples(value):
    return tuple(tuples(v) for v in value) if isinstance(value, list) else value


def architecture_id(genome):
    data = genome.model_dump(mode="json")
    del data["learning_rate"]
    del data["weight_decay"]
    for key in ("layers", "connections", "experts"):
        data[key] = sorted(data[key], key=lambda value: value["innovation"])
    data["convolutions"] = sorted(data["convolutions"], key=lambda value: value["layer"])
    return canonical_sha256(data, schema_version="topograph.architecture/v1", digest_field=None)


def topology_id(genome):
    return canonical_sha256(
        {
            "layers": sorted(n.innovation for n in genome.active_layers()),
            "edges": sorted((e.innovation, e.source, e.target) for e in genome.connections if e.enabled),
        },
        schema_version="topograph.topology/v1",
        digest_field=None,
    )


def distance(a, b):
    left = {e.innovation for e in a.connections if e.enabled}
    right = {e.innovation for e in b.connections if e.enabled}
    union = left | right
    structural = len(left ^ right) / max(1, len(union))
    la, lb = {n.innovation: n for n in a.layers}, {n.innovation: n for n in b.layers}
    common = set(la) & set(lb)
    mismatch = sum(
        (la[i].operator != lb[i].operator)
        + abs(la[i].width - lb[i].width) / 256
        + abs(la[i].weight_bits - lb[i].weight_bits) / 16
        for i in common
    )
    return structural + mismatch / max(1, len(common))


def species(population, threshold=0.45):
    groups = []
    for index, genome in enumerate(population):
        target = next((group for group in groups if distance(genome, population[group[0]]) <= threshold), None)
        if target is None:
            groups.append([index])
        else:
            target.append(index)
    return groups


def select_parents(population, scores, rng, count, *, use_speciation=True):
    groups = species(population) if use_speciation else [list(range(len(population)))]
    # Each extant niche gets a reproductive slot before global competition.
    selected = []
    for i in range(count):
        group = groups[i % len(groups)]
        sampled = rng.sample(group, min(3, len(group)))
        selected.append(max(sampled, key=lambda j: scores[j]))
    return selected


def crossover(a, b, rng):
    # Fitter parent supplies structural backbone; matching innovations align attributes.
    other = {n.innovation: n for n in b.layers}
    layers = []
    for node in a.layers:
        candidate = other[node.innovation] if node.innovation in other else node
        if rng.random() < 0.5:
            candidate = LayerGene.model_validate(
                {**candidate.model_dump(), "order": node.order, "enabled": node.enabled}
            )
        else:
            candidate = node
        layers.append(candidate)
    data = a.model_dump()
    data["layers"] = [n.model_dump() for n in layers]
    try:
        return Genome.model_validate(data)
    except ValueError:
        return a  # Incompatible spatial metadata retains the known-valid fitter parent.


def mutate(genome, rng, innovations, operator):
    data = genome.model_dump()
    layers, edges = list(genome.layers), list(genome.connections)
    target = rng.randrange(len(layers))
    node = layers[target]

    def replace_node(**updates):
        layers[target] = LayerGene.model_validate({**node.model_dump(), **updates})

    if operator == "split" and len(layers) < 16 and len(edges) <= 126:
        available = [e for e in edges if e.enabled]
        edge = rng.choice(available)
        new_id = innovations.obtain(f"split_node:{edge.innovation}")
        if new_id not in {n.innovation for n in layers}:
            orders = {n.innovation: n.order for n in layers}
            before = orders[edge.source] if edge.source != -1 else min(orders.values()) - 1
            order = (before + orders[edge.target]) / 2
            layers.append(LayerGene(innovation=new_id, order=order, width=node.width, weight_bits=node.weight_bits))
            edges = [
                ConnectionGene.model_validate({**e.model_dump(), "enabled": False})
                if e.innovation == edge.innovation
                else e
                for e in edges
            ]
            edges += [
                ConnectionGene(
                    innovation=innovations.obtain(f"split_in:{edge.innovation}"), source=edge.source, target=new_id
                ),
                ConnectionGene(
                    innovation=innovations.obtain(f"split_out:{edge.innovation}"), source=new_id, target=edge.target
                ),
            ]
    elif operator == "skip" and len(edges) < 128:
        pairs = {(e.source, e.target) for e in edges}
        options = [
            (source, n.innovation)
            for n in layers
            for source in [-1, *[s.innovation for s in layers if s.order < n.order]]
            if (source, n.innovation) not in pairs
        ]
        if options:
            source, target_id = rng.choice(options)
            edges.append(
                ConnectionGene(
                    innovation=innovations.obtain(f"edge:{source}:{target_id}"), source=source, target=target_id
                )
            )
    elif operator == "operator":
        choice = rng.choice([op for op in OPERATORS if op != node.operator])
        width = 16 if choice in {"spatial", "attention_lite", "transformer_lite"} else node.width
        replace_node(operator=choice, width=width, heads=1)
        data["convolutions"] = [c.model_dump() for c in genome.convolutions if c.layer != node.innovation]
    elif operator == "width":
        widths = [16, 64] if node.operator == "spatial" else [8, 16, 32, 64]
        widths = [
            w
            for w in widths
            if w != node.width
            and (node.operator not in {"attention_lite", "transformer_lite"} or w % (4 * node.heads) == 0)
        ]
        if widths:
            replace_node(width=rng.choice(widths))
    elif operator == "precision":
        replace_node(weight_bits=rng.choice([bits for bits in (1.58, 4, 8, 16) if bits != node.weight_bits]))
    elif operator == "activation":
        replace_node(activation=rng.choice([a for a in ("relu", "gelu", "tanh", "silu") if a != node.activation]))
    elif operator == "sparsity":
        replace_node(sparsity=rng.choice([s for s in (0.1, 0.25, 0.5, 0.75) if s != node.sparsity]))
    else:
        data["learning_rate"] = rng.choice([v for v in (0.001, 0.003, 0.01) if v != genome.learning_rate])
    data.update(layers=[n.model_dump() for n in layers], connections=[e.model_dump() for e in edges])
    child = Genome.model_validate(data)
    if child.genome_id == genome.genome_id:
        data["learning_rate"] = 0.001 if genome.learning_rate != 0.001 else 0.003
        child = Genome.model_validate(data)
    return child


def descriptor(genome):
    nodes = genome.active_layers()
    depths = {-1: 0}
    edges = [e for e in genome.connections if e.enabled]
    for node in nodes:
        depths[node.innovation] = 1 + max(
            depths[e.source] for e in edges if e.target == node.innovation and e.source in depths
        )
    return [
        max(depths.values()),
        max(n.width for n in nodes),
        max(0, len(edges) - len(nodes)),
        sum(n.weight_bits for n in nodes) / len(nodes),
        len(edges) / max(1, len(nodes) * (len(nodes) + 1) / 2),
    ]


class Scheduler:
    def __init__(self, state=None):
        self.ema = dict(state or {})

    def phase(self, progress):
        return "explore" if progress < 0.5 else "refine" if progress < 0.85 else "polish"

    def choose(self, progress, rng):
        phase = self.phase(progress)
        profile = {"split": 5, "skip": 4, "operator": 3, "width": 2, "precision": 2, "activation": 1, "lr": 1}
        if phase == "refine":
            profile.update(split=1, skip=2, width=4, precision=3)
        elif phase == "polish":
            profile.update(split=0.1, skip=0.1, operator=0.1, width=1, precision=3, activation=3, lr=4)
        names = list(profile)
        weights = [profile[name] * (0.25 + (self.ema[name] if name in self.ema else 0.5)) for name in names]
        return rng.choices(names, weights=weights, k=1)[0]

    def observe(self, operator, success):
        prior = self.ema[operator] if operator in self.ema else 0.5
        self.ema[operator] = 0.8 * prior + 0.2 * success


class Search:
    system = "topograph"

    def __init__(
        self, definitions, *, seed, population_size=4, state=None, benchmark_pooling=False, novelty_weight=0.0
    ):
        if population_size < 2:
            raise ValueError("speciation requires population >= 2")
        self.rng, self.size = Random(seed), population_size
        self.definitions = {d.id: d for d in definitions}
        self.innovations = Innovations()
        self.scheduler = Scheduler()
        self.cache = WeightCache(2 * population_size * len(definitions))
        if not 0 <= novelty_weight <= 1:
            raise ValueError("novelty_weight must lie in [0,1]")
        self.novelty_weight = float(novelty_weight)
        self.benchmark_pooling = bool(benchmark_pooling)
        self.pool_scores = {}
        self.progress = 0.0
        self.benchmarks = {}
        if state:
            state = deepcopy(state)
            self.rng.setstate(tuples(state["rng"]))
            self.benchmark_pooling = state["benchmark_pooling"]
            self.novelty_weight = state["novelty_weight"]
            self.pool_scores = state["pool_scores"]
            self.innovations = Innovations(**state["innovations"])
            self.scheduler = Scheduler(state["scheduler"])
            self.cache = WeightCache(2 * population_size * len(definitions), state["cache"])
            self.benchmarks = state["benchmarks"]
        else:
            for definition in definitions:
                population = [
                    seed_genome(
                        self.innovations, operator=OPERATORS[i % len(OPERATORS)], bits=(16, 8, 4, 1.58)[i % 4]
                    ).model_dump(mode="json")
                    for i in range(population_size)
                ]
                self.benchmarks[definition.id] = {
                    "population": population,
                    "cursor": 0,
                    "generation": 0,
                    "evaluated": 0,
                    "scores": [],
                    "elite": None,
                    "novelty": [],
                    "operators": {},
                    "trace": [],
                    "species": [],
                }

    def candidate(self, benchmark):
        state = self.benchmarks[benchmark]
        return Genome.model_validate(state["population"][state["cursor"]])

    def compile(self, genome, definition, **options):
        return compile_genome(
            genome,
            definition.input_shape,
            definition.output_dim,
            definition.input_modality.value,
            definition.task_kind.value,
            **options,
        )

    def inherit(self, model, benchmark, namespace):
        return self.cache.inherit(
            model,
            namespace=namespace,
            identity=architecture_id(model.genome),
            topology=topology_id(model.genome),
            family=model.genome.genome_id,
            compatible_groups=(),
        )

    def remember(self, model, namespace):
        self.cache.put(
            namespace,
            architecture_id(model.genome),
            topology_id(model.genome),
            model.genome.genome_id,
            model.weights,
            model.buffers,
        )

    def observe(self, benchmark, genome, result):
        state = self.benchmarks[benchmark]
        quality = result["score"] if result["status"] == "ok" else -1e30
        behavior = descriptor(genome)
        distances = [float(np.linalg.norm(np.asarray(behavior) - other)) for other in state["novelty"]]
        novelty = float(np.mean(sorted(distances)[:5])) if distances else 0.0
        if result["status"] == "ok":
            if genome.genome_id not in self.pool_scores:
                self.pool_scores[genome.genome_id] = {}
            self.pool_scores[genome.genome_id][benchmark] = quality
        adjusted = (1 - self.novelty_weight) * quality + self.novelty_weight * novelty
        entry = {
            "genome": genome.model_dump(mode="json"),
            "identity": genome.genome_id,
            "quality": quality,
            "status": result["status"],
            "adjusted": adjusted,
            "novelty": novelty,
        }
        state["scores"].append(entry)
        state["novelty"] = (state["novelty"] + [behavior])[-64:]
        state["trace"].append(genome.genome_id)
        state["cursor"] += 1
        state["evaluated"] += 1
        if result["status"] == "ok" and (state["elite"] is None or quality > state["elite"]["quality"]):
            state["elite"] = entry
        if genome.genome_id in state["operators"]:
            operator, baseline = state["operators"][genome.genome_id]
            self.scheduler.observe(operator, quality > baseline)
        if state["cursor"] == self.size:
            population = [Genome.model_validate(e["genome"]) for e in state["scores"]]
            scores = [self.selection_fitness(e) for e in state["scores"]]
            groups = species(population)
            parents = select_parents(population, scores, self.rng, self.size)
            champion = max(range(len(scores)), key=lambda i: scores[i])
            parents[0] = champion
            children, operators = [], {}
            for slot, index in enumerate(parents):
                parent = population[index]
                if slot == 0:
                    children.append(parent.model_dump(mode="json"))
                    continue
                group = next(group for group in groups if index in group)
                mate = population[self.rng.choice(group)]
                child = crossover(parent, mate, self.rng)
                # Keep the champion of each protected species before mutation fills its slots.
                if slot >= len(groups):
                    op = self.scheduler.choose(self.progress, self.rng)
                    child = mutate(child, self.rng, self.innovations, op)
                    operators[child.genome_id] = [op, state["scores"][index]["quality"]]
                else:
                    # Young species still explore; retain global best in slot zero only.
                    if slot > 0:
                        op = self.scheduler.choose(self.progress, self.rng)
                        child = mutate(child, self.rng, self.innovations, op)
                        operators[child.genome_id] = [op, state["scores"][index]["quality"]]
                children.append(child.model_dump(mode="json"))
            state.update(
                population=children,
                cursor=0,
                scores=[],
                generation=state["generation"] + 1,
                operators=operators,
                species=groups,
            )

    def selection_fitness(self, entry):
        if entry["status"] != "ok":
            return -1e30
        quality = (
            self.pooled_fitness(entry["identity"], entry["quality"]) if self.benchmark_pooling else entry["quality"]
        )
        return (1 - self.novelty_weight) * quality + self.novelty_weight * entry["novelty"]

    def pooled_fitness(self, identity, fallback):
        if identity not in self.pool_scores:
            return fallback
        ranks = []
        for benchmark, value in self.pool_scores[identity].items():
            values = [scores[benchmark] for scores in self.pool_scores.values() if benchmark in scores]
            # Within-benchmark percentiles avoid averaging accuracy with negative MSE.
            ranks.append((sum(v < value for v in values) + 0.5 * sum(v == value for v in values)) / len(values))
        return sum(ranks) / len(ranks)

    def telemetry(self):
        return {
            "schema_version": "1.0.0",
            "system": self.system,
            "topology_size": {
                k: [descriptor(Genome.model_validate(g)) for g in s["population"]] for k, s in self.benchmarks.items()
            },
            "novelty_metrics": {
                k: {"archive_size": len(s["novelty"]), "weight": self.novelty_weight}
                for k, s in self.benchmarks.items()
            },
            "operator_success": self.scheduler.ema,
            "inheritance_entries": len(self.cache.entries),
            "species": {k: s["species"] for k, s in self.benchmarks.items()},
            "map_elites": "deferred_phase6",
            "benchmark_pooling": {"enabled": self.benchmark_pooling, "candidate_count": len(self.pool_scores)},
            "generations": {k: s["generation"] for k, s in self.benchmarks.items()},
        }

    def state(self):
        return {
            "rng": self.rng.getstate(),
            "benchmark_pooling": self.benchmark_pooling,
            "novelty_weight": self.novelty_weight,
            "pool_scores": self.pool_scores,
            "innovations": self.innovations.state(),
            "scheduler": self.scheduler.ema,
            "cache": self.cache.state(),
            "benchmarks": self.benchmarks,
        }
