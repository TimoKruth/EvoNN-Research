"""New-run defaults and explicit alternatives; saved policies retain their meaning."""
import argparse
import json
import platform

from evonn_shared.hierarchy_presets import hierarchy_presets, standard_hierarchy_policy

DEFAULT_BUDGET = 128
DEFAULT_FIT_TIMEOUT = 600.
DEFAULT_TIMEOUT = DEFAULT_BUDGET * (DEFAULT_FIT_TIMEOUT + 30.) + 600.
DEFAULT_BACKEND = ('mlx_native' if platform.system() == 'Darwin' and platform.machine() == 'arm64'
                   else 'numpy_fallback')
UNSET = object()


def preset_policy(name):
    if name == 'legacy':
        return None
    if name == 'standard':
        return standard_hierarchy_policy()
    try:
        return hierarchy_presets()[name]
    except KeyError:
        raise ValueError('unknown Stratograph preset: ' + name) from None


def cli_defaults():
    return dict(budget=DEFAULT_BUDGET, timeout=DEFAULT_TIMEOUT, fit_timeout=DEFAULT_FIT_TIMEOUT,
                backend=DEFAULT_BACKEND, research=standard_hierarchy_policy().model_dump(mode='json'))


def expand_preset(argv):
    if not argv or argv[0] not in {'run', 'evolve'}:
        return argv
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('--preset', choices=('standard', 'legacy', *hierarchy_presets()))
    options, remaining = parser.parse_known_args(argv[1:])
    if options.preset is None:
        return argv
    if any(arg.split('=', 1)[0] in {'--config', '--research', '--resume'} for arg in remaining):
        parser.error('--preset cannot be combined with --config, --research or --resume; '
                     'resume uses the saved policy')
    policy = preset_policy(options.preset)
    return [argv[0], *remaining, '--research',
            json.dumps(policy.model_dump(mode='json') if policy is not None else None, sort_keys=True)]
