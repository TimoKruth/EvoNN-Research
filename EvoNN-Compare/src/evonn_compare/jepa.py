"""Plan, execute and report the bounded full-roster JEPA feasibility pilot.

Uses package-owned workers through files, never imports engines. Receipts are
exploratory validation evidence, not canonical L3/L4 or protected-test evidence.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.metadata
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from evonn_shared.jepa_experiment import PilotSpec, SYSTEMS, MODULES, digest, file_digest, write_json
from evonn_shared.runtime_host import host_fields


ROOT = Path(__file__).resolve().parents[3]


def producer():
    paths = sorted(path for package in ROOT.glob('EvoNN-*') for path in (package/'src').rglob('*.py'))
    paths += [ROOT/'uv.lock']
    return dict(source_sha256=digest({str(path.relative_to(ROOT)): file_digest(path) for path in paths}),
                host=host_fields(), python=sys.version, dependencies={name: importlib.metadata.version(name)
                    for name in ('numpy', 'scipy', 'scikit-learn', 'pydantic')},
                mlx_version=importlib.metadata.version('mlx') if sys.platform == 'darwin' else None)


def cases(spec):
    for benchmark, seed, fraction, arm, system in itertools.product(
            spec.benchmarks, spec.seeds, spec.label_fractions, spec.arms, SYSTEMS):
        for candidate in range(1 if system == 'contenders' else spec.candidates):
            request = dict(spec=spec.model_dump(mode='json'), benchmark=benchmark, seed=seed,
                           label_fraction=fraction, arm=arm, system=system, candidate=candidate)
            if arm in ('distillation', 'jepa_transfer') and system != 'contenders':
                source = {**request, 'arm': 'supervised_long', 'system': spec.transfer_teacher, 'candidate': 0}
                request['teacher_case_id'] = digest(source)[:24]
            yield dict(id=digest(request)[:24], request=request)


def plan(workspace, spec):
    workspace = Path(workspace).absolute()
    workspace.mkdir(parents=True, exist_ok=False)
    matrix = list(cases(spec))
    manifest = dict(version=1, spec=spec.model_dump(mode='json'), producer=producer(), cases=matrix,
                    evidence_scope='exploratory_validation_only_fixed_architectures',
                    prior_cost='reported_prior for frozen teacher arms; fresh initialization otherwise',
                    neural_fits=sum(c['request']['system'] != 'contenders' for c in matrix),
                    contender_fits=2*sum(c['request']['system'] == 'contenders' for c in matrix))
    manifest['manifest_sha256'] = digest(manifest)
    write_json(workspace/'manifest.json', manifest)
    (workspace/'cases').mkdir()
    return manifest


def read_manifest(workspace):
    manifest = json.loads((workspace/'manifest.json').read_text())
    body = {k: v for k, v in manifest.items() if k != 'manifest_sha256'}
    if digest(body) != manifest['manifest_sha256']:
        raise ValueError('pilot manifest digest mismatch')
    spec = PilotSpec.model_validate(manifest['spec'])
    if manifest['cases'] != list(cases(spec)):
        raise ValueError('pilot matrix is incomplete or altered')
    return manifest


def checked_result(directory, case):
    receipt = json.loads((directory/'receipt.json').read_text())
    if receipt['status'] != 'ok':
        return receipt
    if file_digest(directory/'result.json') != receipt['result_sha256']:
        raise ValueError('pilot result digest mismatch')
    result = json.loads((directory/'result.json').read_text())
    if result['request_sha256'] != digest(case['request']) or result['status'] != 'ok':
        raise ValueError('pilot result/request mismatch')
    if case['request']['system'] != 'contenders':
        if (not result['replay_passed'] or not result['recompiled_replay_passed']
                or file_digest(directory/'result.npz') != result['weights_sha256']):
            raise ValueError('pilot weight integrity/replay failure')
    if 'teacher_embeddings_sha256' in result:
        if file_digest(directory/'result.teacher.npz') != result['teacher_embeddings_sha256']:
            raise ValueError('teacher embedding artifact digest mismatch')
    if 'teacher_case_id' in case['request']:
        source_id = case['request']['teacher_case_id']
        if (result['transfer']['source_case'] != source_id or
                file_digest(directory.parent/source_id/'result.teacher.npz') !=
                result['transfer']['teacher_embeddings_sha256']):
            raise ValueError('transfer teacher binding mismatch')
    return {**receipt, 'result': result}


def report(workspace):
    workspace = Path(workspace).absolute()
    manifest = read_manifest(workspace)
    rows, paired = [], []
    for case in manifest['cases']:
        directory = workspace/'cases'/case['id']
        request = case['request']
        row = {key: request[key] for key in ('system', 'benchmark', 'seed', 'label_fraction', 'arm', 'candidate')}
        row['id'] = case['id']
        if (directory/'receipt.json').exists():
            try:
                row.update(checked_result(directory, case))
            except (ValueError, KeyError, OSError) as exc:
                row.update(status='invalid', error=str(exc))
        else:
            row['status'] = 'pending'
        rows.append(row)
    controls = {(r['system'], r['benchmark'], r['seed'], r['label_fraction'], r['candidate']): r
                for r in rows if r['arm'] == 'supervised_long' and r['status'] == 'ok'}
    for row in rows:
        key = tuple(row[k] for k in ('system', 'benchmark', 'seed', 'label_fraction', 'candidate'))
        if row['status'] != 'ok' or row['arm'] == 'supervised_long' or key not in controls:
            continue
        control = controls[key]
        if row['result']['data'] != control['result']['data']:
            raise ValueError('unmatched pilot data across arms')
        if row['system'] != 'contenders' and (
                row['result']['initial_weights_sha256'] != control['result']['initial_weights_sha256']
                or row['result']['genome'] != control['result']['genome']):
            raise ValueError('unmatched architecture or initialization across pilot arms')
        metric = row['result']['metrics']
        sign = 1 if metric['direction'] == 'maximize' else -1
        paired.append(dict(id=row['id'], control=control['id'], contrast='against_supervised_long',
                           quality_improvement=sign*(metric['validation']-control['result']['metrics']['validation']),
                           robustness_improvement=sign*(metric['missing_input_validation']-
                                                       control['result']['metrics']['missing_input_validation'])))
    distillation = {(r['system'], r['benchmark'], r['seed'], r['label_fraction'], r['candidate']): r
                    for r in rows if r['arm'] == 'distillation' and r['status'] == 'ok'}
    for row in rows:
        key = tuple(row[k] for k in ('system', 'benchmark', 'seed', 'label_fraction', 'candidate'))
        if row['arm'] != 'jepa_transfer' or row['status'] != 'ok' or key not in distillation:
            continue
        control = distillation[key]
        metrics = row['result']['metrics']
        sign = 1 if metrics['direction'] == 'maximize' else -1
        paired.append(dict(id=row['id'], control=control['id'], contrast='masked_against_full_input_transfer',
                           quality_improvement=sign*(metrics['validation']-control['result']['metrics']['validation']),
                           robustness_improvement=sign*(metrics['missing_input_validation']-
                                                       control['result']['metrics']['missing_input_validation'])))
    complete = all(row['status'] == 'ok' for row in rows)
    result = dict(status='complete' if complete else 'incomplete', manifest_sha256=manifest['manifest_sha256'],
                  completed=sum(r['status'] == 'ok' for r in rows), total=len(rows), rows=rows,
                  paired_contrasts=paired,
                  interpretation='Descriptive validation pilot; no significance, superiority, or compute-matched claim.')
    write_json(workspace/'report.json', result)
    lines = ['# JEPA feasibility pilot', '', result['interpretation'], '',
             f"Status: **{result['status']}**, {result['completed']}/{len(rows)} worker cases completed.", '',
             'All candidates are shown; no engine is excluded. Positive paired deltas favor the treatment.', '',
             '| System | Data | Seed | Labels | Arm | Candidate | State | Quality | Missing inputs | Rank | Seconds |',
             '|---|---|---:|---:|---|---:|---|---:|---:|---:|---:|']
    for row in rows:
        fitted = row.get('result', {})
        metrics = fitted.get('metrics', {})
        def number(value):
            return f'{value:.5g}' if isinstance(value, (float, int)) else '—'
        lines.append('| ' + ' | '.join(str(row[k]) for k in (
            'system', 'benchmark', 'seed', 'label_fraction', 'arm', 'candidate', 'status')) + ' | ' +
            ' | '.join(number(v) for v in (metrics.get('validation'), metrics.get('missing_input_validation'),
                                           metrics.get('effective_rank'), fitted.get('wall_seconds'))) + ' |')
    by_id = {r['id']: r for r in rows}
    lines += ['', '## Matched candidate contrasts', '',
              'Raw metric differences (accuracy fractions or MSE units); positive favors treatment.', '',
              '| System | Data | Seed | Labels | Candidate | Treatment | Control | Quality gain | Robustness gain |',
              '|---|---|---:|---:|---:|---|---|---:|---:|']
    for pair in paired:
        row, control = by_id[pair['id']], by_id[pair['control']]
        lines.append('| ' + ' | '.join(str(row[k]) for k in ('system', 'benchmark', 'seed', 'label_fraction',
                                                           'candidate', 'arm')) +
                     f" | {control['arm']} | {pair['quality_improvement']:.5g} | {pair['robustness_improvement']:.5g} |")
    (workspace/'report.md').write_text('\n'.join(lines)+'\n')
    return result


def run(workspace, *, max_cases=None, session_timeout=1800):
    workspace = Path(workspace).absolute()
    if max_cases is not None and max_cases < 1:
        raise ValueError('max-cases must be positive')
    if not 1 <= session_timeout <= 1800:
        raise ValueError('session timeout must lie in [1,1800]')
    manifest = read_manifest(workspace)
    if producer() != manifest['producer']:
        raise ValueError('producer changed; create a new pilot workspace and preserve this one')
    started, executed = time.monotonic(), 0
    with (workspace/'run.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for case in manifest['cases']:
            directory = workspace/'cases'/case['id']
            if (directory/'receipt.json').exists():
                receipt = checked_result(directory, case)
                if receipt['status'] != 'ok':
                    break  # Fail closed: never silently replace a charged or interrupted fit.
                continue
            if (max_cases is not None and executed >= max_cases) or time.monotonic()-started >= session_timeout:
                break
            directory.mkdir(exist_ok=False)
            write_json(directory/'request.json', case['request'])
            write_json(directory/'receipt.json', dict(status='running', charged_attempt=True,
                                                      declared_fit_timeout=manifest['spec']['fit_timeout']))
            timeout = min(manifest['spec']['fit_timeout'] + 30, session_timeout-(time.monotonic()-started))
            request = case['request']
            environment = {**os.environ, 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
            command = [sys.executable, '-m', MODULES[request['system']]+'.jepa_worker',
                       str(directory/'request.json'), str(directory/'result.json')]
            fit_started = time.monotonic()
            try:
                if 'teacher_case_id' in request:
                    source_case = next(c for c in manifest['cases'] if c['id'] == request['teacher_case_id'])
                    source_directory = workspace/'cases'/source_case['id']
                    if checked_result(source_directory, source_case)['status'] != 'ok':
                        raise ValueError('teacher execution is incomplete')
                    command += ['--teacher', str(source_directory/'result.teacher.npz')]
                with (directory/'worker.log').open('w') as log:
                    subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                   check=True, timeout=max(0.01, timeout))
                receipt = dict(status='ok', result_sha256=file_digest(directory/'result.json'), charged_attempt=True,
                               worker_seconds=time.monotonic()-fit_started)
                write_json(directory/'receipt.json', receipt)
                checked_result(directory, case)
            except (subprocess.SubprocessError, OSError, ValueError, KeyError) as exc:
                write_json(directory/'receipt.json', dict(status='failed', error=str(exc), charged_attempt=True,
                           actual_work='unknown if worker interrupted; declared cap retained',
                           declared_fit_timeout=manifest['spec']['fit_timeout'],
                           worker_seconds=time.monotonic()-fit_started))
                break
            executed += 1
        return report(workspace)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    planning = commands.add_parser('plan', help='freeze a full matrix without training')
    planning.add_argument('--spec', type=Path, required=True)
    planning.add_argument('--workspace', type=Path, required=True)
    execution = commands.add_parser('run', help='run/resume pending cases; stop on any failure')
    execution.add_argument('workspace', type=Path)
    execution.add_argument('--max-cases', type=int)
    execution.add_argument('--session-timeout', type=float, default=1800)
    reporting = commands.add_parser('report', help='verify saved receipts and rebuild descriptive reports')
    reporting.add_argument('workspace', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'plan':
            result = plan(args.workspace, PilotSpec.model_validate_json(args.spec.read_text()))
            print(json.dumps({key: result[key] for key in ('manifest_sha256', 'neural_fits', 'contender_fits')}))
            return 0
        result = run(args.workspace, max_cases=args.max_cases, session_timeout=args.session_timeout) if (
            args.command == 'run') else report(args.workspace)
        print(json.dumps({key: result[key] for key in ('status', 'completed', 'total')}))
        return int(any(row['status'] in {'failed', 'invalid', 'running'} for row in result['rows']))
    except (OSError, ValueError) as exc:
        parser.exit(2, f'JEPA pilot: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
