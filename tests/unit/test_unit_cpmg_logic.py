import itertools

import numpy as np
import pytest

from sequences.cpmg.logic import CpmgLogic, cpmg_delays, cpmg_event_arrays

pytestmark = pytest.mark.usefixtures("no_qapp")

CPMG_PARAMS = {
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
    "echo_time": 200,
    "read_delay": 1,
    "read_time": 10,
    "scans": 16,
    "level": 50,
    "width": 50,
    "echoes": 10,
}


def test_command_stream(simulated_transport):
    results = CpmgLogic(simulated_transport).run(CPMG_PARAMS)
    assert results is not None
    assert len(simulated_transport.commands) == 2135
    assert {
        c: sum(1 for x, _ in simulated_transport.commands if x == c)
        for c in sorted({x for x, _ in simulated_transport.commands})
    } == {0: 1, 1: 1, 2: 1, 5: 4, 6: 16, 7: 880, 8: 880, 9: 336, 10: 16}
    for scan in range(8):
        block = simulated_transport.commands[7 + 133 * scan : 7 + 133 * (scan + 1)]
        codes = [c for c, d in block]
        assert len(codes) == 133
        assert sum(1 for c in codes if c == 9) == 21


def test_read_chunk_size(simulated_transport):
    CpmgLogic(simulated_transport).run(CPMG_PARAMS)
    assert [d for c, d in simulated_transport.commands if c == 10] == [130] * 16


def test_scan_accumulation(simulated_transport):
    counter = [0]
    payloads = []

    def injected(size):
        counter[0] += 1
        return np.full(size * 2, counter[0], dtype=np.complex64)

    simulated_transport.read_samples = injected
    results = CpmgLogic(simulated_transport).run(
        CPMG_PARAMS, on_step=lambda i, count, value: payloads.append(value.size)
    )
    assert payloads == [130] * 16
    assert list(results) == [0]
    times, data = results[0]
    assert times.dtype == np.float32
    assert times.size == 130
    assert data.dtype == np.complex64
    assert data.size == 260
    assert np.all(data[0::2] == 8.5)


def test_read_time_clamp(simulated_transport):
    params = dict(CPMG_PARAMS, width=5, echo_time=25)
    results = CpmgLogic(simulated_transport).run(params)
    assert results is not None
    read_time = 25 - 5 - 2.0 * 5 - 1
    d1 = 25 / 2.0 - 5 / 2.0 - (2.0 * 5) / 2.0 - 5
    d3 = 25 - 5 - 2.0 * 5 - 1 - read_time
    assert read_time == 9
    assert d1 == 0
    assert d3 == 0
    assert [d for c, d in simulated_transport.commands if c == 10] == [110] * 16


def test_cpmg_delays_clamp():
    read_time, d1, d2, d3 = cpmg_delays(5, 25, 5, 1, 10)
    assert read_time == 9
    assert d1 == 0
    assert d2 == 1
    assert d3 == 0


def test_cpmg_delays_no_clamp():
    read_time, d1, d2, d3 = cpmg_delays(50, 200, 5, 1, 10)
    assert read_time == 10
    assert d1 == 20
    assert d2 == 1
    assert d3 == 84


def test_cpmg_event_arrays():
    reads, delays = cpmg_event_arrays(1000 * 1e3, 5, 50, 100.0, 20, 1, 84, 10, 10)
    assert reads.dtype == bool
    assert reads.size == 55
    assert [index for index, value in enumerate(reads) if value] == list(range(8, 55, 5))
    assert delays.dtype == np.float32
    assert delays.size == 55
    assert np.array_equal(delays[:5], np.array([1000 * 1e3, 1, 5, 50, 20], dtype=np.float32))
    assert np.array_equal(delays[5:10], np.array([5, 100.0, 1, 10, 84], dtype=np.float32))


def test_cpmg_event_arrays_zero_d3():
    reads, delays = cpmg_event_arrays(1000 * 1e3, 5, 5, 10.0, 0, 1, 0, 9, 4)
    assert reads.size == 25
    assert [index for index, value in enumerate(reads) if value] == [8, 13, 18, 23]
    assert np.array_equal(delays[5:10], np.array([5, 10.0, 1, 9, 0], dtype=np.float32))


def test_delay_guard(simulated_transport):
    logs = []
    params = dict(CPMG_PARAMS, width=500, echo_time=100)
    results = CpmgLogic(simulated_transport, logs.append).run(params)
    assert results is None
    assert [c for c, d in simulated_transport.commands] == [0, 1, 5, 5, 5, 5, 2]
    assert "error: negative delay = -705.0 µs" in logs
    logs = []
    before = len(simulated_transport.commands)
    params = dict(CPMG_PARAMS, read_delay=-1)
    results = CpmgLogic(simulated_transport, logs.append).run(params)
    assert results is None
    assert [c for c, d in simulated_transport.commands[before:]] == [0, 1, 5, 5, 5, 5, 2]
    assert logs == ["error: negative delay = -1 µs"]


def test_log_lines(simulated_transport):
    logs = []
    CpmgLogic(simulated_transport, logs.append).run(CPMG_PARAMS)
    assert logs == [f"scan {scan + 1}/16 completed" for scan in range(16)] + [
        "CPMG sequence completed (10 echoes, 16 scans)"
    ]


def test_read_failure(simulated_transport):
    logs = []

    def injected(size):
        return None

    simulated_transport.read_samples = injected
    results = CpmgLogic(simulated_transport, logs.append).run(CPMG_PARAMS)
    assert results is None
    assert logs == ["error: failed to read data"]


def test_save(tmp_path, simulated_transport):
    logs = []
    logic = CpmgLogic(simulated_transport, logs.append)
    results = logic.run(CPMG_PARAMS)
    target = tmp_path / "cpmg.csv"
    logic.save(results, target)
    assert logs[-1] == f"saved data to {target!s}"
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 131
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
    logic = CpmgLogic(simulated_transport, logs.append)
    results = logic.run(CPMG_PARAMS)
    target = tmp_path / "cpmg.csv"
    logic.save(results, target)
    before = len(simulated_transport.commands)
    loaded = logic.load(target)
    assert len(simulated_transport.commands) == before
    assert list(loaded) == [0]
    run_times, run_data = results[0]
    load_times, load_data = loaded[0]
    assert load_data.dtype == np.complex64
    assert load_data.size == 260
    assert np.all(load_data[0::2] == run_data[0::2])
    assert np.all(load_data[1::2] == 0)
    assert np.array_equal(load_data, run_data)
    assert load_times.dtype == np.float32
    assert load_times.size == 130
    assert np.array_equal(load_times, run_times)
    assert logs[-1] == f"loaded data from {target!s}"


def test_zero_scans_contract(simulated_transport):
    logs = []
    results = CpmgLogic(simulated_transport, logs.append).run(dict(CPMG_PARAMS, scans="0"))
    assert results is None
    assert logs == ["error: invalid parameters"]
