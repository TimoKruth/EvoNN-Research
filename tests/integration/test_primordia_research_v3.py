"""Real workers, inherited v3 weights, publication recovery and saved-winner replay."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

import pytest
from evonn_shared import engine_evidence
from evonn_shared.export_reader import read_export
from evonn_shared.runtime_journal import load_runtime_checkpoint


@pytest.mark.parametrize('architecture,optimization', [('expressive_v3', 'stable_v3'), ('portfolio_v4', 'steady_v3')])
def test_research_v3_export_resume_replay_and_integrity(tmp_path, monkeypatch, architecture, optimization):
    def invoke(*args, success=True):
        result = subprocess.run([sys.executable, '-m', 'evonn_primordia.cli', *map(str, args)],
                                cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=600)
        if success:
            assert result.returncode == 0, result.stdout + result.stderr
        return result

    config = dict(pack='tier_b_core_v2', budget=32, epochs=2, seed=42, population_size=4,
                  search_policy='breadth_v2', max_width=12, max_depth=3,
                  architecture_policy=architecture, optimization_policy=optimization, proposal_policy='progress_v3',
                  backend=os.environ.get('EVONN_TEST_BACKEND', 'numpy_fallback'), timeout=540, fit_timeout=60)
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config))
    result = invoke('run', '--config', path, '--output', tmp_path / 'prefix', '--cache', tmp_path / 'cache', '--stop-after', 20)
    prefix = Path(result.stdout.strip())
    baseline = tmp_path / 'baseline' / prefix.name
    recovered = tmp_path / 'recovered' / prefix.name
    shutil.copytree(prefix, baseline)
    shutil.copytree(prefix, recovered)
    invoke('run', '--resume', baseline)
    killed = invoke('run', '--resume', recovered, '--crash-at', 'transaction', '--crash-step', 22, success=False)
    assert killed.returncode == -signal.SIGKILL, killed.stderr
    invoke('run', '--resume', recovered)
    states = [json.loads(load_runtime_checkpoint(root / 'checkpoints')[1]) for root in (baseline, recovered)]
    assert states[0]['search'] == states[1]['search']
    assert states[0]['tip'] == states[1]['tip']
    attempts = states[1]['attempts']
    assert len(attempts) == 32 and all(a['status'] == 'ok' and a['charged'] == 1 for a in attempts)
    assert all(a['allocated_epochs'] == 2 for a in attempts)
    assert all(a['genome']['version'] == (2 if architecture == 'portfolio_v4' and a['benchmark_id'] in
               {'banknote_classification', 'diabetes_regression'} else 3) for a in attempts)
    assert {'elite', 'progress', 'novelty', 'quality', 'founder'} <= {a['proposal']['lane'] for a in attempts}
    assert any(a['inheritance']['mode'] == 'exact' for a in attempts)
    for a in attempts:
        assert a['validation_loss'] <= a['initial_validation_loss'] + 1e-8
    bundle = read_export(recovered / 'symbiosis')
    engine_evidence.validate_engine_bundle(bundle, verify_cache=True)
    assert json.loads(invoke('replay', recovered).stdout)['status'] == 'passed'
    invoke('inspect', recovered)
    rejected = invoke('run', '--resume', recovered, '--architecture-policy', 'v2', success=False)
    assert rejected.returncode != 0 and 'differs from saved run' in rejected.stderr
    read = engine_evidence.artifact_json
    attacked = deepcopy(read(bundle, 'state.json'))
    attacked['search']['proposal_policy'] = 'v2'
    with monkeypatch.context() as patch:
        patch.setattr(engine_evidence, 'artifact_json', lambda b, n: attacked if n == 'state.json' else read(b, n))
        with pytest.raises(ValueError, match='research policy'):
            engine_evidence.validate_engine_bundle(bundle)
    if architecture == 'portfolio_v4':
        attacked = deepcopy(read(bundle, 'state.json'))
        attacked['search']['portfolio_counts']['digits_image'] += 1
        with monkeypatch.context() as patch:
            patch.setattr(engine_evidence, 'artifact_json', lambda b, n: attacked if n == 'state.json' else read(b, n))
            with pytest.raises(ValueError, match='portfolio exploration'):
                engine_evidence.validate_engine_bundle(bundle)
