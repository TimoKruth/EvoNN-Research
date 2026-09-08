#!/usr/bin/env python3
"""Enforce registry citations and engine-advancement PR evidence in CI."""
import argparse
import json
from pathlib import Path
import re
import subprocess

from .decision_gate import validate_decision_block
from .registry import validate_registry


def engine_advancement(paths):
    return any(re.fullmatch(r'EvoNN-(Prism|Topograph|Stratograph|Primordia)/(src|configs)/.+',path) for path in paths)


def check(*, root, body, paths):
    registry=root/'evidence'
    cited='```evonn-evidence' in body or re.search(r'\bevidence/(runs/|index\.jsonl|evidence_report)',body)
    if registry.exists():
        validation=validate_registry(registry,require_artifacts=True)
        if validation['status']!='passed':
            raise ValueError('committed evidence registry invalid: '+'; '.join(validation['blockers']))
    if engine_advancement(paths) or cited:
        result=validate_decision_block(body,registry=registry)
        changed={match.group(1).lower() for path in paths if (match:=re.fullmatch(r'EvoNN-(Prism|Topograph|Stratograph|Primordia)/(src|configs)/.+',path))}
        if changed and set(result['target_engines'])!=changed:
            raise ValueError('analysis target engines differ from changed engine runtime paths')
        return result
    return dict(status='not_applicable',reason='no engine advancement or registry citation')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path.cwd())
    args=parser.parse_args(argv)
    try:
        event=json.loads(args.event.read_text())
        if 'pull_request' not in event:
            if (args.root/'evidence').exists():
                result=validate_registry(args.root/'evidence',require_artifacts=True)
                if result['status']!='passed':
                    raise ValueError('; '.join(result['blockers']))
            else:
                result={'status':'not_applicable','reason':'no committed registry'}
        else:
            base=event['pull_request']['base']['sha']
            head=event['pull_request']['head']['sha']
            if not all(isinstance(sha,str) and re.fullmatch(r'[a-f0-9]{40}',sha) for sha in (base,head)):
                raise ValueError('invalid GitHub revision identity')
            paths=subprocess.check_output(['git','diff','--name-only',base+'...'+head],cwd=args.root,text=True).splitlines()
            result=check(root=args.root,body=event['pull_request']['body'] or '',paths=paths)
            if result['status']=='passed':
                for declared,reviewed in ((result['before_revision'],base),(result['after_revision'],head)):
                    subprocess.run(['git','merge-base','--is-ancestor',declared,reviewed],cwd=args.root,check=True,capture_output=True)
                    changed=subprocess.check_output(['git','diff','--name-only',declared,reviewed],cwd=args.root,text=True).splitlines()
                    if any('/src/' in path or '/configs/' in path or path.startswith('shared-benchmarks/') or path.endswith(('pyproject.toml','uv.lock')) for path in changed):
                        raise ValueError('declared experiment revision differs from reviewed runtime; only non-runtime descendants allowed')
        print(json.dumps(result,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as error:
        parser.exit(1,f'PR evidence gate: {error}\n')


if __name__=='__main__':
    raise SystemExit(main())
