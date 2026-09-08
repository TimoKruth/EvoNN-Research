"""Cheap archive mutation with measured-cost pressure and family leaders."""
from copy import deepcopy
from random import Random
from collections import Counter
from evonn_shared.weight_cache import WeightCache
from .genome import PrimitiveGenome, seed_genome, mutate, caps
from .compiler import compile_genome


def _tuples(value):
    return tuple(_tuples(item) for item in value) if isinstance(value, list) else value


class Search:
    system = 'primordia'
    worker_module = 'evonn_primordia.cli'
    evaluator_fidelity = 'end_to_end_primitive'

    def __init__(self, definitions, *, seed, population_size=4, state=None, budget=64):
        if not 2 <= population_size <= 16:
            raise ValueError('population size must be in [2,16]')
        self.rng, self.size, self.budget = Random(seed), population_size, budget
        self.definitions = {definition.id: definition for definition in definitions}
        self.cache = WeightCache(2*population_size*len(definitions))
        self.benchmarks, self.operator_stats = {}, {}
        if state is not None:
            state = deepcopy(state)
            self.rng.setstate(_tuples(state['rng']))
            self.benchmarks, self.operator_stats = state['benchmarks'], state['operator_stats']
            self.cache = WeightCache(2*population_size*len(definitions), state['cache'])
            self.budget = state['budget']
        else:
            for definition in definitions:
                self.benchmarks[definition.id] = dict(population=[seed_genome(i, definition.task_kind.value,
                    definition.input_modality.value).model_dump(mode='json') for i in range(population_size)],
                    cursor=0, generation=0, evaluated=0, archive=[], scores=[], parents={}, operators={}, lineage=[])

    def candidate(self, benchmark):
        state = self.benchmarks[benchmark]
        return PrimitiveGenome.model_validate(state['population'][state['cursor']])

    def compile(self, genome, definition, **options):
        return compile_genome(genome, definition.input_shape, definition.output_dim,
                              definition.input_modality.value, definition.task_kind.value, **options)

    def epoch_cap(self, benchmark):
        definition = self.definitions[benchmark]
        return caps(definition.task_kind.value, definition.input_modality.value,
                    self.benchmarks[benchmark]['evaluated'])['epochs']

    def inherit(self, model, benchmark, namespace):
        state = self.benchmarks[benchmark]
        identity = model.genome.genome_id
        parents = state['parents'][identity] if identity in state['parents'] else []
        return self.cache.inherit(model, namespace=namespace, identity=identity, topology='primitive',
            family=model.genome.family, parents=parents, compatible_groups=[model.genome.family])

    def remember(self, model, namespace):
        self.cache.put(namespace, model.genome.genome_id, 'primitive', model.genome.family, model.weights, model.buffers)

    def observe(self, benchmark, genome, result):
        state = self.benchmarks[benchmark]
        entry = dict(genome=genome.model_dump(mode='json'), identity=genome.genome_id,
            quality=result['score'] if result['status']=='ok' else -1e30,
            seconds=result.get('train_seconds', 120.), parameters=result.get('parameter_count', 0))
        state['scores'].append(entry)
        state['evaluated'] += 1
        state['cursor'] += 1
        if result['status'] == 'ok':
            unique = {item['identity']: item for item in state['archive']}
            if entry['identity'] not in unique or unique[entry['identity']]['quality'] < entry['quality']:
                unique[entry['identity']] = entry
            state['archive'] = sorted(unique.values(), key=lambda item: (-item['quality'], item['identity']))[:2*self.size]
        if genome.genome_id in state['operators']:
            operation, baseline = state['operators'][genome.genome_id]
            if operation not in self.operator_stats:
                self.operator_stats[operation] = dict(uses=0, successes=0)
            self.operator_stats[operation]['uses'] += 1
            self.operator_stats[operation]['successes'] += int(entry['quality'] > baseline)
        if state['cursor'] == self.size:
            self._reproduce(benchmark)

    def _reproduce(self, benchmark):
        state, definition = self.benchmarks[benchmark], self.definitions[benchmark]
        pool = state['archive'] or state['scores']
        qualities, costs = sorted(item['quality'] for item in pool), sorted(item['seconds'] for item in pool)
        children, parents, operators = [], {}, {}
        for _ in range(self.size):
            parent = self.rng.choice(pool)
            cheap = parent['quality'] <= qualities[len(qualities)//2] and parent['seconds'] >= costs[len(costs)//2]
            child, operation = mutate(PrimitiveGenome.model_validate(parent['genome']), self.rng,
                task=definition.task_kind.value, modality=definition.input_modality.value, cheap=cheap)
            children.append(child.model_dump(mode='json'))
            parents[child.genome_id] = [parent['identity']]
            operators[child.genome_id] = [operation, parent['quality']]
            state['lineage'].append(dict(child=child.genome_id, parents=[parent['identity']], operator=operation,
                                         generation=state['generation']+1))
        state.update(population=children, parents=parents, operators=operators, cursor=0,
                     generation=state['generation']+1, scores=[], lineage=state['lineage'][-256:])

    def telemetry(self):
        return dict(schema_version='1.0.0', system=self.system, evaluator_fidelity=self.evaluator_fidelity,
            primitive_usage={key: dict(Counter(node['operator'] for item in state['archive']
                for node in item['genome']['primitives'])) for key, state in self.benchmarks.items()},
            archive_size={key: len(state['archive']) for key, state in self.benchmarks.items()},
            lineage={key: state['lineage'] for key, state in self.benchmarks.items()},
            operator_success=self.operator_stats,
            epoch_caps={key: self.epoch_cap(key) for key in self.benchmarks},
            generations={key: state['generation'] for key, state in self.benchmarks.items()},
            evaluation_cache_hits=0, promotion_screen='disabled')

    def state(self):
        return dict(rng=self.rng.getstate(), benchmarks=self.benchmarks, operator_stats=self.operator_stats,
                    cache=self.cache.state(), budget=self.budget)
