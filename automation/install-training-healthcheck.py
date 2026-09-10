#!/usr/bin/env python3
"""Install hourly oversight independently of the active training guardian."""
import argparse
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

from training_guardian import digest, read, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guardian-root', type=Path, required=True)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--install-scheduler', action='store_true')
    args = parser.parse_args()
    guardian, root = args.guardian_root.resolve(), args.state_root.resolve()
    assert sys.platform == 'darwin', 'This installer uses launchd'
    assert guardian != root and not root.exists(), 'Use a new independent state directory'
    config = read(guardian / 'config.json')
    read(guardian / 'installation.json')
    python = str(Path(config['producer']) / '.venv/bin/python')
    assert Path(python).is_file()
    label = 'com.evonn.hourly.' + hashlib.sha256(str(guardian).encode()).hexdigest()[:12]
    destination = Path.home() / 'Library/LaunchAgents' / (label + '.plist')
    assert not destination.exists(), 'Existing scheduler requires inspection'
    runtime = root / 'runtime'
    runtime.mkdir(parents=True)
    for name in ('training_healthcheck.py', 'training_guardian.py'):
        shutil.copyfile(Path(__file__).parent / name, runtime / name)
    write(root / 'config.json', dict(guardian_root=str(guardian), state_root=str(root)))
    plist = dict(Label=label, ProgramArguments=[python, str(runtime / 'training_healthcheck.py'),
                 str(root / 'config.json')], WorkingDirectory=str(root), StartInterval=3600,
                 RunAtLoad=True, KeepAlive=False, ProcessType='Background', ExitTimeOut=30,
                 EnvironmentVariables={'PATH': '/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin'},
                 StandardOutPath=str(root / 'launchd.log'), StandardErrorPath=str(root / 'launchd.err.log'))
    with (root / 'launch-agent.plist').open('wb') as stream:
        plistlib.dump(plist, stream)
    subprocess.run(['/usr/bin/plutil', '-lint', str(root / 'launch-agent.plist')], check=True)
    write(root / 'installation.json', dict(label=label, plist=str(destination), interval_seconds=3600,
          source_files={p.name: digest(p) for p in runtime.iterdir()},
          authorization='User requested hourly checks and notification on failures'))
    if args.install_scheduler:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / 'launch-agent.plist', destination)
        subprocess.run(['/bin/launchctl', 'bootstrap', f'gui/{os.getuid()}', str(destination)], check=True)
        subprocess.run(['/bin/launchctl', 'enable', f'gui/{os.getuid()}/{label}'], check=True)
    print(f'{label}: hourly checker prepared at {root}; scheduler installed={args.install_scheduler}')


if __name__ == '__main__':
    main()
