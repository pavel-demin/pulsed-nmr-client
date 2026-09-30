import configparser
import importlib
from pathlib import Path

from common.plot_widget import PlotWidget
from common.sequence_logic import SequenceLogic


class Config:
    def __init__(self, path):
        self.path = path
        self.parser = configparser.ConfigParser()

    def load(self):
        self.parser.read(self.path)

    def save(self):
        with open(self.path, "w") as handle:
            self.parser.write(handle)

    def items(self, section):
        return self.parser.items(section)

    def get(self, section, key):
        return self.parser.get(section, key)

    def set(self, section, key, value):
        if not self.parser.has_section(section):
            self.parser.add_section(section)
        self.parser.set(section, key, str(value))

    @classmethod
    def sequence_path(cls, name):
        return sequence_dir(name) / "config.ini"


def sequence_dir(name=None):
    sequences = Path(__file__).resolve().parent.parent / "sequences"
    return sequences / name if name else sequences


def sequence_classes(name):
    ui_module = importlib.import_module(f"sequences.{name}.ui")
    logic_module = importlib.import_module(f"sequences.{name}.logic")
    ui_class = next(
        cls
        for cls in vars(ui_module).values()
        if isinstance(cls, type)
        and issubclass(cls, PlotWidget)
        and cls is not PlotWidget
        and cls.__module__ == ui_module.__name__
    )
    logic_class = next(
        cls
        for cls in vars(logic_module).values()
        if isinstance(cls, type)
        and issubclass(cls, SequenceLogic)
        and cls is not SequenceLogic
        and cls.__module__ == logic_module.__name__
    )
    return ui_class, logic_class
