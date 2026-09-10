"""Hourly oversight must detect failures without interrupting healthy work."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys

import pytest

AUTOMATION = Path(__file__).parents[1] / 'automation'
sys.path.insert(0, str(AUTOMATION))
try:
    SPEC = importlib.util.spec_from_file_location('healthcheck', AUTOMATION / 'training_healthcheck.py')
    h = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(h)
finally:
    sys.path.pop(0)


@pytest.fixture
def env(tmp_path):
    now = 1800000000
    target = {'producer': '/replacement', 'base': '/replacement/runs'}
    h.write(tmp_path / 'control.json', dict(mode='observe', target=target, live_since=now - 120))
    h.write(tmp_path / 'status.json', dict(state='observing', updated_at=iso(now - 30)))
    h.write(tmp_path / 'installation.json', dict(label='test', initial_probe={'total': 80}))
    (tmp_path / 'history.jsonl').write_text('')
    return tmp_path, now, dict(loaded=True, running=False, exit_code=0), {123: {}}


def iso(value):
    return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()


def check(env, **kwargs):
    root, now, service, alive = env
    return h.assess(root, now, now - 3600, kwargs.get('service', service), kwargs.get('alive', alive))


def test_idle_scheduler_is_normal_and_replacement_target_is_followed(env):
    result = check(env)
    assert result['issues'] == []
    assert result['target']['base'] == '/replacement/runs'


@pytest.mark.parametrize('service', [dict(loaded=False, running=False, exit_code=None),
                                    dict(loaded=True, running=False, exit_code=1)])
def test_missing_or_failed_guardian_is_reported(env, service):
    assert check(env, service=service)['issues']


def test_stale_and_dead_training_is_reported(env):
    root, now, _, _ = env
    h.write(root / 'status.json', dict(state='observing', updated_at=iso(now - 600)))
    assert len(check(env, alive={})['issues']) == 2


def test_bounded_training_and_followup_probe_are_not_mistaken_for_hang(env):
    root, now, service, _ = env
    control = h.read(root / 'control.json')
    control['mode'] = 'repair'  # Crash-safe guardian state during managed training.
    h.write(root / 'control.json', control)
    h.write(root / 'status.json', dict(state='training', updated_at=iso(now - 3600)))
    assert check(env, service={**service, 'running': True}, alive={})['issues'] == []


def test_repaired_failure_between_checks_is_reported_only_in_its_time_window(env):
    root, now, service, alive = env
    (root / 'history.jsonl').write_text(json.dumps(dict(state='repair_pending', updated_at=iso(now - 600))) + '\n')
    assert check(env)['issues']
    assert h.assess(root, now, now - 300, service, alive)['issues'] == []


def test_terminal_completion_needs_matching_receipt_but_no_live_scheduler(env):
    root, _, _, _ = env
    control = h.read(root / 'control.json')
    control['mode'] = 'complete'
    h.write(root / 'control.json', control)
    receipt = dict(target=control['target'], verified={'completed': 80, 'total': 80})
    h.write(root / 'completion.json', receipt)
    assert check(env, service={'loaded': False})['issues'] == []
    receipt['verified']['completed'] = 79
    h.write(root / 'completion.json', receipt)
    assert check(env)['issues']


def test_stuck_repair_reports_problem_even_while_scheduler_running(env):
    root, now, service, _ = env
    h.write(root / 'status.json', dict(state='repairing', updated_at=iso(now - 4000)))
    assert len(check(env, service={**service, 'running': True})['issues']) == 2


def test_tick_reports_broken_files_and_retries_failed_notification(env, monkeypatch):
    root, now, _, _ = env
    output = root / 'hourly'
    output.mkdir()
    (root / 'control.json').write_text('broken')
    monkeypatch.setattr(h.time, 'time', lambda: now)
    calls = []

    def notify(message):
        calls.append(message)
        return {'submitted': len(calls) > 1, 'error': 'test'}

    monkeypatch.setattr(h, 'notify', notify)
    config = dict(guardian_root=str(root), state_root=str(output))
    h.tick(config)
    h.tick(config)
    h.tick(config)
    assert len(calls) == 2
    assert h.read(output / 'status.json')['state'] == 'check_failed'
