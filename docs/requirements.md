# Requirements for the pulsed NMR modular control program

## Purpose and derivation

This document states the software requirements of the pulsed NMR modular control program. Each requirement and its acceptance criterion is standalone; the in-repository references are `README.md` (the project overview and usage), `docs/architecture.md` (the program layout, the module inventory and interfaces, and the naming conventions), the configuration files (`sequences/<name>/config.ini`), the project metadata and tool configuration (`pyproject.toml`), and the license (`LICENSE`).

## Scope

The in-scope sequences are the sequence directories under the `sequences/` directory; the current in-tree list is the `sequences/` directory listing documented in `docs/architecture.md` (the listing in layout, section 2, and the discovery mechanism in dynamic loading, section 5). The entry points are `gui.py` (the graphical user interface) and `cli.py` (the command-line interface); the same sequence logic runs under both entry points. Adding, removing, or renaming a sequence changes the code and `docs/architecture.md`, not this document.

## Requirements

### REQ-01 (entry points)

- Statement: `gui.py` and `cli.py` exist; each can trigger every sequence; the core execution logic is decoupled from the interface so the same sequence logic runs under both entry points.
- Acceptance criterion: `gui.py` and `cli.py` exist at the repository root; under `QT_QPA_PLATFORM=offscreen` and `PULSED_NMR_TRANSPORT=simulated`, the GUI loads every sequence via the dedicated load button and triggers every sequence, and the CLI triggers every sequence with exit status 0; with identical parameters, both entry points produce the identical simulated-transport command stream, demonstrating that the same sequence logic runs under both entry points.

### REQ-02 (modularity)

- Statement: Each sequence resides in its own directory under `sequences/` with implementation code, a GUI layout, and a configuration file; each sequence is split into a logic file (pulse sequence timing and hardware control) and a UI helper file (the code that links the sequence logic to the GUI).
- Acceptance criterion: Each sequence directory under `sequences/` contains a logic file, a UI helper file, a layout, and a configuration file at the committed names of `docs/architecture.md` (layout and naming conventions); the logic files contain the pulse sequence timing and hardware control and no widget access; the UI helper files link the sequence logic to the GUI and contain no pulse timing or hardware command logic.

### REQ-03 (GUI)

- Statement: `gui.py` initializes its main window frame from the frame layout `app/main_window.ui` and dynamically loads a single sequence at a time via a dedicated load button.
- Acceptance criterion: `gui.py` run under `QT_QPA_PLATFORM=offscreen` initializes the main window frame from the frame layout `app/main_window.ui`; a dedicated load button loads exactly one sequence at a time; loading a sequence unloads the previously loaded one; every sequence is loadable.

### REQ-04 (behavior preservation)

- Statement: The sequence logic of the sequences preserves the documented reference timing and hardware command behavior; the sequence layouts and the main window frame are part of the modular structure.
- Acceptance criterion: For each sequence, the command stream (the packed 64-bit little-endian codes and data values) and the timing values produced by the sequence logic match the documented reference behavior of the sequences (the wire-level command streams and timing values recorded by the test suite under the simulated transport); the sequence layouts and the main window frame are the layouts of the modular structure.

### REQ-05 (reuse)

- Statement: Maximum reuse of shared Python helpers, pytest fixtures, and pytest features.
- Acceptance criterion: The shared infrastructure (the transport and the `create_transport` factory, the simulated transport, the configuration loading, the plot base, the shared sequence UI base, and the sequence base) lives in `common/` and is reused by every sequence and both entry points with no per-sequence duplication; the test suite reuses the shared fixtures of `tests/conftest.py` at every test level with no fixture duplication.

### REQ-06 (structure)

- Statement: The program and test suite structure comply with established best practices.
- Acceptance criterion: The program and the test suite follow the committed program layout and the naming conventions of `docs/architecture.md` (layout and naming conventions sections); the four test-level directories (`unit/`, `integration/`, `system/`, `acceptance/`) contain no `__init__.py` (`tests/` itself carries an empty `__init__.py`) and the test file names are unique across the `tests/` tree.

### REQ-07 (hardware isolation)

- Statement: No test requires a live Red Pitaya device or network peer; the hardware transport is isolatable; unit, integration, system, and acceptance tests run against a simulated transport.
- Acceptance criterion: The full test suite runs in this workspace with no Red Pitaya device and no network peer; setting `PULSED_NMR_TRANSPORT=simulated` makes `create_transport` return `SimulatedTransport`; all tests of every level run against the simulated transport.

### REQ-08 (GUI testability)

- Statement: Every GUI component is testable headless under `QT_QPA_PLATFORM=offscreen`.
- Acceptance criterion: Every GUI component (the main window, the log display, the sequence UI helpers, and the plot base) is constructed, operated, and asserted in the test suite under `QT_QPA_PLATFORM=offscreen` without a display.

### REQ-09 (Python code style)

- Statement: No local imports, no type annotations, no docstrings, no comments; consistent naming conventions and structural patterns.
- Acceptance criterion: A machine check over every Python file of the program and of the test suite reports no function-level (local) imports, no type annotations, no docstrings, and no comments; the naming conventions and the structural patterns are those of `docs/architecture.md` (naming conventions section).

### REQ-10 (defect detection)

- Statement: Tests detect bugs and anomalies in the code, never adapt to them; every discovered problem is documented with the evidence needed to triage it (expected versus observed, log path).
- Acceptance criterion: The test suite asserts the expected behavior per the requirements and never the observed buggy behavior (every assertion encodes a required value, not an observed one); every discovered problem in the code is recorded with a defect ID, date, requirement ID, component, expected, observed, evidence with log path, and status.

## References

- `README.md` - the project overview and usage.
- `docs/architecture.md` - the architecture document; the in-repository source of truth for the program layout, the module inventory and interfaces, and the naming conventions.
- `sequences/<name>/config.ini` - the per-sequence configuration files.
- `pyproject.toml` - the project metadata and tool configuration (the pytest, ruff, and black tool settings).
- `LICENSE` - the license.
