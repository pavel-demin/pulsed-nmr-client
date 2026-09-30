import app.main_window as mw_mod
from app.main_window import MainWindow
from common.config import Config, sequence_dir
from common.sequence_logic import PIN_KEYS, pin_state
from common.simulated_transport import SimulatedTransport
from sequences.cal_pulse.ui import CalPulseUiHelper
from sequences.cpmg.ui import CpmgUiHelper
from sequences.fid.ui import FidUiHelper
from tests.conftest import REFERENCE_GENERAL, REFERENCE_SEQUENCE


class FakeDirDialog:
    directory = ""

    @staticmethod
    def getExistingDirectory(parent, title, directory=""):
        return FakeDirDialog.directory


class FakeFileDialog:
    path = ""

    @staticmethod
    def getOpenFileName(parent, title, path="", file_filter=""):
        return (FakeFileDialog.path, "")

    @staticmethod
    def getSaveFileName(parent, title, path="", file_filter=""):
        return (FakeFileDialog.path, "")


def test_frame_state(qapp):
    window = MainWindow()
    assert window.sequence is None
    assert window.running is False
    assert [window.rateValue.itemText(i) for i in range(window.rateValue.count())] == [
        "25",
        "50",
        "125",
        "250",
        "500",
        "1250",
    ]
    assert [window.polarityValue.itemText(i) for i in range(window.polarityValue.count())] == ["neg.", "pos."]
    assert [window.adcRateValue.itemText(i) for i in range(2)] == ["122.88", "125"]
    assert not hasattr(window, "loadDataButton")
    assert not hasattr(window, "saveDataButton")


def test_data_button_delegation(qapp, pinned):
    window = MainWindow()
    window.load_sequence("fid")
    calls = []
    window.sequence.save = lambda: calls.append("save")
    window.sequence.load = lambda: calls.append("load")
    window.sequence.saveDataButton.click()
    window.sequence.loadDataButton.click()
    assert calls == ["save", "load"]


def test_transport_from_factory(qapp, pinned):
    window = MainWindow()
    assert window.transport is None
    window.load_sequence("fid")
    window.run_seq()
    assert isinstance(window.transport, SimulatedTransport)
    assert window.transport.is_connected() is False


def test_dynamic_loading_all_sequences(qapp, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(mw_mod, "QFileDialog", FakeDirDialog)
    expected = {"fid": FidUiHelper, "cal_pulse": CalPulseUiHelper, "cpmg": CpmgUiHelper}
    previous = None
    for name in ("fid", "cal_pulse", "cpmg"):
        FakeDirDialog.directory = str(sequence_dir(name))
        window.loadSeqButton.click()
        assert isinstance(window.sequence, expected[name])
        assert window.seqContainerLayout.count() == 1
        if previous is not None:
            assert window.sequence is not previous
        previous = window.sequence


def test_unknown_sequence(qapp):
    window = MainWindow()
    window.load_sequence("bogus")
    lines = window.log.viewer.toPlainText().splitlines()
    assert lines[-1] == "error: unknown sequence bogus"
    assert window.sequence is None


def test_directory_outside_sequences(qapp, tmp_path, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(mw_mod, "QFileDialog", FakeDirDialog)
    FakeDirDialog.directory = str(tmp_path)
    window.loadSeqButton.click()
    lines = window.log.viewer.toPlainText().splitlines()
    assert lines[-1] == f"error: unknown sequence {tmp_path.name}"
    assert window.sequence is None


def test_adc_rate_switch_repopulates(qapp):
    window = MainWindow()
    window.adcRateValue.setCurrentIndex(0)
    assert [window.rateValue.itemText(i) for i in range(window.rateValue.count())] == [
        "40",
        "80",
        "160",
        "320",
        "640",
        "1280",
    ]
    window.rateValue.setCurrentIndex(5)
    window.adcRateValue.setCurrentIndex(1)
    assert [window.rateValue.itemText(i) for i in range(window.rateValue.count())] == [
        "25",
        "50",
        "125",
        "250",
        "500",
        "1250",
    ]
    assert window.rateValue.currentIndex() == 5


def test_run_disables_controls(qapp, pinned):
    window = MainWindow()
    window.load_sequence("fid")
    window.transport = SimulatedTransport("127.0.0.1", 1001)
    window.start_seq()
    assert window.sequence.controlWidget.isEnabled() is False
    assert window.loadSeqButton.isEnabled() is False
    assert window.loadCfgButton.isEnabled() is False
    assert window.saveCfgButton.isEnabled() is False
    assert window.sequence.loadDataButton.isEnabled() is False
    assert window.sequence.saveDataButton.isEnabled() is False
    assert window.startSeqButton.isEnabled() is True
    window.finish_seq()
    assert window.sequence.controlWidget.isEnabled() is True
    assert window.loadSeqButton.isEnabled() is True
    assert window.loadCfgButton.isEnabled() is True
    assert window.saveCfgButton.isEnabled() is True
    assert window.sequence.loadDataButton.isEnabled() is True
    assert window.sequence.saveDataButton.isEnabled() is True


def test_run_current(qapp, pinned):
    window = MainWindow()
    window.load_sequence("fid")
    window.run_seq()
    assert window.running is False
    assert window.startSeqButton.text() == "Start seq."
    assert window.transport.commands[2:7] == [
        (5, 0),
        (5, 1),
        (5, 2),
        (5, 3),
        (2, int(int(REFERENCE_GENERAL["gain"]) / 50.0 * 4095 + 0.5)),
    ]
    assert len(window.transport.commands) == 38
    lines = window.log.viewer.toPlainText().splitlines()
    assert (
        lines[-1]
        == f"FID sequence completed (read time {REFERENCE_GENERAL['read_time']} \u00b5s, {REFERENCE_GENERAL['scans']} scans)"
    )


def test_run_guards(qapp):
    window = MainWindow()
    window.run_seq()
    assert window.transport is None
    assert window.running is False
    window.running = True
    window.run_seq()
    assert window.transport is None
    assert window.running is True


def test_cfg_save_dialog(qapp, pinned, tmp_path, monkeypatch):
    monkeypatch.setattr(mw_mod, "QFileDialog", FakeFileDialog)
    window = MainWindow()
    window.load_sequence("fid")
    window.sequence.levelValue.setValue(42)
    target = tmp_path / "general.ini"
    FakeFileDialog.path = str(target)
    window.saveCfgButton.click()
    assert target.exists()
    config = Config(str(target))
    config.load()
    for key, value in REFERENCE_GENERAL.items():
        if key not in ("pin0", "pin1", "pin2", "pin3"):
            assert config.get("general", key) == value
    assert config.get("general", "gain") == REFERENCE_GENERAL["gain"]
    for key, _ in PIN_KEYS:
        assert config.get("general", key) == str(pin_state(REFERENCE_GENERAL[key]))
    assert config.get("sequence", "level") == "42"
    assert config.get("sequence", "width") == REFERENCE_SEQUENCE["fid"]["width"]
    fid_config = Config(Config.sequence_path("fid"))
    fid_config.load()
    assert fid_config.get("sequence", "level") == REFERENCE_SEQUENCE["fid"]["level"]
    FakeFileDialog.path = ""
    window.freqValue.setValue(20.0)
    window.saveCfgButton.click()
    config.load()
    assert config.get("general", "freq") == REFERENCE_GENERAL["freq"]


def test_cfg_load_dialog(qapp, pinned, tmp_path, monkeypatch, write_ini):
    monkeypatch.setattr(mw_mod, "QFileDialog", FakeFileDialog)
    program = dict(REFERENCE_GENERAL)
    program["freq"] = "9.99"
    program["scans"] = "8"
    path = tmp_path / "load_unified.ini"
    write_ini(path, {"general": program, "sequence": {"level": "31", "width": "7"}})
    window = MainWindow()
    window.load_sequence("fid")
    window.sequence.levelValue.setValue(42)
    FakeFileDialog.path = str(path)
    window.loadCfgButton.click()
    assert window.freqValue.value() == 9.99
    assert window.scansValue.value() == 8
    assert window.sequence.levelValue.value() == 31
    assert window.sequence.widthValue.value() == 7
    general_only = tmp_path / "load_general.ini"
    general_program = dict(REFERENCE_GENERAL)
    general_program["freq"] = "9.99"
    write_ini(general_only, "general", general_program)
    window.sequence.levelValue.setValue(42)
    FakeFileDialog.path = str(general_only)
    window.loadCfgButton.click()
    assert window.freqValue.value() == 9.99
    assert window.sequence.levelValue.value() == 42
    assert window.sequence.widthValue.value() == 7
    log_lines = window.log.viewer.toPlainText().splitlines()
    assert log_lines[-1] == "error: invalid parameters"
    FakeFileDialog.path = ""
    window.freqValue.setValue(20.0)
    window.loadCfgButton.click()
    assert window.freqValue.value() == 20.0


def test_sequence_cfg_no_sequence(qapp, monkeypatch):
    class RefusingFileDialog:
        @staticmethod
        def getOpenFileName(parent, title, path=""):
            raise AssertionError

        @staticmethod
        def getSaveFileName(parent, title, path=""):
            raise AssertionError

    monkeypatch.setattr(mw_mod, "QFileDialog", RefusingFileDialog)
    window = MainWindow()
    window.loadCfgButton.click()
    window.saveCfgButton.click()
    assert window.sequence is None


def test_run_resets_stopping_after_stop(qapp):
    window = MainWindow()
    window.load_sequence("fid")
    window.run_seq()
    window.sequence.stop()
    window.run_seq()
    assert window.transport.stopping is False


def test_run_connect_failure(qapp, pinned, monkeypatch):
    window = MainWindow()
    window.load_sequence("fid")
    failed = SimulatedTransport("127.0.0.1", 1001)
    failed.stop()
    monkeypatch.setattr(mw_mod, "create_transport", lambda addr, port=1001: failed)
    monkeypatch.setattr(mw_mod, "wait_for_connection", lambda transport, timeout_ms: (False, "connection timeout"))
    window.run_seq()
    assert window.running is False
    assert window.startSeqButton.text() == "Start seq."
    assert window.transport is failed
    assert failed.is_connected() is False
    assert failed.commands == []
    assert window.log.viewer.toPlainText().splitlines()[-1] == "error: connection timeout"
    assert window.loadSeqButton.isEnabled() is True


def test_apply_config_general_and_pins(qapp, pinned, tmp_path, write_ini):
    window = MainWindow()
    window.load_sequence("fid")
    program = dict(REFERENCE_GENERAL)
    program["pin0"] = "1"
    program["pin1"] = "0"
    program["pin2"] = "True"
    program["pin3"] = "False"
    path = tmp_path / "general.ini"
    write_ini(path, {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    window.apply_config(str(path))
    assert window.addrValue.text() == REFERENCE_GENERAL["addr"]
    assert window.freqValue.value() == float(REFERENCE_GENERAL["freq"])
    assert window.rateValue.currentIndex() == int(REFERENCE_GENERAL["rate"])
    assert window.adcRateValue.currentIndex() == (1 if REFERENCE_GENERAL["adc_rate"] == "125" else 0)
    assert window.blankValue.value() == int(REFERENCE_GENERAL["blank"])
    assert window.polarityValue.currentIndex() == int(REFERENCE_GENERAL["polarity"])
    assert window.echoTimeValue.value() == int(REFERENCE_GENERAL["echo_time"])
    assert window.deltaValue.value() == int(REFERENCE_GENERAL["delta"])
    assert window.readDelayValue.value() == int(REFERENCE_GENERAL["read_delay"])
    assert window.readTimeValue.value() == int(REFERENCE_GENERAL["read_time"])
    assert window.scansValue.value() == int(REFERENCE_GENERAL["scans"])
    assert window.gainValue.value() == int(REFERENCE_GENERAL["gain"])
    assert window.pin0.isChecked() is True
    assert window.pin1.isChecked() is False
    assert window.pin2.isChecked() is True
    assert window.pin3.isChecked() is False
    assert window.sequence.levelValue.value() == int(REFERENCE_SEQUENCE["fid"]["level"])
    assert window.sequence.widthValue.value() == int(REFERENCE_SEQUENCE["fid"]["width"])


def test_load_sequence_invalid_general(qapp, tmp_path, monkeypatch, write_ini):
    program = dict(REFERENCE_GENERAL)
    program["rate"] = "abc"
    path = tmp_path / "bad.ini"
    write_ini(path, {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    monkeypatch.setattr(Config, "sequence_path", classmethod(lambda cls, name: path))
    window = MainWindow()
    window.load_sequence("fid")
    log_lines = window.log.viewer.toPlainText().splitlines()
    assert log_lines[-1] == "error: invalid parameters"


def test_apply_config_negative_rate_clamps(qapp, pinned, tmp_path, write_ini):
    window = MainWindow()
    window.load_sequence("fid")
    program = dict(REFERENCE_GENERAL)
    program["rate"] = "-1"
    path = tmp_path / "neg_rate.ini"
    write_ini(path, {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    window.apply_config(str(path))
    assert window.rateValue.currentIndex() == 0
    assert window.rateValue.currentText() != ""
