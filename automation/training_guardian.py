#!/usr/bin/env python3
"""Minute polling, bounded Codex repair and sequential frozen-campaign recovery."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def note(root, state, **values):
    value = dict(state=state, updated_at=stamp(), **values)
    write(root / 'status.json', value)
    with (root / 'history.jsonl').open('a') as stream:
        stream.write(json.dumps(value) + '\n')


def notify(message):
    if sys.platform == 'darwin':
        try:
            subprocess.run(['/usr/bin/osascript', '-e',
                            'on run argv\ndisplay notification (item 1 of argv) with title "EvoNN Training"\nend run',
                            message], capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass  # Durable status/logs do not depend on desktop notification permissions.


@contextmanager
def lock(path):
    with Path(path).open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield stream.fileno()


def bounded(command, *, cwd, stdout, stderr, timeout, fd=None, input_text=None):
    # Children inherit the lease: a crashed guardian cannot duplicate their work.
    process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr,
                               stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                               text=True, start_new_session=True,
                               pass_fds=() if fd is None else (fd,))
    try:
        process.communicate(input=input_text, timeout=timeout)
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        raise
    return process.returncode


def process_table():
    text = subprocess.check_output(['ps', '-axo', 'pid=,ppid=,lstart=,command='], text=True)
    result = {}
    for line in text.splitlines():
        fields = line.strip().split(None, 7)
        if len(fields) == 8:
            result[int(fields[0])] = dict(ppid=int(fields[1]), born=' '.join(fields[2:7]), command=fields[7])
    return result


def active_processes(base):
    return {pid: row for pid, row in process_table().items() if pid != os.getpid()
            and str(base) in row['command'] and any(token in row['command'] for token in
            ('supervisor.py', 'evonn-compare', 'campaign_worker', '.cli run'))}


def stop_stalled(base):
    """Only the verified dedicated campaign tree, with PID birth-time rechecks."""
    table = process_table()
    selected = set(active_processes(base))
    assert selected, 'No confirmed campaign processes'
    while True:
        extended = selected | {pid for pid, row in table.items() if row['ppid'] in selected}
        if extended == selected:
            break
        selected = extended
    selected.discard(os.getpid())
    for sig in (signal.SIGINT, signal.SIGKILL):
        now = process_table()
        for pid in selected:
            if pid in table and now.get(pid) == table[pid]:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
        if sig == signal.SIGINT:
            time.sleep(10)
    if active_processes(base):
        raise RuntimeError('Campaign processes remain; refusing duplicate dispatch')


def validate_config(config):
    assert config['schema_version'] == 1
    for field in ('state_root', 'protocol', 'producer', 'base', 'codex'):
        assert Path(config[field]).is_absolute(), field
    assert digest(config['protocol']) == config['protocol_sha256'], 'Frozen protocol changed'
    assert config['poll_seconds'] == 60 and 0 < config['repair_timeout'] <= 1800
    assert 1 <= config['same_failure_limit'] <= 5
    assert 1 <= config['max_repairs'] <= 12
    assert (Path(config['producer']) / '.venv/bin/python').is_file()
    assert Path(config['codex']).is_file()


def require_systems(protocol, spec):
    required = protocol.get('comparison_policy', {}).get('required_systems', [])
    assert set(required) <= set(spec['systems']), 'Required comparison engine omitted'


def probe(target, protocol_path, *, final=False):
    # Invoked with the target interpreter; no imports from the editing environment.
    from evonn_compare.campaign import CampaignSpec, adopted, events, preflight, read_manifest, slots, slot_id
    producer, base = Path(target['producer']), Path(target['base'])
    assert Path(sys.prefix) == producer / '.venv', 'Wrong interpreter'
    protocol, ready = read(protocol_path), read(base / 'readiness.json')
    assert ready['protocol_sha256'] == digest(protocol_path)
    assert len(ready['campaigns']) == len(protocol['campaigns'])
    completed, total, next_workspace, partial = 0, 0, None, []
    source, data = None, []
    for planned, entry in zip(protocol['campaigns'], ready['campaigns'], strict=True):
        assert entry['id'] == planned['id']
        workspace = Path(entry['workspace'])
        assert workspace == base / 'campaigns' / planned['id']
        assert digest(workspace / 'campaign.json') == entry['manifest_sha256']
        manifest = read_manifest(workspace)
        assert manifest['spec'] == CampaignSpec.model_validate(planned['spec']).model_dump()
        require_systems(protocol, manifest['spec'])
        preflight(workspace)
        assert manifest['identity']['data_files'][
            'EvoNN-Contenders/src/evonn_contenders/pools.yaml'] == protocol['baselines']['pool_sha256']
        if source is None:
            source = manifest['identity']
        assert manifest['identity'] == source, 'Mixed producers'
        # Cache provenance must stay byte-equivalent, including split identities.
        data.append(manifest['datasets'])
        history = events(workspace, manifest)
        done = {e['slot']: e['details'] for e in history if e['kind'] == 'complete'}
        completed += len(done)
        cases = slots(CampaignSpec.model_validate(manifest['spec']))
        total += len(cases)
        for case, system in cases:
            slot = slot_id(case, system)
            if slot in done:
                if final:
                    _, reference = adopted(workspace, manifest, case, system)
                    assert reference == done[slot], 'Completed evidence changed'
            else:
                next_workspace = next_workspace or str(workspace)
                if (workspace / 'runs' / slot).exists():
                    partial.append(dict(workspace=str(workspace), slot=slot, system=system))
    assert total == protocol['execution']['planned_runs']
    return dict(completed=completed, total=total, next_workspace=next_workspace,
                partial=partial, source=source, datasets_sha256=hashlib.sha256(
                    json.dumps(data, sort_keys=True).encode()).hexdigest())


def call_probe(target, config, root, fd, final=False):
    write(root / 'probe-target.json', target)
    command = [str(Path(target['producer']) / '.venv/bin/python'), str(HERE / 'training_guardian.py'),
               'probe', str(root / 'probe-target.json'), '--protocol', config['protocol']]
    if final:
        command += ['--final']
    with (root / 'probe.json').open('w') as out, (root / 'probe.err.log').open('w') as err:
        code = bounded(command, cwd=target['producer'], stdout=out, stderr=err, timeout=1800, fd=fd)
    if code:
        raise RuntimeError((root / 'probe.err.log').read_text()[-6000:])
    return read(root / 'probe.json')


def check_decision(decision, target, clone):
    candidate = {key: decision[key] for key in ('producer', 'base')}
    if decision['action'] == 'resume':
        assert candidate == target, 'Resume cannot switch provenance'
    elif decision['action'] == 'replace':
        assert Path(candidate['producer']).resolve() == clone.resolve()
        assert Path(candidate['base']).resolve().is_relative_to(clone.resolve())
    else:
        raise ValueError('Unknown repair decision')
    return candidate


def repair(config, state, root, fd, error):
    normalized = re.sub(r'invocation-\d+', 'invocation-N', error)
    fingerprint = hashlib.sha256(normalized.encode()).hexdigest()
    count = state.get('failure_counts', {}).get(fingerprint, 0) + 1
    state.setdefault('failure_counts', {})[fingerprint] = count
    state['repairs'] = state.get('repairs', 0) + 1
    state['next_attempt_at'] = time.time() + min(3600, 300 * 2 ** min(count - 1, 4))
    write(root / 'control.json', state)
    if count > config['same_failure_limit'] or state['repairs'] > config['max_repairs']:
        state['mode'] = 'blocked'
        write(root / 'control.json', state)
        note(root, 'blocked', error=error, reason='Repair circuit breaker', target=state['target'])
        notify('Reparatur wiederholt fehlgeschlagen. Training pausiert; Guardian-Status prüfen.')
        return
    incident = root / 'repairs' / (dt.datetime.now().strftime('%Y%m%dT%H%M%S') + f'-{state["repairs"]}')
    incident.mkdir(parents=True)
    target = state['target']
    clone = incident / 'producer'
    with (incident / 'clone.log').open('w') as output:
        subprocess.run(['git', 'clone', '--no-hardlinks', target['producer'], str(clone)],
                       stdout=output, stderr=output, check=True, timeout=120)
    details = dict(target=target, error=error, repair_clone=str(clone), protocol=config['protocol'],
                   original_dataset_sha256=state['dataset_sha256'], attempt=count)
    write(incident / 'incident.json', details)
    schema = dict(type='object', additionalProperties=False,
                  properties={key: {'type': 'string'} for key in ('action', 'producer', 'base', 'summary', 'tests')},
                  required=['action', 'producer', 'base', 'summary', 'tests'])
    schema['properties']['action']['enum'] = ['resume', 'replace', 'blocked']
    write(incident / 'schema.json', schema)
    prompt = (HERE / 'codex-maintenance-prompt.md').read_text() + '\nIncident:\n' + json.dumps(details, indent=2)
    (incident / 'prompt.md').write_text(prompt)
    command = [config['codex'], '--ask-for-approval', 'never', 'exec', '--sandbox', 'workspace-write',
               '--config', 'sandbox_workspace_write.network_access=true', '--ignore-user-config',
               '--ephemeral', '--color', 'never', '--json', '--cd', str(clone),
               '--add-dir', str(incident), '--add-dir', target['base'],
               '--output-schema', str(incident / 'schema.json'),
               '--output-last-message', str(incident / 'decision.json'), '-']
    note(root, 'repairing', error=error, incident=str(incident), target=target)
    notify('Trainingsabbruch erkannt. Codex untersucht und repariert den Lauf.')
    with (incident / 'codex.jsonl').open('w') as out, (incident / 'codex.err.log').open('w') as err:
        code = bounded(command, cwd=clone, stdout=out, stderr=err,
                       timeout=config['repair_timeout'], fd=fd, input_text=prompt)
    if code or not (incident / 'decision.json').is_file():
        note(root, 'retry_pending', error=f'Codex exited {code}', incident=str(incident),
             next_attempt_at=state['next_attempt_at'])
        return
    decision = read(incident / 'decision.json')
    if decision['action'] == 'blocked':
        note(root, 'retry_pending', error=decision['summary'], incident=str(incident),
             next_attempt_at=state['next_attempt_at'])
        notify('Codex-Reparatur benötigt weitere Klärung: ' + decision['summary'][:180])
        return
    candidate = check_decision(decision, target, clone)
    assert not active_processes(target['base']), 'Training still active'
    if decision['action'] == 'resume':
        assert digest(Path(candidate['base']) / 'readiness.json') == state['readiness_sha256']
    checked = call_probe(candidate, config, root, fd)
    assert checked['datasets_sha256'] == state['dataset_sha256'], 'Dataset changes forbidden'
    if decision['action'] == 'resume':
        assert checked['source'] == state['source'], 'Resume source/environment changed'
    if decision['action'] == 'replace':
        assert checked['completed'] == 0 and not checked['partial'], 'Replacement must start empty'
        for entry in read(Path(candidate['base']) / 'readiness.json')['campaigns']:
            assert not (Path(entry['workspace']) / 'events').exists(), 'Replacement was already dispatched'
        state.setdefault('superseded', []).append(dict(target=target, incident=str(incident), reason=decision['summary']))
    state.update(target=candidate, mode='managed', next_attempt_at=0, source=checked['source'],
                 readiness_sha256=digest(Path(candidate['base']) / 'readiness.json'))
    write(root / 'control.json', state)
    note(root, 'repaired', target=candidate, incident=str(incident), summary=decision['summary'])


def tick(config):
    validate_config(config)
    root = Path(config['state_root'])
    with lock(root / 'guardian.lock') as fd:
        state = read(root / 'control.json')
        if state['mode'] in ('complete', 'blocked') or (root / 'PAUSE').exists():
            return
        target = state['target']
        try:
            alive = active_processes(target['base'])
            if alive:
                status_path = Path(target['base']) / 'status.json'
                token = digest(status_path) if status_path.exists() else json.dumps(alive, sort_keys=True)
                if state.get('live_token') != token:
                    state.update(live_token=token, live_since=time.time())
                if time.time() - state['live_since'] > 2100:
                    note(root, 'stalled', target=target, processes=alive)
                    stop_stalled(target['base'])
                    raise RuntimeError('Bounded campaign process stalled for over 35 minutes; stopped verified tree for recovery')
                note(root, 'observing', target=target, processes=alive)
                write(root / 'control.json', state)
                return
            if time.time() < state.get('next_attempt_at', 0):
                return
            if state['mode'] == 'repair':
                repair(config, state, root, fd, state['last_error'])
                return
            assert digest(Path(target['base']) / 'readiness.json') == state['readiness_sha256']
            checked = call_probe(target, config, root, fd)
            assert checked['source'] == state['source'], 'Pinned source/environment changed'
            assert checked['datasets_sha256'] == state['dataset_sha256'], 'Pinned data changed'
            if checked['completed'] == checked['total']:
                verified = call_probe(target, config, root, fd, final=True)
                write(root / 'completion.json', dict(verified=verified, target=target, completed_at=stamp()))
                state['mode'] = 'complete'
                write(root / 'control.json', state)
                note(root, 'complete', completed=checked['completed'], total=checked['total'], target=target)
                notify(f"Vergleich vollständig abgeschlossen und Exporte geprüft: {checked['completed']}/{checked['total']} Runs.")
                return
            if state['mode'] == 'observe':
                raise RuntimeError('Original supervisor stopped before completion. Inspect its status, invocation logs and partial runs.')
            count = state.get('invocations', 0) + 1
            state.update(invocations=count, mode='repair', last_error='Guardian interrupted during a campaign invocation')
            write(root / 'control.json', state)
            note(root, 'training', target=target, completed=checked['completed'], total=checked['total'], invocation=count)
            command = [str(Path(target['producer']) / '.venv/bin/evonn-compare'), 'campaign', 'resume',
                       checked['next_workspace'], '--session-timeout', '1800', '--max-runs', '1']
            outpath = root / f'invocation-{count:04d}.json'
            with outpath.open('x') as out, (root / f'invocation-{count:04d}.err.log').open('x') as err:
                code = bounded(command, cwd=target['producer'], stdout=out, stderr=err, timeout=1900, fd=fd)
            if code:
                raise RuntimeError(f'Campaign exited {code}; inspect {root / f"invocation-{count:04d}.err.log"}')
            result = read(outpath)
            assert result['status'] in ('complete', 'paused') and result['new_runs'] <= 1
            after = call_probe(target, config, root, fd)
            assert after['completed'] > checked['completed'], 'No verified progress'
            state.update(mode='managed', next_attempt_at=0)
            write(root / 'control.json', state)
            note(root, 'progress', completed=after['completed'], total=after['total'], target=target)
        except Exception as error:
            state.update(mode='repair', last_error=f'{type(error).__name__}: {error}')
            write(root / 'control.json', state)
            note(root, 'repair_pending', error=state['last_error'], target=state['target'])


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['tick', 'validate', 'probe'])
    parser.add_argument('config', type=Path)
    parser.add_argument('--protocol', type=Path)
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    if args.action == 'probe':
        print(json.dumps(probe(read(args.config), args.protocol, final=args.final)))
    elif args.action == 'validate':
        validate_config(read(args.config))
        print('Guardian configuration: PASS')
    else:
        try:
            tick(read(args.config))
        except BlockingIOError:
            pass


if __name__ == '__main__':
    main()
