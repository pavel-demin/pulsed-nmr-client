import hashlib
import struct

from sequences.cal_pulse.logic import CalPulseLogic
from sequences.cpmg.logic import CpmgLogic
from sequences.fid.logic import FidLogic

FID_SHA256 = "5c5cde4e401a0ddfbe81161f0611474a26cfe141a3f98b93a895f0d18ab900ae"
FID_FIRST_18_HEX = "c006ca00b081320032000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000603f5973070000007000000000000000807c00000000010070000000000000008070020000000200700000000000000080e104000000d2cc7000000000000000807c000000000000700000000000000080"
CAL_PULSE_SHA256 = "24549db47f52b4697edeb531bf3465e24ae4c00fee9938ef9627e27d496d80e9"
CAL_PULSE_FIRST_18_HEX = "c006ca00b081320032000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000603f5973070000007000000000000000807c00000000010070000000000000008070020000000200700000000000000080f900000000d2cc7000000000000000807c000000000000700000000000000080"
CPMG_SHA256 = "d23ffca2555d17e2d66295f279d14fe11f107b52308804c17c14fcd0ec495895"
CPMG_FIRST_18_HEX = "c006ca00b081320032000000000000100000000000000050010000000000005002000000000000500300000000000050330300000000002000000000000000603f5973070000007000000000000000807c000000000100700000000000000080700200000002007000000000000000806918000000f2ff730000000000000080c3090000000000700000000000000080"

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

CAL_PARAMS = {
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
    "start": 2,
    "stop": 40,
    "step": 2,
}

CAL_PULSE_PARAMS = {
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
    "start": 2,
    "stop": 40,
    "step": 2,
}

CPMG_PARAMS = {
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
    "level": 50,
    "width": 50,
    "echo_time": 200,
    "echoes": 10,
}


def pack_stream(commands):
    return b"".join(struct.pack("<Q", code << 60 | data) for code, data in commands)


def test_fid_wire_stream_matches_legacy_reference(simulated_transport):
    FidLogic(simulated_transport).run(FID_PARAMS)
    commands = simulated_transport.commands
    assert len(commands) == 38
    stream = pack_stream(commands)
    assert len(stream) == 304
    assert hashlib.sha256(stream).hexdigest() == FID_SHA256
    assert pack_stream(commands[:18]).hex() == FID_FIRST_18_HEX
    assert [data for code, data in commands if code == 10] == [13] * 16


def test_cal_pulse_wire_stream_matches_legacy_reference(simulated_transport):
    CalPulseLogic(simulated_transport).run(CAL_PULSE_PARAMS)
    commands = simulated_transport.commands
    assert len(commands) == 627
    stream = pack_stream(commands)
    assert len(stream) == 5016
    assert hashlib.sha256(stream).hexdigest() == CAL_PULSE_SHA256
    assert pack_stream(commands[:18]).hex() == CAL_PULSE_FIRST_18_HEX
    assert [data for code, data in commands if code == 10] == [13] * 320


def test_cpmg_wire_stream_matches_legacy_reference(simulated_transport):
    CpmgLogic(simulated_transport).run(CPMG_PARAMS)
    commands = simulated_transport.commands
    assert len(commands) == 2135
    stream = pack_stream(commands)
    assert len(stream) == 17080
    assert hashlib.sha256(stream).hexdigest() == CPMG_SHA256
    assert pack_stream(commands[:18]).hex() == CPMG_FIRST_18_HEX
    assert [data for code, data in commands if code == 10] == [130] * 16


def test_wire_pack_roundtrip_property(simulated_transport):
    FidLogic(simulated_transport).run(FID_PARAMS)
    stream = pack_stream(simulated_transport.commands)
    for index, (code, data) in enumerate(simulated_transport.commands):
        assert code in (0, 1, 2, 4, 5, 6, 7, 8, 9, 10)
        assert data < 2**60
        chunk = stream[index * 8 : index * 8 + 8]
        packed = struct.unpack("<Q", chunk)[0]
        assert packed == code << 60 | data
