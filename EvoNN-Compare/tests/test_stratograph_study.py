"""Preparation/analysis controls for an explicitly authorized within-engine study."""
from collections import Counter
import json
from pathlib import Path

import pytest

from evonn_compare import stratograph_study as study
from evonn_compare.campaign import CampaignSpec
from evonn_shared.hierarchy_policy import HierarchyResearchPolicy


def plan():
    spec = study.StudySpec()
    return dict(spec=spec.model_dump(), slots=study.slots(spec), hypotheses=study.hypotheses(spec), sha256='test', cache='/tmp/test-cache')


def test_matrix_has_all_versions_matched_cells_and_disjoint_stages():
    spec = study.StudySpec()
    cells = study.slots(spec)
    assert len(cells) == 374
    assert sum(slot['config']['budget'] for slot in cells) == 45408
    assert Counter(s['stage'] for s in cells) == {'main': 352, 'qualification': 22}
    grouped = Counter((s['stage'], s['config']['pack'], s['config']['seed']) for s in cells)
    assert set(grouped.values()) == {11}
    assert cells[0]['stage'] == cells[21]['stage'] == 'qualification'
    assert cells[22]['stage'] == 'main'
    assert len(study.hypotheses(spec)) == 30
    assert len({s['id'] for s in cells}) == len(cells)
    assert study.slots(spec) == cells
    with pytest.raises(ValueError, match='every engine'):
        CampaignSpec(systems=['stratograph'], stratograph_research=HierarchyResearchPolicy())


@pytest.mark.parametrize('changes', [dict(arms=['hybrid']), dict(seeds=[42]*16),
                                    dict(seeds=list(range(8))), dict(qualification_seed=1701),
                                    dict(budget=129), dict(timeout=1800.)])
def test_spec_rejects_underpowered_unpaired_or_unbounded_inputs(changes):
    with pytest.raises(ValueError):
        study.StudySpec(**changes)


def test_prepare_only_prepares_data_never_dispatches_training(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'identity', lambda: {'source': 'frozen'})
    calls = []
    def fake_process(command, timeout, log):
        assert command[2:4] == ['evonn_compare.campaign_worker', 'prepare']
        calls.append(command)
        Path(command[-1]).write_text(json.dumps({'benchmark_id': command[4], 'seed': int(command[5])}))
    monkeypatch.setattr(study, '_bounded_process', fake_process)
    monkeypatch.setattr(study, 'preflight', lambda root: {'status': 'passed', 'training_started': False})
    root = tmp_path/'study'
    assert study.prepare(root, tmp_path/'cache', study.StudySpec())['training_started'] is False
    assert len(calls) == 119
    manifest = study.read_plan(root)
    assert len(manifest['datasets']) == 119
    assert manifest['scope'] == study.SCOPE
    assert not (root/'runs').exists()
    data = json.loads((root/'study.json').read_text())
    data['slots'].pop()
    (root/'study.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='hash'):
        study.read_plan(root)


def test_effects_pair_seeds_and_keep_ties_as_zero():
    spec = study.StudySpec()
    observations = {}
    for seed in spec.seeds:
        for arm, error in [('v2_reference', 10.), ('hybrid', 8.)]:
            observations[(arm, 'language_breadth_v1', seed)] = {'metrics': {'delayed_copy_lm': error}}
    values = study.effects_for_panel(observations, spec, 'hybrid', 'memory')
    assert values == pytest.approx([2/9]*16)
    observations[('hybrid', 'language_breadth_v1', spec.seeds[0])]['metrics']['delayed_copy_lm'] = 10.
    assert study.effects_for_panel(observations, spec, 'hybrid', 'memory')[0] == 0.
    del observations[('hybrid', 'language_breadth_v1', spec.seeds[1])]
    with pytest.raises(KeyError):
        study.effects_for_panel(observations, spec, 'hybrid', 'memory')


def test_missing_cells_keep_the_full_hypothesis_family_and_block_claims(tmp_path, monkeypatch):
    monkeypatch.setattr(study, 'read_plan', lambda root: plan())
    report = study.analyze(tmp_path)
    assert report['status'] == 'incomplete'
    assert len(report['missing']) == 374
    assert len(report['contrasts']) == 30
    assert all(c['holm_pvalue'] == 1 and not c['material_gain'] for c in report['contrasts'])


def test_pause_does_not_dispatch_and_failure_cannot_be_silently_retried(tmp_path, monkeypatch):
    manifest = plan()
    monkeypatch.setattr(study, 'preflight', lambda root: None)
    monkeypatch.setattr(study, 'read_plan', lambda root: manifest)
    monkeypatch.setattr(study, '_bounded_process', lambda *a, **kw: pytest.fail('must not dispatch'))
    (tmp_path/'PAUSE').touch()
    assert study.run_session(tmp_path)['status'] == 'paused'
    state = json.loads((tmp_path/'status.json').read_text())
    state['failures'] = [{'slot': 'qualification', 'reason': 'retained failed fit'}]
    (tmp_path/'status.json').write_text(json.dumps(state))
    with pytest.raises(ValueError, match='no automatic retry'):
        study.run_session(tmp_path)


def test_timeout_is_recorded_as_failure_and_blocks_main(tmp_path, monkeypatch):
    import subprocess
    manifest = plan()
    monkeypatch.setattr(study, 'preflight', lambda root: None)
    monkeypatch.setattr(study, 'read_plan', lambda root: manifest)
    monkeypatch.setattr(study, 'adopt', lambda *args: (None, None))
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('fake', 1)
    monkeypatch.setattr(study, '_bounded_process', timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        study.run_session(tmp_path)
    state = json.loads((tmp_path/'status.json').read_text())
    assert state['status'] == 'incomplete'
    assert state['failures'][0]['slot'].startswith('qualification-')
    assert state['completed'] == {}


def test_successful_dispatch_requires_replay_and_resumes_next_slot(tmp_path, monkeypatch):
    manifest = plan()
    monkeypatch.setattr(study, 'preflight', lambda root: None)
    monkeypatch.setattr(study, 'read_plan', lambda root: manifest)
    invoked = []
    def adopt(root, saved, slot):
        run = root/'runs'/slot['id']/'fake'
        if not run.exists():
            return None, None
        return run, dict(export=str(run.relative_to(root)), documents={})
    def process(command, timeout, log, **kwargs):
        invoked.append(command)
        log.write_text('test double, no model fits')
        if command[3] == 'run':
            output = Path(command[command.index('--output')+1])/'fake'
            output.mkdir(parents=True)
        else:
            assert command[3] == 'replay'
            kwargs['stdout_path'].write_text('{"status":"passed"}')
    monkeypatch.setattr(study, 'adopt', adopt)
    monkeypatch.setattr(study, '_bounded_process', process)
    first = study.run_session(tmp_path, max_runs=1)
    assert first['completed'] == 1 and first['status'] == 'paused'
    second = study.run_session(tmp_path, max_runs=1)
    assert second['completed'] == 2
    assert [c[3] for c in invoked] == ['run', 'replay', 'run', 'replay']
    state = json.loads((tmp_path/'status.json').read_text())
    assert set(state['completed']) == {s['id'] for s in manifest['slots'][:2]}
