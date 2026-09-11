"""V2 primitive registry: pure differentiable, shape-preserving, causal programs.

New primitives are explicit source/version changes. Every registered primitive
is reachable by mutation; none is removed on the basis of observed fitness.
"""


def projection(backend, activated, merged):
    return activated


def gate(backend, activated, merged):
    return activated * backend.sigmoid(merged)


def residual(backend, activated, merged):
    return (activated + merged) * .5


def identity(backend, activated, merged):
    return merged


def sequence(backend, activated, merged):
    if activated.ndim != 3:
        return activated
    # Lower-triangular averaging is causal and stays on the autodiff graph.
    import numpy as np
    length = activated.shape[1]
    matrix = np.tril(np.ones((length, length), dtype=np.float32))
    matrix /= np.arange(1, length + 1, dtype=np.float32)[:, None]
    prefix = backend.array(matrix) @ activated
    return (activated + prefix) * .5


OPERATORS = dict(projection=projection, gate=gate, residual=residual, sequence=sequence, identity=identity)


def register(name, operator):
    import re
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', name) or name in OPERATORS or not callable(operator):
        raise ValueError('a unique primitive name and callable are required')
    OPERATORS[name] = operator
