from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "scripts/policy/validate_import_boundaries.py"
WORKSPACE_MEMBERS = (
    "EvoNN-Shared",
    "EvoNN-Compare",
    "EvoNN-Contenders",
    "EvoNN-Prism",
    "EvoNN-Topograph",
    "EvoNN-Stratograph",
    "EvoNN-Primordia",
)


@pytest.fixture(scope="module")
def validator():
    assert VALIDATOR_PATH.is_file(), "import boundary validator is not installed"
    spec = importlib.util.spec_from_file_location("import_boundaries", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repository_copy(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    shutil.copy2(REPO_ROOT / "pyproject.toml", root / "pyproject.toml")
    for member in WORKSPACE_MEMBERS:
        source = REPO_ROOT / member
        target = root / member
        target.mkdir()
        shutil.copy2(source / "pyproject.toml", target / "pyproject.toml")
        shutil.copytree(source / "src", target / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(
        REPO_ROOT / "shared-benchmarks",
        root / "shared-benchmarks",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    return root


def _diagnostics(validator, root: Path) -> list[str]:
    return validator.validate_repository(root)


def _append_source(root: Path, member: str, relative: str, source: str) -> Path:
    path = root / member / "src" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_checked_in_repository_passes_import_boundary_policy(validator) -> None:
    assert _diagnostics(validator, REPO_ROOT) == []


def test_engine_packages_do_not_import_sibling_engines(validator, repository_copy: Path) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/z_violation.py", "from topograph import search\n")
    _append_source(repository_copy, "EvoNN-Prism", "prism/a_violation.py", "import stratograph.runtime\n")

    first = _diagnostics(validator, repository_copy)
    second = _diagnostics(validator, repository_copy)

    assert first == second
    assert first == sorted(first)
    assert len(first) == 2
    assert "EvoNN-Prism/src/prism/a_violation.py:1" in first[0]
    assert "forbidden import edge evonn-prism -> evonn-stratograph" in first[0]
    assert "EvoNN-Prism/src/prism/z_violation.py:1" in first[1]
    assert "forbidden import edge evonn-prism -> evonn-topograph" in first[1]


def test_shared_does_not_import_system_packages(validator, repository_copy: Path) -> None:
    _append_source(repository_copy, "EvoNN-Shared", "evonn_shared/direct.py", "import evonn_contenders\n")
    _append_source(
        repository_copy,
        "EvoNN-Shared",
        "evonn_shared/dynamic.py",
        'import importlib\nimportlib.import_module("evonn_compare.runtime")\n',
    )
    _append_source(
        repository_copy,
        "EvoNN-Shared",
        "evonn_shared/non_literal.py",
        "from importlib import import_module\nname = 'json'\nimport_module(name)\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("forbidden import edge evonn-shared -> evonn-contenders" in item for item in diagnostics)
    assert any(
        "dynamic.py:2" in item
        and "forbidden dynamic import edge evonn-shared -> evonn-compare" in item
        for item in diagnostics
    )
    assert any(
        "non_literal.py:3" in item
        and "non-literal dynamic import via import_module is disallowed" in item
        for item in diagnostics
    )


def test_compare_uses_artifact_boundary(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Compare",
        "evonn_compare/runner.py",
        "from prism.cli import main\nimport evonn_contenders.runtime\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert any("runner.py:1" in item and "evonn-compare -> evonn-prism" in item for item in diagnostics)
    assert any("runner.py:2" in item and "evonn-compare -> evonn-contenders" in item for item in diagnostics)


def test_workspace_dependencies_match_allowed_matrix(validator, repository_copy: Path) -> None:
    prism_manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    text = prism_manifest.read_text(encoding="utf-8")
    text = text.replace(
        'dependencies = ["evonn-shared"]',
        'dependencies = [\n    "evonn-shared",\n    "EvoNN.Topograph[fast]>=1 ; python_version >= \'3.13\'",\n    "not-evonn-topograph-helper",\n]',
    )
    text += '\n[tool.uv.sources.evonn-topograph]\nworkspace = true\n\n[tool.uv.sources.orphan-helper]\nworkspace = true\n'
    prism_manifest.write_text(text, encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("forbidden dependency edge evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("forbidden workspace source edge evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("workspace source 'orphan-helper' has no matching project dependency" in item for item in diagnostics)
    assert not any("not-evonn-topograph-helper" in item for item in diagnostics)


def test_workspace_member_and_import_identities_are_exact(validator, repository_copy: Path) -> None:
    root_manifest = repository_copy / "pyproject.toml"
    text = root_manifest.read_text(encoding="utf-8")
    text = text.replace('    "EvoNN-Primordia",\n', '    "EvoNN-Prism",\n    "Unexpected-Package",\n')
    root_manifest.write_text(text, encoding="utf-8")
    shared_manifest = repository_copy / "EvoNN-Shared/pyproject.toml"
    shared_manifest.write_text(
        shared_manifest.read_text(encoding="utf-8").replace('packages = ["src/evonn_shared"]', 'packages = ["src/shared_wrong"]'),
        encoding="utf-8",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("duplicate workspace member: EvoNN-Prism" in item for item in diagnostics)
    assert any("missing workspace member: EvoNN-Primordia" in item for item in diagnostics)
    assert any("extra workspace member: Unexpected-Package" in item for item in diagnostics)
    assert any("expected import package path 'src/evonn_shared'" in item for item in diagnostics)


def test_shared_benchmarks_is_data_only(validator, repository_copy: Path) -> None:
    benchmarks = repository_copy / "shared-benchmarks"
    (benchmarks / "pyproject.toml").write_text("[project]\nname='runtime-bypass'\n", encoding="utf-8")
    (benchmarks / "catalog/__init__.py").write_text("", encoding="utf-8")
    (benchmarks / "runtime.py").write_text("print('runtime')\n", encoding="utf-8")
    (benchmarks / "tests/helper.py").write_text("HELPER = True\n", encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("shared-benchmarks/catalog/__init__.py:1" in item and "Python package marker" in item for item in diagnostics)
    assert any("shared-benchmarks/pyproject.toml:1" in item and "Python package metadata" in item for item in diagnostics)
    assert any("shared-benchmarks/runtime.py:1" in item and "runtime Python file" in item for item in diagnostics)
    assert not any("tests/helper.py" in item for item in diagnostics)


def test_dynamic_import_aliases_fail_closed(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/importlib_alias.py",
        'import importlib as il\nil.import_module("topograph.runtime")\n',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/from_alias.py",
        'from importlib import import_module as im\nim("stratograph.runtime")\n',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/assigned_alias.py",
        "import importlib\nloader = importlib.import_module\ntarget = 'topograph'\nloader(target)\n",
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/builtins_alias.py",
        'import builtins as builtin_api\nbuiltin_api.__import__("evonn_primordia.runtime")\n',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/builtin_from_alias.py",
        'from builtins import __import__ as load\nload("topograph.runtime")\n',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 5
    assert any("importlib_alias.py:2" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("from_alias.py:2" in item and "evonn-prism -> evonn-stratograph" in item for item in diagnostics)
    assert any(
        "assigned_alias.py:4" in item and "non-literal dynamic import via importlib.import_module" in item
        for item in diagnostics
    )
    assert any("builtins_alias.py:2" in item and "evonn-prism -> evonn-primordia" in item for item in diagnostics)
    assert any("builtin_from_alias.py:2" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)


def test_runpy_module_aliases_fail_closed(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/runpy_alias.py",
        'import runpy as rp\nrp.run_module("topograph.runtime")\n',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/runpy_from_alias.py",
        "from runpy import run_module as run\ntarget = 'stratograph'\nrun(target)\n",
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/runpy_assigned_alias.py",
        'import runpy\nrunner = runpy.run_module\nrunner("evonn_primordia.runtime")\n',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/runpy_keyword.py",
        'import runpy\nrunpy.run_module(mod_name="topograph.runtime")\n',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 4
    assert any("runpy_alias.py:2" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("runpy_from_alias.py:3" in item and "non-literal dynamic import via runpy.run_module" in item for item in diagnostics)
    assert any("runpy_assigned_alias.py:3" in item and "evonn-prism -> evonn-primordia" in item for item in diagnostics)
    assert any("runpy_keyword.py:2" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)


def test_relative_importlib_calls_resolve_literal_package_and_fail_closed_otherwise(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/relative_own.py",
        'import importlib\nimportlib.import_module(".plugin", "prism")\n',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/relative_forbidden.py",
        'import importlib\nimportlib.import_module(".plugin", package="topograph")\n',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/relative_unknown.py",
        "import importlib\npackage = 'prism'\nimportlib.import_module('.plugin', package)\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert any("relative_forbidden.py:2" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("relative_unknown.py:3" in item and "non-literal dynamic import" in item for item in diagnostics)
    assert not any("relative_own.py" in item for item in diagnostics)


def test_pep621_runtime_entry_points_obey_import_matrix(validator, repository_copy: Path) -> None:
    manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + '''
[project.scripts]
forbidden-script = "topograph.cli:main"
allowed-own = "prism.cli:main"

[project.gui-scripts]
forbidden-gui = "stratograph.gui:main"

[project.entry-points."evonn.plugins"]
forbidden-plugin = "evonn_primordia:SYSTEM"
allowed-shared = "evonn_shared:__version__"
''',
        encoding="utf-8",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("project.scripts.forbidden-script" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("project.gui-scripts.forbidden-gui" in item and "evonn-prism -> evonn-stratograph" in item for item in diagnostics)
    assert any(
        "project.entry-points.evonn.plugins.forbidden-plugin" in item and "evonn-prism -> evonn-primordia" in item
        for item in diagnostics
    )


def test_optional_and_group_dependencies_and_every_source_alternative_are_validated(
    validator, repository_copy: Path
) -> None:
    root_manifest = repository_copy / "pyproject.toml"
    root_manifest.write_text(
        root_manifest.read_text(encoding="utf-8").replace('dev = [\n', 'dev = [\n    "evonn-compare",\n'),
        encoding="utf-8",
    )
    prism_manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    text = prism_manifest.read_text(encoding="utf-8")
    text = text.replace(
        '[tool.uv.sources]\nevonn-shared = { workspace = true }',
        '''[tool.uv.sources]
evonn-shared = { workspace = true }
evonn-topograph = [
    { workspace = true, marker = "sys_platform == 'darwin'" },
    { workspace = true, marker = "sys_platform == 'linux'" },
]
orphan-helper = [
    { workspace = true, marker = "sys_platform == 'darwin'" },
    { workspace = true, marker = "sys_platform == 'linux'" },
]''',
    )
    text += (
        '\n[project.optional-dependencies]\nforbidden = ["EvoNN.Topograph>=1"]\n'
        '\n[dependency-groups]\nforbidden = ["evonn-contenders"]\n'
    )
    prism_manifest.write_text(text, encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("evonn-workspace" in item and "dependency edge evonn-workspace -> evonn-compare" in item for item in diagnostics)
    assert any("optional-dependencies.forbidden" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("dependency-groups.forbidden" in item and "evonn-prism -> evonn-contenders" in item for item in diagnostics)
    assert sum("forbidden workspace source edge evonn-prism -> evonn-topograph" in item for item in diagnostics) == 2
    assert sum("workspace source 'orphan-helper'" in item and "no matching" in item for item in diagnostics) == 2


def test_workspace_exclude_cannot_hide_a_declared_member(validator, repository_copy: Path) -> None:
    manifest = repository_copy / "pyproject.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "[tool.pytest.ini_options]",
            'exclude = ["EvoNN-Prism"]\n\n[tool.pytest.ini_options]',
        ),
        encoding="utf-8",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("workspace exclude is disallowed" in item and "EvoNN-Prism" in item for item in diagnostics)


def test_workspace_and_production_source_symlinks_fail_closed(
    validator, repository_copy: Path, tmp_path: Path
) -> None:
    prism_member = repository_copy / "EvoNN-Prism"
    external_member = tmp_path / "external-prism-member"
    shutil.move(prism_member, external_member)
    prism_member.symlink_to(external_member, target_is_directory=True)

    compare_source = repository_copy / "EvoNN-Compare/src/evonn_compare"
    external_python = tmp_path / "external_runtime.py"
    external_python.write_text("import topograph\n", encoding="utf-8")
    (compare_source / "linked_runtime.py").symlink_to(external_python)

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("EvoNN-Prism:1" in item and "workspace member path must not be a symbolic link" in item for item in diagnostics)
    assert any("linked_runtime.py:1" in item and "production source path must not be a symbolic link" in item for item in diagnostics)


def test_symlinked_package_root_cannot_hide_forbidden_imports(
    validator, repository_copy: Path, tmp_path: Path
) -> None:
    package_root = repository_copy / "EvoNN-Prism/src/prism"
    shutil.rmtree(package_root)
    external_package = tmp_path / "external-prism-package"
    external_package.mkdir()
    (external_package / "__init__.py").write_text("import topograph\n", encoding="utf-8")
    package_root.symlink_to(external_package, target_is_directory=True)

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("EvoNN-Prism/src/prism:1" in item and "production source path must not be a symbolic link" in item for item in diagnostics)


def test_shared_benchmarks_rejects_symlinks(validator, repository_copy: Path, tmp_path: Path) -> None:
    catalog = repository_copy / "shared-benchmarks/catalog"
    shutil.rmtree(catalog)
    external_catalog = tmp_path / "external-catalog"
    external_catalog.mkdir()
    (external_catalog / "__init__.py").write_text("", encoding="utf-8")
    catalog.symlink_to(external_catalog, target_is_directory=True)

    diagnostics = _diagnostics(validator, repository_copy)

    assert any(
        "shared-benchmarks/catalog:1" in item and "symbolic link found in data-only skeleton" in item
        for item in diagnostics
    )


def test_validator_cli_reports_all_violations_and_runs_from_another_directory(
    validator, repository_copy: Path, tmp_path: Path
) -> None:
    _append_source(repository_copy, "EvoNN-Compare", "evonn_compare/b.py", "import prism\n")
    _append_source(repository_copy, "EvoNN-Shared", "evonn_shared/a.py", "__import__('topograph')\n")

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(repository_copy)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    output = result.stdout.splitlines()
    assert output[0] == "Import boundary policy: FAIL (2 violations)"
    assert len([line for line in output if line.startswith("ERROR: ")]) == 2
    assert "evonn-compare -> evonn-prism" in result.stdout
    assert "evonn-shared -> evonn-topograph" in result.stdout


def test_validator_cli_passes_checked_in_repository_from_another_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "Import boundary policy: PASS (7 packages, shared-benchmarks data-only)"
