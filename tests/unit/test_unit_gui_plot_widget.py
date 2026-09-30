import numpy as np
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from common.plot_widget import PlotWidget


class LogStub:
    def __init__(self):
        self.lines = []

    def print(self, text):
        self.lines.append(text)


class HostPlotWidget(PlotWidget):
    def __init__(self):
        super().__init__()
        self.plotWidget = QWidget()
        self.plotLayout = QVBoxLayout(self)
        self.xdataValue = QLabel(self)
        self.ydataValue = QLabel(self)
        self.log = LogStub()
        self.saved = []
        self.loaded = []
        self.setup_plot("x label", "y label", "k-")

    def save(self):
        self.saved.append(1)

    def load(self):
        self.loaded.append(1)


class CsvPlotWidget(HostPlotWidget):
    def save(self):
        def on_save(path):
            np.savetxt(path, np.column_stack((self.xdata, self.ydata)), delimiter=",", header="x,y", comments="")
            self.log.print(f"saved data to {path}")

        self.save_csv("Save file", "test.csv", on_save)

    def load(self):
        def on_load(path):
            self.loaded_data = path

        self.load_csv("Load file", on_load)


class FakeEvent:
    def __init__(self, inaxes, xdata):
        self.inaxes = inaxes
        self.xdata = xdata


def test_setup_plot_headless(qapp):
    widget = HostPlotWidget()
    assert widget.axes is not None
    assert widget.canvas is not None
    assert widget.toolbar is not None
    assert widget.curve is not None
    assert widget.axes.get_xlabel() == "x label"
    assert widget.axes.get_ylabel() == "y label"


def test_update_curve(qapp):
    widget = HostPlotWidget()
    widget.xdata = np.array([0.0, 1.0, 2.0], dtype=np.float32)
    widget.ydata = np.array([0.0, 1.0, 0.5], dtype=np.float32)
    widget.update_curve()
    assert np.all(widget.curve.get_xdata() == widget.xdata)
    assert np.all(widget.curve.get_ydata() == widget.ydata)


def test_draw_fit_curve(qapp):
    widget = HostPlotWidget()
    widget.xdata = np.array([0.0, 1.0, 2.0], dtype=np.float32)
    widget.ydata = np.array([0.0, 1.0, 0.5], dtype=np.float32)
    grid = np.array([0.5, 1.0, 1.5], dtype=np.float32)
    values = np.array([0.5, 1.0, 0.75], dtype=np.float32)
    widget.draw_fit_curve(grid, values, "fit one")
    assert widget.fit_curve is not None
    assert widget.fit_curve.get_label() == "fit one"
    assert np.all(widget.fit_curve.get_xdata() == grid)
    assert np.all(widget.fit_curve.get_ydata() == values)
    widget.draw_fit_curve(grid, values, "fit two")
    labels = [line.get_label() for line in widget.axes.get_lines()]
    assert labels.count("fit two") == 1
    assert "fit one" not in labels
    widget.clear_fit_curve()
    assert widget.fit_curve is None
    labels = [line.get_label() for line in widget.axes.get_lines()]
    assert "fit two" not in labels


def test_on_motion(qapp):
    widget = HostPlotWidget()
    widget.xdata = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    widget.ydata = np.array([10.0, 20.0, 30.0], dtype=np.float32)
    widget.on_motion(FakeEvent(None, 2.5))
    assert widget.xdataValue.text() == ""
    widget.on_motion(FakeEvent(widget.axes, None))
    assert widget.xdataValue.text() == ""
    widget.on_motion(FakeEvent(widget.axes, 2.5))
    assert widget.xdataValue.text() == f"{2.0:12.3f}"
    assert widget.ydataValue.text() == f"{20.0:12.3f}"


def test_save_load_csv_with_fake_dialog(qapp, tmp_path, fake_file_dialog):
    state = fake_file_dialog
    widget = CsvPlotWidget()
    widget.xdata = np.array([0.0, 1.0], dtype=np.float32)
    widget.ydata = np.array([1.0, 2.0], dtype=np.float32)
    target = tmp_path / "out.csv"
    state["code"] = 0
    widget.save()
    assert not target.exists()
    assert widget.log.lines == []
    state["code"] = 1
    state["files"] = [str(target)]
    widget.save()
    assert target.exists()
    assert widget.log.lines == [f"saved data to {target!s}"]
    source = tmp_path / "in.csv"
    with open(str(source), "w") as handle:
        handle.write("x,y\n1,2\n3,4\n")
    state["files"] = [str(source)]
    widget.load()
    assert widget.loaded_data == str(source)
    assert widget.log.lines == [f"saved data to {target!s}"]


def test_data_buttons_on_toolbar(qapp):
    widget = HostPlotWidget()
    assert widget.saveDataButton.text() == "Save data"
    assert widget.loadDataButton.text() == "Load data"
    assert widget.saveDataButton.parent() is widget.toolbar
    assert widget.loadDataButton.parent() is widget.toolbar
    assert widget.saveDataButton.isEnabled() is True
    assert widget.loadDataButton.isEnabled() is True
    widget.loadDataButton.click()
    widget.saveDataButton.click()
    assert widget.loaded == [1]
    assert widget.saved == [1]
