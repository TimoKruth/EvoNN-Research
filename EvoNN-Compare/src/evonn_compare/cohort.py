"""Explicit, source-bound within-cohort inference; never promotes an engine PR.

Engine, required-floor, named-floor and budget contrasts retain their actual
identities. No synthetic before/after labels or rewritten historical rows.
"""
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
import time
import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .statistics import paired_inference, minimum_seeds, _runtime

NATIVE = ('prism', 'topograph', 'stratograph', 'primordia')


class Arm(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    engine: Literal['prism', 'topograph', 'stratograph', 'primordia', 'contenders']
    budget: int = Field(gt=0)
    selection: Literal['winner', 'required_floor', 'named_contender'] = 'winner'
    contender: str | None = None

    @model_validator(mode='after')
    def selection_contract(self):
        if self.engine == 'contenders' and self.selection == 'winner':
            raise ValueError('choose required_floor or one named contender explicitly')
        if self.engine != 'contenders' and self.selection != 'winner':
            raise ValueError('native arm must select its exported winner')
        if (self.selection == 'named_contender') != bool(self.contender):
            raise ValueError('named_contender requires exactly one contender name')
        return self


class Panel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(min_length=1)
    pack: str
    reference: Arm
    target: Arm
    benchmarks: list[str] = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)

    @model_validator(mode='after')
    def contrast_contract(self):
        if self.target.engine not in NATIVE:
            raise ValueError('target must be a native engine')
        if self.reference == self.target:
            raise ValueError('distinct arms required')
        if self.reference.budget != self.target.budget and self.reference.engine != self.target.engine:
            raise ValueError('change engine or budget, not both')
        if len(set(self.seeds)) != len(self.seeds) or len(set(self.benchmarks)) != len(self.benchmarks):
            raise ValueError('duplicate seed or benchmark')
        if any(seed < 0 or seed >= 2**32 for seed in self.seeds):
            raise ValueError('seed outside uint32 range')
        return self


class CohortRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    schema_version: Literal[1] = 1
    policy: Literal['within-cohort-relative-v1'] = 'within-cohort-relative-v1'
    label: str = Field(min_length=1)
    source_revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    materiality: float = Field(default=.01, ge=0)
    panels: list[Panel] = Field(min_length=1)
    campaigns: list['CampaignBinding'] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_panels(self):
        if len({p.id for p in self.panels}) != len(self.panels):
            raise ValueError('duplicate panel id')
        contrasts = [json.dumps(p.model_dump(exclude={'id'}), sort_keys=True) for p in self.panels]
        if len(set(contrasts)) != len(contrasts):
            raise ValueError('duplicate contrast')
        return self


class CampaignBinding(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    path: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def absolute_manifest(self):
        if not Path(self.path).is_absolute() or Path(self.path).name != 'campaign.json':
            raise ValueError('absolute campaign.json path required')
        return self


CohortRequest.model_rebuild()


def _budget_shape(row):
    """Evaluation total and its exact derived training cap form one intervention."""
    budget = json.loads(json.dumps(row['comparison_policy']['budget']))
    if 'training' in budget:
        training = budget['training']
        if training['total_cap'] != training['per_candidate'] * row['budget']:
            raise ValueError('training cap is not the declared per-fit cap times fit budget')
        training.pop('total_cap')
    budget.pop('evaluation')
    return budget


def _select(rows, arm, panel):
    available = [r for r in rows if r['engine'] == arm.engine and r['budget'] == arm.budget
                 and r['pack'] == panel.pack and r['seed'] in panel.seeds and r['benchmark'] in panel.benchmarks]
    if arm.selection == 'required_floor':
        available = [r for r in available if r.get('required_floor')]
    elif arm.selection == 'named_contender':
        available = [r for r in available if r.get('contender_id') == arm.contender]
    cells = defaultdict(list)
    for row in available:
        cells[row['seed'], row['benchmark']].append(row)
    picked, blockers = {}, []
    for seed in sorted(panel.seeds):
        for benchmark in sorted(panel.benchmarks):
            candidates = cells[seed, benchmark]
            if not candidates:
                blockers.append(f'{arm.engine}@{arm.budget}: missing {benchmark}/seed{seed}')
                continue
            if arm.selection == 'required_floor':
                from evonn_shared.active_catalog import get_benchmark
                required = set(get_benchmark(benchmark).required_contenders)
                successful = {r.get('contender_id') for r in candidates if r['status'] == 'ok'}
                if not required or not required <= successful:
                    blockers.append(f'incomplete required floor for {benchmark}/seed{seed}')
            if len({r['run_id'] for r in candidates}) != 1:
                blockers.append('duplicate run for an expected arm/seed/benchmark')
            if len({r['outcome_id'] for r in candidates}) != len(candidates):
                blockers.append('duplicate outcome observation')
            if len({(r['metric'], r['direction'], r['ceiling']) for r in candidates}) != 1:
                blockers.append('metric semantics differ within a cell')
            valid = [r for r in candidates if r['status'] == 'ok' and r['value'] is not None and math.isfinite(r['value'])]
            if len(valid) != len(candidates):
                blockers.append('failed or nonfinite expected outcome')
            if valid:
                picked[seed, benchmark] = sorted(valid, key=lambda r: (
                    -r['value'] if r['direction'] == 'max' else r['value'], r['outcome_id']))[0]
    return picked, available, blockers


def _panel(rows, request, panel, artifacts_verified):
    a, full_a, blockers_a = _select(rows, panel.reference, panel)
    b, full_b, blockers_b = _select(rows, panel.target, panel)
    blockers = blockers_a + blockers_b
    full = full_a + full_b
    if not artifacts_verified:
        blockers.append('current external-artifact revalidation required')
    if not full or any(r.get('git_commit') != request.source_revision for r in full):
        blockers.append('source revision differs from explicit cohort revision')
    if any(not r.get('source_clean') or r.get('quality_level') not in ('L3', 'L4') for r in full):
        blockers.append('clean source and verified L3 artifacts required')
    if any(r['accounting_state'] != 'complete' or r['operating_state'] not in ('contract-fair', 'trusted-core', 'trusted-extended') for r in full):
        blockers.append('unfair or incomplete lane')
    if any(r['backend'] != ('sklearn_contender' if r['engine'] == 'contenders' else 'mlx_native') for r in full):
        blockers.append('native engines and reviewed CPU contender backend required')
    if any(r['engine'] == 'contenders' and r['operating_state'] not in ('trusted-core', 'trusted-extended') for r in full):
        blockers.append('verified contender admission required')
    run_classes = {r.get('run_class', 'local') for r in full}
    if len(run_classes) != 1:
        blockers.append('run classes differ')
    minimum = max((minimum_seeds(panel.pack, value) for value in run_classes), default=3)
    if len(panel.seeds) < minimum:
        blockers.append(f'at least {minimum} independent paired seeds required')
    # Repeated seeds within each arm must use the exact same full policy.
    for values in (full_a, full_b):
        if len({json.dumps(r.get('comparison_policy'), sort_keys=True) for r in values}) != 1:
            blockers.append('within-arm runtime or training policy drift')
    if {r['run_id'] for r in full_a} & {r['run_id'] for r in full_b}:
        blockers.append('same run reused in both arms')
    for key in sorted(set(a) & set(b)):
        left, right = a[key], b[key]
        if not left.get('data_binding') or left['data_binding'] != right.get('data_binding'):
            blockers.append('paired data/split provenance differs')
        if (left['metric'], left['direction'], left['ceiling']) != (right['metric'], right['direction'], right['ceiling']):
            blockers.append('paired metric/direction/ceiling differs')
        pa, pb = left['comparison_policy'], right['comparison_policy']
        if left['seeding'] != right['seeding']:
            blockers.append('seeding regimes differ')
        if left['engine'] == right['engine']:
            if {k:v for k,v in pa.items() if k != 'budget'} != {k:v for k,v in pb.items() if k != 'budget'}:
                blockers.append('budget contrast changed runtime or training policy')
            try:
                same_budget_shape = _budget_shape(left) == _budget_shape(right)
            except (ValueError, KeyError, TypeError):
                same_budget_shape = False
            if not same_budget_shape:
                blockers.append('budget contrast changed another budget dimension')
        elif pa['budget'] != pb['budget']:
            blockers.append('cross-engine budget envelopes differ')
        if left['engine'] != 'contenders':
            if not left.get('comparison_fingerprint') or left['comparison_fingerprint'] != right.get('comparison_fingerprint'):
                blockers.append('shared native training/runtime identity differs')
        elif (left['host_fingerprint'] != right['host_fingerprint'] and
              (not left.get('matched_host_fingerprint') or left['matched_host_fingerprint'] != right.get('matched_host_fingerprint'))):
            blockers.append('floor and target host differ')
    # Keep actual arm identities in runtime output; full attempt allocations are
    # not synthesized into a fake before/after experiment.
    runtime = {'reference': _runtime(full_a), 'target': _runtime(full_b)}
    if not all(value['complete'] for value in runtime.values()):
        blockers.append('complete attempt runtime and family measurements required')
    effects, raw, excluded, ties = [], [], [], 0
    complete = len(a) == len(b) == len(panel.seeds) * len(panel.benchmarks)
    if not blockers and complete:
        excluded = [benchmark for benchmark in panel.benchmarks if all(
            a[seed,benchmark]['value'] == b[seed,benchmark]['value'] == a[seed,benchmark]['ceiling'] for seed in panel.seeds)]
        for seed in sorted(panel.seeds):
            seed_effects = []
            for benchmark in sorted(panel.benchmarks):
                left, right = a[seed,benchmark], b[seed,benchmark]
                ceiling_tie = left['value'] == right['value'] == left['ceiling']
                ties += int(ceiling_tie)
                delta = (right['value'] - left['value']) * (1 if left['direction'] == 'max' else -1)
                scale = abs(left['value']) + abs(right['value'])
                value = 2 * delta / scale if scale else 0.
                raw.append(dict(seed=seed, benchmark=benchmark, reference=left['value'], target=right['value'],
                    reference_run_id=left['run_id'], target_run_id=right['run_id'], reference_outcome=left['outcome_id'],
                    target_outcome=right['outcome_id'], delta=delta, effect=value, ceiling_tie=ceiling_tie))
                if benchmark not in excluded:
                    seed_effects.append(value)
            if seed_effects:
                effects.append(statistics.mean(seed_effects))
    inference = paired_inference(effects, materiality=request.materiality)
    ready = not blockers and complete and len(effects) == len(panel.seeds)
    label = 'needs_more_runs' if len(panel.seeds) < minimum or not complete else 'inconclusive'
    if ready:
        low, high = inference['bootstrap_ci95']
        if -request.materiality <= low <= high <= request.materiality:
            label = 'no_material_change'
        elif high < -request.materiality:
            label = 'regression'
        elif low > request.materiality:
            label = 'likely_gain'
    return dict(**panel.model_dump(exclude={'seeds'}), **inference, seeds=sorted(panel.seeds), minimum_seeds=minimum,
        level='L4' if ready else 'L3', statistical_label=label, aggregation_label='inconclusive' if ready else 'blocked',
        blockers=sorted(set(blockers)), seed_effects=effects, raw_deltas=raw, excluded_benchmarks=sorted(excluded),
        ceiling_ties=ties, runtime_tradeoffs=runtime,
        view='contender_including' if panel.reference.engine == 'contenders' else 'engines_only',
        fully_saturated=complete and not blockers and not effects)


def analyze_cohort(rows, request, *, artifacts_verified=False):
    request = CohortRequest.model_validate(request)
    selected = [r for r in rows if r['label'] == request.label]
    groups = [_panel(selected, request, panel, artifacts_verified) for panel in request.panels]
    tested = sorted([g for g in groups if g['wilcoxon']['status'] == 'available'], key=lambda g:g['wilcoxon']['pvalue'])
    previous = 0.
    for index, group in enumerate(tested):
        # Unavailable tests remain in the declared family (equivalent to p=1).
        # A missing or saturated contrast cannot strengthen another contrast.
        adjusted = max(previous, min(1., group['wilcoxon']['pvalue'] * (len(groups)-index)))
        previous = adjusted
        group['wilcoxon']['holm_pvalue'] = adjusted
        if group['statistical_label'] == 'likely_gain' and adjusted <= .05:
            group['statistical_label'] = 'clear_gain'
    for group in groups:
        if group['level'] == 'L4' and group['statistical_label'] == 'no_material_change':
            group['aggregation_label'] = 'no_material_change'
        elif group['level'] == 'L4' and group['statistical_label'] == 'clear_gain':
            group['aggregation_label'] = 'gain'
    return dict(schema_version=1, request=request.model_dump(), groups=groups,
        status='blocked' if any(g['blockers'] for g in groups) else 'evaluated',
        decision_category='inconclusive', engine_advancement_authorized=False,
        limitations=['L4 is evidence quality, not automatic promotion or a causal claim.',
            'Seed bootstrap intervals are descriptive at small samples; ceiling ties have no win credit.',
            'These contrasts do not establish preregistration, protected-test performance or transfer.'])


def cohort_report(registry, request, *, require_artifacts=False):
    """Validate historical receipts, then rederive a separate current projection."""
    from .registry import validate_registry, read_registry, _relocation, _load_source, _observations
    from .workspace import ownership, derived, encoded
    with ownership(Path(registry)) as root:
        from evonn_shared.runtime_io import code_identity, source_identity
        commit, dirty = code_identity()
        consumer = dict(git_commit=commit, code_dirty=dirty, source_sha256=source_identity())
        started = time.monotonic()
        parsed = CohortRequest.model_validate(request)
        validation = validate_registry(root, require_artifacts=require_artifacts)
        if validation['status'] != 'passed':
            raise ValueError('; '.join(validation['blockers']))
        validated_at = time.monotonic()
        records = [r for r in read_registry(root) if r['label'] == parsed.label and r['decision_status'] not in ('superseded', 'rejected')]
        rows = []
        roots = _relocation(root) if require_artifacts else None
        campaigns = []
        if require_artifacts:
            from evonn_shared.artifact_io import read_verified_artifact
            from evonn_shared.telemetry import ArtifactReference
            from .campaign import CampaignSpec, sha
            for binding in parsed.campaigns:
                path = Path(binding.path)
                payload = read_verified_artifact(path.parent, ArtifactReference(path=path.name, sha256=binding.sha256), max_bytes=16*1024**2)
                manifest = json.loads(payload)
                if (manifest['sha256'] != sha({k:v for k,v in manifest.items() if k != 'sha256'}) or
                        manifest['schema_version'] != 'evonn.campaign/v1' or manifest['workspace'] != str(path.parent)):
                    raise ValueError('invalid bound campaign manifest')
                CampaignSpec.model_validate(manifest['spec'])
                if manifest['identity']['commit'] != parsed.source_revision:
                    raise ValueError('campaign source differs from requested cohort')
                campaigns.append(manifest)
        for record in records:
            if require_artifacts:
                binding = next(b for b in record['case_runs'] if b['run_id'] == record['run_id'])
                bundle = _load_source(binding, roots)
                acceptance = dict(cohort=record['case_document']['cohort'], engine_only=record['case_document']['no_contenders'],
                    operating_state=record['lane_trust_state'], accounting_state=record['budget_accounting_state'], repeatability_state=record['repeatability_state'])
                current = _observations(bundle, record['case_id'], acceptance, record['label'], record['output_quality_level'])
                for manifest in campaigns:
                    from .campaign import slot_id
                    from .cases import Case
                    from evonn_shared.runtime_io import encode
                    system = bundle.manifest.system.value
                    spec = manifest['spec']
                    if (record['pack'] != spec['pack'] or record['budget'] not in spec['budgets'] or
                            record['seed'] not in spec['seeds'] or system not in spec['systems']):
                        continue
                    slot = slot_id(Case(record['pack'], record['budget'], record['seed']), system)
                    expected = Path(manifest['workspace'])/'runs'/slot/record['run_id']/'symbiosis'
                    if str(expected) != binding['path']:
                        continue
                    host = manifest['identity']['host']
                    fields = dict(zip(('host','system','machine','processor'), host, strict=True))
                    codec = encoded if system == 'contenders' else encode
                    expected_hash = hashlib.sha256(codec(fields)).hexdigest()
                    if bundle.manifest.runtime.host_fingerprint != expected_hash:
                        raise ValueError('export host differs from bound campaign host')
                    canonical_host = hashlib.sha256(encoded(fields)).hexdigest()
                    for row in current:
                        row['matched_host_fingerprint'] = canonical_host
                rows.extend(current)
            else:
                rows.extend(record['observations'])
        projected_at = time.monotonic()
        result = analyze_cohort(rows, parsed, artifacts_verified=require_artifacts)
        result['consumer'] = consumer
        result['timing_seconds'] = dict(validation=validated_at-started, projection=projected_at-validated_at,
            inference=time.monotonic()-projected_at)
        result['registry'] = dict(validation=validation, record_ids=[r['record_id'] for r in records],
            index_sha256=hashlib.sha256((root/'index.jsonl').read_bytes()).hexdigest())
        # Separate filenames: neither immutable rows nor historical derived reports change.
        derived(root / 'cohort_report.json', encoded(result))
        table = '# Within-cohort evidence\n\nNo engine advancement is authorized by this report.\n\n| Panel | Level | Seeds | Label |\n|---|---|---|---|\n'
        for group in result['groups']:
            table += f"| {group['id']} | {group['level']} | {group['n']} | {group['statistical_label']} |\n"
            table += ''.join('\nBlocker: '+b+'\n' for b in group['blockers'])
        derived(root / 'cohort_report.md', table.encode())
        return result
