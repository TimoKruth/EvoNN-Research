"""Qualification recovery launcher: one native chunk per bounded worker.

Install as runtime/runner-v3.py beside the frozen runner.py. The additive
runner-amendment.json binds this launcher while readiness.json remains intact.
Engine source, fit settings and cumulative invocation clocks are unchanged.
"""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from evonn_compare.campaign import (
    CampaignSpec, adopted, identity, lease, match_config, preflight,
    read_manifest, run_campaign, slot_id,
)
from evonn_compare.cases import Case
from evonn_shared.engine_evidence import artifact_json
from evonn_shared.export_reader import read_export
from evonn_shared.runtime_clock import read as read_clock
from evonn_shared.runtime_journal import load_runtime_checkpoint

BASE = Path(__file__).resolve().parents[1]
PRODUCER = BASE.parents[1]
MODULES = dict(prism='prism.cli', topograph='topograph.cli', stratograph='stratograph.cli',
               primordia='evonn_primordia.cli', contenders='evonn_contenders.cli')


def read(path):
    return json.loads(path.read_text())


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()


def write(path, value, *, replace=False):
    if replace:
        temp = path.with_suffix('.tmp')
        temp.write_bytes(encoded(value))
        with temp.open('rb') as stream:
            os.fsync(stream.fileno())
        temp.replace(path)
    else:
        with path.open('xb') as stream:
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())


def status(state, **values):
    completed = len(list((BASE/'receipts').glob('*.json')))
    write(BASE/'status.json', dict(state=state, updated_at=stamp(), completed=completed,
          total=30, study_maximum=840, pid=os.getpid(), **values), replace=True)


def check_inputs():
    amendment = read(BASE/'runner-amendment.json')
    assert digest(Path(__file__)) == amendment['runner_sha256'], 'Launcher drift'
    assert digest(BASE/'readiness.json') == amendment['original_readiness_sha256'], 'Readiness drift'
    ready = read(BASE/'readiness.json')
    assert identity() == ready['identity'], 'Producer/environment/host drift'
    for relative, sha in ready['files'].items():
        assert digest(BASE/relative) == sha, relative
    for path in (BASE/'receipts').glob('*.json'):
        receipt = read(path)
        for name, sha in receipt['documents'].items():
            assert digest(Path(receipt['export'])/name) == sha, 'Completed export changed'


def paused():
    return (BASE/'PAUSE').exists() or (BASE/'STOP').exists()


def command_run(command, path, seconds, fd):
    # Remain in the supervisor-owned worker process group. Its lease survives
    # a parent death until the child exits, preventing duplicate dispatch.
    if seconds <= 0:
        raise RuntimeError('No command allowance remaining')
    # Preserve logs from interrupted commands; recovery gets a separate log.
    if path.exists():
        path = path.with_name(f'{path.stem}-resume-{time.time_ns()}{path.suffix}')
    with path.open('x') as stream:
        child = subprocess.Popen(command, cwd=PRODUCER, stdout=stream,
                                 stderr=subprocess.STDOUT, pass_fds=(fd,))
        child.wait(timeout=seconds)
    if child.returncode:
        raise RuntimeError(f'Exit {child.returncode}; see {path}')
    return path


def checkpoint(run):
    _, payload = load_runtime_checkpoint(run/'checkpoints')
    state = json.loads(payload)
    directory = run/'invocation_clock'
    starts = sorted(directory.glob('*_start.json'))
    assert starts, 'Missing invocation clock'
    for start in starts:
        a = read_clock(directory, start.name)
        b = read_clock(directory, start.name.replace('_start', '_end'))
        assert b['start'] == a['sha256'], 'Unclosed or mismatched invocation clock'
    assert len(starts) == len(list(directory.glob('*_end.json')))
    return state


def worker(index, system, outer_fd):
    check_inputs()
    row = read(BASE/'qualification-matrix.json')[index]
    campaign = BASE/'campaigns'/row['id']
    manifest = read_manifest(campaign)
    CampaignSpec.model_validate(manifest['spec'])
    case = Case(row['pack'], row['regime']['proposal_limit'], row['seed'])
    ident = row['id']+'-'+system
    deadline = time.monotonic()+1680
    if paused():
        return
    preflight(campaign)
    if system == 'contenders':
        # Whole bounded contender slot; incomplete Contenders are never restarted.
        status('training', active=ident, engine=system, budget=case.budget, seed=case.seed)
        command_run([sys.executable, '-m', 'evonn_compare.cli', 'campaign', 'run',
                     str(campaign), '--max-runs', '1'], BASE/'logs'/f'{ident}-contenders.log',
                    min(1580, deadline-time.monotonic()), outer_fd)
    else:
        with lease(campaign) as fd:
            run, reference = adopted(campaign, manifest, case, system)
            output = campaign/'runs'/slot_id(case, system)
            output.mkdir(parents=True, exist_ok=True)
            state = checkpoint(run) if run is not None else None
            if state is not None:
                match_config(read(run/'config.yaml'), manifest, case, system)
            completed = state['completed'] if state else 0
            while reference is None and completed < case.budget:
                if paused():
                    status('paused', active=ident, committed_fits=completed)
                    return
                # Never shorten a chunk's supervisory allowance to squeeze it
                # into a nearly expired worker. The engine retains its own
                # cumulative 1500-second budget across these invocations.
                if deadline-time.monotonic() < 1520:
                    status('between_chunks', active=ident, engine=system,
                           budget=case.budget, seed=case.seed, committed_fits=completed)
                    return
                # First qualify the existing clean boundary at 16 committed fits,
                # then continue in bounded chunks with the original total clock.
                target = min(completed+16, case.budget)
                before = state['attempts'] if state else []
                command = [sys.executable, '-m', MODULES[system], 'run', '--config',
                           str(BASE/'plan/engine-configs'/row['id']/(system+'.json')),
                           '--output', str(output), '--cache', str(BASE/'cache'),
                           '--stop-after', str(target)]
                if run is not None:
                    command += ['--resume', str(run)]
                status('training', active=ident, engine=system, budget=case.budget,
                       seed=case.seed, committed_fits=completed, next_boundary=target)
                command_run(command, BASE/'logs'/f'{ident}-to{target:03d}.log',
                            min(1520, deadline-time.monotonic()), fd)
                candidates = list(output.iterdir())
                assert len(candidates) == 1
                run = candidates[0]
                state = checkpoint(run)
                assert state['completed'] == target, 'Bounded fit target not completed'
                assert state['attempts'][:completed] == before, 'Prior committed work changed'
                assert len(state['attempts']) == target
                assert all(a['status'] == 'ok' for a in state['attempts']), 'Failed/invalid fit'
                write(BASE/'boundaries'/f'{ident}-to{target:03d}.json',
                      dict(at=stamp(), completed=target, prior_completed=completed,
                           attempts_sha256=hashlib.sha256(encoded(state['attempts'])).hexdigest(),
                           prior_attempts_unchanged=True, all_invocation_clocks_closed=True,
                           elapsed_accounted=state['elapsed'], run=str(run)))
                completed = target
                # Yield even at the final boundary: export adoption and replay
                # receive a fresh bounded worker without renewing fit time.
                status('between_chunks', active=ident, engine=system,
                       budget=case.budget, seed=case.seed, committed_fits=completed)
                return
            run, reference = adopted(campaign, manifest, case, system)
            assert reference is not None, 'No verified complete export'
        # With one second remaining this can only adopt; a 1520-second dispatch
        # reservation cannot fit. Keep the standard completion journal/report.
        run_campaign(campaign, session_timeout=1)
    run, reference = adopted(campaign, manifest, case, system)
    assert reference is not None
    bundle = read_export(run/'symbiosis')
    assert bundle.manifest.accounting.failed_evaluations == 0
    replay = None
    if system != 'contenders':
        status('replaying', active=ident, engine=system, budget=case.budget, seed=case.seed)
        log = BASE/'logs'/f'{ident}-replay.log'
        log = command_run([sys.executable, '-m', MODULES[system], 'replay', str(run)], log,
                    min(180, deadline-time.monotonic()), outer_fd)
        replay = read(log)
        assert replay['status'] == 'passed' and len(replay['checks']) == 4
    else:
        attempts = artifact_json(bundle, 'attempts.json')['attempts']
        from evonn_shared.active_catalog import get_benchmark, load_parity_pack
        for name in load_parity_pack(case.pack).benchmarks:
            kind = get_benchmark(name).task_kind.value
            needed = {'language_modeling': 'transformer_lm_tiny',
                      'regression': 'catboost', 'image_classification': 'cnn_small'}.get(kind)
            if 'digits' in name:
                needed = 'cnn_small'
            if 'banknote' in name:
                needed = 'catboost'
            assert needed is not None, (name, kind)
            assert any(a['benchmark_id'] == name and a['status'] == 'ok' and a['family'] == needed
                       for a in attempts), f'Required enhanced baseline missing: {name}/{needed}'
    write(BASE/'receipts'/(ident+'.json'), dict(at=stamp(), stage=row['stage'], system=system,
          budget=case.budget, seed=case.seed, export=str(run/'symbiosis'),
          accounting=bundle.manifest.accounting.model_dump(mode='json'), replay=replay,
          documents={name:digest(run/'symbiosis'/name) for name in ('manifest.json','summary.json','results.json')}))


def tick():
    with (BASE/'supervisor.lock').open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        if (BASE/'qualification-execution-complete.json').exists() or (BASE/'failure.json').exists():
            return
        if paused():
            status('paused')
            return
        try:
            check_inputs()
            for index, row in enumerate(read(BASE/'qualification-matrix.json')):
                for system in row['systems']:
                    ident = row['id']+'-'+system
                    if (BASE/'receipts'/(ident+'.json')).exists():
                        continue
                    log = BASE/'logs'/f'{ident}-worker-{time.time_ns()}.log'
                    with log.open('x') as stream:
                        child = subprocess.Popen([sys.executable, __file__, 'worker', str(index), system, str(lock.fileno())],
                            cwd=PRODUCER, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                            pass_fds=(lock.fileno(),))
                        try:
                            child.wait(timeout=1740)
                            if child.returncode:
                                raise RuntimeError(f'Qualification worker exit {child.returncode}; see {log}')
                        except BaseException:
                            try:
                                os.killpg(child.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            child.wait()
                            raise
                    if paused():
                        status('paused', last=ident)
                    elif (BASE/'receipts'/(ident+'.json')).exists():
                        status('between_runs', last=ident)
                    return
            write(BASE/'qualification-execution-complete.json', dict(at=stamp(), runs=30,
                  training_complete=True, qualification_accepted=False, next_stage_authorized=False,
                  blockers=['Profiling reconciliation and equivalence need review.',
                            'Chunked clean-pause evidence needs review; request-driven fit-boundary stop is not implemented.',
                            'Breadth baseline adequacy and causality qualification need review.',
                            'Policy-aware analysis and measured-compute execution remain gated.']))
            status('qualification_complete_awaiting_gate_review')
        except Exception as error:
            write(BASE/'failure.json', dict(at=stamp(), error=str(error), replacement_authorized=False))
            status('blocked', error=str(error))
            raise


if __name__ == '__main__':
    if sys.argv[1] == 'tick':
        tick()
    elif sys.argv[1] == 'worker':
        worker(int(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
    else:
        raise SystemExit('Expected tick or worker')
