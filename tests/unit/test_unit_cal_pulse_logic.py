import itertools
import warnings

import numpy as np
import pytest

from sequences.cal_pulse.logic import (
    CalPulseLogic,
    calibrate,
    sweep_values,
)

pytestmark = pytest.mark.usefixtures("no_qapp")

CAL_PULSE_PARAMS = {
    "freq": 13.24,
    "rate": 5,
    "adc_rate": 125.0,
    "blank": 5,
    "polarity": 1,
    "gain": 10,
    "pin0": False,
    "pin1": False,
    "pin2": False,
    "pin3": False,
    "delta": 1000,
    "read_delay": 1,
    "read_time": 10,
    "scans": 16,
    "level": 10,
    "start": 2,
    "stop": 40,
    "step": 2,
}


def zero_point():
    return np.zeros(26, dtype=np.complex64), np.zeros(13, dtype=np.float32)


def test_command_stream(simulated_transport):
    results = CalPulseLogic(simulated_transport).run(CAL_PULSE_PARAMS)
    assert results is not None
    assert len(simulated_transport.commands) == 627
    assert {
        c: sum(1 for x, _ in simulated_transport.commands if x == c)
        for c in sorted({x for x, _ in simulated_transport.commands})
    } == {0: 1, 1: 1, 2: 1, 5: 4, 6: 20, 7: 120, 8: 120, 9: 40, 10: 320}
    assert [d for c, d in simulated_transport.commands if c == 10] == [13] * 320
    expected_prefix = [
        (0, 14216341763000000),
        (1, 50),
        (5, 0),
        (5, 1),
        (5, 2),
        (5, 3),
        (2, 819),
        (6, 0),
        (7, 124999999),
        (8, 0),
        (7, 1099511627900),
        (8, 0),
        (7, 2199023256176),
        (8, 0),
        (7, 57651792690807033),
        (8, 0),
        (7, 124),
        (8, 0),
    ]
    assert simulated_transport.commands[:18] == expected_prefix


def test_sweep_result(simulated_transport):
    points = []
    results = CalPulseLogic(simulated_transport).run(
        CAL_PULSE_PARAMS, on_step=lambda i, count, value: points.append((i, count, value))
    )
    assert len(results) == 20
    assert list(results) == [2.0 + 2.0 * i for i in range(20)]
    for value in results.values():
        assert value[0].dtype == np.float32
        assert value[0].size == 13
        assert value[1].dtype == np.complex64
        assert value[1].size == 26
    assert len(points) == 20
    assert [count for _, count, _ in points] == [20] * 20
    assert [value for _, _, value in points] == [0.0] * 20


def test_sweep_signal_injection(simulated_transport, inject_nutation):
    inject_nutation()
    results = CalPulseLogic(simulated_transport).run(CAL_PULSE_PARAMS)
    assert len(results) == 20


def test_peak_report(simulated_transport, inject_nutation):
    inject_nutation()
    logs = []
    CalPulseLogic(simulated_transport, logs.append).run(CAL_PULSE_PARAMS)
    assert "calibrated 90° pulse width: 7.972 µs" in logs


def test_log_lines(simulated_transport):
    logs = []
    CalPulseLogic(simulated_transport, logs.append).run(CAL_PULSE_PARAMS)
    assert len(logs) == 22
    assert logs[0] == "step 1/20: width=2.000 µs, peak=0.000"
    assert logs[19] == "step 20/20: width=40.000 µs, peak=0.000"
    assert logs[20] == "calibrated 90° pulse width: 0.000 µs"
    assert logs[-1] == "pulse calibration completed (20 points)"


def test_empty_sweep(simulated_transport):
    logs = []
    params = dict(CAL_PULSE_PARAMS, start=40, stop=2)
    results = CalPulseLogic(simulated_transport, logs.append).run(params)
    assert results == {}
    assert logs == ["pulse calibration completed (0 points)"]


def test_read_failure(simulated_transport):
    logs = []

    def injected(size):
        return None

    simulated_transport.read_samples = injected
    results = CalPulseLogic(simulated_transport, logs.append).run(CAL_PULSE_PARAMS)
    assert results is None
    assert logs == ["error: failed to read data at point 1"]


def test_stop_during_sweep(simulated_transport):
    logs = []
    logic = CalPulseLogic(simulated_transport, logs.append)
    counter = [0]

    def injected(size):
        counter[0] += 1
        if counter[0] == 16:
            logic.stopping = True
        return np.zeros(size * 2, dtype=np.complex64)

    simulated_transport.read_samples = injected
    results = logic.run(CAL_PULSE_PARAMS)
    assert results is None
    assert not any("completed" in line for line in logs)


def test_stop_line(simulated_transport):
    logs = []
    logic = CalPulseLogic(simulated_transport, logs.append)
    logic.stop()
    assert logs == ["pulse calibration stopped"]
    assert logic.stopping is True
    assert simulated_transport.stopping is True


def test_save(tmp_path, simulated_transport):
    logs = []
    logic = CalPulseLogic(simulated_transport, logs.append)
    results = logic.run(CAL_PULSE_PARAMS)
    target = tmp_path / "cal_pulse.csv"
    logic.save(results, target)
    assert logs[-1] == f"saved data to {target!s}"
    lines = target.read_text().splitlines()
    assert lines[0] == "pulse_width,time,real,imag"
    assert len(lines) == 20 * 13 + 1
    for i in range(20):
        group = lines[1 + 13 * i : 1 + 13 * (i + 1)]
        assert [float(line.split(",")[0]) for line in group] == [2.0 + 2.0 * i] * 13
        times = [float(line.split(",")[1]) for line in group]
        assert all(a <= b for a, b in itertools.pairwise(times))
        assert all(float(line.split(",")[2]) == 0.0 for line in group)
        assert all(float(line.split(",")[3]) == 0.0 for line in group)
    empty_result = logic.run(dict(CAL_PULSE_PARAMS, start=40, stop=2))
    other = tmp_path / "none.csv"
    logic.save(empty_result, other)
    assert logs[-1] == "error: no data to save"
    assert not other.exists()


def test_load(tmp_path, simulated_transport):
    logs = []
    logic = CalPulseLogic(simulated_transport, logs.append)
    results = logic.run(CAL_PULSE_PARAMS)
    target = tmp_path / "cal_pulse.csv"
    logic.save(results, target)
    before = len(simulated_transport.commands)
    loaded = logic.load(target)
    assert len(simulated_transport.commands) == before
    assert list(loaded) == list(results)
    assert list(loaded) == [2.0 + 2.0 * i for i in range(20)]
    for key in results:
        run_times, run_data = results[key]
        load_times, load_data = loaded[key]
        assert load_times.dtype == np.float32
        assert load_times.size == 13
        assert load_data.dtype == np.complex64
        assert load_data.size == 26
        assert np.array_equal(load_times, run_times)
        assert np.array_equal(load_data, run_data)
    assert logs[-1] == f"loaded data from {target!s}"
    assert logic.load(tmp_path / "missing.csv") is None
    assert logs[-1].startswith("error:")
    two = tmp_path / "two.csv"
    two.write_text("pulse_width,time,real,imag\n3.0,0.0,1.0,-2.0\n3.0,0.8,3.0,4.0\n7.0,0.0,5.0,6.0\n7.0,0.8,-1.0,2.0\n")
    loaded2 = logic.load(two)
    assert list(loaded2) == [3.0, 7.0]
    times3, data3 = loaded2[3.0]
    assert times3.dtype == np.float32
    assert np.all(times3 == np.array([0.0, 0.8], dtype=np.float32))
    assert data3.dtype == np.complex64
    assert np.all(data3[0::2] == np.array([1.0 - 1j * 2.0, 3.0 + 1j * 4.0], dtype=np.complex64))
    header = tmp_path / "header.csv"
    header.write_text("pulse_width,time,real,imag\n")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert logic.load(header) == None


def test_sweep_values():
    values = sweep_values(2, 40, 2)
    assert values.dtype == np.float32
    assert list(values) == [2.0 + 2.0 * i for i in range(20)]


def test_calibrate_zero_input():
    results = {2.0: zero_point(), 4.0: zero_point(), 6.0: zero_point()}
    pw90, widths, heights, fit = calibrate(results)
    assert pw90 == 0.0
    assert list(widths) == [2.0, 4.0, 6.0]
    assert np.all(heights == 0.0)
    assert fit is None


def test_calibrate_empty():
    pw90, widths, heights, fit = calibrate({})
    assert pw90 == 0.0
    assert widths.size == 0
    assert heights.size == 0
    assert fit is None


def test_calibrate_few_points():
    single = {5.0: (np.full(26, 1.0, dtype=np.complex64), np.zeros(13, dtype=np.float32))}
    pw90, widths, heights, fit = calibrate(single)
    assert pw90 == 0.0
    assert list(widths) == [5.0]
    assert fit is None
    pair = {
        5.0: (np.full(26, 1.0, dtype=np.complex64), np.zeros(13, dtype=np.float32)),
        7.0: (np.full(26, 4.0, dtype=np.complex64), np.zeros(13, dtype=np.float32)),
    }
    pw90, widths, heights, fit = calibrate(pair)
    assert pw90 == 0.0
    assert list(widths) == [5.0, 7.0]
    assert np.all(heights == 0.0)
    assert fit is None
    t_axis = np.arange(13, dtype=float)

    def decayed(amp):
        raw = np.zeros(26, dtype=np.complex64)
        raw[0::2] = amp * np.exp(-t_axis / 3.0) * np.exp(1j * t_axis * 0.7)
        return raw

    triple = {
        5.0: (np.zeros(13, dtype=np.float32), decayed(1.0)),
        7.0: (np.zeros(13, dtype=np.float32), decayed(4.0)),
        9.0: (np.zeros(13, dtype=np.float32), decayed(9.0)),
    }
    pw90, widths, heights, fit = calibrate(triple)
    assert pw90 == 0.0
    assert list(widths) == [5.0, 7.0, 9.0]
    assert fit is None


def test_calibrate_fit_params(simulated_transport, inject_nutation):
    inject_nutation()
    results = CalPulseLogic(simulated_transport).run(CAL_PULSE_PARAMS)
    pw90, widths, heights, fit = calibrate(results)
    assert fit is not None
    x0, period, tau, coefficients = fit
    assert pw90 == period / 4.0
    a = coefficients[0]
    b = coefficients[1]
    c = coefficients[2]
    w = 2.0 * np.pi / period
    x = widths - x0
    y = a + np.exp(-x / tau) * (b * np.sin(w * x) + c * np.cos(w * x))
    assert np.allclose(y, heights, atol=0.1)


def test_run_zero_input(simulated_transport):
    logs = []
    results = CalPulseLogic(simulated_transport, logs.append).run(CAL_PULSE_PARAMS)
    assert len(results) == 20
    assert "calibrated 90° pulse width: 0.000 µs" in logs


def test_round_trip_calibrate(tmp_path, simulated_transport, inject_nutation):
    inject_nutation()
    logic = CalPulseLogic(simulated_transport)
    results = logic.run(CAL_PULSE_PARAMS)
    target = tmp_path / "round.csv"
    logic.save(results, target)
    loaded = logic.load(target)
    pw90_run, widths_run, heights_run, fit_run = calibrate(results)
    pw90_load, widths_load, heights_load, fit_load = calibrate(loaded)
    assert fit_run is not None
    assert fit_load is not None
    assert np.isclose(fit_run[0], fit_load[0])
    assert np.isclose(pw90_run, pw90_load)
    assert np.array_equal(widths_run, widths_load)
    assert np.array_equal(heights_run, heights_load)
    assert np.isclose(pw90_run, 8.0, atol=0.05)


def test_zero_scans_contract(simulated_transport):
    logs = []
    results = CalPulseLogic(simulated_transport, logs.append).run(dict(CAL_PULSE_PARAMS, scans="0"))
    assert results is None
    assert logs == ["error: invalid parameters"]


def test_negative_delay_contract(simulated_transport):
    logs = []
    results = CalPulseLogic(simulated_transport, logs.append).run(dict(CAL_PULSE_PARAMS, start=-5, stop=-1, step=1))
    assert results is None
    assert [c for c, d in simulated_transport.commands] == [0, 1, 5, 5, 5, 5, 2]
    assert logs == ["error: negative delay = -5.0 µs"]
