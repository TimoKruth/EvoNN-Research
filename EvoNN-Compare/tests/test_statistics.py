"""Independent seed units and conservative advancement decisions."""
from copy import deepcopy

import pytest

from evonn_compare.statistics import compare_cohorts as analyze, decision_category, minimum_seeds

def compare_cohorts(rows, *, before, after):
    return analyze(rows,before=before,after=after,request=dict(before=before,after=after,before_revision="a"*40,after_revision="b"*40,panels=[dict(pack="tier1_core",budget=64,engine="prism",benchmarks=["one","two","three"],seeds=[0,1,2])]))


def observations(label, *, seeds=range(3), delta=0.0, pack='tier1_core'):
    return [dict(label=label, run_id=f'{label}_{seed}', case_id=f'case_{label}_{seed}',
        engine='prism', benchmark=benchmark, family='tabular', task_kind='classification',
        pack=pack, budget=64, seed=seed, value=.5 + delta, direction='max', ceiling=1.0,
        outcome_id='winner',data_binding={'fixture':'fixed-data'},status='ok', accounting_state='complete', operating_state='trusted-core',
        backend='mlx_native', comparison_policy={'backend':'mlx_native','host':'host','epochs':12},
        git_commit='a'*40 if label=='before' else 'b'*40, quality_level='L3',
        source_clean=True, evaluation_count=8, wall_clock=10., evals_per_second=6.4,
        seconds_per_success=1.25, score_per_second=.05, train_seconds=1., model_family='mlp',
        seeding={'seeding_ladder':'none'})
        for seed in seeds for benchmark in ('one','two','three')]


def test_seed_units_not_benchmarks_and_no_clear_gain_at_three():
    result = compare_cohorts(observations('before') + observations('after', delta=.1), before='before', after='after')
    group = result['groups'][0]
    assert group['n'] == 3 and group['statistical_label'] == 'likely_gain'
    assert group['wilcoxon']['status'] == 'insufficient_data'
    assert group['level'] == 'L4'
    assert result['decision_category'] == 'inconclusive'
    assert group['bootstrap_ci95'][0] > 0


@pytest.mark.parametrize('change', ['missing','duplicate','backend','budget','policy','source','failed'])
def test_missing_confounded_or_duplicate_pairs_block(change):
    rows = observations('before') + observations('after',delta=.1)
    if change=='missing':
        rows.pop()
    elif change=='duplicate':
        rows.append({**rows[-1], 'run_id':'duplicate'})
    elif change=='backend':
        rows[-1]['backend']='numpy_fallback'
    elif change=='budget':
        rows[-1]['budget']=128
    elif change=='policy':
        rows[-1]['comparison_policy']={'epochs':99}
    elif change=='source':
        rows[-1]['git_commit']='c'*40
    else:
        rows[-1]['status']='failed'
    result=compare_cohorts(rows,before='before',after='after')
    assert not any(group['level']=='L4' for group in result['groups'])
    assert result['decision_category'] != 'promote'


def test_saturation_has_no_win_credit_and_portability_no_advancement():
    rows=observations('before')+observations('after')
    for row in rows:
        row['value']=1.
    result=compare_cohorts(rows,before='before',after='after')
    assert result['groups'][0]['ceiling_ties']==9
    assert result['groups'][0]['statistical_label']=='inconclusive'
    rows=observations('before')+observations('after',seeds=range(8),delta=.1)
    for row in rows:
        row['backend']='numpy_fallback'
    assert compare_cohorts(rows,before='before',after='after')['decision_category']!='promote'


def test_decision_precedence_and_seed_thresholds():
    assert minimum_seeds('tier_a_contract','local')==3
    assert minimum_seeds('tier_b_core','overnight')==2
    assert minimum_seeds('tier_b_core','local')==3
    assert minimum_seeds('tier_d_broad','overnight')==3
    assert decision_category([{'pack':'tier1_core','statistical_label':'regression','aggregation_label':'blocked'}])=='Tier 1 regression'
    assert decision_category([{'pack':'tier_b_core','statistical_label':'needs_more_runs','aggregation_label':'blocked'}])=='needs more seeds'
    assert decision_category([{'pack':'tier_b_core','statistical_label':'clear_gain','aggregation_label':'gain'}])=='Tier B-only gain'


def test_report_is_deterministic_and_always_emits_diagnostics():
    rows=observations('before')+observations('after',delta=.1)
    first=compare_cohorts(rows,before='before',after='after')
    assert first==compare_cohorts(list(reversed(deepcopy(rows))),before='before',after='after')
    assert {'transfer_proof','lm_flatline','engine_roles'} <= first['diagnostics'].keys()
    assert first['groups'][0]['runtime_tradeoffs']['family_allocation']


def test_missing_whole_benchmark_or_seed_on_both_sides_cannot_disappear():
    rows=observations('before')+observations('after',delta=.1)
    for remaining in ([r for r in rows if r['benchmark']!='one'],[r for r in rows if r['seed']!=2]):
        assert compare_cohorts(remaining,before='before',after='after')['groups'][0]['level']!='L4'


def test_one_saturated_seed_cannot_hide_regression_and_controls_do_not_block():
    rows=observations('before',seeds=range(6))+observations('after',seeds=range(6),delta=.1)
    for row in rows:
        if row['benchmark']=='one':
            row['value']=1. if row['seed']==0 else .9 if row['label']=='before' else .1
    request=dict(before='before',after='after',before_revision='a'*40,after_revision='b'*40,
        panels=[dict(pack='tier1_core',budget=64,engine='prism',benchmarks=['one','two','three'],seeds=list(range(6)))])
    result=analyze(rows,before='before',after='after',request=request)
    assert result['groups'][0]['effect_mean']<0
    assert result['decision_category']!='promote'
    rows=observations('before',seeds=range(6))+observations('after',seeds=range(6),delta=.1)
    controls=[{**r,'engine':'contenders','backend':'sklearn_contender','run_id':'control_'+r['run_id']} for r in rows]
    result=analyze(rows+controls,before='before',after='after',request=request)
    assert len(result['groups'])==1
    assert result['decision_category']=='promote'


def test_audit_support_budget_does_not_create_an_unrequested_panel():
    requested = observations('before') + observations('after', delta=.1)
    support = [{**row, 'budget':128, 'run_id':'support_'+row['run_id']} for row in observations('before')]
    result = compare_cohorts(requested+support, before='before', after='after')
    assert len(result['groups']) == 1
    assert result['groups'][0]['budget'] == 64 and result['groups'][0]['level'] == 'L4'
    requested[-1]['budget'] = 128
    result = compare_cohorts(requested+support, before='before', after='after')
    assert result['groups'][0]['level'] != 'L4'
