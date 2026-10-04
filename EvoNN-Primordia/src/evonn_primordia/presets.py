"""Operational presets expand to explicit, replayable research controls."""
import argparse

from evonn_shared.primordia_policy import PrimordiaResearchPolicy, RESEARCH_DEFAULTS
from evonn_shared.primordia_presets import PRESETS


def preset_policy(name):
    if name not in PRESETS:
        raise ValueError("unknown Primordia preset: " + name)
    return PrimordiaResearchPolicy(**PRESETS[name])


def cli_configuration(argv):
    """Bare fresh CLI runs use standard; explicit controls/configs keep v2 defaults.

    A preset becomes explicit flags, so a conflicting resume is rejected by the
    existing saved-config checks. We prohibit combining presets with resumes to
    keep restoring historical runs independent of new default choices.
    """
    if not argv or argv[0] not in {"run", "evolve"}:
        return argv, {}
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--preset", choices=tuple(PRESETS))
    options, remaining = parser.parse_known_args(argv[1:])
    policy_flags = {"--" + k.replace("_", "-") for k in RESEARCH_DEFAULTS} | {"--search-policy"}
    flags = {arg.split("=", 1)[0] for arg in remaining}
    if options.preset is not None:
        if flags & (policy_flags | {"--config", "--resume"}):
            parser.error("--preset cannot be combined with --config, --resume or individual research policies; "
                         "resume uses saved controls, and custom controls can be supplied without a preset")
        policy = preset_policy(options.preset).model_dump()
        expanded = [argv[0], *remaining, "--search-policy", policy["search_policy"]]
        for key in RESEARCH_DEFAULTS:
            expanded += ["--" + key.replace("_", "-"), policy[key]]
        return expanded, {}
    if flags & (policy_flags | {"--config", "--resume"}):
        return argv, {}
    # Low-level RunConfig/Search and campaign defaults stay backwards compatible.
    policy = preset_policy("standard").model_dump()
    return argv, {key: policy[key] for key in RESEARCH_DEFAULTS}
