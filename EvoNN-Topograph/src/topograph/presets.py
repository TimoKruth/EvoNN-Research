"""Named configurations; expand to existing policies without changing replay identities."""
import argparse
import json

from evonn_shared.topograph_policy import TopographResearchPolicy


def preset_policy(name):
    if name in {"legacy", "open"}:
        return name, None
    if name == "next":
        return "next", TopographResearchPolicy()
    if name == "mixer":
        # Exact winning arm of the completed September 2026 confirmation.
        return "next", TopographResearchPolicy(adapters="mixer")
    raise ValueError("unknown Topograph preset: " + name)


def new_run_policy(variant=None, research_options=None):
    """Resolve an omitted policy to mixer; explicit variants retain their settings."""
    if variant is not None:
        return variant, research_options
    variant, policy = preset_policy("mixer")
    options = policy.model_dump(mode="json")
    if research_options is not None:
        options.update(research_options.model_dump(mode="json")
                       if isinstance(research_options, TopographResearchPolicy) else research_options)
    return variant, options


def expand_preset(argv):
    """Explicit presets are fully serialized; ordinary defaults resolve in RunConfig."""
    if not argv or argv[0] not in {"run", "evolve"}:
        return argv
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--preset", choices=("mixer", "next", "open", "legacy"))
    options, remaining = parser.parse_known_args(argv[1:])
    if options.preset is None:
        return argv
    if any(arg.split("=", 1)[0] in {"--config", "--variant", "--research-options", "--resume"}
           for arg in remaining):
        parser.error("--preset cannot be combined with --config, --variant, --research-options or --resume; "
                     "resume uses the saved configuration")
    variant, policy = preset_policy(options.preset)
    result = [argv[0], *remaining, "--variant", variant]
    if policy is not None:
        result += ["--research-options", json.dumps(policy.model_dump(mode="json"), sort_keys=True)]
    return result
