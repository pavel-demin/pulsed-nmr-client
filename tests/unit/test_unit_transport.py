import struct

import numpy as np
from PySide6.QtNetwork import QAbstractSocket

from common.simulated_transport import SimulatedTransport
from common.transport import Transport, create_transport


class FakeSocket:
    def __init__(self, state, buf=b""):
        self._state = state
        self._buf = buf
        self.written = []
        self.aborted = False

    def write(self, data):
        self.written.append(bytes(data))

    def state(self):
        return self._state

    def bytesAvailable(self):
        return len(self._buf)

    def read(self, n):
        out = self._buf[:n]
        self._buf = self._buf[n:]
        return out

    def abort(self):
        self.aborted = True


def make_transport(state, buf=b""):
    transport = Transport("127.0.0.1")
    transport.socket = FakeSocket(state, buf)
    return transport


def test_wire_format_pack():
    transport = make_transport(QAbstractSocket.SocketState.ConnectedState)
    transport.send(7, 124)
    assert transport.socket.written == [struct.pack("<Q", 7 << 60 | 124)]
    transport.send(0, 14216341763000000)
    assert transport.socket.written[-1] == struct.pack("<Q", 14216341763000000)


def test_default_port_and_addr():
    transport = Transport("127.0.0.1")
    assert transport.addr == "127.0.0.1"
    assert transport.port == 1001


def test_is_connected_states():
    disconnected = make_transport(QAbstractSocket.SocketState.UnconnectedState)
    assert disconnected.is_connected() is False
    connected = make_transport(QAbstractSocket.SocketState.ConnectedState)
    assert connected.is_connected() is True


def test_read_samples_stopping_guard():
    transport = make_transport(QAbstractSocket.SocketState.ConnectedState, struct.pack("<4f", 1.0, 0.0, 0.0, 2.0))
    transport.stopping = True
    assert transport.read_samples(1) is None
    assert transport.socket.written == [struct.pack("<Q", 10 << 60 | 1)]


def test_read_samples_disconnected_guard():
    transport = make_transport(QAbstractSocket.SocketState.UnconnectedState, struct.pack("<4f", 1.0, 0.0, 0.0, 2.0))
    assert transport.read_samples(1) is None
    assert transport.socket.written == [struct.pack("<Q", 10 << 60 | 1)]


def test_read_samples_single_chunk():
    transport = make_transport(QAbstractSocket.SocketState.ConnectedState, struct.pack("<4f", 1.0, 0.0, 0.0, 2.0))
    results = transport.read_samples(1)
    assert results is not None
    assert results.dtype == np.complex64
    assert results.size == 2
    assert results[0] == 1.0 + 0j
    assert results[1] == 0.0 + 2.0j
    assert transport.socket.written == [struct.pack("<Q", 10 << 60 | 1)]


def test_close_aborts_socket():
    transport = make_transport(QAbstractSocket.SocketState.ConnectedState)
    transport.stop()
    assert transport.socket.aborted is True


def test_factory_branches(monkeypatch):
    monkeypatch.setenv("PULSED_NMR_TRANSPORT", "simulated")
    simulated = create_transport("10.0.0.5", 9999)
    assert isinstance(simulated, SimulatedTransport)
    assert simulated.addr == "10.0.0.5"
    assert simulated.port == 9999
    monkeypatch.delenv("PULSED_NMR_TRANSPORT")
    tcp = create_transport("10.0.0.5", 9999)
    assert isinstance(tcp, Transport)
    assert not isinstance(tcp, SimulatedTransport)
    assert tcp.is_connected() is False
    monkeypatch.setenv("PULSED_NMR_TRANSPORT", "other")
    tcp_other = create_transport("10.0.0.5", 9999)
    assert isinstance(tcp_other, Transport)
