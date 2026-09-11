"""Ranked, reconstructable primitive banks with explicit unproven transfer state."""
from collections import Counter
import importlib.metadata
import json
from evonn_shared.runtime_io import derived, encode
from evonn_shared.export_reader import read_document, read_export
from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
from evonn_shared.seed_artifact import seal_seed
from .genome import PrimitiveGenome


def _bank(context, trials):
    successful = [row for row in trials if row['status']=='ok']
    grouped = {}
    for row in successful:
        key = (row['benchmark_id'],row['genome_id'])
        if key not in grouped or grouped[key]['score'] < row['score']:
            grouped[key] = row
    ranked = sorted(grouped.values(), key=lambda row:(row['benchmark_id'],-row['score'],row['genome_id']))
    seeds, entries, leaders, families = [], [], {}, {}
    data = {item['benchmark_id']:item for item in context['data']}
    for row in ranked:
        genome = PrimitiveGenome.model_validate(row['genome'])
        definition = context['definitions'][row['benchmark_id']]
        descriptors = dict(width=float(genome.width),depth=float(len(genome.primitives)),
            gates=float(sum(p.operator=='gate' for p in genome.primitives)),
            sparse=float(sum(p.operator=='sparse' for p in genome.primitives)))
        entry = dict(benchmark=row['benchmark_id'], candidate=row['genome_id'], genome=row['genome'],
            quality=row['metric_value'], direction=definition['primary_metric']['direction'],
            metric=definition['primary_metric']['name'], descriptors=descriptors,
            rank=1+sum(item['benchmark']==row['benchmark_id'] for item in entries),
            transfer_status='unproven', selection='validation only; no downstream evidence')
        entries.append(entry)
        if row['benchmark_id'] not in leaders:
            leaders[row['benchmark_id']] = entry
            family = definition['input_modality'] + ':' + definition['task_kind']
            if family not in families:
                families[family] = []
            # Scores across datasets have incompatible scales: retain each benchmark leader.
            families[family].append(entry)
        provenance = data[row['benchmark_id']]
        config = context['config']
        targets=['stratograph','topograph','prism']
        seeds.append(seal_seed(dict(source=dict(engine='primordia',version=context['version'],
            commit=config['git_commit'],code_dirty=config['code_dirty'],run_id=context['run_id'],
            candidate_id=row['genome_id'],benchmark=row['benchmark_id'],pack=config['pack'],
            seed=config['seed'],budget_spent=context['budget_spent'],runtime=context['runtime']),
            encoding=dict(format=genome.encoding,genome=row['genome']),descriptors=descriptors,
            quality=dict(metric=entry['metric'],direction=entry['direction'],value=float(entry['quality'])),
            diversity=dict(operator_types=float(len({p.operator for p in genome.primitives}))),
            contamination=dict(policy='train-fit_validation-selection_no-target-test',raw_sha256=provenance['raw_sha256'],
                split_sha256=provenance['split_sha256'],target_overlap='unknown_requires_target_check'),
            compatible_targets=targets,ingestion=[dict(target=target,protocol='evonn.motif-translation/v1',
                status='translation_required_not_native_ingestion',instructions='Translate primitive operators and merge semantics into a target-owned genome; validate source split overlap and charge the declared source budget before any fair transfer claim.') for target in targets])))
    return dict(schema_version=1,entries=entries,benchmark_coverage=sorted(leaders),
        operator_coverage=dict(Counter(p['operator'] for row in ranked for p in row['genome']['primitives'])),
        transfer_status='unproven'), seeds, dict(benchmarks=leaders,families=families,
            family_policy='per-benchmark representatives; no cross-metric numeric ranking')


def rebuild_bank(root):
    if not (root/'symbiosis').exists():
        return None  # Incomplete runs have no published bank to reconstruct.
    bundle=read_export(root/'symbiosis')
    validate_engine_bundle(bundle,verify_cache=True)
    checked={name:artifact_json(bundle,name) for name in ('bank_context.json','trial_records.json','best_results.json')}
    for name,payload in checked.items():
        if json.loads(read_document(root,name))!=payload:
            raise ValueError('local bank reconstruction input differs from immutable export: '+name)
    context,trials,best=(checked[name] for name in ('bank_context.json','trial_records.json','best_results.json'))
    bank,seeds,leaders=_bank(context,trials)
    if best != leaders['benchmarks']:
        raise ValueError('best-results reconstruction disagrees with trial records')
    for name,payload in [('primitive_bank.json',bank),('seed_candidates.json',seeds),('search_leaders.json',leaders)]:
        derived(root/name,encode(payload))
    return bank


def build_artifacts(workspace,state,definitions,runtime):
    context=dict(config=state['config'],run_id=workspace.run_id,runtime=runtime,
        version=importlib.metadata.version('evonn-primordia'),budget_spent=sum(a['charged'] for a in state['attempts']),
        data=json.loads(read_document(workspace.root,'dataset_provenance.json')),
        definitions={definition.id:definition.model_dump(mode='json') for definition in definitions})
    bank,seeds,leaders=_bank(context,state['attempts'])
    documents={'bank_context.json':context,'trial_records.json':state['attempts'],'best_results.json':leaders['benchmarks'],
               'primitive_bank.json':bank,'seed_candidates.json':seeds,'search_leaders.json':leaders}
    for name,payload in documents.items():
        derived(workspace.root/name,encode(payload))
    report='# Primitive bank\n\nValidation-selected motifs; downstream transfer is unproven.\n\n'
    for name,entry in leaders['benchmarks'].items():
        report+=f"- {name}: {entry['metric']} = {entry['quality']:.6g}; {entry['genome']}\n"
    derived(workspace.root/'primitive_bank.md',report.encode())
    return (*documents,'primitive_bank.md')
