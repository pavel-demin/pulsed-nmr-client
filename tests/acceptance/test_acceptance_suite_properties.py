import ast
import gc
import io
import os
import re
import tokenize
from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QVBoxLayout, QWidget

from app.log_display import LogDisplay
from app.main_window import MainWindow
from common.plot_widget import PlotWidget
from common.simulated_transport import SimulatedTransport
from common.transport import create_transport
from tests.conftest import REFERENCE_GENERAL, REFERENCE_SEQUENCE

PROGRAM_ROOT = Path(__file__).resolve().parents[2]
ASTYLE_EXCLUDE = ("tasks", ".pytest_cache", "__pycache__", ".ruff_cache")

NETWORK_OPEN = re.compile(r"connectToHos[t]|QTc[p]Socket|QUd[p]Socket|import\s+socke[t]|from\s+socke[t]\s+import")


def all_program_python_files():
    found = set()
    for directory in (".", "common", "app", "sequences"):
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


def style_violations(files):
    bad = []
    for name in files:
        src = Path(name).read_text()
        tree = ast.parse(src)
        all_imports = [node.lineno for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        top_imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        docstrings = [
            node.lineno
            for node in [tree]
            + [x for x in ast.walk(tree) if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            if ast.get_docstring(node)
        ]
        annotations = [node.lineno for node in ast.walk(tree) if isinstance(node, (ast.AnnAssign, ast.TypeAlias))]
        annotations += [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and (
                node.returns
                or any(
                    a.annotation
                    for a in list(node.args.args) + list(node.args.posonlyargs) + list(node.args.kwonlyargs)
                )
            )
        ]
        tokens = tokenize.generate_tokens(io.StringIO(src).readline)
        comments = [tok.start[0] for tok in tokens if tok.type == tokenize.COMMENT]
        for label, hits in [
            ("local imports", [lineno for lineno in all_imports if len(top_imports) < len(all_imports)]),
            ("docstrings", docstrings),
            ("annotations", annotations),
            ("comments", comments),
        ]:
            if hits:
                bad.append((name, label, hits))
    return bad


class HostPlotWidget(PlotWidget):
    def __init__(self):
        super().__init__()
        self.plotWidget = QWidget()
        self.plotLayout = QVBoxLayout(self)


def test_acceptance_gui_components_headless(qapp, pinned):
    window = MainWindow()
    window.load_sequence("fid")
    window.run_seq()
    assert len(window.transport.commands) == 38
    assert (
        window.log.viewer.toPlainText().splitlines()[-1]
        == f"FID sequence completed (read time {REFERENCE_GENERAL['read_time']} \u00b5s, {REFERENCE_GENERAL['scans']} scans)"
    )
    assert window.running is False
    assert window.startSeqButton.text() == "Start seq."
    log = LogDisplay(QPlainTextEdit())
    log.print("acceptance probe")
    assert "acceptance probe" in log.viewer.toPlainText()
    expected_params = {
        name: {key: int(value) for key, value in mapping.items()} for name, mapping in REFERENCE_SEQUENCE.items()
    }
    expected_params["cpmg"]["echo_time"] = int(REFERENCE_GENERAL["echo_time"])
    for name in ("fid", "cal_pulse", "cpmg"):
        window.load_sequence(name)
        params = window.sequence.collect_params()
        for key, value in expected_params[name].items():
            assert params[key] == value
        window.sequence.update_plot_limits()
        window.sequence.stop()
    plot = HostPlotWidget()
    plot.setup_plot("x", "y", "-")
    plot.xdata = np.array([0.0, 1.0], dtype=np.float32)
    plot.ydata = np.array([0.5, 1.5], dtype=np.float32)
    plot.update_curve()
    window.close()
    gc.collect()
    QApplication.processEvents()


def test_acceptance_hardware_isolation_simulated():
    assert os.environ["PULSED_NMR_TRANSPORT"] == "simulated"
    assert type(create_transport("127.0.0.1", 1001)) is SimulatedTransport
    for path in sorted((PROGRAM_ROOT / "tests").glob("**/test_*.py")):
        for line in path.read_text().splitlines():
            assert NETWORK_OPEN.search(line) is None


def test_acceptance_code_style_all_python():
    files = all_python_files()
    assert len(files) == 55
    assert style_violations(files) == []
