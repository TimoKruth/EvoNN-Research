"""Materialize the next staged study without data downloads, fits or schedulers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from evonn_compare.campaign import CampaignSpec
from evonn_shared.hierarchy_policy import HierarchyResearchPolicy
from evonn_shared.prism_policy import PrismResearchPolicy
from evonn_shared.primordia_policy import PrimordiaResearchPolicy
from evonn_shared.active_catalog import load_parity_pack
from prism.config import RunConfig as PrismConfig
from topograph.config import RunConfig as TopographConfig
from stratograph.config import RunConfig as StratographConfig
from evonn_primordia.config import RunConfig as PrimordiaConfig

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / 'governance/next-research-study-20260914.json'
SYSTEMS = ['prism', 'topograph', 'stratograph', 'primordia', 'contenders']
MODELS = dict(prism=PrismConfig, topograph=TopographConfig, stratograph=StratographConfig, primordia=PrimordiaConfig)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def policies():
    return dict(prism_research=PrismResearchPolicy().model_dump(mode='json'),
                topograph_variant='open',
                stratograph_research=HierarchyResearchPolicy(evaluator='trainable', normalization='rms').model_dump(mode='json'),
                primordia_research=PrimordiaResearchPolicy().model_dump(mode='json'))


def arms():
    result = {'refresh_reference': policies()}
    for variant in ['legacy', 'archive', 'training', 'broad']:
        p = policies()
        p['prism_research']['variant'] = variant
        result['prism_' + variant] = p
    fixed = policies()
    fixed['stratograph_research']['evolve_representation'] = False
    result['stratograph_fixed'] = fixed
    for label, field, value in [('proxy', 'evaluator', 'proxy'), ('no_norm', 'normalization', 'none'),
                                 ('train_standard', 'normalization', 'train_standard'),
                                 ('fresh', 'inheritance', 'fresh'), ('quality', 'selection', 'quality')]:
        p = deepcopy(fixed)
        p['stratograph_research'][field] = value
        result['stratograph_' + label] = p
    return result


def generate(output):
    protocol = json.loads(PROTOCOL.read_text())
    assert not output.exists(), 'Use a fresh output directory; existing plans are never overwritten'
    output.mkdir(parents=True)
    available = arms()
    assert len(available) == 11
    all_seeds = [seed for stage in protocol['stages'] for seed in stage['seeds']]
    assert len(all_seeds) == len(set(all_seeds)), 'Stage seed cohorts overlap'
    historic_seeds = set()

    def scan(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {'seed', 'seeds'}:
                    candidates = item if isinstance(item, list) else [item]
                    historic_seeds.update(v for v in candidates if type(v) is int)
                scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)

    files = subprocess.check_output(['git', 'ls-files', 'governance/*.json'], cwd=ROOT, text=True).splitlines()
    checked = []
    for name in files:
        path = ROOT / name
        if path == PROTOCOL:
            continue
        scan(json.loads(path.read_text()))
        checked.append(name)
    assert not set(all_seeds) & historic_seeds, 'Planned seed previously used in tracked governance'
    plans, configs, symbolic = [], 0, []
    for stage in protocol['stages']:
        for pack in stage['packs']:
            assert len(load_parity_pack(pack).benchmarks) == 4
            # Rotate arm order across seeds; reverse on alternate regime blocks.
            for regime_index, regime in enumerate(stage['regimes']):
                for seed_index, seed in enumerate(stage['seeds']):
                    names = stage['arms']
                    offset = seed_index % len(names)
                    ordered = names[offset:] + names[:offset]
                    if regime_index % 2:
                        ordered = ordered[::-1]
                    for arm_index, arm in enumerate(ordered):
                        ident = f"{stage['id']}-{pack}-{regime['id']}-s{seed}-{arm}"
                        order_offset = (seed_index + regime_index + arm_index) % 5
                        roster = SYSTEMS[order_offset:] + SYSTEMS[:order_offset]
                        if regime_index % 2:
                            roster = roster[::-1]
                        selected = arm == 'selected_bundle'
                        gated_compute = regime['mode'] != 'fixed_proposals'
                        row = dict(id=ident, stage=stage['id'], pack=pack, regime=regime, seed=seed,
                                   arm=arm, systems=roster, planned_runs=5,
                                   maximum_fit_attempts=5 * regime['proposal_limit'], dispatch_authorized=False)
                        if selected or gated_compute:
                            row.update(spec_file=None, status='conditional_not_executable', reasons=[])
                            if selected:
                                row['reasons'].append('Policy nomination must be frozen from screening, before opening confirmation seeds.')
                            if gated_compute:
                                row['reasons'].append('Versioned measured-training budget execution/export support is not implemented.')
                            symbolic.append(row)
                        else:
                            values = dict(pack=pack, budgets=[regime['proposal_limit']], seeds=[seed], systems=roster,
                                          backend='mlx_native', epochs=12, enhanced=True, timeout=1500.0,
                                          fit_timeout=90.0, min_free_bytes=20 * 1024**3, **available[arm])
                            spec = CampaignSpec.model_validate(values).model_dump(mode='json')
                            path = output / 'campaign-specs' / f'{ident}.json'
                            write(path, spec)
                            row.update(spec_file=str(path.relative_to(output)), spec_sha256=digest(path),
                                       status='schema_validated_not_preflighted')
                            for system in SYSTEMS[:-1]:
                                user = dict(pack=pack, budget=regime['proposal_limit'], seed=seed, epochs=12,
                                            population_size=4, backend='mlx_native', target_device='cpu',
                                            timeout=1500.0, fit_timeout=90.0)
                                if system == 'prism':
                                    user.update(spec['prism_research'])
                                elif system == 'topograph':
                                    user.update(variant=spec['topograph_variant'], benchmark_pooling=False, novelty_weight=0.0)
                                elif system == 'stratograph':
                                    user.update(variant='shared', research=spec['stratograph_research'])
                                else:
                                    user.update(spec['primordia_research'])
                                config = MODELS[system].model_validate(user).model_dump(mode='json')
                                write(output / 'engine-configs' / ident / f'{system}.json', config)
                                configs += 1
                        plans.append(row)
    total_runs = sum(row['planned_runs'] for row in plans)
    total_fits = sum(row['maximum_fit_attempts'] for row in plans)
    assert total_runs == protocol['maximum_runs'] and total_fits == protocol['maximum_fit_attempts']
    assert all(set(row['systems']) == set(SYSTEMS) for row in plans)
    assert len({row['id'] for row in plans}) == len(plans)
    write(output / 'matrix.json', plans)
    write(output / 'arms.json', available)
    write(output / 'validation.json', dict(status='planning_validation_passed', training_started=False,
          dispatch_authorized=False, protocol_sha256=digest(PROTOCOL), maximum_runs=total_runs,
          maximum_fit_attempts=total_fits, concrete_campaign_specs=len(plans) - len(symbolic),
          conditional_campaigns=len(symbolic), validated_native_configs=configs,
          seed_collision_check='No overlaps across stages or with seed fields in the listed tracked governance JSON.',
          seed_audit_files=checked, unresolved_gates=protocol['launch_gates']))
    print(json.dumps(dict(output=str(output), maximum_runs=total_runs, maximum_fit_attempts=total_fits,
                         concrete_campaign_specs=len(plans) - len(symbolic),
                         conditional_campaigns=len(symbolic), validated_native_configs=configs,
                         training_started=False), indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: prepare_next_study.py FRESH_OUTPUT_DIRECTORY (planning only)')
    generate(Path(sys.argv[1]).absolute())
