"""Raw-feature reference pool for the separate JEPA pilot data contract.

Every arm executes the same controls; these estimators do not receive JEPA
training. This is a disclosed small pilot pool, not the canonical contender floor.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from threadpoolctl import threadpool_limits
from evonn_shared.jepa_experiment import PilotSpec, load_data, masks, write_json, digest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('result', type=Path)
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text())
    spec = PilotSpec.model_validate(request['spec'])
    if request['system'] != 'contenders' or request['arm'] not in spec.arms:
        raise ValueError('contender request mismatch')
    data = load_data(request['benchmark'], request['seed'], request['label_fraction'])
    regression = data['regression']
    pool = (('ridge', Ridge(alpha=1)), ('hist_gradient_boosting', HistGradientBoostingRegressor(
        max_iter=64, max_leaf_nodes=15, early_stopping=False, random_state=request['seed']))) if regression else (
        ('logistic_regression', LogisticRegression(max_iter=300)),
        ('hist_gradient_boosting', HistGradientBoostingClassifier(
            max_iter=64, max_leaf_nodes=15, early_stopping=False, random_state=request['seed'])))
    rows = []
    keep = masks(np.random.default_rng(request['seed']+17), len(data['xv']), data['xv'].shape[1], 0.25,
                 request['benchmark'])
    for name, model in pool:
        started = time.monotonic()
        with threadpool_limits(limits=1):
            model.fit(data['x'][data['labeled']], data['y'])
            clean = model.predict(data['xv'])
            missing = model.predict(data['xv']*keep)
        if regression:
            def quality(p):
                return float(np.mean((p*data['target_scale']+data['target_mean']-data['yv'])**2))
        else:
            def quality(p):
                return float(np.mean(p == data['yv']))
        rows.append(dict(estimator=name, validation=quality(clean), missing_input_validation=quality(missing),
                         wall_seconds=time.monotonic()-started))
    winner = sorted(rows, key=lambda row: row['validation'], reverse=not regression)[0]
    write_json(args.result, dict(status='ok', system='contenders', request_sha256=digest(request),
               data=data['provenance'], estimators=rows, fits=len(rows),
               metrics=dict(metric='mse' if regression else 'accuracy',
                            direction='minimize' if regression else 'maximize',
                            validation=winner['validation'], missing_input_validation=winner['missing_input_validation']),
               wall_seconds=sum(row['wall_seconds'] for row in rows),
               policy='raw_features_same_pool_each_arm_validation_selected',
               budget_note='fixed estimator caps; not update- or compute-matched to neural fits'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
