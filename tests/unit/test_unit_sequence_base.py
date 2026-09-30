import warnings

import numpy as np
import pytest

from common.sequence_logic import SYNC_TIME_US, SequenceLogic


class FailingReader:
    stopping = False

    def send(self, code, data):
        pass

    def read_samples(self, size):
        return None


def test_module_constants():
    assert SYNC_TIME_US == 1


def test_rates_table():
    assert SequenceLogic.rates_122_88 == [40, 80, 160, 320, 640, 1280]
    assert SequenceLogic.rates_125 == [25, 50, 125, 250, 500, 1250]
    base = SequenceLogic(None)
    base.adc_rate = 122.88
    assert base.rate_for(0) == 40
    base.adc_rate = 125
    assert base.rate_for(0) == 25


def test_rate_for():
    base = SequenceLogic(None)
    base.adc_rate = 122.88
    assert [base.rate_for(index) for index in range(6)] == [40, 80, 160, 320, 640, 1280]
    base.adc_rate = 125
    assert [base.rate_for(index) for index in range(6)] == [25, 50, 125, 250, 500, 1250]


def test_preview():
    base = SequenceLogic.preview(125, 5)
    assert base.adc_rate == 125
    assert base.cic_rate == 50
    assert SequenceLogic.preview(122.88, 0).cic_rate == 1536
    reads = np.array([False, False, False, False, False, True], dtype=bool)
    times = np.array([1000 * 1e3, 1, 5, 10, 1, 10], dtype=np.float32)
    manual = SequenceLogic(None)
    manual.adc_rate = 122.88
    manual.cic_rate = manual.cic_rate_for(0)
    assert np.array_equal(
        SequenceLogic.preview(122.88, 0).compute_time(reads, times), manual.compute_time(reads, times)
    )


def test_set_rates_122_88(simulated_transport):
    base = SequenceLogic(simulated_transport)
    expected_rates = {0: 1536, 1: 768, 2: 384, 3: 192, 4: 96, 5: 48}
    for index in range(6):
        base.set_rates(122.88, index)
        assert base.adc_rate == 122.88
        assert base.cic_rate == expected_rates[index]
        assert simulated_transport.commands[-1] == (1, expected_rates[index])


def test_set_freq_command(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.set_freq(13.24)
    assert simulated_transport.commands == [(0, 14216341763000000)]
    base.set_freq(9.9)
    assert simulated_transport.commands[-1] == (0, 9900000 << 30 | 9900000)


def test_set_rates_commands(simulated_transport):
    base = SequenceLogic(simulated_transport)
    expected_rates = {0: 2500, 1: 1250, 2: 500, 3: 250, 4: 125, 5: 50}
    for index in range(6):
        base.set_rates(125, index)
        assert base.adc_rate == 125
        assert base.cic_rate == expected_rates[index]
        assert simulated_transport.commands[-1] == (1, expected_rates[index])


def test_set_gain_commands(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.set_gain(50)
    assert simulated_transport.commands[-1] == (2, 4095)
    base.set_gain(25)
    assert simulated_transport.commands[-1] == (2, 2048)
    base.set_gain(1)
    assert simulated_transport.commands[-1] == (2, 82)


def test_set_pin_commands(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.set_pin(0, True)
    assert simulated_transport.commands[-1] == (4, 0)
    base.set_pin(0, False)
    assert simulated_transport.commands[-1] == (5, 0)
    base.set_pin(1, True)
    assert simulated_transport.commands[-1] == (4, 1)
    base.set_pin(3, True)
    assert simulated_transport.commands[-1] == (4, 3)


def test_set_pin_string_and_bool_contract(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.set_pin(0, "0")
    assert simulated_transport.commands[-1] == (5, 0)
    base.set_pin(0, "1")
    assert simulated_transport.commands[-1] == (4, 0)
    base.set_pin(0, "true")
    assert simulated_transport.commands[-1] == (4, 0)
    base.set_pin(0, " False ")
    assert simulated_transport.commands[-1] == (5, 0)
    base.set_pin(1, True)
    assert simulated_transport.commands[-1] == (4, 1)
    base.set_pin(1, False)
    assert simulated_transport.commands[-1] == (5, 1)


def test_clear_events_command(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.set_rates(125, 5)
    base.clear_events()
    assert base.last_delay == 12500
    assert base.size == 0
    assert base.last_read == 0
    assert simulated_transport.commands[-1] == (6, 0)


def test_add_event_command_pair(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.add_event(delay=1, gate=1, level=10)
    assert simulated_transport.commands == [(7, 3277 << 44 | 1 << 41 | 124), (8, 0)]


def test_polarity_gate_flip(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.add_event(delay=1, gate=1)
    assert simulated_transport.commands[0] == (7, 1 << 41 | 124)
    base.polarity = 0
    base.add_event(delay=1, gate=1)
    assert simulated_transport.commands[2] == (7, 124)


def test_phase_encoding(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.add_event(delay=1, tx_phase=90.0, rx_phase=180.0)
    assert simulated_transport.commands[1] == (8, 536870912 << 30 | 268435456)


def test_size_accumulation_and_read_data(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.set_rates(125, 5)
    base.clear_events()
    base.add_event(delay=1000 * 1e3)
    base.add_event(delay=SYNC_TIME_US, sync=1)
    base.add_event(delay=5, gate=1)
    base.add_event(delay=10, gate=1, level=10)
    base.add_event(delay=1)
    base.add_event(delay=10, read=1)
    assert simulated_transport.commands[-1] == (9, 1250145)
    assert base.size == 0
    results = base.read_data()
    assert simulated_transport.commands[-2:] == [(9, 1099511627788), (10, 13)]
    assert base.size == 13
    assert results.dtype == np.complex64
    assert results.size == 26
    before = len(simulated_transport.commands)
    second = base.read_data()
    assert simulated_transport.commands[before:] == [(10, 13)]
    assert second.size == 26
    empty = SequenceLogic(simulated_transport)
    assert empty.read_data() is None


def test_compute_time():
    base = SequenceLogic(None)
    reads = np.array([False, False, False, False, False, True], dtype=bool)
    times = np.array([1000 * 1e3, 1, 5, 10, 1, 10], dtype=np.float32)
    results = base.compute_time(reads, times)
    assert results.dtype == np.float32
    assert results.size == 13
    assert np.isclose(results[0], 1000116.8)
    assert np.isclose(results[-1], 1000126.4)
    empty = base.compute_time(np.array([], dtype=bool), np.array([], dtype=np.float32))
    assert empty.dtype == np.float32
    assert empty.size == 0


def test_read_scan_failure():
    logs = []
    base = SequenceLogic(FailingReader())
    base.log = logs.append
    base.size = 2
    assert base.read_scan() is None
    assert logs == ["error: failed to read data"]
    assert base.read_scan(3) is None
    assert logs[-1] == "error: failed to read data at point 3"


def test_accumulate(simulated_transport, monkeypatch):
    logs = []
    calls = []

    def fake_read_samples(size):
        calls.append(size)
        return np.full(size * 2, len(calls), dtype=np.complex64)

    monkeypatch.setattr(simulated_transport, "read_samples", fake_read_samples)
    base = SequenceLogic(simulated_transport)
    base.log = logs.append
    base.size = 2
    payloads = []

    def on_step(scan, scans, payload):
        payloads.append((scan, scans, payload))

    results = base.accumulate(3, on_step)
    assert np.array_equal(results, np.full(4, 2, dtype=np.complex64))
    assert [(scan, scans) for scan, scans, _ in payloads] == [(0, 3), (1, 3), (2, 3)]
    assert np.array_equal(payloads[0][2], np.full(2, 1, dtype=np.complex64))
    assert np.array_equal(payloads[1][2], np.full(2, 1.5, dtype=np.complex64))
    assert np.array_equal(payloads[2][2], np.full(2, 2, dtype=np.complex64))
    assert logs == ["scan 1/3 completed", "scan 2/3 completed", "scan 3/3 completed"]
    assert calls == [2, 2, 2]


def test_accumulate_failure():
    logs = []
    base = SequenceLogic(FailingReader())
    base.log = logs.append
    base.size = 2
    assert base.accumulate(2, None) is None
    assert logs == ["error: failed to read data"]
    base2 = SequenceLogic(FailingReader())
    base2.stopping = True
    assert base2.accumulate(2, None) is None
    assert logs == ["error: failed to read data"]


def test_accumulate_into():
    base = SequenceLogic(None)
    samples = np.array([1, 2, 3], dtype=np.complex64)
    assert base.accumulate_into(None, samples) is samples
    other = np.array([4, 5, 6], dtype=np.complex64)
    assert np.array_equal(base.accumulate_into(samples, other), samples + other)


def test_check_delays():
    logs = []
    base = SequenceLogic(None)
    base.log = logs.append
    assert base.check_delays([1.0, -2.5]) is False
    assert "error: negative delay = -2.5 µs" in logs
    assert base.check_delays([0.0, 1.0]) is True
    silent = SequenceLogic(None)
    assert silent.check_delays([-1.0]) is False
    assert "error: negative delay = -2.5 µs" in logs


def test_stop_sets_flags(simulated_transport):
    base = SequenceLogic(simulated_transport)
    base.stop()
    assert base.stopping is True
    assert simulated_transport.stopping is True


def test_save_single_point(tmp_path):
    logs = []
    base = SequenceLogic(None)
    base.log = logs.append
    target = tmp_path / "out.csv"
    base.save(None, target)
    assert logs == ["error: no data to save"]
    assert not target.exists()
    base.save({}, target)
    assert logs == ["error: no data to save", "error: no data to save"]
    assert not target.exists()
    results = {0: (np.arange(13, dtype=np.float32), np.zeros(26, dtype=np.complex64))}
    base.save(results, target)
    assert logs[-1] == f"saved data to {target!s}"
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 14


def test_load_single_point(tmp_path, simulated_transport):
    logs = []
    base = SequenceLogic(None)
    base.log = logs.append
    assert base.load(tmp_path / "missing.csv") is None
    assert logs[-1].startswith("error:")
    path = tmp_path / "in.csv"
    path.write_text("time,real,imag\n1.0,2.0,-3.0\n4.0,5.0,6.0\n")
    results = base.load(path)
    assert list(results) == [0]
    times, data = results[0]
    assert times.dtype == np.float32
    assert np.all(times == np.array([1.0, 4.0], dtype=np.float32))
    assert data.dtype == np.complex64
    assert data.size == 4
    assert np.all(data[0::2] == np.array([2 - 3j, 5 + 6j], dtype=np.complex64))
    assert np.all(data[1::2] == 0)
    assert logs[-1] == f"loaded data from {path!s}"
    header = tmp_path / "header.csv"
    header.write_text("time,real,imag\n")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert base.load(header) is None
    assert logs[-1].startswith("error:")
    base2 = SequenceLogic(simulated_transport)
    assert base2.load(path) is not None
    assert simulated_transport.commands == []


def testsave_file(tmp_path):
    logs = []
    base = SequenceLogic(None)
    base.log = logs.append
    target = tmp_path / "out.csv"
    columns = np.column_stack(
        (np.arange(3, dtype=np.float32), np.ones(3, dtype=np.float32), np.zeros(3, dtype=np.float32))
    )
    base.save_file(target, columns, "a,b,c")
    assert logs == [f"saved data to {target!s}"]
    lines = target.read_text().splitlines()
    assert lines[0] == "a,b,c"
    assert len(lines) == 4
    base.save_file(tmp_path / "missing" / "dir" / "out.csv", columns, "a,b,c")
    assert len(logs) == 2
    assert logs[-1].startswith("error:")


def test_read_csv_rows(tmp_path):
    logs = []
    base = SequenceLogic(None)
    base.log = logs.append
    assert base.read_csv_rows(tmp_path / "missing.csv") is None
    assert len(logs) == 1
    assert logs[0].startswith("error:")
    path = tmp_path / "rows.csv"
    path.write_text("a,b,c\n1.0,2.0,3.0\n4.0,5.0,6.0\n")
    rows = base.read_csv_rows(path)
    assert rows is not None
    assert np.array_equal(rows, np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]))
    assert len(logs) == 1


def test_configure_scan_count_validation(simulated_transport):
    logs = []
    base = SequenceLogic(simulated_transport)
    base.log = logs.append
    params = {
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
        "scans": 16,
    }
    assert base.configure(params) == 16
    params["scans"] = 0
    assert base.configure(params) is None
    params["scans"] = -1
    assert base.configure(params) is None
    assert logs.count("error: invalid parameters") == 2


def test_rate_for_negative_index_contract():
    base = SequenceLogic(None)
    with pytest.raises(IndexError):
        base.rate_for(-1)
    base.adc_rate = 125
    assert [base.rate_for(i) for i in range(6)] == [25, 50, 125, 250, 500, 1250]
    base.adc_rate = 122.88
    assert [base.rate_for(i) for i in range(6)] == [40, 80, 160, 320, 640, 1280]
