"""Real process, persistence and portable evidence acceptance for v2."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import pytest
from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
from evonn_shared.export_reader import read_export
from evonn_shared.hierarchy_diagnostics import research_diagnostics


def invoke(*args):
    return subprocess.run([sys.executable, '-m', 'stratograph.cli', *map(str, args)],
                          capture_output=True, text=True, timeout=240, env=os.environ.copy())


@pytest.mark.parametrize('evaluator,backend', [('proxy', 'numpy_fallback'), ('trainable', 'mlx_native')])
def test_v2_real_resume_export_and_replay(tmp_path, evaluator, backend, monkeypatch):
    if backend == 'mlx_native' and (platform.system() != 'Darwin' or platform.machine() != 'arm64'):
        backend = 'numpy_fallback'
    policy = dict(version=2, evaluator=evaluator, screen_epochs=1, normalization='train_standard', evolve_representation=False)
    budget = 128 if evaluator == 'proxy' else 32
    first = invoke('run', '--pack', 'tier1_core_smoke', '--budget', budget, '--epochs', 2,
                   '--population-size', 2, '--timeout', 220, '--fit-timeout', 20,
                   '--backend', backend, '--research', json.dumps(policy),
                   '--output', tmp_path/'runs', '--cache', tmp_path/'cache', '--stop-after', 17)
    assert first.returncode == 0, first.stderr
    run = Path(first.stdout.strip().splitlines()[-1])
    drift = invoke('run', '--resume', run, '--research', json.dumps({**policy, 'inheritance': 'fresh'}))
    assert drift.returncode != 0 and 'differs from saved run' in drift.stderr
    crashed = invoke('run', '--resume', run, '--crash-at', 'transaction', '--crash-step', 18)
    assert crashed.returncode == -9, crashed.stderr
    resumed = invoke('run', '--resume', run)
    assert resumed.returncode == 0, resumed.stderr
    bundle = read_export(run/'symbiosis')
    validate_engine_bundle(bundle, verify_cache=True)
    assert bundle.results.coverage.ok == budget
    attempts = artifact_json(bundle, 'attempts.json')['attempts']
    assert all(row['inherited_epoch_savings'] == 0 for row in attempts)
    assert all(row['allocated_epochs'] == (2 if row['research_evaluation']['lane'].startswith('revisit_') else 1) for row in attempts)
    if evaluator == 'proxy':
        assert any(row['allocated_epochs'] == 2 for row in attempts)
        assert any(row['research_evaluation']['lane'] == 'revisit_random' for row in attempts)
    assert all(row['genome']['schema_version'] == 2 for row in attempts)
    if evaluator == 'trainable':
        assert any(row['hierarchy_weights_changed'] for row in attempts)
    assert artifact_json(bundle, 'research_diagnostics.json') == research_diagnostics(attempts)
    replay = invoke('replay', run)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)['status'] == 'passed'

    from copy import deepcopy
    from evonn_shared import engine_evidence
    original = engine_evidence.artifact_json
    diagnostics = artifact_json(bundle, 'research_diagnostics.json')
    tampered = deepcopy(diagnostics)
    panel = next(iter(tampered['benchmarks'].values()))
    panel['fits_charged'] += 1
    with monkeypatch.context() as patch:
        patch.setattr(engine_evidence, 'artifact_json', lambda bundle, name: tampered if name == 'research_diagnostics.json' else original(bundle, name))
        with pytest.raises(ValueError, match='diagnostics'):
            validate_engine_bundle(bundle, verify_cache=True)
