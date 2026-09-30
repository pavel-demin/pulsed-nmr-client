import contextlib
import io
import json
import os
import runpy
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PULSED_NMR_TRANSPORT"] = "simulated"

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

import app.cli_app as cli_mod
import common.config as config_mod

prog_dir = sys.argv[1]
sequence = sys.argv[2]
tmp_dir = sys.argv[3]
out_path = sys.argv[4]
saved_csv = sys.argv[5]
options = sys.argv[6:]

config_mod.Config.sequence_path = classmethod(lambda cls, name: Path(tmp_dir) / (name + ".ini"))

captured = []
factory = cli_mod.create_transport


def spy(addr, port=1001):
    transport = factory(addr, port)
    captured.append(transport)
    return transport


cli_mod.create_transport = spy
sys.argv = ["cli.py", sequence, saved_csv] + options
buffer = io.StringIO()
code = 0
errors = []
try:
    with contextlib.redirect_stdout(buffer):
        try:
            runpy.run_path(Path(prog_dir) / "cli.py", run_name="__main__")
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
except Exception as exc:
    code = -1
    errors.append(f"runpy exception {exc!r}")

stdout = buffer.getvalue()
qt_app = QApplication.instance() is not None or QCoreApplication.instance() is not None
transport = captured[0] if captured else None
stream = [list(command) for command in transport.commands] if transport is not None else []
transport_type = type(transport).__name__ if transport is not None else "none"
if len(captured) != 1:
    errors.append(f"transport captured {len(captured)} times")

results = {
    "code": code,
    "stdout": stdout,
    "stream": stream,
    "captured_count": len(captured),
    "qt_app": qt_app,
    "transport_type": transport_type,
    "errors": errors,
}
saved_path = Path(saved_csv)
if saved_path.exists():
    results["saved"] = {"exists": True, "lines": saved_path.read_text().splitlines()}
else:
    results["saved"] = {"exists": False, "lines": []}
with open(out_path, "w") as fh:
    json.dump(results, fh)

if errors:
    print(f"cli driver FAILED: {errors!r}")
    sys.exit(1)
print(f"cli driver captured: {sequence}, {len(stream)} commands, rc {code}, qt_app {qt_app}")
