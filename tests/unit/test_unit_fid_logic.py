import itertools

import numpy as np
import pytest

from sequences.fid.logic import FidLogic

pytestmark = pytest.mark.usefixtures("no_qapp")

FID_PARAMS = {
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
    "width": 10,
}


def test_command_stream(simulated_transport):
    results = FidLogic(simulated_transport).run(FID_PARAMS)
    assert results is not None
    assert len(simulated_transport.commands) == 38
    assert [c for c, d in simulated_transport.commands] == [0, 1, 5, 5, 5, 5, 2, 6] + [7, 8] * 6 + [9, 9] + [10] * 16
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
        (7, 57651792690808033),
        (8, 0),
        (7, 124),
        (8, 0),
    ]
    assert simulated_transport.commands[:18] == expected_prefix


def test_read_commands(simulated_transport):
    FidLogic(simulated_transport).run(FID_PARAMS)
    assert [d for c, d in simulated_transport.commands if c == 10] == [13] * 16


def test_scan_averaging(simulated_transport):
    counter = [0]

    def injected(size):
        counter[0] += 1
        return np.full(size * 2, counter[0], dtype=np.complex64)

    simulated_transport.read_samples = injected
    results = FidLogic(simulated_transport).run(FID_PARAMS)
    assert list(results) == [0]
    times, data = results[0]
    assert times.dtype == np.float32
    assert times.size == 13
    assert data.dtype == np.complex64
    assert data.size == 26
    assert np.all(data[0::2] == 8.5)


def test_log_line(simulated_transport):
    logs = []
    FidLogic(simulated_transport, logs.append).run(FID_PARAMS)
    assert logs == [f"scan {n}/16 completed" for n in range(1, 17)] + [
        "FID sequence completed (read time 10 µs, 16 scans)"
    ]


def test_stop(simulated_transport):
    logs = []
    logic = FidLogic(simulated_transport, logs.append)
    logic.stop()
    assert logs == ["FID sequence stopped"]
    assert logic.stopping is True
    assert simulated_transport.stopping is True


def test_read_failure(simulated_transport):
    logs = []

    def injected(size):
        return None

    simulated_transport.read_samples = injected
    results = FidLogic(simulated_transport, logs.append).run(FID_PARAMS)
    assert results is None
    assert logs == ["error: failed to read data"]


def test_stop_during_scan(simulated_transport):
    logs = []
    logic = FidLogic(simulated_transport, logs.append)
    counter = [0]

    def injected(size):
        counter[0] += 1
        if counter[0] == 1:
            logic.stopping = True
        return np.zeros(size * 2, dtype=np.complex64)

    simulated_transport.read_samples = injected
    results = logic.run(FID_PARAMS)
    assert results is None
    assert logs == ["scan 1/16 completed"]


def test_save(tmp_path, simulated_transport):
    logs = []
    logic = FidLogic(simulated_transport, logs.append)
    results = logic.run(FID_PARAMS)
    target = tmp_path / "fid.csv"
    logic.save(results, target)
    assert logs[-1] == f"saved data to {target!s}"
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 14
    rows = np.loadtxt(str(target), delimiter=",", skiprows=1)
    assert np.all(rows[:, 1] == 0.0)
    assert np.all(rows[:, 2] == 0.0)
    times = rows[:, 0]
    assert all(a <= b for a, b in itertools.pairwise(times))
    other = tmp_path / "none.csv"
    logic.save(None, other)
    assert logs[-1] == "error: no data to save"
    assert not other.exists()


def test_load(tmp_path, simulated_transport):
    logs = []
    logic = FidLogic(simulated_transport, logs.append)
    results = logic.run(FID_PARAMS)
    target = tmp_path / "fid.csv"
    logic.save(results, target)
    before = len(simulated_transport.commands)
    loaded = logic.load(target)
    assert len(simulated_transport.commands) == before
    assert list(loaded) == [0]
    run_times, run_data = results[0]
    load_times, load_data = loaded[0]
    assert load_data.dtype == np.complex64
    assert load_data.size == 26
    assert np.all(load_data[0::2] == run_data[0::2])
    assert np.all(load_data[1::2] == 0)
    assert np.array_equal(load_data, run_data)
    assert load_times.dtype == np.float32
    assert load_times.size == 13
    assert np.array_equal(load_times, run_times)
    assert logs[-1] == f"loaded data from {target!s}"


def test_zero_scans_contract(simulated_transport):
    logs = []
    results = FidLogic(simulated_transport, logs.append).run(dict(FID_PARAMS, scans="0"))
    assert results is None
    assert logs == ["error: invalid parameters"]


def test_negative_delay_contract(simulated_transport):
    logs = []
    results = FidLogic(simulated_transport, logs.append).run(dict(FID_PARAMS, width=-5))
    assert results is None
    assert [c for c, d in simulated_transport.commands] == [0, 1, 5, 5, 5, 5, 2]
    assert logs == ["error: negative delay = -5 µs"]
