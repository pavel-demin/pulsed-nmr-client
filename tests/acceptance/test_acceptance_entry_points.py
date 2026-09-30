import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

import app.main_window as mw_mod
from app.cli_app import CliApp
from app.main_window import MainWindow
from common.config import Config, sequence_dir
from sequences.cpmg.ui import CpmgUiHelper
from sequences.fid.ui import FidUiHelper
from tests.conftest import REFERENCE_GENERAL, REFERENCE_SEQUENCE, pack_stream

PROGRAM_ROOT = Path(__file__).resolve().parents[2]
GUI_DRIVER = PROGRAM_ROOT / "tests" / "system" / "gui_driver.py"
CLI_DRIVER = PROGRAM_ROOT / "tests" / "system" / "cli_driver.py"
DRIVER_TIMEOUT = 120
ENV = os.environ.copy()
ENV["QT_QPA_PLATFORM"] = "offscreen"
ENV["PULSED_NMR_TRANSPORT"] = "simulated"
FID_COMMANDS = 38
FID_SHA256 = "afc651e0bbd3e8c728eb2dbc112fc2f365d3222e685a4c91fdf1c8e4c2b82306"
FID_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000506676000000000000008076010000000200700000000000000080"
FID_GUI_COMMANDS = 38
FID_GUI_SHA256 = "afc651e0bbd3e8c728eb2dbc112fc2f365d3222e685a4c91fdf1c8e4c2b82306"
FID_GUI_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000506676000000000000008076010000000200700000000000000080"
CAL_COMMANDS = 317
CAL_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CAL_GUI_COMMANDS = 317
CAL_GUI_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_GUI_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CAL_PULSE_COMMANDS = 317
CAL_PULSE_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_PULSE_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CAL_PULSE_GUI_COMMANDS = 317
CAL_PULSE_GUI_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_PULSE_GUI_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CPMG_COMMANDS = 983
CPMG_SHA256 = "61cf8fa913748002c68e95b14d21c326e1bbcc6867808853c49a12abe80a0b98"
CPMG_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080c30900000020337300000000000000802c370000000200700000000000000080"
CPMG_GUI_COMMANDS = 983
CPMG_GUI_SHA256 = "61cf8fa913748002c68e95b14d21c326e1bbcc6867808853c49a12abe80a0b98"
CPMG_GUI_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080c30900000020337300000000000000802c370000000200700000000000000080"
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
    "addr": "192.168.1.100",
    "pin0": 0,
    "pin1": 0,
    "pin2": 0,
    "pin3": 0,
    "gain": 10,
}
CAPTURE_GENERAL = {
    key: value for key, value in GENERAL_SET.items() if key not in ("addr", "gain", "pin0", "pin1", "pin2", "pin3")
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
EXPECTED_STDOUT_FID = [f"scan {n}/16 completed" for n in range(1, 17)] + [
    "FID sequence completed (read time 20 µs, 16 scans)"
]
EXPECTED_STDOUT_CPMG = [
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
]


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


def run_cli_driver(sequence, config, tmp_path, write_ini, output):
    config(None)
    config(sequence)
    write_ini(tmp_path / "program.ini", "general", GENERAL_SET)
    write_ini(tmp_path / (sequence + ".ini"), {"general": GENERAL_SET, "sequence": SEQUENCE_SET[sequence]})
    out_path = str(tmp_path / (f"cli_{sequence}.json"))
    proc = subprocess.run(
        [sys.executable, CLI_DRIVER, PROGRAM_ROOT, sequence, str(tmp_path), out_path, str(output)],
        check=False,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT,
        cwd=PROGRAM_ROOT,
    )
    data = json.loads((tmp_path / (f"cli_{sequence}.json")).read_text())
    return proc, data


def run_both(sequence, config, tmp_path, write_ini, output):
    config(None)
    config(sequence)
    write_ini(tmp_path / "program.ini", "general", GENERAL_SET)
    write_ini(tmp_path / (sequence + ".ini"), {"general": GENERAL_SET, "sequence": SEQUENCE_SET[sequence]})
    subprocess.run(
        [sys.executable, GUI_DRIVER, PROGRAM_ROOT, sequence, str(tmp_path), str(tmp_path / (f"gui_{sequence}.json"))],
        check=False,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT,
        cwd=PROGRAM_ROOT,
    )
    subprocess.run(
        [
            sys.executable,
            CLI_DRIVER,
            PROGRAM_ROOT,
            sequence,
            str(tmp_path),
            str(tmp_path / (f"cli_{sequence}.json")),
            str(output),
        ],
        check=False,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT,
        cwd=PROGRAM_ROOT,
    )
    gui_data = json.loads((tmp_path / (f"gui_{sequence}.json")).read_text())
    cli_data = json.loads((tmp_path / (f"cli_{sequence}.json")).read_text())
    return gui_data, cli_data


def check_gui_scenario(proc, data, sequence):
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
    idle = data["capture"]["idle"]
    assert idle["transport_is_none"] is True
    assert idle["running"] is False
    assert idle["start_button"] == "Start seq."
    loaded = data["capture"]["loaded"]
    assert loaded["helper_type"] == HELPER_TYPE[sequence]
    assert loaded["container_count"] == 1
    assert loaded["item_is_current"] is True
    assert loaded["save_data_button"] == "Save data"
    assert loaded["load_data_button"] == "Load data"
    assert data["capture"]["ini"] == dict(GENERAL_INI, **SEQUENCE_INI[sequence])
    assert data["capture"]["post_set"] == dict(CAPTURE_GENERAL, **SEQUENCE_SET[sequence])


def check_cli_scenario(proc, data):
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["code"] == 0
    assert data["captured_count"] == 1
    assert data["transport_type"] == "SimulatedTransport"
    assert data["qt_app"] is False


def test_acceptance_gui_run_fid(config, tmp_path):
    proc, data = run_gui_driver("fid", config, tmp_path)
    check_gui_scenario(proc, data, "fid")
    run = data["capture"]["post_run"]
    stream = run["stream"]
    assert len(stream) == FID_GUI_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == FID_GUI_SHA256
    assert pack_stream(stream[:18]).hex() == FID_GUI_FIRST_18_HEX
    assert run["log"] == EXPECTED_GUI_LOG["fid"]


def test_acceptance_gui_run_cal_pulse(config, tmp_path):
    proc, data = run_gui_driver("cal_pulse", config, tmp_path)
    check_gui_scenario(proc, data, "cal_pulse")
    run = data["capture"]["post_run"]
    stream = run["stream"]
    assert len(stream) == CAL_PULSE_GUI_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == CAL_PULSE_GUI_SHA256
    assert pack_stream(stream[:18]).hex() == CAL_PULSE_GUI_FIRST_18_HEX
    assert run["running"] is False
    assert run["start_button"] == "Start seq."
    assert run["container_count"] == 1
    assert run["helper_type"] == HELPER_TYPE["cal_pulse"]
    lines = run["log"]
    assert len(lines) == 12
    for line in lines[0:10]:
        assert SWEEP_LINE.match(line)
    assert lines[10] == "calibrated 90° pulse width: 0.000 µs"
    assert lines[11] == "pulse calibration completed (10 points)"


def test_acceptance_gui_run_cpmg(config, tmp_path):
    proc, data = run_gui_driver("cpmg", config, tmp_path)
    check_gui_scenario(proc, data, "cpmg")
    run = data["capture"]["post_run"]
    stream = run["stream"]
    assert len(stream) == CPMG_GUI_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == CPMG_GUI_SHA256
    assert pack_stream(stream[:18]).hex() == CPMG_GUI_FIRST_18_HEX
    assert run["running"] is False
    assert run["start_button"] == "Start seq."
    assert run["container_count"] == 1
    assert run["helper_type"] == HELPER_TYPE["cpmg"]
    assert run["log"] == EXPECTED_GUI_LOG["cpmg"]


def test_acceptance_cli_run_fid(config, tmp_path, write_ini):
    target = tmp_path / "cli_fid_save.csv"
    proc, data = run_cli_driver("fid", config, tmp_path, write_ini, output=target)
    check_cli_scenario(proc, data)
    stream = data["stream"]
    assert len(stream) == FID_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == FID_SHA256
    assert pack_stream(stream[:18]).hex() == FID_FIRST_18_HEX
    assert data["stdout"].splitlines() == EXPECTED_STDOUT_FID + [f"saved data to {target!s}"]


def test_acceptance_cli_run_cal_pulse(config, tmp_path, write_ini):
    target = tmp_path / "cli_cal_pulse_save.csv"
    proc, data = run_cli_driver("cal_pulse", config, tmp_path, write_ini, output=target)
    check_cli_scenario(proc, data)
    stream = data["stream"]
    assert len(stream) == CAL_PULSE_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == CAL_PULSE_SHA256
    assert pack_stream(stream[:18]).hex() == CAL_PULSE_FIRST_18_HEX
    lines = data["stdout"].splitlines()
    assert len(lines) == 13
    for line in lines[0:10]:
        assert SWEEP_LINE.match(line)
    assert lines[10] == "calibrated 90° pulse width: 0.000 µs"
    assert lines[11] == "pulse calibration completed (10 points)"
    assert lines[12] == f"saved data to {target!s}"


def test_acceptance_cli_run_cpmg(config, tmp_path, write_ini):
    target = tmp_path / "cli_cpmg_save.csv"
    proc, data = run_cli_driver("cpmg", config, tmp_path, write_ini, output=target)
    check_cli_scenario(proc, data)
    stream = data["stream"]
    assert len(stream) == CPMG_COMMANDS
    assert hashlib.sha256(pack_stream(stream)).hexdigest() == CPMG_SHA256
    assert pack_stream(stream[:18]).hex() == CPMG_FIRST_18_HEX
    assert data["stdout"].splitlines() == EXPECTED_STDOUT_CPMG + [f"saved data to {target!s}"]


def test_acceptance_gui_cli_equivalence_fid(config, tmp_path, write_ini):
    gui_data, cli_data = run_both("fid", config, tmp_path, write_ini, tmp_path / "cli_fid_save.csv")
    assert gui_data["window_captured"] is True
    assert gui_data["errors"] == []
    assert cli_data["errors"] == []
    gui_stream = gui_data["capture"]["post_run"]["stream"]
    cli_stream = cli_data["stream"]
    assert gui_stream == cli_stream
    assert len(gui_stream) == FID_GUI_COMMANDS
    assert len(cli_stream) == FID_COMMANDS
    assert hashlib.sha256(pack_stream(gui_stream)).hexdigest() == FID_GUI_SHA256
    assert hashlib.sha256(pack_stream(cli_stream)).hexdigest() == FID_SHA256


def test_acceptance_gui_cli_equivalence_cal_pulse(config, tmp_path, write_ini):
    gui_data, cli_data = run_both("cal_pulse", config, tmp_path, write_ini, tmp_path / "cli_cal_pulse_save.csv")
    assert gui_data["window_captured"] is True
    assert gui_data["errors"] == []
    assert cli_data["errors"] == []
    gui_stream = gui_data["capture"]["post_run"]["stream"]
    cli_stream = cli_data["stream"]
    assert gui_stream == cli_stream
    assert len(gui_stream) == CAL_PULSE_GUI_COMMANDS
    assert len(cli_stream) == CAL_PULSE_COMMANDS
    assert hashlib.sha256(pack_stream(gui_stream)).hexdigest() == CAL_PULSE_GUI_SHA256
    assert hashlib.sha256(pack_stream(cli_stream)).hexdigest() == CAL_PULSE_SHA256


def test_acceptance_gui_cli_equivalence_cpmg(config, tmp_path, write_ini):
    gui_data, cli_data = run_both("cpmg", config, tmp_path, write_ini, tmp_path / "cli_cpmg_save.csv")
    assert gui_data["window_captured"] is True
    assert gui_data["errors"] == []
    assert cli_data["errors"] == []
    gui_stream = gui_data["capture"]["post_run"]["stream"]
    cli_stream = cli_data["stream"]
    assert gui_stream == cli_stream
    assert len(gui_stream) == CPMG_GUI_COMMANDS
    assert len(cli_stream) == CPMG_COMMANDS
    assert hashlib.sha256(pack_stream(gui_stream)).hexdigest() == CPMG_GUI_SHA256
    assert hashlib.sha256(pack_stream(cli_stream)).hexdigest() == CPMG_SHA256


def test_acceptance_cli_save_fid(pinned, tmp_path, capsys):
    target = tmp_path / "fid.csv"
    code = CliApp(["fid", str(target)]).run()
    out = capsys.readouterr().out
    assert code == 0
    assert f"saved data to {target!s}" in out
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 14


def test_acceptance_cli_save_cal_pulse(pinned, tmp_path, capsys):
    target = tmp_path / "cal_pulse.csv"
    code = CliApp(["cal_pulse", str(target)]).run()
    out = capsys.readouterr().out
    assert code == 0
    assert f"saved data to {target!s}" in out
    lines = target.read_text().splitlines()
    assert lines[0] == "pulse_width,time,real,imag"
    assert len(lines) == 1 + 20 * 13


def test_acceptance_cli_save_cpmg(pinned, tmp_path, capsys):
    target = tmp_path / "cpmg.csv"
    code = CliApp(["cpmg", str(target)]).run()
    out = capsys.readouterr().out
    assert code == 0
    assert f"saved data to {target!s}" in out
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 131


def test_acceptance_save_equivalence(qapp, pinned, tmp_path, fake_file_dialog):
    gui_target = tmp_path / "gui_fid.csv"
    state = fake_file_dialog
    state["files"] = [str(gui_target)]
    window = MainWindow()
    window.load_sequence("fid")
    window.run_seq()
    window.sequence.save()
    window.close()
    cli_target = tmp_path / "cli_fid.csv"
    code = CliApp(["fid", str(cli_target)]).run()
    assert code == 0
    assert gui_target.exists()
    assert cli_target.exists()
    assert gui_target.read_bytes() == cli_target.read_bytes()


def test_acceptance_load_format_matches_run(qapp, pinned, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    for name in ("fid", "cal_pulse", "cpmg"):
        window = MainWindow()
        window.load_sequence(name)
        window.run_seq()
        run_csv = tmp_path / (name + "_run.csv")
        state["files"] = [str(run_csv)]
        window.sequence.save()
        assert run_csv.exists()
        run_results = window.sequence.results
        window.close()
        window2 = MainWindow()
        window2.load_sequence(name)
        state["files"] = [str(run_csv)]
        window2.sequence.load()
        assert list(window2.sequence.results) == list(run_results)
        for key in run_results:
            run_times, run_data = run_results[key]
            load_times, load_data = window2.sequence.results[key]
            assert np.array_equal(load_data, run_data)
            assert np.array_equal(load_times, run_times)
        lines = window2.log.viewer.toPlainText().splitlines()
        assert f"loaded data from {run_csv!s}" in lines
        window2.close()


def test_acceptance_load_before_run_save(qapp, pinned, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    source = tmp_path / "src.csv"
    source.write_text("time,real,imag\n1.0,2.0,-3.0\n4.0,5.0,6.0\n")
    target = tmp_path / "after_load.csv"
    window = MainWindow()
    window.load_sequence("fid")
    state["files"] = [str(source)]
    window.sequence.load()
    state["files"] = [str(target)]
    window.sequence.save()
    assert target.exists()
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    rows = np.loadtxt(str(target), delimiter=",", skiprows=1)
    assert np.all(rows == np.array([[1.0, 2.0, -3.0], [4.0, 5.0, 6.0]]))
    window.close()


class FakeDirDialog:
    directory = ""

    @staticmethod
    def getExistingDirectory(parent, title, directory=""):
        return FakeDirDialog.directory


def test_acceptance_directory_load_dialog(qapp, pinned, tmp_path, monkeypatch):
    window = MainWindow()
    monkeypatch.setattr(mw_mod, "QFileDialog", FakeDirDialog)
    FakeDirDialog.directory = str(sequence_dir() / "fid")
    window.loadSeqButton.click()
    assert type(window.sequence) is FidUiHelper
    FakeDirDialog.directory = str(sequence_dir() / "cpmg")
    window.loadSeqButton.click()
    assert type(window.sequence) is CpmgUiHelper
    assert window.seqContainerLayout.count() == 1
    FakeDirDialog.directory = str(tmp_path)
    window.loadSeqButton.click()
    lines = window.log.viewer.toPlainText().splitlines()
    assert lines[-1] == f"error: unknown sequence {tmp_path.name}"
    previous = window.sequence
    FakeDirDialog.directory = ""
    window.loadSeqButton.click()
    assert window.sequence is previous
    assert len(window.log.viewer.toPlainText().splitlines()) == len(lines)


def test_acceptance_sequence_cfg_dialog(qapp, pinned, tmp_path, monkeypatch, write_ini):
    class FakeCfgFileDialog:
        path = ""

        @staticmethod
        def getOpenFileName(parent, title, path="", file_filter=""):
            return (FakeCfgFileDialog.path, "")

        @staticmethod
        def getSaveFileName(parent, title, path="", file_filter=""):
            return (FakeCfgFileDialog.path, "")

    monkeypatch.setattr(mw_mod, "QFileDialog", FakeCfgFileDialog)
    window = MainWindow()
    window.load_sequence("fid")
    window.sequence.levelValue.setValue(42)
    seq_file = tmp_path / "sequence.ini"
    FakeCfgFileDialog.path = str(seq_file)
    window.saveCfgButton.click()
    seq_config = Config(str(seq_file))
    seq_config.load()
    assert seq_config.get("general", "freq") == "13.24"
    assert seq_config.get("sequence", "level") == "42"
    assert seq_config.get("sequence", "width") == "10"
    window.sequence.levelValue.setValue(1)
    FakeCfgFileDialog.path = str(seq_file)
    window.loadCfgButton.click()
    assert window.sequence.levelValue.value() == 42
    general_file = tmp_path / "general.ini"
    general_program = dict(REFERENCE_GENERAL, freq="8.88")
    write_ini(general_file, "general", general_program)
    FakeCfgFileDialog.path = str(general_file)
    window.loadCfgButton.click()
    assert window.freqValue.value() == 8.88
    assert window.sequence.levelValue.value() == 42
    assert window.sequence.widthValue.value() == 10
    assert window.log.viewer.toPlainText().splitlines()[-1] == "error: invalid parameters"
    before = seq_file.read_text()
    FakeCfgFileDialog.path = ""
    window.loadCfgButton.click()
    window.saveCfgButton.click()
    assert window.freqValue.value() == 8.88
    assert window.sequence.levelValue.value() == 42
    assert seq_file.read_text() == before
    window.close()

    class RefusingFileDialog:
        calls = 0

        @staticmethod
        def getOpenFileName(parent, title, path="", file_filter=""):
            RefusingFileDialog.calls += 1
            return ("", "")

        @staticmethod
        def getSaveFileName(parent, title, path="", file_filter=""):
            RefusingFileDialog.calls += 1
            return ("", "")

    monkeypatch.setattr(mw_mod, "QFileDialog", RefusingFileDialog)
    window2 = MainWindow()
    window2.loadCfgButton.click()
    window2.saveCfgButton.click()
    assert window2.sequence is None
    assert RefusingFileDialog.calls == 0
