import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import pack_stream

PROGRAM_ROOT = Path(__file__).resolve().parents[2]
DRIVER_TIMEOUT = 120
ENV = os.environ.copy()
ENV["QT_QPA_PLATFORM"] = "offscreen"
ENV["PULSED_NMR_TRANSPORT"] = "simulated"

FID_SHA256 = "afc651e0bbd3e8c728eb2dbc112fc2f365d3222e685a4c91fdf1c8e4c2b82306"
FID_COMMANDS = 38
FID_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000506676000000000000008076010000000200700000000000000080"
FID_GUI_SHA256 = "afc651e0bbd3e8c728eb2dbc112fc2f365d3222e685a4c91fdf1c8e4c2b82306"
FID_GUI_COMMANDS = 38
CAL_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_COMMANDS = 317
CAL_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CAL_GUI_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_GUI_COMMANDS = 317
CAL_PULSE_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_PULSE_COMMANDS = 317
CAL_PULSE_GUI_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_PULSE_GUI_COMMANDS = 317
CPMG_SHA256 = "61cf8fa913748002c68e95b14d21c326e1bbcc6867808853c49a12abe80a0b98"
CPMG_COMMANDS = 983
CPMG_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080c30900000020337300000000000000802c370000000200700000000000000080"
CPMG_GUI_SHA256 = "61cf8fa913748002c68e95b14d21c326e1bbcc6867808853c49a12abe80a0b98"
CPMG_GUI_COMMANDS = 983

GUI_DRIVER = Path(__file__).resolve().parent / "gui_driver.py"
CLI_DRIVER = Path(__file__).resolve().parent / "cli_driver.py"
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
SEQUENCE_SET = {
    "fid": {"level": 80, "width": 4},
    "cal_pulse": {"level": 20, "start": 4, "stop": 30, "step": 3},
    "cpmg": {"level": 40, "width": 20, "echoes": 4},
}


def run_both(sequence, config, tmp_path, write_ini):
    config(None)
    config(sequence)
    write_ini(tmp_path / "program.ini", "general", GENERAL_SET)
    write_ini(tmp_path / (sequence + ".ini"), {"general": GENERAL_SET, "sequence": SEQUENCE_SET[sequence]})
    gui_proc = subprocess.run(
        [sys.executable, GUI_DRIVER, PROGRAM_ROOT, sequence, str(tmp_path), str(tmp_path / (f"gui_{sequence}.json"))],
        check=False,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT,
        cwd=PROGRAM_ROOT,
    )
    cli_proc = subprocess.run(
        [
            sys.executable,
            CLI_DRIVER,
            PROGRAM_ROOT,
            sequence,
            str(tmp_path),
            str(tmp_path / (f"cli_{sequence}.json")),
            str(tmp_path / (f"cli_{sequence}_save.csv")),
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
    assert gui_proc.returncode == 0
    assert cli_proc.returncode == 0
    return (gui_data, cli_data)


def test_gui_cli_equivalence_fid(config, tmp_path, write_ini):
    gui_data, cli_data = run_both("fid", config, tmp_path, write_ini)
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


def test_gui_cli_equivalence_cal_pulse(config, tmp_path, write_ini):
    gui_data, cli_data = run_both("cal_pulse", config, tmp_path, write_ini)
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


def test_gui_cli_equivalence_cpmg(config, tmp_path, write_ini):
    gui_data, cli_data = run_both("cpmg", config, tmp_path, write_ini)
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
