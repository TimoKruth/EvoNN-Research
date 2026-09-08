"""Winner-conditioned motif mining and explicit hierarchy-proxy diagnostics."""
from collections import Counter
from evonn_shared.runtime_io import derived, encode
from .genome import HierarchicalGenome
from .search import descriptor


def build_artifacts(workspace,state,definitions,runtime):
    winners={}
    for row in state['attempts']:
        benchmark=row['benchmark_id']
        if row['status']=='ok' and (benchmark not in winners or row['score']>winners[benchmark]['score']):
            winners[benchmark]=row
    local,global_counts={},Counter()
    for benchmark,row in winners.items():
        genome=HierarchicalGenome.model_validate(row['genome'])
        counts=Counter(cell.program_id for cell in genome.cells)
        global_counts.update(counts)
        local[benchmark]=dict(candidate=row['genome_id'],quality=row['metric_value'],descriptors=descriptor(genome),
            programs=dict(counts),cells=[cell.model_dump(mode='json') for cell in genome.cells],
            lineage=state['search']['benchmarks'][benchmark]['lineage'])
    motifs=dict(schema_version=1,evaluator_fidelity='hierarchy_features_trained_head',
        global_frequency=dict(global_counts),local_winners=local,variant=state['config']['variant'],
        interpretation='Deterministic cell programs with a trained GELU head; no end-to-end hierarchy or transfer claim.')
    diagnostics=[]
    for definition in definitions:
        if definition.task_kind.value=='language_modeling':
            rows=[a for a in state['attempts'] if a['benchmark_id']==definition.id and a['status']=='ok']
            values=[a['metric_value'] for a in rows]
            diagnostics.append(dict(benchmark=definition.id,values=values,flatline=len(values)>1 and max(values)-min(values)<1e-8,
                causal_input=True,evaluator_fidelity='hierarchy_features_trained_head',
                broad_claim_ready=False,reason='proxy LM requires repeated real-text native qualification'))
    derived(workspace.root/'motif_analysis.json',encode(motifs))
    derived(workspace.root/'lm_diagnostics.json',encode(diagnostics))
    return ('motif_analysis.json','lm_diagnostics.json')
