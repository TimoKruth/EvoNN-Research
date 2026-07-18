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
    shutil.copytree(
        REPO_ROOT / "scripts",
        root / "scripts",
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


def _append_script(root: Path, relative: str, source: str) -> Path:
    path = root / "scripts" / relative
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

    assert first == second == sorted(first)
    assert len(first) == 2
    assert "a_violation.py:1" in first[0] and "evonn-prism -> evonn-stratograph" in first[0]
    assert "z_violation.py:1" in first[1] and "evonn-prism -> evonn-topograph" in first[1]


def test_shared_does_not_import_system_packages(validator, repository_copy: Path) -> None:
    _append_source(repository_copy, "EvoNN-Shared", "evonn_shared/compare.py", "import evonn_compare\n")
    _append_source(repository_copy, "EvoNN-Shared", "evonn_shared/engine.py", "from prism import runtime\n")

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert any("evonn-shared -> evonn-compare" in item for item in diagnostics)
    assert any("evonn-shared -> evonn-prism" in item for item in diagnostics)


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
    manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    text = manifest.read_text(encoding="utf-8")
    text = text.replace(
        'dependencies = ["evonn-shared"]',
        'dependencies = [\n    "evonn-shared",\n    "evonn-topograph[fast]>=1 ; python_version >= \'3.13\'",\n    "not-evonn-topograph-helper",\n]',
    )
    text += '\n[tool.uv.sources.evonn-topograph]\nworkspace = true\n\n[tool.uv.sources.orphan-helper]\nworkspace = true\n'
    manifest.write_text(text, encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("forbidden dependency edge evonn-prism -> evonn-topograph" in item for item in diagnostics)
    source_diagnostic = next(item for item in diagnostics if "workspace source edge evonn-prism -> evonn-topograph" in item)
    assert f"pyproject.toml:{_line_number(manifest, '[tool.uv.sources.evonn-topograph]')}:" in source_diagnostic
    assert any("workspace source 'orphan-helper'" in item and "no matching" in item for item in diagnostics)
    assert not any("not-evonn-topograph-helper" in item for item in diagnostics)


def test_optional_group_entry_point_and_source_alternatives_are_validated(validator, repository_copy: Path) -> None:
    manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    text = manifest.read_text(encoding="utf-8").replace(
        'evonn-shared = { workspace = true }',
        '''evonn-shared = [
    { workspace = true, marker = "sys_platform == 'darwin'" },
    { path = "../EvoNN-Shared", marker = "sys_platform == 'linux'" },
]''',
    )
    text += '''
[project.optional-dependencies]
forbidden = ["EvoNN.Topograph>=1"]

[dependency-groups]
forbidden = ["evonn-contenders"]

[project.scripts]
forbidden-script = "evonn_primordia.cli:main"
'''
    manifest.write_text(text, encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("invalid workspace source alternative for 'evonn-shared' alternative 1" in item for item in diagnostics)
    optional = next(item for item in diagnostics if "optional-dependencies.forbidden" in item)
    group = next(item for item in diagnostics if "dependency-groups.forbidden" in item)
    entry = next(item for item in diagnostics if "project.scripts.forbidden-script" in item)
    optional_line = _line_number(manifest, 'forbidden = ["EvoNN.Topograph')
    group_line = _line_number(manifest, 'forbidden = ["evonn-contenders')
    entry_line = _line_number(manifest, "forbidden-script =")
    assert f"pyproject.toml:{optional_line}:" in optional
    assert f"pyproject.toml:{group_line}:" in group
    assert f"pyproject.toml:{entry_line}:" in entry


def test_workspace_topology_and_import_identities_are_exact(validator, repository_copy: Path) -> None:
    root_manifest = repository_copy / "pyproject.toml"
    root_manifest.write_text(
        root_manifest.read_text(encoding="utf-8").replace(
            '    "EvoNN-Primordia",\n',
            '    "EvoNN-Prism",\n    "Unexpected-Package",\n',
        ),
        encoding="utf-8",
    )
    prism_src = repository_copy / "EvoNN-Prism/src"
    (prism_src / "topograph").mkdir()
    (prism_src / "topograph/__init__.py").write_text("", encoding="utf-8")
    (prism_src / "unexpected.py").write_text("VALUE = 1\n", encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("duplicate workspace member: EvoNN-Prism" in item for item in diagnostics)
    assert any("missing workspace member: EvoNN-Primordia" in item for item in diagnostics)
    assert any("extra workspace member: Unexpected-Package" in item for item in diagnostics)
    assert sum("unexpected top-level src entry" in item for item in diagnostics) == 2


def test_workspace_and_manifest_symlinks_fail_closed(validator, repository_copy: Path, tmp_path: Path) -> None:
    manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    external_manifest = tmp_path / "external.toml"
    shutil.move(manifest, external_manifest)
    manifest.symlink_to(external_manifest)
    linked = repository_copy / "EvoNN-Compare/src/evonn_compare/linked.py"
    external_python = tmp_path / "external.py"
    external_python.write_text("import topograph\n", encoding="utf-8")
    linked.symlink_to(external_python)

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("workspace manifest must not be a symbolic link" in item for item in diagnostics)
    assert any("linked.py:1" in item and "production source path must not be a symbolic link" in item for item in diagnostics)


def test_shared_benchmarks_is_data_only(validator, repository_copy: Path) -> None:
    benchmarks = repository_copy / "shared-benchmarks"
    (benchmarks / "pyproject.toml").write_text("[project]\nname='runtime-bypass'\n", encoding="utf-8")
    (benchmarks / "catalog/__init__.py").write_text("", encoding="utf-8")
    (benchmarks / "runtime.py").write_text("print('runtime')\n", encoding="utf-8")
    (benchmarks / "tests/helper.py").write_text("HELPER = True\n", encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("catalog/__init__.py:1" in item and "Python package marker" in item for item in diagnostics)
    assert any("pyproject.toml:1" in item and "Python package metadata" in item for item in diagnostics)
    assert any("runtime.py:1" in item and "runtime Python file" in item for item in diagnostics)
    assert not any("tests/helper.py" in item for item in diagnostics)


@pytest.mark.parametrize(
    ("source", "primitive"),
    [
        ("import importlib\n", "importlib"),
        ("import importlib as provider\n", "importlib"),
        ("from importlib import import_module\n", "import_module"),
        ("from importlib import import_module as loader\n", "import_module"),
        ("from importlib import *\n", "importlib"),
        ("import runpy\n", "runpy"),
        ("import runpy as provider\n", "runpy"),
        ("from runpy import run_module\n", "run_module"),
        ("from runpy import run_module as loader\n", "run_module"),
        ("from runpy import *\n", "runpy"),
        ("import builtins\n", "builtins"),
        ("import builtins as provider\n", "builtins"),
        ("from builtins import __import__\n", "__import__"),
        ("from builtins import __import__ as loader\n", "__import__"),
        ("from builtins import *\n", "builtins"),
    ],
)
def test_dynamic_loading_provider_imports_are_strictly_banned(
    validator, repository_copy: Path, source: str, primitive: str
) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/provider.py", source)

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "provider.py:1" in diagnostics[0]
    assert "dynamic-loading primitive" in diagnostics[0]
    assert primitive in diagnostics[0]


@pytest.mark.parametrize(
    ("source", "primitive"),
    [
        ('__import__("topograph")\n', "__import__"),
        ('loader = __import__\nloader("topograph")\n', "__import__"),
        ('exec("import topograph")\n', "exec"),
        ('runner = exec\nrunner("import topograph")\n', "exec"),
        ('eval("__import__(\\"topograph\\")")\n', "eval"),
        ('runner = eval\nrunner("1 + 1")\n', "eval"),
        ('getattr(container, "import_module")\n', "import_module"),
        ('hasattr(container, "run_module")\n', "run_module"),
        ('setattr(container, "__import__", value)\n', "__import__"),
        ('delattr(container, "import_module")\n', "import_module"),
        ('container["import_module"]\n', "import_module"),
    ],
)
def test_dynamic_execution_and_explicit_reflection_are_strictly_banned(
    validator, repository_copy: Path, source: str, primitive: str
) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/reflection.py", source)

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "reflection.py:1" in diagnostics[0]
    assert primitive in diagnostics[0]


def test_wrappers_containers_and_control_flow_are_blocked_at_primitive_acquisition(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/wrapper.py",
        '''import importlib as provider
container = {"loader": provider.import_module}
if enabled:
    selected = container["loader"]
else:
    selected = print
selected("topograph.runtime")
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "wrapper.py:1" in diagnostics[0]
    assert "importlib" in diagnostics[0]


def test_safe_specific_and_optional_static_imports_remain_allowed(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/safe_imports.py",
        '''import importlib.metadata
import importlib.metadata as metadata_api
from importlib import metadata
from importlib.metadata import version
from runpy import run_path
from builtins import len as builtin_len
import json
from pathlib import Path
try:
    import mlx
except ImportError:
    mlx = None
''',
    )

    assert _diagnostics(validator, repository_copy) == []


def test_safe_specific_import_does_not_enable_dynamic_primitive_use(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/specific_then_dynamic.py",
        '''import importlib.metadata
loader = importlib.import_module
loader("topograph.runtime")
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "specific_then_dynamic.py:2" in diagnostics[0]
    assert "import_module" in diagnostics[0]


def test_production_scope_includes_shipped_scripts_with_exact_validator_allowlist(
    validator, repository_copy: Path
) -> None:
    _append_script(repository_copy, "tools/forbidden.py", "import runpy\n")
    _append_script(repository_copy, "policy/not_the_validator.py", "import importlib\n")
    copied_validator = repository_copy / "scripts/policy/validate_import_boundaries.py"
    assert copied_validator.is_file()

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("scripts/tools/forbidden.py:1" in item and "runpy" in item for item in diagnostics)
    assert any("scripts/policy/not_the_validator.py:1" in item and "importlib" in item for item in diagnostics)
    assert not any("scripts/policy/validate_import_boundaries.py" in item for item in diagnostics)


def test_test_trees_are_exempt_but_similarly_named_production_paths_are_not(
    validator, repository_copy: Path
) -> None:
    package_test = repository_copy / "EvoNN-Prism/tests/test_dynamic.py"
    package_test.parent.mkdir()
    package_test.write_text("import importlib\n", encoding="utf-8")
    root_test = repository_copy / "tests/test_dynamic.py"
    root_test.parent.mkdir()
    root_test.write_text("import runpy\n", encoding="utf-8")
    _append_source(repository_copy, "EvoNN-Prism", "prism/tests_like.py", "import builtins\n")

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "prism/tests_like.py:1" in diagnostics[0]
    assert not any("tests/test_dynamic.py" in item for item in diagnostics)


def test_research_log_records_abandoned_interpreter_as_non_authoritative() -> None:
    path = REPO_ROOT / "research/logs/2026-07-18-dynamic-import-policy.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "document_kind: research_log" in text
    assert "status: completed" in text
    assert "authoritative: false" in text
    assert "strict primitive prohibition" in text
    assert "document_kind: execution_plan" not in text


def test_validator_cli_reports_all_violations_and_runs_from_another_directory(
    validator, repository_copy: Path, tmp_path: Path
) -> None:
    _append_source(repository_copy, "EvoNN-Compare", "evonn_compare/b.py", "import prism\n")
    _append_script(repository_copy, "tool.py", "eval('1 + 1')\n")

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
    assert "eval" in result.stdout


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
