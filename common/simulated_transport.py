import numpy as np
from PySide6.QtCore import QObject, Signal


class SimulatedTransport(QObject):
    connected = Signal()
    errorOccurred = Signal(str)

    def __init__(self, addr, port=1001):
        super().__init__()
        self.addr = addr
        self.port = port
        self.stopping = False
        self.connected_state = True
        self.commands = []

    def is_connected(self):
        return self.connected_state

    def send(self, code, data):
        self.commands.append((int(code), int(data)))

    def read_samples(self, size):
        self.commands.append((10, int(size)))
        return np.zeros(size * 2, dtype=np.complex64)

    def start(self):
        self.connected.emit()

    def stop(self):
        self.connected_state = False

    def reset(self):
        self.commands = []
