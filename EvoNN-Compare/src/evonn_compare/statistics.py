"""Conservative paired-seed inference, distinct from observed leaderboards.

Bootstrap units are independent seeds over a fixed benchmark set, never trials
or benchmark rows. Relative effects use 2*(after-before)/(|after|+|before|),
with direction applied; raw metric deltas remain available per benchmark.
"""
from collections import defaultdict
from enum import StrEnum
import json
import math
import statistics

import numpy as np
from scipy.stats import PermutationMethod, friedmanchisquare, rankdata, wilcoxon
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class StatisticalLabel(StrEnum):
    CLEAR_GAIN = 'clear_gain'
    LIKELY_GAIN = 'likely_gain'
    NO_MATERIAL_CHANGE = 'no_material_change'
    REGRESSION = 'regression'
    INCONCLUSIVE = 'inconclusive'
    NEEDS_MORE_RUNS = 'needs_more_runs'


class AggregationLabel(StrEnum):
    GAIN = 'gain'
    NO_MATERIAL_CHANGE = 'no_material_change'
    INCONCLUSIVE = 'inconclusive'
    BLOCKED = 'blocked'


class DecisionCategory(StrEnum):
    TIER1_REGRESSION = 'Tier 1 regression'
    NEEDS_MORE_SEEDS = 'needs more seeds'
    TIERB_GAIN = 'Tier B-only gain'
    REGRESS = 'regress'
    PROMOTE = 'promote'
    INCONCLUSIVE = 'inconclusive'


class ComparisonPanel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    pack: str
    budget: int = Field(gt=0)
    engine: str
    benchmarks: list[str] = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    schema_version: Literal[1] = 1
    policy: Literal['paired-seed-relative-v1'] = 'paired-seed-relative-v1'
    before: str
    after: str
    before_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    after_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    panels: list[ComparisonPanel] = Field(min_length=1)
    materiality: float = Field(default=.01, ge=0)
    claim_scope: Literal['engine_advancement','contract_validation'] = 'engine_advancement'


def minimum_seeds(pack, run_class):
    return 2 if pack.startswith(('tier_b_', 'tier_c_')) and run_class == 'overnight' else 3


def decision_category(groups):
    if any(g['pack'] == 'tier1_core' and g['statistical_label'] == 'regression' for g in groups):
        return DecisionCategory.TIER1_REGRESSION.value
    if any(g['statistical_label'] == 'needs_more_runs' or g.get('uncertainty_reason')=='noisy_repeats' for g in groups):
        return DecisionCategory.NEEDS_MORE_SEEDS.value
    gains = [g for g in groups if g['aggregation_label'] == 'gain']
    if gains and all(g['pack'].startswith('tier_b_') for g in gains):
        return DecisionCategory.TIERB_GAIN.value
    if any(g['statistical_label'] == 'regression' for g in groups):
        return DecisionCategory.REGRESS.value
    if (any(g['pack'] == 'tier1_core' for g in gains)
            and all(g['aggregation_label'] in ('gain', 'no_material_change') for g in groups)):
        return DecisionCategory.PROMOTE.value
    return DecisionCategory.INCONCLUSIVE.value


def paired_inference(values, *, materiality=.01):
    array = np.asarray(values, dtype=float)
    if not np.isfinite(array).all() or not math.isfinite(materiality) or materiality < 0:
        raise ValueError('finite effects and nonnegative materiality required')
    n = len(array)
    result = dict(n=n, effect_mean=float(array.mean()) if n else None,
        bootstrap_ci95=None, standardized_effect=None, rank_biserial=None,
        bootstrap_method='4096 percentile resamples of independent paired seed means; RNG seed 0',
        wilcoxon={'status':'insufficient_data', 'n':n, 'reason':'requires at least six nonzero independent paired seeds'},
        materiality=materiality)
    if n < 2:
        return result
    rng = np.random.default_rng(0)
    means = [float(rng.choice(array, size=n, replace=True).mean()) for _ in range(4096)]
    result['bootstrap_ci95'] = [float(x) for x in np.quantile(means, [.025, .975])]
    deviation = float(array.std(ddof=1))
    result['standardized_effect'] = float(array.mean()/deviation) if deviation > 0 else None
    nonzero = np.round(array[array != 0], 12)
    if len(nonzero):
        ranks = rankdata(np.abs(nonzero))
        result['rank_biserial'] = float(np.sum(ranks*np.sign(nonzero))/np.sum(ranks))
    if n >= 6 and np.count_nonzero(nonzero) >= 6:
        test = wilcoxon(np.round(array,12), method=PermutationMethod(n_resamples=8192, rng=np.random.default_rng(0)))
        result['wilcoxon'] = dict(status='available', n=n, statistic=float(test.statistic),
            pvalue=float(test.pvalue), method='two-sided signed-rank permutation, <=8192 permutations',
            assumption='independent seed effects symmetric under the null; diagnostic, not causal proof')
    return result


def guarded_friedman(seed_system_scores):
    """Conservative chi-square approximation guard, per SciPy's stated regime."""
    array = np.asarray(seed_system_scores, dtype=float)
    if array.ndim != 2 or array.shape[0] <= 10 or array.shape[1] <= 6:
        return {'status':'insufficient_data', 'reason':'requires >10 independent seed blocks and >6 systems'}
    if not np.isfinite(array).all():
        raise ValueError('Friedman requires finite complete blocks')
    if np.all(array == array[:, :1]):
        return {'status':'not_applicable', 'reason':'all systems tied within every seed'}
    test = friedmanchisquare(*array.T)
    return dict(status='available', statistic=float(test.statistic), pvalue=float(test.pvalue),
        n=len(array), systems=array.shape[1], method='Friedman chi-square approximation')


def _runtime(rows):
    rows=sorted(rows,key=lambda r:(r['label'],r['run_id'],r['benchmark'],r['outcome_id']))
    unique = {(r['label'],r['run_id']):r for r in rows}
    groups = defaultdict(list)
    for row in unique.values():
        groups[row['label']].append(row)
    summary = {}
    for label, values in sorted(groups.items()):
        summary[label] = {field: statistics.median([r[field] for r in values if (r[field] if field in r else None) is not None])
            if any((r[field] if field in r else None) is not None for r in values) else None
            for field in ('wall_clock','evals_per_second','seconds_per_success')}
    allocation = defaultdict(float)
    for row in rows:
        if row.get('train_seconds') is not None:
            allocation[(row['label'], row.get('model_family') or 'unknown')] += row['train_seconds']
    complete=bool(rows) and all(all(field in r and r[field] is not None and math.isfinite(r[field]) for field in ('wall_clock','evals_per_second','seconds_per_success','score_per_second','train_seconds')) and r.get('model_family') for r in rows)
    return dict(complete=bool(complete),per_label=summary, score_per_second=[dict(label=r['label'],run_id=r['run_id'],benchmark=r['benchmark'],value=r.get('score_per_second')) for r in rows],
        family_allocation=[dict(label=label,family=family,seconds=seconds) for (label,family),seconds in sorted(allocation.items())],
        note='family allocation covers exported outcomes; raw lower-is-better score/time is not utility')


def _paired_group(rows, before, after, materiality, panel=None, request=None):
    first=rows[0]
    grouped=defaultdict(list)
    for row in rows:
        grouped[(row['label'],row['seed'],row['benchmark'])].append(row)
    seeds=sorted({r['seed'] for r in rows})
    benchmarks=sorted({r['benchmark'] for r in rows})
    blockers=[]
    if panel is None:
        blockers.append('explicit expected comparison panel required for L4')
    elif set(seeds)!=set(panel.seeds) or set(benchmarks)!=set(panel.benchmarks):
        blockers.append('observed seeds/benchmarks differ from declared panel')
    if request is not None:
        for row in rows:
            revision=request.before_revision if row['label']==before else request.after_revision
            if row['git_commit']!=revision:
                blockers.append('source revision differs from declared intervention')
    if any(len(values)!=1 for values in grouped.values()):
        blockers.append('duplicate observations for label/seed/benchmark')
    if len(grouped)!=2*len(seeds)*len(benchmarks):
        blockers.append('missing paired seed/benchmark observations')
    if any(r['status']!='ok' or r['value'] is None or not math.isfinite(r['value']) for r in rows):
        blockers.append('failed, missing or nonfinite outcomes')
    if any(r['accounting_state']!='complete' or r['operating_state'] not in ('contract-fair','trusted-core','trusted-extended') for r in rows):
        blockers.append('unfair or incomplete lane')
    if any(r.get('quality_level') not in ('L3','L4') or not r.get('source_clean') for r in rows):
        blockers.append('clean source and verified L3 artifacts required')
    if len({json.dumps(r['comparison_policy'],sort_keys=True) for r in rows})!=1 or len({r['backend'] for r in rows})!=1:
        blockers.append('backend, host, data or training protocol drift')
    for label in (before,after):
        if len({r['git_commit'] for r in rows if r['label']==label})!=1:
            blockers.append('one explicit source revision required per cohort')
    if {r['run_id'] for r in rows if r['label']==before} & {r['run_id'] for r in rows if r['label']==after}:
        blockers.append('same run reused as both before and after')
    minimum=minimum_seeds(first['pack'],first.get('run_class','local'))
    deltas=[]
    raw=[]
    ties=0
    if not blockers:
        saturated={benchmark for benchmark in benchmarks if all(
            grouped[(before,seed,benchmark)][0]['value']==grouped[(after,seed,benchmark)][0]['value']==grouped[(before,seed,benchmark)][0]['ceiling'] for seed in seeds)}
        ties=sum(grouped[(before,seed,benchmark)][0]['value']==grouped[(after,seed,benchmark)][0]['value']==grouped[(before,seed,benchmark)][0]['ceiling'] for seed in seeds for benchmark in benchmarks)
        for seed in seeds:
            effects=[]
            for benchmark in benchmarks:
                a,b=(grouped[(label,seed,benchmark)][0] for label in (before,after))
                if not a.get('data_binding') or not b.get('data_binding') or a['data_binding']!=b['data_binding']:
                    blockers.append('paired dataset or split provenance drift')
                    continue
                if a['direction']!=b['direction'] or a['ceiling']!=b['ceiling']:
                    blockers.append('metric direction or ceiling drift')
                    continue
                if benchmark in saturated:
                    continue
                delta=(b['value']-a['value'])*(1 if a['direction']=='max' else -1)
                scale=abs(a['value'])+abs(b['value'])
                effects.append(2*delta/scale if scale else 0.)
                raw.append(dict(seed=seed,benchmark=benchmark,delta=delta))
            if effects:
                deltas.append(statistics.mean(effects))
    inference=paired_inference(deltas,materiality=materiality)
    label='inconclusive'
    if len(seeds)<minimum:
        label='needs_more_runs'
    elif not blockers and len(deltas)==len(seeds):
        low,high=inference['bootstrap_ci95']
        if -materiality<=low<=high<=materiality:
            label='no_material_change'
        elif high < -materiality:
            label='regression'
        elif low>materiality:
            test=inference['wilcoxon']
            label='clear_gain' if test['status']=='available' and test['pvalue']<=.05 else 'likely_gain'
    if len(seeds)<minimum:
        blockers.append(f'at least {minimum} paired independent seeds required')
    runtime=_runtime(rows)
    if not runtime['complete']:
        blockers.append('complete runtime and family allocation measurements required')
    ready=not blockers and len(deltas)==len(seeds)
    native=all(r['backend']=='mlx_native' for r in rows)
    floor=all(r['operating_state'] in ('trusted-core','trusted-extended') for r in rows)
    aggregation='inconclusive'
    if not ready or not native or not floor:
        aggregation='blocked'
    elif label=='clear_gain':
        aggregation='gain'
    elif label=='no_material_change':
        aggregation='no_material_change'
    return dict(pack=first['pack'],budget=first['budget'],engine=first['engine'],seeds=seeds,benchmarks=benchmarks,
        **inference,statistical_label=label,aggregation_label=aggregation,blockers=sorted(set(blockers)),
        level='L4' if ready else 'L3',minimum_seeds=minimum,ceiling_ties=ties,raw_deltas=raw,
        seed_effects=deltas,runtime_tradeoffs=runtime,portability_only=not native,
        excluded_benchmarks=sorted(saturated) if not blockers else [],
        uncertainty_reason='noisy_repeats' if ready and label=='inconclusive' and deltas else None,
        friedman={'status':'insufficient_data','reason':'paired before/after has only two systems'},
        effect_scale='symmetric relative difference, direction-aware, equal benchmark weight')


def compare_cohorts(rows, *, before, after, materiality=.01, request=None):
    if before==after or not before or not after:
        raise ValueError('two distinct explicit cohort labels required')
    if not math.isfinite(materiality) or materiality<0:
        raise ValueError('finite nonnegative materiality required')
    if request is not None:
        request=AnalysisRequest.model_validate(request)
        if request.before!=before or request.after!=after:
            raise ValueError('analysis labels differ from request')
        materiality=request.materiality
        identities=[(p.pack,p.budget,p.engine) for p in request.panels]
        if len(set(identities))!=len(identities) or any(len(set(p.seeds))!=len(p.seeds) or len(set(p.benchmarks))!=len(p.benchmarks) for p in request.panels):
            raise ValueError('duplicate declared panel, seed or benchmark')
    from .evidence import best_rows
    full_rows=rows
    rows=best_rows(rows)
    selected=sorted([r for r in rows if r['label'] in (before,after)],key=lambda r:(r['pack'],r['budget'],r['engine'],r['label'],r['seed'],r['benchmark'],r['run_id']))
    groups=defaultdict(list)
    targets=None if request is None else {(p.pack,p.budget,p.engine) for p in request.panels}
    for row in selected:
        if targets is None or (row['pack'],row['budget'],row['engine']) in targets:
            groups[(row['pack'],row['budget'],row['engine'])].append(row)
    panels={} if request is None else {(p.pack,p.budget,p.engine):p for p in request.panels}
    results=[_paired_group(values,before,after,materiality,panels[key] if key in panels else None,request) for key,values in sorted(groups.items())]
    for key,panel in sorted(panels.items()):
        if key not in groups:
            results.append(dict(pack=panel.pack,budget=panel.budget,engine=panel.engine,n=0,level='L0',statistical_label='needs_more_runs',aggregation_label='blocked',blockers=['entire declared panel missing'],wilcoxon={'status':'insufficient_data'}))
    for group in results:
        runtime_rows=[r for r in full_rows if r['label'] in (before,after) and (r['pack'],r['budget'],r['engine'])==(group['pack'],group['budget'],group['engine'])]
        group['runtime_tradeoffs']=_runtime(runtime_rows)
        if not group['runtime_tradeoffs']['complete'] and group['level']=='L4':
            group['level']='L3'
            group['aggregation_label']='blocked'
            group['blockers'].append('incomplete full-attempt runtime allocation')
    # Holm correction across available group tests; clear gain requires familywise evidence.
    tested=sorted([g for g in results if g['wilcoxon']['status']=='available'],key=lambda g:g['wilcoxon']['pvalue'])
    previous=0.
    for i,group in enumerate(tested):
        adjusted=max(previous,min(1.,group['wilcoxon']['pvalue']*(len(tested)-i)))
        previous=adjusted
        group['wilcoxon']['holm_pvalue']=adjusted
        if group['statistical_label']=='clear_gain' and adjusted>.05:
            group['statistical_label']='likely_gain'
            if group['aggregation_label']=='gain':
                group['aggregation_label']='inconclusive'
    return dict(schema_version=1,before=before,after=after,groups=results,
        request=request.model_dump() if request is not None else None,
        decision_category=decision_category(results),diagnostics=diagnostics(selected,results),
        limitations=['Bootstrap uncertainty at few seeds is descriptive; likely_gain is not promotion.',
                     'Source revision is the declared intervention; observational comparisons do not prove causality.'])


def diagnostics(rows, groups):
    transfers=[dict(run_id=r['run_id'],seeding=r.get('seeding')) for r in rows if r.get('seeding',{}).get('seeding_ladder','none')!='none']
    from .evidence import best_rows
    lm=defaultdict(list)
    for row in best_rows(rows):
        if row['task_kind']=='language_modeling' and row['status']=='ok':
            policy={key:value for key,value in row['comparison_policy'].items() if key!='budget'}
            binding=json.dumps([policy,row['git_commit'],row.get('data_binding')],sort_keys=True)
            lm[(row['label'],row['engine'],row['benchmark'],row['seed'],binding)].append(row)
    flat=[]
    for key,values in sorted(lm.items()):
        budgets={r['budget'] for r in values}
        flat.append(dict(label=key[0],engine=key[1],benchmark=key[2],seed=key[3],budgets=sorted(budgets),
            status='insufficient_data' if len(budgets)<2 else 'flatline' if len({r['value'] for r in values})==1 else 'varying'))
    return dict(transfer_proof=dict(status='insufficient_data' if transfers else 'not_applicable',native_claim_ready=False,sources=transfers),
        lm_flatline=flat or [{'status':'not_applicable'}],
        engine_roles=[dict(engine=engine,role='challenger' if any(g['engine']==engine and g['aggregation_label']=='gain' for g in groups) else 'watch',
            status='provisional' if any(g['engine']==engine and g['aggregation_label']=='gain' for g in groups) else 'insufficient_data',reason='paired change evidence; portfolio leadership needs repeated all-system family comparisons')
            for engine in sorted({r['engine'] for r in rows if r['engine']!='contenders'})])


def descriptive_evidence(rows):
    """Observed ranks stay inside label/pack/budget/seed/protocol partitions."""
    from .evidence import best_rows, comparison_groups
    best=best_rows(rows)
    cases=defaultdict(list)
    for row in best:
        cases[(row['label'],row['pack'],row['budget'],row['seed'],row['case_id'],row['benchmark'])].append(row)
    ranks=[]
    project_ranks=[]
    margins=[]
    ceilings=[]
    for key,values in sorted(cases.items()):
        for partition in comparison_groups(values):
            eligible=[r for r in partition if r['status']=='ok' and r['accounting_state']=='complete' and r['operating_state'] not in ('exploratory','reference')]
            if not eligible:
                continue
            scores=[-r['value'] if r['direction']=='max' else r['value'] for r in eligible]
            ranked=rankdata(scores,method='average')
            for row,rank in zip(eligible,ranked,strict=True):
                ranks.append(dict(label=row['label'],case_id=row['case_id'],run_id=row['run_id'],engine=row['engine'],
                    pack=row['pack'],budget=row['budget'],seed=row['seed'],benchmark=row['benchmark'],family=row['family'],
                    rank=float(rank),participants=len(eligible),best_observed=True,decision_grade=False))
            projects=[r for r in eligible if r['engine']!='contenders']
            project_scores=[-r['value'] if r['direction']=='max' else r['value'] for r in projects]
            context=sorted((r['engine'],r['git_commit'],json.dumps(r['comparison_policy'],sort_keys=True)) for r in projects)
            for row,rank in zip(projects,rankdata(project_scores,method='average'),strict=True):
                project_ranks.append(dict(label=row['label'],case_id=row['case_id'],run_id=row['run_id'],engine=row['engine'],
                    pack=row['pack'],budget=row['budget'],seed=row['seed'],benchmark=row['benchmark'],family=row['family'],
                    rank=float(rank),participants=len(projects),context=context,view='projects_only'))
            floor_ids={r['run_id'] for r in eligible if r['engine']=='contenders' and r['operating_state'] in ('trusted-core','trusted-extended')}
            floor=[r for r in rows if r['run_id'] in floor_ids and r['label']==key[0] and r['case_id']==key[4] and r['benchmark']==key[5] and r['engine']=='contenders' and r['status']=='ok' and r.get('required_floor',False)]
            if floor:
                baseline=(max if floor[0]['direction']=='max' else min)(floor,key=lambda r:r['value'])
                for row in eligible:
                    if row['engine']!='contenders':
                        delta=(row['value']-baseline['value'])*(1 if row['direction']=='max' else -1)
                        margins.append(dict(label=row['label'],pack=row['pack'],budget=row['budget'],seed=row['seed'],
                            engine=row['engine'],benchmark=row['benchmark'],family=row['family'],raw_margin=delta,
                            floor_outcome=baseline['outcome_id'],floor_run_id=baseline['run_id']))
            ceiling=[r for r in eligible if r['ceiling'] is not None and r['value']==r['ceiling']]
            if len(ceiling)>1:
                ceilings.append(dict(case_id=key[4],benchmark=key[5],engines=[r['engine'] for r in ceiling],win_credit=0))
    slopes=[]
    budget_groups=defaultdict(list)
    for row in best:
        if row['status']=='ok':
            budget_groups[(row['label'],row['pack'],row['engine'],row['benchmark'],row['seed'])].append(row)
    for key,values in sorted(budget_groups.items()):
        ordered=sorted(values,key=lambda r:r['budget'])
        for left,right in zip(ordered,ordered[1:]):
            if left['budget']==right['budget']:
                continue
            # Budget is the explicit intervention; the remaining runtime/data policy must match.
            a={k:v for k,v in left['comparison_policy'].items() if k!='budget'}
            b={k:v for k,v in right['comparison_policy'].items() if k!='budget'}
            compatible=a==b and left['git_commit']==right['git_commit'] and bool(left.get('data_binding')) and left.get('data_binding')==right.get('data_binding')
            left_envelope=left['comparison_policy'].get('budget',{})
            right_envelope=right['comparison_policy'].get('budget',{})
            compatible=compatible and {k:v for k,v in left_envelope.items() if k!='evaluation'}=={k:v for k,v in right_envelope.items() if k!='evaluation'}
            slopes.append(dict(label=key[0],pack=key[1],engine=key[2],benchmark=key[3],seed=key[4],
                from_budget=left['budget'],to_budget=right['budget'],status='descriptive' if compatible else 'blocked',
                slope=(right['value']-left['value'])*(1 if left['direction']=='max' else -1)/(right['budget']-left['budget']) if compatible else None))
    reported_diagnostics=diagnostics(rows,[])
    reported_diagnostics['engine_roles']=portfolio_roles(best,project_ranks)
    return dict(rank_distribution=ranks,projects_only_rank_distribution=project_ranks,score_distribution=best,contender_floor_margins=margins,
        ceiling_ties=ceilings,budget_slopes=slopes,runtime_tradeoffs=_runtime(rows),
        diagnostics=reported_diagnostics,friedman={'status':'insufficient_data','reason':'current portfolio has at most five systems; asymptotic test unqualified'})


def portfolio_roles(rows,ranks):
    """Provisional roles require repeated clean native leads on a fixed panel."""
    roles=[]
    for engine in sorted({r['engine'] for r in rows if r['engine']!='contenders'}):
        own=[r for r in rows if r['engine']==engine]
        admissible={r['run_id'] for r in own if r['backend']=='mlx_native' and r.get('source_clean') and r.get('quality_level') in ('L3','L4') and r['operating_state'] in ('trusted-core','trusted-extended') and r['value']!=r['ceiling']}
        families=defaultdict(list)
        for rank in ranks:
            if rank['run_id'] in admissible and rank['participants']>=2:
                families[(rank['label'],rank['pack'],rank['budget'],rank['family'],json.dumps(rank['context'],sort_keys=True))].append(rank)
        findings=[]
        for key,values in sorted(families.items()):
            seeds={r['seed'] for r in values}
            benchmarks={r['benchmark'] for r in values}
            if len(seeds)<3 or len(values)!=len(seeds)*len(benchmarks):
                continue
            seed_ranks=[statistics.mean(r['rank'] for r in values if r['seed']==seed) for seed in seeds]
            findings.append(dict(label=key[0],pack=key[1],budget=key[2],family=key[3],comparison_context=json.loads(key[4]),seeds=sorted(seeds),mean_rank=statistics.mean(seed_ranks),repeated_leader=all(rank==1 for rank in seed_ranks)))
        leads=[f for f in findings if f['repeated_leader']]
        role='watch'
        if findings and len(leads)==len(findings):
            role='leader_candidate'
        elif leads:
            role='specialist'
        elif any(f['mean_rank']<=2 for f in findings):
            role='challenger'
        roles.append(dict(engine=engine,role=role,status='provisional' if findings else 'insufficient_data',family_evidence=findings,
            seed_source_status='insufficient_data: downstream native transfer proof required'))
    return roles
