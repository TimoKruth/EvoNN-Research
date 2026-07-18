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
        '''dependencies = [
    "evonn-shared",
    "numpy>=2.1,<3",
    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
]''',
        '''dependencies = [
    "evonn-shared",
    "numpy>=2.1,<3",
    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
    "evonn-topograph[fast]>=1 ; python_version >= '3.13'",
    "not-evonn-topograph-helper",
]''',
    )
    text += '\n[tool.uv.sources.evonn-topograph]\nworkspace = true\n\n[tool.uv.sources.orphan-helper]\nworkspace = true\n'
    manifest.write_text(text, encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("forbidden dependency edge evonn-prism -> evonn-topograph" in item for item in diagnostics)
    source_diagnostic = next(item for item in diagnostics if "workspace source edge evonn-prism -> evonn-topograph" in item)
    assert f"pyproject.toml:{_line_number(manifest, '[tool.uv.sources.evonn-topograph]')}:1:" in source_diagnostic
    assert any("workspace source 'orphan-helper'" in item and "no matching" in item for item in diagnostics)
    assert not any("not-evonn-topograph-helper" in item for item in diagnostics)


def test_project_dependency_entries_are_strings_and_group_includes_are_scoped(
    validator, repository_copy: Path
) -> None:
    manifest = repository_copy / "EvoNN-Prism/pyproject.toml"
    text = manifest.read_text(encoding="utf-8").replace(
        '''dependencies = [
    "evonn-shared",
    "numpy>=2.1,<3",
    "mlx>=0.25,<1; sys_platform == 'darwin' and platform_machine == 'arm64'",
]''',
        'dependencies = ["evonn-shared", { include-group = "base" }]',
    )
    text += '''
[project.optional-dependencies]
invalid = [{ include-group = "base" }]

[dependency-groups]
base = ["pytest"]
valid = [{ include-group = "base" }]
missing = [{ include-group = "absent" }]
invalid-entry = [{ include-group = 7 }]
broken = "not-a-list"
ref-broken = [{ include-group = "broken" }]
'''
    manifest.write_text(text, encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    project_line = _line_number(manifest, 'dependencies = ["evonn-shared",')
    optional_line = _line_number(manifest, "invalid =")
    missing_line = _line_number(manifest, "missing =")
    invalid_entry_line = _line_number(manifest, "invalid-entry =")
    broken_line = _line_number(manifest, "broken =")
    ref_broken_line = _line_number(manifest, "ref-broken =")
    assert any(
        f"pyproject.toml:{project_line}:1" in item
        and "project.dependencies dependency must be a PEP 508 string" in item
        for item in diagnostics
    )
    assert any(
        f"pyproject.toml:{optional_line}:1" in item
        and "project.optional-dependencies.invalid dependency must be a PEP 508 string" in item
        for item in diagnostics
    )
    assert any(
        f"pyproject.toml:{missing_line}:1" in item and "missing dependency group 'absent'" in item
        for item in diagnostics
    )
    assert any(
        f"pyproject.toml:{invalid_entry_line}:1" in item and "include-group must be a non-empty string" in item
        for item in diagnostics
    )
    assert any(
        f"pyproject.toml:{broken_line}:1" in item and "dependency-groups.broken must be a list" in item
        for item in diagnostics
    )
    assert any(
        f"pyproject.toml:{ref_broken_line}:1" in item and "invalid dependency group 'broken'" in item
        for item in diagnostics
    )
    assert not any("dependency-groups.valid" in item for item in diagnostics)


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
    assert f"pyproject.toml:{optional_line}:1:" in optional
    assert f"pyproject.toml:{group_line}:1:" in group
    assert f"pyproject.toml:{entry_line}:1:" in entry


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


@pytest.mark.parametrize(
    ("member", "relative_link"),
    [
        ("EvoNN-Primordia", "."),
        ("EvoNN-Topograph", "src"),
        ("EvoNN-Stratograph", "src/stratograph"),
    ],
)
def test_symlinked_package_source_subtrees_are_not_read(
    validator,
    repository_copy: Path,
    tmp_path: Path,
    member: str,
    relative_link: str,
) -> None:
    link = repository_copy / member
    if relative_link != ".":
        link /= relative_link
    external = tmp_path / f"external-{member}-{relative_link.replace('/', '-')}"
    shutil.move(link, external)
    link.symlink_to(external, target_is_directory=True)

    if relative_link == ".":
        injected = external / "src/evonn_primordia/external_content.py"
    elif relative_link == "src":
        injected = external / "topograph/external_content.py"
    else:
        injected = external / "external_content.py"
    injected.write_text("not valid Python !!!\n", encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("must not be a symbolic link" in item and member in item for item in diagnostics)
    assert not any("external_content.py" in item for item in diagnostics)


def test_shared_benchmarks_is_data_only(validator, repository_copy: Path) -> None:
    benchmarks = repository_copy / "shared-benchmarks"
    (benchmarks / "pyproject.toml").write_text("[project]\nname='runtime-bypass'\n", encoding="utf-8")
    (benchmarks / "catalog/__init__.py").write_text("", encoding="utf-8")
    (benchmarks / "runtime.py").write_text("print('runtime')\n", encoding="utf-8")
    (benchmarks / "tests/helper.py").write_text("HELPER = True\n", encoding="utf-8")

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("catalog/__init__.py:1:1" in item and "Python package marker" in item for item in diagnostics)
    assert any("pyproject.toml:1:1" in item and "Python package metadata" in item for item in diagnostics)
    assert any("runtime.py:1:1" in item and "runtime Python file" in item for item in diagnostics)
    assert not any("tests/helper.py" in item for item in diagnostics)


def test_shared_benchmark_root_symlink_stops_before_external_inspection(
    validator, repository_copy: Path, tmp_path: Path
) -> None:
    benchmarks = repository_copy / "shared-benchmarks"
    shutil.rmtree(benchmarks)
    external = tmp_path / "external-benchmarks"
    external.mkdir()
    (external / "runtime.py").write_text("eval('external')\n", encoding="utf-8")
    benchmarks.symlink_to(external, target_is_directory=True)

    diagnostics = _diagnostics(validator, repository_copy)
    benchmark_diagnostics = [item for item in diagnostics if "shared-benchmarks" in item]

    assert len(benchmark_diagnostics) == 1
    assert "shared-benchmarks:1:1" in benchmark_diagnostics[0]
    assert "symbolic link" in benchmark_diagnostics[0]
    assert "runtime.py" not in benchmark_diagnostics[0]
    assert not any("Required shared benchmark" in item for item in benchmark_diagnostics)


def test_shared_benchmark_policy_module_is_regular_and_parsed(
    validator, repository_copy: Path, tmp_path: Path
) -> None:
    module = repository_copy / "EvoNN-Shared/src/evonn_shared/benchmarks.py"
    external = tmp_path / "external-benchmarks.py"
    external.write_text("not valid Python !!!\n", encoding="utf-8")
    module.unlink()
    module.symlink_to(external)

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("benchmarks.py:1:1" in item and "must not be a symbolic link" in item for item in diagnostics)
    assert any("benchmarks.py:1:1" in item and "regular non-symlink" in item for item in diagnostics)
    assert not any("cannot parse production Python" in item and "benchmarks.py" in item for item in diagnostics)

    module.unlink()
    module.write_text("not valid Python !!!\n", encoding="utf-8")
    diagnostics = _diagnostics(validator, repository_copy)
    assert any("benchmarks.py:1:1" in item and "cannot parse production Python" in item for item in diagnostics)


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


def test_only_exact_runtime_probe_may_call_static_mlx_eval(
    validator, repository_copy: Path
) -> None:
    _append_script(repository_copy, "ci/runtime_probe.py", "import mlx.core as mx\nmx.eval(result)\n")
    _append_script(repository_copy, "ci/mlx_neighbor.py", "import mlx.core as mx\nmx.eval(result)\n")

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "mlx_neighbor.py" in diagnostics[0]
    assert "eval" in diagnostics[0]


def test_runtime_probe_mlx_exception_does_not_allow_python_eval(
    validator, repository_copy: Path
) -> None:
    _append_script(
        repository_copy,
        "ci/runtime_probe.py",
        "import mlx.core as mx\nmx.eval(result)\neval('1 + 1')\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "runtime_probe.py:3" in diagnostics[0]
    assert "eval" in diagnostics[0]


def test_builtin_namespace_dunder_import_is_banned_before_computed_key_use(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/builtin_namespace_import.py",
        '''from builtins import __dict__ as namespace
key = "__" + "import__"
loader = namespace[key]
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "builtin_namespace_import.py:1:1" in diagnostics[0]
    assert "__dict__" in diagnostics[0]


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


@pytest.mark.parametrize(
    ("source", "primitive"),
    [
        ('from builtins import getattr as reflect\nreflect(container, "import_module")\n', "getattr"),
        ('from builtins import hasattr as reflect\n', "hasattr"),
        ('from builtins import setattr as reflect\n', "setattr"),
        ('from builtins import delattr as reflect\n', "delattr"),
        ('reflect = getattr\nreflect(container, "import_module")\n', "getattr"),
        ('consume(hasattr)\n', "hasattr"),
        ('from operator import attrgetter as acquire\nacquire("run_module")\n', "attrgetter"),
        ('from operator import methodcaller\n', "methodcaller"),
        ('from operator import *\n', "operator"),
        ('import operator\nacquire = operator.attrgetter\n', "attrgetter"),
    ],
)
def test_reflection_primitive_acquisition_is_strictly_banned(
    validator, repository_copy: Path, source: str, primitive: str
) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/reflection_alias.py", source)

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "reflection_alias.py" in diagnostics[0]
    assert primitive in diagnostics[0]


@pytest.mark.parametrize(
    ("source", "primitive"),
    [
        ("from operator import getitem as lookup\n", "getitem"),
        ("from operator import itemgetter as lookup\n", "itemgetter"),
        ("import operator\nlookup = operator.getitem\n", "getitem"),
        ("import operator\nlookup = operator.itemgetter\n", "itemgetter"),
        ("from helpers import exec_module as run\n", "exec_module"),
        ("from helpers import load_module as run\n", "load_module"),
    ],
)
def test_reserved_primitive_imports_and_operator_acquisition_are_banned(
    validator, repository_copy: Path, source: str, primitive: str
) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/reserved_import.py", source)

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "reserved_import.py:" in diagnostics[0]
    assert primitive in diagnostics[0]


@pytest.mark.parametrize(
    ("receiver", "helper"),
    [("globals()", "getattr"), ("__builtins__", "hasattr"), ("container", "setattr"), ("helpers", "delattr")],
)
def test_subscript_reflection_helper_acquisition_is_strictly_banned(
    validator, repository_copy: Path, receiver: str, helper: str
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/reflection_subscript.py",
        f'helper = {receiver}["{helper}"]\n',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    expected_count = 2 if receiver in {"__builtins__", "globals()"} else 1
    assert len(diagnostics) == expected_count
    assert all("reflection_subscript.py:1" in item for item in diagnostics)
    assert any(helper in item for item in diagnostics)
    if receiver == "__builtins__":
        assert any("namespace primitive reference: __builtins__" in item for item in diagnostics)


@pytest.mark.parametrize("helper", ["getattr", "hasattr", "setattr", "delattr"])
def test_direct_reflection_requires_literal_safe_attribute_name(
    validator, repository_copy: Path, helper: str
) -> None:
    required_tail = ", value" if helper == "setattr" else ""
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/computed_reflection.py",
        f'name = "import_module"\n{helper}(container, name{required_tail})\n',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "computed_reflection.py:2" in diagnostics[0]
    assert helper in diagnostics[0]
    assert "literal safe attribute-name" in diagnostics[0]


def test_direct_reflection_rejects_unknown_parameter_name(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/parameter_reflection.py",
        "def read(name):\n    return getattr(container, name)\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "parameter_reflection.py:2" in diagnostics[0]
    assert "getattr" in diagnostics[0]
    assert "literal safe attribute-name" in diagnostics[0]


@pytest.mark.parametrize(
    ("source", "primitive"),
    [
        ("value = module.getattr\n", "getattr"),
        ("value = module.hasattr\n", "hasattr"),
        ("value = module.setattr\n", "setattr"),
        ("value = module.delattr\n", "delattr"),
        ("value = module.__builtins__\n", "__builtins__"),
        ('value = globals()["__builtins__"]\n', "__builtins__"),
        ('value = getattr(module, "__builtins__")\n', "__builtins__"),
    ],
)
def test_namespace_and_reflection_attribute_acquisition_is_banned(
    validator, repository_copy: Path, source: str, primitive: str
) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/namespace_attribute.py", source)

    diagnostics = _diagnostics(validator, repository_copy)

    expected_count = 2 if "globals()" in source else 1
    assert len(diagnostics) == expected_count
    assert all("namespace_attribute.py:1:" in item for item in diagnostics)
    assert any(primitive in item for item in diagnostics)


def test_namespace_getattribute_and_class_reflection_are_banned(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/namespace_dunders.py",
        '''import importlib.metadata
plugins = importlib.metadata.__getattribute__("entry_points")()
plugin_class = plugins[0].__class__
loader = plugins[0].__getattribute__("load")
namespace = importlib.metadata.__dict__
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 4
    assert any("namespace_dunders.py:2:11" in item and "__getattribute__" in item for item in diagnostics)
    assert any("namespace_dunders.py:3:16" in item and "__class__" in item for item in diagnostics)
    assert any("namespace_dunders.py:4:10" in item and "__getattribute__" in item for item in diagnostics)
    assert any("namespace_dunders.py:5:13" in item and "__dict__" in item for item in diagnostics)


@pytest.mark.parametrize("primitive", ["globals", "locals", "vars"])
def test_namespace_reflection_primitive_names_are_banned(
    validator, repository_copy: Path, primitive: str
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/namespace_primitive.py",
        f"namespace = {primitive}()\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "namespace_primitive.py:1:13" in diagnostics[0]
    assert primitive in diagnostics[0]


@pytest.mark.parametrize(
    ("method", "key"),
    [
        ("get", "__builtins__"),
        ("__getitem__", "__import__"),
        ("setdefault", "eval"),
        ("pop", "import_module"),
        ("get", "hasattr"),
    ],
)
def test_mapping_lookup_methods_reject_literal_dangerous_acquisition_keys(
    validator, repository_copy: Path, method: str, key: str
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/mapping_lookup.py",
        f'mapping.{method}("{key}")\n',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "mapping_lookup.py:1:1" in diagnostics[0]
    assert method in diagnostics[0]
    assert key in diagnostics[0]


@pytest.mark.parametrize(
    ("source", "primitive"),
    [
        ('lookup = dict.get\nlookup(mapping, "__builtins__")\n', "get"),
        ('lookup = dict.__getitem__\nlookup(mapping, "__import__")\n', "__getitem__"),
        ('lookup = object.__getattribute__\nlookup(plugin, "load")\n', "__getattribute__"),
    ],
)
def test_unbound_namespace_lookup_apis_are_banned(
    validator, repository_copy: Path, source: str, primitive: str
) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/unbound_lookup.py", source)

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "unbound_lookup.py:1:10" in diagnostics[0]
    assert primitive in diagnostics[0]


def test_namespace_mapping_lookup_chain_is_banned(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/namespace_mapping.py",
        '''namespace = globals().get("__builtins__")
loader = namespace.get("__import__")
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("namespace_mapping.py:1:13" in item and "globals" in item for item in diagnostics)
    assert any("namespace_mapping.py:1:13" in item and "__builtins__" in item for item in diagnostics)
    assert any("namespace_mapping.py:2:10" in item and "__import__" in item for item in diagnostics)


@pytest.mark.parametrize(
    "source",
    [
        'mapping.get(key="__builtins__")\n',
        'mapping.__getitem__(key="__import__")\n',
        'mapping.setdefault(key="eval", default=value)\n',
        'mapping.pop(key="import_module")\n',
        'mapping.get(*("__builtins__",))\n',
        'mapping.pop(*( "__import__", default))\n',
        'mapping.get(name)\n',
        'mapping.__getitem__(*keys)\n',
        'mapping.setdefault()\n',
        'mapping.pop("safe_name", default=value)\n',
    ],
)
def test_mapping_lookup_call_forms_fail_closed_unless_key_is_literal_and_safe(
    validator, repository_copy: Path, source: str
) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/mapping_call_form.py", source)

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "mapping_call_form.py:1:1" in diagnostics[0]
    assert "mapping" in diagnostics[0]


def test_benign_mapping_lookup_remains_allowed(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/benign_mapping.py",
        '''value = mapping.get("safe_name")
value = mapping.__getitem__("safe_name")
value = mapping.setdefault("safe_name", default)
value = mapping.pop("safe_name")
value = mapping.get(*("safe_name",))
''',
    )

    assert _diagnostics(validator, repository_copy) == []


def test_benign_direct_reflection_calls_remain_allowed(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/benign_reflection.py",
        '''value = getattr(container, "safe_name")
exists = hasattr(container, "safe_name")
setattr(container, "safe_name", value)
delattr(container, "safe_name")
''',
    )

    assert _diagnostics(validator, repository_copy) == []


def test_builtins_namespace_is_forbidden_in_package_and_shipped_script(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/builtins_namespace.py",
        "loader = __builtins__.get('__import__')\n",
    )
    _append_script(repository_copy, "tools/builtins_namespace.py", "namespace = __builtins__.__dict__\n")

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 4
    assert sum("prism/builtins_namespace.py:1" in item for item in diagnostics) == 2
    assert any("mapping get" in item and "__import__" in item for item in diagnostics)
    assert sum("scripts/tools/builtins_namespace.py:1" in item for item in diagnostics) == 2
    assert any("__builtins__" in item for item in diagnostics)
    assert any("__dict__" in item for item in diagnostics)


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

    assert len(diagnostics) == 2
    assert any("wrapper.py:1" in item and "importlib" in item for item in diagnostics)
    assert any("wrapper.py:2" in item and "import_module" in item for item in diagnostics)


def test_provider_import_does_not_suppress_independent_later_violations(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/multiple_primitives.py",
        '''import importlib
from operator import attrgetter
getattr(container, "run_module")
eval("1 + 1")
loader = importlib.import_module
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert diagnostics == sorted(diagnostics)
    assert len(diagnostics) == 6
    assert any("multiple_primitives.py:1:1" in item and "importlib" in item for item in diagnostics)
    assert any("multiple_primitives.py:2:1" in item and "attrgetter" in item for item in diagnostics)
    assert any("multiple_primitives.py:3:1" in item and "run_module" in item for item in diagnostics)
    assert any("multiple_primitives.py:4:1" in item and "eval" in item for item in diagnostics)
    assert any("multiple_primitives.py:5:10" in item and "import_module" in item for item in diagnostics)
    assert any(
        "multiple_primitives.py:5:10" in item and "primitive reference: importlib" in item
        for item in diagnostics
    )


def test_importlib_submodules_other_than_metadata_and_exec_module_are_banned(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/importlib_util.py",
        '''import importlib.util
spec = importlib.util.spec_from_file_location("module", path)
spec.loader.exec_module(module)
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("importlib_util.py:1:1" in item and "importlib.util" in item for item in diagnostics)
    assert any("importlib_util.py:2:8" in item and "importlib" in item for item in diagnostics)
    assert any("importlib_util.py:3:1" in item and "exec_module" in item for item in diagnostics)


def test_same_line_primitive_diagnostics_preserve_ast_columns(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/same_line.py",
        "eval('1'); eval('2')\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert any("same_line.py:1:1" in item for item in diagnostics)
    assert any("same_line.py:1:12" in item for item in diagnostics)


def test_nested_repeated_same_start_acquisitions_keep_distinct_identity(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/nested_same_start.py",
        "value = module.exec_module.exec_module\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert len(set(diagnostics)) == 2
    assert all("nested_same_start.py:1:9-" in item and "exec_module" in item for item in diagnostics)


def test_same_line_diagnostic_columns_use_unicode_code_points(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/unicode_columns.py",
        "π = 0; eval('x'); eval('y')\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 2
    assert any("unicode_columns.py:1:8" in item for item in diagnostics)
    assert any("unicode_columns.py:1:19" in item for item in diagnostics)


def test_safe_specific_and_optional_static_imports_remain_allowed(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/safe_imports.py",
        '''import importlib.metadata
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


@pytest.mark.parametrize(
    "primitive",
    [
        "import_module",
        "runpy",
        "run_module",
        "builtins",
        "attrgetter",
        "methodcaller",
        "exec_module",
        "load_module",
        "__loader__",
        "__spec__",
        "importlib",
    ],
)
def test_bare_dynamic_and_reflection_primitive_names_are_banned(
    validator, repository_copy: Path, primitive: str
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/bare_primitive.py",
        f"provider = {primitive}\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "bare_primitive.py:1:12" in diagnostics[0]
    assert primitive in diagnostics[0]


@pytest.mark.parametrize(
    "source",
    [
        "import importlib.metadata as md\n",
        "from importlib import metadata\n",
        "from importlib import metadata as md\n",
        "metadata_module = importlib.metadata\n",
    ],
)
def test_importlib_metadata_module_alias_or_acquisition_is_banned(
    validator, repository_copy: Path, source: str
) -> None:
    _append_source(repository_copy, "EvoNN-Prism", "prism/metadata_alias.py", source)

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "metadata_alias.py:1:" in diagnostics[0]
    assert "metadata" in diagnostics[0]


def test_importlib_metadata_attribute_chain_remains_allowed(validator, repository_copy: Path) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/metadata_chain.py",
        '''import importlib.metadata
version = importlib.metadata.version("example")
''',
    )

    assert _diagnostics(validator, repository_copy) == []


@pytest.mark.parametrize(
    ("expression", "primitives"),
    [
        ("importlib.metadata.exec_module.safe", ("exec_module",)),
        ("importlib.metadata.__builtins__.safe", ("__builtins__",)),
        ("importlib.metadata.__loader__.exec_module", ("__loader__", "exec_module")),
        ("importlib.metadata.__builtins__.__import__", ("__builtins__", "__import__")),
    ],
)
def test_importlib_metadata_prefix_does_not_hide_forbidden_outer_attributes(
    validator, repository_copy: Path, expression: str, primitives: tuple[str, ...]
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/metadata_outer_attribute.py",
        f"import importlib.metadata\nvalue = {expression}\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == len(primitives)
    assert all("metadata_outer_attribute.py:2:9" in item for item in diagnostics)
    for primitive in primitives:
        assert any(primitive in item for item in diagnostics)


def test_importlib_metadata_plugin_acquisition_is_banned(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/metadata_plugins.py",
        '''from importlib.metadata import entry_points
plugin = importlib.metadata.entry_points(group="example")[0].load()
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("metadata_plugins.py:1:1" in item and "entry_points" in item for item in diagnostics)
    assert any("metadata_plugins.py:2:10" in item and "entry_points" in item for item in diagnostics)
    assert any("metadata_plugins.py:2:10" in item and "load" in item for item in diagnostics)


def test_importlib_metadata_loader_and_spec_acquisition_are_banned(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/metadata_loader.py",
        '''import importlib.metadata
loader = importlib.metadata.__loader__
loader.load_module("module")
spec = importlib.metadata.__spec__
''',
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 3
    assert any("metadata_loader.py:2:10" in item and "__loader__" in item for item in diagnostics)
    assert any("metadata_loader.py:3:1" in item and "load_module" in item for item in diagnostics)
    assert any("metadata_loader.py:4:8" in item and "__spec__" in item for item in diagnostics)


def test_importlib_metadata_import_does_not_allow_bare_importlib_name(
    validator, repository_copy: Path
) -> None:
    _append_source(
        repository_copy,
        "EvoNN-Prism",
        "prism/metadata_provider.py",
        "import importlib.metadata\nprovider = importlib\n",
    )

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 1
    assert "metadata_provider.py:2:12" in diagnostics[0]
    assert "importlib" in diagnostics[0]


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

    assert len(diagnostics) == 2
    assert all("specific_then_dynamic.py:2:10" in item for item in diagnostics)
    assert any("primitive reference: importlib" in item for item in diagnostics)
    assert any("attribute acquisition: import_module" in item for item in diagnostics)


def test_only_exact_policy_and_runtime_scripts_may_import_workspace_packages(
    validator, repository_copy: Path
) -> None:
    _append_script(repository_copy, "tools/forbidden_shared.py", "import evonn_shared\n")
    _append_script(repository_copy, "policy/neighbor.py", "from evonn_shared import benchmarks\n")
    _append_script(repository_copy, "tools/forbidden_engine.py", "import prism\n")
    _append_script(repository_copy, "tools/forbidden_compare.py", "from evonn_compare import runner\n")
    _append_script(
        repository_copy,
        "ci/runtime_probe.py",
        "import evonn_compare\nimport evonn_contenders\nimport evonn_primordia\nimport evonn_shared\n"
        "import prism\nimport stratograph\nimport topograph\n",
    )
    _append_script(repository_copy, "policy/validate_backend_capabilities.py", "import evonn_shared\n")

    diagnostics = _diagnostics(validator, repository_copy)

    assert len(diagnostics) == 4
    assert any("forbidden_shared.py:1:1" in item and "repository-scripts -> evonn-shared" in item for item in diagnostics)
    assert any("neighbor.py:1:1" in item and "repository-scripts -> evonn-shared" in item for item in diagnostics)
    assert any("forbidden_engine.py:1:1" in item and "repository-scripts -> evonn-prism" in item for item in diagnostics)
    assert any("forbidden_compare.py:1:1" in item and "repository-scripts -> evonn-compare" in item for item in diagnostics)
    assert not any(
        path in item
        for item in diagnostics
        for path in (
            "scripts/policy/validate_import_boundaries.py",
            "scripts/policy/validate_backend_capabilities.py",
            "scripts/ci/runtime_probe.py",
        )
    )


def test_scripts_topology_rejects_symlinked_files_and_directories(
    validator, repository_copy: Path, tmp_path: Path
) -> None:
    external_directory = tmp_path / "external-tools"
    external_directory.mkdir()
    (external_directory / "eval_bypass.py").write_text("eval('1 + 1')\n", encoding="utf-8")
    (repository_copy / "scripts/linked-tools").symlink_to(external_directory, target_is_directory=True)

    external_python = tmp_path / "external-script.py"
    external_python.write_text("import runpy\n", encoding="utf-8")
    (repository_copy / "scripts/linked.py").symlink_to(external_python)

    diagnostics = _diagnostics(validator, repository_copy)

    topology = [item for item in diagnostics if "shipped scripts path must not be a symbolic link" in item]
    assert len(topology) == 2
    assert topology == sorted(topology)
    assert any("scripts/linked-tools:1:1" in item for item in topology)
    assert any("scripts/linked.py:1:1" in item for item in topology)
    assert not any("eval_bypass.py" in item or "external-script.py" in item for item in diagnostics)


def test_checked_in_scripts_topology_has_no_symlinks(validator) -> None:
    assert not any(
        "shipped scripts path must not be a symbolic link" in item
        for item in _diagnostics(validator, REPO_ROOT)
    )


def test_production_scope_scans_validator_and_neighboring_path_variants(
    validator, repository_copy: Path
) -> None:
    copied_validator = repository_copy / "scripts/policy/validate_import_boundaries.py"
    assert copied_validator.is_file()
    assert _diagnostics(validator, repository_copy) == []

    copied_validator.write_text(
        copied_validator.read_text(encoding="utf-8") + "\neval('1 + 1')\n",
        encoding="utf-8",
    )
    _append_script(repository_copy, "tools/forbidden.py", "import runpy\n")
    _append_script(repository_copy, "policy/not_the_validator.py", "import importlib\n")
    _append_script(repository_copy, "policy/nested/validate_import_boundaries.py", "import builtins\n")

    diagnostics = _diagnostics(validator, repository_copy)

    assert any("scripts/policy/validate_import_boundaries.py" in item and "eval" in item for item in diagnostics)
    assert any("scripts/tools/forbidden.py:1" in item and "runpy" in item for item in diagnostics)
    assert any("scripts/policy/not_the_validator.py:1" in item and "importlib" in item for item in diagnostics)
    assert any("scripts/policy/nested/validate_import_boundaries.py:1" in item and "builtins" in item for item in diagnostics)


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
