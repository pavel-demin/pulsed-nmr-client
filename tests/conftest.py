import os
import struct
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
)

from app.log_display import LogDisplay
from common import plot_widget
from common.config import Config
from common.simulated_transport import SimulatedTransport

REFERENCE_GENERAL = {
    "addr": "192.168.1.100",
    "freq": "13.24",
    "rate": "5",
    "adc_rate": "125",
    "blank": "5",
    "polarity": "1",
    "echo_time": "200",
    "delta": "1000",
    "read_delay": "1",
    "read_time": "10",
    "scans": "16",
    "gain": "10",
    "pin0": "0",
    "pin1": "0",
    "pin2": "0",
    "pin3": "0",
}

REFERENCE_SEQUENCE = {
    "fid": {"level": "10", "width": "10"},
    "cal_pulse": {"level": "10", "start": "2", "stop": "40", "step": "2"},
    "cpmg": {"level": "50", "width": "50", "echoes": "10"},
}


def pack_stream(commands):
    return b"".join(struct.pack("<Q", code << 60 | data) for code, data in commands)


class FakeMainWindow:
    pass


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True, scope="session")
def simulated_env():
    previous = os.environ.get("PULSED_NMR_TRANSPORT")
    os.environ["PULSED_NMR_TRANSPORT"] = "simulated"
    yield
    if previous is None:
        os.environ.pop("PULSED_NMR_TRANSPORT", None)
    else:
        os.environ["PULSED_NMR_TRANSPORT"] = previous


@pytest.fixture
def simulated_transport():
    transport = SimulatedTransport("127.0.0.1", 1001)
    yield transport
    transport.reset()


@pytest.fixture
def fake_file_dialog(monkeypatch):
    state = {"code": 1, "files": []}

    class FakeFileDialog:
        class DialogCode:
            Rejected = 0
            Accepted = 1

        class AcceptMode:
            AcceptSave = 0
            AcceptOpen = 1

        def __init__(self, parent, title, path, file_filter):
            pass

        def setDefaultSuffix(self, suffix):
            pass

        def selectFile(self, name):
            pass

        def setAcceptMode(self, mode):
            pass

        def exec(self):
            return state["code"]

        def selectedFiles(self):
            return state["files"]

    monkeypatch.setattr(plot_widget, "QFileDialog", FakeFileDialog)
    return state


@pytest.fixture
def inject_hump(simulated_transport):
    counter = [0]

    def injected(size):
        counter[0] += 1
        sweep_value = 2.0 + 2.0 * ((counter[0] - 1) // 16)
        return np.full(size * 2, 100.0 / (1.0 + ((sweep_value - 10.0) / 2.0) ** 2), dtype=np.complex64)

    simulated_transport.read_samples = injected


@pytest.fixture
def inject_nutation(simulated_transport):
    def make(pw90=8.0):
        counter = [0]

        def injected(size):
            counter[0] += 1
            sweep_value = 2.0 + 2.0 * ((counter[0] - 1) // 16)
            return np.full(size * 2, np.sin((np.pi / 2.0) * sweep_value / pw90), dtype=np.complex64)

        simulated_transport.read_samples = injected

    return make


@pytest.fixture
def write_ini():
    def make(path, section, mapping=None):
        if mapping is None:
            sections = section
        else:
            sections = {section: mapping}
        lines = []
        for index, (name, values) in enumerate(sections.items()):
            if index:
                lines.append("")
            lines.append(f"[{name}]")
            for key, value in values.items():
                lines.append(f"{key} = {value}")
        Path(path).write_text("\n".join(lines) + "\n")

    return make


@pytest.fixture
def config(tmp_path, write_ini):
    def make(name=None):
        if name is None:
            path = tmp_path / "program.ini"
            write_ini(path, "general", REFERENCE_GENERAL)
        else:
            path = tmp_path / (name + ".ini")
            write_ini(path, {"general": REFERENCE_GENERAL, "sequence": REFERENCE_SEQUENCE[name]})
        return Config(str(path))

    return make


@pytest.fixture
def pinned(tmp_path, monkeypatch, write_ini):
    for seq_name, mapping in REFERENCE_SEQUENCE.items():
        path = tmp_path / (f"pinned_{seq_name}.ini")
        lines = ["[general]"]
        for key, value in REFERENCE_GENERAL.items():
            lines.append(f"{key} = {value}")
        lines.append("")
        lines.append("[sequence]")
        for key, value in mapping.items():
            lines.append(f"{key} = {value}")
        path.write_text("\n".join(lines) + "\n")
    sequence_path = tmp_path / (f"pinned_{next(iter(REFERENCE_SEQUENCE))}.ini")
    monkeypatch.setattr(Config, "sequence_path", classmethod(lambda cls, name: tmp_path / (f"pinned_{name}.ini")))
    return sequence_path


@pytest.fixture
def log_display(qapp):
    def make():
        return LogDisplay(QPlainTextEdit())

    return make


@pytest.fixture
def fake_main_window(qapp, simulated_transport):
    def make(**overrides):
        window = FakeMainWindow()
        window.transport = simulated_transport
        window.addrValue = QLineEdit("192.168.1.100")
        window.freqValue = QDoubleSpinBox()
        window.freqValue.setRange(0.0, 100000.0)
        window.freqValue.setValue(13.24)
        window.rateValue = QComboBox()
        window.rateValue.addItems(["25", "50", "125", "250", "500", "1250"])
        window.rateValue.setCurrentIndex(5)
        window.adcRateValue = QComboBox()
        window.adcRateValue.addItems(["122.88", "125"])
        window.adcRateValue.setCurrentIndex(1)
        window.scansValue = QSpinBox()
        window.scansValue.setRange(1, 1000)
        window.scansValue.setValue(16)
        window.polarityValue = QComboBox()
        window.polarityValue.addItems(["neg.", "pos."])
        window.polarityValue.setCurrentIndex(1)
        window.blankValue = QSpinBox()
        window.blankValue.setRange(0, 1000000)
        window.blankValue.setValue(5)
        window.echoTimeValue = QSpinBox()
        window.echoTimeValue.setRange(0, 1000000)
        window.echoTimeValue.setValue(200)
        window.deltaValue = QSpinBox()
        window.deltaValue.setRange(0, 1000000)
        window.deltaValue.setValue(1000)
        window.readDelayValue = QSpinBox()
        window.readDelayValue.setRange(0, 1000000)
        window.readDelayValue.setValue(1)
        window.readTimeValue = QSpinBox()
        window.readTimeValue.setRange(0, 1000000)
        window.readTimeValue.setValue(10)
        window.gainValue = QSpinBox()
        window.gainValue.setRange(0, 50)
        window.gainValue.setValue(10)
        for name in ("pin0", "pin1", "pin2", "pin3"):
            setattr(window, name, QCheckBox())
        for name, value in overrides.items():
            setattr(window, name, value)
        return window

    return make


@pytest.fixture(scope="module")
def no_qapp():
    assert QApplication.instance() is None
    assert QCoreApplication.instance() is None
    yield
    assert QApplication.instance() is None
    assert QCoreApplication.instance() is None


LEVEL_ORDER = {"unit": 0, "integration": 1, "system": 2, "acceptance": 3}


def level_of(path):
    for part in str(path).split(os.sep):
        if part in LEVEL_ORDER:
            return LEVEL_ORDER[part]
    return len(LEVEL_ORDER)


def pytest_collection_modifyitems(config, items):
    items.sort(key=lambda item: level_of(item.fspath))
