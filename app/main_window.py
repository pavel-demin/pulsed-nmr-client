import configparser
from pathlib import Path

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtUiTools import loadUiType
from PySide6.QtWidgets import QFileDialog

from app.log_display import LogDisplay
from common.config import Config, sequence_classes, sequence_dir
from common.sequence_logic import GENERAL_KEYS, PIN_KEYS, SequenceLogic, pin_state
from common.transport import CONNECT_TIMEOUT_MS, create_transport, wait_for_connection

Ui_MainWindow, QMainWindow = loadUiType(str(Path(__file__).resolve().parent / "main_window.ui"))


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.running = False
        self.sequence = None
        self.transport = None
        self.log = LogDisplay(self.logViewer)
        self.adcRateValue.addItems(["122.88", "125"])
        self.adcRateValue.setCurrentIndex(1)
        self.update_rate_items()
        self.polarityValue.addItems(["neg.", "pos."])
        self.polarityValue.setCurrentIndex(1)
        rx = QRegularExpression(
            r"^((?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)|rp-[0-9A-Fa-f]{6}\.local)$"
        )
        self.addrValue.setValidator(QRegularExpressionValidator(rx, self.addrValue))
        self.loadCfgButton.clicked.connect(self.load_config)
        self.saveCfgButton.clicked.connect(self.save_config)
        self.startSeqButton.clicked.connect(self.run_seq)
        self.loadSeqButton.clicked.connect(self.choose_sequence)

        self.adcRateValue.currentIndexChanged.connect(self.update_rate_items)

    def choose_sequence(self):
        directory = QFileDialog.getExistingDirectory(self, "Select sequence directory", str(sequence_dir()))
        if not directory:
            return
        self.load_sequence(Path(directory).name)

    def load_sequence(self, name):
        if not (sequence_dir(name)).is_dir():
            self.log.print(f"error: unknown sequence {name}")
            return
        try:
            ui_class, _ = sequence_classes(name)
        except Exception as e:
            self.log.print(f"error: {e}")
            return
        if self.sequence is not None:
            self.seqContainerLayout.removeWidget(self.sequence)
            self.sequence.deleteLater()
            self.sequence = None
        sequence = ui_class(self, self.log)
        self.seqContainerLayout.addWidget(sequence)
        self.seqValue.setText(name)
        self.sequence = sequence
        try:
            self.apply_config(Config.sequence_path(name))
        except (configparser.Error, ValueError, KeyError, IndexError):
            self.log.print("error: invalid parameters")

    def update_rate_items(self):
        if self.adcRateValue.currentIndex() == 0:
            rates = [str(rate) for rate in SequenceLogic.rates_122_88]
        else:
            rates = [str(rate) for rate in SequenceLogic.rates_125]
        index = max(min(self.rateValue.currentIndex(), len(rates) - 1), 0)
        self.rateValue.clear()
        self.rateValue.addItems(rates)
        self.rateValue.setCurrentIndex(index)

    def run_seq(self):
        if self.running or self.sequence is None:
            return
        self.running = True
        transport = create_transport(self.addrValue.text(), 1001)
        self.transport = transport
        if not transport.is_connected():
            connected, error = wait_for_connection(transport, CONNECT_TIMEOUT_MS)
            if not connected:
                self.log.print(f"error: {error}")
                transport.stop()
                self.running = False
                return
        self.start_seq()
        try:
            self.sequence.start()
        finally:
            transport.stop()
            self.finish_seq()

    def set_controls_enabled(self, enabled):
        self.sequence.controlWidget.setEnabled(enabled)
        self.loadSeqButton.setEnabled(enabled)
        self.loadCfgButton.setEnabled(enabled)
        self.saveCfgButton.setEnabled(enabled)
        self.sequence.loadDataButton.setEnabled(enabled)
        self.sequence.saveDataButton.setEnabled(enabled)

    def start_seq(self):
        self.transport.stopping = False
        self.running = True
        self.startSeqButton.setText("Stop seq.")
        self.startSeqButton.clicked.disconnect()
        self.startSeqButton.clicked.connect(self.stop_seq)
        self.set_controls_enabled(False)

    def finish_seq(self):
        self.running = False
        self.startSeqButton.setText("Start seq.")
        self.startSeqButton.clicked.disconnect()
        self.startSeqButton.clicked.connect(self.run_seq)
        self.set_controls_enabled(True)

    def stop_seq(self):
        if not self.running:
            return
        if self.sequence is not None:
            self.sequence.stop()

    def apply_config(self, path):
        config = Config(path)
        config.load()
        self.addrValue.setText(config.get("general", "addr"))
        for key, attr, convert, op in GENERAL_KEYS:
            value = config.get("general", key)
            obj = getattr(self, attr)
            if op == "adc":
                obj.setCurrentIndex(0 if value == "122.88" else 1)
            elif op == "rate":
                obj.setCurrentIndex(max(0, min(convert(value), obj.count() - 1)))
            elif op == "value":
                obj.setValue(convert(value))
            else:
                obj.setCurrentIndex(convert(value))
        for key, index in PIN_KEYS:
            obj = getattr(self, key)
            obj.setChecked(pin_state(config.get("general", key)))

        self.sequence.load_config(config)

    def load_config(self):
        if self.sequence is None:
            return
        dir = str(Config.sequence_path(self.sequence.sequence_name))
        path, _ = QFileDialog.getOpenFileName(self, "Load configuration", dir, "*.ini")
        if not path:
            return
        try:
            self.apply_config(path)
        except (configparser.Error, ValueError, KeyError, IndexError):
            self.log.print("error: invalid parameters")

    def save_config(self):
        if self.sequence is None:
            return
        dir = str(Config.sequence_path(self.sequence.sequence_name))
        path, _ = QFileDialog.getSaveFileName(self, "Save configuration", dir, "*.ini")
        if not path:
            return
        config = Config(path)
        config.load()
        config.set("general", "addr", self.addrValue.text())
        for key, attr, _, op in GENERAL_KEYS:
            obj = getattr(self, attr)
            if op == "adc":
                config.set("general", key, obj.currentText())
            elif op == "rate":
                config.set("general", key, obj.currentIndex())
            elif op == "value":
                config.set("general", key, obj.value())
            else:
                config.set("general", key, obj.currentIndex())
        for key, _ in PIN_KEYS:
            obj = getattr(self, key)
            config.set("general", key, obj.isChecked())
        self.sequence.save_config(config)
        config.save()
