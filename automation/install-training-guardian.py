#!/usr/bin/env python3
"""Install a per-comparison macOS guardian without touching the training producer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

from training_guardian import digest, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer', type=Path, required=True)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--install-scheduler', action='store_true')
    args = parser.parse_args()
    producer, base, root = [p.resolve() for p in (args.producer, args.base, args.state_root)]
    assert base.is_relative_to(producer)
    assert sys.platform == 'darwin', 'This installer uses launchd'
    codex = shutil.which('codex')
    assert codex, 'Codex CLI not installed'
    label = 'com.evonn.guardian.' + hashlib.sha256(str(base).encode()).hexdigest()[:12]
    plist_path = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
    print(json.dumps(dict(producer=str(producer), base=str(base), state_root=str(root),
                          label=label, plist=str(plist_path), interval_seconds=60), indent=2))
    if args.dry_run:
        return
    assert not (root / 'config.json').exists(), 'Existing guardian requires inspection; refusing overwrite'
    assert not plist_path.exists(), 'Existing scheduler requires inspection'
    runtime = root / 'runtime'
    runtime.mkdir(parents=True)
    for name in ('training_guardian.py', 'codex-maintenance-prompt.md'):
        shutil.copyfile(Path(__file__).parent / name, runtime / name)
    protocol = root / 'protocol.json'
    shutil.copyfile(producer / 'governance/tier-b-confirmation.json', protocol)
    target = dict(producer=str(producer), base=str(base))
    write(root / 'initial-target.json', target)
    result = subprocess.run([str(producer / '.venv/bin/python'), str(runtime / 'training_guardian.py'),
                             'probe', str(root / 'initial-target.json'), '--protocol', str(protocol)],
                            cwd=producer, text=True, capture_output=True, timeout=1800, check=True)
    checked = json.loads(result.stdout)
    config = dict(schema_version=1, state_root=str(root), protocol=str(protocol), protocol_sha256=digest(protocol),
                  **target, codex=codex, poll_seconds=60, repair_timeout=1800, same_failure_limit=3, max_repairs=12)
    write(root / 'config.json', config)
    write(root / 'control.json', dict(mode='observe', target=target, source=checked['source'],
                                     dataset_sha256=checked['datasets_sha256'],
                                     readiness_sha256=digest(base / 'readiness.json'),
                                     next_attempt_at=0, invocations=0, repairs=0))
    write(root / 'installation.json', dict(label=label, plist=str(plist_path), source_files={
        p.name: digest(p) for p in runtime.iterdir() if p.is_file()}, initial_probe=checked,
        authorization='User requested autonomous Codex repair/resume/restart until one complete comparison'))
    # A pinned runner remains available even if the editing checkout changes branch.
    plist = dict(Label=label, ProgramArguments=['/usr/bin/caffeinate', '-i', str(producer / '.venv/bin/python'),
                 str(runtime / 'training_guardian.py'), 'tick', str(root / 'config.json')],
                 WorkingDirectory=str(root), StartInterval=60, RunAtLoad=True, KeepAlive=False,
                 ProcessType='Standard', ExitTimeOut=60,
                 EnvironmentVariables={'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
                 StandardOutPath=str(root / 'launchd.log'), StandardErrorPath=str(root / 'launchd.err.log'))
    with (root / 'launch-agent.plist').open('wb') as stream:
        plistlib.dump(plist, stream)
    subprocess.run(['plutil', '-lint', str(root / 'launch-agent.plist')], check=True)
    if args.install_scheduler:
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / 'launch-agent.plist', plist_path)
        subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(plist_path)], check=True)
        subprocess.run(['launchctl', 'enable', f'gui/{os.getuid()}/{label}'], check=True)
        print('Guardian installed and active; existing training remains its current supervisor’s responsibility.')


if __name__ == '__main__':
    main()
