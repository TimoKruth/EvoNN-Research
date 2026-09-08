from random import Random

import pytest

from stratograph.genome import HierarchicalGenome, seed_genome, clone_cell, specialize, mutate, crossover


def test_hierarchy_invariants_and_structural_metrics():
    genome=seed_genome('classification',4,budget=64)
    assert genome.reuse_ratio>0 and genome.macro_depth>=2 and genome.max_cell_depth>=2
    assert HierarchicalGenome.model_validate(genome.model_dump(mode='json')).genome_id==genome.genome_id
    for transform in ('duplicate','missing_cell','macro_cycle','cell_cycle','unreachable'):
        data=genome.model_dump(mode='json')
        if transform=='duplicate':
            data['macro_nodes'].append(data['macro_nodes'][0])
        elif transform=='missing_cell':
            data['macro_nodes'][0]['cell_id']='missing'
        elif transform=='macro_cycle':
            data['macro_edges'].append({'source':data['output'],'target':data['macro_nodes'][0]['id']})
        elif transform=='cell_cycle':
            data['cells'][0]['edges'].append({'source':data['cells'][0]['output'],'target':data['cells'][0]['nodes'][0]['id']})
        else:
            data['macro_edges']=[]
        with pytest.raises(ValueError):
            HierarchicalGenome.model_validate(data)


def test_clone_then_specialize_and_crossover_preserve_validity():
    a=seed_genome('regression',16,budget=64)
    clone=clone_cell(a,a.macro_nodes[-1].id)
    assert len(clone.cells)==len(a.cells)+1 and clone.reuse_ratio<a.reuse_ratio
    changed=specialize(clone,clone.macro_nodes[-1].cell_id,Random(7))
    assert changed.genome_id!=clone.genome_id
    for seed in range(30):
        b,operator=mutate(a,Random(seed),budget=64)
        child=crossover(a,b,Random(seed),budget=64)
        assert operator and child.macro_depth<=6
        HierarchicalGenome.model_validate(child.model_dump(mode='json'))


def test_all_ablations_and_explicit_profiles():
    for variant in ('flat','unshared','shared','no-clone','no-motif-bias'):
        g=seed_genome('classification',64,budget=64,variant=variant)
        if variant=='flat':
            assert len(g.macro_nodes)==1
        if variant=='unshared':
            assert g.reuse_ratio==0
    assert seed_genome('language_modeling',32,budget=64).profile=='language_modeling'
    assert seed_genome('classification',784,budget=64,modality='image').profile=='image'


def test_crossover_is_independent_of_process_hash_seed(tmp_path):
    import json
    import os
    import subprocess
    import sys
    from stratograph.genome import MacroNodeGene,Edge
    base=seed_genome('classification',4)
    cell=base.cells[0]
    branched=HierarchicalGenome.model_validate({**base.model_dump(),
        'cells':[cell], 'macro_nodes':[MacroNodeGene(id=f'm{i}',cell_id=cell.id) for i in range(6)],
        'macro_edges':[Edge(source=f'm{i}',target='m5') for i in range(5)],'output':'m5'})
    path=tmp_path/'parent.json'
    path.write_text(branched.model_dump_json())
    code="from stratograph.genome import HierarchicalGenome,crossover;from random import Random;import sys,json;g=HierarchicalGenome.model_validate_json(open(sys.argv[1]).read());print(json.dumps([crossover(g,g,Random(i)).genome_id for i in range(100)]))"
    outputs=[subprocess.check_output([sys.executable,'-c',code,str(path)],env={**os.environ,'PYTHONHASHSEED':seed},text=True) for seed in ('1','2')]
    assert json.loads(outputs[0])==json.loads(outputs[1])


def test_cell_structure_evolves_and_motifs_are_full_programs():
    genome=seed_genome('classification',4)
    seen=set()
    rng=Random(16)
    for _ in range(250):
        genome,operation=mutate(genome,rng,motif_bank=genome.cells)
        seen.add(operation)
        HierarchicalGenome.model_validate(genome.model_dump(mode='json'))
    assert {'cell-grow','cell-prune','cell-rewire','motif','skip','rewire'}<=seen
