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


def _line_number(path: Path, text: str, occurrence: int = 1) -> int:
    matches = [number for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if text in line]
    return matches[occurrence - 1]


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
        'dependencies = [\n    "evonn-shared",\n    "evonn-topograph[fast]>=1 ; python_version >= \'3.13\'",\n    "not-evonn-topograph-helper",\n]',
    )
    text += '\n[tool.uv.sources.evonn-topograph]\nworkspace = true\n\n[tool.uv.sources.orphan-helper]\nworkspace = true\n'
    prism_manifest.write_text(text, encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("forbidden dependency edge evonn-prism -> evonn-topograph" in item for item in diagnostics)
    source_diagnostic = next(
        item for item in diagnostics if "forbidden workspace source edge evonn-prism -> evonn-topograph" in item
    )
    source_line = _line_number(prism_manifest, "[tool.uv.sources.evonn-topograph]")
    dependency_line = _line_number(prism_manifest, '"evonn-topograph[fast]')
    assert f"EvoNN-Prism/pyproject.toml:{source_line}:" in source_diagnostic
    assert f"pyproject.toml:{dependency_line}:" not in source_diagnostic
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


def test_dynamic_alias_resolution_is_source_ordered(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/later_rebind.py",
        '''import importlib as provider
provider.import_module("topograph.runtime")
import runpy as provider
provider.run_module("stratograph.runtime")
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert any("later_rebind.py:2" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("later_rebind.py:4" in item and "evonn-prism -> evonn-stratograph" in item for item in diagnostics)


def test_dynamic_alias_resolution_respects_function_and_class_scopes(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/scope_collision.py",
        '''import importlib as provider

def parameter_shadow(provider):
    provider.import_module("topograph.runtime")

class Namespace:
    provider = object()
    provider.import_module("topograph.runtime")

def local_rebind():
    import runpy as provider
    provider.run_module("stratograph.runtime")

provider.import_module("evonn_primordia.runtime")
provider = object()
provider.import_module("topograph.runtime")
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert any("scope_collision.py:12" in item and "evonn-prism -> evonn-stratograph" in item for item in diagnostics)
    assert any("scope_collision.py:14" in item and "evonn-prism -> evonn-primordia" in item for item in diagnostics)
    assert not any(
        "scope_collision.py:4" in item or "scope_collision.py:8" in item or "scope_collision.py:16" in item
        for item in diagnostics
    )


def test_branch_merge_preserves_possible_dynamic_loader(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/branch_loader.py",
        '''import importlib
if flag:
    loader = importlib.import_module
else:
    loader = print
loader("topograph.runtime")
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "branch_loader.py:6" in diagnostics[0]
    assert "evonn-prism -> evonn-topograph" in diagnostics[0]


def test_try_and_loop_merges_preserve_feasible_loaders(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/try_loader.py",
        '''import importlib
try:
    loader = importlib.import_module
    risky()
except Exception:
    loader = print
loader("topograph.runtime")
''',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/loop_loader.py",
        '''import importlib
loader = importlib.import_module
for item in items:
    loader = print
loader("stratograph.runtime")
''',
    )
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/break_loader.py",
        '''import importlib
loader = print
for item in items:
    loader = importlib.import_module
    break
else:
    loader = print
loader("topograph.runtime")
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("try_loader.py:7" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("loop_loader.py:5" in item and "evonn-prism -> evonn-stratograph" in item for item in diagnostics)
    assert any("break_loader.py:8" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)


def test_function_call_uses_global_bindings_available_at_invocation(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/runtime_global.py",
        '''def load():
    provider.import_module("topograph.runtime")

import importlib as provider
load()
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "runtime_global.py:2" in diagnostics[0]
    assert "evonn-prism -> evonn-topograph" in diagnostics[0]


def test_function_call_uses_rebinding_before_invocation(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/runtime_rebind.py",
        '''import importlib as provider

def load():
    provider.import_module("topograph.runtime")

provider = print
load()
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert diagnostics == []


def test_function_global_and_nonlocal_rebindings_propagate_at_calls(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/function_rebinding.py",
        '''import importlib as provider

def global_load():
    global provider
    provider.import_module("topograph.runtime")
    provider = print

global_load()
provider.import_module("stratograph.runtime")

def outer():
    import importlib as nested_provider
    def nested_load():
        nonlocal nested_provider
        nested_provider.import_module("evonn_primordia.runtime")
        nested_provider = print
    nested_load()
    nested_provider.import_module("topograph.runtime")

outer()
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert any("function_rebinding.py:5" in item and "evonn-prism -> evonn-topograph" in item for item in diagnostics)
    assert any("function_rebinding.py:15" in item and "evonn-prism -> evonn-primordia" in item for item in diagnostics)
    assert not any("function_rebinding.py:9" in item or "function_rebinding.py:18" in item for item in diagnostics)


def test_nested_global_rebinding_propagates_through_outer_call(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/nested_global.py",
        '''import importlib as provider

def outer():
    def inner():
        global provider
        provider = print
    inner()

outer()
provider.import_module("topograph.runtime")
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert diagnostics == []


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
    script_diagnostic = next(item for item in diagnostics if "project.scripts.forbidden-script" in item)
    assert "evonn-prism -> evonn-topograph" in script_diagnostic
    assert f"pyproject.toml:{_line_number(manifest, 'forbidden-script =')}:" in script_diagnostic
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
    optional_diagnostic = next(item for item in diagnostics if "optional-dependencies.forbidden" in item)
    assert "evonn-prism -> evonn-topograph" in optional_diagnostic
    optional_line = _line_number(prism_manifest, 'forbidden = ["EvoNN.Topograph')
    assert f"pyproject.toml:{optional_line}:" in optional_diagnostic
    group_diagnostic = next(item for item in diagnostics if "dependency-groups.forbidden" in item)
    assert "evonn-prism -> evonn-contenders" in group_diagnostic
    group_line = _line_number(prism_manifest, 'forbidden = ["evonn-contenders')
    assert f"pyproject.toml:{group_line}:" in group_diagnostic
    assert sum("forbidden workspace source edge evonn-prism -> evonn-topograph" in item for item in diagnostics) == 2
    assert sum("workspace source 'orphan-helper'" in item and "no matching" in item for item in diagnostics) == 2


def test_internal_workspace_source_rejects_every_mixed_marker_alternative(
    validator, repository_copy: Path
) -> None:
    manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            'evonn-shared = { workspace = true }',
            '''evonn-shared = [
    { workspace = true, marker = "sys_platform == 'darwin'" },
    { path = "../EvoNN-Shared", marker = "sys_platform == 'linux'" },
    "malformed-alternative",
]''',
        ),
        encoding="utf-8",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    invalid = [item for item in diagnostics if "invalid workspace source alternative for 'evonn-shared'" in item]
    assert len(invalid) == 2
    assert "alternative 1" in invalid[0]
    assert "alternative 2" in invalid[1]
    assert f"pyproject.toml:{_line_number(manifest, '{ path =')}:" in invalid[0]
    assert f"pyproject.toml:{_line_number(manifest, 'malformed-alternative')}:" in invalid[1]


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


def test_workspace_manifest_symlink_fails_closed(validator, repository_copy: Path, tmp_path: Path) -> None:
    manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    external_manifest = tmp_path / "external-pyproject.toml"
    shutil.move(manifest, external_manifest)
    manifest.symlink_to(external_manifest)

    diagnostics = _diagnostics(validator, repository_copy)

    assert any(
        "EvoNN-Prism/pyproject.toml:1" in item and "workspace manifest must not be a symbolic link" in item
        for item in diagnostics
    )


def test_src_contains_exactly_one_expected_top_level_import_root(validator, repository_copy: Path) -> None:
    prism_src = repository_copy / "EvoNN-Prism/src"
    (prism_src / "topograph").mkdir()
    (prism_src / "topograph/__init__.py").write_text("", encoding="utf-8")
    (prism_src / "namespace_only").mkdir()
    (prism_src / "unexpected_module.py").write_text("VALUE = 1\n", encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    identity_errors = [item for item in diagnostics if "unexpected top-level src entry" in item]
    assert len(identity_errors) == 3
    assert any("EvoNN-Prism/src/topograph:1" in item for item in identity_errors)
    assert any("EvoNN-Prism/src/namespace_only:1" in item for item in identity_errors)
    assert any("EvoNN-Prism/src/unexpected_module.py:1" in item for item in identity_errors)


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
