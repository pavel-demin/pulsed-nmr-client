import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from tests.conftest import pack_stream

PROGRAM_ROOT = Path(__file__).resolve().parents[2]
DRIVER_TIMEOUT = 120
ENV = os.environ.copy()
ENV["QT_QPA_PLATFORM"] = "offscreen"
ENV["PULSED_NMR_TRANSPORT"] = "simulated"

FID_SHA256 = "afc651e0bbd3e8c728eb2dbc112fc2f365d3222e685a4c91fdf1c8e4c2b82306"
FID_COMMANDS = 38
FID_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000506676000000000000008076010000000200700000000000000080"
CAL_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_COMMANDS = 317
CAL_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CAL_PULSE_SHA256 = "1f4dd0718d4fec808cf60bee33be051b6812ddf370b3614d1ea9a1716720bce6"
CAL_PULSE_COMMANDS = 317
CAL_PULSE_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080f301000000909971000000000000008076010000000200700000000000000080"
CPMG_SHA256 = "61cf8fa913748002c68e95b14d21c326e1bbcc6867808853c49a12abe80a0b98"
CPMG_COMMANDS = 983
CPMG_FIRST_18_HEX = "002d3101404b4c00fa000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000609facb9030002007000000000000000807c0000000003007000000000000000806a030000000000700000000000000080c30900000020337300000000000000802c370000000200700000000000000080"

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
POINT_LINE = re.compile(r"^point \d+/\d+: width=\d+\.\d{3} µs, signal=\d+\.\d{3}$")
SWEEP_LINE = re.compile(r"^step \d+/\d+: width=\d+\.\d{3} µs, peak=\d+\.\d{3}$")


def run_cli_driver(sequence, config, tmp_path, write_ini, output):
    config(None)
    config(sequence)
    write_ini(tmp_path / "program.ini", "general", GENERAL_SET)
    write_ini(tmp_path / (sequence + ".ini"), {"general": GENERAL_SET, "sequence": SEQUENCE_SET[sequence]})
    driver_args = [
        sys.executable,
        CLI_DRIVER,
        PROGRAM_ROOT,
        sequence,
        str(tmp_path),
        str(tmp_path / (f"cli_{sequence}.json")),
        str(output),
    ]
    proc = subprocess.run(
        driver_args,
        check=False,
        env=ENV,
        capture_output=True,
        text=True,
        timeout=DRIVER_TIMEOUT,
        cwd=PROGRAM_ROOT,
    )
    return (proc, json.loads((tmp_path / (f"cli_{sequence}.json")).read_text()))


def assert_full_cli_scenario(proc, data):
    assert proc.returncode == 0
    assert data["errors"] == []
    assert data["code"] == 0
    assert data["captured_count"] == 1
    assert data["transport_type"] == "SimulatedTransport"
    assert data["qt_app"] is False


def test_cli_run_fid_stream_and_stdout(config, tmp_path, write_ini):
    target = tmp_path / "cli_fid_save.csv"
    proc, data = run_cli_driver("fid", config, tmp_path, write_ini, output=target)
    assert_full_cli_scenario(proc, data)
    assert len(data["stream"]) == FID_COMMANDS
    assert hashlib.sha256(pack_stream(data["stream"])).hexdigest() == FID_SHA256
    assert pack_stream(data["stream"][:18]).hex() == FID_FIRST_18_HEX
    assert data["stdout"].splitlines() == EXPECTED_STDOUT_FID + [f"saved data to {target!s}"]


def test_cli_run_cal_pulse_stream_and_stdout(config, tmp_path, write_ini):
    target = tmp_path / "cli_cal_pulse_save.csv"
    proc, data = run_cli_driver("cal_pulse", config, tmp_path, write_ini, output=target)
    assert_full_cli_scenario(proc, data)
    assert len(data["stream"]) == CAL_PULSE_COMMANDS
    assert hashlib.sha256(pack_stream(data["stream"])).hexdigest() == CAL_PULSE_SHA256
    assert pack_stream(data["stream"][:18]).hex() == CAL_PULSE_FIRST_18_HEX
    lines = data["stdout"].splitlines()
    assert len(lines) == 13
    assert all(SWEEP_LINE.match(line) for line in lines[0:10])
    assert lines[10] == "calibrated 90° pulse width: 0.000 µs"
    assert lines[11] == "pulse calibration completed (10 points)"
    assert lines[12] == f"saved data to {target!s}"
    assert data["saved"]["exists"] is True
    saved = data["saved"]["lines"]
    assert saved[0] == "pulse_width,time,real,imag"
    cal_set = SEQUENCE_SET["cal_pulse"]
    points = len(np.arange(cal_set["start"], cal_set["stop"] + cal_set["step"], cal_set["step"], dtype=np.float32))
    size = data["stream"][-1][1]
    assert len(saved) == 1 + points * size
    for i in range(points):
        block = saved[1 + size * i : 1 + size * (i + 1)]
        assert [float(line.split(",")[0]) for line in block] == [4.0 + 3.0 * i] * size


def test_cli_run_cpmg_stream_and_stdout(config, tmp_path, write_ini):
    target = tmp_path / "cli_cpmg_save.csv"
    proc, data = run_cli_driver("cpmg", config, tmp_path, write_ini, output=target)
    assert_full_cli_scenario(proc, data)
    assert len(data["stream"]) == CPMG_COMMANDS
    assert hashlib.sha256(pack_stream(data["stream"])).hexdigest() == CPMG_SHA256
    assert pack_stream(data["stream"][:18]).hex() == CPMG_FIRST_18_HEX
    assert data["stdout"].splitlines() == EXPECTED_STDOUT_CPMG + [f"saved data to {target!s}"]


def test_cli_run_fid_save_output(config, tmp_path, write_ini):
    target = tmp_path / "cli_fid_out.csv"
    proc, data = run_cli_driver("fid", config, tmp_path, write_ini, output=target)
    assert_full_cli_scenario(proc, data)
    assert len(data["stream"]) == FID_COMMANDS
    assert hashlib.sha256(pack_stream(data["stream"])).hexdigest() == FID_SHA256
    assert pack_stream(data["stream"][:18]).hex() == FID_FIRST_18_HEX
    assert data["stdout"].splitlines() == EXPECTED_STDOUT_FID + [f"saved data to {target!s}"]
    assert data["saved"]["exists"] is True
    saved = data["saved"]["lines"]
    assert saved[0] == "time,real,imag"
    assert len(saved) == 1 + data["stream"][-1][1]


def test_cli_run_cpmg_save_output(config, tmp_path, write_ini):
    target = tmp_path / "cli_cpmg_out.csv"
    proc, data = run_cli_driver("cpmg", config, tmp_path, write_ini, output=target)
    assert_full_cli_scenario(proc, data)
    assert len(data["stream"]) == CPMG_COMMANDS
    assert hashlib.sha256(pack_stream(data["stream"])).hexdigest() == CPMG_SHA256
    assert pack_stream(data["stream"][:18]).hex() == CPMG_FIRST_18_HEX
    assert data["stdout"].splitlines() == EXPECTED_STDOUT_CPMG + [f"saved data to {target!s}"]
    assert data["saved"]["exists"] is True
    saved = data["saved"]["lines"]
    assert saved[0] == "time,real,imag"
    assert len(saved) == 1 + data["stream"][-1][1]
