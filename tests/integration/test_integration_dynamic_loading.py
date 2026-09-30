import app.main_window as mw_mod
from app.main_window import MainWindow
from common.config import sequence_dir
from sequences.cal_pulse.ui import CalPulseUiHelper
from sequences.cpmg.ui import CpmgUiHelper
from sequences.fid.ui import FidUiHelper


class FakeDirDialog:
    directory = ""

    @staticmethod
    def getExistingDirectory(parent, title, directory=""):
        return FakeDirDialog.directory


def test_load_chain_fid_cpmg_cal_pulse(qapp, pinned, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(mw_mod, "QFileDialog", FakeDirDialog)
    previous = None
    for name, helper_type in (
        ("fid", FidUiHelper),
        ("cpmg", CpmgUiHelper),
        ("cal_pulse", CalPulseUiHelper),
    ):
        FakeDirDialog.directory = str(sequence_dir(name))
        window.loadSeqButton.click()
        assert type(window.sequence) is helper_type
        assert window.seqContainerLayout.count() == 1
        assert window.seqContainerLayout.itemAt(0).widget() is window.sequence
        assert window.sequence.parent() is window.seqContainer
        if previous is not None:
            assert window.sequence is not previous
            members = [window.seqContainerLayout.itemAt(i).widget() for i in range(window.seqContainerLayout.count())]
            assert previous not in members
        previous = window.sequence


def test_loaded_sequence_runnable_through_window(qapp, pinned):
    window = MainWindow()
    window.load_sequence("fid")
    window.run_seq()
    assert len(window.transport.commands) == 38
    lines = window.log.viewer.toPlainText().splitlines()
    assert lines[-1] == "FID sequence completed (read time 10 µs, 16 scans)"
    assert window.running is False
    assert window.startSeqButton.text() == "Start seq."
    window.load_sequence("cpmg")
    window.run_seq()
    assert len(window.transport.commands) == 2135
    lines = window.log.viewer.toPlainText().splitlines()
    assert lines[-1] == "CPMG sequence completed (10 echoes, 16 scans)"


def test_controls_disabled_during_run(qapp, pinned, monkeypatch):
    window = MainWindow()
    window.load_sequence("fid")
    original_factory = mw_mod.create_transport
    original_read = None
    recorded = {}

    def probe(size):
        if not recorded:
            recorded["state"] = {
                "startSeqButton": window.startSeqButton.isEnabled(),
                "loadSeqButton": window.loadSeqButton.isEnabled(),
                "saveDataButton": window.sequence.saveDataButton.isEnabled(),
                "loadDataButton": window.sequence.loadDataButton.isEnabled(),
                "loadCfgButton": window.loadCfgButton.isEnabled(),
                "saveCfgButton": window.saveCfgButton.isEnabled(),
                "controlWidget": window.sequence.controlWidget.isEnabled(),
            }
        return original_read(size)

    def factory(addr, port=1001):
        nonlocal original_read
        transport = original_factory(addr, port)
        original_read = transport.read_samples
        transport.read_samples = probe
        return transport

    monkeypatch.setattr(mw_mod, "create_transport", factory)
    window.run_seq()
    mid = recorded["state"]
    assert mid["startSeqButton"] is True
    for name in (
        "loadSeqButton",
        "loadCfgButton",
        "saveCfgButton",
        "saveDataButton",
        "loadDataButton",
        "controlWidget",
    ):
        assert mid[name] is False
    assert window.startSeqButton.isEnabled() is True
    assert window.loadSeqButton.isEnabled() is True
    assert window.loadCfgButton.isEnabled() is True
    assert window.saveCfgButton.isEnabled() is True
    assert window.sequence.saveDataButton.isEnabled() is True
    assert window.sequence.loadDataButton.isEnabled() is True
    assert window.sequence.controlWidget.isEnabled() is True
    lines = window.log.viewer.toPlainText().splitlines()
    assert lines[-1] == "FID sequence completed (read time 10 µs, 16 scans)"


def test_stop_and_rerun_resets_stopping(qapp, pinned, monkeypatch):
    window = MainWindow()
    window.load_sequence("fid")
    created = []
    original_factory = mw_mod.create_transport

    def factory(addr, port=1001):
        transport = original_factory(addr, port)
        created.append(transport)
        return transport

    monkeypatch.setattr(mw_mod, "create_transport", factory)
    window.run_seq()
    window.sequence.stop()
    lines = window.log.viewer.toPlainText().splitlines()
    assert lines[-1] == "FID sequence stopped"
    window.run_seq()
    assert window.transport.stopping is False
    assert len(window.transport.commands) == 38
    assert created[0].stopping is True
    assert created[1].stopping is False
    lines = window.log.viewer.toPlainText().splitlines()
    assert lines[-1] == "FID sequence completed (read time 10 µs, 16 scans)"


def test_stop_button_terminates_run(qapp, pinned, monkeypatch):
    window = MainWindow()
    window.load_sequence("fid")
    original_factory = mw_mod.create_transport
    original_read = None
    clicked = {}

    def probe(size):
        if not clicked:
            clicked["yes"] = True
            window.startSeqButton.click()
        return original_read(size)

    def factory(addr, port=1001):
        nonlocal original_read
        transport = original_factory(addr, port)
        original_read = transport.read_samples
        transport.read_samples = probe
        return transport

    monkeypatch.setattr(mw_mod, "create_transport", factory)
    window.run_seq()
    assert window.running is False
    assert window.startSeqButton.text() == "Start seq."
    assert window.transport.is_connected() is False
    assert window.loadSeqButton.isEnabled() is True
    assert window.sequence.saveDataButton.isEnabled() is True
    lines = window.log.viewer.toPlainText().splitlines()
    assert "FID sequence stopped" in lines
