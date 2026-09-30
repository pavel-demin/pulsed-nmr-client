import os
import struct

import numpy as np
from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

from common.simulated_transport import SimulatedTransport

CONNECT_TIMEOUT_MS = 5000


class Transport(QObject):
    connected = Signal()
    errorOccurred = Signal(str)

    def __init__(self, addr, port=1001):
        super().__init__()
        self.addr = addr
        self.port = port
        self.stopping = False
        self.socket = QTcpSocket(self)
        self.socket.connected.connect(self.connected)
        self.socket.errorOccurred.connect(self.socket_error)
        self.loop = QEventLoop()
        self.socket.readyRead.connect(self.loop.quit)
        self.socket.errorOccurred.connect(self.loop.quit)

    def socket_error(self, error):
        self.errorOccurred.emit(self.socket.errorString())

    def start(self):
        self.socket.connectToHost(self.addr, self.port)

    def is_connected(self):
        return self.socket.state() == QAbstractSocket.SocketState.ConnectedState

    def send(self, code, data):
        self.socket.write(struct.pack("<Q", int(code) << 60 | int(data)))

    def read_samples(self, size):
        self.send(10, size)
        data = np.zeros(size * 2, dtype=np.complex64)
        view = data.view(np.uint8)
        limit = view.size
        offset = 0
        while offset < limit:
            if self.stopping or self.socket.state() != QAbstractSocket.SocketState.ConnectedState:
                return None
            if self.socket.bytesAvailable() < limit - offset:
                self.loop.exec()
            if self.stopping or self.socket.bytesAvailable() == 0:
                return None
            chunk = self.socket.read(limit - offset)
            count = len(chunk)
            if count == 0:
                return None
            view[offset : offset + count] = np.frombuffer(chunk, np.uint8)
            offset += count
        return data

    def stop(self):
        self.loop.quit()
        self.socket.abort()


def create_transport(addr, port=1001):
    if os.environ.get("PULSED_NMR_TRANSPORT") == "simulated":
        return SimulatedTransport(addr, port)
    return Transport(addr, port)


def wait_for_connection(transport, timeout_ms):
    if QCoreApplication.instance() is None:
        QCoreApplication([])
    errors = []
    loop = QEventLoop()

    def on_error(text):
        errors.append(text)
        loop.quit()

    def on_timeout():
        loop.quit()

    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(on_timeout)
    transport.connected.connect(loop.quit)
    transport.errorOccurred.connect(on_error)
    transport.start()
    timeout.start(timeout_ms)
    loop.exec()
    timeout.stop()
    if not transport.is_connected():
        return False, errors[0] if errors else "connection timeout"
    return True, None
