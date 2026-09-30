import inspect

import numpy as np

from common.simulated_transport import SimulatedTransport
from common.transport import Transport


def test_interface_conformance_with_transport():
    for method in ("start", "is_connected", "send", "read_samples", "stop"):
        assert inspect.signature(getattr(Transport, method)) == inspect.signature(getattr(SimulatedTransport, method))
    assert hasattr(Transport, "connected") and hasattr(SimulatedTransport, "connected")
    assert hasattr(Transport, "errorOccurred") and hasattr(SimulatedTransport, "errorOccurred")
    assert Transport("127.0.0.1").stopping is False
    assert SimulatedTransport("127.0.0.1").stopping is False
    assert hasattr(SimulatedTransport, "reset")
    assert not hasattr(Transport, "reset")


def test_command_recording(simulated_transport):
    simulated_transport.send(7, 124)
    assert simulated_transport.commands == [(7, 124)]
    simulated_transport.send(7.0, 124.9)
    assert simulated_transport.commands[-1] == (7, 124)


def test_read_samples_zero_buffer(simulated_transport):
    results = simulated_transport.read_samples(13)
    assert simulated_transport.commands == [(10, 13)]
    assert results.dtype == np.complex64
    assert results.size == 26
    assert np.all(results == 0)


def test_read_samples_injection(simulated_transport):
    fixed = np.ones(10, dtype=np.complex64)

    def injected(size):
        return fixed

    simulated_transport.read_samples = injected
    results = simulated_transport.read_samples(5)
    assert results is fixed
    assert simulated_transport.commands == []


def test_start_emits_signal():
    transport = SimulatedTransport("127.0.0.1", 1001)
    emissions = []
    transport.connected.connect(lambda: emissions.append(1))
    transport.start()
    transport.start()
    assert len(emissions) == 2


def test_close_and_reset(simulated_transport):
    assert simulated_transport.is_connected() is True
    simulated_transport.stop()
    assert simulated_transport.is_connected() is False
    simulated_transport.send(7, 124)
    simulated_transport.reset()
    assert simulated_transport.commands == []
