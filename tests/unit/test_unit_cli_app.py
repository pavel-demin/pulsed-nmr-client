import pytest

import app.cli_app as cli_mod
from app.cli_app import CliApp
from common.config import Config
from common.sequence_logic import GENERAL_KEYS
from tests.conftest import REFERENCE_GENERAL, REFERENCE_SEQUENCE

pytestmark = pytest.mark.usefixtures("no_qapp")


def run_cli(argv, capsys):
    code = CliApp(argv).run()
    return code, capsys.readouterr().out


def test_parse_choices():
    assert CliApp(["fid", "out.csv"]).args.sequence == "fid"
    assert CliApp(["cal_pulse", "out.csv"]).args.sequence == "cal_pulse"
    assert CliApp(["cpmg", "out.csv"]).args.sequence == "cpmg"


def test_parse_rejects_unknown():
    with pytest.raises(SystemExit):
        CliApp(["bogus"])


def test_parse_rejects_unknown_option():
    with pytest.raises(SystemExit):
        CliApp(["fid", "--rate", "5"])


def test_fid_run_reports(capsys, pinned, tmp_path):
    code, out = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 0
    assert (
        f"FID sequence completed (read time {REFERENCE_GENERAL['read_time']} \u00b5s, {REFERENCE_GENERAL['scans']} scans)"
        in out
    )


def test_cal_pulse_run_reports(capsys, pinned, tmp_path):
    code, out = run_cli(["cal_pulse", str(tmp_path / "cal.csv")], capsys)
    assert code == 0
    assert "pulse calibration completed (20 points)" in out


def test_cpmg_run_reports(capsys, pinned, tmp_path):
    code, out = run_cli(["cpmg", str(tmp_path / "cpmg.csv")], capsys)
    assert code == 0
    assert "CPMG sequence completed" in out


def test_build_params_new_keys(tmp_path, write_ini):
    path = tmp_path / "general.ini"
    write_ini(path, "general", REFERENCE_GENERAL)
    config = Config(str(path))
    config.load()
    params = CliApp(["fid", "out.csv"]).build_params(config)
    for key, _, _, _ in GENERAL_KEYS:
        if key != "gain":
            assert params[key] == REFERENCE_GENERAL[key]
    rewritten = dict(REFERENCE_GENERAL)
    del rewritten["adc_rate"]
    del rewritten["scans"]
    write_ini(path, "general", rewritten)
    config = Config(str(path))
    config.load()
    params = CliApp(["fid", "out.csv"]).build_params(config)
    assert "adc_rate" not in params
    assert "scans" not in params


def test_invalid_rate_rejected(capsys, pinned, write_ini, tmp_path):
    program = dict(REFERENCE_GENERAL)
    program["rate"] = "99"
    write_ini(Config.sequence_path("fid"), {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    code, out = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 1
    assert "error: invalid parameters" in out


def test_parse_output_arg():
    with pytest.raises(SystemExit):
        CliApp(["fid"])
    assert CliApp(["fid", "out.csv"]).args.output == "out.csv"
    with pytest.raises(SystemExit):
        CliApp(["fid", "a", "b"])


def test_run_saves_output(capsys, pinned, tmp_path):
    target = tmp_path / "fid.csv"
    code = CliApp(["fid", str(target)]).run()
    out = capsys.readouterr().out
    assert code == 0
    assert f"saved data to {target!s}" in out
    assert target.exists()
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 14


def test_run_no_output_on_failure(capsys, pinned, write_ini, tmp_path):
    program = dict(REFERENCE_GENERAL)
    program["rate"] = "99"
    write_ini(Config.sequence_path("fid"), {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    target = tmp_path / "fid.csv"
    code = CliApp(["fid", str(target)]).run()
    out = capsys.readouterr().out
    assert code == 1
    assert "error: invalid parameters" in out
    assert not target.exists()


def test_run_empty_sweep_no_file(capsys, pinned, write_ini, tmp_path):
    write_ini(
        Config.sequence_path("cal_pulse"),
        {"general": REFERENCE_GENERAL, "sequence": {"level": "10", "start": "40", "stop": "2", "step": "2"}},
    )
    target = tmp_path / "cal.csv"
    code = CliApp(["cal_pulse", str(target)]).run()
    out = capsys.readouterr().out
    assert code == 0
    assert "error: no data to save" in out
    assert not target.exists()


def test_run_gain_pin_prefix(capsys, pinned, tmp_path, monkeypatch):
    original = cli_mod.create_transport
    recorded = []

    def spy(addr, port):
        transport = original(addr, port)
        recorded.append(transport)
        return transport

    monkeypatch.setattr(cli_mod, "create_transport", spy)
    code, _ = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 0
    assert recorded[0].commands[2:7] == [
        (5, 0),
        (5, 1),
        (5, 2),
        (5, 3),
        (2, int(int(REFERENCE_GENERAL["gain"]) / 50.0 * 4095 + 0.5)),
    ]
    assert len(recorded[0].commands) == 38


def test_run_gain_pin_from_config(capsys, pinned, write_ini, tmp_path, monkeypatch):
    program = dict(REFERENCE_GENERAL)
    program["gain"] = "50"
    program["pin1"] = "True"
    write_ini(Config.sequence_path("fid"), {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    original = cli_mod.create_transport
    recorded = []

    def spy(addr, port):
        transport = original(addr, port)
        recorded.append(transport)
        return transport

    monkeypatch.setattr(cli_mod, "create_transport", spy)
    code, _ = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 0
    assert recorded[0].commands[2:7] == [(5, 0), (4, 1), (5, 2), (5, 3), (2, 4095)]


def test_run_pin_from_ini_zero_one(capsys, pinned, write_ini, tmp_path, monkeypatch):
    program = dict(REFERENCE_GENERAL)
    program["pin0"] = "1"
    program["pin1"] = "0"
    write_ini(Config.sequence_path("fid"), {"general": program, "sequence": REFERENCE_SEQUENCE["fid"]})
    original = cli_mod.create_transport
    recorded = []

    def spy(addr, port):
        transport = original(addr, port)
        recorded.append(transport)
        return transport

    monkeypatch.setattr(cli_mod, "create_transport", spy)
    code, _ = run_cli(["fid", str(tmp_path / "fid.csv")], capsys)
    assert code == 0
    assert recorded[0].commands[2:6] == [(4, 0), (5, 1), (5, 2), (5, 3)]
