import sys
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PySide6.QtWidgets import QFileDialog, QPushButton, QWidget

SAVE_DIR = Path.home() if sys.platform == "win32" else "."


class PlotWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.xdata = np.array([], np.float32)
        self.ydata = np.array([], np.float32)
        self.fit_curve = None

    def setup_plot(self, xlabel, ylabel, style):
        figure = Figure()
        if sys.platform != "win32":
            figure.set_facecolor("none")
        figure.subplots_adjust(left=0.12, bottom=0.12, right=0.98, top=0.95)
        self.axes = figure.add_subplot(111)
        self.axes.grid()
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel(ylabel)
        (self.curve,) = self.axes.plot([], [], style)
        self.canvas = FigureCanvas(figure)
        self.plotLayout.addWidget(self.canvas)
        self.toolbar = NavigationToolbar(self.canvas, self.plotWidget, False)
        actions = self.toolbar.actions()
        if int(matplotlib.__version__[0]) < 2:
            self.toolbar.removeAction(actions[7])
        else:
            self.toolbar.removeAction(actions[6])
        self.plotLayout.addWidget(self.toolbar)
        self.toolbar.addSeparator()
        self.loadDataButton = QPushButton("Load data")
        self.toolbar.addWidget(self.loadDataButton)
        self.saveDataButton = QPushButton("Save data")
        self.toolbar.addWidget(self.saveDataButton)
        self.loadDataButton.clicked.connect(self.load)
        self.saveDataButton.clicked.connect(self.save)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)

    def csv_dialog(self, title, accept, callback, select_file=None):
        try:
            dialog = QFileDialog(self, title, SAVE_DIR, "*.csv")
            dialog.setDefaultSuffix("csv")
            if select_file is not None:
                dialog.selectFile(select_file)
            dialog.setAcceptMode(accept)
            if dialog.exec() == QFileDialog.DialogCode.Accepted:
                name = dialog.selectedFiles()
                callback(name[0])
        except Exception as e:
            self.log.print(f"error: {e}")

    def save_csv(self, title, default_name, callback):
        self.csv_dialog(title, QFileDialog.AcceptMode.AcceptSave, callback, default_name)

    def load_csv(self, title, callback):
        self.csv_dialog(title, QFileDialog.AcceptMode.AcceptOpen, callback)

    def update_curve(self):
        self.curve.set_xdata(self.xdata)
        self.curve.set_ydata(self.ydata)
        self.axes.relim()
        self.axes.autoscale_view()
        self.canvas.draw()

    def draw_fit_curve(self, x, y, label):
        if self.fit_curve is not None:
            self.fit_curve.remove()
            self.fit_curve = None
        (self.fit_curve,) = self.axes.plot(x, y, color="r", linestyle="-", label=label)
        self.axes.legend()
        self.update_curve()

    def clear_fit_curve(self):
        if self.fit_curve is not None:
            self.fit_curve.remove()
            self.fit_curve = None
            self.axes.legend()

    def on_motion(self, event):
        if event.inaxes != self.axes:
            return
        x = event.xdata
        if x is None:
            return
        index = np.argmin(np.abs(self.xdata - x))
        self.xdataValue.setText(f"{self.xdata[index]:12.3f}")
        self.ydataValue.setText(f"{self.ydata[index]:12.3f}")

    def save(self):
        raise NotImplementedError

    def load(self):
        raise NotImplementedError
