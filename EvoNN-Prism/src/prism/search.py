"""Family-diverse evolution, benchmark-local archives, and resumable variation state."""

from collections import Counter
from random import Random
from copy import deepcopy
import numpy as np
from .genome import ModelGenome, compatible_families, mutate, crossover, GROUPS
from .compiler import compile_genome
from evonn_shared.weight_cache import WeightCache


def tuples(value):
    return tuple(tuples(v) for v in value) if isinstance(value, list) else value


class Search:
    system = "prism"

    def __init__(self, definitions, *, seed, population_size=4, state=None):
        if population_size < 2:
            raise ValueError("family diversity requires at least two population members")
        self.rng = Random(seed)
        self.size, self.definitions = population_size, {d.id: d for d in definitions}
        self.cache = WeightCache(2 * population_size * len(definitions))
        self.benchmarks = {}
        self.operator_stats = {}
        if state:
            state = deepcopy(state)
            self.rng.setstate(tuples(state["rng"]))
            self.benchmarks = state["benchmarks"]
            self.operator_stats = state["operator_stats"]
            self.cache = WeightCache(2 * population_size * len(definitions), state["cache"])
        else:
            for d in definitions:
                allowed = compatible_families(d.input_modality.value, d.task_kind.value)
                if not allowed:
                    raise ValueError(f"no compatible family for {d.id}")
                population = [
                    ModelGenome(family=allowed[i % len(allowed)], hidden_layers=(8 + 8 * (i % 3),)).model_dump(
                        mode="json"
                    )
                    for i in range(population_size)
                ]
                self.benchmarks[d.id] = {
                    "population": population,
                    "cursor": 0,
                    "generation": 0,
                    "evaluated": 0,
                    "scores": [],
                    "elite": None,
                    "pareto": [],
                    "niches": {},
                    "parents": {},
                    "operators": {},
                    "trace": [],
                }

    def candidate(self, benchmark):
        state = self.benchmarks[benchmark]
        return ModelGenome.model_validate(state["population"][state["cursor"]])

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
        g, state = model.genome, self.benchmarks[benchmark]
        parents = state["parents"][g.genome_id] if g.genome_id in state["parents"] else ()
        inherited = self.cache.inherit(
            model,
            namespace=namespace,
            identity=g.genome_id,
            topology=GROUPS[g.family],
            family=g.family,
            parents=parents,
            compatible_groups=[f for f, group in GROUPS.items() if group == GROUPS[g.family]],
        )
        if g.genome_id in state["operators"]:
            operator = state["operators"][g.genome_id][0]
            if operator in {"morph_widen", "morph_deepen"} and parents and inherited["source"] == parents[0]:
                item = next(
                    v
                    for v in self.cache.entries.values()
                    if v["namespace"] == namespace and v["identity"] == inherited["source"]
                )
                preserve_morphism(model, item["weights"], operator)
                inherited["function_preserving"] = True
        return inherited

    def remember(self, model, namespace):
        g = model.genome
        self.cache.put(namespace, g.genome_id, GROUPS[g.family], g.family, model.weights, model.buffers)

    def observe(self, benchmark, genome, result):
        state = self.benchmarks[benchmark]
        quality = result["score"] if result["status"] == "ok" else -1e30
        entry = {
            "genome": genome.model_dump(mode="json"),
            "identity": genome.genome_id,
            "quality": quality,
            "parameters": result.get("parameter_count", 0),
        }
        state["scores"].append(entry)
        state["trace"].append(genome.genome_id)
        state["evaluated"] += 1
        state["cursor"] += 1
        if result["status"] == "ok":
            if state["elite"] is None or quality > state["elite"]["quality"]:
                state["elite"] = entry
            niches = state["niches"]
            if genome.family not in niches or quality > niches[genome.family]["quality"]:
                niches[genome.family] = entry
            previous = next((e for e in state["pareto"] if e["identity"] == entry["identity"]), None)
            retained = previous if previous is not None and previous["quality"] >= entry["quality"] else entry
            candidates = [e for e in state["pareto"] if e["identity"] != entry["identity"]] + [retained]
            state["pareto"] = [
                e
                for e in candidates
                if not any(
                    o["quality"] >= e["quality"]
                    and o["parameters"] <= e["parameters"]
                    and (o["quality"] > e["quality"] or o["parameters"] < e["parameters"])
                    for o in candidates
                )
            ]
        if genome.genome_id in state["operators"]:
            op, baseline = state["operators"][genome.genome_id]
            prior = self.operator_stats[op] if op in self.operator_stats else {"uses": 0, "successes": 0, "ema": 0.5}
            improved = quality > baseline
            self.operator_stats[op] = {
                "uses": prior["uses"] + 1,
                "successes": prior["successes"] + int(improved),
                "ema": 0.8 * prior["ema"] + 0.2 * improved,
            }
        if state["cursor"] == self.size:
            self._reproduce(benchmark)

    def _reproduce(self, benchmark):
        state, definition = self.benchmarks[benchmark], self.definitions[benchmark]
        allowed = compatible_families(definition.input_modality.value, definition.task_kind.value)
        pool = sorted(state["scores"], key=lambda e: (-e["quality"], e["identity"]))

        def tournament():
            return max(self.rng.sample(pool, min(3, len(pool))), key=lambda e: e["quality"])

        children = [pool[0]["genome"]]
        parents, operators = {}, {}
        for slot in range(1, self.size):
            a, c = tournament(), tournament()
            parent = ModelGenome.model_validate(a["genome"])
            rate = self.operator_stats["crossover"]["ema"] if "crossover" in self.operator_stats else 0.5
            if self.rng.random() < 0.2 + 0.6 * rate:
                child = crossover(
                    parent, ModelGenome.model_validate(c["genome"]), self.rng, self.rng.choice(["uniform", "splice"])
                )
                op = "crossover"
                if child.genome_id == parent.genome_id:
                    child, op = mutate(child, self.rng, allowed)
            else:
                child, op = mutate(parent, self.rng, allowed)
            # Preserve a second architectural niche, cycling underrepresented families.
            if slot == 1 and len(allowed) > 1:
                present = {v["family"] for v in children}
                missing = [f for f in allowed if f not in present]
                family = missing[state["generation"] % len(missing)]
                child = ModelGenome.model_validate({**child.model_dump(), "family": family, "residual": False})
                op = "family"
            identities = {ModelGenome.model_validate(g).genome_id for g in children}
            while child.genome_id in identities:
                child = ModelGenome.model_validate(
                    {**child.model_dump(), "learning_rate": self.rng.uniform(0.0001, 0.01)}
                )
            children.append(child.model_dump(mode="json"))
            parents[child.genome_id] = [a["identity"], c["identity"]]
            operators[child.genome_id] = [op, a["quality"]]
        state.update(
            population=children,
            cursor=0,
            generation=state["generation"] + 1,
            scores=[],
            parents=parents,
            operators=operators,
        )

    def telemetry(self):
        return {
            "schema_version": "1.0.0",
            "system": self.system,
            "family_distribution": {
                k: dict(Counter(g["family"] for g in s["population"])) for k, s in self.benchmarks.items()
            },
            "archive_occupancy": {
                k: {"family": len(s["niches"]), "pareto": len(s["pareto"]), "elite": int(s["elite"] is not None)}
                for k, s in self.benchmarks.items()
            },
            "operator_success": self.operator_stats,
            "inheritance_entries": len(self.cache.entries),
            "generations": {k: s["generation"] for k, s in self.benchmarks.items()},
            "promotion_screen": "disabled",
            "evaluation_cache_hits": 0,
        }

    def state(self):
        return {
            "rng": self.rng.getstate(),
            "benchmarks": self.benchmarks,
            "operator_stats": self.operator_stats,
            "cache": self.cache.state(),
        }


def preserve_morphism(model, previous_weights, operator):
    """Net2Wider/identity-deeper for plain ReLU MLPs; other domains are rejected."""
    g = model.genome
    if not (
        g.family == "mlp" and g.activation == "relu" and g.norm_type == "none" and g.dropout == 0 and not g.residual
    ):
        raise ValueError("morphism requires plain ReLU MLP without normalization/dropout/residual")
    old = {k: np.asarray(v, dtype=np.float32) for k, v in previous_weights.items()}
    for key, value in old.items():
        if key in model.weights and model.weights[key].shape == value.shape:
            model.weights[key] = value.copy()
    if operator == "morph_deepen":
        added = [key for key in model.weights if key.startswith("layer") and key.endswith(".w") and key not in old]
        if len(added) != 1:
            raise ValueError("deepen must insert exactly one identity layer")
        key = added[0]
        rows, cols = model.weights[key].shape
        if rows != cols:
            raise ValueError("identity layer must preserve width")
        model.weights[key] = np.eye(rows, dtype=np.float32)
        model.weights[key[:-1] + "b"] = np.zeros(rows, dtype=np.float32)
    elif operator == "morph_widen":
        changed = [
            key
            for key in old
            if key.startswith("layer") and key.endswith(".w") and old[key].shape[1] != model.weights[key].shape[1]
        ]
        if len(changed) != 1:
            raise ValueError("widen must expand exactly one layer")
        key = changed[0]
        before, after = old[key].shape[1], model.weights[key].shape[1]
        if after <= before:
            raise ValueError("widen cannot shrink")
        mapping = np.arange(after) % before
        copies = np.bincount(mapping, minlength=before)
        model.weights[key] = old[key][:, mapping].copy()
        model.weights[key[:-1] + "b"] = old[key[:-1] + "b"][mapping].copy()
        index = int(key.removeprefix("layer").removesuffix(".w"))
        outgoing = f"layer{index + 1}.w" if f"layer{index + 1}.w" in old else "head.w"
        model.weights[outgoing] = (old[outgoing][mapping] / copies[mapping, None]).astype(np.float32)
    else:
        raise ValueError("unknown morphism")
