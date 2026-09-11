"""Protected exploration, archive revival, and representation-aware inheritance."""
from copy import deepcopy
import math
import numpy as np
from .genome import HierarchicalGenome, CellGene
from .operators import OPERATORS
from .genome_v2 import seed, mutate, recombine

# Fixed rotating slots protect exploration even when quality selection is strong.
# quality-only is an explicit ablation; the ordinary policy never disables a lane.
LANES = ('quality', 'niche', 'novelty', 'fresh', 'quality', 'revisit_random',
         'niche', 'revisit_uncertain', 'fresh', 'novelty', 'revisit_promising', 'reservoir')


def fresh(search, benchmark, index):
    definition = search.definitions[benchmark]
    policy = search.research.model_dump(mode='json')
    policy['_image'] = definition.input_modality.value == 'image'
    return seed(definition.task_kind.value, math.prod(definition.input_shape), search.rng,
                policy=policy, variant=search.variant, index=index)


def initialize(search):
    for benchmark, state in search.benchmarks.items():
        state.update(population=[fresh(search, benchmark, i).model_dump(mode='json') for i in range(search.size)],
                     reservoir=[], arrivals=0, selection_counts={}, proposal_metadata=[{'lane': 'initial', 'parents': [], 'operator': 'seed'} for _ in range(search.size)])
    search.parameter_maps = {}


def metadata(search, benchmark):
    state = search.benchmarks[benchmark]
    return state['proposal_metadata'][state['cursor']]


def observe(search, benchmark, genome, result):
    state = search.benchmarks[benchmark]
    info = metadata(search, benchmark)
    previous = next((entry for entry in state['reservoir'] if entry['identity'] == genome.genome_id), None)
    entry = dict(genome=genome.model_dump(mode='json'), identity=genome.genome_id,
                 quality=result['score'] if result['status'] == 'ok' else -1e30,
                 parameters=result.get('parameter_count', 0), behavior=result.get('behavior', []),
                 observations=1 + (previous['observations'] if previous else 0))
    state['scores'].append(entry)
    state['selection_counts'][info['lane']] = (state['selection_counts'][info['lane']] if info['lane'] in state['selection_counts'] else 0) + 1
    state['cursor'] += 1
    state['evaluated'] += 1
    if result['status'] == 'ok':
        size = search.research.archive_size
        unique = {item['identity']: item for item in state['archive']}
        if genome.genome_id not in unique or entry['quality'] > unique[genome.genome_id]['quality']:
            unique[genome.genome_id] = entry
        state['archive'] = sorted(unique.values(), key=lambda item: (-item['quality'], item['identity']))[:max(2, size//4)]
        state['arrivals'] += 1
        if previous is not None:
            state['reservoir'] = [entry if item['identity'] == entry['identity'] else item for item in state['reservoir']]
        elif len(state['reservoir']) < size:
            state['reservoir'].append(entry)
        else:
            position = search.rng.randrange(state['arrivals'])
            if position < size:
                state['reservoir'][position] = entry
        niche = f'{genome.macro_depth}:{round(genome.reuse_ratio, 1)}:{genome.max_cell_depth}'
        if niche not in state['niches'] or entry['quality'] > state['niches'][niche]['quality']:
            state['niches'][niche] = entry
        if len(state['niches']) > size:
            # No global-quality eviction of niches: memory pressure is not a fitness judgement.
            del state['niches'][search.rng.choice(sorted(state['niches']))]
    if info['operator'] not in search.operator_stats:
        search.operator_stats[info['operator']] = dict(uses=0, successes=0)
    stats = search.operator_stats[info['operator']]
    stats['uses'] += 1
    stats['successes'] += int(result['status'] == 'ok' and 'baseline' in info and entry['quality'] > info['baseline'])
    if state['cursor'] == search.size:
        reproduce(search, benchmark)


def novelty(entry, pool):
    behavior = np.asarray(entry['behavior'], dtype=float)
    distances = [float(np.linalg.norm(behavior - other['behavior'])) for other in pool
                 if other['identity'] != entry['identity'] and len(other['behavior']) == len(behavior) and len(behavior)]
    return min(distances) if distances else 0.0


def reproduce(search, benchmark):
    state = search.benchmarks[benchmark]
    available = {entry['identity']: entry for group in (state['scores'], state['reservoir'], list(state['niches'].values()), state['archive']) for entry in group}
    pool = sorted(available.values(), key=lambda entry: entry['identity'])
    children, infos, parents, operators = [], [], {}, {}
    for slot in range(search.size):
        lane = LANES[(state['generation'] * search.size + slot) % len(LANES)] if search.research.selection == 'diverse' else 'quality'
        info = dict(lane=lane, parents=[], operator='seed', crossover=False)
        if lane == 'fresh':
            child = fresh(search, benchmark, search.rng.randrange(search.research.max_macro_nodes))
        else:
            if lane == 'niche':
                candidates = list(state['niches'].values()) or pool
            elif lane in ('reservoir', 'revisit_random', 'revisit_uncertain', 'novelty'):
                candidates = state['reservoir'] or pool
            else:
                candidates = state['archive'] or pool
            if lane == 'novelty':
                # Sample among the most distinct; deterministic identity breaks ties.
                ranked = sorted(candidates, key=lambda entry: (-novelty(entry, pool), entry['identity']))
                parent = search.rng.choice(ranked[:max(1, len(ranked)//4)])
            elif lane == 'revisit_uncertain':
                minimum = min(entry['observations'] for entry in candidates)
                parent = search.rng.choice([entry for entry in candidates if entry['observations'] == minimum])
            elif lane in ('quality', 'revisit_promising'):
                parent = max(search.rng.sample(candidates, min(2, len(candidates))), key=lambda entry: entry['quality'])
            else:
                parent = search.rng.choice(candidates)
            child = HierarchicalGenome.model_validate(parent['genome'])
            info.update(parents=[parent['identity']], baseline=parent['quality'])
            if lane.startswith('revisit_'):
                info['operator'] = lane
            else:
                if search.rng.random() < .5:
                    donor = search.rng.choice(pool)
                    child = recombine(child, HierarchicalGenome.model_validate(donor['genome']), search.rng)
                    info['parents'].append(donor['identity'])
                    info['crossover'] = True
                motifs = [CellGene.model_validate(cell) for entry in pool for cell in entry['genome']['cells']]
                child, info['operator'] = mutate(child, search.rng, motif_bank=motifs)
        children.append(child.model_dump(mode='json'))
        infos.append(info)
        parents[child.genome_id] = info['parents']
        operators[child.genome_id] = [info['operator'], info.get('baseline', -1e30)]
        state['lineage'].append(dict(child=child.genome_id, parents=info['parents'], operator=info['operator'],
                                     lane=lane, crossover=info['crossover'], generation=state['generation']+1))
    state.update(population=children, proposal_metadata=infos, cursor=0, generation=state['generation']+1,
                 scores=[], parents=parents, operators=operators)
    state['lineage'] = state['lineage'][-256:]


def inherit(search, model, benchmark, namespace):
    mode = search.research.inheritance
    if mode == 'fresh':
        return dict(mode='none', source=None, copied_parameters=0)
    info = metadata(search, benchmark)
    candidates = [(key, item) for key, item in search.cache.entries.items()
                  if item['namespace'] == namespace and item['identity'] in search.parameter_maps]
    candidates.sort(key=lambda pair: (pair[1]['identity'] == model.genome.genome_id,
                                      pair[1]['identity'] in info['parents']), reverse=True)
    for key, item in candidates:
        mapping = search.parameter_maps[item['identity']]
        remapping = {}
        origins = {cell.parameter_id: cell.origin_parameter_id for cell in model.genome.cells}
        for name, signature in model.parameter_signatures.items():
            if name not in model.weights:
                continue
            parts = name.split('.')
            origin = origins[parts[1]] if parts[1] in origins else None
            inherited_name = '.'.join([parts[0], origin, *parts[2:]]) if origin else None
            for source in (name, inherited_name):
                if source is not None and source in item['weights'] and source in mapping['parameters'] and mapping['parameters'][source] == signature:
                    if np.asarray(item['weights'][source]).shape == model.weights[name].shape:
                        remapping[name] = source
                        break
        all_cells = all(key in remapping for key in model.weights if key.startswith('cell.'))
        same_features = all_cells and model.representation_signature(remapping) == mapping['feature_signature']
        exact = item['identity'] == model.genome.genome_id
        copied = 0
        for name, value in model.weights.items():
            source = (remapping[name] if name in remapping else None) if name.startswith('cell.') else (name if same_features or mode == 'head_diagnostic' else None)
            if source is not None and source in item['weights']:
                old = np.asarray(item['weights'][source], dtype=np.float32)
                if old.shape == value.shape:
                    model.weights[name] = old.copy()
                    copied += old.size
        if copied:
            if same_features:
                model.buffers = {k: tuple(np.asarray(v, dtype=np.float32) for v in values) for k, values in item['buffers'].items()}
                model.reuse_feature_statistics = True
            search.cache.entries.move_to_end(key)
            return dict(mode='exact' if exact and copied == model.parameter_count else 'partial',
                        source=item['identity'], copied_parameters=copied)
    return dict(mode='none', source=None, copied_parameters=0)


def remember(search, model, namespace):
    search.cache.put(namespace, model.genome.genome_id, model.evaluator_fidelity, model.genome.profile, model.weights, model.buffers)
    search.parameter_maps[model.genome.genome_id] = dict(feature_signature=model.feature_signature,
                                                        parameters=deepcopy(model.parameter_signatures))
    retained = {item['identity'] for item in search.cache.entries.values()}
    search.parameter_maps = {key: value for key, value in search.parameter_maps.items() if key in retained}


def telemetry(search):
    return dict(policy_version=2, selection_policy=search.research.selection,
                protected_cycle=list(LANES) if search.research.selection == 'diverse' else [],
                selection_counts={key: state['selection_counts'] for key, state in search.benchmarks.items()},
                reservoir_occupancy={key: len(state['reservoir']) for key, state in search.benchmarks.items()},
                registered_primitives=sorted(OPERATORS),
                promotion_screen='disabled' if not search.research.screen_epochs else 'charged_archive_revisits')
