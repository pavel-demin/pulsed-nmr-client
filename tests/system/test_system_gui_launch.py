import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

from tests.conftest import REFERENCE_GENERAL, REFERENCE_SEQUENCE

PROGRAM_ROOT = Path(__file__).resolve().parents[2]
DRIVER_TIMEOUT = 120
ENV = os.environ.copy()
ENV["QT_QPA_PLATFORM"] = "offscreen"
ENV["PULSED_NMR_TRANSPORT"] = "simulated"

FID_GUI_SHA256 = "afc651e0bbd3e8c728eb2dbc112fc2f365d3222e685a4c91fdf1c8e4c2b82306"
FID_GUI_COMMANDS = 38
FID_GUI_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000506676000000000000008076010000000200700000000000000080"
CAL_GUI_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_GUI_COMMANDS = 317
CAL_GUI_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CAL_PULSE_GUI_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_PULSE_GUI_COMMANDS = 317
CAL_PULSE_GUI_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CPMG_GUI_SHA256 = "61cf8fa913748002c68e95b14d21c326e1bbcc6867808853c49a12abe80a0b98"
CPMG_GUI_COMMANDS = 983
CPMG_GUI_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080c30900000020337300000000000000802c370000000200700000000000000080"

GUI_DRIVER = Path(__file__).resolve().parent / "gui_driver.py"
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
CONTROL_NAMES = (
    "startSeqButton",
    "loadSeqButton",
    "loadCfgButton",
    "saveCfgButton",
    "saveDataButton",
    "loadDataButton",
    "controlWidget",
)
GENERAL_INI = {
    key: (float(value) if key in ("freq", "adc_rate") else int(value))
    for key, value in REFERENCE_GENERAL.items()
    if key not in ("addr", "gain", "pin0", "pin1", "pin2", "pin3")
}
SEQUENCE_INI = {
    name: {key: int(value) for key, value in mapping.items()} for name, mapping in REFERENCE_SEQUENCE.items()
}
GENERAL_SET = {
    "freq": 20.0,
    "rate": 3,
    "adc_rate": 125.0,
    "blank": 7,
    "polarity": 0,
    "echo_time": 300,
    "delta": 500,
    "read_delay": 3,
    "read_time": 20,
    "scans": 16,
}
SEQUENCE_SET = {
    "fid": {"level": 80, "width": 4},
    "cal_pulse": {"level": 20, "start": 4, "stop": 30, "step": 3},
    "cpmg": {"level": 40, "width": 20, "echoes": 4},
}
HELPER_TYPE = {
    "fid": "FidUiHelper",
    "cal_pulse": "CalPulseUiHelper",
    "cpmg": "CpmgUiHelper",
}
EXPECTED_GUI_LOG = {
    "fid": [f"scan {n}/16 completed" for n in range(1, 17)] + ["FID sequence completed (read time 20 µs, 16 scans)"],
    "cpmg": [
        "scan 1/16 completed",
        "scan 2/16 completed",
        "scan 3/16 completed",
        "scan 4/16 completed",
        "scan 5/16 completed",
        "scan 6/16 completed",
        "scan 7/16 completed",
        "scan 8/16 completed",
        "scan 9/16 completed",
        "scan 10/16 completed",
        "scan 11/16 completed",
        "scan 12/16 completed",
        "scan 13/16 completed",
        "scan 14/16 completed",
        "scan 15/16 completed",
        "scan 16/16 completed",
        "CPMG sequence completed (4 echoes, 16 scans)",
    ],
}
POINT_LINE = re.compile(r"^point \d+/\d+: width=\d+\.\d{3} µs, signal=\d+\.\d{3}$")
SWEEP_LINE = re.compile(r"^step \d+/\d+: width=\d+\.\d{3} µs, peak=\d+\.\d{3}$")


def pack_stream(commands):
    return b"".join(struct.pack("<Q", code << 60 | data) for code, data in commands)


def run_gui_driver(sequence, config, tmp_path, load_csv=None):
    config(None)
    config(sequence)
    args = [sys.executable, GUI_DRIVER, PROGRAM_ROOT, sequence, str(tmp_path), str(tmp_path / (f"gui_{sequence}.json"))]
    if load_csv is not None:
        args.append(str(load_csv))
    proc = subprocess.run(
        args,
        check=False,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT,
        cwd=PROGRAM_ROOT,
    )
    return (proc, json.loads((tmp_path / (f"gui_{sequence}.json")).read_text()))


def test_gui_launch_fid_stream_and_log(config, tmp_path):
    proc, data = run_gui_driver("fid", config, tmp_path)
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["window_captured"] is True
    assert data["capture"]["frame"]["title"] == "Pulsed NMR"
    assert data["capture"]["frame"]["missing_widgets"] == []
    assert data["capture"]["frame"]["adc_rate_items"] == ["122.88", "125"]
    assert data["capture"]["frame"]["load_button_text"] == "Load seq."
    assert data["capture"]["frame"]["cfg_load_button"] == "Load cfg."
    assert data["capture"]["frame"]["cfg_save_button"] == "Save cfg."
    assert data["capture"]["frame"]["log_display_type"] == "LogDisplay"
    assert data["capture"]["frame"]["container_count_before"] == 0
    assert data["capture"]["frame"]["addr"] == "192.168.1.100"
    assert data["capture"]["idle"]["transport_is_none"] is True
    assert data["capture"]["idle"]["running"] is False
    assert data["capture"]["idle"]["start_button"] == "Start seq."
    assert data["capture"]["loaded"]["helper_type"] == HELPER_TYPE["fid"]
    assert data["capture"]["loaded"]["container_count"] == 1
    assert data["capture"]["loaded"]["item_is_current"] is True
    assert data["capture"]["loaded"]["save_data_button"] == "Save data"
    assert data["capture"]["loaded"]["load_data_button"] == "Load data"
    assert data["capture"]["ini"] == dict(GENERAL_INI, **SEQUENCE_INI["fid"])
    assert data["capture"]["post_set"] == dict(GENERAL_SET, **SEQUENCE_SET["fid"])
    stream = data["capture"]["post_run"]["stream"]
    assert len(stream) == FID_GUI_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == FID_GUI_SHA256
    assert pack_stream(stream[:18]).hex() == FID_GUI_FIRST_18_HEX
    assert data["capture"]["post_run"]["transport_connected"] is False
    assert data["capture"]["post_run"]["log"] == EXPECTED_GUI_LOG["fid"]


def test_gui_launch_fid_run_state_resets(config, tmp_path):
    proc, data = run_gui_driver("fid", config, tmp_path)
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["window_captured"] is True
    assert data["capture"]["frame"]["title"] == "Pulsed NMR"
    assert data["capture"]["frame"]["missing_widgets"] == []
    assert data["capture"]["frame"]["adc_rate_items"] == ["122.88", "125"]
    assert data["capture"]["frame"]["load_button_text"] == "Load seq."
    assert data["capture"]["frame"]["log_display_type"] == "LogDisplay"
    assert data["capture"]["frame"]["container_count_before"] == 0
    assert data["capture"]["frame"]["addr"] == "192.168.1.100"
    assert data["capture"]["idle"]["transport_is_none"] is True
    assert data["capture"]["idle"]["running"] is False
    assert data["capture"]["idle"]["start_button"] == "Start seq."
    assert data["capture"]["loaded"]["helper_type"] == HELPER_TYPE["fid"]
    assert data["capture"]["loaded"]["container_count"] == 1
    assert data["capture"]["loaded"]["item_is_current"] is True
    assert data["capture"]["ini"] == dict(GENERAL_INI, **SEQUENCE_INI["fid"])
    assert data["capture"]["post_set"] == dict(GENERAL_SET, **SEQUENCE_SET["fid"])
    assert data["capture"]["post_run"]["running"] is False
    assert data["capture"]["post_run"]["start_button"] == "Start seq."
    assert data["capture"]["post_run"]["container_count"] == 1
    assert data["capture"]["post_run"]["helper_type"] == HELPER_TYPE["fid"]


def test_gui_launch_cal_pulse_run(config, tmp_path):
    proc, data = run_gui_driver("cal_pulse", config, tmp_path)
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["window_captured"] is True
    assert data["capture"]["frame"]["title"] == "Pulsed NMR"
    assert data["capture"]["frame"]["missing_widgets"] == []
    assert data["capture"]["frame"]["adc_rate_items"] == ["122.88", "125"]
    assert data["capture"]["frame"]["load_button_text"] == "Load seq."
    assert data["capture"]["frame"]["log_display_type"] == "LogDisplay"
    assert data["capture"]["frame"]["container_count_before"] == 0
    assert data["capture"]["frame"]["addr"] == "192.168.1.100"
    assert data["capture"]["idle"]["transport_is_none"] is True
    assert data["capture"]["idle"]["running"] is False
    assert data["capture"]["idle"]["start_button"] == "Start seq."
    assert data["capture"]["loaded"]["helper_type"] == HELPER_TYPE["cal_pulse"]
    assert data["capture"]["loaded"]["container_count"] == 1
    assert data["capture"]["loaded"]["item_is_current"] is True
    assert data["capture"]["ini"] == dict(GENERAL_INI, **SEQUENCE_INI["cal_pulse"])
    assert data["capture"]["post_set"] == dict(GENERAL_SET, **SEQUENCE_SET["cal_pulse"])
    stream = data["capture"]["post_run"]["stream"]
    assert len(stream) == CAL_PULSE_GUI_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == CAL_PULSE_GUI_SHA256
    assert pack_stream(stream[:18]).hex() == CAL_PULSE_GUI_FIRST_18_HEX
    assert data["capture"]["post_run"]["transport_connected"] is False
    assert data["capture"]["post_run"]["running"] is False
    assert data["capture"]["post_run"]["start_button"] == "Start seq."
    assert data["capture"]["post_run"]["container_count"] == 1
    assert data["capture"]["post_run"]["helper_type"] == HELPER_TYPE["cal_pulse"]
    lines = data["capture"]["post_run"]["log"]
    assert len(lines) == 12
    assert all(SWEEP_LINE.match(line) for line in lines[0:10])
    assert lines[10] == "calibrated 90° pulse width: 0.000 µs"
    assert lines[11] == "pulse calibration completed (10 points)"


def test_gui_launch_cpmg_run(config, tmp_path):
    proc, data = run_gui_driver("cpmg", config, tmp_path)
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["window_captured"] is True
    assert data["capture"]["frame"]["title"] == "Pulsed NMR"
    assert data["capture"]["frame"]["missing_widgets"] == []
    assert data["capture"]["frame"]["adc_rate_items"] == ["122.88", "125"]
    assert data["capture"]["frame"]["load_button_text"] == "Load seq."
    assert data["capture"]["frame"]["log_display_type"] == "LogDisplay"
    assert data["capture"]["frame"]["container_count_before"] == 0
    assert data["capture"]["frame"]["addr"] == "192.168.1.100"
    assert data["capture"]["idle"]["transport_is_none"] is True
    assert data["capture"]["idle"]["running"] is False
    assert data["capture"]["idle"]["start_button"] == "Start seq."
    assert data["capture"]["loaded"]["helper_type"] == HELPER_TYPE["cpmg"]
    assert data["capture"]["loaded"]["container_count"] == 1
    assert data["capture"]["loaded"]["item_is_current"] is True
    assert data["capture"]["ini"] == dict(GENERAL_INI, **SEQUENCE_INI["cpmg"])
    assert data["capture"]["post_set"] == dict(GENERAL_SET, **SEQUENCE_SET["cpmg"])
    stream = data["capture"]["post_run"]["stream"]
    assert len(stream) == CPMG_GUI_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == CPMG_GUI_SHA256
    assert pack_stream(stream[:18]).hex() == CPMG_GUI_FIRST_18_HEX
    assert data["capture"]["post_run"]["transport_connected"] is False
    assert data["capture"]["post_run"]["running"] is False
    assert data["capture"]["post_run"]["start_button"] == "Start seq."
    assert data["capture"]["post_run"]["container_count"] == 1
    assert data["capture"]["post_run"]["helper_type"] == HELPER_TYPE["cpmg"]
    assert data["capture"]["post_run"]["log"] == EXPECTED_GUI_LOG["cpmg"]


def test_gui_launch_controls_disabled_during_run(config, tmp_path):
    proc, data = run_gui_driver("fid", config, tmp_path)
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["window_captured"] is True
    mid = data["capture"]["mid_run"]
    assert mid["startSeqButton"] is True
    for name in CONTROL_NAMES:
        if name != "startSeqButton":
            assert mid[name] is False
    for name in CONTROL_NAMES:
        assert data["capture"]["post_run"]["controls"][name] is True


def test_gui_launch_fid_data_load(config, tmp_path):
    load_csv = tmp_path / "load_fid.csv"
    load_csv.write_text("time,real,imag\n0.0,1.0,2.0\n1.0,-1.0,3.0\n2.0,4.0,-5.0\n")
    proc, data = run_gui_driver("fid", config, tmp_path, load_csv=load_csv)
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["window_captured"] is True
    assert data["capture"]["frame"]["title"] == "Pulsed NMR"
    assert data["capture"]["frame"]["missing_widgets"] == []
    assert data["capture"]["frame"]["adc_rate_items"] == ["122.88", "125"]
    assert data["capture"]["frame"]["load_button_text"] == "Load seq."
    assert data["capture"]["frame"]["log_display_type"] == "LogDisplay"
    assert data["capture"]["frame"]["container_count_before"] == 0
    assert data["capture"]["frame"]["addr"] == "192.168.1.100"
    assert data["capture"]["idle"]["transport_is_none"] is True
    assert data["capture"]["idle"]["running"] is False
    assert data["capture"]["idle"]["start_button"] == "Start seq."
    assert data["capture"]["loaded"]["helper_type"] == HELPER_TYPE["fid"]
    assert data["capture"]["loaded"]["container_count"] == 1
    assert data["capture"]["loaded"]["item_is_current"] is True
    assert data["capture"]["loaded"]["save_data_button"] == "Save data"
    assert data["capture"]["loaded"]["load_data_button"] == "Load data"
    assert data["capture"]["ini"] == dict(GENERAL_INI, **SEQUENCE_INI["fid"])
    assert data["capture"]["post_set"] == dict(GENERAL_SET, **SEQUENCE_SET["fid"])
    assert data["capture"]["pre_run_load"] == {
        "log": [f"loaded data from {tmp_path / 'load_fid.csv'}"],
        "results_keys": [0.0],
        "data_sizes": [6],
        "time_sizes": [3],
        "xdata_size": 3,
        "ydata_size": 3,
        "fit_curve": False,
        "logic_created": True,
    }
    stream = data["capture"]["post_run"]["stream"]
    assert len(stream) == FID_GUI_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == FID_GUI_SHA256
    assert pack_stream(stream[:18]).hex() == FID_GUI_FIRST_18_HEX
    assert data["capture"]["post_run"]["running"] is False
    assert data["capture"]["post_run"]["transport_connected"] is False
    assert data["capture"]["post_run"]["log"] == [
        f"loaded data from {tmp_path / 'load_fid.csv'}",
    ] + [
        f"scan {n}/16 completed" for n in range(1, 17)
    ] + ["FID sequence completed (read time 20 µs, 16 scans)"]
