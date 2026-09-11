"""Family-diverse evolution, benchmark-local archives, and resumable variation state."""

from collections import Counter
from random import Random
from copy import deepcopy
import numpy as np
from .genome import ModelGenome, compatible_families, mutate, crossover, GROUPS
from .compiler import compile_genome
from .research import policy
from .weight_cache import PrismWeightCache as WeightCache


def tuples(value):
    return tuple(tuples(v) for v in value) if isinstance(value, list) else value


class Search:
    system = "prism"

    def __init__(self, definitions, *, seed, population_size=4, state=None, variant=None, fixed_genomes=None):
        if population_size < 2:
            raise ValueError("family diversity requires at least two population members")
        self.rng = Random(seed)
        self.variant = (state.get("variant", "legacy") if state else "open") if variant is None else variant
        self.policy = policy(self.variant)
        saved_fixed = state.get("fixed_genomes") if state else None
        self.fixed_genomes = deepcopy(saved_fixed if fixed_genomes is None else fixed_genomes)
        if self.fixed_genomes is not None:
            if not self.policy["training"] or set(self.fixed_genomes) != {d.id for d in definitions}:
                raise ValueError("fixed architectures require training/open variant and the complete benchmark pack")
            self.fixed_genomes = {key: ModelGenome.model_validate(value).model_dump(mode="json")
                                  for key, value in self.fixed_genomes.items()}
        if state and self.fixed_genomes != saved_fixed:
            raise ValueError("fixed architectures differ from saved search")
        if state and state.get("variant", "legacy") != self.variant:
            raise ValueError("search policy differs from saved state")
        self.size, self.definitions = population_size, {d.id: d for d in definitions}
        self.cache = WeightCache(2 * population_size * len(definitions))
        self.benchmarks = {}
        self.operator_stats = {}
        self.context_stats = {}
        if state:
            state = deepcopy(state)
            self.rng.setstate(tuples(state["rng"]))
            self.benchmarks = state["benchmarks"]
            self.operator_stats = state["operator_stats"]
            self.context_stats = state.get("context_stats", {})
            self.cache = WeightCache(2 * population_size * len(definitions), state["cache"])
        else:
            for d in definitions:
                allowed = self.allowed(d)
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
        for state in self.benchmarks.values():
            for key, default in {"reservoir": [], "reservoir_seen": 0, "nursery": {}, "history": {},
                                 "proposals": {}, "descriptors": {}, "parent_origins": {}}.items():
                state.setdefault(key, deepcopy(default))
        if self.fixed_genomes is not None and not saved_fixed:
            for key, state in self.benchmarks.items():
                state["population"] = [deepcopy(self.fixed_genomes[key]) for _ in range(self.size)]

    def allowed(self, definition):
        families = compatible_families(definition.input_modality.value, definition.task_kind.value)
        return families if self.policy["broad"] else [family for family in families if family != "composite"]

    def proposal(self, benchmark, genome):
        state = self.benchmarks[benchmark]
        if self.fixed_genomes is not None:
            return {"origin": "fixed_architecture", "parents": [genome.genome_id] if state["evaluated"] else [],
                    "operator": "fixed_fit", "changed_fields": [], "protected": True}
        return deepcopy(state["proposals"].get(genome.genome_id, {
            "origin": "initial", "parents": [], "operator": "seed", "changed_fields": [], "protected": True,
        }))

    def candidate(self, benchmark):
        state = self.benchmarks[benchmark]
        if self.fixed_genomes is not None:
            return ModelGenome.model_validate(self.fixed_genomes[benchmark])
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
        inherited["source_updates"] = state["history"].get(inherited["source"], {}).get("lineage_updates", 0)
        inherited["source_needs_more_training"] = state["history"].get(inherited["source"], {}).get("needs_more_training", False)
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
        self.cache.put(namespace, g.genome_id, GROUPS[g.family], g.family, model.weights, model.buffers,
                       getattr(model, "optimizer_state", None))

    def observe(self, benchmark, genome, result):
        state = self.benchmarks[benchmark]
        quality = result["score"] if result["status"] == "ok" else -1e30
        entry = {
            "genome": genome.model_dump(mode="json"),
            "identity": genome.genome_id,
            "quality": quality,
            "parameters": result.get("parameter_count", 0),
        }
        proposal = self.proposal(benchmark, genome)
        inherited = result.get("inheritance", {})
        prior = state["history"].get(genome.genome_id, {})
        state["history"][genome.genome_id] = {
            "lineage_updates": inherited.get("source_updates", 0) + result.get("updates", 0),
            "evaluations": prior.get("evaluations", 0) + 1,
            "score": quality,
            "needs_more_training": result.get("best_epoch", -1) == result.get("epochs", -2),
        }
        origin = proposal["origin"]
        state["parent_origins"][origin] = state["parent_origins"].get(origin, 0) + 1
        state["scores"].append(entry)
        state["trace"].append(genome.genome_id)
        state["evaluated"] += 1
        state["cursor"] += 1
        if result["status"] == "ok":
            if self.policy["archive"]:
                # Reservoir sampling admits weak successes independently of quality.
                state["reservoir_seen"] += 1
                capacity = 4 * self.size
                if len(state["reservoir"]) < capacity:
                    state["reservoir"].append(entry)
                else:
                    index = self.rng.randrange(state["reservoir_seen"])
                    if index < capacity:
                        state["reservoir"][index] = entry
                if proposal.get("protected"):
                    old = state["nursery"].get(genome.family, {})
                    state["nursery"][genome.family] = {"entry": entry, "steps": old.get("steps", 0) + 1}
                descriptor = f"{genome.family}:{len(genome.blocks) or len(genome.hidden_layers)}:{max(1, entry['parameters']).bit_length()}:{result.get('behavior_bucket', 'unknown')}"
                previous_descriptor = state["descriptors"].get(descriptor)
                if previous_descriptor is None or quality > previous_descriptor["quality"]:
                    state["descriptors"][descriptor] = entry
                if len(state["descriptors"]) > 8 * self.size:
                    # Bounded residency, no blacklist: any descriptor can return.
                    del state["descriptors"][next(iter(state["descriptors"]))]
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
            context = f"{benchmark}:{genome.family}:{op}"
            previous_context = self.context_stats.get(context, {"uses": 0, "successes": 0, "ema": .5})
            self.context_stats[context] = {"uses": previous_context["uses"] + 1,
                "successes": previous_context["successes"] + int(improved),
                "ema": .8 * previous_context["ema"] + .2 * improved}
        if state["cursor"] == self.size:
            self._reproduce(benchmark)

    def _reproduce(self, benchmark):
        if self.fixed_genomes is not None:
            state = self.benchmarks[benchmark]
            state.update(population=[deepcopy(self.fixed_genomes[benchmark]) for _ in range(self.size)],
                         cursor=0, generation=state["generation"] + 1, scores=[])
            return
        if self.policy["archive"]:
            return self._reproduce_open(benchmark)
        state, definition = self.benchmarks[benchmark], self.definitions[benchmark]
        allowed = self.allowed(definition)
        pool = sorted(state["scores"], key=lambda e: (-e["quality"], e["identity"]))

        def tournament():
            return max(self.rng.sample(pool, min(3, len(pool))), key=lambda e: e["quality"])

        children = [pool[0]["genome"]]
        parents, operators = {}, {}
        champion = ModelGenome.model_validate(children[0])
        proposals = {champion.genome_id: {"origin": "continuation", "parents": [champion.genome_id],
                     "operator": "continue", "changed_fields": [], "protected": state["generation"] % 4 == 3}}
        for slot in range(1, self.size):
            a, c = tournament(), tournament()
            parent = ModelGenome.model_validate(a["genome"])
            rate = self.operator_stats["crossover"]["ema"] if "crossover" in self.operator_stats else 0.5
            if self.rng.random() < 0.2 + 0.6 * rate:
                child = crossover(
                    parent,
                    ModelGenome.model_validate(c["genome"]),
                    self.rng,
                    self.rng.choice(["uniform", "splice"]),
                    task=definition.task_kind.value,
                    broad=self.policy["broad"],
                )
                op = "crossover"
                if child.genome_id == parent.genome_id:
                    child, op = mutate(child, self.rng, allowed, task=definition.task_kind.value, broad=self.policy["broad"])
            else:
                child, op = mutate(parent, self.rng, allowed, task=definition.task_kind.value, broad=self.policy["broad"])
            # Preserve a second architectural niche, cycling underrepresented families.
            if slot == 1 and len(allowed) > 1:
                present = {v["family"] for v in children}
                missing = [f for f in allowed if f not in present]
                family = missing[state["generation"] % len(missing)]
                child = self.convert_family(child, family, definition)
                op = "family"
            identities = {ModelGenome.model_validate(g).genome_id for g in children}
            while child.genome_id in identities:
                child = ModelGenome.model_validate(
                    {**child.model_dump(), "learning_rate": self.rng.uniform(0.0001, 0.01)}
                )
            children.append(child.model_dump(mode="json"))
            parents[child.genome_id] = [a["identity"], c["identity"]]
            operators[child.genome_id] = [op, a["quality"]]
            proposals[child.genome_id] = {"origin": "population", "parents": parents[child.genome_id],
                "operator": op, "changed_fields": [key for key, value in child.model_dump().items()
                                                    if parent.model_dump().get(key) != value], "protected": slot == 1}
        state.update(
            population=children,
            cursor=0,
            generation=state["generation"] + 1,
            scores=[],
            parents=parents,
            operators=operators,
            proposals=proposals,
        )

    def convert_family(self, genome, family, definition):
        data = {**genome.model_dump(), "family": family, "residual": False, "blocks": []}
        if family == "composite":
            data["blocks"] = [{"kind": "dense"}, {"kind": "gated", "skip_from": 0}]
        if definition.task_kind.value == "language_modeling" and data["norm_type"] == "batch":
            data["norm_type"] = "layer"
        return ModelGenome.model_validate(data)

    def _reproduce_open(self, benchmark):
        state, definition = self.benchmarks[benchmark], self.definitions[benchmark]
        allowed, task = self.allowed(definition), definition.task_kind.value
        pool = sorted(state["scores"], key=lambda e: (-e["quality"], e["identity"]))
        children, parents, operators, proposals = [pool[0]["genome"]], {}, {}, {}
        champion = ModelGenome.model_validate(children[0])
        proposals[champion.genome_id] = {"origin": "continuation", "operator": "continue",
            "parents": [champion.genome_id], "changed_fields": [],
            "protected": state["generation"] % 4 == 3}
        parents[champion.genome_id] = [champion.genome_id]
        for slot in range(1, self.size):
            protected = slot == 1
            if protected:
                # A deterministic rotation guarantees exposure, even for size two.
                family = allowed[state["generation"] % len(allowed)]
                nursery = state["nursery"].get(family)
                if nursery and nursery["steps"] < 3:
                    a, origin = nursery["entry"], "nursery"
                elif family in state["niches"] and self.rng.random() < .5:
                    a, origin = state["niches"][family], "family_archive"
                    state["nursery"].pop(family, None)
                else:
                    a, origin = None, "fresh"
                    state["nursery"].pop(family, None)
            else:
                lane = self.rng.randrange(4)
                candidates = (state["reservoir"] if lane == 0 else list(state["descriptors"].values())
                              if lane == 1 else pool if lane == 2 else [])
                a = self.rng.choice(candidates) if candidates else None
                origin = ("reservoir", "descriptor_archive", "population", "fresh")[lane] if a else "fresh"
                family = a["genome"]["family"] if a else self.rng.choice(allowed)
            if a is None:
                parent = None
                child = ModelGenome(family=family, hidden_layers=(self.rng.choice([8, 16, 24, 32]),))
                op, parent_ids, baseline = "seed", [], -1e30
            else:
                parent = ModelGenome.model_validate(a["genome"])
                context = self.context_stats.get(f"{benchmark}:{parent.family}:crossover", {"ema": .5})
                if not protected and self.rng.random() < .2 + .6 * context["ema"]:
                    second = self.rng.choice(pool)
                    child = crossover(parent, ModelGenome.model_validate(second["genome"]), self.rng,
                                      task=task, broad=self.policy["broad"])
                    op, parent_ids = "crossover", [a["identity"], second["identity"]]
                    if child.genome_id == parent.genome_id:
                        child, op = mutate(parent, self.rng, allowed, task=task, broad=self.policy["broad"])
                        parent_ids = [a["identity"]]
                else:
                    child, op = mutate(parent, self.rng, allowed, family_locked=protected,
                                       task=task, broad=self.policy["broad"])
                    parent_ids = [a["identity"]]
                baseline = a["quality"]
            identities = {ModelGenome.model_validate(g).genome_id for g in children}
            if child.genome_id in identities:
                # Record the real fallback instead of claiming a structural change.
                while child.genome_id in identities:
                    child = ModelGenome.model_validate({**child.model_dump(), "learning_rate": 10 ** self.rng.uniform(-5, -1)})
                op = "lr"
            before = parent.model_dump() if parent else {}
            proposals[child.genome_id] = {"origin": origin, "operator": op, "parents": parent_ids,
                "changed_fields": [key for key, value in child.model_dump().items() if before.get(key) != value],
                "protected": protected}
            children.append(child.model_dump(mode="json"))
            parents[child.genome_id], operators[child.genome_id] = parent_ids, [op, baseline]
        state.update(population=children, cursor=0, generation=state["generation"] + 1, scores=[],
                     parents=parents, operators=operators, proposals=proposals)

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
            "research_variant": self.variant,
            "search_mode": "fixed_architectures" if self.fixed_genomes is not None else "adaptive",
            "context_operator_success": self.context_stats,
            "parent_origins": {k: s["parent_origins"] for k, s in self.benchmarks.items()},
            "exploration_occupancy": {k: {"reservoir": len(s["reservoir"]), "descriptors": len(s["descriptors"]),
                                         "nursery": len(s["nursery"])} for k, s in self.benchmarks.items()},
        }

    def state(self):
        return {
            "rng": self.rng.getstate(),
            "benchmarks": self.benchmarks,
            "operator_stats": self.operator_stats,
            "cache": self.cache.state(),
            "variant": self.variant,
            "context_stats": self.context_stats,
            "fixed_genomes": self.fixed_genomes,
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
