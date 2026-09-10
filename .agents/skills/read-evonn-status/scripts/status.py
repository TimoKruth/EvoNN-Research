#!/usr/bin/env python3
"""Bounded read-only EvoNN status snapshot, without ML or project imports."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time

SYSTEMS = ('prism', 'topograph', 'stratograph', 'primordia', 'contenders')
PROBLEMS = {'repair_pending', 'repairing', 'retry_pending', 'blocked', 'stalled'}
MAX_BYTES = 2_000_000


def read(path, errors, required=False):
    try:
        with path.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('file exceeds 2 MB status-query limit')
        return json.loads(data)
    except FileNotFoundError:
        if required:
            errors.append({'file': str(path), 'error': 'missing'})
    except (OSError, ValueError) as error:
        errors.append({'file': str(path), 'error': str(error)})
    return {}


def epoch(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def age(value, now):
    stamp = epoch(value)
    return round(now - stamp, 1) if stamp is not None else None


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, timeout=3)
    return result.returncode, result.stdout


def service(label):
    if not label or platform.system() != 'Darwin':
        return {'loaded': None, 'running': None}
    code, text = run(['/bin/launchctl', 'print', f'gui/{os.getuid()}/{label}'])
    last = re.search(r'^\s*last exit code = (\d+)', text, re.M)
    return {'loaded': code == 0, 'running': bool(re.search(r'^\s*state = running\s*$', text, re.M)),
            'last_exit_code': int(last[1]) if last else None}


def processes():
    code, text = run(['ps', '-axo', 'pid=,stat=,etime=,command='])
    if code:
        raise RuntimeError('Cannot read process table')
    rows = []
    for line in text.splitlines():
        fields = line.strip().split(None, 3)
        if len(fields) == 4 and fields[0].isdigit():
            rows.append(dict(pid=int(fields[0]), state=fields[1], elapsed=fields[2], command=fields[3]))
    return rows


def discover(project, errors):
    configs = sorted((project / '.artifacts').glob('*/config.json'))
    if len(configs) > 128:
        raise ValueError('Too many configs; select --guardian explicitly')
    guardians, hourly = [], []
    for path in configs:
        config = read(path, errors)
        if not isinstance(config, dict):
            continue
        if {'state_root', 'protocol', 'producer', 'base', 'poll_seconds'} <= config.keys():
            control = read(path.parent / 'control.json', errors, True)
            guardians.append({'guardian': str(path.parent), 'mode': control.get('mode')})
        elif {'guardian_root', 'state_root'} <= config.keys():
            hourly.append((Path(config['guardian_root']).resolve(), path.parent))
    unfinished = [item for item in guardians if item['mode'] != 'complete']
    if len(unfinished) == 1:
        return Path(unfinished[0]['guardian']), guardians, hourly
    if not unfinished and len(guardians) == 1:
        return Path(guardians[0]['guardian']), guardians, hourly
    return None, unfinished or guardians, hourly


def history(root, errors):
    path = root / 'history.jsonl'
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            start = max(0, stream.tell() - 262144)
            stream.seek(start)
            if start:
                stream.readline()
            lines = stream.read(262144).splitlines(keepends=True)
        # A concurrent append can leave the last line temporarily incomplete.
        return [json.loads(line) for line in lines if line.endswith(b'\n')]
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as error:
        errors.append({'file': str(path), 'error': str(error)})
        return []


def counts(base, errors):
    ready = read(base / 'readiness.json', errors, True)
    entries = ready.get('campaigns', [])
    if not entries or len(entries) > 128:
        raise ValueError('Missing or excessive campaign list')
    by_engine, by_budget = {}, {}
    total = completed = 0
    remaining, incomplete_rosters = [], []
    for entry in entries:
        workspace = Path(entry['workspace']).resolve()
        if not workspace.is_relative_to(base.resolve() / 'campaigns'):
            raise ValueError('Campaign workspace outside current target')
        manifest = read(workspace / 'campaign.json', errors, True)
        spec = manifest['spec']
        missing = sorted(set(SYSTEMS) - set(spec['systems']))
        if missing:
            incomplete_rosters.append({'campaign': entry['id'], 'missing_systems': missing})
        expected = {f"{spec['pack']}_b{budget}_s{seed}_{system}": (system, budget, seed)
                    for budget in spec['budgets'] for seed in spec['seeds'] for system in spec['systems']}
        paths = sorted((workspace / 'events').glob('*.json'))
        if len(paths) > 2048:
            raise ValueError('Journal exceeds per-campaign status-query limit')
        done = set()
        for path in paths:
            event = read(path, errors, True)
            if event.get('kind') == 'complete':
                slot = event.get('slot')
                if slot not in expected or slot in done:
                    raise ValueError('Unknown or duplicate journal completion')
                done.add(slot)
        for slot, (system, budget, seed) in expected.items():
            finished = slot in done
            for table, key in ((by_engine, system), (by_budget, str(budget))):
                row = table.setdefault(key, {'completed': 0, 'planned': 0})
                row['planned'] += 1
                row['completed'] += int(finished)
            total += 1
            completed += int(finished)
            if not finished and len(remaining) < 1:
                remaining.append(dict(system=system, budget=budget, seed=seed, campaign=entry['id']))
    return dict(completed=completed, planned=total, percent=round(100 * completed / total, 1) if total else None,
                by_engine=by_engine, by_budget=by_budget, next_pending=remaining[0] if remaining else None,
                incomplete_campaign_rosters=incomplete_rosters,
                missing_systems=[system for system in SYSTEMS if system not in by_engine],
                evidence='journal counts; exports not revalidated by this query')


def summarize(root, hourly, rows, now, errors):
    control = read(root / 'control.json', errors, True)
    status = read(root / 'status.json', errors, True)
    target = control['target']
    base = Path(target['base'])
    installation = read(root / 'installation.json', errors, True)
    scheduler = service(installation.get('label'))
    matching = [row for row in rows if row['pid'] != os.getpid() and
                ((str(base) in row['command'] and any(token in row['command'] for token in
                  ('supervisor.py', 'evonn-compare', '.cli run', 'campaign_worker')))
                 or (str(root) in row['command'] and 'training_guardian.py' in row['command']))]
    live = [row for row in matching if not row['state'].startswith(('T', 'Z'))]
    engines = []
    for row in live:
        match = re.search(r'-m (prism|topograph|stratograph|primordia|evonn_contenders)\.cli run\b', row['command'])
        if match:
            item = dict(system=match[1].replace('evonn_', ''), pid=row['pid'], elapsed=row['elapsed'])
            for option in ('budget', 'seed'):
                value = re.search(r'--' + option + r' (\d+)\b', row['command'])
                item[option] = int(value[1]) if value else None
            engines.append(item)
    progress = counts(base, errors)
    warnings = []
    frozen_host = control.get('source', {}).get('host', [None])[0]
    host = dict(current=platform.node(), frozen=frozen_host)
    host['matches'] = host['current'] == frozen_host if frozen_host else None
    state = status.get('state', 'unknown')
    paused = (root / 'PAUSE').exists()
    if paused:
        state = 'paused'
    elif control.get('mode') == 'complete':
        state = 'complete'
    elif control.get('mode') == 'blocked':
        state = 'blocked'
    elif engines:
        state = 'training'
    elif any(' probe ' in row['command'] for row in live):
        state = 'validating'
    elif state in ('progress', 'resuming_by_user', 'repaired') and scheduler['loaded']:
        state = 'between_runs'
    if host['matches'] is False and state != 'complete':
        warnings.append('hostname_drift')
    if state in PROBLEMS:
        warnings.append('guardian_' + state)
    fresh = age(status.get('updated_at'), now)
    if state not in ('complete', 'paused', 'blocked'):
        if scheduler['loaded'] is False:
            warnings.append('guardian_scheduler_missing')
        if fresh is None or fresh > (3900 if scheduler['running'] else 300):
            warnings.append('guardian_status_stale_or_missing')
        if scheduler.get('last_exit_code') not in (None, 0) and not scheduler['running']:
            warnings.append('guardian_last_exit_failed')
        if not live and not scheduler['running'] and fresh is not None and fresh > 180:
            warnings.append('no_live_training_or_guardian')
    if progress['missing_systems'] or progress['incomplete_campaign_rosters']:
        warnings.append('comparison_roster_incomplete')
    receipt = read(root / 'completion.json', errors)
    verified = receipt.get('verified', {})
    receipt_matches = bool(receipt and receipt.get('target') == target and
                           verified.get('completed') == verified.get('total') == progress['planned'] == progress['completed'])
    if state == 'complete' and not receipt_matches:
        warnings.append('completion_receipt_missing_or_inconsistent')
    recent = history(root, errors)
    problems = [dict(updated_at=e.get('updated_at'), state=e['state'], error=str(e.get('error', ''))[-600:])
                for e in recent if e.get('state') in PROBLEMS][-3:]
    latest_progress = next((e.get('updated_at') for e in reversed(recent)
                            if e.get('state') in ('progress', 'complete', 'training')), None)
    hourly_status = []
    for guardian, directory in hourly:
        if guardian != root:
            continue
        data = read(directory / 'status.json', errors)
        meta = read(directory / 'installation.json', errors)
        hourly_status.append(dict(path=str(directory), scheduler=service(meta.get('label')),
                                  checked_at=data.get('updated_at'), age_seconds=age(data.get('updated_at'), now),
                                  issues_at_that_check=data.get('issues', [])))
    return dict(guardian=str(root), target=target, state=state, paused=paused, progress=progress,
                active_engines=engines, live_processes=[{k: row[k] for k in ('pid', 'state', 'elapsed')} for row in live],
                guardian_status=dict(state=status.get('state'), updated_at=status.get('updated_at'), age_seconds=fresh,
                                     mode=control.get('mode'), scheduler=scheduler, repair_attempts=control.get('repairs', 0)),
                current_error=str(status.get('error', ''))[-800:] if status.get('state') in PROBLEMS else None,
                hostname=host, warnings=warnings, historical_errors=problems, latest_training_progress_at=latest_progress,
                hourly=hourly_status, completion=dict(receipt_matches=receipt_matches, completed_at=receipt.get('completed_at'),
                                                     scientific_evaluation='not assessed by status query'))


def main():
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--guardian', type=Path)
    args = parser.parse_args()
    now = time.time()
    errors = []
    result = {'queried_at': dt.datetime.now().astimezone().isoformat(timespec='seconds')}
    try:
        selected, candidates, hourly = discover(args.project.expanduser().resolve(), errors)
        root = args.guardian.expanduser().resolve() if args.guardian else selected
        if root:
            result.update(summarize(root, hourly, processes(), now, errors))
        else:
            result.update(error='ambiguous_guardians' if candidates else 'no_guardian_found', candidates=candidates)
    except (OSError, ValueError, TypeError, KeyError, IndexError, RuntimeError, subprocess.TimeoutExpired) as error:
        result.update(error='status_query_incomplete', detail=str(error))
    result['read_errors'] = errors
    if errors:
        result.setdefault('warnings', []).append('incomplete_snapshot_read_errors')
    result['query_elapsed_ms'] = round((time.perf_counter() - started) * 1000, 1)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
