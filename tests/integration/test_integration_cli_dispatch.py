from app.cli_app import CliApp
from common.config import Config
from tests.conftest import REFERENCE_GENERAL, REFERENCE_SEQUENCE


def run_cli(argv, capsys):
    code = CliApp(argv).run()
    captured = capsys.readouterr()
    return code, captured.out


def test_cli_fid_dispatch_config_values(capsys, pinned, tmp_path):
    code, out = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 0
    assert (
        f"FID sequence completed (read time {REFERENCE_GENERAL['read_time']} \u00b5s, {REFERENCE_GENERAL['scans']} scans)"
        in out
    )


def test_cli_cal_pulse_dispatch_config_values(capsys, pinned, tmp_path):
    code, out = run_cli(["cal_pulse", str(tmp_path / "cal_pulse.csv")], capsys)
    assert code == 0
    assert "pulse calibration completed (20 points)" in out


def test_cli_cpmg_dispatch_config_values(capsys, pinned, tmp_path):
    code, out = run_cli(["cpmg", str(tmp_path / "cpmg.csv")], capsys)
    assert code == 0
    assert (
        f"CPMG sequence completed ({REFERENCE_SEQUENCE['cpmg']['echoes']} echoes, {REFERENCE_GENERAL['scans']} scans)"
        in out
    )


def test_cli_fid_config_read_time(capsys, pinned, write_ini, tmp_path):
    program = dict(REFERENCE_GENERAL)
    program["read_time"] = "20"
    write_ini(Config.sequence_path("fid"), {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    code, out = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 0
    assert (
        f"FID sequence completed (read time {int(program['read_time'])} \u00b5s, {int(program['scans'])} scans)" in out
    )


def test_cli_cpmg_config_echoes(capsys, pinned, write_ini, tmp_path):
    sequence = dict(REFERENCE_SEQUENCE["cpmg"])
    sequence["echoes"] = "4"
    write_ini(Config.sequence_path("cpmg"), {"general": REFERENCE_GENERAL, "sequence": sequence})
    code, out = run_cli(["cpmg", str(tmp_path / "cpmg.csv")], capsys)
    assert code == 0
    assert f"CPMG sequence completed ({sequence['echoes']} echoes, {REFERENCE_GENERAL['scans']} scans)" in out


def test_cli_invalid_rate_contract(capsys, pinned, write_ini, tmp_path):
    program = dict(REFERENCE_GENERAL)
    program["rate"] = "99"
    write_ini(Config.sequence_path("fid"), {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    code, out = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 1
    assert "error: invalid parameters" in out


def test_cli_fid_save_output(capsys, pinned, tmp_path):
    target = tmp_path / "fid.csv"
    code, out = run_cli(["fid", str(target)], capsys)
    assert code == 0
    assert "FID sequence completed" in out
    assert f"saved data to {target!s}" in out
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 14


def test_cli_cpmg_save_output(capsys, pinned, tmp_path):
    target = tmp_path / "cpmg.csv"
    code, out = run_cli(["cpmg", str(target)], capsys)
    assert code == 0
    assert f"saved data to {target!s}" in out
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 131


def test_cli_invalid_scans_contract(capsys, pinned, write_ini, tmp_path):
    program = dict(REFERENCE_GENERAL)
    program["scans"] = "0"
    write_ini(Config.sequence_path("fid"), {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    code, out = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 1
    assert "error: invalid parameters" in out


def test_cli_negative_rate_contract(capsys, pinned, write_ini, tmp_path):
    program = dict(REFERENCE_GENERAL)
    program["rate"] = "-1"
    write_ini(Config.sequence_path("fid"), {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    code, out = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 1
    assert "error: invalid parameters" in out
