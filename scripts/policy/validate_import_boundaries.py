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


class _BindingValue(NamedTuple):
    known: frozenset[str]
    unknown: bool = False


def _known_binding(*values: str) -> _BindingValue:
    return _BindingValue(frozenset(values), False)


def _union_bindings(values: list[_BindingValue]) -> _BindingValue:
    return _BindingValue(
        frozenset().union(*(value.known for value in values)),
        any(value.unknown for value in values),
    )


_UNKNOWN_BINDING = _BindingValue(frozenset(), True)
_MODULE_FUNCTIONS = {
    "builtins": {"__import__": "builtins.__import__"},
    "importlib": {"import_module": "importlib.import_module"},
    "runpy": {"run_module": "runpy.run_module"},
}


class _BindingScope:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.bindings: dict[str, _BindingValue] = {}
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def clone(self) -> _BindingScope:
        cloned = _BindingScope(self.kind)
        cloned.bindings = self.bindings.copy()
        cloned.global_names = self.global_names.copy()
        cloned.nonlocal_names = self.nonlocal_names.copy()
        return cloned


class _LocalBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.bound: set[str] = set()
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def _target(self, target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            self.bound.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._target(item)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def visit_Import(self, node: ast.Import) -> None:
        self.bound.update(alias.asname or alias.name.partition(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.bound.update(alias.asname or alias.name for alias in node.names if alias.name != "*")

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._target(target)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._target(node.target)
        if node.value:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._target(node.target)
        self.visit(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._target(node.target)
        self.visit(node.value)

    def visit_For(self, node: ast.For) -> None:
        self._target(node.target)
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars:
                self._target(item.optional_vars)
        self.generic_visit(node)

    visit_AsyncWith = visit_With

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.bound.add(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.bound.add(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.bound.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


class _LoopExitFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found = False

    def visit_Break(self, node: ast.Break) -> None:
        self.found = True

    def visit_Continue(self, node: ast.Continue) -> None:
        self.found = True

    def visit_For(self, node: ast.For) -> None:
        return

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        return

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


def _contains_current_loop_exit(statement: ast.stmt) -> bool:
    finder = _LoopExitFinder()
    if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
        return False
    finder.visit(statement)
    return finder.found


def _call_argument(call: ast.Call, keyword: str) -> ast.expr | None:
    if call.args:
        return call.args[0]
    return next((item.value for item in call.keywords if item.arg == keyword), None)


def _literal_dynamic_root(call: ast.Call, kind: str) -> tuple[str | None, bool]:
    keyword = "mod_name" if "run_module" in kind else "name"
    argument = _call_argument(call, keyword)
    if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
        return None, False
    module_name = argument.value
    if module_name.startswith("."):
        if "import_module" not in kind:
            return None, False
        package_argument = call.args[1] if len(call.args) > 1 else next(
            (item.value for item in call.keywords if item.arg == "package"),
            None,
        )
        if not isinstance(package_argument, ast.Constant) or not isinstance(package_argument.value, str):
            return None, False
        try:
            module_name = importlib.util.resolve_name(module_name, package_argument.value)
        except (ImportError, ValueError):
            return None, False
    return module_name.partition(".")[0], True


class _PythonImportAnalyzer(ast.NodeVisitor):
    def __init__(self, repo_root: Path, path: Path, source_distribution: str, diagnostics: list[str]) -> None:
        self.repo_root = repo_root
        self.path = path
        self.source_distribution = source_distribution
        self.allowed_targets = ALLOWED_INTERNAL_TARGETS[source_distribution]
        self.diagnostics = diagnostics
        module_scope = _BindingScope("module")
        module_scope.bindings["__import__"] = _known_binding("call:__import__")
        self.scopes = [module_scope]
        self.functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.external_functions: list[str] = []
        self.active_functions: set[str] = set()
        self.function_exit_outcomes: list[list[list[_BindingScope]]] = []

    def visit_Module(self, node: ast.Module) -> None:
        self._visit_statements(node.body)
        for token in list(self.external_functions):
            self._execute_function(token, propagate=False, mask_module_globals=False)

    def _lookup(self, name: str) -> _BindingValue:
        current = self.scopes[-1]
        if name in current.global_names:
            return self.scopes[0].bindings.get(name, _UNKNOWN_BINDING)
        if name in current.nonlocal_names:
            for scope in reversed(self.scopes[:-1]):
                if scope.kind == "function" and name in scope.bindings:
                    return scope.bindings[name]
            return _UNKNOWN_BINDING
        for scope in reversed(self.scopes):
            if current.kind == "function" and scope.kind == "class":
                continue
            if name in scope.bindings:
                return scope.bindings[name]
        return _UNKNOWN_BINDING

    def _bind(self, name: str, value: _BindingValue) -> None:
        current = self.scopes[-1]
        if name in current.global_names:
            self.scopes[0].bindings[name] = value
            return
        if name in current.nonlocal_names:
            for scope in reversed(self.scopes[:-1]):
                if scope.kind == "function":
                    scope.bindings[name] = value
                    return
        current.bindings[name] = value

    def _bind_target(self, target: ast.expr, value: _BindingValue = _UNKNOWN_BINDING) -> None:
        if isinstance(target, ast.Name):
            self._bind(target.id, value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._bind_target(item)
        elif isinstance(target, ast.Starred):
            self._bind_target(target.value)

    def _expression_binding(self, expression: ast.expr) -> _BindingValue:
        if isinstance(expression, ast.Name):
            return self._lookup(expression.id)
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            module_binding = self._lookup(expression.value.id)
            known: set[str] = set()
            unknown = module_binding.unknown
            for candidate in module_binding.known:
                if not candidate.startswith("module:"):
                    unknown = True
                    continue
                module = candidate.removeprefix("module:")
                kind = _MODULE_FUNCTIONS.get(module, {}).get(expression.attr)
                if kind:
                    known.add(f"call:{kind}")
                else:
                    unknown = True
            return _BindingValue(frozenset(known), unknown)
        if isinstance(expression, ast.IfExp):
            return _union_bindings(
                [self._expression_binding(expression.body), self._expression_binding(expression.orelse)]
            )
        return _UNKNOWN_BINDING

    def _call_bindings(self, call: ast.Call) -> tuple[list[str], list[str], bool]:
        binding = self._expression_binding(call.func)
        loaders = sorted(
            (candidate.removeprefix("call:") for candidate in binding.known if candidate.startswith("call:")),
            key=lambda item: item.encode("utf-8"),
        )
        functions = sorted(
            (candidate for candidate in binding.known if candidate.startswith("function:")),
            key=lambda item: item.encode("utf-8"),
        )
        return loaders, functions, binding.unknown

    def _report_static_import(self, module_name: str, line: int) -> None:
        target = SPEC_BY_IMPORT_ROOT.get(module_name.partition(".")[0])
        if target and target.distribution != self.source_distribution and target.distribution not in self.allowed_targets:
            self.diagnostics.append(
                _diagnostic(
                    self.repo_root,
                    self.path,
                    line,
                    self.source_distribution,
                    f"forbidden import edge {self.source_distribution} -> {target.distribution} via {module_name}",
                )
            )

    def _report_dynamic_import(self, call: ast.Call, kind: str) -> None:
        target_root, is_literal = _literal_dynamic_root(call, kind)
        if not is_literal:
            self.diagnostics.append(
                _diagnostic(
                    self.repo_root,
                    self.path,
                    call.lineno,
                    self.source_distribution,
                    f"non-literal dynamic import via {kind} is disallowed because its target cannot be validated",
                )
            )
            return
        target = SPEC_BY_IMPORT_ROOT.get(target_root or "")
        if target and target.distribution != self.source_distribution and target.distribution not in self.allowed_targets:
            self.diagnostics.append(
                _diagnostic(
                    self.repo_root,
                    self.path,
                    call.lineno,
                    self.source_distribution,
                    f"forbidden dynamic import edge {self.source_distribution} -> {target.distribution} via {kind}",
                )
            )

    def _visit_statements(self, statements: list[ast.stmt]) -> str | None:
        for statement in statements:
            channel = self.visit(statement)
            if channel in {"break", "continue", "return", "raise"}:
                return channel
        return None

    def _merge_outcomes(self, original: list[_BindingScope], outcomes: list[list[_BindingScope]]) -> None:
        self.scopes = original
        for index, scope in enumerate(self.scopes):
            names = set().union(*(outcome[index].bindings for outcome in outcomes))
            merged: dict[str, _BindingValue] = {}
            for name in names:
                values = [outcome[index].bindings.get(name, _UNKNOWN_BINDING) for outcome in outcomes]
                merged[name] = _union_bindings(values)
            scope.bindings = merged

    def _analyze_branches(self, branches: list[list[ast.stmt]]) -> None:
        original = self.scopes
        outcomes: list[list[_BindingScope]] = []
        for branch in branches:
            self.scopes = [scope.clone() for scope in original]
            self._visit_statements(branch)
            outcomes.append([scope.clone() for scope in self.scopes])
        self._merge_outcomes(original, outcomes)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._report_static_import(alias.name, node.lineno)
            root = alias.name.partition(".")[0]
            bound_name = alias.asname or root
            if root in _MODULE_FUNCTIONS and (alias.asname is None or alias.name == root):
                self._bind(bound_name, _known_binding(f"module:{root}"))
            else:
                self._bind(bound_name, _UNKNOWN_BINDING)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            self._report_static_import(node.module, node.lineno)
        functions = _MODULE_FUNCTIONS.get(node.module or "", {}) if node.level == 0 else {}
        for alias in node.names:
            if alias.name == "*":
                self.scopes[-1].bindings = {
                    name: _UNKNOWN_BINDING for name in self.scopes[-1].bindings
                }
                continue
            kind = functions.get(alias.name)
            if kind == "importlib.import_module":
                kind = "import_module"
            self._bind(
                alias.asname or alias.name,
                _known_binding(f"call:{kind}") if kind else _UNKNOWN_BINDING,
            )

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        binding = self._expression_binding(node.value)
        for target in node.targets:
            self._bind_target(target, binding)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.visit(node.annotation)
        if node.value:
            self.visit(node.value)
            binding = self._expression_binding(node.value)
        else:
            binding = _UNKNOWN_BINDING
        self._bind_target(node.target, binding)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        self._bind_target(node.target)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._bind_target(node.target, self._expression_binding(node.value))

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            self._bind_target(target)

    def visit_Break(self, node: ast.Break) -> str:
        return "break"

    def visit_Continue(self, node: ast.Continue) -> str:
        return "continue"

    def visit_Return(self, node: ast.Return) -> str:
        if node.value:
            self.visit(node.value)
        if self.function_exit_outcomes:
            self.function_exit_outcomes[-1].append([scope.clone() for scope in self.scopes])
        return "return"

    def visit_Raise(self, node: ast.Raise) -> str:
        if node.exc:
            self.visit(node.exc)
        if node.cause:
            self.visit(node.cause)
        if self.function_exit_outcomes:
            self.function_exit_outcomes[-1].append([scope.clone() for scope in self.scopes])
        return "raise"

    def visit_Call(self, node: ast.Call) -> None:
        loaders, functions, binding_unknown = self._call_bindings(node)
        self.generic_visit(node)
        for kind in loaders:
            self._report_dynamic_import(node, kind)
        self._invoke_functions(functions, binding_unknown)

    def _function_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> _BindingScope:
        function_scope = _BindingScope("function")
        collector = _LocalBindingCollector()
        for statement in node.body:
            collector.visit(statement)
        function_scope.global_names = collector.global_names
        function_scope.nonlocal_names = collector.nonlocal_names
        for name in collector.bound - collector.global_names - collector.nonlocal_names:
            function_scope.bindings[name] = _UNKNOWN_BINDING
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.args.vararg:
            arguments.append(node.args.vararg)
        if node.args.kwarg:
            arguments.append(node.args.kwarg)
        for argument in arguments:
            function_scope.bindings[argument.arg] = _UNKNOWN_BINDING
        return function_scope

    def _execute_function(self, token: str, propagate: bool, mask_module_globals: bool = False) -> None:
        if token in self.active_functions:
            return
        node = self.functions.get(token)
        if node is None:
            return
        caller_scopes = self.scopes
        self.scopes = [scope.clone() for scope in caller_scopes]
        if mask_module_globals:
            self.scopes[0].bindings = {
                name: (_known_binding("call:__import__") if name == "__import__" else _UNKNOWN_BINDING)
                for name in self.scopes[0].bindings
            }
        function_scope = self._function_scope(node)
        self.scopes.append(function_scope)
        self.active_functions.add(token)
        self.function_exit_outcomes.append([])
        self._visit_statements(node.body)
        exit_outcomes = self.function_exit_outcomes.pop()
        self.active_functions.remove(token)
        if exit_outcomes:
            function_scopes = self.scopes
            outcomes = [[scope.clone() for scope in self.scopes], *exit_outcomes]
            self._merge_outcomes(function_scopes, outcomes)
        outer_outcome = self.scopes[:-1]
        self.scopes = caller_scopes
        if not propagate:
            return
        self.scopes[0].bindings = outer_outcome[0].bindings.copy()
        for index, scope in enumerate(self.scopes[1:], 1):
            if scope.kind == "function":
                scope.bindings = outer_outcome[index].bindings.copy()

    def _invoke_functions(self, tokens: list[str], binding_unknown: bool) -> None:
        if not tokens:
            return
        if len(tokens) == 1 and not binding_unknown:
            self._execute_function(tokens[0], propagate=True)
            return
        original = self.scopes
        outcomes: list[list[_BindingScope]] = []
        if binding_unknown:
            outcomes.append([scope.clone() for scope in original])
        for token in tokens:
            self.scopes = [scope.clone() for scope in original]
            self._execute_function(token, propagate=True)
            outcomes.append([scope.clone() for scope in self.scopes])
        self._merge_outcomes(original, outcomes)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for expression in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if expression:
                self.visit(expression)
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.args.vararg:
            arguments.append(node.args.vararg)
        if node.args.kwarg:
            arguments.append(node.args.kwarg)
        for argument in arguments:
            if argument.annotation:
                self.visit(argument.annotation)
        if node.returns:
            self.visit(node.returns)
        for type_parameter in getattr(node, "type_params", []):
            self.visit(type_parameter)
        token = f"function:{id(node)}"
        self.functions[token] = node
        if self.scopes[-1].kind in {"module", "class"}:
            self.external_functions.append(token)
        self._execute_function(token, propagate=False, mask_module_globals=True)
        self._bind(node.name, _known_binding(token))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for expression in [*node.decorator_list, *node.bases, *(item.value for item in node.keywords)]:
            self.visit(expression)
        class_scope = _BindingScope("class")
        collector = _LocalBindingCollector()
        for statement in node.body:
            collector.visit(statement)
        class_scope.global_names = collector.global_names
        class_scope.nonlocal_names = collector.nonlocal_names
        self.scopes.append(class_scope)
        self._visit_statements(node.body)
        self.scopes.pop()
        self._bind(node.name, _UNKNOWN_BINDING)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for expression in [*node.args.defaults, *node.args.kw_defaults]:
            if expression:
                self.visit(expression)
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.args.vararg:
            arguments.append(node.args.vararg)
        if node.args.kwarg:
            arguments.append(node.args.kwarg)
        for argument in arguments:
            if argument.annotation:
                self.visit(argument.annotation)
        outer = self.scopes
        self.scopes = [scope.clone() for scope in outer]
        function_scope = _BindingScope("function")
        for argument in arguments:
            function_scope.bindings[argument.arg] = _UNKNOWN_BINDING
        self.scopes.append(function_scope)
        self.visit(node.body)
        self.scopes = outer

    def _pattern_binding_names(self, pattern: ast.pattern) -> set[str]:
        names: set[str] = set()
        for item in ast.walk(pattern):
            if isinstance(item, ast.MatchAs) and item.name:
                names.add(item.name)
            elif isinstance(item, ast.MatchStar) and item.name:
                names.add(item.name)
            elif isinstance(item, ast.MatchMapping) and item.rest:
                names.add(item.rest)
        return names

    def visit_Match(self, node: ast.Match) -> None:
        self.visit(node.subject)
        original = self.scopes
        outcomes: list[list[_BindingScope]] = [[scope.clone() for scope in original]]
        for case in node.cases:
            self.scopes = [scope.clone() for scope in original]
            for name in self._pattern_binding_names(case.pattern):
                self._bind(name, _UNKNOWN_BINDING)
            if case.guard:
                self.visit(case.guard)
            self._visit_statements(case.body)
            outcomes.append([scope.clone() for scope in self.scopes])
        self._merge_outcomes(original, outcomes)

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        self._analyze_branches([node.body, node.orelse])

    def _analyze_loop(self, body: list[ast.stmt], orelse: list[ast.stmt], target: ast.expr | None = None) -> None:
        original = self.scopes
        outcomes: list[list[_BindingScope]] = []

        self.scopes = [scope.clone() for scope in original]
        self._visit_statements(orelse)
        outcomes.append([scope.clone() for scope in self.scopes])

        self.scopes = [scope.clone() for scope in original]
        if target:
            self._bind_target(target)
        channel: str | None = None
        for statement in body:
            channel = self.visit(statement)
            if _contains_current_loop_exit(statement):
                outcomes.append([scope.clone() for scope in self.scopes])
            if channel in {"break", "continue", "return", "raise"}:
                break
        outcomes.append([scope.clone() for scope in self.scopes])
        if channel not in {"break", "return", "raise"}:
            self._visit_statements(orelse)
            outcomes.append([scope.clone() for scope in self.scopes])
        self._merge_outcomes(original, outcomes)

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test)
        self._analyze_loop(node.body, node.orelse)

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        self._analyze_loop(node.body, node.orelse, node.target)

    visit_AsyncFor = visit_For

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self._bind_target(item.optional_vars)
        self._visit_statements(node.body)

    visit_AsyncWith = visit_With

    def visit_Try(self, node: ast.Try) -> None:
        original = self.scopes
        outcomes: list[list[_BindingScope]] = []

        self.scopes = [scope.clone() for scope in original]
        body_channel = self._visit_statements(node.body)
        if body_channel is None:
            self._visit_statements(node.orelse)
        self._visit_statements(node.finalbody)
        outcomes.append([scope.clone() for scope in self.scopes])

        for handler in node.handlers:
            for prefix_length in range(len(node.body) + 1):
                self.scopes = [scope.clone() for scope in original]
                self._visit_statements(node.body[:prefix_length])
                if handler.type:
                    self.visit(handler.type)
                if handler.name:
                    self._bind(handler.name, _UNKNOWN_BINDING)
                self._visit_statements(handler.body)
                self._visit_statements(node.finalbody)
                outcomes.append([scope.clone() for scope in self.scopes])

        self._merge_outcomes(original, outcomes)

    visit_TryStar = visit_Try


def validate_python_imports(repo_root: Path) -> list[str]:
    """Parse production source trees and reject forbidden or unresolved dynamic imports."""
    diagnostics: list[str] = []
    for spec in PACKAGE_SPECS:
        source_root = repo_root / spec.directory / "src"
        if not source_root.is_dir():
            continue
        for path in sorted(source_root.rglob("*.py"), key=lambda item: item.as_posix().encode("utf-8")):
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, UnicodeError, SyntaxError) as exc:
                line = exc.lineno if isinstance(exc, SyntaxError) and exc.lineno else 1
                diagnostics.append(
                    _diagnostic(repo_root, path, line, spec.distribution, f"cannot parse production Python: {exc}")
                )
                continue
            _PythonImportAnalyzer(repo_root, path, spec.distribution, diagnostics).visit(tree)
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
