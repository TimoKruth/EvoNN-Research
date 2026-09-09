"""Actual arm identities, missing-cell rejection and independent seed inference."""
from copy import deepcopy
import json

import pytest

from evonn_compare.cohort import CohortRequest, analyze_cohort


def data(seeds=range(3)):
    rows=[]
    for engine,value in [('prism',.8),('topograph',.9),('contenders',.7)]:
        for budget in (64,128):
            for seed in seeds:
                for bench in ('one','two'):
                    rows.append(dict(label='cohort',pack='tier_b_core_v2',engine=engine,budget=budget,seed=seed,
                        benchmark=bench,metric='accuracy',direction='max',ceiling=1.,value=value+(budget==128)*.01,
                        run_id=f'{engine}_{budget}_{seed}',case_id=f'{budget}_{seed}',outcome_id='candidate',
                        status='ok',quality_level='L3',source_clean=True,git_commit='a'*40,
                        backend='sklearn_contender' if engine=='contenders' else 'mlx_native',
                        operating_state='trusted-core',accounting_state='complete',run_class='local',
                        comparison_policy={'runtime':{'host':'same'},'training':{'epochs':12},'budget':{'evaluation':{'total':budget},'time':1500}},
                        comparison_fingerprint='same',data_binding={'seed':seed,'benchmark':bench},seeding={'seeding_ladder':'none'},host_fingerprint='host',
                        required_floor=True,contender_id='baseline',wall_clock=10.,evals_per_second=6.4,seconds_per_success=.2,
                        score_per_second=.08,train_seconds=1.,model_family='family',family='tabular'))
    return rows


def request(seeds=range(3), reference='prism', target='topograph', from_budget=64,to_budget=64):
    return dict(label='cohort',source_revision='a'*40,panels=[dict(id='contrast',pack='tier_b_core_v2',
        reference=dict(engine=reference,budget=from_budget,selection='required_floor' if reference=='contenders' else 'winner'),
        target=dict(engine=target,budget=to_budget),benchmarks=['one','two'],seeds=list(seeds))])


def test_engine_contrast_keeps_identity_and_does_not_authorize_advancement():
    result=analyze_cohort(data(),request(),artifacts_verified=True)
    group=result['groups'][0]
    assert group['level']=='L4' and group['n']==3 and group['statistical_label']=='likely_gain'
    assert group['reference']['engine']=='prism' and group['target']['engine']=='topograph'
    assert group['view']=='engines_only' and not result['engine_advancement_authorized']
    assert result==analyze_cohort(list(reversed(data())),request(),artifacts_verified=True)


def test_floor_named_selection_and_budget_contrasts():
    r=request(reference='contenders')
    r['panels'][0]['reference'].update(selection='named_contender',contender='baseline')
    assert analyze_cohort(data(),r,artifacts_verified=True)['groups'][0]['level']=='L4'
    r['panels'][0]['reference']['contender']='missing'
    assert analyze_cohort(data(),r,artifacts_verified=True)['status']=='blocked'
    result=analyze_cohort(data(),request(target='prism',to_budget=128),artifacts_verified=True)
    assert result['groups'][0]['level']=='L4'
    assert result['groups'][0]['raw_deltas'][0]['delta']==pytest.approx(.01)


@pytest.mark.parametrize('change',['source','dirty','data','host','backend','policy','envelope','metric','seeding','duplicate_run','duplicate_outcome','missing','failed','runtime','fingerprint','run_class'])
def test_invalid_expected_cells_block_l4(change):
    rows=data();row=next(r for r in rows if r['engine']=='topograph' and r['budget']==64)
    if change=='source':row['git_commit']='b'*40
    elif change=='dirty':row['source_clean']=False
    elif change=='data':row['data_binding']={}
    elif change=='host':row['comparison_policy']['runtime']['host']='other'
    elif change=='backend':row['backend']='numpy_fallback'
    elif change=='policy':row['comparison_policy']['training']['epochs']=99
    elif change=='envelope':row['comparison_policy']['budget']['time']=500
    elif change=='metric':row['metric']='wrong'
    elif change=='seeding':row['seeding']={'seeding_ladder':'direct'}
    elif change=='duplicate_run':rows.append({**row,'run_id':'other'})
    elif change=='duplicate_outcome':rows.append(deepcopy(row))
    elif change=='missing':rows.remove(row)
    elif change=='failed':row['status']='failed'
    elif change=='runtime':row['train_seconds']=None
    elif change=='fingerprint':row['comparison_fingerprint']=None
    else:row['run_class']='overnight'
    group=analyze_cohort(rows,request(),artifacts_verified=True)['groups'][0]
    assert group['level']!='L4' and group['blockers']


def test_missing_seed_on_both_arms_and_offline_never_promote():
    rows=[r for r in data() if r['seed']!=2]
    assert analyze_cohort(rows,request(),artifacts_verified=True)['groups'][0]['level']!='L4'
    assert analyze_cohort(data(),request())['groups'][0]['level']!='L4'


def test_ceiling_ties_excluded_and_partial_ceiling_cannot_hide_regression():
    rows=data()
    for row in rows:
        if row['benchmark']=='one':row['value']=1.
    group=analyze_cohort(rows,request(),artifacts_verified=True)['groups'][0]
    assert group['excluded_benchmarks']==['one'] and group['ceiling_ties']==3
    for row in rows:
        if row['engine']=='topograph' and row['seed']>0 and row['benchmark']=='one':row['value']=.1
    group=analyze_cohort(rows,request(),artifacts_verified=True)['groups'][0]
    assert group['effect_mean']<0 and not group['excluded_benchmarks']
    for row in rows:row['value']=1.
    group=analyze_cohort(rows,request(),artifacts_verified=True)['groups'][0]
    assert group['fully_saturated'] and group['statistical_label']=='inconclusive'


def test_six_seed_clear_gain_holm_and_explicit_schema_guards():
    group=analyze_cohort(data(range(6)),request(range(6)),artifacts_verified=True)['groups'][0]
    assert group['n']==6 and group['statistical_label']=='clear_gain'
    assert group['wilcoxon']['holm_pvalue']<=.05
    for edit in ('duplicate','same','two_interventions','bad_seed','bad_floor','unknown'):
        r=request()
        if edit=='duplicate':r['panels'].append(deepcopy(r['panels'][0]))
        elif edit=='same':r['panels'][0]['target']=r['panels'][0]['reference']
        elif edit=='two_interventions':r['panels'][0]['target']['budget']=128
        elif edit=='bad_seed':r['panels'][0]['seeds']=[1,1,2]
        elif edit=='bad_floor':r['panels'][0]['reference']['selection']='required_floor'
        else:r['unexpected']=True
        with pytest.raises(ValueError):CohortRequest.model_validate(r)


def test_required_floor_must_be_complete_in_each_seed(monkeypatch):
    from types import SimpleNamespace
    from evonn_shared import active_catalog
    monkeypatch.setattr(active_catalog,'get_benchmark',lambda name:SimpleNamespace(required_contenders=['baseline','second']))
    rows=data()
    rows += [{**r,'contender_id':'second','outcome_id':'second','value':.65} for r in rows if r['engine']=='contenders']
    assert analyze_cohort(rows,request(reference='contenders'),artifacts_verified=True)['groups'][0]['level']=='L4'
    rows=[r for r in rows if not (r['contender_id']=='second' and r['seed']==2)]
    result=analyze_cohort(rows,request(reference='contenders'),artifacts_verified=True)
    assert result['status']=='blocked' and any('incomplete required floor' in b for b in result['groups'][0]['blockers'])


def test_separate_report_never_changes_registry_and_offline_cannot_claim_l4(tmp_path,export_factory):
    from evonn_compare.registry import promote, registry_report
    from evonn_compare.cohort import cohort_report
    source=export_factory(tmp_path/'export')
    root=tmp_path/'registry'
    promote(source.root,registry=root,label='cohort')
    registry_report(root)
    index=(root/'index.jsonl').read_bytes();historical=(root/'evidence_report.json').read_bytes()
    result=cohort_report(root,request())
    assert result['status']=='blocked' and result['groups'][0]['level']!='L4'
    assert (root/'index.jsonl').read_bytes()==index and (root/'evidence_report.json').read_bytes()==historical
    assert (root/'cohort_report.json').exists()


def test_budget_contrast_allows_only_the_derived_training_total():
    rows=data()
    for row in rows:
        row['comparison_policy']['budget']['training']=dict(unit='fit',per_candidate=1.,total_cap=float(row['budget']))
    r=request(target='prism',to_budget=128)
    assert analyze_cohort(rows,r,artifacts_verified=True)['groups'][0]['level']=='L4'
    row=next(r for r in rows if r['engine']=='prism' and r['budget']==128)
    row['comparison_policy']['budget']['training']['total_cap']=999.
    assert analyze_cohort(rows,r,artifacts_verified=True)['groups'][0]['level']!='L4'


def test_different_floor_host_needs_verified_campaign_binding():
    rows=data()
    for row in rows:
        if row['engine']=='contenders':row['host_fingerprint']='different-codec'
    r=request(reference='contenders');r['panels'][0]['reference'].update(selection='named_contender',contender='baseline')
    assert analyze_cohort(rows,r,artifacts_verified=True)['groups'][0]['level']!='L4'
    for row in rows:row['matched_host_fingerprint']='validated-common-host'
    assert analyze_cohort(rows,r,artifacts_verified=True)['groups'][0]['level']=='L4'
