"""Bidirectional hierarchy edits and persistent projection initialization identities."""
from .genome import (HierarchicalGenome, CellGene, CellNodeGene, MacroNodeGene, Edge,
                     seed_genome, clone_cell, specialize, crossover, order, _construct)
from .operators import OPERATORS
from .research import ResearchPolicy


def seed(task, input_dim, rng, *, policy, variant='shared', index=0):
    # Profiles bias initial programs; every registered primitive remains mutable.
    old = seed_genome(task, input_dim, modality='image' if policy.pop('_image', False) else 'tabular',
                      variant=variant, index=index)
    settings = ResearchPolicy.model_validate(policy)
    data = old.model_dump(mode='json')
    data.update(schema_version=2, execution=settings.model_dump(mode='json'))
    projection_seeds = {}
    for cell in data['cells']:
        cell['parameter_id'] = f'{rng.randrange(2**64):016x}'
        cell['nodes'] = cell['nodes'][:settings.max_cell_nodes]
        ids = {n['id'] for n in cell['nodes']}
        cell['edges'] = [e for e in cell['edges'] if e['source'] in ids and e['target'] in ids]
        cell['output'] = cell['nodes'][-1]['id']
        for node in cell['nodes']:
            # Unsharing alone retains the same initial functions as sharing.
            signature = (node['id'], node['width'], node['activation'], node['primitive'])
            if signature not in projection_seeds:
                projection_seeds[signature] = rng.randrange(2**32)
            node.update(width=min(node['width'], settings.max_width), projection_seed=projection_seeds[signature])
    # Cover shallow and deeper starts in the ordinary shared search itself.
    count = 1 if variant == 'flat' else 1 + index % min(3, settings.max_macro_nodes)
    library = data['cells']
    data['macro_nodes'] = [{'id': f'm{i}', 'cell_id': library[min(i, len(library)-1)]['id'] if variant == 'unshared' else library[0]['id']} for i in range(count)]
    if variant == 'unshared':
        # The seed may need more distinct cells than the legacy profile supplied.
        data['cells'] = [{**library[min(i, len(library)-1)], 'id': f'cell{i}', 'parameter_id': f'{rng.randrange(2**64):016x}'} for i in range(count)]
        data['macro_nodes'] = [{'id': f'm{i}', 'cell_id': f'cell{i}'} for i in range(count)]
    used = {n['cell_id'] for n in data['macro_nodes']}
    data['cells'] = [c for c in data['cells'] if c['id'] in used]
    data['macro_edges'] = [{'source': f'm{i}', 'target': f'm{i+1}'} for i in range(count-1)]
    data['output'] = f'm{count-1}'
    return HierarchicalGenome.model_validate(data)


def collapse(genome, node_id):
    node = next(n for n in genome.macro_nodes if n.id == node_id)
    return _construct(genome, macro_nodes=[MacroNodeGene(id='m0', cell_id=node.cell_id)], macro_edges=[], output='m0')


def contract(genome, node_id):
    if len(genome.macro_nodes) == 1:
        return genome
    ordered, incoming, _ = order(genome.macro_nodes, genome.macro_edges, genome.output)
    if node_id == genome.output:
        return collapse(genome, incoming[node_id][-1])
    edges = {(e.source, e.target) for e in genome.macro_edges if node_id not in (e.source, e.target)}
    successors = [e.target for e in genome.macro_edges if e.source == node_id]
    edges.update((a, b) for a in incoming[node_id] for b in successors)
    return _construct(genome, macro_nodes=[n for n in genome.macro_nodes if n.id != node_id],
                      macro_edges=[Edge(source=a, target=b) for a, b in sorted(edges)])


def mutate(genome, rng, *, motif_bank=(), operation=None):
    policy = ResearchPolicy.model_validate(genome.execution)
    operations = ['activation', 'specialize', 'projection-randomize', 'width', 'primitive',
                  'cell-grow', 'cell-prune', 'cell-rewire', 'head', 'representation', 'optimizer']
    if genome.variant != 'flat':
        operations += ['expand', 'contract', 'collapse', 'skip', 'rewire']
    if genome.variant not in ('unshared', 'flat', 'no-clone'):
        operations += ['clone', 'share']
    if motif_bank and genome.variant != 'no-motif-bias':
        operations += ['motif']
    if not policy.evolve_representation:
        operations.remove('representation')
        operations.remove('head')
    op = rng.choice(operations) if operation is None else operation
    if op not in operations:
        raise ValueError('operator is unavailable for this variant')
    cell = rng.choice(genome.cells)
    if op in ('activation', 'specialize'):
        return specialize(genome, cell.id, rng), op
    if op == 'collapse':
        return collapse(genome, rng.choice(genome.macro_nodes).id), op
    if op == 'contract':
        return contract(genome, rng.choice(genome.macro_nodes).id), op
    if op == 'clone':
        return clone_cell(genome, rng.choice(genome.macro_nodes).id), op
    if op == 'share':
        node = rng.choice(genome.macro_nodes)
        return _construct(genome, macro_nodes=[MacroNodeGene(id=n.id, cell_id=cell.id) if n == node else n for n in genome.macro_nodes]), op
    if op == 'expand':
        if len(genome.macro_nodes) >= policy.max_macro_nodes:
            return genome, op
        identity = next(f'm{i}' for i in range(9) if f'm{i}' not in {n.id for n in genome.macro_nodes})
        # Temporarily shared so unshared expansion can clone the new reference.
        child = _construct(genome, variant='shared' if genome.variant == 'unshared' else genome.variant,
                           macro_nodes=[*genome.macro_nodes, MacroNodeGene(id=identity, cell_id=cell.id)],
                           macro_edges=[*genome.macro_edges, Edge(source=genome.output, target=identity)], output=identity)
        if genome.variant == 'unshared':
            child = clone_cell(child, identity)
            child = _construct(child, variant='unshared')
        return child, op
    if op in ('skip', 'rewire', 'cell-rewire'):
        is_cell = op == 'cell-rewire'
        nodes, edges, output = (cell.nodes, cell.edges, cell.output) if is_cell else (genome.macro_nodes, genome.macro_edges, genome.output)
        ordered = order(nodes, edges, output)[0]
        pairs = {(e.source, e.target) for e in edges}
        candidates = []
        for i, a in enumerate(ordered):
            for b in ordered[i+1:]:
                if (a, b) in pairs:
                    continue
                trial = [*edges, Edge(source=a, target=b)]
                candidates.append(trial)
        if op != 'skip':
            for index in range(len(edges)):
                trial = [e for i, e in enumerate(edges) if i != index]
                try:
                    order(nodes, trial, output)
                    candidates.append(trial)
                except ValueError:
                    pass
        if not candidates:
            return genome, op
        changed_edges = rng.choice(candidates)
        if not is_cell:
            return _construct(genome, macro_edges=changed_edges), op
        replacement = CellGene.model_validate({**cell.model_dump(), 'edges': changed_edges})
    elif op in ('head', 'representation'):
        execution = dict(genome.execution)
        if op == 'head':
            execution['head_width'] = rng.randint(4, 64)
        else:
            field = rng.choice(['normalization', 'residual', 'readout'])
            execution[field] = rng.choice({'normalization': ['none', 'train_standard', 'rms'],
                                           'residual': [False, True], 'readout': ['final', 'all', 'input_final']}[field])
        return _construct(genome, execution=execution), op
    elif op == 'optimizer':
        return _construct(genome, learning_rate=10 ** rng.uniform(-4, -1.3), weight_decay=rng.uniform(0, .1)), op
    elif op == 'motif':
        donor = rng.choice(motif_bank)
        replacement = CellGene.model_validate({**donor.model_dump(), 'id': cell.id, 'origin': donor.id,
                                               'parameter_id': f'{rng.randrange(2**64):016x}', 'origin_parameter_id': donor.parameter_id})
    else:
        data = cell.model_dump(mode='json')
        chosen = rng.randrange(len(cell.nodes))
        node = data['nodes'][chosen]
        if op == 'projection-randomize':
            node['projection_seed'] = rng.randrange(2**32)
        elif op == 'width':
            node['width'] = rng.randint(4, policy.max_width)
        elif op == 'primitive':
            node['primitive'] = rng.choice(sorted(OPERATORS))
        elif op == 'cell-grow' and len(cell.nodes) < policy.max_cell_nodes:
            identity = next(f'n{i}' for i in range(7) if f'n{i}' not in {n.id for n in cell.nodes})
            data['nodes'].append(CellNodeGene(id=identity, width=cell.nodes[-1].width,
                                             primitive=rng.choice(sorted(OPERATORS)), projection_seed=rng.randrange(2**32)).model_dump())
            data['edges'].append(Edge(source=cell.output, target=identity).model_dump())
            data['output'] = identity
        elif op == 'cell-prune' and len(cell.nodes) > 1:
            removed = order(cell.nodes, cell.edges, cell.output)[0][0]
            data['nodes'] = [n for n in data['nodes'] if n['id'] != removed]
            data['edges'] = [e for e in data['edges'] if removed not in (e['source'], e['target'])]
        replacement = CellGene.model_validate(data)
    return _construct(genome, cells=[replacement if c.id == cell.id else c for c in genome.cells]), op


def recombine(a, b, rng):
    policy = ResearchPolicy.model_validate(a.execution)
    if policy.max_macro_nodes == 1:
        return a
    # Legacy crossover's effective limit is translated from the explicit envelope.
    budget = max(0, (policy.max_macro_nodes - 2) * 16)
    return crossover(a, b, rng, budget=budget)
