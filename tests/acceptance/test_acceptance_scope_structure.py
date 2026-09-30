import ast
import os
import re
from pathlib import Path

PROGRAM_ROOT = Path(__file__).resolve().parents[2]
SEQUENCE_DIRS = ("fid", "cal_pulse", "cpmg")
SEQUENCE_FILES = ("logic.py", "ui.py", "layout.ui", "config.ini")
PROGRAM_PY_DIRS = (".", "common", "app", "sequences")
ASTYLE_EXCLUDE = ("tasks", ".pytest_cache", "__pycache__", ".ruff_cache")
FIXTURE_DEF = re.compile(r"pytest\.fixtur[e]")


def all_program_python_files():
    found = set()
    for directory in PROGRAM_PY_DIRS:
        for path in (PROGRAM_ROOT / directory).glob("**/*.py"):
            if not any(part in ASTYLE_EXCLUDE for part in path.parts):
                found.add(str(path))
    return sorted(found)


def all_python_files():
    found = set(all_program_python_files())
    for path in (PROGRAM_ROOT / "tests").glob("**/*.py"):
        if not any(part in ASTYLE_EXCLUDE for part in path.parts):
            found.add(str(path))
    return sorted(found)


def import_modules(tree):
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    return modules


def test_acceptance_scope_in_scope_sequences():
    for name in SEQUENCE_DIRS:
        for file_name in SEQUENCE_FILES + ("__init__.py",):
            assert (PROGRAM_ROOT / "sequences" / name / file_name).is_file()
    sequence_dirs = set()
    for path in (PROGRAM_ROOT / "sequences").iterdir():
        if path.is_dir() and all((path / file_name).is_file() for file_name in SEQUENCE_FILES):
            sequence_dirs.add(path.name)
    assert sequence_dirs == set(SEQUENCE_DIRS)
    for directory in PROGRAM_PY_DIRS:
        base = PROGRAM_ROOT / directory
        patterns = ("*.py", "*.ui", "*.ini") if directory == "." else ("**/*.py", "**/*.ui", "**/*.ini")
        for pattern in patterns:
            for path in base.glob(pattern):
                if any(part in ASTYLE_EXCLUDE for part in path.parts):
                    continue


def test_acceptance_modularity_logic_ui_split():
    for name in SEQUENCE_DIRS:
        logic_tree = ast.parse((PROGRAM_ROOT / "sequences" / name / "logic.py").read_text())
        for module in import_modules(logic_tree):
            root = module.split(".")[0]
            assert not root.startswith("PySide6") and not root.startswith("PyQt")
        assert any(
            node.module == "common.sequence_logic" for node in ast.walk(logic_tree) if isinstance(node, ast.ImportFrom)
        )
        ui_tree = ast.parse((PROGRAM_ROOT / "sequences" / name / "ui.py").read_text())
        assert any(
            node.module == "sequences." + name + ".logic"
            for node in ast.walk(ui_tree)
            if isinstance(node, ast.ImportFrom)
        )
        assert any(
            node.module == "common.sequence_ui" for node in ast.walk(ui_tree) if isinstance(node, ast.ImportFrom)
        )


def test_acceptance_qt_binding_pyside6_only():
    qt_modules = set()
    for name in all_python_files():
        tree = ast.parse(Path(name).read_text())
        for node in ast.walk(tree):
            for module in import_modules_from(node):
                root = module.split(".")[0]
                if root.startswith(("PySide6", "PyQt")):
                    qt_modules.add(root)
            if isinstance(node, ast.Try):
                bodies = list(node.body) + list(node.orelse)
                for handler in node.handlers:
                    bodies.extend(handler.body)
                for body in bodies:
                    for child in ast.walk(body):
                        for module in import_modules_from(child):
                            root = module.split(".")[0]
                            assert not (root.startswith(("PySide6", "PyQt")))
    assert qt_modules <= {"PySide6"}


def import_modules_from(node):
    modules = []
    if isinstance(node, ast.Import):
        modules.extend(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        modules.append(node.module or "")
    return modules


def test_acceptance_reuse_shared_infrastructure():
    for name in SEQUENCE_DIRS:
        logic_tree = ast.parse((PROGRAM_ROOT / "sequences" / name / "logic.py").read_text())
        assert any(
            node.module == "common.sequence_logic" for node in ast.walk(logic_tree) if isinstance(node, ast.ImportFrom)
        )
        ui_tree = ast.parse((PROGRAM_ROOT / "sequences" / name / "ui.py").read_text())
        ui_modules = {node.module for node in ast.walk(ui_tree) if isinstance(node, ast.ImportFrom)}
        assert "common.sequence_ui" in ui_modules
        py_files = {path.name for path in (PROGRAM_ROOT / "sequences" / name).glob("*.py")}
        assert py_files == {"__init__.py", "logic.py", "ui.py"}
    for entry in ("app/main_window.py", "app/cli_app.py"):
        tree = ast.parse((PROGRAM_ROOT / entry).read_text())
        assert any(node.module == "common.transport" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    for level in ("unit", "integration", "system", "acceptance"):
        for path in (PROGRAM_ROOT / "tests" / level).glob("**/*.py"):
            assert FIXTURE_DEF.search(path.read_text()) is None


def test_acceptance_committed_layout_and_names():
    manifest = (
        "gui.py",
        "cli.py",
        "README.md",
        "tests/conftest.py",
        "common/transport.py",
        "common/simulated_transport.py",
        "common/config.py",
        "common/plot_widget.py",
        "common/sequence_logic.py",
        "sequences/fid/logic.py",
        "sequences/cal_pulse/logic.py",
        "sequences/cpmg/logic.py",
        "sequences/fid/ui.py",
        "sequences/cal_pulse/ui.py",
        "sequences/cpmg/ui.py",
        "app/main_window.py",
        "app/log_display.py",
        "app/cli_app.py",
        "app/__init__.py",
        "sequences/__init__.py",
        "sequences/fid/__init__.py",
        "sequences/cal_pulse/__init__.py",
        "sequences/cpmg/__init__.py",
        "common/__init__.py",
        "app/main_window.ui",
        "sequences/fid/layout.ui",
        "sequences/cal_pulse/layout.ui",
        "sequences/cpmg/layout.ui",
        "sequences/fid/config.ini",
        "sequences/cal_pulse/config.ini",
        "sequences/cpmg/config.ini",
        "docs/architecture.md",
        "docs/requirements.md",
        "pyproject.toml",
    )
    for entry in manifest:
        assert (PROGRAM_ROOT / entry).is_file()
    test_files = list((PROGRAM_ROOT / "tests").glob("**/test_*.py"))
    basenames = [path.name for path in test_files]
    assert len(basenames) == len(set(basenames))
    for path in test_files:
        assert re.match(r"test_.*\.py", path.name)
    acceptance_modules = sorted(
        path.name for path in (PROGRAM_ROOT / "tests" / "acceptance").iterdir() if path.is_file()
    )
    assert acceptance_modules == sorted(
        (
            "test_acceptance_entry_points.py",
            "test_acceptance_gui_frame.py",
            "test_acceptance_migration.py",
            "test_acceptance_scope_structure.py",
            "test_acceptance_suite_properties.py",
        )
    )
    non_test = sorted(
        str(path.relative_to(PROGRAM_ROOT)).replace(os.sep, "/")
        for path in (PROGRAM_ROOT / "tests").glob("**/*.py")
        if not path.name.startswith("test_") and "__pycache__" not in path.parts
    )
    assert non_test == sorted(
        ("tests/__init__.py", "tests/conftest.py", "tests/system/cli_driver.py", "tests/system/gui_driver.py")
    )
