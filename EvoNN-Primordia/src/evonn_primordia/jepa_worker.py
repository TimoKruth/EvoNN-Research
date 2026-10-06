"""Primordia-owned JEPA pilot compilation and isolated worker."""
from .genome import PrimitiveGenome, Primitive
from .compiler import compile_genome


SYSTEM = 'primordia'


def build(spec, data, candidate, seed):
    genome = PrimitiveGenome(version=2, width=16+8*candidate,
                             primitives=(Primitive(operator=('dense', 'gate')[candidate % 2]),))
    return genome, compile_genome(genome, (data['x'].shape[1]*2,), spec.latent_dim,
                                  'tabular', 'classification', backend=spec.backend, device=spec.device, seed=seed)


def main(argv=None):
    import argparse
    import json
    from pathlib import Path
    from evonn_shared.jepa_experiment import PilotSpec, load_data, write_json, digest, file_digest
    from .jepa_training import fit, measure, encode
    import numpy as np
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('result', type=Path)
    parser.add_argument('--teacher', type=Path)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text())
    if request['system'] != SYSTEM:
        raise ValueError('worker system mismatch')
    spec = PilotSpec.model_validate(request['spec'])
    if request['arm'] not in spec.arms or not 0 <= request['candidate'] < spec.candidates:
        raise ValueError('invalid pilot arm/candidate')
    data = load_data(request['benchmark'], request['seed'], request['label_fraction'])
    seed = request['seed'] + request['candidate'] * 1009
    genome, model = build(spec, data, request['candidate'], seed)
    teacher_embeddings, source = None, None
    if request['arm'] in ('distillation', 'jepa_transfer'):
        if args.teacher is None:
            raise ValueError('frozen teacher artifact is required')
        source = json.loads(args.teacher.with_name('result.json').read_text())
        if source['data'] != data['provenance'] or file_digest(args.teacher) != source['teacher_embeddings_sha256']:
            raise ValueError('teacher data lineage or artifact digest mismatch')
        with np.load(args.teacher, allow_pickle=False) as saved:
            teacher_embeddings = saved['embeddings'].copy()
    result = fit(model, data, spec, request['arm'], seed, args.result.with_suffix('.npz'),
                 teacher_embeddings=teacher_embeddings)
    if source is not None:
        result['transfer'] = dict(source_case=request['teacher_case_id'],
            teacher_embeddings_sha256=source['teacher_embeddings_sha256'],
            source_updates=source['updates'], source_wall_seconds=source['wall_seconds'],
            accounting='reported_prior; not a charged-prior or native motif-transfer gain')
    _, rebuilt = build(spec, data, request['candidate'], seed)
    with np.load(args.result.with_suffix('.npz'), allow_pickle=False) as saved:
        restored = {key: rebuilt.backend.array(saved[key]) for key in saved.files}
    replayed, _ = measure(rebuilt, restored, data, seed)
    if any(not np.isclose(replayed[key], result['metrics'][key], rtol=1e-6, atol=1e-6)
           for key in ('validation', 'missing_input_validation', 'effective_rank')):
        raise ValueError('recompiled model replay mismatch')
    result['recompiled_replay_passed'] = True
    if spec.transfer_teacher == SYSTEM and request['arm'] == 'supervised_long' and request['candidate'] == 0:
        import time
        export_started = time.monotonic()
        embeddings = rebuilt.backend.numpy(encode(rebuilt, restored, data['x'], np.ones_like(data['x'])))
        teacher_path = args.result.with_suffix('.teacher.npz')
        np.savez_compressed(teacher_path, embeddings=embeddings)
        result['teacher_embeddings_sha256'] = file_digest(teacher_path)
        result['teacher_export_seconds'] = time.monotonic()-export_started
        result['teacher_export_encoder_examples'] = len(data['x'])
    result.update(status='ok', system=SYSTEM, request_sha256=digest(request),
                  genome=genome.model_dump(mode='json'), data=data['provenance'],
                  backend=spec.backend, backend_version=model.backend.version, device=spec.device,
                  policy='fixed_architectures_fresh_initialization_no_search')
    write_json(args.result, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
