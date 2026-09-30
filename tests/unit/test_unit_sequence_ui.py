import configparser
import time

import numpy as np
import pytest
from PySide6.QtWidgets import QLabel, QSpinBox, QVBoxLayout, QWidget

from common import plot_widget
from common.config import Config
from common.sequence_ui import SequenceUiHelper
from common.simulated_transport import SimulatedTransport


class LogStub:
    def __init__(self):
        self.lines = []

    def print(self, text):
        self.lines.append(text)


class FakeEvent:
    def __init__(self, inaxes, xdata):
        self.inaxes = inaxes
        self.xdata = xdata


def make_logic_class(constructions):
    class StubLogic:
        def __init__(self, transport, log):
            self.transport = transport
            self.log = log
            self.stopping = False
            self.stopped = 0
            constructions.append(self)

        def stop(self):
            self.stopping = True
            self.stopped += 1

        def run(self, params, on_step=None):
            return None

    return StubLogic


class HostSequenceUi(SequenceUiHelper):
    def __init__(self, main_window):
        super().__init__()
        self.plotWidget = QWidget()
        self.plotLayout = QVBoxLayout(self)
        self.xdataValue = QLabel(self)
        self.ydataValue = QLabel(self)
        self.main_window = main_window
        self.log = LogStub()
        self.setup_plot("x label", "y label", "k-")

    def collect_params(self):
        return dict(self.general_params())

    def update_plot_limits(self):
        self.xdata = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        self.data = np.zeros(self.xdata.size, dtype=np.complex64)
        self.ydata = np.abs(self.data)
        self.update_curve()


def test_general_params(qapp, fake_main_window):
    helper = HostSequenceUi(fake_main_window())
    params = helper.general_params()
    assert params == {
        "freq": 13.24,
        "rate": 5,
        "adc_rate": 125.0,
        "blank": 5,
        "polarity": 1,
        "delta": 1000,
        "echo_time": 200,
        "read_delay": 1,
        "read_time": 10,
        "gain": 10,
        "scans": 16,
        "pin0": False,
        "pin1": False,
        "pin2": False,
        "pin3": False,
    }


def test_ensure_logic_creates_logic_once(qapp, fake_main_window):
    window = fake_main_window()
    constructions = []
    helper = HostSequenceUi(window)
    helper.logic_class = make_logic_class(constructions)
    helper.ensure_logic()
    helper.ensure_logic()
    assert len(constructions) == 1
    assert constructions[0].transport is window.transport
    assert callable(constructions[0].log)


def test_stop_delegates_only_when_logic_exists(qapp, fake_main_window):
    window = fake_main_window()
    constructions = []
    helper = HostSequenceUi(window)
    helper.logic_class = make_logic_class(constructions)
    helper.stop()
    assert constructions == []
    helper.ensure_logic()
    helper.stop()
    assert constructions[0].stopped == 1
    assert constructions[0].stopping is True


def test_save_empty_results(qapp, fake_main_window, monkeypatch):
    dialogs = []

    class RecordingFileDialog:
        def __init__(self, parent, title, path, file_filter):
            dialogs.append(title)

    monkeypatch.setattr(plot_widget, "QFileDialog", RecordingFileDialog)
    helper = HostSequenceUi(fake_main_window())
    helper.results = None
    helper.save()
    assert dialogs == []
    assert helper.log.lines == ["error: no data to save"]


def test_default_name(qapp, fake_main_window, monkeypatch):
    helper = HostSequenceUi(fake_main_window())
    helper.name_prefix = "host"
    monkeypatch.setattr(time, "strftime", lambda fmt: "20260925-213600")
    assert helper.default_name() == "host-20260925-213600.csv"


def testapply_results(qapp, fake_main_window):
    helper = HostSequenceUi(fake_main_window())
    data = np.zeros(4, dtype=np.complex64)
    data[0] = 1 - 2j
    data[2] = 3 + 4j
    times = np.array([1.0, 2.0], dtype=np.float32)
    helper.apply_results({0: (times, data)})
    assert np.array_equal(helper.xdata, times)
    assert helper.data.size == 2
    assert np.all(helper.data == np.array([1 - 2j, 3 + 4j], dtype=np.complex64))
    assert np.array_equal(helper.ydata, np.abs(helper.data))


def test_on_motion_defaults(qapp, fake_main_window):
    helper = HostSequenceUi(fake_main_window())
    helper.on_motion(FakeEvent(None, 2.5))
    assert helper.xdataValue.text() == ""
    helper.on_motion(FakeEvent(helper.axes, None))
    assert helper.xdataValue.text() == ""
    helper.xdata = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    helper.data = np.zeros(6, dtype=np.complex64)
    helper.data[0] = 7 - 0j
    helper.ydata = np.abs(helper.data)
    helper.on_motion(FakeEvent(helper.axes, 2.5))
    assert helper.xdataValue.text() == f"{2.0:12.3f}"
    assert helper.ydataValue.text() == f"{0.0:12.3f}"


def test_start_resets_stopped_logic(qapp, fake_main_window):
    window = fake_main_window()
    constructions = []
    helper = HostSequenceUi(window)
    helper.logic_class = make_logic_class(constructions)
    helper.ensure_logic()
    helper.stop()
    helper.start()
    assert helper.logic is constructions[0]
    assert constructions[0].stopping is False


def test_start_rebinds_logic_transport(qapp, fake_main_window):
    window = fake_main_window()
    constructions = []
    helper = HostSequenceUi(window)
    helper.logic_class = make_logic_class(constructions)
    helper.ensure_logic()
    assert constructions[0].transport is window.transport
    window.transport = SimulatedTransport("127.0.0.1", 1001)
    helper.start()
    assert constructions[0].transport is window.transport


def test_load_config(qapp, fake_main_window, tmp_path):
    helper = HostSequenceUi(fake_main_window())
    helper.sequence_name = "host"
    helper.sequence_settings = [("level", "levelValue"), ("width", "widthValue")]
    helper.levelValue = QSpinBox()
    helper.widthValue = QSpinBox()
    path = tmp_path / "full.ini"
    config = Config(str(path))
    config.set("sequence", "level", "7")
    config.set("sequence", "width", "3")
    config.save()
    helper.load_config(config)
    assert helper.levelValue.value() == 7
    assert helper.widthValue.value() == 3
    partial = tmp_path / "partial.ini"
    config = Config(str(partial))
    config.set("sequence", "level", "2")
    config.save()
    with pytest.raises(configparser.NoOptionError):
        helper.load_config(config)


def test_save_config(qapp, fake_main_window, tmp_path):
    helper = HostSequenceUi(fake_main_window())
    helper.sequence_settings = [("level", "levelValue"), ("width", "widthValue")]
    helper.levelValue = QSpinBox()
    helper.widthValue = QSpinBox()
    helper.levelValue.setValue(21)
    helper.widthValue.setValue(14)
    path = tmp_path / "saved.ini"
    config = Config(str(path))
    helper.save_config(config)
    config.save()
    saved = Config(str(path))
    saved.load()
    assert saved.get("sequence", "level") == "21"
    assert saved.get("sequence", "width") == "14"
