import gc
import json
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

import app.main_window as mw_mod
from app.main_window import MainWindow
from common.config import sequence_dir
from sequences.cal_pulse.ui import CalPulseUiHelper
from sequences.cpmg.ui import CpmgUiHelper
from sequences.fid.ui import FidUiHelper

PROGRAM_ROOT = Path(__file__).resolve().parents[2]
GUI_DRIVER = PROGRAM_ROOT / "tests" / "system" / "gui_driver.py"
DRIVER_TIMEOUT = 120
ENV = os.environ.copy()
ENV["QT_QPA_PLATFORM"] = "offscreen"
ENV["PULSED_NMR_TRANSPORT"] = "simulated"
FRAME_WIDGETS = (
    "startSeqButton",
    "loadSeqButton",
    "loadCfgButton",
    "saveCfgButton",
    "addrValue",
    "freqValue",
    "rateValue",
    "polarityValue",
    "blankValue",
    "echoTimeValue",
    "deltaValue",
    "readDelayValue",
    "readTimeValue",
    "adcRateValue",
    "gainValue",
    "scansValue",
    "pin0",
    "pin1",
    "pin2",
    "pin3",
)


class FakeDirDialog:
    directory = ""

    @staticmethod
    def getExistingDirectory(parent, title, directory=""):
        return FakeDirDialog.directory


def run_gui_driver(sequence, config, tmp_path):
    config(None)
    config(sequence)
    out_path = str(tmp_path / (f"gui_{sequence}.json"))
    proc = subprocess.run(
        [sys.executable, GUI_DRIVER, PROGRAM_ROOT, sequence, str(tmp_path), out_path],
        check=False,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT,
        cwd=PROGRAM_ROOT,
    )
    data = json.loads((tmp_path / (f"gui_{sequence}.json")).read_text())
    return proc, data


def test_acceptance_frame_from_migrated_layout(config, tmp_path):
    proc, data = run_gui_driver("fid", config, tmp_path)
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["window_captured"] is True
    frame = data["capture"]["frame"]
    assert frame["title"] == "Pulsed NMR"
    assert frame["missing_widgets"] == []
    assert frame["adc_rate_items"] == ["122.88", "125"]
    assert frame["load_button_text"] == "Load seq."
    assert frame["cfg_load_button"] == "Load cfg."
    assert frame["cfg_save_button"] == "Save cfg."
    assert frame["log_display_type"] == "LogDisplay"
    assert frame["container_count_before"] == 0
    assert frame["addr"] == "192.168.1.100"
    assert data["capture"]["loaded"]["save_data_button"] == "Save data"
    assert data["capture"]["loaded"]["load_data_button"] == "Load data"


def test_acceptance_load_chain_single_sequence(qapp, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(mw_mod, "QFileDialog", FakeDirDialog)
    previous = None
    for name, helper_type in (("fid", FidUiHelper), ("cpmg", CpmgUiHelper), ("cal_pulse", CalPulseUiHelper)):
        FakeDirDialog.directory = str(sequence_dir(name))
        window.loadSeqButton.click()
        assert type(window.sequence) is helper_type
        assert window.seqContainerLayout.count() == 1
        assert window.seqContainerLayout.itemAt(0).widget() is window.sequence
        assert window.sequence.parent() is window.seqContainer
        if previous is not None:
            assert window.sequence is not previous
            assert window.seqContainerLayout.itemAt(0).widget() is not previous
        previous = window.sequence
    window.close()
    gc.collect()
    QApplication.processEvents()
