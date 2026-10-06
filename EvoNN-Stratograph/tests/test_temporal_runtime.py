"""V3 process isolation, crash recovery, portable evidence and native replay."""
import json
from pathlib import Path

import pytest

from evonn_shared.engine_evidence import artifact_json, validate_engine_bundle
from evonn_shared.export_reader import read_export
from .test_research_runtime import invoke
from .test_temporal import BACKENDS


@pytest.mark.parametrize('backend', BACKENDS)
def test_temporal_full_pipeline(tmp_path, backend, monkeypatch):
    policy = dict(version=3, evaluator='trainable', temporal='hybrid', embedding_width=8,
                  max_width=8, max_macro_nodes=2, max_cell_nodes=2,
                  normalization='train_standard', evolve_temporal=True, dropout=.1)
    first = invoke('run', '--pack', 'tier_b_core_v2', '--budget', 24, '--epochs', 2,
                   '--population-size', 2, '--timeout', 220, '--fit-timeout', 20,
                   '--backend', backend, '--research', json.dumps(policy),
                   '--output', tmp_path / 'runs', '--cache', tmp_path / 'cache', '--stop-after', 5)
    assert first.returncode == 0, first.stderr
    run = Path(first.stdout.strip().splitlines()[-1])
    drift = invoke('run', '--resume', run, '--research', json.dumps({**policy, 'temporal': 'attention'}))
    assert drift.returncode != 0 and 'differs from saved run' in drift.stderr
    crashed = invoke('run', '--resume', run, '--crash-at', 'transaction', '--crash-step', 6)
    assert crashed.returncode == -9, crashed.stderr
    resumed = invoke('run', '--resume', run)
    assert resumed.returncode == 0, resumed.stderr
    bundle = read_export(run / 'symbiosis')
    validate_engine_bundle(bundle, verify_cache=True)
    assert bundle.results.coverage.ok == 24
    attempts = artifact_json(bundle, 'attempts.json')['attempts']
    assert all(row['evaluator_fidelity'] == 'end_to_end_hierarchy_v3' for row in attempts)
    assert all(len(row['validation_curve']) == row['epochs'] == 2 for row in attempts)
    assert any(row['embedding_weights_changed'] for row in attempts)
    assert all(row['inherited_epoch_savings'] == 0 for row in attempts)
    replay = invoke('replay', run)
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)['status'] == 'passed'

    from copy import deepcopy
    from evonn_shared import engine_evidence
    original = engine_evidence.artifact_json
    tampered = deepcopy(artifact_json(bundle, 'attempts.json'))
    tampered['attempts'][0]['selected_epoch'] = 999
    with monkeypatch.context() as patch:
        patch.setattr(engine_evidence, 'artifact_json', lambda b, name: tampered if name == 'attempts.json' else original(b, name))
        with pytest.raises(ValueError):
            validate_engine_bundle(bundle, verify_cache=True)
