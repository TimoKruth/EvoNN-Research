#!/usr/bin/env python3
"""Validate EvoNN workspace import, dependency, and data-only boundaries."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
import re
import sys
import tomllib
from typing import Any, NamedTuple

from evonn_shared.benchmarks import find_data_skeleton_violations


class PackageSpec(NamedTuple):
    directory: str
    distribution: str
    import_root: str


PACKAGE_SPECS = (
    PackageSpec("EvoNN-Shared", "evonn-shared", "evonn_shared"),
    PackageSpec("EvoNN-Compare", "evonn-compare", "evonn_compare"),
    PackageSpec("EvoNN-Contenders", "evonn-contenders", "evonn_contenders"),
    PackageSpec("EvoNN-Prism", "evonn-prism", "prism"),
    PackageSpec("EvoNN-Topograph", "evonn-topograph", "topograph"),
    PackageSpec("EvoNN-Stratograph", "evonn-stratograph", "stratograph"),
    PackageSpec("EvoNN-Primordia", "evonn-primordia", "evonn_primordia"),
)
EXPECTED_MEMBERS = tuple(spec.directory for spec in PACKAGE_SPECS)
SPEC_BY_DISTRIBUTION = {spec.distribution: spec for spec in PACKAGE_SPECS}
SPEC_BY_IMPORT_ROOT = {spec.import_root: spec for spec in PACKAGE_SPECS}
ALLOWED_INTERNAL_TARGETS = {
    spec.distribution: (set() if spec.distribution == "evonn-shared" else {"evonn-shared"})
    for spec in PACKAGE_SPECS
}
SCRIPT_ALLOWED_INTERNAL_TARGETS = {
    "policy/validate_import_boundaries.py": {"evonn-shared"},
    "policy/validate_backend_capabilities.py": {"evonn-shared"},
    "policy/validate_workspace_dependencies.py": {"evonn-shared"},
    "ci/runtime_probe.py": {spec.distribution for spec in PACKAGE_SPECS},
}
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")


def normalize_distribution_name(name: str) -> str:
    """Apply the PEP 503 normalization used for PEP 508 distribution names."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str | None:
    """Extract and normalize the distribution name from a PEP 508 requirement."""
    match = _REQUIREMENT_NAME.match(requirement)
    return normalize_distribution_name(match.group(1)) if match else None


def _diagnostic(
    repo_root: Path,
    path: Path,
    line: int,
    source: str,
    message: str,
    column: int = 1,
    end_line: int | None = None,
    end_column: int | None = None,
) -> str:
    try:
        relative = path.relative_to(repo_root).as_posix()
    except ValueError:
        relative = path.as_posix()
    location = f"{relative}:{max(line, 1)}:{max(column, 1)}"
    if end_line is not None and end_column is not None:
        location += f"-{max(end_line, 1)}:{max(end_column, 1)}"
    return f"{location}: {source}: {message}"


def _load_toml(path: Path, repo_root: Path, source: str, diagnostics: list[str]) -> dict[str, Any] | None:
    try:
        with path.open("rb") as stream:
            metadata = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        diagnostics.append(_diagnostic(repo_root, path, 1, source, f"cannot load TOML: {exc}"))
        return None
    if not isinstance(metadata, dict):
        diagnostics.append(_diagnostic(repo_root, path, 1, source, "TOML document must be a table"))
        return None
    return metadata


def _split_toml_dotted_key(value: str) -> tuple[str, ...]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    for character in value.strip():
        if quote:
            current.append(character)
            if quote == '"' and character == "\\" and not escaped:
                escaped = True
                continue
            if character == quote and not escaped:
                quote = None
            escaped = False
        elif character in {'"', "'"}:
            quote = character
            current.append(character)
        elif character == ".":
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    parts.append("".join(current).strip())

    normalized: list[str] = []
    for part in parts:
        if len(part) >= 2 and part[0] == part[-1] and part[0] in {'"', "'"}:
            try:
                normalized.append(tomllib.loads(f"value = {part}")["value"])
            except tomllib.TOMLDecodeError:
                normalized.append(part[1:-1])
        else:
            normalized.append(part)
    return tuple(normalized)


def _toml_assignment_key(line: str) -> tuple[str, ...] | None:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if quote:
            if quote == '"' and character == "\\" and not escaped:
                escaped = True
                continue
            if character == quote and not escaped:
                quote = None
            escaped = False
        elif character in {'"', "'"}:
            quote = character
        elif character == "=":
            return _split_toml_dotted_key(line[:index])
        elif character == "#":
            return None
    return None


def _toml_bracket_delta(line: str) -> int:
    quote: str | None = None
    escaped = False
    delta = 0
    for character in line:
        if quote:
            if quote == '"' and character == "\\" and not escaped:
                escaped = True
                continue
            if character == quote and not escaped:
                quote = None
            escaped = False
        elif character in {'"', "'"}:
            quote = character
        elif character in "[{":
            delta += 1
        elif character in "]}":
            delta -= 1
        elif character == "#":
            break
    return delta


class TomlLocator:
    """Locate declarations in the small, conventional TOML used by this workspace."""

    def __init__(self, path: Path) -> None:
        try:
            self.lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            self.lines = []
        self.sections: list[tuple[str, ...]] = []
        current: tuple[str, ...] = ()
        for line in self.lines:
            stripped = line.strip()
            match = re.match(r"^\[\[?(.*?)\]\]?(?:\s*#.*)?$", stripped)
            if match:
                current = _split_toml_dotted_key(match.group(1))
            self.sections.append(current)

    def section_line(self, section: tuple[str, ...], default: int = 1) -> int:
        for number, current in enumerate(self.sections, 1):
            if current == section and self.lines[number - 1].lstrip().startswith("["):
                return number
        return default

    def key_line(self, section: tuple[str, ...], key: str, default: int = 1) -> int:
        for number, (line, current) in enumerate(zip(self.lines, self.sections), 1):
            if current == section and _toml_assignment_key(line) == (key,):
                return number
        return default

    def assignment_span(self, section: tuple[str, ...], key: str) -> tuple[int, int]:
        start = self.key_line(section, key, 0)
        if not start:
            return (0, 0)
        balance = 0
        for number in range(start, len(self.lines) + 1):
            balance += _toml_bracket_delta(self.lines[number - 1])
            if number == start and balance <= 0:
                return (start, start)
            if number > start and balance <= 0:
                return (start, number)
        return (start, len(self.lines))

    def value_line(self, section: tuple[str, ...], key: str, value: str, default: int = 1) -> int:
        start, end = self.assignment_span(section, key)
        if not start:
            return default
        for number in range(start, end + 1):
            if value in self.lines[number - 1]:
                return number
        return start

    def alternative_lines(self, section: tuple[str, ...], key: str, count: int) -> list[int]:
        start, end = self.assignment_span(section, key)
        if not start:
            return [1] * count
        candidates: list[int] = []
        for number in range(start, end + 1):
            stripped = self.lines[number - 1].strip()
            if number == start:
                _, _, value = stripped.partition("=")
                if value.strip().startswith("[") and value.count("{") + value.count('"') > 1 and start == end:
                    candidates.extend([start] * count)
                continue
            if stripped.startswith(("{", '"', "'")):
                candidates.append(number)
        if len(candidates) < count:
            candidates.extend([start] * (count - len(candidates)))
        return candidates[:count]


def _workspace_table(root_metadata: dict[str, Any]) -> dict[str, Any]:
    tool = root_metadata.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    workspace = uv.get("workspace") if isinstance(uv, dict) else None
    return workspace if isinstance(workspace, dict) else {}


def _workspace_members(root_metadata: dict[str, Any]) -> list[Any]:
    members = _workspace_table(root_metadata).get("members")
    return members if isinstance(members, list) else []


def _symlinks_at_or_below(root: Path) -> list[Path]:
    if root.is_symlink():
        return [root]
    paths = [path for path in root.rglob("*") if path.is_symlink()] if root.is_dir() else []
    return sorted(set(paths), key=lambda item: item.as_posix().encode("utf-8"))


def validate_workspace_members(repo_root: Path) -> list[str]:
    """Validate the exact workspace member set and package/import identities."""
    diagnostics: list[str] = []
    root_manifest = repo_root / "pyproject.toml"
    root_locator = TomlLocator(root_manifest)
    if root_manifest.is_symlink():
        diagnostics.append(
            _diagnostic(repo_root, root_manifest, 1, "evonn-workspace", "root workspace manifest must not be a symbolic link")
        )
    root_metadata = _load_toml(root_manifest, repo_root, "evonn-workspace", diagnostics)
    if root_metadata is None:
        return sorted(diagnostics)

    workspace = _workspace_table(root_metadata)
    raw_members = _workspace_members(root_metadata)
    if "exclude" in workspace:
        diagnostics.append(
            _diagnostic(
                repo_root,
                root_manifest,
                root_locator.key_line(("tool", "uv", "workspace"), "exclude"),
                "evonn-workspace",
                f"workspace exclude is disallowed because it can hide declared members: {workspace['exclude']!r}",
            )
        )
    if not raw_members:
        diagnostics.append(
            _diagnostic(repo_root, root_manifest, 1, "evonn-workspace", "tool.uv.workspace.members must be a non-empty list")
        )
    string_members = [member for member in raw_members if isinstance(member, str)]
    for index, member in enumerate(raw_members):
        if not isinstance(member, str):
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    root_manifest,
                    1,
                    "evonn-workspace",
                    f"workspace member at index {index} must be a string",
                )
            )
    counts = Counter(string_members)
    for member in sorted((item for item, count in counts.items() if count > 1), key=lambda item: item.encode("utf-8")):
        diagnostics.append(
            _diagnostic(
                repo_root,
                root_manifest,
                root_locator.value_line(("tool", "uv", "workspace"), "members", member),
                "evonn-workspace",
                f"duplicate workspace member: {member}",
            )
        )
    actual = set(string_members)
    expected = set(EXPECTED_MEMBERS)
    for member in sorted(expected - actual, key=lambda item: item.encode("utf-8")):
        diagnostics.append(
            _diagnostic(repo_root, root_manifest, 1, "evonn-workspace", f"missing workspace member: {member}")
        )
    for member in sorted(actual - expected, key=lambda item: item.encode("utf-8")):
        diagnostics.append(
            _diagnostic(
                repo_root,
                root_manifest,
                root_locator.value_line(("tool", "uv", "workspace"), "members", member),
                "evonn-workspace",
                f"extra workspace member: {member}",
            )
        )

    for spec in PACKAGE_SPECS:
        member_root = repo_root / spec.directory
        if member_root.is_symlink():
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    member_root,
                    1,
                    spec.distribution,
                    "workspace member path must not be a symbolic link",
                )
            )
            continue
        source_root = member_root / "src"
        source_links = _symlinks_at_or_below(source_root)
        for link in source_links:
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    link,
                    1,
                    spec.distribution,
                    "production source path must not be a symbolic link",
                )
            )
        if not source_root.is_symlink():
            if not source_root.is_dir():
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        source_root,
                        1,
                        spec.distribution,
                        "required production src directory is missing",
                    )
                )
            else:
                for entry in sorted(source_root.iterdir(), key=lambda item: item.name.encode("utf-8")):
                    if entry.name != spec.import_root:
                        diagnostics.append(
                            _diagnostic(
                                repo_root,
                                entry,
                                1,
                                spec.distribution,
                                f"unexpected top-level src entry; expected only '{spec.import_root}'",
                            )
                        )
        if spec.distribution == "evonn-shared":
            benchmark_policy = source_root / spec.import_root / "benchmarks.py"
            blocked_by_symlink = any(
                benchmark_policy == link or link in benchmark_policy.parents for link in source_links
            )
            if blocked_by_symlink or not benchmark_policy.is_file():
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        benchmark_policy,
                        1,
                        spec.distribution,
                        "canonical benchmark policy module must be a regular non-symlink production file",
                    )
                )
        manifest = member_root / "pyproject.toml"
        locator = TomlLocator(manifest)
        if manifest.is_symlink():
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    manifest,
                    1,
                    spec.distribution,
                    "workspace manifest must not be a symbolic link",
                )
            )
        metadata = _load_toml(manifest, repo_root, spec.distribution, diagnostics)
        if metadata is None:
            continue
        project = metadata.get("project")
        actual_distribution = project.get("name") if isinstance(project, dict) else None
        if actual_distribution != spec.distribution:
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    manifest,
                    locator.key_line(("project",), "name"),
                    spec.distribution,
                    f"workspace distribution identity must be '{spec.distribution}', found {actual_distribution!r}",
                )
            )
        tool = metadata.get("tool")
        hatch = tool.get("hatch") if isinstance(tool, dict) else None
        build = hatch.get("build") if isinstance(hatch, dict) else None
        targets = build.get("targets") if isinstance(build, dict) else None
        wheel = targets.get("wheel") if isinstance(targets, dict) else None
        packages = wheel.get("packages") if isinstance(wheel, dict) else None
        expected_package_path = f"src/{spec.import_root}"
        if packages != [expected_package_path]:
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    manifest,
                    locator.key_line(("tool", "hatch", "build", "targets", "wheel"), "packages"),
                    spec.distribution,
                    f"expected import package path '{expected_package_path}', found {packages!r}",
                )
            )
        if not (repo_root / spec.directory / expected_package_path).is_dir():
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    manifest,
                    locator.key_line(("tool", "hatch", "build", "targets", "wheel"), "packages"),
                    spec.distribution,
                    f"expected import root directory is missing: {expected_package_path}",
                )
            )
    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


def _source_entries(metadata: dict[str, Any]) -> dict[str, Any]:
    tool = metadata.get("tool")
    uv = tool.get("uv") if isinstance(tool, dict) else None
    sources = uv.get("sources") if isinstance(uv, dict) else None
    return sources if isinstance(sources, dict) else {}


def _source_alternatives(value: Any) -> list[tuple[int | None, Any]]:
    if isinstance(value, list):
        return list(enumerate(value)) if value else [(None, value)]
    return [(None, value)]


def _valid_workspace_source_alternative(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("workspace") is not True:
        return False
    if not set(value) <= {"workspace", "marker"}:
        return False
    marker = value.get("marker")
    return marker is None or (isinstance(marker, str) and bool(marker.strip()))


def _is_workspace_source(value: Any) -> bool:
    alternatives = _source_alternatives(value)
    return bool(alternatives) and all(_valid_workspace_source_alternative(item) for _, item in alternatives)


def _source_alternative_lines(locator: TomlLocator, raw_name: str, value: Any) -> list[int]:
    alternatives = _source_alternatives(value)
    sources_section = ("tool", "uv", "sources")
    if locator.key_line(sources_section, raw_name, 0):
        return locator.alternative_lines(sources_section, raw_name, len(alternatives))
    nested_section = (*sources_section, raw_name)
    return [locator.section_line(nested_section)] * len(alternatives)


def _dependency_surfaces(
    metadata: dict[str, Any],
    manifest: Path,
    locator: TomlLocator,
    repo_root: Path,
    source: str,
    diagnostics: list[str],
) -> list[tuple[str, list[Any]]]:
    surfaces: list[tuple[str, list[Any]]] = []
    project = metadata.get("project")
    dependencies = project.get("dependencies") if isinstance(project, dict) else None
    if not isinstance(dependencies, list):
        diagnostics.append(
            _diagnostic(
                repo_root,
                manifest,
                locator.key_line(("project",), "dependencies"),
                source,
                "project.dependencies must be a list",
            )
        )
    else:
        surfaces.append(("project.dependencies", dependencies))

    optional = project.get("optional-dependencies") if isinstance(project, dict) else None
    if optional is not None and not isinstance(optional, dict):
        diagnostics.append(
            _diagnostic(
                repo_root,
                manifest,
                locator.key_line(
                    ("project",),
                    "optional-dependencies",
                    locator.section_line(("project", "optional-dependencies")),
                ),
                source,
                "project.optional-dependencies must be a table",
            )
        )
    elif isinstance(optional, dict):
        for group, requirements in optional.items():
            surface = f"project.optional-dependencies.{group}"
            if isinstance(requirements, list):
                surfaces.append((surface, requirements))
            else:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        locator.key_line(("project", "optional-dependencies"), str(group)),
                        source,
                        f"{surface} must be a list",
                    )
                )

    groups = metadata.get("dependency-groups")
    if groups is not None and not isinstance(groups, dict):
        diagnostics.append(
            _diagnostic(
                repo_root,
                manifest,
                locator.key_line((), "dependency-groups", locator.section_line(("dependency-groups",))),
                source,
                "dependency-groups must be a table",
            )
        )
    elif isinstance(groups, dict):
        for group, requirements in groups.items():
            surface = f"dependency-groups.{group}"
            if isinstance(requirements, list):
                surfaces.append((surface, requirements))
            else:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        locator.key_line(("dependency-groups",), str(group)),
                        source,
                        f"{surface} must be a list",
                    )
                )
    return surfaces


def _dependency_location(locator: TomlLocator, surface: str, dependency: str | None = None) -> int:
    if surface == "project.dependencies":
        section, key = ("project",), "dependencies"
    elif surface.startswith("project.optional-dependencies."):
        section, key = ("project", "optional-dependencies"), surface.removeprefix("project.optional-dependencies.")
    else:
        section, key = ("dependency-groups",), surface.removeprefix("dependency-groups.")
    return locator.value_line(section, key, dependency) if dependency is not None else locator.key_line(section, key)


def _runtime_entry_point_surfaces(
    project: dict[str, Any],
) -> list[tuple[str, tuple[str, ...], str, Any]]:
    entries: list[tuple[str, tuple[str, ...], str, Any]] = []
    for table_name in ("scripts", "gui-scripts"):
        table = project[table_name] if table_name in project else None
        if isinstance(table, dict):
            entries.extend(
                (f"project.{table_name}.{name}", ("project", table_name), str(name), value)
                for name, value in table.items()
            )
    groups = project.get("entry-points")
    if isinstance(groups, dict):
        for group, table in groups.items():
            if isinstance(table, dict):
                entries.extend(
                    (
                        f"project.entry-points.{group}.{name}",
                        ("project", "entry-points", str(group)),
                        str(name),
                        value,
                    )
                    for name, value in table.items()
                )
    return entries


def _validate_dependency_context(
    repo_root: Path,
    manifest: Path,
    metadata: dict[str, Any],
    source: str,
    diagnostics: list[str],
) -> None:
    allowed_targets = ALLOWED_INTERNAL_TARGETS[source] if source in ALLOWED_INTERNAL_TARGETS else set()
    locator = TomlLocator(manifest)
    dependency_names: set[str] = set()
    dependency_lines: dict[str, int] = {}
    groups = metadata.get("dependency-groups")
    dependency_groups = groups if isinstance(groups, dict) else {}
    for surface, requirements in _dependency_surfaces(metadata, manifest, locator, repo_root, source, diagnostics):
        for dependency in requirements:
            if isinstance(dependency, dict) and surface.startswith("dependency-groups."):
                line = _dependency_location(locator, surface)
                if set(dependency) != {"include-group"} or not isinstance(dependency["include-group"], str) or not dependency["include-group"].strip():
                    diagnostics.append(
                        _diagnostic(
                            repo_root,
                            manifest,
                            line,
                            source,
                            f"{surface} include-group must be a non-empty string in a single-key table",
                        )
                    )
                    continue
                included_group = dependency["include-group"]
                if included_group not in dependency_groups:
                    diagnostics.append(
                        _diagnostic(
                            repo_root,
                            manifest,
                            line,
                            source,
                            f"{surface} references missing dependency group {included_group!r}",
                        )
                    )
                elif not isinstance(dependency_groups[included_group], list):
                    diagnostics.append(
                        _diagnostic(
                            repo_root,
                            manifest,
                            line,
                            source,
                            f"{surface} references invalid dependency group {included_group!r}; expected a list",
                        )
                    )
                continue
            if not isinstance(dependency, str):
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        _dependency_location(locator, surface),
                        source,
                        f"{surface} dependency must be a PEP 508 string, found {dependency!r}",
                    )
                )
                continue
            target = requirement_name(dependency)
            if target is None:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        _dependency_location(locator, surface, dependency),
                        source,
                        f"cannot parse PEP 508 dependency name from {dependency!r} in {surface}",
                    )
                )
                continue
            dependency_names.add(target)
            if target not in dependency_lines:
                dependency_lines[target] = _dependency_location(locator, surface, dependency)
            if target in SPEC_BY_DISTRIBUTION and target not in allowed_targets:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        _dependency_location(locator, surface, dependency),
                        source,
                        f"forbidden dependency edge {source} -> {target} in {surface} from requirement {dependency!r}",
                    )
                )

    sources = _source_entries(metadata)
    for raw_name, source_value in sources.items():
        if not isinstance(raw_name, str):
            continue
        target = normalize_distribution_name(raw_name)
        alternatives = _source_alternatives(source_value)
        lines = _source_alternative_lines(locator, raw_name, source_value)
        for (index, alternative), line in zip(alternatives, lines):
            suffix = "" if index is None else f" alternative {index}"
            valid_workspace = _valid_workspace_source_alternative(alternative)
            if target in SPEC_BY_DISTRIBUTION and not valid_workspace:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        line,
                        source,
                        f"invalid workspace source alternative for '{raw_name}'{suffix}; expected only workspace = true and an optional non-empty marker",
                    )
                )
                continue
            if not valid_workspace:
                continue
            if target not in dependency_names:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        line,
                        source,
                        f"workspace source '{raw_name}'{suffix} has no matching project dependency",
                    )
                )
            if target not in SPEC_BY_DISTRIBUTION:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        line,
                        source,
                        f"workspace source '{raw_name}'{suffix} is not one of the exact EvoNN workspace distributions",
                    )
                )
            elif target not in allowed_targets:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        line,
                        source,
                        f"forbidden workspace source edge {source} -> {target}{suffix}",
                    )
                )
    for target in sorted(dependency_names & set(SPEC_BY_DISTRIBUTION), key=lambda item: item.encode("utf-8")):
        source_value = next(
            (value for name, value in sources.items() if isinstance(name, str) and normalize_distribution_name(name) == target),
            None,
        )
        if target in allowed_targets and not _is_workspace_source(source_value):
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    manifest,
                    dependency_lines[target] if target in dependency_lines else 1,
                    source,
                    f"internal dependency '{target}' must have a matching workspace = true source",
                )
            )

    project = metadata.get("project")
    if not isinstance(project, dict):
        return
    for surface, section, key, target_value in _runtime_entry_point_surfaces(project):
        line = locator.key_line(section, key)
        if not isinstance(target_value, str):
            diagnostics.append(
                _diagnostic(repo_root, manifest, line, source, f"{surface} must be a string module target")
            )
            continue
        module_name = target_value.partition(":")[0].strip()
        import_root = module_name.partition(".")[0]
        target_spec = SPEC_BY_IMPORT_ROOT[import_root] if import_root in SPEC_BY_IMPORT_ROOT else None
        if target_spec and target_spec.distribution != source and target_spec.distribution not in allowed_targets:
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    manifest,
                    line,
                    source,
                    f"forbidden runtime entry point edge {source} -> {target_spec.distribution} at {surface}",
                )
            )


def validate_dependencies(repo_root: Path) -> list[str]:
    """Validate every internal dependency, workspace source, and entry-point edge."""
    diagnostics: list[str] = []
    root_manifest = repo_root / "pyproject.toml"
    root_metadata = _load_toml(root_manifest, repo_root, "evonn-workspace", diagnostics)
    if root_metadata is not None:
        _validate_dependency_context(repo_root, root_manifest, root_metadata, "evonn-workspace", diagnostics)
    for spec in PACKAGE_SPECS:
        manifest = repo_root / spec.directory / "pyproject.toml"
        metadata = _load_toml(manifest, repo_root, spec.distribution, diagnostics)
        if metadata is not None:
            _validate_dependency_context(repo_root, manifest, metadata, spec.distribution, diagnostics)
    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


_RESERVED_PRIMITIVE_KINDS = {
    "importlib": "provider",
    "import_module": "provider",
    "runpy": "provider",
    "run_module": "provider",
    "builtins": "provider",
    "__import__": "execution",
    "exec": "execution",
    "eval": "execution",
    "getattr": "builtin-reflection",
    "hasattr": "builtin-reflection",
    "setattr": "builtin-reflection",
    "delattr": "builtin-reflection",
    "attrgetter": "operator-reflection",
    "methodcaller": "operator-reflection",
    "getitem": "operator-reflection",
    "itemgetter": "operator-reflection",
    "globals": "namespace",
    "locals": "namespace",
    "vars": "namespace",
    "__builtins__": "namespace",
    "__dict__": "namespace",
    "__class__": "namespace",
    "__getattribute__": "namespace",
    "exec_module": "loader",
    "load_module": "loader",
    "__loader__": "loader",
    "__spec__": "loader",
    "entry_points": "metadata-plugin",
    "EntryPoint": "metadata-plugin",
}
_RESERVED_PRIMITIVE_NAMES = frozenset(_RESERVED_PRIMITIVE_KINDS)
_BUILTIN_REFLECTION_HELPERS = frozenset(
    name for name, kind in _RESERVED_PRIMITIVE_KINDS.items() if kind == "builtin-reflection"
)
_METADATA_PLUGIN_APIS = frozenset(
    name for name, kind in _RESERVED_PRIMITIVE_KINDS.items() if kind == "metadata-plugin"
)
_PROVIDER_STAR_MODULES = {"importlib", "runpy", "builtins", "operator"}
_ALLOWED_IMPORTLIB_METADATA_NAMES = {"version", "PackageNotFoundError"}
_MAPPING_LOOKUP_METHODS = {"get", "__getitem__", "setdefault", "pop"}
_MAPPING_POSITIONAL_COUNTS = {"get": {1, 2}, "__getitem__": {1}, "setdefault": {1, 2}, "pop": {1, 2}}
_UNBOUND_LOOKUP_APIS = {"dict": {"get", "__getitem__"}, "object": {"__getattribute__"}}
ALLOWED_EXTERNAL_MODULE_ATTRIBUTE_CALLS = frozenset({("mlx.core", "eval")})
_ALLOWED_EXTERNAL_MODULES = frozenset(module for module, _ in ALLOWED_EXTERNAL_MODULE_ATTRIBUTE_CALLS)


def _external_import_binding(node: ast.Import | ast.ImportFrom, alias: ast.alias) -> tuple[str, str, tuple[str, ...]] | None:
    if isinstance(node, ast.Import) and alias.name in _ALLOWED_EXTERNAL_MODULES:
        if alias.asname:
            return alias.asname, alias.name, (alias.asname,)
        root = alias.name.partition(".")[0]
        return root, alias.name, tuple(alias.name.split("."))
    if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
        for module in _ALLOWED_EXTERNAL_MODULES:
            parent, _, leaf = module.rpartition(".")
            if node.module == parent and alias.name == leaf:
                local_name = alias.asname or alias.name
                return local_name, module, (local_name,)
    return None


def _import_bound_name(node: ast.Import | ast.ImportFrom, alias: ast.alias) -> str | None:
    if alias.name == "*":
        return None
    if alias.asname:
        return alias.asname
    return alias.name.partition(".")[0] if isinstance(node, ast.Import) else alias.name


def _match_bound_names(pattern: ast.pattern) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(pattern):
        if isinstance(node, ast.MatchAs) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


class _LexicalScopeMap(ast.NodeVisitor):
    def __init__(self) -> None:
        self.scopes: dict[ast.AST, ast.AST] = {}
        self.current_scope: ast.AST | None = None

    def visit_Module(self, node: ast.Module) -> None:
        previous = self.current_scope
        self.current_scope = node
        self.scopes[node] = node
        for statement in node.body:
            self.visit(statement)
        self.current_scope = previous

    def _visit_function_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.scopes[node] = self.current_scope if self.current_scope is not None else node
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        if node.returns:
            self.visit(node.returns)
        previous = self.current_scope
        self.current_scope = node
        for statement in node.body:
            self.visit(statement)
        self.current_scope = previous

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function_scope(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function_scope(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.scopes[node] = self.current_scope if self.current_scope is not None else node
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        previous = self.current_scope
        self.current_scope = node
        self.visit(node.body)
        self.current_scope = previous

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scopes[node] = self.current_scope if self.current_scope is not None else node
        for expression in (*node.decorator_list, *node.bases, *(keyword.value for keyword in node.keywords)):
            self.visit(expression)
        previous = self.current_scope
        self.current_scope = node
        for statement in node.body:
            self.visit(statement)
        self.current_scope = previous

    def generic_visit(self, node: ast.AST) -> None:
        if self.current_scope is not None:
            self.scopes[node] = self.current_scope
        super().generic_visit(node)


def _external_alias_rebindings(tree: ast.Module, aliases: set[str]) -> set[str]:
    rebound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id in aliases:
            rebound.add(node.id)
        elif isinstance(node, ast.arg) and node.arg in aliases:
            rebound.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in aliases:
            rebound.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name in aliases:
            rebound.add(node.name)
        elif isinstance(node, ast.pattern):
            rebound.update(_match_bound_names(node) & aliases)
    return rebound


def _allowed_external_call_attributes(tree: ast.Module) -> set[ast.Attribute]:
    scope_map = _LexicalScopeMap()
    scope_map.visit(tree)
    bindings: dict[str, set[tuple[str, tuple[str, ...], ast.AST]]] = {}
    imported_names: dict[str, set[tuple[str, tuple[str, ...], ast.AST] | None]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for alias in node.names:
            bound_name = _import_bound_name(node, alias)
            if bound_name is None:
                continue
            descriptor = _external_import_binding(node, alias)
            normalized = (descriptor[1], descriptor[2], scope_map.scopes[node]) if descriptor else None
            if bound_name not in imported_names:
                imported_names[bound_name] = set()
            imported_names[bound_name].add(normalized)
            if descriptor:
                if bound_name not in bindings:
                    bindings[bound_name] = set()
                bindings[bound_name].add(normalized)

    candidate_aliases = set(bindings)
    rebound = _external_alias_rebindings(tree, candidate_aliases)
    valid_bindings: set[tuple[str, tuple[str, ...], ast.AST]] = set()
    for alias_name, descriptors in bindings.items():
        if alias_name in rebound or len(descriptors) != 1 or imported_names[alias_name] != descriptors:
            continue
        valid_bindings.update(descriptors)

    allowed: set[ast.Attribute] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver_parts: list[str] = []
        receiver: ast.expr = node.func.value
        while isinstance(receiver, ast.Attribute):
            receiver_parts.append(receiver.attr)
            receiver = receiver.value
        if not isinstance(receiver, ast.Name):
            continue
        receiver_parts.append(receiver.id)
        receiver_path = tuple(reversed(receiver_parts))
        call_scope = scope_map.scopes[node] if node in scope_map.scopes else None
        for module, imported_receiver, import_scope in valid_bindings:
            scope_matches = import_scope is tree or import_scope is call_scope
            if (
                scope_matches
                and receiver_path == imported_receiver
                and (module, node.func.attr) in ALLOWED_EXTERNAL_MODULE_ATTRIBUTE_CALLS
            ):
                allowed.add(node.func)
    return allowed


class _StrictPythonPolicy(ast.NodeVisitor):
    def __init__(
        self,
        repo_root: Path,
        path: Path,
        source_text: str,
        source_distribution: str,
        allowed_targets: set[str],
        diagnostics: list[str],
        allowed_external_call_attributes: set[ast.Attribute],
    ) -> None:
        self.repo_root = repo_root
        self.path = path
        self.source_lines = source_text.splitlines()
        self.source_distribution = source_distribution
        self.allowed_targets = allowed_targets
        self.diagnostics = diagnostics
        self.allowed_external_call_attributes = allowed_external_call_attributes

    def _character_column(self, line: int, byte_offset: int) -> int:
        if not 1 <= line <= len(self.source_lines):
            return byte_offset + 1
        prefix = self.source_lines[line - 1].encode("utf-8")[:byte_offset]
        return len(prefix.decode("utf-8")) + 1

    def _error(self, node: ast.AST, message: str) -> None:
        line = getattr(node, "lineno", 1)
        end_line = getattr(node, "end_lineno", line)
        self.diagnostics.append(
            _diagnostic(
                self.repo_root,
                self.path,
                line,
                self.source_distribution,
                message,
                self._character_column(line, getattr(node, "col_offset", 0)),
                end_line,
                self._character_column(end_line, getattr(node, "end_col_offset", 0)),
            )
        )

    def _check_static_import(self, module_name: str, node: ast.AST) -> None:
        import_root = module_name.partition(".")[0]
        target = SPEC_BY_IMPORT_ROOT[import_root] if import_root in SPEC_BY_IMPORT_ROOT else None
        if target and target.distribution != self.source_distribution and target.distribution not in self.allowed_targets:
            self._error(
                node,
                f"forbidden import edge {self.source_distribution} -> {target.distribution} via {module_name}",
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_static_import(alias.name, node)
            root = alias.name.partition(".")[0]
            allowed_metadata = alias.name == "importlib.metadata" and alias.asname is None
            if (root == "importlib" and not allowed_metadata) or root in {"runpy", "builtins"}:
                self._error(
                    node,
                    f"forbidden dynamic-loading primitive import: {alias.name}",
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            self._check_static_import(node.module, node)
        if node.level == 0 and node.module == "importlib.metadata":
            for alias in node.names:
                if alias.name not in _ALLOWED_IMPORTLIB_METADATA_NAMES:
                    primitive = node.module if alias.name == "*" else alias.name
                    self._error(node, f"forbidden importlib.metadata acquisition: {primitive}")
            return
        if node.level == 0 and node.module == "importlib":
            for alias in node.names:
                primitive = node.module if alias.name == "*" else alias.name
                self._error(
                    node,
                    f"forbidden dynamic-loading primitive import: {primitive} from {node.module}",
                )
            return
        if node.level == 0 and node.module and node.module.startswith("importlib."):
            self._error(node, f"forbidden dynamic-loading primitive import: {node.module}")
            return
        module_name = node.module or "." * node.level
        for alias in node.names:
            if alias.name in _RESERVED_PRIMITIVE_NAMES or (
                alias.name == "*" and node.level == 0 and node.module in _PROVIDER_STAR_MODULES
            ):
                primitive = module_name if alias.name == "*" else alias.name
                self._error(
                    node,
                    f"forbidden dynamic-loading primitive import: {primitive} from {module_name}",
                )

    @staticmethod
    def _call_name(function: ast.expr) -> str | None:
        if isinstance(function, ast.Name):
            return function.id
        if isinstance(function, ast.Attribute):
            return function.attr
        return None

    @staticmethod
    def _literal_string(expression: ast.expr | None) -> str | None:
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            return expression.value
        return None

    @staticmethod
    def _is_importlib_metadata_prefix(node: ast.Attribute) -> bool:
        return (
            node.attr == "metadata"
            and isinstance(node.value, ast.Name)
            and node.value.id == "importlib"
        )

    @staticmethod
    def _contains_metadata_plugin_api(node: ast.AST) -> bool:
        return any(
            (isinstance(descendant, ast.Attribute) and descendant.attr in _METADATA_PLUGIN_APIS)
            or (isinstance(descendant, ast.Name) and descendant.id in _METADATA_PLUGIN_APIS)
            for descendant in ast.walk(node)
        )

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id in _RESERVED_PRIMITIVE_NAMES:
            kind = _RESERVED_PRIMITIVE_KINDS[node.id]
            self._error(node, f"forbidden {kind} primitive reference: {node.id}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        direct_metadata_attribute = (
            isinstance(node.value, ast.Attribute) and self._is_importlib_metadata_prefix(node.value)
        )
        if isinstance(node.ctx, ast.Load):
            if node.attr in _RESERVED_PRIMITIVE_NAMES and node not in self.allowed_external_call_attributes:
                self._error(node, f"forbidden reserved primitive attribute acquisition: {node.attr}")
            elif (
                isinstance(node.value, ast.Name)
                and node.value.id in _UNBOUND_LOOKUP_APIS
                and node.attr in _UNBOUND_LOOKUP_APIS[node.value.id]
            ):
                self._error(node, f"forbidden unbound namespace lookup acquisition: {node.value.id}.{node.attr}")
            elif node.attr == "load" and self._contains_metadata_plugin_api(node.value):
                self._error(node, "forbidden importlib.metadata entry-point load acquisition")
            elif direct_metadata_attribute and node.attr not in _ALLOWED_IMPORTLIB_METADATA_NAMES:
                self._error(node, f"forbidden importlib.metadata attribute acquisition: {node.attr}")
        if direct_metadata_attribute:
            return
        if self._is_importlib_metadata_prefix(node):
            self._error(node, "forbidden importlib.metadata module acquisition")
            return
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        reflected = self._literal_string(node.slice)
        if reflected in _RESERVED_PRIMITIVE_NAMES:
            self._error(node, f"forbidden explicit reflection naming reserved primitive: {reflected}")
        self.generic_visit(node)

    @staticmethod
    def _expanded_positional_arguments(node: ast.Call) -> list[ast.expr] | None:
        expanded: list[ast.expr] = []
        for argument in node.args:
            if not isinstance(argument, ast.Starred):
                expanded.append(argument)
            elif isinstance(argument.value, (ast.List, ast.Tuple)):
                expanded.extend(argument.value.elts)
            else:
                return None
        return expanded

    def _check_mapping_lookup_call(self, node: ast.Call, function_name: str) -> None:
        arguments = self._expanded_positional_arguments(node)
        keyword_key = next((keyword.value for keyword in node.keywords if keyword.arg == "key"), None)
        key_expression = arguments[0] if arguments else keyword_key
        reflected = self._literal_string(key_expression)
        valid_form = (
            arguments is not None
            and len(arguments) in _MAPPING_POSITIONAL_COUNTS[function_name]
            and not node.keywords
        )
        if reflected in _RESERVED_PRIMITIVE_NAMES:
            self._error(
                node,
                f"forbidden mapping {function_name} acquisition of reserved primitive: {reflected}",
            )
        elif not valid_form or reflected is None:
            self._error(
                node,
                f"forbidden mapping {function_name} call: requires a literal safe key in a valid positional call form",
            )

    def visit_Call(self, node: ast.Call) -> None:
        function_name = self._call_name(node.func)
        if isinstance(node.func, ast.Attribute) and function_name in _MAPPING_LOOKUP_METHODS:
            self._check_mapping_lookup_call(node, function_name)
        direct_builtin_reflection = (
            isinstance(node.func, ast.Name) and function_name in _BUILTIN_REFLECTION_HELPERS
        )
        if direct_builtin_reflection:
            reflected = self._literal_string(node.args[1]) if len(node.args) > 1 else None
            if reflected is None:
                self._error(
                    node,
                    f"forbidden non-literal reflection: {function_name} requires a literal safe attribute-name argument",
                )
            elif reflected in _RESERVED_PRIMITIVE_NAMES:
                self._error(
                    node,
                    f"forbidden explicit reflection naming dynamic primitive: {reflected}",
                )
            for argument in node.args:
                self.visit(argument)
            for keyword in node.keywords:
                self.visit(keyword.value)
            return
        self.generic_visit(node)


def validate_scripts_topology(repo_root: Path) -> list[str]:
    """Reject symlinks anywhere in the shipped scripts tree."""
    diagnostics = [
        _diagnostic(
            repo_root,
            path,
            1,
            "repository-scripts",
            "shipped scripts path must not be a symbolic link",
        )
        for path in _symlinks_at_or_below(repo_root / "scripts")
    ]
    return sorted(diagnostics, key=lambda item: item.encode("utf-8"))


def _production_python_files(repo_root: Path) -> list[tuple[Path, str, set[str]]]:
    files: list[tuple[Path, str, set[str]]] = []
    for spec in PACKAGE_SPECS:
        member_root = repo_root / spec.directory
        source_root = member_root / "src"
        if member_root.is_symlink() or source_root.is_symlink() or not source_root.is_dir():
            continue
        links = set(_symlinks_at_or_below(source_root))
        files.extend(
            (path, spec.distribution, ALLOWED_INTERNAL_TARGETS[spec.distribution])
            for path in source_root.rglob("*.py")
            if not any(path == link or link in path.parents for link in links)
        )

    scripts_root = repo_root / "scripts"
    if scripts_root.is_dir() and not scripts_root.is_symlink():
        for path in scripts_root.rglob("*.py"):
            if not path.is_symlink():
                relative = path.relative_to(scripts_root).as_posix()
                allowed_targets = SCRIPT_ALLOWED_INTERNAL_TARGETS[relative] if relative in SCRIPT_ALLOWED_INTERNAL_TARGETS else set()
                files.append((path, "repository-scripts", allowed_targets))
    return sorted(files, key=lambda item: item[0].relative_to(repo_root).as_posix().encode("utf-8"))


def validate_python_imports(repo_root: Path) -> list[str]:
    """Enforce script topology, static import edges, and the strict primitive ban."""
    diagnostics = validate_scripts_topology(repo_root)
    for path, source_distribution, allowed_targets in _production_python_files(repo_root):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            line = exc.lineno if isinstance(exc, SyntaxError) and exc.lineno else 1
            diagnostics.append(
                _diagnostic(repo_root, path, line, source_distribution, f"cannot parse production Python: {exc}")
            )
            continue
        _StrictPythonPolicy(
            repo_root,
            path,
            source,
            source_distribution,
            allowed_targets,
            diagnostics,
            _allowed_external_call_attributes(tree),
        ).visit(tree)
    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


def validate_shared_benchmarks(repo_root: Path) -> list[str]:
    """Apply the shared package's canonical data-only benchmark layout invariant."""
    diagnostics: list[str] = []
    data_root = repo_root / "shared-benchmarks"
    try:
        violations = find_data_skeleton_violations(data_root)
    except OSError as exc:
        diagnostics.append(
            _diagnostic(
                repo_root,
                repo_root / "EvoNN-Shared/src/evonn_shared/benchmarks.py",
                1,
                "evonn-shared",
                f"cannot apply shared benchmark layout invariant: {exc}",
            )
        )
        return diagnostics
    for relative, message in violations:
        diagnostics.append(_diagnostic(repo_root, data_root / relative, 1, "shared-benchmarks", message))
    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


def validate_repository(repo_root: Path) -> list[str]:
    """Return all deterministic policy diagnostics for a repository root."""
    root = repo_root.resolve()
    diagnostics = [
        *validate_workspace_members(root),
        *validate_dependencies(root),
        *validate_python_imports(root),
        *validate_shared_benchmarks(root),
    ]
    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) > 1:
        print("Usage: validate_import_boundaries.py [REPOSITORY_ROOT]")
        return 2
    repo_root = Path(arguments[0]).resolve() if arguments else Path(__file__).resolve().parents[2]
    diagnostics = validate_repository(repo_root)
    if diagnostics:
        print(f"Import boundary policy: FAIL ({len(diagnostics)} violations)")
        for diagnostic in diagnostics:
            print(f"ERROR: {diagnostic}")
        return 1
    print("Import boundary policy: PASS (7 packages, shared-benchmarks data-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
