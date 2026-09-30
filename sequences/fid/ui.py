from pathlib import Path

import numpy as np
from PySide6.QtUiTools import loadUiType

from common.sequence_logic import SYNC_TIME_US
from common.sequence_ui import SequenceUiHelper
from sequences.fid.logic import FidLogic

Ui_FidDisplay, QWidget = loadUiType(str(Path(__file__).resolve().parent / "layout.ui"))

X_LABEL = "time, µs"
Y_LABEL = "signal amplitude"


class FidUiHelper(SequenceUiHelper, Ui_FidDisplay):
    sequence_name = "fid"
    logic_class = FidLogic
    save_title = "Save FID file"
    load_title = "Load FID file"
    name_prefix = "fid"
    sequence_settings = [("level", "levelValue"), ("width", "widthValue")]

    def __init__(self, main_window, log):
        super().__init__(main_window, log)
        self.setupUi(self)
        self.setup_plot(X_LABEL, Y_LABEL, "")

    def collect_params(self):
        return dict(
            self.general_params(),
            level=self.levelValue.value(),
            width=self.widthValue.value(),
        )

    def update_plot_limits(self):
        delta = self.main_window.deltaValue.value() * 1e3
        blank = self.main_window.blankValue.value()
        p90 = self.widthValue.value()
        read_delay = self.main_window.readDelayValue.value()
        read_time = self.main_window.readTimeValue.value()
        reads = np.array([False, False, False, False, False, True], dtype=bool)
        delays = np.array([delta, SYNC_TIME_US, blank, p90, read_delay, read_time], dtype=np.float32)
        self.preview_axis(reads, delays)
