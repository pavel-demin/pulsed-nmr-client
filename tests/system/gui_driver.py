import json
import os
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["PULSED_NMR_TRANSPORT"] = "simulated"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import app.main_window as mw_mod
import common.config as config_mod
import common.plot_widget as plot_mod
import gui

sequence = sys.argv[2]
tmp_dir = sys.argv[3]
out_path = sys.argv[4]
load_csv = sys.argv[5] if len(sys.argv) > 5 else ""

config_mod.Config.sequence_path = classmethod(lambda cls, name: Path(tmp_dir) / (name + ".ini"))

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
GENERAL_KEYS = (
    "freq",
    "rate",
    "adc_rate",
    "blank",
    "polarity",
    "echo_time",
    "delta",
    "read_delay",
    "read_time",
    "scans",
)
SEQUENCE_KEYS = {
    "fid": ("level", "width"),
    "cal_pulse": ("level", "start", "stop", "step"),
    "cpmg": ("level", "width", "echoes"),
}

state = {"window": None, "capture": {}, "errors": []}


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
        return FakeFileDialog.DialogCode.Accepted

    def selectedFiles(self):
        return [load_csv]


class FakeDirDialog:
    directory = str(Path(sys.argv[1]) / "sequences" / sequence)

    @staticmethod
    def getExistingDirectory(parent, title, directory=""):
        return FakeDirDialog.directory


def general_values(window):
    values = {
        "freq": window.freqValue.value(),
        "rate": window.rateValue.currentIndex(),
        "adc_rate": float(window.adcRateValue.currentText()),
        "blank": window.blankValue.value(),
        "polarity": window.polarityValue.currentIndex(),
        "echo_time": window.echoTimeValue.value(),
        "delta": window.deltaValue.value(),
        "read_delay": window.readDelayValue.value(),
        "read_time": window.readTimeValue.value(),
        "scans": window.scansValue.value(),
    }
    return values


def sequence_values(window):
    helper = window.sequence
    return {name: getattr(helper, name + "Value").value() for name in SEQUENCE_KEYS[sequence]}


def set_general(window):
    window.freqValue.setValue(20.0)
    window.rateValue.setCurrentIndex(3)
    window.blankValue.setValue(7)
    window.polarityValue.setCurrentIndex(0)
    window.echoTimeValue.setValue(300)
    window.deltaValue.setValue(500)
    window.readDelayValue.setValue(3)
    window.readTimeValue.setValue(20)


def set_sequence(window):
    if sequence == "fid":
        window.sequence.levelValue.setValue(80)
        window.sequence.widthValue.setValue(4)
    elif sequence == "cal_pulse":
        window.sequence.levelValue.setValue(20)
        window.sequence.startValue.setValue(4)
        window.sequence.stopValue.setValue(30)
        window.sequence.stepValue.setValue(3)
    else:
        window.sequence.levelValue.setValue(40)
        window.sequence.widthValue.setValue(20)
        window.sequence.echoesValue.setValue(4)


def capture():
    window = state["window"]
    capture = state["capture"]
    capture["frame"] = {
        "title": window.windowTitle(),
        "missing_widgets": [name for name in FRAME_WIDGETS if getattr(window, name) is None],
        "adc_rate_items": [window.adcRateValue.itemText(i) for i in range(window.adcRateValue.count())],
        "scans_value": window.scansValue.value(),
        "rx_gain_range": [window.gainValue.minimum(), window.gainValue.maximum()],
        "pin_count": window.pinsLayout.count(),
        "load_button_text": window.loadSeqButton.text(),
        "cfg_load_button": window.loadCfgButton.text(),
        "cfg_save_button": window.saveCfgButton.text(),
        "log_display_type": type(window.log).__name__,
        "container_count_before": window.seqContainerLayout.count(),
        "addr": window.addrValue.text(),
    }
    capture["idle"] = {
        "transport_is_none": window.transport is None,
        "running": window.running,
        "start_button": window.startSeqButton.text(),
    }
    mw_mod.QFileDialog = FakeDirDialog
    window.loadSeqButton.click()
    capture["loaded"] = {
        "helper_type": type(window.sequence).__name__,
        "container_count": window.seqContainerLayout.count(),
        "item_is_current": window.seqContainerLayout.itemAt(0).widget() is window.sequence,
        "save_data_button": window.sequence.saveDataButton.text(),
        "load_data_button": window.sequence.loadDataButton.text(),
    }
    if load_csv:
        plot_mod.QFileDialog = FakeFileDialog
        window.sequence.loadDataButton.click()
        capture["pre_run_load"] = {
            "log": window.log.viewer.toPlainText().splitlines(),
            "results_keys": sorted(float(key) for key in window.sequence.results),
            "data_sizes": [int(value[1].size) for value in window.sequence.results.values()],
            "time_sizes": [int(value[0].size) for value in window.sequence.results.values()],
            "xdata_size": int(window.sequence.xdata.size),
            "ydata_size": int(window.sequence.ydata.size),
            "fit_curve": window.sequence.fit_curve is not None,
            "logic_created": window.sequence.logic is not None,
        }
    capture["ini"] = dict(general_values(window), **sequence_values(window))
    set_general(window)
    set_sequence(window)
    capture["post_set"] = dict(general_values(window), **sequence_values(window))
    original_factory = mw_mod.create_transport
    created = []
    original_read = None

    def read_probe(size):
        if "mid_run" not in capture:
            capture["mid_run"] = {
                "startSeqButton": window.startSeqButton.isEnabled(),
                "loadSeqButton": window.loadSeqButton.isEnabled(),
                "saveDataButton": window.sequence.saveDataButton.isEnabled(),
                "loadDataButton": window.sequence.loadDataButton.isEnabled(),
                "loadCfgButton": window.loadCfgButton.isEnabled(),
                "saveCfgButton": window.saveCfgButton.isEnabled(),
                "controlWidget": window.sequence.controlWidget.isEnabled(),
            }
        return original_read(size)

    def factory_wrapper(addr, port=1001):
        nonlocal original_read
        transport = original_factory(addr, port)
        created.append(transport)
        original_read = transport.read_samples
        transport.read_samples = read_probe
        return transport

    mw_mod.create_transport = factory_wrapper
    window.startSeqButton.click()
    capture["post_run"] = {
        "running": window.running,
        "start_button": window.startSeqButton.text(),
        "container_count": window.seqContainerLayout.count(),
        "helper_type": type(window.sequence).__name__,
        "stream": [list(command) for command in window.transport.commands],
        "transport_connected": window.transport.is_connected(),
        "log": window.log.viewer.toPlainText().splitlines(),
        "controls": {
            "startSeqButton": window.startSeqButton.isEnabled(),
            "loadSeqButton": window.loadSeqButton.isEnabled(),
            "saveDataButton": window.sequence.saveDataButton.isEnabled(),
            "loadDataButton": window.sequence.loadDataButton.isEnabled(),
            "loadCfgButton": window.loadCfgButton.isEnabled(),
            "saveCfgButton": window.saveCfgButton.isEnabled(),
            "controlWidget": window.sequence.controlWidget.isEnabled(),
        },
    }


def drive():
    try:
        capture()
    except Exception as exc:
        state["errors"].append(f"capture exception {exc!r}")
    finally:
        QApplication.instance().quit()


class CapturedMainWindow(mw_mod.MainWindow):
    def showEvent(self, event):
        super().showEvent(event)
        state["window"] = self
        QTimer.singleShot(0, drive)


gui.MainWindow = CapturedMainWindow
try:
    gui.main()
except SystemExit:
    pass
except Exception as exc:
    state["errors"].append(f"gui.main exception {exc!r}")

if state["window"] is None:
    state["errors"].append("window not captured")
results = {"window_captured": state["window"] is not None, "capture": state["capture"], "errors": state["errors"]}
with open(out_path, "w") as fh:
    json.dump(results, fh)

if state["errors"]:
    print("gui driver FAILED: {!r}".format(state["errors"]))
    sys.exit(1)
print(f"gui driver captured: {sequence}, {len(state['capture'].get('post_run', {}).get('stream', []))} commands")
