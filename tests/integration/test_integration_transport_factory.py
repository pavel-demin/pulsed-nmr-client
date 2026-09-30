import hashlib
import struct

from common.simulated_transport import SimulatedTransport
from common.transport import Transport, create_transport
from sequences.fid.logic import FidLogic

FID_SHA256 = "5c5cde4e401a0ddfbe81161f0611474a26cfe141a3f98b93a895f0d18ab900ae"

FID_PARAMS = {
    "freq": 13.24,
    "rate": 5,
    "adc_rate": 125.0,
    "blank": 5,
    "polarity": 1,
    "gain": 10,
    "pin0": False,
    "pin1": False,
    "pin2": False,
    "pin3": False,
    "delta": 1000,
    "read_delay": 1,
    "read_time": 10,
    "scans": 16,
    "level": 10,
    "width": 10,
}


def pack_stream(commands):
    return b"".join(struct.pack("<Q", code << 60 | data) for code, data in commands)


def test_factory_simulated_substitution(monkeypatch):
    monkeypatch.setenv("PULSED_NMR_TRANSPORT", "simulated")
    transport = create_transport("10.0.0.1", 1234)
    assert type(transport) is SimulatedTransport
    assert transport.addr == "10.0.0.1"
    assert transport.port == 1234
    assert transport.is_connected() is True


def test_factory_non_simulated_returns_tcp(monkeypatch):
    monkeypatch.delenv("PULSED_NMR_TRANSPORT")
    transport = create_transport("10.0.0.1", 1234)
    assert type(transport) is Transport
    assert transport.is_connected() is False
    transport.stop()
    monkeypatch.setenv("PULSED_NMR_TRANSPORT", "tcp")
    transport = create_transport("10.0.0.1", 1234)
    assert type(transport) is Transport
    transport.stop()


def test_factory_substituted_run_matches_legacy(monkeypatch):
    monkeypatch.setenv("PULSED_NMR_TRANSPORT", "simulated")
    transport = create_transport("127.0.0.1", 1001)
    FidLogic(transport).run(FID_PARAMS)
    stream = pack_stream(transport.commands)
    assert len(stream) == 304
    assert hashlib.sha256(stream).hexdigest() == FID_SHA256
