This repository contains a modular program for controlling pulsed NMR applications for Red Pitaya STEMlab 125-14 and Red Pitaya SDRlab 122-16:

https://pavel-demin.github.io/red-pitaya-notes/pulsed-nmr/

https://pavel-demin.github.io/red-pitaya-notes/pulsed-nmr-122-88/

## Project structure

- [gui.py](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/gui.py) - entry point for the graphical user interface (GUI).
- [cli.py](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/cli.py) - entry point for the command-line interface (CLI).
- [app](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/app) - application modules: main window, CLI app, log display.
- [common](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/common) - shared modules: communication transport, configuration, plot widget, sequence base classes.
- [sequences](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/sequences) - sequences: one subdirectory per sequence.
- [tests](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/tests) - test suite (unit, integration, system, and acceptance tests).
- [docs](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/docs) - documentation: [architecture.md](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/docs/architecture.md) and [requirements.md](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/docs/requirements.md).
- [LICENSE](https://github.com/pavel-demin/pulsed-nmr-client/tree/main/LICENSE) - license.

## Requirements

- Python 3.13 or newer.
- `python3 -m pip install PySide6 matplotlib numpy pytest`

## Running the GUI

```
python3 gui.py
```

Press the "Load seq." button to open the directory selection dialog and choose a sequence. Press the "Start seq." button to connect to the server running on the Red Pitaya board and run the sequence.

## Running the CLI

```
python3 cli.py <sequence> <output>
```

The CLI runs the named sequence once and writes the acquired data to `<output>` without starting the GUI.

## Configuration

Each sequence has its own `sequences/<name>/config.ini` file, containing a `[general]` section with the system parameters and a `[sequence]` section with the sequence-specific parameters. Both entry points use the same configuration files.

## Testing

```
python3 -m pytest
```
