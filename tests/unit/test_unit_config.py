import configparser
import shutil

import pytest

from common.config import Config, sequence_classes, sequence_dir
from common.sequence_logic import GENERAL_KEYS, PIN_KEYS
from sequences.cal_pulse.logic import CalPulseLogic
from sequences.cal_pulse.ui import CalPulseUiHelper
from sequences.cpmg.logic import CpmgLogic
from sequences.cpmg.ui import CpmgUiHelper
from sequences.fid.logic import FidLogic
from sequences.fid.ui import FidUiHelper
from tests.conftest import REFERENCE_GENERAL, REFERENCE_SEQUENCE

pytestmark = pytest.mark.usefixtures("no_qapp")


def test_sequence_paths():
    for name in ("fid", "cal_pulse", "cpmg"):
        path = Config.sequence_path(name)
        assert path.is_absolute()
        assert path.parent.name == name
        assert path.name == "config.ini"
        assert path.exists()


def test_load_and_values(pinned):
    config = Config(pinned)
    config.load()
    for key, value in REFERENCE_GENERAL.items():
        assert config.get("general", key) == value
    for name, mapping in REFERENCE_SEQUENCE.items():
        sequence = Config(Config.sequence_path(name))
        sequence.load()
        for key, value in mapping.items():
            assert sequence.get("sequence", key) == value


def test_value_fallback(config):
    loaded = config()
    loaded.load()
    with pytest.raises(configparser.NoOptionError):
        loaded.get("general", "missing_key")
    with pytest.raises(configparser.NoSectionError):
        loaded.get("MissingSection", "key")


def test_set_value_save_round_trip(config):
    copy = config()
    copy.set("General", "freq", "9.9")
    copy.set("NewSection", "new_key", "v1")
    copy.save()
    parser = configparser.ConfigParser()
    parser.read(copy.path)
    assert parser.get("General", "freq") == "9.9"
    assert parser.get("NewSection", "new_key") == "v1"


def test_sequence_sections(config):
    sections = {
        "fid": ("level", "width"),
        "cal_pulse": ("level", "start", "stop", "step"),
        "cpmg": ("level", "width", "echoes"),
    }
    for name, keys in sections.items():
        copy = config(name)
        copy.load()
        for key in keys:
            assert copy.get("sequence", key) is not None


def test_sequence_dir():
    path = sequence_dir()
    assert path.name == "sequences"
    assert path.is_dir()


def test_sequence_classes_all_sequences():
    assert sequence_classes("fid") == (FidUiHelper, FidLogic)
    assert sequence_classes("cal_pulse") == (CalPulseUiHelper, CalPulseLogic)
    assert sequence_classes("cpmg") == (CpmgUiHelper, CpmgLogic)


def test_general_config_tables():
    assert GENERAL_KEYS == [
        ("adc_rate", "adcRateValue", None, "adc"),
        ("rate", "rateValue", int, "rate"),
        ("freq", "freqValue", float, "value"),
        ("polarity", "polarityValue", int, "index"),
        ("blank", "blankValue", int, "value"),
        ("delta", "deltaValue", int, "value"),
        ("echo_time", "echoTimeValue", int, "value"),
        ("read_delay", "readDelayValue", int, "value"),
        ("read_time", "readTimeValue", int, "value"),
        ("gain", "gainValue", int, "value"),
        ("scans", "scansValue", int, "value"),
    ]
    assert PIN_KEYS == [("pin0", 0), ("pin1", 1), ("pin2", 2), ("pin3", 3)]
    params = [key for key, _, _, _ in GENERAL_KEYS if key != "gain"]
    assert params == [
        "adc_rate",
        "rate",
        "freq",
        "polarity",
        "blank",
        "delta",
        "echo_time",
        "read_delay",
        "read_time",
        "scans",
    ]


def test_sequence_classes_invalid():
    with pytest.raises(ImportError):
        sequence_classes("bogus")
    scratch = sequence_dir() / "_bad_tmp"
    try:
        scratch.mkdir()
        (scratch / "ui.py").write_text("")
        with pytest.raises((ImportError, StopIteration)):
            sequence_classes("_bad_tmp")
    finally:
        shutil.rmtree(scratch)
