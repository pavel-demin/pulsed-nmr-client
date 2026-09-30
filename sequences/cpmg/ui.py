from pathlib import Path

from PySide6.QtUiTools import loadUiType

from common.sequence_ui import SequenceUiHelper
from sequences.cpmg.logic import CpmgLogic, cpmg_delays, cpmg_event_arrays

Ui_CpmgDisplay, QWidget = loadUiType(str(Path(__file__).resolve().parent / "layout.ui"))

X_LABEL = "time, µs"
Y_LABEL = "signal amplitude"


class CpmgUiHelper(SequenceUiHelper, Ui_CpmgDisplay):
    sequence_name = "cpmg"
    logic_class = CpmgLogic
    save_title = "Save CPMG file"
    load_title = "Load CPMG file"
    name_prefix = "cpmg"
    sequence_settings = [("level", "levelValue"), ("width", "widthValue"), ("echoes", "echoesValue")]

    def __init__(self, main_window, log):
        super().__init__(main_window, log)
        self.setupUi(self)
        self.setup_plot(X_LABEL, Y_LABEL, "")

    def collect_params(self):
        return dict(
            self.general_params(),
            level=self.levelValue.value(),
            width=self.widthValue.value(),
            echoes=self.echoesValue.value(),
        )

    def update_plot_limits(self):
        delta = self.main_window.deltaValue.value() * 1e3
        blank = self.main_window.blankValue.value()
        p90 = self.widthValue.value()
        p180 = 2.0 * p90
        echo_time = self.main_window.echoTimeValue.value()
        echoes = self.echoesValue.value()
        read_delay = self.main_window.readDelayValue.value()
        read_time = self.main_window.readTimeValue.value()
        read_time, d1, d2, d3 = cpmg_delays(p90, echo_time, blank, read_delay, read_time)
        reads, delays = cpmg_event_arrays(delta, blank, p90, p180, d1, d2, d3, read_time, echoes)
        self.preview_axis(reads, delays)
