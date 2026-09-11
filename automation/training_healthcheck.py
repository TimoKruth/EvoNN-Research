#!/usr/bin/env python3
"""Read-only hourly oversight of training and its minute guardian."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from training_guardian import active_processes, lock, read, stamp, write

PROBLEMS = {'blocked', 'stalled', 'repair_pending', 'repairing', 'retry_pending'}


def timestamp(value):
    return dt.datetime.fromisoformat(value).timestamp()


def scheduler(label):
    result = subprocess.run(['/bin/launchctl', 'print', f'gui/{os.getuid()}/{label}'],
                            text=True, capture_output=True, timeout=10)
    running = re.search(r'^\s*state = running\s*$', result.stdout, re.MULTILINE)
    exit_code = re.search(r'^\s*last exit code = (\d+)', result.stdout, re.MULTILINE)
    return dict(loaded=result.returncode == 0, running=bool(running),
                exit_code=int(exit_code[1]) if exit_code else None)


def assess(root, now, since, service, alive):
    """Use the guardian's current target, including any replacement producer."""
    control, status = read(root / 'control.json'), read(root / 'status.json')
    issues = []
    # Capture even failures repaired between hourly checks, without repeating old history.
    with (root / 'history.jsonl').open() as stream:
        for line in stream:
            event = json.loads(line)
            if since < timestamp(event['updated_at']) <= now and event['state'] in PROBLEMS:
                issues.append('Fehler seit letzter Kontrolle: ' + event['state'])
    if control['mode'] == 'complete':
        receipt = read(root / 'completion.json')
        expected = read(root / 'installation.json')['initial_probe']['total']
        verified = receipt['verified']
        if (receipt['target'] != control['target'] or verified['completed'] != expected
                or verified['total'] != expected or expected <= 0):
            issues.append('Abschlussnachweis passt nicht zum aktuellen Vergleich')
        return dict(state='complete', issues=sorted(set(issues)), completed=verified['completed'], total=expected)
    if not service['loaded']:
        issues.append('Minuten-Guardian ist nicht in launchd geladen')
    elif service['exit_code'] not in (None, 0) and not service['running']:
        issues.append(f"Minuten-Guardian endete mit Exit-Code {service['exit_code']}")
    age = now - timestamp(status['updated_at'])
    # A training or repair tick can validate for up to 30 minutes after its
    # bounded operation; final validation can contain two 30-minute probes.
    limit = 3900 if service['running'] else 300
    if age > limit:
        issues.append(f'Guardian-Status seit {int(age / 60)} Minuten unverändert')
    if control['mode'] == 'blocked' or status['state'] in PROBLEMS:
        issues.append('Reparaturstatus: ' + status['state'])
    if (root / 'PAUSE').exists():
        issues.append('Guardian ist durch PAUSE angehalten')
    if control['mode'] == 'observe':
        if alive and now - control.get('live_since', now) > 2400:
            issues.append('Trainingsfortschritt seit mehr als 40 Minuten unverändert')
        if not alive and not service['running'] and age > 180:
            issues.append('Kein Trainingsprozess und keine aktive Prüfung/Reparatur')
    return dict(state=status['state'], target=control['target'], issues=sorted(set(issues)),
                guardian_age_seconds=round(age), scheduler=service, training_processes=list(alive))


def notify(message):
    """Record delivery errors; macOS ultimately controls notification visibility."""
    result = subprocess.run(['/usr/bin/osascript', '-e',
                            'on run argv\ndisplay notification (item 1 of argv) with title "EvoNN Stundenkontrolle"\nend run',
                            message], capture_output=True, text=True, timeout=10)
    return dict(submitted=result.returncode == 0, error=result.stderr.strip())


def tick(config):
    root, output = Path(config['guardian_root']), Path(config['state_root'])
    with lock(output / 'check.lock'):
        now = time.time()
        previous = read(output / 'status.json') if (output / 'status.json').exists() else {}
        since = previous.get('checked_at_epoch', now - 3600)
        try:
            installation = read(root / 'installation.json')
            control = read(root / 'control.json')
            result = assess(root, now, since, scheduler(installation['label']),
                            active_processes(control['target']['base']))
        except Exception as error:
            result = dict(state='check_failed', issues=[f'Kontrolle fehlgeschlagen: {type(error).__name__}: {error}'])
        result.update(updated_at=stamp(), checked_at_epoch=now)
        signature = hashlib.sha256(json.dumps(result['issues']).encode()).hexdigest()
        last_alert = previous.get('last_alert_epoch', 0)
        last_signature = previous.get('last_alert_signature')
        if result['issues'] and (signature != last_signature or now - last_alert >= 3500):
            try:
                result['notification'] = notify('; '.join(result['issues'])[:700])
            except (OSError, subprocess.TimeoutExpired) as error:
                result['notification'] = dict(submitted=False, error=str(error))
            if result['notification']['submitted']:
                last_alert, last_signature = now, signature
        result.update(last_alert_epoch=last_alert, last_alert_signature=last_signature)
        write(output / 'status.json', result)
        with (output / 'history.jsonl').open('a') as stream:
            stream.write(json.dumps(result) + '\n')
        print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    args = parser.parse_args()
    try:
        tick(read(args.config))
    except BlockingIOError:
        pass


if __name__ == '__main__':
    main()
