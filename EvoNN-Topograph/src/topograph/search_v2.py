"""Auditable exploration, bounded archives and parent-directed transfer."""

from collections import Counter
from copy import deepcopy
from random import Random
import numpy as np
from evonn_shared.weight_cache import WeightCache
from .genome import Innovations, OPERATORS, seed_genome
from .genome_v2 import GenomeV2
from .compiler_v2 import compile_genome, parameter_estimate
from .search import architecture_id, descriptor, species, tuples
from .operators import CORE, BROAD, edit, crossover, adapters, reachability_catalog, execution_topology
from .research import policy, lookup, take


class ResearchSearch:
    system = "topograph"

    def __init__(
        self,
        definitions,
        *,
        seed,
        population_size=4,
        state=None,
        benchmark_pooling=False,
        novelty_weight=0.0,
        variant="open",
    ):
        if not 2 <= population_size <= 16:
            raise ValueError("population must lie in [2,16]")
        self.variant = state["variant"] if state else variant
        self.policy = policy(self.variant)
        if self.variant == "legacy":
            raise ValueError("legacy search must use the v1 implementation")
        self.size, self.rng = population_size, Random(seed)
        self.reservoir_rng = Random(seed ^ 0xAE5E)
        self.definitions = {d.id: d for d in definitions}
        self.innovations = Innovations()
        self.cache = WeightCache(2 * population_size * len(definitions))
        self.ema, self.benchmarks, self.pool_scores = {}, {}, {}
        self.benchmark_pooling, self.novelty_weight = benchmark_pooling, novelty_weight
        self.progress, self.cache_history, self.training_ledger = 0.0, {}, {}
        self.inflight, self.pending_cache = {}, {}
        if state:
            if state.get("research_schema") != 2:
                raise ValueError("unsupported research search state")
            self.rng.setstate(tuples(state["rng"]))
            self.reservoir_rng.setstate(tuples(state["reservoir_rng"]))
            self.innovations = Innovations(**state["innovations"])
            self.cache = WeightCache(self.cache.capacity, state["cache"])
            self.ema = deepcopy(state["scheduler"])
            self.benchmarks = deepcopy(state["benchmarks"])
            self.pool_scores = deepcopy(state["pool_scores"])
            self.benchmark_pooling = state["benchmark_pooling"]
            self.novelty_weight = state["novelty_weight"]
            self.cache_history = deepcopy(state["cache_history"])
            self.training_ledger = deepcopy(state["training_ledger"])
            self.inflight = deepcopy(state["inflight"])
            self.pending_cache = deepcopy(state["pending_cache"])
            self.progress = state["progress"]
        else:
            for definition in definitions:
                population = [self.immigrant(definition, i) for i in range(self.size)]
                self.benchmarks[definition.id] = dict(
                    population=[g.model_dump(mode="json") for g in population],
                    cursor=0,
                    generation=0,
                    evaluated=0,
                    scores=[],
                    elite=None,
                    novelty=[],
                    operators={},
                    trace=[],
                    species=[],
                    proposals=[self.proposal_record("initial", fresh=True, protected=True) for _ in population],
                    records={},
                    reservoir=[],
                    seen=0,
                    source_cursor=0,
                    operator_cursor=0,
                    species_last={},
                    allocations=[],
                    events=[],
                    source_counts={},
                    revival_count=0,
                    quality_cells={},
                    behavior_cells={},
                    pareto=[],
                    credit_events=[],
                )

    def immigrant(self, definition, index):
        # Rotate all operator families; precision is sampled independently of family.
        operator = OPERATORS[index % len(OPERATORS)]
        genome = GenomeV2.model_validate(
            seed_genome(self.innovations, operator=operator, bits=self.rng.choice((1.58, 4, 8, 16))).model_dump()
        )
        if self.policy["broad"]:
            data = genome.model_dump()
            data["input_adapter"] = self.rng.choice(adapters(definition))
            genome = GenomeV2.model_validate(data)
        return genome

    @staticmethod
    def proposal_record(source, *, parents=(), fresh=False, protected=False, **details):
        return dict(
            source=source,
            parents=list(parents),
            fresh=fresh,
            protected=protected,
            requested=None,
            actual=None,
            topology_changed=False,
            preservation=None,
            **details,
        )

    def candidate(self, benchmark):
        s = self.benchmarks[benchmark]
        return GenomeV2.model_validate(s["population"][s["cursor"]])

    def proposal(self, benchmark):
        s = self.benchmarks[benchmark]
        return deepcopy(s["proposals"][s["cursor"]])

    def compile(self, genome, definition, **options):
        model = compile_genome(
            genome,
            definition.input_shape,
            definition.output_dim,
            definition.input_modality.value,
            definition.task_kind.value,
            **options,
        )
        model.benchmark_id = definition.id
        return model

    def inherit(self, model, benchmark, namespace):
        proposal = self.proposal(benchmark)
        empty = dict(mode="none", source=None, copied_parameters=0, ancestor_attempts=[], source_genome=None)
        if proposal["fresh"]:
            self.inflight[benchmark] = empty
            return empty
        if not self.policy["training"]:
            from .search import topology_id

            result = self.cache.inherit(
                model,
                namespace=namespace,
                identity=architecture_id(model.genome),
                topology=topology_id(model.genome),
                family=model.genome.genome_id,
            )
            key = namespace + ":" + str(result["source"])
            result.update(ancestor_attempts=lookup(self.cache_history, key, []), source_genome=None)
            self.inflight[benchmark] = deepcopy(result)
            return result
        records = self.benchmarks[benchmark]["records"]
        identity = architecture_id(model.genome)
        wanted = [identity] + [
            architecture_id(GenomeV2.model_validate(records[p]["genome"])) for p in proposal["parents"] if p in records
        ]
        for candidate in dict.fromkeys(wanted):
            key = namespace + ":" + candidate
            if key not in self.cache.entries:
                continue
            item = self.cache.entries[key]
            copied = 0
            widening = proposal["preservation"] == "zero_pad_widen" and candidate != identity
            for name, value in model.weights.items():
                if name not in item["weights"]:
                    continue
                old = np.asarray(item["weights"][name], dtype=np.float32)
                if old.ndim != value.ndim:
                    continue
                if old.shape == value.shape:
                    model.weights[name] = old.copy()
                    copied += old.size
                else:
                    overlap = tuple(slice(0, min(a, b)) for a, b in zip(old.shape, value.shape))
                    if widening:
                        model.weights[name] = np.zeros_like(value)
                    model.weights[name][overlap] = old[overlap]
                    copied += old[overlap].size
            if copied:
                self.cache.entries.move_to_end(key)
                result = dict(
                    mode="exact" if candidate == identity and copied == model.parameter_count else "partial",
                    source=candidate,
                    copied_parameters=copied,
                    source_genome=item["family"],
                    ancestor_attempts=list(lookup(self.cache_history, key, [])),
                )
                if proposal["preservation"] and candidate != identity and item["family"] in records:
                    parent = self.compile(
                        GenomeV2.model_validate(records[item["family"]]["genome"]),
                        self.definitions[benchmark],
                        backend=model.backend.name,
                        device=model.backend.device,
                        seed=0,
                    )
                    parent.weights = {k: np.asarray(v, dtype=np.float32) for k, v in item["weights"].items()}
                    rng = np.random.default_rng(0)
                    shape = (4, *self.definitions[benchmark].input_shape)
                    probe = (
                        rng.integers(0, model.output_dim, size=shape) if model.token_input else rng.normal(size=shape)
                    )
                    predictions = [
                        m.backend.numpy(
                            m.forward({k: m.backend.array(v) for k, v in m.weights.items()}, m.backend.array(probe))
                        )
                        for m in (parent, model)
                    ]
                    drift = float(np.max(np.abs(predictions[0] - predictions[1])))
                    scale = max(1, float(np.max(np.abs(predictions[0]))))
                    result["preservation_probe"] = dict(
                        absolute_drift=drift,
                        relative_drift=drift / scale,
                        passed=drift <= 1e-5 * scale,
                        source="synthetic_input_probe/v1",
                        scope="finite diagnostic, not a proof for all inputs",
                    )
                self.inflight[benchmark] = deepcopy(result)
                return result
        self.inflight[benchmark] = empty
        return empty

    def remember(self, model, namespace):
        from .search import topology_id

        self.cache.put(
            namespace,
            architecture_id(model.genome),
            topology_id(model.genome),
            model.genome.genome_id,
            model.weights,
            model.buffers,
        )
        self.cache_history = {k: v for k, v in self.cache_history.items() if k in self.cache.entries}
        self.pending_cache[model.benchmark_id] = namespace + ":" + architecture_id(model.genome)

    def vector(self, entry):
        genome = GenomeV2.model_validate(entry["genome"])
        structural = np.asarray(descriptor(genome), dtype=float) / np.array([32, 256, 128, 16, 1])
        operators = np.array(
            [sum(n.operator == op for n in genome.active_layers()) / len(genome.active_layers()) for op in OPERATORS]
        )
        return np.concatenate((structural, operators, np.asarray(entry.get("behavior", [0.0] * 16))))

    def archive_parent(self, benchmark, role):
        s = self.benchmarks[benchmark]
        records = s["records"]
        values = list(records.values())
        if role == "quality" or role == "fresh_control":
            return max(values, key=lambda e: e["quality"])
        if role == "reservoir":
            return records[self.reservoir_rng.choice(s["reservoir"])]
        if role == "uncertain":
            return min(values, key=lambda e: (e["evaluations"], e["last_selected"], e["identity"]))
        leaders = set(s["quality_cells"].values()) | set(s["behavior_cells"].values()) | set(s["pareto"])
        values = [records[g] for g in sorted(leaders)] or values
        # Novelty is separate from raw quality; task metrics never enter this distance.
        live = [records[g["identity"]] for g in s["scores"]]
        return max(
            values,
            key=lambda e: (
                min(float(np.linalg.norm(self.vector(e) - self.vector(v))) for v in live),
                -e["last_selected"],
            ),
        )

    def update_views(self, state):
        state["quality_cells"], state["behavior_cells"] = {}, {}
        valid = [e for e in state["records"].values() if e["status"] == "ok"]
        for entry in valid:
            genome = GenomeV2.model_validate(entry["genome"])
            d = descriptor(genome)
            families = tuple(sorted({n.operator for n in genome.active_layers()}))
            structural = repr((d[0] // 2, int(d[1]).bit_length(), families, genome.input_adapter))
            behavioral = repr(tuple(min(3, max(0, int((v + 1) * 2))) for v in entry["behavior"][:4]))
            for table, cell in ((state["quality_cells"], structural), (state["behavior_cells"], behavioral)):
                old = lookup(table, cell)
                if old is None or entry["quality"] > state["records"][old]["quality"]:
                    table[cell] = entry["identity"]
        state["pareto"] = [
            a["identity"]
            for a in valid
            if not any(
                b["quality"] >= a["quality"]
                and b["parameters"] <= a["parameters"]
                and (b["quality"] > a["quality"] or b["parameters"] < a["parameters"])
                for b in valid
            )
        ]

    def vary(self, benchmark, parent, mate):
        s = self.benchmarks[benchmark]
        child, cross = parent, "not_selected"
        if parent.genome_id != mate.genome_id and self.rng.random() < 0.25:
            child, cross = crossover(parent, mate, self.rng, self.innovations)
            if parameter_estimate(child, self.definitions[benchmark]) > 2_000_000:
                child, cross = parent, "resource_parameter_cap"
        names = list(CORE + (BROAD if self.policy["broad"] else ()))
        first = names[(s["operator_cursor"] // 3) % len(names)]
        # Round-robin proposals protect operator access; adaptive proposals supplement it.
        if s["operator_cursor"] % 3:
            first = self.rng.choices(names, [0.25 + lookup(self.ema, benchmark + ":" + op, 0.5) for op in names])[0]
        s["operator_cursor"] += 1
        remaining = [op for op in names if op != first]
        self.rng.shuffle(remaining)
        rejected = []
        for op in [first, *remaining]:
            result = edit(
                child, self.rng, self.innovations, op, self.definitions[benchmark], broad=self.policy["broad"]
            )
            if result is not None:
                candidate, detail = result
                if parameter_estimate(candidate, self.definitions[benchmark]) > 2_000_000:
                    rejected.append(op + ":resource_parameter_cap")
                    continue
                detail["mutation_topology_changed"] = detail["topology_changed"]
                detail["topology_changed"] = execution_topology(candidate) != execution_topology(parent)
                if cross == "branch_import":
                    detail["preservation"] = None
                return candidate, {**detail, "crossover": cross, "inapplicable": rejected}
            rejected.append(op)
        raise ValueError("no applicable registered mutation, including learning rate")

    def reproduce(self, benchmark):
        s = self.benchmarks[benchmark]
        population = [GenomeV2.model_validate(e["genome"]) for e in s["scores"]]
        groups = species(population)
        scores = [e["quality"] for e in s["scores"]]
        champion = max(range(len(scores)), key=scores.__getitem__)
        champion_group = next(g for g in groups if champion in g)
        # Reserving the champion reorders niches; it never overwrites an assigned slot.
        groups = [champion_group, *[g for g in groups if g is not champion_group]]
        role = None
        if self.policy["archive"]:
            roles = ("diversity", "uncertain", "reservoir", "immigrant", "fresh_control")
            role = roles[s["source_cursor"] % len(roles)]
            s["source_cursor"] += 1
        breeding_slots = self.size - int(role is not None)
        # When archive exploration needs a slot, defer a niche explicitly and rotate it.
        if role:
            groups = sorted(
                groups, key=lambda g: min(lookup(s["species_last"], population[i].genome_id, -1) for i in g)
            )
        children, proposals, allocated = [], [], []
        for slot in range(breeding_slots):
            group = groups[slot % len(groups)]
            index = max(group, key=scores.__getitem__)
            parent = population[index]
            for i in group:
                s["species_last"][population[i].genome_id] = s["generation"]
            allocated.append([population[i].genome_id for i in group])
            if index == champion and not role:
                child = parent
                proposal = self.proposal_record("champion", parents=[parent.genome_id])
            else:
                # Mates outside the current niche remain eligible, including archive discoveries.
                mate = self.rng.choice(population)
                child, details = self.vary(benchmark, parent, mate)
                proposal = self.proposal_record("species", parents=[parent.genome_id, mate.genome_id])
                proposal.update(details)
            children.append(child.model_dump(mode="json"))
            proposals.append(proposal)
        if role:
            if role == "immigrant":
                child = self.immigrant(self.definitions[benchmark], self.size + s["source_cursor"] // 5 - 1)
                proposal = self.proposal_record(role, fresh=True, protected=True)
            else:
                entry = self.archive_parent(benchmark, role)
                parent = GenomeV2.model_validate(entry["genome"])
                entry["last_selected"] = s["evaluated"]
                s["revival_count"] += parent.genome_id not in {g.genome_id for g in population}
                if role in ("uncertain", "fresh_control"):
                    child = parent
                    proposal = self.proposal_record(
                        role, parents=[parent.genome_id], protected=True, fresh=role == "fresh_control"
                    )
                else:
                    child, details = self.vary(benchmark, parent, population[champion])
                    proposal = self.proposal_record(
                        role, parents=[parent.genome_id, population[champion].genome_id], protected=True
                    )
                    proposal.update(details)
            children.append(child.model_dump(mode="json"))
            proposals.append(proposal)
        s["allocations"].append(
            dict(
                generation=s["generation"],
                allocated=allocated,
                deferred=[[population[i].genome_id for i in g] for g in groups[breeding_slots:]],
                archive_source=role,
            )
        )
        s.update(
            population=children,
            proposals=proposals,
            cursor=0,
            scores=[],
            generation=s["generation"] + 1,
            species=groups,
        )

    def observe(self, benchmark, genome, result):
        s = self.benchmarks[benchmark]
        proposal = self.proposal(benchmark)
        quality = result["score"] if result["status"] == "ok" else -1e30
        identity = genome.genome_id
        previous = lookup(s["records"], identity)
        entry = dict(
            genome=genome.model_dump(mode="json"),
            identity=identity,
            quality=quality,
            status=result["status"],
            adjusted=quality,
            novelty=0,
            behavior=result.get("behavior_descriptor", [0.0] * 16),
            evaluations=1,
            last_selected=s["evaluated"],
            last_attempt=s["evaluated"],
            parents=proposal["parents"],
            origin_operator=previous["origin_operator"] if previous else proposal["actual"],
            parameters=result.get("parameter_count", previous["parameters"] if previous else 0),
        )
        if previous:
            entry["evaluations"] += previous["evaluations"]
            entry["last_selected"] = previous["last_selected"]
            if previous["quality"] > quality:
                entry.update(quality=previous["quality"], behavior=previous["behavior"], status=previous["status"])
        else:
            s["seen"] += 1
            if len(s["reservoir"]) < 32:
                s["reservoir"].append(identity)
            else:
                index = self.reservoir_rng.randrange(s["seen"])
                if index < 32:
                    s["reservoir"][index] = identity
        s["records"][identity] = entry
        if self.policy["archive"]:
            self.update_views(s)
        # Attempt fitness remains its actual observation, not its historical maximum.
        s["scores"].append({**entry, "quality": quality, "status": result["status"]})
        if result["status"] == "ok" and (s["elite"] is None or quality > s["elite"]["quality"]):
            s["elite"] = deepcopy(entry)
            # Small, explicitly heuristic descendant credit supplements immediate success.
            pending, visited = list(proposal["parents"]), {identity}
            while pending and len(visited) < 9:
                ancestor, pending = pending[0], pending[1:]
                if ancestor in visited or ancestor not in s["records"]:
                    continue
                visited.add(ancestor)
                old = s["records"][ancestor]
                if old["origin_operator"]:
                    key = benchmark + ":" + old["origin_operator"]
                    self.ema[key] = 0.98 * lookup(self.ema, key, 0.5) + 0.02
                    s["credit_events"].append(
                        dict(
                            ancestor=ancestor,
                            descendant=identity,
                            operator=old["origin_operator"],
                            kind="descendant_gain_heuristic",
                        )
                    )
                pending.extend(old["parents"])
        s["novelty"] = (s["novelty"] + [descriptor(genome)])[-64:]
        s["trace"].append(identity)
        s["source_counts"][proposal["source"]] = lookup(s["source_counts"], proposal["source"], 0) + 1
        if proposal["actual"]:
            baselines = [s["records"][p]["quality"] for p in proposal["parents"] if p in s["records"]]
            if baselines:
                key = benchmark + ":" + proposal["actual"]
                self.ema[key] = 0.8 * lookup(self.ema, key, 0.5) + 0.2 * (quality > baselines[0])
        s["events"].append(
            {
                **proposal,
                "identity": identity,
                "status": result["status"],
                "outcome_id": result.get("outcome_id", f"{benchmark}:{s['evaluated']}"),
            }
        )
        inheritance = take(self.inflight, benchmark, {})
        attempt_id = result.get("outcome_id", f"{benchmark}:{s['evaluated']}")
        self.training_ledger[attempt_id] = {k: lookup(result, k, 0) for k in ("epochs", "updates", "train_seconds")}
        ancestry = sorted(set(inheritance.get("ancestor_attempts", []) + [attempt_id]))
        result["ancestral_training"] = {
            k: sum(self.training_ledger[a][k] for a in ancestry) for k in ("epochs", "updates", "train_seconds")
        }
        result["ancestral_training"]["attempts"] = ancestry
        key = take(self.pending_cache, benchmark, None)
        if result["status"] == "ok" and key in self.cache.entries:
            self.cache_history[key] = ancestry
        s["cursor"] += 1
        s["evaluated"] += 1
        if s["cursor"] == len(s["population"]):
            self.reproduce(benchmark)

    def telemetry(self):
        return dict(
            schema_version="1.0.0",
            system=self.system,
            topology_size={
                b: [descriptor(GenomeV2.model_validate(g)) for g in s["population"]] for b, s in self.benchmarks.items()
            },
            novelty_metrics={
                b: dict(archive_size=len(s["novelty"]), weight=self.novelty_weight) for b, s in self.benchmarks.items()
            },
            operator_success=self.ema,
            inheritance_entries=len(self.cache.entries),
            species={b: s["species"] for b, s in self.benchmarks.items()},
            generations={b: s["generation"] for b, s in self.benchmarks.items()},
            map_elites="multi_view_quality_cells/v2; scientifically_unqualified"
            if self.policy["archive"]
            else "disabled",
            benchmark_pooling=dict(enabled=self.benchmark_pooling, candidate_count=len(self.pool_scores)),
            research=dict(
                version=2,
                variant=self.variant,
                reachability=reachability_catalog(),
                archive={
                    b: dict(
                        retained_genomes=len(s["records"]),
                        reservoir=len(s["reservoir"]),
                        source_counts=s["source_counts"],
                        revivals=s["revival_count"],
                        structural_cells=len(s["quality_cells"]),
                        behavior_cells=len(s["behavior_cells"]),
                        pareto=len(s["pareto"]),
                        delayed_credit_events=len(s["credit_events"]),
                        effective_operations=dict(Counter(e["actual"] for e in s["events"] if e["actual"])),
                    )
                    for b, s in self.benchmarks.items()
                },
                retention="All evaluated genomes retained within the existing 256-attempt envelope; weights use bounded LRU.",
                descriptor="scaled_structure+operator_fractions+training_probe/v1; no protected-test data",
                qualification="experimental; no superiority claim",
            ),
        )

    def state(self):
        return {
            **deepcopy(
                dict(
                    research_schema=2,
                    variant=self.variant,
                    rng=self.rng.getstate(),
                    reservoir_rng=self.reservoir_rng.getstate(),
                    innovations=self.innovations.state(),
                    scheduler=self.ema,
                    benchmarks=self.benchmarks,
                    pool_scores=self.pool_scores,
                    benchmark_pooling=self.benchmark_pooling,
                    novelty_weight=self.novelty_weight,
                    progress=self.progress,
                    cache_history=self.cache_history,
                    training_ledger=self.training_ledger,
                    inflight=self.inflight,
                    pending_cache=self.pending_cache,
                )
            ),
            "cache": self.cache.state(),
        }
