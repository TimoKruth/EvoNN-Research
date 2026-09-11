"""Cheap archive mutation with deterministic work-cost pressure and family leaders."""

from copy import deepcopy
from random import Random
from collections import Counter
import math
from evonn_shared.weight_cache import WeightCache
from .genome import PrimitiveGenome, seed_genome, mutate, caps, fresh_genome, mutate_broad
from .compiler import compile_genome


def work_cost(parameter_count, updates):
    """Deterministic work proxy; measured seconds remain in the attempt ledger."""
    if any(type(value) is not int or value <= 0 for value in (parameter_count, updates)):
        raise ValueError("positive parameter and optimizer-update counts required")
    return parameter_count * updates


def _tuples(value):
    return tuple(_tuples(item) for item in value) if isinstance(value, list) else value


class Search:
    system = "primordia"
    worker_module = "evonn_primordia.cli"
    evaluator_fidelity = "end_to_end_primitive"

    def __init__(self, definitions, *, seed, population_size=4, state=None, budget=64,
                 search_policy="breadth_v2", max_width=48, max_depth=8, training_epochs=12):
        if not 2 <= population_size <= 16:
            raise ValueError("population size must be in [2,16]")
        self.rng, self.size, self.budget = Random(seed), population_size, budget
        if state is not None:
            search_policy = state.get("search_policy", "legacy_v1")
            max_width, max_depth = state.get("max_width", 24), state.get("max_depth", 4)
            training_epochs = state.get("training_epochs", 12)
        if search_policy not in {"legacy_v1", "breadth_v2"}:
            raise ValueError("unknown search policy")
        if type(max_width) is not int or not 2 <= max_width <= 256 or type(max_depth) is not int or not 1 <= max_depth <= 32:
            raise ValueError("invalid explicit architecture envelope")
        self.policy, self.max_width, self.max_depth = search_policy, max_width, max_depth
        if type(training_epochs) is not int or not 1 <= training_epochs <= 1000:
            raise ValueError("invalid training envelope")
        self.training_epochs = training_epochs
        self.definitions = {definition.id: definition for definition in definitions}
        self.cache = WeightCache(2 * population_size * len(definitions))
        self.cache_quality = {}
        self.benchmarks, self.operator_stats = {}, {}
        if state is not None:
            state = deepcopy(state)
            self.rng.setstate(_tuples(state["rng"]))
            self.benchmarks, self.operator_stats = state["benchmarks"], state["operator_stats"]
            self.cache = WeightCache(2 * population_size * len(definitions), state["cache"])
            self.cache_quality = state.get("cache_quality", {})
            self.budget = state["budget"]
        else:
            for definition in definitions:
                self.benchmarks[definition.id] = dict(
                    population=[
                        (fresh_genome(self.rng, max_width=max_width, max_depth=max_depth, founder=i)
                         if self.policy == "breadth_v2" else
                         seed_genome(i, definition.task_kind.value, definition.input_modality.value)).model_dump(mode="json")
                        for i in range(population_size)
                    ],
                    cursor=0,
                    generation=0,
                    evaluated=0,
                    archive=[],
                    scores=[],
                    parents={},
                    operators={},
                    lineage=[],
                )
                if self.policy == "breadth_v2":
                    self.benchmarks[definition.id].update(
                        young=[], reservoir=[], novelty=[], pareto=[], seen=0,
                        proposal_meta=[dict(lane="founder", fresh=True, parents=[], operator="founder", baseline=None)
                                       for _ in range(self.size)],
                        exploration=dict(lanes={}, structural_changes=0, structure_unchanged=0,
                                         resource_deferred=0, failed=0, boundary_proposals=0),
                    )

    def candidate(self, benchmark):
        state = self.benchmarks[benchmark]
        return PrimitiveGenome.model_validate(state["population"][state["cursor"]])

    def compile(self, genome, definition, **options):
        return compile_genome(
            genome,
            definition.input_shape,
            definition.output_dim,
            definition.input_modality.value,
            definition.task_kind.value,
            **options,
        )

    def epoch_cap(self, benchmark):
        if self.policy == "breadth_v2":
            return self.training_epochs
        definition = self.definitions[benchmark]
        return caps(
            definition.task_kind.value, definition.input_modality.value, self.benchmarks[benchmark]["evaluated"]
        )["epochs"]

    def inherit(self, model, benchmark, namespace):
        state = self.benchmarks[benchmark]
        identity = model.genome.genome_id
        if self.policy == "breadth_v2":
            meta = self.proposal(benchmark)
            if meta["fresh"]:
                return dict(mode="none", source=None, copied_parameters=0)
            parents = meta["parents"]
            if not any(namespace + ":" + candidate in self.cache.entries for candidate in [identity, *parents]):
                # An evicted lineage gets a fresh fit, never unrelated cached weights.
                return dict(mode="none", source=None, copied_parameters=0)
        else:
            parents = state["parents"][identity] if identity in state["parents"] else []
        return self.cache.inherit(
            model,
            namespace=namespace,
            identity=identity,
            topology="primitive",
            family=model.genome.family,
            parents=parents,
            compatible_groups=[model.genome.family],
        )

    def remember(self, model, namespace, result=None):
        key = namespace + ":" + model.genome.genome_id
        if self.policy == "breadth_v2" and result is not None:
            if key in self.cache.entries and result["score"] <= (self.cache_quality[key] if key in self.cache_quality else -math.inf):
                return
        self.cache.put(
            namespace, model.genome.genome_id, "primitive", model.genome.family, model.weights, model.buffers
        )
        if self.policy == "breadth_v2" and result is not None:
            self.cache_quality[key] = result["score"]
            self.cache_quality = {k: v for k, v in self.cache_quality.items() if k in self.cache.entries}

    def observe(self, benchmark, genome, result):
        state = self.benchmarks[benchmark]
        entry = dict(
            genome=genome.model_dump(mode="json"),
            identity=genome.genome_id,
            quality=result["score"] if result["status"] == "ok" else -1e30,
            cost_units=work_cost(result["parameter_count"], result["updates"]) if result["status"] == "ok" else 0,
            parameters=result.get("parameter_count", 0),
        )
        if self.policy == "breadth_v2":
            entry["behavior"] = result.get("behavior_descriptor", [])
            entry["birth"] = state["evaluated"]
            self._retain_broad(benchmark, state, entry, result)
        state["scores"].append(entry)
        state["evaluated"] += 1
        state["cursor"] += 1
        if result["status"] == "ok":
            unique = {item["identity"]: item for item in state["archive"]}
            if entry["identity"] not in unique or unique[entry["identity"]]["quality"] < entry["quality"]:
                unique[entry["identity"]] = entry
            state["archive"] = sorted(unique.values(), key=lambda item: (-item["quality"], item["identity"]))[
                : 2 * self.size
            ]
        if self.policy == "legacy_v1" and genome.genome_id in state["operators"]:
            operation, baseline = state["operators"][genome.genome_id]
            if operation not in self.operator_stats:
                self.operator_stats[operation] = dict(uses=0, successes=0)
            self.operator_stats[operation]["uses"] += 1
            self.operator_stats[operation]["successes"] += int(entry["quality"] > baseline)
        if state["cursor"] == self.size:
            self._reproduce(benchmark)

    def _reproduce(self, benchmark):
        if self.policy == "breadth_v2":
            return self._reproduce_broad(benchmark)
        state, definition = self.benchmarks[benchmark], self.definitions[benchmark]
        pool = state["archive"] or state["scores"]
        qualities, costs = sorted(item["quality"] for item in pool), sorted(item["cost_units"] for item in pool)
        children, parents, operators = [], {}, {}
        for _ in range(self.size):
            parent = self.rng.choice(pool)
            cheap = (
                parent["quality"] <= qualities[len(qualities) // 2] and parent["cost_units"] >= costs[len(costs) // 2]
            )
            child, operation = mutate(
                PrimitiveGenome.model_validate(parent["genome"]),
                self.rng,
                task=definition.task_kind.value,
                modality=definition.input_modality.value,
                cheap=cheap,
            )
            children.append(child.model_dump(mode="json"))
            parents[child.genome_id] = [parent["identity"]]
            operators[child.genome_id] = [operation, parent["quality"]]
            state["lineage"].append(
                dict(
                    child=child.genome_id,
                    parents=[parent["identity"]],
                    operator=operation,
                    generation=state["generation"] + 1,
                )
            )
        state.update(
            population=children,
            parents=parents,
            operators=operators,
            cursor=0,
            generation=state["generation"] + 1,
            scores=[],
            lineage=state["lineage"][-256:],
        )

    def proposal(self, benchmark):
        state = self.benchmarks[benchmark]
        return deepcopy(state["proposal_meta"][state["cursor"]]) if self.policy == "breadth_v2" else {}

    @staticmethod
    def _distance(left, right):
        a, b = left.get("behavior", []), right.get("behavior", [])
        if a and len(a) == len(b):
            return sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)
        ga, gb = left["genome"], right["genome"]
        return (abs(math.log2(ga["width"] / gb["width"])) + abs(len(ga["primitives"]) - len(gb["primitives"]))
                + float(ga["primitives"] != gb["primitives"]))

    def _retain_broad(self, benchmark, state, entry, result):
        meta = self.proposal(benchmark)
        stats = state["exploration"]
        lane = meta["lane"]
        stats["lanes"][lane] = (stats["lanes"][lane] if lane in stats["lanes"] else 0) + 1
        if "structural_change" in meta:
            stats["structural_changes" if meta["structural_change"] else "structure_unchanged"] += 1
        stats["boundary_proposals"] += int(entry["genome"]["width"] == self.max_width
                                             or len(entry["genome"]["primitives"]) == self.max_depth)
        stats["failed"] += int(result["status"] != "ok")
        reason = result.get("reason") or ""
        stats["resource_deferred"] += int(result["status"] != "ok" and any(
            word in reason.lower() for word in ("cap", "timeout", "time limit", "memory")))
        # A score-independent reservoir also preserves failed candidates for retries.
        state["seen"] += 1
        if len(state["reservoir"]) < 8 * self.size:
            state["reservoir"].append(entry)
        else:
            index = self.rng.randrange(state["seen"])
            if index < len(state["reservoir"]):
                state["reservoir"][index] = entry
        state["young"] = (state["young"] + [entry])[-2 * self.size:]
        if result["status"] == "ok":
            unique = {item["identity"]: item for item in state["novelty"] + [entry]}
            remaining = list(unique.values())
            selected = [max(remaining, key=lambda item: (item["quality"], item["identity"]))]
            remaining.remove(selected[0])
            while remaining and len(selected) < 2 * self.size:
                pick = max(remaining, key=lambda item: (min(self._distance(item, other) for other in selected),
                                                        item["quality"], item["identity"]))
                selected.append(pick)
                remaining.remove(pick)
            state["novelty"] = selected
            pool = list({item["identity"]: item for item in state["pareto"] + [entry]}.values())
            front = [item for item in pool if not any(
                other["quality"] >= item["quality"] and other["cost_units"] <= item["cost_units"]
                and (other["quality"] > item["quality"] or other["cost_units"] < item["cost_units"])
                for other in pool)]
            front.sort(key=lambda item: (item["cost_units"], -item["quality"], item["identity"]))
            if len(front) > 2 * self.size:
                front = [front[round(i * (len(front) - 1) / (2 * self.size - 1))] for i in range(2 * self.size)]
            state["pareto"] = front
        operation = meta["operator"]
        if operation not in self.operator_stats:
            self.operator_stats[operation] = dict(uses=0, successes=0, descendant_improvements=0)
        counts = self.operator_stats[operation]
        counts["uses"] += 1
        counts["successes"] += int(meta["baseline"] is not None and entry["quality"] > meta["baseline"])
        ancestors = set(meta["parents"])
        for link in reversed(state["lineage"]):
            if link["child"] in ancestors:
                ancestors.remove(link["child"])
                ancestors.update(link["parents"])
                if link.get("baseline") is not None and entry["quality"] > link["baseline"]:
                    prior = self.operator_stats[link["operator"]] if link["operator"] in self.operator_stats else None
                    if prior is not None:
                        prior["descendant_improvements"] += 1
        state["lineage"].append(dict(child=entry["identity"], parents=meta["parents"], operator=meta["operator"],
                                     generation=state["generation"], baseline=meta["baseline"], lane=meta["lane"]))
        state["lineage"] = state["lineage"][-256:]

    def _reproduce_broad(self, benchmark):
        state = self.benchmarks[benchmark]
        # Guaranteed recurring opportunities, independent of current quality.
        lanes = ("quality", "novelty", "young", "reservoir", "fresh", "patient", "fresh_retrain", "cost")
        children, metadata = [], []
        for i in range(self.size):
            lane = lanes[(state["evaluated"] - self.size + i) % len(lanes)]
            pools = {"quality": state["archive"], "novelty": state["novelty"], "young": state["young"],
                    "reservoir": state["reservoir"], "patient": state["reservoir"],
                    "fresh_retrain": state["archive"], "cost": state["pareto"]}
            pool = pools[lane] if lane in pools else []
            if not pool or lane == "fresh":
                child = fresh_genome(self.rng, max_width=self.max_width, max_depth=self.max_depth)
                meta = dict(lane="fresh", fresh=True, parents=[], operator="restart", baseline=None)
            else:
                parent = self.rng.choice(pool)
                original = PrimitiveGenome.model_validate(parent["genome"])
                if lane in {"patient", "fresh_retrain"}:
                    child, operation = original, lane
                else:
                    child, operation = mutate_broad(original, self.rng, max_width=self.max_width, max_depth=self.max_depth)
                structural = any(child.model_dump()[key] != original.model_dump()[key]
                                 for key in ("width", "primitives", "sources", "sparse_offsets", "temporal_mode", "temporal_lag"))
                meta = dict(lane=lane, fresh=lane == "fresh_retrain", parents=[parent["identity"]],
                            operator=operation, baseline=parent["quality"], structural_change=structural)
            children.append(child.model_dump(mode="json"))
            metadata.append(meta)
        state.update(population=children, proposal_meta=metadata, cursor=0, generation=state["generation"] + 1,
                     scores=[], lineage=state["lineage"][-256:])

    def telemetry(self):
        result = dict(
            schema_version="1.0.0",
            system=self.system,
            evaluator_fidelity=self.evaluator_fidelity,
            primitive_usage={
                key: dict(
                    Counter(node["operator"] for item in state["archive"] for node in item["genome"]["primitives"])
                )
                for key, state in self.benchmarks.items()
            },
            archive_size={key: len(state["archive"]) for key, state in self.benchmarks.items()},
            lineage={key: state["lineage"] for key, state in self.benchmarks.items()},
            operator_success=self.operator_stats,
            epoch_caps={key: self.epoch_cap(key) for key in self.benchmarks},
            generations={key: state["generation"] for key, state in self.benchmarks.items()},
            evaluation_cache_hits=0,
            promotion_screen="disabled",
        )
        if self.policy == "breadth_v2":
            result.update(search_policy=self.policy, architecture_envelope=dict(max_width=self.max_width, max_depth=self.max_depth),
                          exploration={key: {**state["exploration"],
                              "retention_sizes": {name: len(state[name]) for name in ("archive", "young", "novelty", "reservoir", "pareto")},
                              "behavior_diversity": (sum(self._distance(a, b) for i, a in enumerate(state["novelty"])
                                                         for b in state["novelty"][i + 1:])
                                                     / max(1, len(state["novelty"]) * (len(state["novelty"]) - 1) / 2))}
                                       for key, state in self.benchmarks.items()})
        return result

    def state(self):
        result = dict(
            rng=self.rng.getstate(),
            benchmarks=self.benchmarks,
            operator_stats=self.operator_stats,
            cache=self.cache.state(),
            budget=self.budget,
        )
        if self.policy == "breadth_v2":
            result.update(search_policy=self.policy, max_width=self.max_width, max_depth=self.max_depth,
                          training_epochs=self.training_epochs, cache_quality=self.cache_quality)
        return result
