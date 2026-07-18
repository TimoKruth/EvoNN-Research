#!/usr/bin/env python3
"""Validate EvoNN workspace import, dependency, and data-only boundaries."""

from __future__ import annotations

import ast
from collections import Counter
import importlib.util
from pathlib import Path
import re
import sys
import tomllib
from typing import Any, NamedTuple


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
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")


def normalize_distribution_name(name: str) -> str:
    """Apply the PEP 503 normalization used for PEP 508 distribution names."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(requirement: str) -> str | None:
    """Extract and normalize the distribution name from a PEP 508 requirement."""
    match = _REQUIREMENT_NAME.match(requirement)
    return normalize_distribution_name(match.group(1)) if match else None


def _diagnostic(repo_root: Path, path: Path, line: int, source: str, message: str) -> str:
    try:
        relative = path.relative_to(repo_root).as_posix()
    except ValueError:
        relative = path.as_posix()
    return f"{relative}:{max(line, 1)}: {source}: {message}"


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


def _line_containing(path: Path, value: str, default: int = 1) -> int:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return default
    for number, line in enumerate(lines, 1):
        if value in line:
            return number
    return default


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
    paths = [root] if root.is_symlink() else []
    if root.is_dir():
        paths.extend(path for path in root.rglob("*") if path.is_symlink())
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
        source_root = member_root / "src"
        for link in _symlinks_at_or_below(source_root):
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    link,
                    1,
                    spec.distribution,
                    "production source path must not be a symbolic link",
                )
            )
        if not source_root.is_dir():
            diagnostics.append(
                _diagnostic(repo_root, source_root, 1, spec.distribution, "required production src directory is missing")
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


def _workspace_source_alternatives(value: Any) -> list[tuple[int | None, dict[str, Any]]]:
    return [
        (index, alternative)
        for index, alternative in _source_alternatives(value)
        if _valid_workspace_source_alternative(alternative)
    ]


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
        table = project.get(table_name)
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
    allowed_targets = ALLOWED_INTERNAL_TARGETS.get(source, set())
    locator = TomlLocator(manifest)
    dependency_names: set[str] = set()
    dependency_lines: dict[str, int] = {}
    for surface, requirements in _dependency_surfaces(metadata, manifest, locator, repo_root, source, diagnostics):
        for dependency in requirements:
            if isinstance(dependency, dict) and set(dependency) == {"include-group"}:
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
            dependency_lines.setdefault(target, _dependency_location(locator, surface, dependency))
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
                    dependency_lines.get(target, 1),
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
        target_spec = SPEC_BY_IMPORT_ROOT.get(module_name.partition(".")[0])
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


_FORBIDDEN_PROVIDER_IMPORTS = {"runpy", "builtins"}
_FORBIDDEN_FROM_IMPORTS = {
    "importlib": {"import_module", "*"},
    "runpy": {"run_module", "*"},
    "builtins": {"__import__", "exec", "eval", "getattr", "hasattr", "setattr", "delattr", "*"},
    "operator": {"attrgetter", "methodcaller", "*"},
}
_FORBIDDEN_CALLS = {"__import__", "exec", "eval"}
_BUILTIN_REFLECTION_HELPERS = {"getattr", "hasattr", "setattr", "delattr"}
_OPERATOR_REFLECTION_HELPERS = {"attrgetter", "methodcaller"}
_FORBIDDEN_REFLECTION_NAMES = {"import_module", "run_module", "__import__", "exec", "eval"}
_FORBIDDEN_ATTRIBUTE_ACQUISITIONS = _FORBIDDEN_REFLECTION_NAMES | _OPERATOR_REFLECTION_HELPERS
_FORBIDDEN_SUBSCRIPT_ACQUISITIONS = _FORBIDDEN_ATTRIBUTE_ACQUISITIONS | _BUILTIN_REFLECTION_HELPERS


class _StrictPythonPolicy(ast.NodeVisitor):
    def __init__(
        self,
        repo_root: Path,
        path: Path,
        source_distribution: str,
        allowed_targets: set[str],
        diagnostics: list[str],
    ) -> None:
        self.repo_root = repo_root
        self.path = path
        self.source_distribution = source_distribution
        self.allowed_targets = allowed_targets
        self.diagnostics = diagnostics
        self.provider_import_reported = False

    def _error(self, line: int, message: str) -> None:
        self.diagnostics.append(
            _diagnostic(self.repo_root, self.path, line, self.source_distribution, message)
        )

    def _check_static_import(self, module_name: str, line: int) -> None:
        target = SPEC_BY_IMPORT_ROOT.get(module_name.partition(".")[0])
        if target and target.distribution != self.source_distribution and target.distribution not in self.allowed_targets:
            self._error(
                line,
                f"forbidden import edge {self.source_distribution} -> {target.distribution} via {module_name}",
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_static_import(alias.name, node.lineno)
            root = alias.name.partition(".")[0]
            if alias.name == "importlib" or root in _FORBIDDEN_PROVIDER_IMPORTS:
                self.provider_import_reported = True
                self._error(
                    node.lineno,
                    f"forbidden dynamic-loading primitive import: {alias.name}",
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            self._check_static_import(node.module, node.lineno)
        if node.level != 0 or not node.module:
            return
        forbidden = _FORBIDDEN_FROM_IMPORTS.get(node.module)
        if not forbidden:
            return
        for alias in node.names:
            if alias.name in forbidden:
                self.provider_import_reported = True
                primitive = node.module if alias.name == "*" else alias.name
                self._error(
                    node.lineno,
                    f"forbidden dynamic-loading primitive import: {primitive} from {node.module}",
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

    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load):
            return
        if node.id in _FORBIDDEN_CALLS:
            self._error(node.lineno, f"forbidden dynamic execution primitive reference: {node.id}")
        elif node.id in _BUILTIN_REFLECTION_HELPERS:
            self._error(node.lineno, f"forbidden reflection primitive acquisition: {node.id}")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            not self.provider_import_reported
            and isinstance(node.ctx, ast.Load)
            and node.attr in _FORBIDDEN_ATTRIBUTE_ACQUISITIONS
        ):
            self._error(node.lineno, f"forbidden dynamic primitive attribute acquisition: {node.attr}")
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        reflected = self._literal_string(node.slice)
        if reflected in _FORBIDDEN_SUBSCRIPT_ACQUISITIONS:
            self._error(node.lineno, f"forbidden explicit reflection naming dynamic primitive: {reflected}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        function_name = self._call_name(node.func)
        direct_builtin_reflection = (
            isinstance(node.func, ast.Name) and function_name in _BUILTIN_REFLECTION_HELPERS
        )
        if direct_builtin_reflection:
            reflected = self._literal_string(node.args[1]) if len(node.args) > 1 else None
            if reflected is None:
                self._error(
                    node.lineno,
                    f"forbidden non-literal reflection: {function_name} requires a literal safe attribute-name argument",
                )
            elif reflected in _FORBIDDEN_SUBSCRIPT_ACQUISITIONS:
                self._error(
                    node.lineno,
                    f"forbidden explicit reflection naming dynamic primitive: {reflected}",
                )
            for argument in node.args:
                self.visit(argument)
            for keyword in node.keywords:
                self.visit(keyword.value)
            return
        self.generic_visit(node)


def _production_python_files(repo_root: Path) -> list[tuple[Path, str, set[str]]]:
    files: list[tuple[Path, str, set[str]]] = []
    for spec in PACKAGE_SPECS:
        source_root = repo_root / spec.directory / "src"
        if not source_root.is_dir():
            continue
        files.extend(
            (path, spec.distribution, ALLOWED_INTERNAL_TARGETS[spec.distribution])
            for path in source_root.rglob("*.py")
        )

    scripts_root = repo_root / "scripts"
    if scripts_root.is_dir():
        for path in scripts_root.rglob("*.py"):
            files.append((path, "repository-scripts", set()))
    return sorted(files, key=lambda item: item[0].relative_to(repo_root).as_posix().encode("utf-8"))


def validate_python_imports(repo_root: Path) -> list[str]:
    """Enforce static import edges and the strict production primitive ban."""
    diagnostics: list[str] = []
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
            source_distribution,
            allowed_targets,
            diagnostics,
        ).visit(tree)
    return sorted(set(diagnostics), key=lambda item: item.encode("utf-8"))


def _load_benchmark_invariant(repo_root: Path) -> Any:
    module_path = repo_root / "EvoNN-Shared/src/evonn_shared/benchmarks.py"
    spec = importlib.util.spec_from_file_location("_evonn_shared_benchmark_policy", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_shared_benchmarks(repo_root: Path) -> list[str]:
    """Apply the shared package's canonical data-only benchmark layout invariant."""
    diagnostics: list[str] = []
    data_root = repo_root / "shared-benchmarks"
    try:
        invariant = _load_benchmark_invariant(repo_root)
        violations = invariant.find_data_skeleton_violations(data_root)
    except (AttributeError, ImportError, OSError, SyntaxError) as exc:
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
