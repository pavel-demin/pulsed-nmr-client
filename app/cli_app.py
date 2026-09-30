import argparse
import configparser

from common.config import Config, sequence_classes, sequence_dir
from common.transport import CONNECT_TIMEOUT_MS, create_transport, wait_for_connection


def sequence_names():
    return sorted(path.name for path in sequence_dir().iterdir() if path.is_dir() and not path.name.startswith("__"))


class CliApp:
    def __init__(self, argv):
        names = sequence_names()
        self.sequence_map = {name: sequence_classes(name)[1] for name in names}
        parser = argparse.ArgumentParser()
        parser.add_argument("sequence", choices=tuple(names))
        parser.add_argument("output")
        self.args = parser.parse_args(argv)

    def build_params(self, config):
        params = {}
        if config.parser.has_section("general"):
            for k, v in config.items("general"):
                params[k] = v
        if config.parser.has_section("sequence"):
            for k, v in config.items("sequence"):
                params[k] = v
        return params

    def run(self):
        args = self.args
        config = Config(Config.sequence_path(args.sequence))
        try:
            config.load()
            params = self.build_params(config)
            addr = params["addr"]
        except (configparser.Error, ValueError, KeyError, IndexError):
            print("error: invalid parameters")
            return 1
        transport = create_transport(addr, 1001)
        if not transport.is_connected():
            connected, error = wait_for_connection(transport, CONNECT_TIMEOUT_MS)
            if not connected:
                print(f"error: {error}")
                return 1
        logic = self.sequence_map[args.sequence](transport, print)
        try:
            results = logic.run(params)
        except (ValueError, KeyError, IndexError):
            print("error: invalid parameters")
            return 1
        finally:
            transport.stop()
        if results is None:
            return 1
        logic.save(results, args.output)
        return 0
