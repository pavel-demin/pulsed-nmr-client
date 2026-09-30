import itertools
import warnings

import numpy as np

from sequences.cal_pulse.logic import calibrate
from sequences.cal_pulse.ui import X_LABEL, CalPulseUiHelper


def test_construction_and_config(qapp, fake_main_window, log_display):
    helper = CalPulseUiHelper(fake_main_window(), log_display())
    assert helper.axes.get_xlabel() == X_LABEL
    assert X_LABEL.encode("utf-8") == b"pulse width, \xc2\xb5s"
    assert helper.xdata.size == 0
    assert helper.results is None
    assert helper.logic is None


def test_plot_axis_and_valuechanged(qapp, fake_main_window, log_display):
    helper = CalPulseUiHelper(fake_main_window(), log_display())
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    helper.update_plot_limits()
    assert helper.xdata.size == 20
    helper.stopValue.setValue(42)
    assert helper.xdata.size == 21
    helper.stopValue.setValue(40)
    assert helper.xdata.size == 20


def test_run_trigger(qapp, fake_main_window, log_display):
    window = fake_main_window()
    log = log_display()
    helper = CalPulseUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    helper.start()
    assert len(window.transport.commands) == 627
    assert len(helper.results) == 20
    assert helper.ydata.size == 20
    assert helper.fit_curve is None
    lines = log.viewer.toPlainText().splitlines()
    assert lines[-1] == "pulse calibration completed (20 points)"


def test_collect_params(qapp, fake_main_window, log_display):
    helper = CalPulseUiHelper(fake_main_window(), log_display())
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    params = helper.collect_params()
    assert params["freq"] == 13.24
    assert params["rate"] == 5
    assert params["blank"] == 5
    assert params["polarity"] == 1
    assert params["delta"] == 1000
    assert params["read_delay"] == 1
    assert params["read_time"] == 10
    assert params["level"] == 10
    assert params["start"] == 2
    assert params["stop"] == 40
    assert params["step"] == 2


def test_collect_params_general(qapp, fake_main_window, log_display):
    helper = CalPulseUiHelper(fake_main_window(), log_display())
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    params = helper.collect_params()
    assert params["adc_rate"] == 125.0
    assert params["scans"] == 16
    assert params["freq"] == 13.24
    assert params["rate"] == 5
    assert params["blank"] == 5
    assert params["polarity"] == 1
    assert params["delta"] == 1000
    assert params["read_delay"] == 1
    assert params["read_time"] == 10
    assert params["gain"] == 10
    assert params["pin0"] is False
    assert params["pin1"] is False
    assert params["pin2"] is False
    assert params["pin3"] is False
    assert params["level"] == 10
    assert params["start"] == 2
    assert params["stop"] == 40
    assert params["step"] == 2


def test_fit_curve_after_run(qapp, fake_main_window, log_display, inject_nutation):
    window = fake_main_window()
    helper = CalPulseUiHelper(window, log_display())
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    inject_nutation()
    helper.start()
    assert helper.fit_curve is not None
    pw90, _, _, fit = calibrate(helper.results)
    assert fit is not None
    x0, period, tau, coefficients = fit
    assert helper.fit_curve.get_label() == f"90° pulse width = {pw90:.2f} µs"
    grid = np.linspace(float(helper.xdata.min()), float(helper.xdata.max()), 200, dtype=np.float32)
    assert np.allclose(helper.fit_curve.get_xdata(), grid)
    a = coefficients[0]
    b = coefficients[1]
    c = coefficients[2]
    w = 2.0 * np.pi / period
    x = grid - x0
    assert np.allclose(
        helper.fit_curve.get_ydata(),
        a + np.exp(-x / tau) * (b * np.sin(w * x) + c * np.cos(w * x)),
        atol=1e-4,
    )


def test_fit_curve_after_load(qapp, fake_main_window, log_display, tmp_path, fake_file_dialog, inject_nutation):
    state = fake_file_dialog
    window = fake_main_window()
    helper = CalPulseUiHelper(window, log_display())
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    inject_nutation()
    helper.start()
    target = tmp_path / "nut.csv"
    state["code"] = 1
    state["files"] = [str(target)]
    helper.save()
    assert target.exists()
    helper2 = CalPulseUiHelper(fake_main_window(), log_display())
    state["files"] = [str(target)]
    helper2.load()
    assert helper2.fit_curve is not None
    assert np.allclose(helper.fit_curve.get_xdata(), helper2.fit_curve.get_xdata())
    assert np.allclose(helper.fit_curve.get_ydata(), helper2.fit_curve.get_ydata())


def test_stop(qapp, fake_main_window, log_display):
    window = fake_main_window()
    log = log_display()
    helper = CalPulseUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    helper.start()
    helper.stop()
    lines = log.viewer.toPlainText().splitlines()
    assert lines[-1] == "pulse calibration stopped"
    assert helper.logic.stopping is True
    assert window.transport.stopping is True


def test_save_csv(qapp, fake_main_window, log_display, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    window = fake_main_window()
    log = log_display()
    helper = CalPulseUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    target = tmp_path / "out.csv"
    state["code"] = 0
    helper.save()
    assert not target.exists()
    assert log.viewer.toPlainText().splitlines()[-1] == "error: no data to save"
    helper.start()
    state["code"] = 1
    state["files"] = [str(target)]
    helper.save()
    assert target.exists()
    lines = target.read_text().splitlines()
    assert lines[0] == "pulse_width,time,real,imag"
    assert len(lines) == 20 * 13 + 1
    for i in range(20):
        group = lines[1 + 13 * i : 1 + 13 * (i + 1)]
        assert [float(line.split(",")[0]) for line in group] == [2.0 + 2.0 * i] * 13
        times = [float(line.split(",")[1]) for line in group]
        assert all(a <= b for a, b in itertools.pairwise(times))


def test_load_csv(qapp, fake_main_window, log_display, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    helper = CalPulseUiHelper(fake_main_window(), log_display())
    source = tmp_path / "in.csv"
    source.write_text(
        "pulse_width,time,real,imag\n3.0,0.0,1.0,-2.0\n3.0,0.8,3.0,4.0\n7.0,0.0,5.0,6.0\n7.0,0.8,-1.0,2.0\n"
    )
    state["files"] = [str(source)]
    helper.load()
    assert list(helper.results) == [3.0, 7.0]
    times, data = helper.results[3.0]
    assert times.dtype == np.float32
    assert np.all(times == np.array([0.0, 0.8], dtype=np.float32))
    assert data.dtype == np.complex64
    assert data.size == 4
    assert np.all(data[0::2] == np.array([1.0 - 2j, 3.0 + 4j], dtype=np.complex64))
    assert np.all(data[1::2] == 0)
    assert np.all(helper.xdata == np.array([3.0, 7.0], dtype=np.float32))
    assert np.allclose(helper.ydata, np.array([0.7406845, 5.7145004], dtype=np.float32))
    assert helper.fit_curve is None


def test_load_error(qapp, fake_main_window, log_display, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    log = log_display()
    helper = CalPulseUiHelper(fake_main_window(), log)
    state["files"] = [str(tmp_path / "missing.csv")]
    helper.load()
    assert helper.results is None
    assert log.viewer.toPlainText().splitlines()[-1].startswith("error:")
    header = tmp_path / "header.csv"
    header.write_text("pulse_width,time,real,imag\n")
    state["files"] = [str(header)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        helper.load()
    assert helper.results is None
    assert helper.xdata.size == 0
    assert helper.fit_curve is None
