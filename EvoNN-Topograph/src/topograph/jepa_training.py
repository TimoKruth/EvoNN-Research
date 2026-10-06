"""Package-owned fixed-architecture JEPA pilot training.

Kept identical across engines on purpose: no shared engine core or sibling imports.
The local jepa_worker owns compilation. This is an experimental EMA latent
prediction objective with variance/covariance regularization, not a T-JEPA or
LeJEPA reproduction. Fixed masks within a batch prevent mask identity alone
from satisfying the cross-example variance constraint.
"""
from __future__ import annotations

import time
from pathlib import Path
import numpy as np
from evonn_shared.jepa_experiment import masks, file_digest


def regularization(b, z):
    centered = z - z.mean(axis=0, keepdims=True)
    std = ((centered * centered).mean(axis=0) + 1e-4) ** 0.5
    variance = b.relu(1 - std).mean()
    covariance = centered.transpose((1, 0)) @ centered / max(1, z.shape[0]-1)
    off_diagonal = covariance * b.array(1-np.eye(z.shape[1], dtype=np.float32))
    return variance, (off_diagonal * off_diagonal).sum() / z.shape[1]


def encode(model, parameters, x, keep):
    b = model.backend
    inputs = b.concatenate([b.array(x * keep), b.array(keep)], axis=-1)
    return model.forward(parameters, inputs, training=False)


def auxiliary_loss(model, parameters, teacher, x, keep, arm, spec):
    b = model.backend
    z = encode(model, parameters, x, keep)
    if arm == 'reconstruction':
        prediction = z @ parameters['pilot.decoder.w'] + parameters['pilot.decoder.b']
        hidden = b.array(1-keep)
        return (((prediction - b.array(x)) * hidden) ** 2).sum() / hidden.sum()
    complement = 1-keep
    target = b.stop(encode(model, teacher, x, complement))
    prediction = (z @ parameters['pilot.predictor.w'] + parameters['pilot.predictor.b']
                  + b.array(complement) @ parameters['pilot.mask.w'])
    other = encode(model, parameters, x, complement)
    variance, covariance = regularization(b, z)
    other_variance, other_covariance = regularization(b, other)
    return (((prediction-target)**2).mean()
            + spec.variance_weight * (variance+other_variance)/2
            + spec.covariance_weight * (covariance+other_covariance)/2)


def logits(model, parameters, x):
    z = encode(model, parameters, x, np.ones_like(x))
    return z @ parameters['pilot.task.w'] + parameters['pilot.task.b']


def supervised_loss(model, parameters, x, y, regression):
    b = model.backend
    output = logits(model, parameters, x)
    if regression:
        return ((output.reshape((-1,))-b.array(y))**2).mean()
    shifted = output-b.array(b.numpy(output).max(axis=-1, keepdims=True))
    log_probs = shifted-b.log(b.exp(shifted).sum(axis=-1, keepdims=True))
    hot = b.array(np.eye(output.shape[-1], dtype=np.float32)[y])
    return -(hot * log_probs).sum(axis=-1).mean()


def measure(model, parameters, data, seed):
    b = model.backend
    clean = b.numpy(logits(model, parameters, data['xv']))
    keep = masks(np.random.default_rng(data['provenance']['seed']+17), len(data['xv']), data['xv'].shape[1], 0.25,
                 data['provenance']['benchmark'].removeprefix('jepa_pilot_').removesuffix('_v1'))
    z_missing = encode(model, parameters, data['xv'], keep)
    missing = b.numpy(z_missing @ parameters['pilot.task.w'] + parameters['pilot.task.b'])
    if data['regression']:
        def quality(output):
            prediction = output.reshape(-1)*data['target_scale'] + data['target_mean']
            return float(np.mean((prediction-data['yv'])**2))
        metric, direction = 'mse', 'minimize'
    else:
        def quality(output):
            return float(np.mean(output.argmax(-1) == data['yv']))
        metric, direction = 'accuracy', 'maximize'
    diagnostics = representation_diagnostics(model, parameters, data['x'])
    return dict(metric=metric, direction=direction, validation=quality(clean),
                missing_input_validation=quality(missing), **diagnostics), clean


def representation_diagnostics(model, parameters, x):
    b = model.backend
    probe = x[:min(128, len(x))]
    embedding = b.numpy(encode(model, parameters, probe, np.ones_like(probe)))
    singular = np.linalg.svd(embedding-embedding.mean(0), compute_uv=False)
    energy = singular**2
    weights = energy / max(float(energy.sum()), 1e-20)
    rank = float(np.exp(-np.sum(weights * np.log(np.maximum(weights, 1e-20))))) if energy.sum() > 1e-20 else 0.0
    return dict(effective_rank=rank, mean_feature_std=float(embedding.std(0).mean()))


def fit(model, data, spec, arm, seed, output, *, teacher_embeddings=None):
    """Fixed update schedules, fresh initialization, no validation early stopping."""
    b = model.backend
    if arm in ('distillation', 'jepa_transfer'):
        if (teacher_embeddings is None or teacher_embeddings.shape != (len(data['x']), spec.latent_dim)
                or not np.isfinite(teacher_embeddings).all()):
            raise ValueError('finite, row-aligned frozen teacher embeddings required')
    started = time.monotonic()
    initial = {key: value.copy() for key, value in model.weights.items()}
    d, width = spec.latent_dim, data['x'].shape[1]
    rng = np.random.default_rng(seed+1)
    arrays = {key: value.copy() for key, value in initial.items()}
    for name, shape in [('task', (d, data['output_dim'])), ('decoder', (d, width)), ('predictor', (d, d))]:
        arrays[f'pilot.{name}.w'] = (rng.normal(size=shape)/np.sqrt(shape[0])).astype(np.float32)
        arrays[f'pilot.{name}.b'] = np.zeros(shape[1], dtype=np.float32)
    arrays['pilot.mask.w'] = (rng.normal(size=(width, d))/np.sqrt(width)).astype(np.float32)
    # Auxiliary heads are initialized identically in every arm, but only active
    # parameters are optimized. Actual parameter counts are disclosed below.
    moments = {key: np.zeros_like(value) for key, value in arrays.items()}
    variances = {key: np.zeros_like(value) for key, value in arrays.items()}
    teacher = {key: value.copy() for key, value in initial.items()} if arm == 'jepa' else {}
    curve, phase_seconds, updates, forward_examples = [], {}, 0, 0
    phase_updates = {'pretrain': 0, 'finetune': 0}
    pre_rng, supervised_rng = np.random.default_rng(seed+2), np.random.default_rng(seed+3)
    plans = [('pretrain', spec.pretrain_steps), ('finetune', spec.finetune_steps)]
    if arm == 'supervised_short':
        plans = [('finetune', spec.finetune_steps)]
    if arm == 'supervised_long':
        plans = [('finetune', spec.pretrain_steps+spec.finetune_steps)]
    before = {key: value.copy() for key, value in arrays.items()}
    pretrain_diagnostics = None
    for phase, steps in plans:
        phase_started = time.monotonic()
        # A fresh optimizer at the phase boundary avoids reusing SSL moments for
        # the downstream objective; all arms use the same fine-tuning schedule.
        moments = {key: np.zeros_like(value) for key, value in arrays.items()}
        variances = {key: np.zeros_like(value) for key, value in arrays.items()}
        for step in range(steps):
            if time.monotonic()-started >= spec.fit_timeout:
                raise TimeoutError('pilot fit wall-clock limit reached')
            if phase == 'pretrain':
                indices = pre_rng.choice(len(data['x']), size=min(spec.batch_size, len(data['x'])), replace=False)
                x = data['x'][indices]
                keep = masks(pre_rng, 1, width, spec.mask_fraction,
                             data['provenance']['benchmark'].removeprefix('jepa_pilot_').removesuffix('_v1'))
                keep = np.broadcast_to(keep, x.shape).copy()
                teacher_parameters = {key: b.array(value) for key, value in teacher.items()}
                if arm == 'distillation':
                    keep = np.ones_like(x)
                def objective(p):
                    if arm in ('distillation', 'jepa_transfer'):
                        z = encode(model, p, x, keep)
                        prediction = z @ p['pilot.predictor.w'] + p['pilot.predictor.b']
                        prediction = prediction + b.array(1-keep) @ p['pilot.mask.w']
                        variance, covariance = regularization(b, z)
                        return (((prediction-b.array(teacher_embeddings[indices]))**2).mean()
                                + spec.variance_weight*variance + spec.covariance_weight*covariance)
                    return auxiliary_loss(model, p, teacher_parameters, x, keep, arm, spec)
                forward_examples += len(x) * (3 if arm == 'jepa' else 1)
            else:
                indices = supervised_rng.choice(len(data['labeled']), size=min(spec.batch_size, len(data['labeled'])),
                                                replace=False)
                x, y = data['x'][data['labeled'][indices]], data['y'][indices]
                def objective(p):
                    return supervised_loss(model, p, x, y, data['regression'])
                forward_examples += len(x)
            parameters = {key: b.array(value) for key, value in arrays.items()}
            value, gradients = b.gradients(objective, parameters)
            if not np.isfinite(value) or any(not np.isfinite(g).all() for g in gradients.values()):
                raise ValueError('nonfinite pilot objective or gradient')
            norm = np.sqrt(sum(float(np.sum(g*g)) for g in gradients.values()))
            clipping = min(1.0, 1.0/max(norm, 1e-12))
            for key, gradient in gradients.items():
                gradient = gradient * clipping
                moments[key] = 0.9*moments[key] + 0.1*gradient
                variances[key] = 0.999*variances[key] + 0.001*gradient**2
                arrays[key] -= spec.learning_rate * (moments[key]/(1-0.9**(step+1))) / (
                    np.sqrt(variances[key]/(1-0.999**(step+1)))+1e-8)
            if any(not np.isfinite(v).all() for v in arrays.values()):
                raise ValueError('nonfinite pilot weights')
            if phase == 'pretrain' and arm == 'jepa':
                for key in teacher:
                    teacher[key] = spec.ema_decay*teacher[key] + (1-spec.ema_decay)*arrays[key]
            updates += 1
            phase_updates[phase] += 1
            curve.append(dict(phase=phase, step=step+1, loss=float(value)))
        phase_seconds[phase] = time.monotonic()-phase_started
        if phase == 'pretrain':
            pretrain_diagnostics = representation_diagnostics(model, {k: b.array(v) for k, v in arrays.items()}, data['x'])
            pretrain_diagnostics['encoder_weight_delta'] = float(np.sqrt(sum(
                float(np.sum((arrays[k]-initial[k])**2)) for k in initial)))
    parameters = {key: b.array(value) for key, value in arrays.items()}
    metrics, predictions = measure(model, parameters, data, seed)
    output = Path(output)
    np.savez_compressed(output, **arrays)
    with np.load(output, allow_pickle=False) as saved:
        reloaded = {key: b.array(saved[key]) for key in saved.files}
    replay = b.numpy(logits(model, reloaded, data['xv']))
    if not np.allclose(predictions, replay, rtol=1e-6, atol=1e-6):
        raise ValueError('saved pilot winner replay mismatch')
    source_delta = np.sqrt(sum(float(np.sum((arrays[k]-initial[k])**2)) for k in initial))
    import hashlib
    initial_digest = hashlib.sha256(b''.join(before[k].tobytes() for k in sorted(before))).hexdigest()
    return dict(metrics=metrics, pretrain_diagnostics=pretrain_diagnostics, curve=curve,
                updates=updates, phase_updates=phase_updates, phase_seconds=phase_seconds,
                encoder_forward_examples=forward_examples, initial_weights_sha256=initial_digest,
                encoder_weight_delta=float(source_delta),
                encoder_parameters=sum(v.size for v in initial.values()),
                deployed_parameters=sum(v.size for k, v in arrays.items() if k in initial or k.startswith('pilot.task.')),
                allocated_training_parameter_bytes=sum(v.nbytes for v in arrays.values())*3 +
                    (sum(v.nbytes for v in teacher.values()) if arm == 'jepa' else 0),
                wall_seconds=time.monotonic()-started, weights_sha256=file_digest(output), replay_passed=True,
                budget_note='matched updates are not matched compute; forward work and wall time are reported')
