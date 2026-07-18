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
                _line_containing(root_manifest, "exclude"),
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
                _line_containing(root_manifest, f'"{member}"'),
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
                _line_containing(root_manifest, f'"{member}"'),
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
        manifest = member_root / "pyproject.toml"
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
                    _line_containing(manifest, "name"),
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
                    _line_containing(manifest, "packages"),
                    spec.distribution,
                    f"expected import package path '{expected_package_path}', found {packages!r}",
                )
            )
        if not (repo_root / spec.directory / expected_package_path).is_dir():
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    manifest,
                    _line_containing(manifest, "packages"),
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


def _workspace_source_alternatives(value: Any) -> list[tuple[int | None, dict[str, Any]]]:
    if isinstance(value, dict):
        return [(None, value)] if value.get("workspace") is True else []
    if isinstance(value, list):
        return [
            (index, alternative)
            for index, alternative in enumerate(value)
            if isinstance(alternative, dict) and alternative.get("workspace") is True
        ]
    return []


def _is_workspace_source(value: Any) -> bool:
    return bool(_workspace_source_alternatives(value))


def _dependency_surfaces(
    metadata: dict[str, Any],
    manifest: Path,
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
                _line_containing(manifest, "dependencies"),
                source,
                "project.dependencies must be a list",
            )
        )
    else:
        surfaces.append(("project.dependencies", dependencies))

    optional = project.get("optional-dependencies") if isinstance(project, dict) else None
    if optional is not None and not isinstance(optional, dict):
        diagnostics.append(
            _diagnostic(repo_root, manifest, _line_containing(manifest, "optional-dependencies"), source, "project.optional-dependencies must be a table")
        )
    elif isinstance(optional, dict):
        for group, requirements in optional.items():
            surface = f"project.optional-dependencies.{group}"
            if isinstance(requirements, list):
                surfaces.append((surface, requirements))
            else:
                diagnostics.append(
                    _diagnostic(repo_root, manifest, _line_containing(manifest, str(group)), source, f"{surface} must be a list")
                )

    groups = metadata.get("dependency-groups")
    if groups is not None and not isinstance(groups, dict):
        diagnostics.append(
            _diagnostic(repo_root, manifest, _line_containing(manifest, "dependency-groups"), source, "dependency-groups must be a table")
        )
    elif isinstance(groups, dict):
        for group, requirements in groups.items():
            surface = f"dependency-groups.{group}"
            if isinstance(requirements, list):
                surfaces.append((surface, requirements))
            else:
                diagnostics.append(
                    _diagnostic(repo_root, manifest, _line_containing(manifest, str(group)), source, f"{surface} must be a list")
                )
    return surfaces


def _runtime_entry_point_surfaces(project: dict[str, Any]) -> list[tuple[str, Any]]:
    entries: list[tuple[str, Any]] = []
    for table_name in ("scripts", "gui-scripts"):
        table = project.get(table_name)
        if isinstance(table, dict):
            entries.extend((f"project.{table_name}.{name}", value) for name, value in table.items())
    groups = project.get("entry-points")
    if isinstance(groups, dict):
        for group, table in groups.items():
            if isinstance(table, dict):
                entries.extend((f"project.entry-points.{group}.{name}", value) for name, value in table.items())
    return entries


def _validate_dependency_context(
    repo_root: Path,
    manifest: Path,
    metadata: dict[str, Any],
    source: str,
    diagnostics: list[str],
) -> None:
    allowed_targets = ALLOWED_INTERNAL_TARGETS.get(source, set())
    dependency_names: set[str] = set()
    for surface, requirements in _dependency_surfaces(metadata, manifest, repo_root, source, diagnostics):
        for dependency in requirements:
            if isinstance(dependency, dict) and set(dependency) == {"include-group"}:
                continue
            if not isinstance(dependency, str):
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        _line_containing(manifest, surface.rpartition(".")[2]),
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
                        _line_containing(manifest, dependency),
                        source,
                        f"cannot parse PEP 508 dependency name from {dependency!r} in {surface}",
                    )
                )
                continue
            dependency_names.add(target)
            if target in SPEC_BY_DISTRIBUTION and target not in allowed_targets:
                diagnostics.append(
                    _diagnostic(
                        repo_root,
                        manifest,
                        _line_containing(manifest, dependency),
                        source,
                        f"forbidden dependency edge {source} -> {target} in {surface} from requirement {dependency!r}",
                    )
                )

    sources = _source_entries(metadata)
    for raw_name, source_value in sources.items():
        if not isinstance(raw_name, str):
            continue
        target = normalize_distribution_name(raw_name)
        line = _line_containing(manifest, raw_name)
        for index, _alternative in _workspace_source_alternatives(source_value):
            suffix = "" if index is None else f" alternative {index}"
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
                    _line_containing(manifest, target),
                    source,
                    f"internal dependency '{target}' must have a matching workspace = true source",
                )
            )

    project = metadata.get("project")
    if not isinstance(project, dict):
        return
    for surface, target_value in _runtime_entry_point_surfaces(project):
        if not isinstance(target_value, str):
            diagnostics.append(
                _diagnostic(repo_root, manifest, _line_containing(manifest, surface.rpartition(".")[2]), source, f"{surface} must be a string module target")
            )
            continue
        module_name = target_value.partition(":")[0].strip()
        target_spec = SPEC_BY_IMPORT_ROOT.get(module_name.partition(".")[0])
        if target_spec and target_spec.distribution != source and target_spec.distribution not in allowed_targets:
            diagnostics.append(
                _diagnostic(
                    repo_root,
                    manifest,
                    _line_containing(manifest, target_value),
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


class _DynamicImportAliases(ast.NodeVisitor):
    _MODULE_FUNCTIONS = {
        "builtins": {"__import__": "builtins.__import__"},
        "importlib": {"import_module": "importlib.import_module"},
        "runpy": {"run_module": "runpy.run_module"},
    }

    def __init__(self) -> None:
        self.module_aliases: dict[str, str] = {name: name for name in self._MODULE_FUNCTIONS}
        self.callable_aliases: dict[str, str] = {"__import__": "__import__"}

    def _expression_kind(self, expression: ast.expr) -> str | None:
        if isinstance(expression, ast.Name):
            return self.callable_aliases.get(expression.id)
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            module = self.module_aliases.get(expression.value.id)
            if module:
                return self._MODULE_FUNCTIONS[module].get(expression.attr)
        return None

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            module = alias.name.partition(".")[0]
            if module in self._MODULE_FUNCTIONS:
                self.module_aliases[alias.asname or module] = module

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        functions = self._MODULE_FUNCTIONS.get(node.module or "", {})
        for alias in node.names:
            kind = functions.get(alias.name)
            if kind:
                if node.module == "importlib" and alias.name == "import_module":
                    kind = "import_module"
                self.callable_aliases[alias.asname or alias.name] = kind

    def visit_Assign(self, node: ast.Assign) -> None:
        kind = self._expression_kind(node.value)
        if kind:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.callable_aliases[target.id] = kind

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None and isinstance(node.target, ast.Name):
            kind = self._expression_kind(node.value)
            if kind:
                self.callable_aliases[node.target.id] = kind


def _dynamic_import_kind(call: ast.Call, aliases: _DynamicImportAliases) -> str | None:
    return aliases._expression_kind(call.func)


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
            aliases = _DynamicImportAliases()
            aliases.visit(tree)
            for node in ast.walk(tree):
                target_root: str | None = None
                import_kind = "import"
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        target_root = alias.name.partition(".")[0]
                        target_spec = SPEC_BY_IMPORT_ROOT.get(target_root)
                        if target_spec and target_spec.distribution not in ALLOWED_INTERNAL_TARGETS[spec.distribution] and target_spec.distribution != spec.distribution:
                            diagnostics.append(
                                _diagnostic(
                                    repo_root,
                                    path,
                                    node.lineno,
                                    spec.distribution,
                                    f"forbidden import edge {spec.distribution} -> {target_spec.distribution} via {alias.name}",
                                )
                            )
                    continue
                if isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:
                        target_root = node.module.partition(".")[0]
                        target_spec = SPEC_BY_IMPORT_ROOT.get(target_root)
                        if target_spec and target_spec.distribution not in ALLOWED_INTERNAL_TARGETS[spec.distribution] and target_spec.distribution != spec.distribution:
                            diagnostics.append(
                                _diagnostic(
                                    repo_root,
                                    path,
                                    node.lineno,
                                    spec.distribution,
                                    f"forbidden import edge {spec.distribution} -> {target_spec.distribution} via {node.module}",
                                )
                            )
                    continue
                if not isinstance(node, ast.Call):
                    continue
                import_kind = _dynamic_import_kind(node, aliases) or ""
                if not import_kind:
                    continue
                target_root, is_literal = _literal_dynamic_root(node, import_kind)
                if not is_literal:
                    diagnostics.append(
                        _diagnostic(
                            repo_root,
                            path,
                            node.lineno,
                            spec.distribution,
                            f"non-literal dynamic import via {import_kind} is disallowed because its target cannot be validated",
                        )
                    )
                    continue
                target_spec = SPEC_BY_IMPORT_ROOT.get(target_root or "")
                if target_spec and target_spec.distribution not in ALLOWED_INTERNAL_TARGETS[spec.distribution] and target_spec.distribution != spec.distribution:
                    diagnostics.append(
                        _diagnostic(
                            repo_root,
                            path,
                            node.lineno,
                            spec.distribution,
                            f"forbidden dynamic import edge {spec.distribution} -> {target_spec.distribution} via {import_kind}",
                        )
                    )
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
