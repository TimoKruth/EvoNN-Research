"""Recovery must preserve evidence and never dispatch overlapping campaigns."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

SPEC = importlib.util.spec_from_file_location('guardian', Path(__file__).parents[1] / 'automation/training_guardian.py')
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)


@pytest.fixture
def env(tmp_path, monkeypatch):
    target = {'producer': str(tmp_path / 'producer'), 'base': str(tmp_path / 'base')}
    Path(target['base']).mkdir()
    g.write(Path(target['base']) / 'readiness.json', {'original': True})
    state = dict(mode='observe', target=target, source={'commit': 'original'}, dataset_sha256='data',
                 readiness_sha256=g.digest(Path(target['base']) / 'readiness.json'), next_attempt_at=0)
    g.write(tmp_path / 'control.json', state)
    config = dict(state_root=str(tmp_path), same_failure_limit=3, max_repairs=12)
    monkeypatch.setattr(g, 'validate_config', lambda c: None)
    monkeypatch.setattr(g, 'notify', lambda s: None)
    monkeypatch.setattr(g, 'active_processes', lambda b: {})
    checked = dict(completed=2, total=48, source=state['source'], datasets_sha256='data', next_workspace='/frozen/campaign')
    monkeypatch.setattr(g, 'call_probe', lambda *a, **k: checked.copy())
    return config, state, checked


def test_live_training_is_observed_without_probe_or_model(env, monkeypatch, tmp_path):
    config, _, _ = env
    monkeypatch.setattr(g, 'active_processes', lambda b: {123: {'born': 'now', 'command': 'verified'}})
    monkeypatch.setattr(g, 'call_probe', lambda *a, **k: pytest.fail('Live training must not be inspected expensively'))
    monkeypatch.setattr(g, 'repair', lambda *a: pytest.fail('No model on healthy training'))
    g.tick(config)
    assert g.read(tmp_path / 'status.json')['state'] == 'observing'


def test_crash_triggers_repair_on_next_tick(env, monkeypatch, tmp_path):
    config, _, _ = env
    g.tick(config)
    assert g.read(tmp_path / 'control.json')['mode'] == 'repair'
    calls = []
    monkeypatch.setattr(g, 'repair', lambda *args: calls.append(args[-1]))
    g.tick(config)
    assert len(calls) == 1 and 'supervisor stopped' in calls[0]


def test_managed_resume_then_complete_requires_final_validation(env, monkeypatch, tmp_path):
    config, state, checked = env
    state['mode'] = 'managed'
    g.write(tmp_path / 'control.json', state)
    checks = []

    def probe(*args, **kwargs):
        checks.append(kwargs.get('final', False))
        return checked.copy()

    def dispatch(command, **kwargs):
        assert command[-4:] == ['--session-timeout', '1800', '--max-runs', '1']
        checked['completed'] = 48
        json.dump({'status': 'complete', 'new_runs': 1}, kwargs['stdout'])
        return 0

    monkeypatch.setattr(g, 'call_probe', probe)
    monkeypatch.setattr(g, 'bounded', dispatch)
    g.tick(config)
    assert g.read(tmp_path / 'control.json')['mode'] == 'managed'
    assert not (tmp_path / 'completion.json').exists()
    g.tick(config)
    assert checks[-1] is True
    assert g.read(tmp_path / 'control.json')['mode'] == 'complete'
    assert (tmp_path / 'completion.json').exists()


def test_incomplete_validation_never_claims_completion(env, monkeypatch, tmp_path):
    config, _, checked = env
    checked['completed'] = 48

    def probe(*args, **kwargs):
        if kwargs.get('final'):
            raise ValueError('corrupt export')
        return checked

    monkeypatch.setattr(g, 'call_probe', probe)
    g.tick(config)
    assert not (tmp_path / 'completion.json').exists()
    assert g.read(tmp_path / 'control.json')['mode'] == 'repair'


def test_timeout_or_failure_goes_to_repair_without_repeating_dispatch(env, monkeypatch, tmp_path):
    config, state, _ = env
    state['mode'] = 'managed'
    g.write(tmp_path / 'control.json', state)
    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired('campaign', 1900)

    monkeypatch.setattr(g, 'bounded', fail)
    g.tick(config)
    assert len(calls) == 1
    assert g.read(tmp_path / 'control.json')['mode'] == 'repair'


@pytest.mark.parametrize('mode', ['complete', 'blocked'])
def test_terminal_states_do_no_work(env, monkeypatch, tmp_path, mode):
    config, state, _ = env
    state['mode'] = mode
    g.write(tmp_path / 'control.json', state)
    monkeypatch.setattr(g, 'active_processes', lambda b: pytest.fail('terminal state'))
    g.tick(config)


def test_pause_and_backoff_do_not_launch_model(env, monkeypatch, tmp_path):
    config, state, _ = env
    state.update(mode='repair', next_attempt_at=g.time.time() + 3600)
    g.write(tmp_path / 'control.json', state)
    monkeypatch.setattr(g, 'repair', lambda *a: pytest.fail('backoff'))
    g.tick(config)
    (tmp_path / 'PAUSE').touch()
    monkeypatch.setattr(g, 'active_processes', lambda b: pytest.fail('pause'))
    g.tick(config)


def test_repeated_failure_circuit_breaker(env, tmp_path):
    config, state, _ = env
    error = 'same error'
    fingerprint = g.hashlib.sha256(error.encode()).hexdigest()
    state['failure_counts'] = {fingerprint: 3}
    g.repair(config, state, tmp_path, None, error)
    assert g.read(tmp_path / 'control.json')['mode'] == 'blocked'
    assert not (tmp_path / 'repairs').exists()


def test_decision_cannot_redirect_resume_or_escape_clone(tmp_path):
    target = {'producer': '/original', 'base': '/original/runs'}
    clone = tmp_path / 'clone'
    assert g.check_decision(dict(action='resume', **target), target, clone) == target
    with pytest.raises(AssertionError):
        g.check_decision(dict(action='resume', producer='/other', base='/other/runs'), target, clone)
    with pytest.raises(AssertionError):
        g.check_decision(dict(action='replace', producer=str(clone), base='/outside'), target, clone)
    clone.mkdir()
    (clone / 'escape').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(AssertionError):
        g.check_decision(dict(action='replace', producer=str(clone), base=str(clone / 'escape')), target, clone)


def test_changed_readiness_is_rejected_before_dispatch(env, monkeypatch, tmp_path):
    config, state, _ = env
    state['mode'] = 'managed'
    g.write(tmp_path / 'control.json', state)
    g.write(Path(state['target']['base']) / 'readiness.json', {'tampered': True})
    monkeypatch.setattr(g, 'bounded', lambda *a, **k: pytest.fail('Must not dispatch'))
    g.tick(config)
    assert g.read(tmp_path / 'control.json')['mode'] == 'repair'


def test_lock_survives_inherited_child(tmp_path):
    lock_path = tmp_path / 'lock'
    with g.lock(lock_path) as fd:
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], pass_fds=(fd,))
    try:
        with pytest.raises(BlockingIOError):
            with g.lock(lock_path):
                pass
    finally:
        child.terminate()
        child.wait(timeout=5)
    with g.lock(lock_path):
        pass


def test_bounded_timeout_terminates_real_child(tmp_path):
    with (tmp_path / 'out').open('w') as out:
        with pytest.raises(subprocess.TimeoutExpired):
            g.bounded([sys.executable, '-c', 'import time; time.sleep(30)'],
                      cwd=tmp_path, stdout=out, stderr=out, timeout=0.1)


def test_stall_cleanup_rechecks_pid_birth_before_signalling(monkeypatch):
    original = {100: {'ppid': 1, 'born': 'old', 'command': '/run/supervisor.py'},
                101: {'ppid': 100, 'born': 'old', 'command': 'worker'}}
    recycled = {100: {'ppid': 1, 'born': 'new', 'command': 'unrelated'}, 101: original[101]}
    tables = iter([original, recycled, recycled])
    active = iter([{100: original[100]}, {}])
    monkeypatch.setattr(g, 'process_table', lambda: next(tables))
    monkeypatch.setattr(g, 'active_processes', lambda b: next(active))
    monkeypatch.setattr(g.time, 'sleep', lambda s: None)
    killed = []
    monkeypatch.setattr(os, 'kill', lambda pid, sig: killed.append((pid, sig)))
    g.stop_stalled('/run')
    assert killed == [(101, signal.SIGINT), (101, signal.SIGKILL)]


def test_repair_launches_cli_and_accepts_only_verified_resume(env, monkeypatch, tmp_path):
    config, state, _ = env
    producer = Path(state['target']['producer'])
    producer.mkdir()
    subprocess.run(['git', 'init', '-q', str(producer)], check=True)
    (producer / 'README.md').write_text('fixture')
    subprocess.run(['git', '-C', str(producer), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(producer), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                    '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture'], check=True)
    fake = tmp_path / 'codex-fixture'
    fake.write_text('#!' + sys.executable + '\n' + '''
import sys,json,pathlib
args=sys.argv
assert args[1:4]==['--ask-for-approval','never','exec']
assert args[args.index('--sandbox')+1]=='workspace-write'
assert '--dangerously-bypass-approvals-and-sandbox' not in args
prompt=sys.stdin.read()
incident=json.loads(prompt.split('Incident:\\n',1)[1])
result=dict(action='resume',**incident['target'],summary='Transient fixture repaired',tests='fixture')
pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(result))
''')
    fake.chmod(0o755)
    config.update(codex=str(fake), protocol=str(tmp_path / 'protocol.json'), repair_timeout=10)
    state.update(mode='repair', last_error='fixture failure')
    g.repair(config, state, tmp_path, None, state['last_error'])
    result = g.read(tmp_path / 'control.json')
    assert result['mode'] == 'managed'
    assert result['target'] == state['target']
    incidents = list((tmp_path / 'repairs').iterdir())
    assert len(incidents) == 1
    assert g.read(incidents[0] / 'decision.json')['action'] == 'resume'
    assert (incidents[0] / 'producer/README.md').read_text() == 'fixture'


def test_stalled_training_enters_repair_after_verified_cleanup(env, monkeypatch, tmp_path):
    config, state, _ = env
    alive = {100: {'born': 'old', 'command': 'supervisor'}}
    state.update(live_token=json.dumps(alive, sort_keys=True), live_since=g.time.time() - 2200)
    g.write(tmp_path / 'control.json', state)
    monkeypatch.setattr(g, 'active_processes', lambda b: alive)
    stopped = []
    monkeypatch.setattr(g, 'stop_stalled', lambda b: stopped.append(b))
    g.tick(config)
    assert stopped == [state['target']['base']]
    assert g.read(tmp_path / 'control.json')['mode'] == 'repair'
