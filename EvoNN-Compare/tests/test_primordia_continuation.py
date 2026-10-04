import json
from pathlib import Path
import subprocess
import sys

import pytest

from evonn_compare import campaign as c
from evonn_compare import primordia_study as study


def test_extended_time_is_scoped_to_segmented_primordia():
    spec = study.specification('full_steady', 'language_breadth_v1').model_dump(mode='json')
    assert c.CampaignSpec.model_validate({**spec, 'timeout': 36000.0}).timeout == 36000
    for value in (1741., 1800., 36001.):
        with pytest.raises(ValueError):
            c.CampaignSpec.model_validate({**spec, 'timeout': value})
    with pytest.raises(ValueError):
        c.CampaignSpec(timeout=36000.0)


def test_segment_completion_resumes_without_replacement(tmp_path, monkeypatch):
    spec = study.specification('full_steady', 'language_breadth_v1').model_dump(mode='json')
    spec.update(timeout=36000.0, seeds=[23101, 23102])
    root = tmp_path/'campaign'
    root.mkdir()
    manifest = dict(spec=spec, sha256='a'*64, cache='/cache')
    model_run = root/'run'
    model_run.mkdir()
    (model_run/'config.yaml').write_text('{}')
    completed = 0
    calls = []
    history = []
    monkeypatch.setattr(c, 'preflight', lambda root: None)
    monkeypatch.setattr(c, 'read_manifest', lambda root: manifest)
    monkeypatch.setattr(c, 'events', lambda *a: history)
    monkeypatch.setattr(c, 'active_dispatch', lambda *a: None)
    monkeypatch.setattr(c, 'workspace_report', lambda *a: None)
    monkeypatch.setattr(c, 'match_config', lambda *a: None)
    def adopt(root, manifest, case, system):
        assert case.seed == 23102, 'must not revalidate other declared seeds before dispatch'
        return model_run if completed else None, {'run_id':'same'} if completed == 256 else None
    monkeypatch.setattr(c, 'adopted', adopt)
    monkeypatch.setattr(c, 'load_runtime_checkpoint', lambda *a: (None, json.dumps(dict(completed=completed, elapsed=completed*5., attempts=[dict(status='ok')]*completed)).encode()))
    def dispatch(command, timeout, log, **kwargs):
        nonlocal completed
        event = json.loads(Path(command[-2]).read_text())
        calls.append(event['details']['command'])
        assert timeout == 1760
        completed += 128
    monkeypatch.setattr(c, '_bounded_process', dispatch)
    target = c.Case('language_breadth_v1', 256, 23102)
    first = c.run_campaign(root, max_runs=1, only_case=target)
    assert first['status'] == 'paused' and first['new_runs'] == 1
    second = c.run_campaign(root, max_runs=1, only_case=target)
    assert second['status'] == 'paused' and completed == 256 and second['completed'] == 1 and second['total'] == 2
    assert '--resume' not in calls[0] and calls[1][-2:] == ['--resume', str(model_run)]
    assert c.run_campaign(root, only_case=target)['new_runs'] == 0
    with pytest.raises(ValueError, match='outside'):
        c.run_campaign(root, only_case=c.Case('language_breadth_v1', 256, 999))


def test_real_extended_run_keeps_prefix_and_replays(tmp_path):
    def invoke(*args):
        result = subprocess.run([sys.executable, '-m', 'evonn_primordia.cli', *map(str, args)],
                                capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout+result.stderr
        return result.stdout.strip()
    config = tmp_path/'config.json'
    config.write_text(json.dumps(dict(pack='tier_b_core_v2', budget=4, seed=21991, epochs=1,
                                     timeout=36000., fit_timeout=30., backend='numpy_fallback', max_width=8, max_depth=2)))
    # Advance only the test clock after two real worker results. This exercises
    # the automatic session boundary without waiting 29 minutes.
    program = """
import sys
from evonn_primordia import run
from evonn_primordia.cli import main
original_process, original_time = run._process, run.time.monotonic
count, offset = 0, 0.
def process(*args, **kwargs):
    global count, offset
    result = original_process(*args, **kwargs)
    if args[1] == '_worker':
        count += 1
        if count == 2:
            offset = 1720.
    return result
run._process = process
run.time.monotonic = lambda: original_time() + offset
sys.argv[0] = 'primordia'
main()
"""
    first = subprocess.run([sys.executable, '-c', program, 'run', '--config', str(config),
                            '--output', str(tmp_path/'runs'), '--cache', str(tmp_path/'cache')],
                           capture_output=True, text=True, timeout=120)
    assert first.returncode == 0, first.stdout + first.stderr
    run = Path(first.stdout.strip()).parent
    prefix = json.loads((run/'state.json').read_text())
    assert prefix['completed'] == 2 and prefix['elapsed'] >= 1720
    invoke('run', '--resume', run)
    final = json.loads((run/'state.json').read_text())
    assert final['completed'] == 4 and final['attempts'][:2] == prefix['attempts']
    assert final['elapsed'] >= prefix['elapsed']
    assert all(a['status'] == 'ok' for a in final['attempts'])
    assert len(list((run/'invocation_clock').glob('*_end.json'))) == 2
    assert json.loads(invoke('replay', run))['status'] == 'passed'


def test_historical_verification_uses_original_producer(tmp_path, monkeypatch):
    from evonn_compare import primordia_continuation as continuation
    old_python = tmp_path/'old-producer/.venv/bin/python'
    monkeypatch.setattr(study, 'read_plan', lambda p: {'identity': {'python': str(old_python)}})
    def checked(command, **kwargs):
        assert command[0] == str(old_python)
        assert kwargs['cwd'] == tmp_path/'old-producer'
        assert "c.identity() != plan['identity']" in command[2]
        assert 'study.collect' in command[2]
        return subprocess.CompletedProcess(command, 0, stdout='{"verified": true}')
    monkeypatch.setattr(continuation.subprocess, 'run', checked)
    assert continuation.parent_snapshot(tmp_path/'old-study') == {'verified': True}


def test_unrecognized_cached_audit_is_rejected():
    from evonn_compare import primordia_continuation as continuation
    with pytest.raises(ValueError, match='unrecognized'):
        continuation.verify_cached_parent({'verified_preparation': {'sha256':'0'*64}})


def test_cached_audit_rejects_changed_export_bytes(tmp_path, monkeypatch):
    from evonn_compare import primordia_continuation as continuation
    parent = tmp_path/'parent'
    export = parent/'qualification/control/tier_b_core_v2/export'
    export.mkdir(parents=True)
    document = export/'manifest.json'
    expected = c.hashlib.sha256(b'original').hexdigest()
    document.write_bytes(b'changed')
    row = dict(campaign='qualification/control/tier_b_core_v2', phase='qualification', pack='tier_b_core_v2', seed=1,
               reference={'export':'export', 'documents':[{'path':'manifest.json', 'sha256':expected}]})
    previous = dict(parent_sha256='parent-proof', qualification=[row], inherited={}, retained_failure={})
    digest = c.sha(previous)
    old = tmp_path/'prepared'
    old.mkdir()
    (old/'continuation.json').write_bytes(c.encoded({**previous, 'sha256':digest}))
    monkeypatch.setattr(continuation, 'VERIFIED_PREPARATION_SHA', digest)
    plan = {**previous, 'parent':str(parent), 'verified_preparation':{'root':str(old), 'sha256':digest}}
    with pytest.raises(ValueError, match='historical document changed'):
        continuation.verify_cached_parent(plan)
