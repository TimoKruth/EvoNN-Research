"""Read-only status must distinguish valid pauses, stale jobs and old alerts."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location('evonn_status_skill', Path(__file__).parents[1] /
                                            '.agents/skills/read-evonn-status/scripts/status.py')
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path / '.artifacts/guardian'
    base = tmp_path / 'replacement/.artifacts/comparison'
    workspace = base / 'campaigns/case'
    write(workspace / 'campaign.json', {'spec': {'pack': 'p', 'budgets': [256], 'seeds': [59], 'systems': list(s.SYSTEMS)}})
    write(base / 'readiness.json', {'campaigns': [{'id': 'case', 'workspace': str(workspace)}]})
    write(workspace / 'events/1.json', {'kind': 'complete', 'slot': 'p_b256_s59_prism'})
    target = {'producer': str(tmp_path / 'replacement'), 'base': str(base)}
    write(root / 'control.json', {'mode': 'repair', 'target': target, 'source': {'host': ['fixed']},
                                'last_error': 'Guardian interrupted during a campaign invocation'})
    write(root / 'status.json', {'state': 'training', 'updated_at': '2026-09-10T12:00:00+00:00'})
    write(root / 'installation.json', {'label': 'test'})
    monkeypatch.setattr(s.platform, 'node', lambda: 'fixed')
    monkeypatch.setattr(s, 'service', lambda _: {'loaded': True, 'running': True, 'last_exit_code': 0})
    now = s.epoch('2026-09-10T12:20:00+00:00')
    return root, base, target, now


def summary(env, rows=None):
    root, _, _, now = env
    errors = []
    result = s.summarize(root, [], rows or [], now, errors)
    assert errors == []
    return result


def test_replacement_target_counts_and_crash_sentinel_not_failure(env):
    result = summary(env)
    assert result['target'] == env[2]
    assert result['progress']['completed'] == 1 and result['progress']['planned'] == 5
    assert result['current_error'] is None and result['warnings'] == []
    assert result['completion']['receipt_matches'] is False


def test_live_engine_verified_by_command_not_recorded_pid(env):
    root, base, _, _ = env
    rows = [dict(pid=9999999, state='S', elapsed='01:00', command=f'python -m topograph.cli run --budget 256 --seed 59 --output {base}/runs/x')]
    result = summary(env, rows)
    assert result['active_engines'][0]['system'] == 'topograph'
    rows[0]['command'] = 'unrelated program'
    assert summary(env, rows)['active_engines'] == []


def test_pause_and_current_hostname_drift(env, monkeypatch):
    (env[0] / 'PAUSE').touch()
    monkeypatch.setattr(s.platform, 'node', lambda: 'changed')
    result = summary(env)
    assert result['state'] == 'paused'
    assert result['warnings'] == ['hostname_drift']


def test_idle_service_normal_but_stale_status_is_not(env, monkeypatch):
    monkeypatch.setattr(s, 'service', lambda _: {'loaded': True, 'running': False, 'last_exit_code': 0})
    root, _, _, now = env
    write(root / 'status.json', {'state': 'progress', 'updated_at': '2026-09-10T12:19:30+00:00'})
    assert summary(env)['state'] == 'between_runs'
    assert summary(env)['warnings'] == []
    write(root / 'status.json', {'state': 'progress', 'updated_at': '2026-09-10T12:00:00+00:00'})
    assert 'guardian_status_stale_or_missing' in summary(env)['warnings']


def test_historical_error_not_current_failure(env):
    (env[0] / 'history.jsonl').write_text(json.dumps({'state': 'repair_pending', 'error': 'old drift',
                                                  'updated_at': '2026-09-10T11:00:00+00:00'}) + '\n')
    result = summary(env)
    assert len(result['historical_errors']) == 1
    assert result['current_error'] is None and result['warnings'] == []


def test_complete_requires_receipt_matching_counts_and_target(env):
    root, _, target, _ = env
    control = s.read(root / 'control.json', [])
    control['mode'] = 'complete'
    write(root / 'control.json', control)
    write(root / 'completion.json', {'target': target, 'verified': {'completed': 5, 'total': 5}})
    assert 'completion_receipt_missing_or_inconsistent' in summary(env)['warnings']


def test_discovery_does_not_guess_between_unfinished_guardians(tmp_path):
    for name in ['a', 'b']:
        root = tmp_path / '.artifacts' / name
        write(root / 'config.json', dict(state_root=str(root), protocol='p', producer='p', base='b', poll_seconds=60))
        write(root / 'control.json', {'mode': 'managed'})
    root, candidates, _ = s.discover(tmp_path, [])
    assert root is None and len(candidates) == 2


def test_duplicate_completion_and_malformed_json_not_silent(env):
    workspace = env[1] / 'campaigns/case'
    write(workspace / 'events/2.json', {'kind': 'complete', 'slot': 'p_b256_s59_prism'})
    with pytest.raises(ValueError, match='duplicate'):
        s.counts(env[1], [])
    (workspace / 'events/2.json').write_text('{')
    errors = []
    s.counts(env[1], errors)
    assert len(errors) == 1


def test_new_machine_identity_does_not_report_network_rename(env, monkeypatch):
    control = s.read(env[0] / 'control.json', [])
    token = 'machine-v1:' + 'a' * 64
    control['source']['host'] = [token, 'Darwin', 'arm64', 'arm']
    write(env[0] / 'control.json', control)
    monkeypatch.setattr(s.platform, 'node', lambda: 'new.router')
    monkeypatch.setattr(s, 'run', lambda command: (0, json.dumps({'host': token})))
    result = summary(env)
    assert result['host_identity']['scheme'] == 'machine-v1' and not result['warnings']
    monkeypatch.setattr(s, 'run', lambda command: (0, json.dumps({'host': 'machine-v1:' + 'b' * 64})))
    assert 'machine_identity_drift' in summary(env)['warnings']
