import hashlib

import numpy as np

from sequences.cal_pulse.logic import calibrate
from sequences.cal_pulse.ui import CalPulseUiHelper
from sequences.cpmg.ui import CpmgUiHelper
from sequences.fid.ui import FidUiHelper
from tests.conftest import pack_stream

FID_SHA256 = "5c5cde4e401a0ddfbe81161f0611474a26cfe141a3f98b93a895f0d18ab900ae"
CAL_SHA256 = "24549db47f52b4697edeb531bf3465e24ae4c00fee9938ef9627e27d496d80e9"
CAL_PULSE_SHA256 = "24549db47f52b4697edeb531bf3465e24ae4c00fee9938ef9627e27d496d80e9"
CPMG_SHA256 = "d23ffca2555d17e2d66295f279d14fe11f107b52308804c17c14fcd0ec495895"


def inject_hump(transport):
    counter = [0]
    original_read = transport.read_samples

    def injected(size):
        counter[0] += 1
        original_read(size)
        sweep_value = 2.0 + 2.0 * ((counter[0] - 1) // 16)
        return np.full(size * 2, 100.0 / (1.0 + ((sweep_value - 10.0) / 2.0) ** 2), dtype=np.complex64)

    transport.read_samples = injected


def inject_nutation(transport, pw90=8.0):
    counter = [0]
    original_read = transport.read_samples

    def injected(size):
        counter[0] += 1
        original_read(size)
        sweep_value = 2.0 + 2.0 * ((counter[0] - 1) // 16)
        return np.full(size * 2, np.sin((np.pi / 2.0) * sweep_value / pw90), dtype=np.complex64)

    transport.read_samples = injected


def test_fid_config_to_widget_to_wire(qapp, fake_main_window, log_display, pinned):
    window = fake_main_window()
    log = log_display()
    helper = FidUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.widthValue.setValue(10)
    helper.update_plot_limits()
    assert (helper.levelValue.value(), helper.widthValue.value()) == (10, 10)
    assert helper.xdata.dtype == np.float32
    assert helper.xdata.size == 13
    helper.start()
    commands = window.transport.commands
    assert len(commands) == 38
    assert hashlib.sha256(pack_stream(commands)).hexdigest() == FID_SHA256
    assert helper.data.size == 13
    assert np.allclose(helper.ydata, np.abs(helper.data))
    lines = log.viewer.toPlainText().splitlines()
    assert lines[-1] == "FID sequence completed (read time 10 µs, 16 scans)"


def test_cal_pulse_config_to_widget_to_wire(qapp, fake_main_window, log_display, pinned):
    window = fake_main_window()
    log = log_display()
    helper = CalPulseUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    helper.update_plot_limits()
    assert (
        helper.levelValue.value(),
        helper.startValue.value(),
        helper.stopValue.value(),
        helper.stepValue.value(),
    ) == (
        10,
        2,
        40,
        2,
    )
    assert helper.xdata.dtype == np.float32
    assert helper.xdata.size == 20
    helper.start()
    commands = window.transport.commands
    assert len(commands) == 627
    assert hashlib.sha256(pack_stream(commands)).hexdigest() == CAL_PULSE_SHA256
    assert helper.ydata.size == 20
    assert helper.fit_curve is None
    lines = log.viewer.toPlainText().splitlines()
    assert lines[0] == "step 1/20: width=2.000 µs, peak=0.000"
    assert lines[-1] == "pulse calibration completed (20 points)"


def test_cpmg_config_to_widget_to_wire(qapp, fake_main_window, log_display, pinned):
    window = fake_main_window()
    log = log_display()
    helper = CpmgUiHelper(window, log)
    helper.levelValue.setValue(50)
    helper.widthValue.setValue(50)
    helper.echoesValue.setValue(10)
    helper.update_plot_limits()
    assert (helper.levelValue.value(), helper.widthValue.value(), helper.echoesValue.value()) == (50, 50, 10)
    assert helper.xdata.dtype == np.float32
    assert helper.xdata.size == 130
    helper.start()
    commands = window.transport.commands
    assert len(commands) == 2135
    assert hashlib.sha256(pack_stream(commands)).hexdigest() == CPMG_SHA256
    assert helper.data.size == 130
    assert np.allclose(helper.ydata, np.abs(helper.data))
    lines = log.viewer.toPlainText().splitlines()
    assert lines[-1] == "CPMG sequence completed (10 echoes, 16 scans)"


def test_fid_widget_value_reaches_wire(qapp, fake_main_window, log_display, pinned):
    window = fake_main_window()
    helper = FidUiHelper(window, log_display())
    helper.levelValue.setValue(10)
    helper.widthValue.setValue(20)
    helper.start()
    assert window.transport.commands[14] == (7, 57651792690809283)


def test_cpmg_widget_value_reaches_wire(qapp, fake_main_window, log_display, pinned):
    window = fake_main_window()
    log = log_display()
    helper = CpmgUiHelper(window, log)
    helper.levelValue.setValue(50)
    helper.widthValue.setValue(50)
    helper.echoesValue.setValue(4)
    helper.start()
    commands = window.transport.commands
    assert [data for code, data in commands if code == 10] == [52] * 16
    assert helper.data.size == 52
    lines = log.viewer.toPlainText().splitlines()
    assert lines[-1] == "CPMG sequence completed (4 echoes, 16 scans)"


def test_cal_pulse_widget_value_reaches_wire(qapp, fake_main_window, log_display, pinned):
    window = fake_main_window()
    log = log_display()
    helper = CalPulseUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stepValue.setValue(2)
    helper.stopValue.setValue(42)
    helper.start()
    commands = window.transport.commands
    assert [data for code, data in commands if code == 10] == [13] * 336
    assert helper.ydata.size == 21
    lines = log.viewer.toPlainText().splitlines()
    assert lines[20] == "step 21/21: width=42.000 µs, peak=0.000"
    assert lines[-1] == "pulse calibration completed (21 points)"


def test_fid_load_wiring(qapp, fake_main_window, log_display, pinned, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    window = fake_main_window()
    log = log_display()
    helper = FidUiHelper(window, log)
    helper.start()
    assert len(helper.logic.transport.commands) == 38
    run_csv = tmp_path / "fid_run.csv"
    state["code"] = 1
    state["files"] = [str(run_csv)]
    helper.save()
    assert run_csv.exists()
    window2 = fake_main_window()
    log2 = log_display()
    helper2 = FidUiHelper(window2, log2)
    state["code"] = 1
    state["files"] = [str(run_csv)]
    helper2.load()
    assert len(helper2.logic.transport.commands) == 38
    assert list(helper2.results) == list(helper.results)
    for key in helper.results:
        run_times, run_data = helper.results[key]
        load_times, load_data = helper2.results[key]
        assert np.array_equal(load_data, run_data)
        assert np.array_equal(load_times, run_times)
    assert np.array_equal(helper2.xdata, helper.xdata)
    assert np.array_equal(helper2.ydata, helper.ydata)
    reload_csv = tmp_path / "fid_reload.csv"
    state["code"] = 1
    state["files"] = [str(reload_csv)]
    helper2.save()
    assert reload_csv.read_bytes() == run_csv.read_bytes()


def test_cal_pulse_load_wiring(qapp, fake_main_window, log_display, pinned, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    window = fake_main_window()
    log = log_display()
    helper = CalPulseUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.startValue.setValue(2)
    helper.stopValue.setValue(40)
    helper.stepValue.setValue(2)
    inject_nutation(window.transport)
    helper.start()
    assert len(helper.logic.transport.commands) == 627
    run_csv = tmp_path / "cal_pulse_run.csv"
    state["code"] = 1
    state["files"] = [str(run_csv)]
    helper.save()
    assert run_csv.exists()
    window2 = fake_main_window()
    log2 = log_display()
    helper2 = CalPulseUiHelper(window2, log2)
    helper2.levelValue.setValue(10)
    helper2.startValue.setValue(2)
    helper2.stopValue.setValue(40)
    helper2.stepValue.setValue(2)
    state["code"] = 1
    state["files"] = [str(run_csv)]
    helper2.load()
    assert len(helper2.logic.transport.commands) == 627
    assert list(helper2.results) == list(helper.results)
    for key in helper.results:
        run_times, run_data = helper.results[key]
        load_times, load_data = helper2.results[key]
        assert np.array_equal(load_times, run_times)
        assert np.all(load_data[0::2] == run_data[0::2])
        assert np.all(load_data[1::2] == 0)
    assert np.array_equal(helper2.xdata, helper.xdata)
    assert np.array_equal(helper2.ydata, helper.ydata)
    assert helper.fit_curve is not None
    assert helper2.fit_curve is not None
    pw90, _, _, fit = calibrate(helper2.results)
    assert fit is not None
    assert helper.fit_curve.get_label() == f"90° pulse width = {pw90:.2f} µs"
    assert helper2.fit_curve.get_label() == f"90° pulse width = {pw90:.2f} µs"
    assert np.allclose(helper.fit_curve.get_xdata(), helper2.fit_curve.get_xdata())
    assert np.allclose(helper.fit_curve.get_ydata(), helper2.fit_curve.get_ydata())
    reload_csv = tmp_path / "cal_pulse_reload.csv"
    state["code"] = 1
    state["files"] = [str(reload_csv)]
    helper2.save()
    assert reload_csv.read_bytes() == run_csv.read_bytes()


def test_cpmg_load_wiring(qapp, fake_main_window, log_display, pinned, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    window = fake_main_window()
    log = log_display()
    helper = CpmgUiHelper(window, log)
    helper.levelValue.setValue(50)
    helper.widthValue.setValue(50)
    helper.echoesValue.setValue(10)
    helper.start()
    assert len(helper.logic.transport.commands) == 2135
    run_csv = tmp_path / "cpmg_run.csv"
    state["code"] = 1
    state["files"] = [str(run_csv)]
    helper.save()
    assert run_csv.exists()
    window2 = fake_main_window()
    log2 = log_display()
    helper2 = CpmgUiHelper(window2, log2)
    helper2.levelValue.setValue(50)
    helper2.widthValue.setValue(50)
    helper2.echoesValue.setValue(10)
    state["code"] = 1
    state["files"] = [str(run_csv)]
    helper2.load()
    assert len(helper2.logic.transport.commands) == 2135
    assert list(helper2.results) == list(helper.results)
    for key in helper.results:
        run_times, run_data = helper.results[key]
        load_times, load_data = helper2.results[key]
        assert np.array_equal(load_data, run_data)
        assert np.array_equal(load_times, run_times)
    assert np.array_equal(helper2.xdata, helper.xdata)
    assert np.array_equal(helper2.ydata, helper.ydata)
    reload_csv = tmp_path / "cpmg_reload.csv"
    state["code"] = 1
    state["files"] = [str(reload_csv)]
    helper2.save()
    assert reload_csv.read_bytes() == run_csv.read_bytes()
