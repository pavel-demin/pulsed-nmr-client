import itertools

import numpy as np

from sequences.fid.ui import X_LABEL, FidUiHelper


class FakeEvent:
    def __init__(self, inaxes, xdata):
        self.inaxes = inaxes
        self.xdata = xdata


def test_construction_and_config(qapp, fake_main_window, log_display):
    helper = FidUiHelper(fake_main_window(), log_display())
    assert helper.axes.get_xlabel() == X_LABEL
    assert X_LABEL.encode("utf-8") == b"time, \xc2\xb5s"
    assert helper.xdata.size == 0
    assert helper.results is None
    assert helper.logic is None


def test_plot_axis(qapp, fake_main_window, log_display):
    helper = FidUiHelper(fake_main_window(), log_display())
    helper.levelValue.setValue(10)
    helper.widthValue.setValue(10)
    helper.update_plot_limits()
    assert helper.xdata.dtype == np.float32
    assert helper.xdata.size == 13
    assert helper.ydata.size == 13
    assert np.all(helper.ydata == 0.0)


def test_run_trigger(qapp, fake_main_window, log_display):
    window = fake_main_window()
    log = log_display()
    helper = FidUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.widthValue.setValue(10)
    helper.start()
    assert len(window.transport.commands) == 38
    assert helper.data.size == 13
    assert np.all(helper.ydata == 0.0)
    lines = log.viewer.toPlainText().splitlines()
    assert lines[-1] == "FID sequence completed (read time 10 µs, 16 scans)"


def test_collect_params(qapp, fake_main_window, log_display):
    window = fake_main_window()
    helper = FidUiHelper(window, log_display())
    helper.levelValue.setValue(33)
    helper.widthValue.setValue(10)
    window.deltaValue.setValue(2000)
    params = helper.collect_params()
    assert params["level"] == 33
    assert params["delta"] == 2000
    assert params["freq"] == 13.24
    assert params["rate"] == 5
    assert params["blank"] == 5
    assert params["polarity"] == 1
    assert params["read_delay"] == 1
    assert params["read_time"] == 10


def test_collect_params_general(qapp, fake_main_window, log_display):
    helper = FidUiHelper(fake_main_window(), log_display())
    helper.levelValue.setValue(10)
    helper.widthValue.setValue(10)
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
    assert params["width"] == 10


def test_on_motion(qapp, fake_main_window, log_display):
    helper = FidUiHelper(fake_main_window(), log_display())
    helper.levelValue.setValue(10)
    helper.widthValue.setValue(10)
    helper.update_plot_limits()
    x = float(helper.xdata[0])
    helper.on_motion(FakeEvent(helper.axes, x))
    assert helper.xdataValue.text() == f"{x:12.3f}"
    assert helper.ydataValue.text() == f"{0.0:12.3f}"


def test_stop(qapp, fake_main_window, log_display):
    window = fake_main_window()
    log = log_display()
    helper = FidUiHelper(window, log)
    helper.levelValue.setValue(10)
    helper.widthValue.setValue(10)
    helper.start()
    helper.stop()
    lines = log.viewer.toPlainText().splitlines()
    assert lines[-1] == "FID sequence stopped"
    assert helper.logic.stopping is True
    assert window.transport.stopping is True


def test_save_csv(qapp, fake_main_window, log_display, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    window = fake_main_window()
    log = log_display()
    helper = FidUiHelper(window, log)
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
    assert lines[0] == "time,real,imag"
    assert len(lines) == 1 + 13
    rows = np.loadtxt(str(target), delimiter=",", skiprows=1)
    assert np.all(rows[:, 1] == 0.0)
    assert np.all(rows[:, 2] == 0.0)
    times = rows[:, 0]
    assert all(a <= b for a, b in itertools.pairwise(times))
    source = tmp_path / "in.csv"
    source.write_text("time,real,imag\n1.0,2.0,-3.0\n4.0,5.0,6.0\n")
    state["files"] = [str(source)]
    helper.load()
    second = tmp_path / "out2.csv"
    state["files"] = [str(second)]
    helper.save()
    assert second.exists()
    rows2 = np.loadtxt(str(second), delimiter=",", skiprows=1)
    assert np.all(rows2 == np.array([[1.0, 2.0, -3.0], [4.0, 5.0, 6.0]]))


def test_load_csv(qapp, fake_main_window, log_display, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    state["code"] = 0
    window = fake_main_window()
    log = log_display()
    helper = FidUiHelper(window, log)
    helper.load()
    assert helper.results is None
    assert log.viewer.toPlainText().splitlines() == []
    source = tmp_path / "in.csv"
    source.write_text("time,real,imag\n1.0,2.0,-3.0\n4.0,5.0,6.0\n")
    state["code"] = 1
    state["files"] = [str(source)]
    helper.load()
    assert list(helper.results) == [0]
    times, data = helper.results[0]
    assert times.dtype == np.float32
    assert np.all(times == np.array([1.0, 4.0], dtype=np.float32))
    assert data.dtype == np.complex64
    assert data.size == 4
    assert np.all(data[0::2] == np.array([2 - 3j, 5 + 6j], dtype=np.complex64))
    assert np.all(data[1::2] == 0)
    assert np.array_equal(helper.xdata, times)
    assert np.array_equal(helper.ydata, np.abs(helper.data))
    assert helper.logic is not None
    assert log.viewer.toPlainText().splitlines()[-1] == f"loaded data from {source!s}"
    target = tmp_path / "out.csv"
    state["files"] = [str(target)]
    helper.save()
    assert target.exists()
    lines = target.read_text().splitlines()
    assert lines[0] == "time,real,imag"
    assert len(lines) == 3
    rows = np.loadtxt(str(target), delimiter=",", skiprows=1)
    assert np.all(rows == np.array([[1.0, 2.0, -3.0], [4.0, 5.0, 6.0]]))
