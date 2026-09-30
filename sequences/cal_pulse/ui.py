from pathlib import Path

import numpy as np
from PySide6.QtUiTools import loadUiType

from common.sequence_logic import sweep_values
from common.sequence_ui import SequenceUiHelper
from sequences.cal_pulse.logic import CalPulseLogic, calibrate

Ui_CalPulseDisplay, QWidget = loadUiType(str(Path(__file__).resolve().parent / "layout.ui"))

X_LABEL = "pulse width, µs"
Y_LABEL = "peak intensity"


class CalPulseUiHelper(SequenceUiHelper, Ui_CalPulseDisplay):
    sequence_name = "cal_pulse"
    logic_class = CalPulseLogic
    save_title = "Save pulse calibration file"
    load_title = "Load pulse calibration file"
    name_prefix = "cal-pulse"
    sequence_settings = [
        ("level", "levelValue"),
        ("start", "startValue"),
        ("stop", "stopValue"),
        ("step", "stepValue"),
    ]

    def __init__(self, main_window, log):
        super().__init__(main_window, log)
        self.setupUi(self)
        self.setup_plot(X_LABEL, Y_LABEL, "o-")
        self.startValue.valueChanged.connect(self.update_plot_limits)
        self.stopValue.valueChanged.connect(self.update_plot_limits)
        self.stepValue.valueChanged.connect(self.update_plot_limits)

    def collect_params(self):
        return dict(
            self.general_params(),
            level=self.levelValue.value(),
            start=self.startValue.value(),
            stop=self.stopValue.value(),
            step=self.stepValue.value(),
        )

    def update_plot_limits(self):
        self.clear_fit_curve()
        self.xdata = sweep_values(self.startValue.value(), self.stopValue.value(), self.stepValue.value())
        self.ydata = np.zeros(self.xdata.size, dtype=float)
        self.update_curve()

    def on_step(self, index, count, payload):
        self.ydata[index] = payload
        self.update_curve()

    def apply_results(self, results):
        pw90, widths, heights, fit = calibrate(results)
        self.xdata = widths
        self.ydata = heights
        if fit is None:
            self.update_curve()
            return
        x0, period, tau, coefficients = fit
        grid = np.linspace(float(widths.min()), float(widths.max()), 200, dtype=float)
        a = coefficients[0]
        b = coefficients[1]
        c = coefficients[2]
        w = 2.0 * np.pi / period
        x = grid - x0
        y = a + np.exp(-x / tau) * (b * np.sin(w * x) + c * np.cos(w * x))

        self.draw_fit_curve(grid, y, f"90° pulse width = {pw90:.2f} µs")
