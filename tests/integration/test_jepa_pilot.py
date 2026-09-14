"""JEPA objective, engine, accounting and full-roster artifact qualification."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from evonn_shared.jepa_experiment import PilotSpec, SYSTEMS, ARMS, TRANSFER_ARMS, load_data, masks, digest
from evonn_compare.jepa import cases, plan, read_manifest, report, run
from prism import jepa_worker as prism_worker, jepa_training as prism_training
from topograph import jepa_worker as topograph_worker, jepa_training as topograph_training
from stratograph import jepa_worker as stratograph_worker, jepa_training as stratograph_training
from evonn_primordia import jepa_worker as primordia_worker, jepa_training as primordia_training

ENGINES = [(prism_worker, prism_training), (topograph_worker, topograph_training),
           (stratograph_worker, stratograph_training), (primordia_worker, primordia_training)]


def specification(**kwargs):
    return PilotSpec(**dict(benchmarks=('breast_cancer',), seeds=(131,), label_fractions=(0.1,),
                           candidates=1, pretrain_steps=2, finetune_steps=2, batch_size=8, latent_dim=4, **kwargs))


def tiny_data():
    rng = np.random.default_rng(29)
    x = rng.normal(size=(24, 6)).astype(np.float32)
    return dict(x=x[:16], xv=x[16:], y=(x[:8, 0] > 0).astype(np.int64),
                yv=(x[16:, 0] > 0).astype(np.int64), labeled=np.arange(8), output_dim=2,
                regression=False, target_mean=0, target_scale=1,
                provenance=dict(benchmark='jepa_pilot_breast_cancer_v1', seed=131))


@pytest.mark.parametrize('override', [dict(systems=SYSTEMS[:-1]), dict(arms=ARMS[:-1]),
    dict(seeds=()), dict(seeds=(3, 3)), dict(label_fractions=(0,)), dict(device='gpu'),
    dict(candidates=9), dict(pretrain_steps=0), dict(learning_rate=float('nan'))])
def test_invalid_or_partial_matrices_rejected(override):
    with pytest.raises(ValueError):
        PilotSpec(**override)


def test_data_keeps_unlabeled_rows_and_training_transforms_identical():
    low, full = (load_data('breast_cancer', 131, fraction) for fraction in (0.1, 1.0))
    np.testing.assert_array_equal(low['x'], full['x'])
    np.testing.assert_array_equal(low['xv'], full['xv'])
    assert len(low['y']) == len(low['labeled']) < len(full['y'])
    assert low['provenance']['split_sha256'] == full['provenance']['split_sha256']
    assert set(low['y']) == {0, 1}
    assert not low['provenance']['test_access']
    np.testing.assert_allclose(low['x'].mean(0), 0, atol=2e-5)


@pytest.mark.parametrize('benchmark,width', [('digits', 64), ('breast_cancer', 30)])
def test_masks_are_reproducible_complementary_and_nonempty(benchmark, width):
    keep = masks(np.random.default_rng(12), 8, width, 0.5, benchmark)
    np.testing.assert_array_equal(keep, masks(np.random.default_rng(12), 8, width, 0.5, benchmark))
    assert np.all(keep*(1-keep) == 0)
    assert np.all((keep.sum(1) > 0) & (keep.sum(1) < width))


@pytest.mark.parametrize('worker,training', ENGINES, ids=[w.SYSTEM for w, _ in ENGINES])
def test_actual_engine_jepa_gradients_and_control_accounting(tmp_path, worker, training):
    spec, data = specification(), tiny_data()
    results = {}
    for arm in ARMS:
        _, model = worker.build(spec, data, 0, 131)
        results[arm] = training.fit(model, data, spec, arm, 131, tmp_path/f'{arm}.npz')
        assert results[arm]['encoder_weight_delta'] > 0
        assert results[arm]['replay_passed']
        if arm in ('jepa', 'reconstruction'):
            assert results[arm]['pretrain_diagnostics']['encoder_weight_delta'] > 0
    assert len({r['initial_weights_sha256'] for r in results.values()}) == 1
    assert results['supervised_short']['updates'] == 2
    assert results['supervised_long']['updates'] == results['jepa']['updates'] == 4
    assert results['jepa']['encoder_forward_examples'] == 64
    assert results['reconstruction']['encoder_forward_examples'] == 32
    assert results['jepa']['phase_updates'] == {'pretrain': 2, 'finetune': 2}
    assert results['jepa']['curve'] != results['reconstruction']['curve']
    with np.load(tmp_path/'jepa.npz') as first, np.load(tmp_path/'supervised_long.npz') as second:
        assert any(not np.array_equal(first[k], second[k]) for k in first.files)


def test_variance_penalty_detects_constant_representations():
    _, model = prism_worker.build(specification(), tiny_data(), 0, 131)
    b = model.backend
    variance, covariance = prism_training.regularization(b, b.array(np.zeros((8, 4), np.float32)))
    assert float(b.numpy(variance)) > 0.98
    assert float(b.numpy(covariance)) == 0


def test_numpy_regularization_gradient_matches_finite_difference():
    _, model = prism_worker.build(specification(), tiny_data(), 0, 131)
    b = model.backend
    z = np.random.default_rng(1).normal(size=(8, 4)).astype(np.float32)*0.2
    def loss(p):
        variance, covariance = prism_training.regularization(b, p['z'])
        return variance + covariance*0.04
    _, gradients = b.gradients(loss, {'z': b.array(z)})
    plus, minus = z.copy(), z.copy()
    plus[0, 0] += 0.001
    minus[0, 0] -= 0.001
    numerical = (float(b.numpy(loss({'z': b.array(plus)})))-float(b.numpy(loss({'z': b.array(minus)}))))/0.002
    assert gradients['z'][0, 0] == pytest.approx(numerical, abs=1e-4)


def test_masked_student_cannot_observe_hidden_values():
    _, model = prism_worker.build(specification(), tiny_data(), 0, 131)
    data = tiny_data()['x']
    keep = np.ones_like(data)
    keep[:, :3] = 0
    altered = data.copy()
    altered[:, :3] += 100
    p = {k: model.backend.array(v) for k, v in model.weights.items()}
    np.testing.assert_array_equal(model.backend.numpy(prism_training.encode(model, p, data, keep)),
                                  model.backend.numpy(prism_training.encode(model, p, altered, keep)))


def test_manifest_and_pending_report_include_every_engine(tmp_path):
    workspace = tmp_path/'pilot'
    manifest = plan(workspace, specification())
    assert len(manifest['cases']) == 20
    assert manifest['neural_fits'] == 16
    assert manifest['contender_fits'] == 8
    result = report(workspace)
    assert result['status'] == 'incomplete'
    assert {r['system'] for r in result['rows']} == set(SYSTEMS)
    manifest['cases'].pop()
    manifest['manifest_sha256'] = digest({k: v for k, v in manifest.items() if k != 'manifest_sha256'})
    (workspace/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='matrix'):
        read_manifest(workspace)


def test_producer_drift_blocks_resume(tmp_path, monkeypatch):
    from evonn_compare import jepa
    workspace = tmp_path/'pilot'
    plan(workspace, specification())
    monkeypatch.setattr(jepa, 'producer', lambda: {'source_sha256': 'changed'})
    with pytest.raises(ValueError, match='producer changed'):
        run(workspace, max_cases=1)


def test_training_copies_stay_identical():
    paths = [Path(module.__file__) for _, module in ENGINES]
    assert len({p.read_bytes() for p in paths}) == 1


def test_matrix_matches_architectures_across_arms():
    matrix = list(cases(specification()))
    assert len({c['id'] for c in matrix}) == len(matrix)
    assert {(c['request']['arm'], c['request']['system']) for c in matrix} == set(
        (arm, system) for arm in ARMS for system in SYSTEMS)


def test_transfer_requires_controls_and_binds_teacher_within_each_split():
    with pytest.raises(ValueError):
        specification(transfer_teacher='prism')
    spec = specification(transfer_teacher='prism', arms=ARMS+TRANSFER_ARMS)
    matrix = list(cases(spec))
    assert len(matrix) == 30
    by_id = {case['id']: case['request'] for case in matrix}
    for case in matrix:
        request = case['request']
        if 'teacher_case_id' in request:
            source = by_id[request['teacher_case_id']]
            assert source['system'] == 'prism' and source['arm'] == 'supervised_long'
            assert source['candidate'] == 0
            for field in ('benchmark', 'seed', 'label_fraction'):
                assert source[field] == request[field]


@pytest.mark.parametrize('worker,training', ENGINES, ids=[w.SYSTEM for w, _ in ENGINES])
def test_frozen_teacher_transfer_uses_actual_engine(tmp_path, worker, training):
    spec, data = specification(transfer_teacher='prism', arms=ARMS+TRANSFER_ARMS), tiny_data()
    teacher = np.random.default_rng(23).normal(size=(len(data['x']), spec.latent_dim)).astype(np.float32)
    before = teacher.copy()
    results = []
    for arm in TRANSFER_ARMS:
        _, model = worker.build(spec, data, 0, 131)
        result = training.fit(model, data, spec, arm, 131, tmp_path/f'{arm}.npz', teacher_embeddings=teacher)
        assert result['pretrain_diagnostics']['encoder_weight_delta'] > 0
        results.append(result)
    np.testing.assert_array_equal(teacher, before)
    assert results[0]['initial_weights_sha256'] == results[1]['initial_weights_sha256']
    assert results[0]['curve'] != results[1]['curve']
    with pytest.raises(ValueError, match='teacher embeddings'):
        training.fit(model, data, spec, 'jepa_transfer', 131, tmp_path/'bad.npz', teacher_embeddings=teacher[:2])


def test_ema_target_has_no_gradients(tmp_path):
    spec, data = specification(), tiny_data()
    _, model = prism_worker.build(spec, data, 0, 131)
    b = model.backend
    prism_training.fit(model, data, spec, 'jepa', 131, tmp_path/'fit.npz')
    with np.load(tmp_path/'fit.npz') as saved:
        parameters = {key: b.array(saved[key]) for key in saved.files}
    parameters.update({'target/'+key: b.array(value) for key, value in model.weights.items()})
    x = data['x'][:8]
    keep = np.ones_like(x)
    keep[:, :3] = 0
    def loss(p):
        teacher = {key: p['target/'+key] for key in model.weights}
        return prism_training.auxiliary_loss(model, p, teacher, x, keep, 'jepa', spec)
    _, gradients = b.gradients(loss, parameters)
    assert all(np.count_nonzero(gradient) == 0 for key, gradient in gradients.items() if key.startswith('target/'))
    assert any(np.count_nonzero(gradient) for key, gradient in gradients.items() if key in model.weights)


@pytest.mark.skipif(sys.platform != 'darwin', reason='MLX qualification runs on macOS')
@pytest.mark.parametrize('worker,training', ENGINES, ids=[w.SYSTEM for w, _ in ENGINES])
def test_native_backend_real_training(tmp_path, worker, training):
    spec, data = specification(backend='mlx_native'), tiny_data()
    _, model = worker.build(spec, data, 0, 131)
    result = training.fit(model, data, spec, 'jepa', 131, tmp_path/'native.npz')
    assert result['encoder_weight_delta'] > 0
    assert result['pretrain_diagnostics']['encoder_weight_delta'] > 0
    assert result['replay_passed']


def test_failure_is_charged_visible_and_never_silently_retried(tmp_path, monkeypatch):
    from evonn_compare import jepa
    import subprocess
    workspace = tmp_path/'failed'
    plan(workspace, specification())
    identity = jepa.producer()
    monkeypatch.setattr(jepa, 'producer', lambda: identity)
    calls = []
    def fail(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired('pilot-worker', 1)
    monkeypatch.setattr(jepa.subprocess, 'run', fail)
    result = run(workspace, max_cases=1)
    assert result['status'] == 'incomplete'
    failed = [r for r in result['rows'] if r['status'] == 'failed']
    assert len(failed) == 1 and failed[0]['charged_attempt']
    assert {r['system'] for r in result['rows']} == set(SYSTEMS)
    run(workspace, max_cases=1)
    assert len(calls) == 1


def test_complete_run_resume_and_artifact_tampering(tmp_path):
    """Real isolated five-system execution and resume at a case boundary."""
    workspace = tmp_path/'complete'
    plan(workspace, specification())
    first = run(workspace, max_cases=5)
    assert first['completed'] == 5 and first['status'] == 'incomplete'
    result = run(workspace)
    assert result['completed'] == 20 and result['status'] == 'complete'
    before = (workspace/'report.json').read_bytes()
    assert run(workspace)['status'] == 'complete'
    assert (workspace/'report.json').read_bytes() == before
    case = next(r for r in result['rows'] if r['system'] == 'prism')
    weights = workspace/'cases'/case['id']/'result.npz'
    weights.write_bytes(weights.read_bytes()+b'tamper')
    checked = report(workspace)
    assert checked['status'] == 'incomplete'
    assert next(r for r in checked['rows'] if r['id'] == case['id'])['status'] == 'invalid'


@pytest.mark.parametrize('during_worker', [False, True])
def test_mid_session_producer_change_cannot_publish_success(tmp_path, monkeypatch, during_worker):
    from evonn_compare import jepa
    workspace = tmp_path/'drift'
    manifest = plan(workspace, specification())
    identity = manifest['producer']
    identities = iter([identity, identity, {'changed': True}] if during_worker else [identity, {'changed': True}])
    monkeypatch.setattr(jepa, 'producer', lambda: next(identities))
    monkeypatch.setattr(jepa.subprocess, 'run', lambda *args, **kwargs: None)
    if during_worker:
        result = run(workspace, max_cases=1)
        assert result['status'] == 'incomplete' and result['completed'] == 0
        assert result['rows'][0]['status'] == 'failed'
        assert 'producer changed during the worker' in result['rows'][0]['error']
    else:
        with pytest.raises(ValueError, match='producer changed during the session'):
            run(workspace, max_cases=1)
        assert not list((workspace/'cases').glob('*/receipt.json'))


def test_optional_mlx_metadata_is_not_required_for_numpy(monkeypatch):
    from evonn_compare import jepa
    original = jepa.importlib.metadata.version
    def without_mlx(name):
        if name == 'mlx':
            raise jepa.importlib.metadata.PackageNotFoundError(name)
        return original(name)
    monkeypatch.setattr(jepa.importlib.metadata, 'version', without_mlx)
    assert jepa.producer()['mlx_version'] is None
