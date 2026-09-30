import time

import numpy as np

from common.plot_widget import PlotWidget
from common.sequence_logic import PIN_KEYS, SequenceLogic


class SequenceUiHelper(PlotWidget):
    sequence_name = None
    logic_class = None
    save_title = None
    load_title = None
    name_prefix = None
    sequence_settings = []

    def __init__(self, main_window=None, log=None):
        super().__init__()
        self.main_window = main_window
        self.log = log
        self.logic = None
        self.results = None

    def preview_axis(self, reads, delays):
        base = SequenceLogic.preview(
            float(self.main_window.adcRateValue.currentText()),
            self.main_window.rateValue.currentIndex(),
        )
        self.xdata = base.compute_time(reads, delays)
        self.data = np.zeros(len(self.xdata), dtype=np.complex64)
        self.ydata = np.abs(self.data)
        self.update_curve()

    def load_config(self, config):
        for key, attr in self.sequence_settings:
            getattr(self, attr).setValue(int(config.get("sequence", key)))
        self.update_plot_limits()

    def save_config(self, config):
        for key, attr in self.sequence_settings:
            config.set("sequence", key, str(getattr(self, attr).value()))

    def general_params(self):
        window = self.main_window
        params = {
            "adc_rate": float(window.adcRateValue.currentText()),
            "rate": window.rateValue.currentIndex(),
            "freq": window.freqValue.value(),
            "polarity": window.polarityValue.currentIndex(),
            "blank": window.blankValue.value(),
            "delta": window.deltaValue.value(),
            "echo_time": window.echoTimeValue.value(),
            "read_delay": window.readDelayValue.value(),
            "read_time": window.readTimeValue.value(),
            "gain": window.gainValue.value(),
            "scans": window.scansValue.value(),
        }
        for key, index in PIN_KEYS:
            params[key] = getattr(window, key).isChecked()
        return params

    def ensure_logic(self):
        if self.logic is None:
            self.logic = self.logic_class(self.main_window.transport, self.log.print)

    def default_name(self):
        return "{}-{}.csv".format(self.name_prefix, time.strftime("%Y%m%d-%H%M%S"))

    def start(self):
        self.update_plot_limits()
        params = self.collect_params()
        self.ensure_logic()
        self.logic.transport = self.main_window.transport
        self.logic.stopping = False
        results = self.logic.run(params, on_step=self.on_step)
        if results is None:
            return
        self.results = results
        self.apply_results(results)

    def on_step(self, index, count, payload):
        self.data = payload
        self.ydata = np.abs(self.data)
        self.update_curve()

    def apply_results(self, results):
        times, data = results[0]
        self.data = data[0::2]
        self.xdata = times
        self.ydata = np.abs(self.data)
        self.update_curve()

    def stop(self):
        if self.logic is not None:
            self.logic.stop()

    def save(self):
        if not self.results:
            self.log.print("error: no data to save")
            return
        self.save_csv(self.save_title, self.default_name(), lambda path: self.logic.save(self.results, path))

    def load(self):
        self.ensure_logic()

        def on_load(path):
            results = self.logic.load(path)
            if results is None:
                return
            self.results = results
            self.apply_results(results)

        self.load_csv(self.load_title, on_load)

    def on_motion(self, event):
        if event.inaxes != self.axes:
            return
        x = event.xdata
        if x is None:
            return
        index = np.argmin(np.abs(self.xdata - x))
        self.xdataValue.setText(f"{self.motion_x(x, index):12.3f}")
        self.ydataValue.setText(f"{self.motion_y(x, index):12.3f}")

    def motion_x(self, x, index):
        return self.xdata[index]

    def motion_y(self, x, index):
        return self.ydata[index]
