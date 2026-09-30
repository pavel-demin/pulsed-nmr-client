# Architecture of the pulsed NMR modular control program

## 1. Purpose and scope

This document describes the architecture of the pulsed NMR modular control program. It covers the program layout (section 2), the module inventory and interfaces (section 3), the dependency rules (section 4), the dynamic loading mechanism (section 5), the transport isolation design (section 6), the naming conventions (section 7), and the references (section 8).

## 2. Layout

The program layout:

```
pulsed-nmr-client/
  gui.py                          # entry point, thin launcher
  cli.py                          # entry point, thin launcher
  README.md                       # project overview and usage
  LICENSE                         # license
  pyproject.toml                  # project metadata and tool configuration
  docs/
    requirements.md               # program requirements document
    architecture.md               # architecture document
  common/                         # shared infrastructure components
    __init__.py                   # scaffolding
    transport.py                  # TCP transport + create_transport factory
    simulated_transport.py        # simulated transport for tests
    config.py                     # INI config loading and saving, sequence_dir/sequence_classes
    plot_widget.py                # shared plot base
    sequence_logic.py             # shared timing and command helpers
    sequence_ui.py                # shared sequence UI base for the helpers
  app/                            # application modules and frame layouts
    __init__.py                   # scaffolding
    main_window.ui                # main window frame layout, adapted for dynamic loading
    main_window.py                # MainWindow component
    log_display.py                # LogDisplay component
    cli_app.py                    # CliApp component
  sequences/                      # sequence directory parent
    __init__.py                   # scaffolding
    fid/
      __init__.py                 # scaffolding
      layout.ui                   # sequence layout
      config.ini                  # sequence config
      logic.py                    # FidLogic
      ui.py                       # FidUiHelper
    cal_pulse/
      __init__.py                 # scaffolding
      layout.ui                   # sequence layout
      config.ini                  # sequence config
      logic.py                    # CalPulseLogic
      ui.py                       # CalPulseUiHelper
    cpmg/
      __init__.py                 # scaffolding
      layout.ui                   # sequence layout
      config.ini                  # sequence config
      logic.py                    # CpmgLogic
      ui.py                       # CpmgUiHelper
  tests/
    __init__.py                   # scaffolding (empty)
    conftest.py                   # shared fixtures
    unit/                         # unit tests
    integration/                  # integration tests
    system/                       # system tests
      cli_driver.py               # CLI capture driver script
      gui_driver.py               # GUI capture driver script
    acceptance/                   # acceptance tests
```

The layout contains the entry points `gui.py` and `cli.py`, the `LICENSE` file, the `pyproject.toml` configuration file (project metadata plus the pytest, ruff, and black tool settings), the `docs/` documentation pair, the `common/` shared infrastructure modules, the `app/` application modules and frame layouts, the `sequences/` directory with one subdirectory per sequence, each holding an `__init__.py` scaffolding file, a layout, a configuration file, a logic module, and a UI helper module, and the `tests/` tree with its `__init__.py`, the shared fixtures, the two capture driver scripts in `tests/system/`, and the four test-level directories.

## 3. Module inventory and interfaces

This section lists every program module and its public interface; the descriptions are the current contracts of the implemented modules.

### 3.1 common/transport.py

`class Transport(QObject)` - the TCP transport (the signals `connected` and `errorOccurred` are declared on the class):

- `__init__(self, addr, port=1001)` - stores addr and port; creates the `QTcpSocket` and the `QEventLoop`; wires the socket signals (the socket `connected` is forwarded to the transport `connected`, the socket `errorOccurred` is relayed through the `socket_error` handler that re-emits `errorOccurred` with the socket's error string, and both `readyRead` and `errorOccurred` quit the event loop - the mechanism by which `read_samples` blocks for data); starts disconnected; public attribute `stopping = False`.
- Signals: `connected` (no arguments), `errorOccurred` (one string argument).
- `start(self)` - initiates the connection to (addr, port).
- `is_connected(self)` - True while the socket is in the `ConnectedState`.
- `send(self, code, data)` - writes `struct.pack("<Q", int(code) << 60 | int(data))`.
- `read_samples(self, size)` - issues the read request (code 10, data `size`) and reads the raw sample buffer: a numpy `complex64` array of `size * 2` elements; returns `None` on a `stopping` or disconnected condition mid-read.
- `stop(self)` - quits the event loop and aborts the socket.
- `create_transport(addr, port=1001)` (module function) - returns `SimulatedTransport(addr, port)` when `os.environ.get("PULSED_NMR_TRANSPORT")` equals `"simulated"`, and `Transport(addr, port)` otherwise.
- Module constant `CONNECT_TIMEOUT_MS = 5000` - the connection timeout policy in milliseconds, shared by the CLI connect wait and the GUI run-time connect wait.
- `wait_for_connection(transport, timeout_ms)` (module function) - the centralized connect-wait policy: it ensures a `QCoreApplication` instance exists, creates a `QEventLoop`, connects the `transport.connected` signal to `loop.quit`, the `transport.errorOccurred` signal to a handler that appends the error text and quits, and a single-shot `QTimer` to a timeout handler that quits; it then calls `transport.start()`, starts the timer with `timeout_ms`, and runs the loop; after the loop it stops the timer and returns `(True, None)` when `transport.is_connected()`, else `(False, errors[0] if errors else "connection timeout")`.

### 3.2 common/simulated_transport.py

`class SimulatedTransport(QObject)` - the same public interface as `Transport` (same method names and signatures, same signals, same `stopping` attribute), plus the test-support `reset` method:

- `__init__(self, addr, port=1001)` - stores addr and port; starts in the connected state (`is_connected()` True from construction); `commands = []`.
- `send(self, code, data)` - appends `(code, data)` as an integer tuple to `commands` (the recorded command stream; the wire equivalent is the 64-bit little-endian value `code << 60 | data`).
- `read_samples(self, size)` - records `(10, size)` in `commands` and returns `np.zeros(size * 2, dtype=np.complex64)`; the documented injection point for tests (tests may override or replace the method to inject data).
- `start(self)` - emits the `connected` signal (on each call).
- `is_connected(self)` - True while `connected_state` is set (from construction until `stop()`).
- `stop(self)` - transitions to the disconnected state.
- `reset(self)` - clears `commands` (test-support-only method; the one documented interface difference from `Transport`).

### 3.3 common/config.py

`class Config` - the INI configuration reader/writer (standard-library `configparser` based; the class logic is GUI-independent and needs no `QApplication`, while the module itself imports `PlotWidget` and `SequenceLogic` at top level for `sequence_classes` and therefore reaches matplotlib and PySide6 transitively, section 4):

- `__init__(self, path)` - stores the file path; nothing is loaded yet.
- `load()` - parses the INI file.
- `get(self, section, key)` - returns the string value, and raises `configparser.NoOptionError` when the key is absent or `configparser.NoSectionError` when the section is absent.
- `set(self, section, key, value)` - sets the value, creating the section if needed.
- `items(self, section)` - returns the (key, value) pairs of the section.
- `save()` - writes the file.
- `parser` - the underlying `configparser` object (used by `CliApp.build_params` for its per-section guards).
- `sequence_path(name)` (class method) - the absolute path of `sequences/<name>/config.ini` (implemented as `sequence_dir(name) / "config.ini"`).
- Values are strings; the GUI caller applies the widget-load conversions of section 3.5, and the CLI defers the `int(...)`/`float(...)` conversions (and the `pin_state` parsing of the pin values) to the logic of section 3.7 at `run` time.

### 3.4 common/plot_widget.py

`class PlotWidget(QWidget)` - the shared plot base class for the sequence plot areas:

- `__init__(self)` - `xdata`, `ydata` (empty `float32` arrays), `fit_curve = None`.
- `setup_plot(self, xlabel, ylabel, style)` - builds the matplotlib `Figure`, canvas, and navigation toolbar into `self.plotLayout` (the layout object name of the sequence layout), removes the toolbar action at index 6 (index 7 on matplotlib < 2; the `Subplots` action on the current matplotlib 3.x), and connects the motion event; the toolbar additionally carries a separator and the two `QPushButton` data buttons `loadDataButton` (text `Load data`) and `saveDataButton` (text `Save data`), added through `addSeparator()`/`addWidget()` and wired to the widget's own `load`/`save`; the subclass must provide the attributes `plotLayout` and `plotWidget` before calling it (and `log`, an object with `print`, before `save_csv`/`load_csv`).
- `csv_dialog(self, title, accept, callback, select_file=None)` - the shared dialog skeleton: it constructs `QFileDialog(self, title, SAVE_DIR, "*.csv")` (`SAVE_DIR` is the dialog's initial directory: the home directory on Windows, the current working directory otherwise), sets the default suffix to `csv`, selects the file only when `select_file` is not `None`, sets the accept mode, and, on `DialogCode.Accepted`, invokes `callback(name[0])` with the first selected file name; the surrounding `try/except Exception` that logs `error: <e>` lives here (on the dialog side).
- `save_csv(self, title, default_name, callback)` - the thin save wrapper over `csv_dialog`: it calls `csv_dialog(title, QFileDialog.AcceptMode.AcceptSave, callback, default_name)`, so the save path selects the file before the accept mode; the CSV write and the `saved data to <path>` log line live in the logic-layer save (section 3.5).
- `load_csv(self, title, callback)` - the thin open wrapper over `csv_dialog`: it calls `csv_dialog(title, QFileDialog.AcceptMode.AcceptOpen, callback)` (the load path never selects a file); it contains no `np.loadtxt` call; the CSV read, the `loaded data from <path>` success line, and the read error handling live in the logic-layer load (sections 3.5 and 3.7). In the GUI the logic-layer load logs through the same `LogDisplay`, so the user-visible log lines are unchanged.
- `update_curve(self)` - sets the curve data, autoscales, and draws.
- `draw_fit_curve(self, x, y, label)` - draws the fitted result curve as a solid red line (`axes.plot(x, y, color="r", linestyle="-", label=label)`), replacing any existing fit curve first (the old artist is removed and `fit_curve` reset to `None`), then `axes.legend()` and `update_curve()` (replace, then draw, then legend, then update); the label is the result label of the sequence.
- `clear_fit_curve(self)` - when `fit_curve` is not `None`, removes the artist, resets `fit_curve` to `None`, and calls `axes.legend()` (remove-and-relabel).
- `on_motion(self, event)` - the default snaps to the nearest x sample and updates `xdataValue`/`ydataValue` from `xdata`/`ydata`; the shared sequence UI base overrides it (section 3.8, through the `motion_x`/`motion_y` hooks).
- `save(self)` / `load(self)` - required in the subclass (the widget's own plot-toolbar data buttons `saveDataButton`/`loadDataButton` invoke them).

### 3.5 common/sequence_logic.py

Module constants: `SYNC_TIME_US = 1`, `ADC_RATE_122_88 = 122.88`, and `ADC_RATE_125 = 125` (the two supported ADC sample rates in MSPS). The scan count is the configured `[general]` `scans` key; there is no scan-count constant in the module. The module function `sweep_values(start, stop, step)` returns `np.arange(start, stop + step, step, dtype=np.float32)` (the sweep point grid of the calibration sequences).

Module table `GENERAL_KEYS` - the eleven `(key, widget attribute, convert, op)` tuples for general keys: `MainWindow.apply_config`/`save_config` use them to map general keys (e.g., `adc_rate`, `rate`, `gain`) to specific widget update and save operations (`adc` maps the raw string to the combo index - `122.88` to 0, anything else to 1 - and saves `currentText()`; `rate` maps the converted index, clamped to the combo, and saves `currentIndex()`; `value` calls `setValue(convert(value))` and saves `value()`; `index` maps the converted value to the combo index and saves `currentIndex()`), `SequenceLogic.configure` reads the `freq`, `adc_rate`, `rate`, `polarity`, `gain`, and `scans` entries of the `params` contract (and the `pin0` to `pin3` entries through `PIN_KEYS`), and the widgets named in the widget-attribute column are the ones the sequence UI `general_params` reads directly (the mapping is duplicated there, not table-driven); `addr` is excluded from the table and handled directly.

Module table `PIN_KEYS` - the four `(ini key, pin index)` tuples (`pin0` to `pin3`), consumed by `MainWindow.apply_config`/`save_config`, the sequence UI `general_params` (the pin checkboxes), and `SequenceLogic.configure` (the pin wire commands).

Module function `pin_state(value)` - True when the stripped, lower-cased value is `"1"` or `"true"` (the pin-string parse; consumed by `MainWindow.apply_config` and `SequenceLogic.set_pin`).

`class SequenceLogic` - the shared timing and command base for the logic modules:

- Class attributes `rates_122_88 = [40, 80, 160, 320, 640, 1280]` and `rates_125 = [25, 50, 125, 250, 500, 1250]`: the two CIC-divisor rate tables in kSPS (six entries each); the active table is selected by the ADC rate (`rates_122_88` for the 122.88 MSPS selection, `rates_125` otherwise).
- `__init__(self, transport)` - stores the transport; state: `adc_rate = 125` (MSPS; the default selects the `rates_125` table), `cic_rate = 50`, `last_delay = 0`, `last_read = 0`, `size = 0`, `stopping = False`, `polarity = 1`, `log = None` (a callable taking a string; silent no-op when None).
- `log_line(self, text)` - invokes `self.log(text)` when `self.log` is not `None` (the no-op lives here, not at the call sites); every log line described in section 3.7 goes through it.
- `set_freq(self, value)` - `freq = int(value * 1e6 + 0.5)`; `transport.send(0, freq << 30 | freq)`.
- `rate_for(self, index)` - raises `IndexError` when `index < 0`; otherwise returns `self.rates_122_88[index]` when `self.adc_rate == ADC_RATE_122_88` and `self.rates_125[index]` otherwise (the active table entry in kSPS; the exact float equality is safe - both sides derive from the same decimal literals).
- `cic_rate_for(self, index)` - `int(adc_rate * 1e3 / rate / 2)` with `rate` the `rate_for(index)` entry in kSPS (the CIC divisor: 122.88 MSPS gives 1536, 768, 384, 192, 96, 48 for indices 0-5; 125 MSPS gives 2500, 1250, 500, 250, 125, 50 for indices 0-5).
- `preview(adc_rate, rate_index)` (class method) - a throwaway instance (`transport` `None`) with `adc_rate`/`cic_rate` set, used by the UI helpers to compute preview time axes without a transport.
- `set_rates(self, adc_rate, rate_index)` - stores `adc_rate` on the instance, `cic_rate = cic_rate_for(rate_index)`; `transport.send(1, cic_rate)`.
- `set_gain(self, gain)` - `transport.send(2, int(gain / 50.0 * 4095 + 0.5))` (the gain-to-DAC conversion over the 0-50 dB range of `gainValue`; 50 dB gives 4095, 25 dB gives 2048, 1 dB gives 82).
- `set_pin(self, pin, checked)` - `transport.send(4 if pin_state(checked) else 5, pin)` (the set/clear pin wire command, pins 0-3; bool and string values both parse through `pin_state`).
- `configure(self, params)` - the shared run header of section 3.7: `set_freq(float(params["freq"]))`, `set_rates(float(params["adc_rate"]), int(params["rate"]))`, then the four pin commands in `PIN_KEYS` order (`set_pin(index, params[key])` for `params["pin0"]` through `params["pin3"]`, each parsed through `pin_state`), then the gain command `set_gain(int(params["gain"]))`, and `polarity = int(params["polarity"])`; it then validates the scan count - when `int(params["scans"])` is below 1 it logs `error: invalid parameters` and returns `None`, else it returns the parsed scan count (the documented parameter-error contract; the run methods end with `None` on the `None` return). The wire command order is freq, rate, pins, gain, and the committed `params` contract includes the required keys `gain` and `pin0` to `pin3` (a missing key is a `KeyError` caught by the `CliApp.run` run-phase guard and reported as `error: invalid parameters`; the GUI run path has no such guard, and the helper's `collect_params` always supplies the full contract).
- `clear_events(self)` - resets the size state (`last_delay = int(adc_rate * cic_rate * 2.0 + 0.5)`, `last_read = 0`, `size = 0`); `transport.send(6, 0)`.
- `add_event(self, delay, sync=0, gate=0, read=0, level=0, tx_phase=0, rx_phase=0)` - the polarity gate flip uses `self.polarity` (index 0 flips the gate); packs the event into the 64-bit code 7 payload (level, gate, sync, delay-1) and the code 8 payload (rx_phase, tx_phase); sends code 7 then code 8; accumulates the size state.
- `update_size(self)` - computes the pending read size `sz = int(last_delay / (cic_rate * 2.0) + 0.5)`; when `sz > 0` sends code 9 with data `last_read << 40 | (sz - 1)`; when a read is pending, adds `sz` to `self.size`; resets `last_delay` and `last_read`.
- `compute_time(self, reads, delays)` - builds the float32 time axis of the read events.
- `read_data(self)` - `update_size()`; returns `None` when `self.size == 0`; otherwise returns `self.transport.read_samples(self.size)` (the socket loop lives in `Transport.read_samples`).
- `read_scan(self, point=None)` - `read_data()`; on a `None` result logs the failure line (`error: failed to read data`, or `error: failed to read data at point <point>` when `point` is given) and returns `None`; otherwise returns the samples.
- `accumulate_into(self, data, samples)` - `samples` when `data` is `None`, else `data + samples` (the per-scan accumulation).
- `accumulate_step(self, data, scan, scans, on_step)` - one scan: `read_scan()`, accumulate into `data`, call `on_step(scan, scans, data[0::2] / (scan + 1))` (the running average of the even-slot samples) when given, and log `scan <scan + 1>/<scans> completed`; returns `(data, failed)`.
- `accumulate(self, scans, on_step)` - the FID scan loop: repeats `accumulate_step` over `range(scans)` (returns `None` on an early stop or a read failure) and returns the averaged `data`.
- `sweep_results(self, params, points, on_point)` - the per-point sweep loop shared by the calibration sequences (section 3.7): for each point it checks the stopping flag, builds the FID sequence, repeats `scans` scans with the `read_scan(i + 1)` and `accumulate_into` accumulation (a `None` sample or a stop before the point or before a scan returns `None`), averages `data /= scans`, records `results[float(sweep_value)] = (self.compute_time(reads, delays), data)`, and calls `on_point(i, points.size, sweep_value, data)`; returns the `results` dictionary.
- `event_arrays(self, events)` - builds the `reads`/`delays` numpy arrays of an event list (`reads` the truth value of each event's `read` key, `delays` each event's `delay`).
- `check_delays(self, delays)` - validates the event delays; logs `error: negative delay = <value> µs` and returns `False` on a negative value, else returns `True`.
- `stop(self)` - sets `self.stopping = True` and `self.transport.stopping = True`.
- `save_file(self, path, columns, header)` - the shared best-effort CSV write: `np.savetxt(path, columns, delimiter=",", header=header, comments="")`, logs `saved data to <path>` on success, and wraps the write in a `try/except Exception` that logs `error: <e>`.
- `save(self, results, path)` - the logic-layer CSV save (numpy and the standard library only): when `results` is `None` or empty it logs `error: no data to save` and writes nothing; otherwise it unpacks `times, data = results[0]`, takes `samples = data[0::2]`, and writes through `save_file` the three columns under the header `time,real,imag` (`times`, `samples.real`, `samples.imag`).
- `read_csv_rows(self, path)` - the shared CSV read: `np.loadtxt(path, delimiter=",", skiprows=1)`; on any exception it logs `error: <e>` and returns `None`.
- `load(self, path)` - the logic-layer CSV load (numpy and the standard library only): it reads the file with `read_csv_rows`; on a `None` read it returns `None`; otherwise it builds `samples = (loaded[:, 1] + 1j * loaded[:, 2]).astype(np.complex64)`, `time_axis = loaded[:, 0].astype(np.float32)`, and `raw = np.zeros(2 * samples.size, dtype=np.complex64)` with `raw[0::2] = samples`, logs `loaded data from <path>`, and returns `{0: (time_axis, raw)}` - exactly the `run` result format of section 3.7; on a conversion exception it logs `error: <e>` and returns `None`.
- `sweep_save(self, results, path)` - the four-column `pulse_width,time,real,imag` sweep CSV write shared by the calibration sequences: when `results` is `None` or empty it logs `error: no data to save` and writes nothing; otherwise it appends, per sweep point and per time sample, the sweep value, the time axis value, `data[0::2].real` (the real sample), and `data[0::2].imag` (the imaginary sample) - the odd slots carry no information and are not written - and writes the four columns through `save_file` under the header `pulse_width,time,real,imag`.
- `sweep_load(self, path)` - the four-column sweep CSV read shared by the calibration sequences: it reads the file with `read_csv_rows` (a `None` read returns `None`), groups the rows by the `pulse_width` column (as a float key), and, per sweep value, reconstructs the complex samples from the `real` and `imag` columns into the even slots of `data` (the odd slots are zero) with the `time` column as the time axis; it logs `loaded data from <path>` and returns the `{sweep value: (time_axis, data)}` dictionary in the `run` result format of section 3.7; on a conversion exception it logs `error: <e>` and returns `None`.
- The `set_freq`/`set_rates` methods are unguarded; they are reached only once a run is in flight on a connected transport, enforced by the `MainWindow.run_seq` running/no-sequence guard and the `CliApp.run` connect wait.

### 3.6 Configuration structure and key mappings

- The configuration sections in use are `[general]` and `[sequence]`, both present in every sequence file; there are no default configuration values in code.
- A configuration file missing a required key or section is invalid input reported as `error: invalid parameters` (the CLI prints the line and exits 1; the GUI logs the line and keeps the sequence loaded).
- The frame's general widgets start at their `app/main_window.ui` layout defaults and the sequence parameter widgets start at their sequence `layout.ui` defaults when the helper is constructed; the selected sequence's configuration replaces both at `load_sequence`.
- The table-driven key mapping has a single source in `GENERAL_KEYS`/`PIN_KEYS` in `common/sequence_logic.py` (imported from there by `app/main_window.py` together with `pin_state`; `common/config.py` imports neither the key tables nor `pin_state`; `SequenceUiHelper.general_params` carries a hand-maintained duplicate of the key-to-widget mapping, not table-driven), consumed table-driven by `MainWindow.apply_config`/`save_config` (both `GENERAL_KEYS` and `PIN_KEYS`; the op dispatch and save mapping of section 3.5, the `[sequence]` values through the helper's `load_config`/`save_config`) and by `SequenceLogic.configure` (`PIN_KEYS` only; the general keys are read directly by name, as section 3.5 states).
- `CliApp.build_params` dumps both sections raw (a missing section contributes no keys) with no conversion and no exclusion, so the CLI parameter dictionary's `gain` and `pin0` to `pin3` are sent by `SequenceLogic.configure` (section 3.5) at run time.
- `Config` returns strings; the GUI applies the widget-load conversions of section 3.5, and the logic applies the `int(...)`/`float(...)` conversions of section 3.7 (and the `pin_state` parsing of the pin values) at `run` time.

### 3.7 The sequence logic modules

The sequence logic modules `sequences/<name>/logic.py` define subclasses of `SequenceLogic`:

- `__init__(self, transport, log=None)` - `super().__init__(transport)`; stores the log callable (default: silent no-op; the `log_line` of section 3.5 no-ops when it is `None`).
- `run(self, params, on_step=None)` - configures frequency and sample rates, then executes the sequence for the specified scan count. All three `run` methods start from `scans = self.configure(params)` (the shared run header of section 3.5, including the scan-count validation) and build their event lists; a `None` return from `configure` (a scan count below 1, reported as `error: invalid parameters`) ends the run with `None`. The calibration sequence cal_pulse obtains its per-point sweep loop from `SequenceLogic.sweep_results` and its four-column `pulse_width,time,real,imag` CSV format from `SequenceLogic.sweep_save`/`sweep_load` (its `save`/`load` are one-line delegations). `on_step(index, count, payload)` reports progress per sweep point or per scan. The method returns a dictionary mapping keys (either `0` or sweep values) to `(time, data)` tuples - the float32 time axis first, then the complex64 sample array of twice the time-axis length with the samples in the even slots and the odd slots zero - or `None` on read failures, early stops, or negative delays. On completion each sequence logs its completion lines: `FID sequence completed (read time <read_time> µs, <scans> scans)` (fid), `CPMG sequence completed (<echoes> echoes, <scans> scans)` (cpmg), and the `step <i+1>/<n>: width=<v> µs, peak=<v>` lines plus `calibrated 90° pulse width: <pw90> µs` (logged only when the sweep is non-empty) and `pulse calibration completed (<points> points)` (cal_pulse). Missing-key and conversion errors are handled by the caller: the CLI run-phase guard reports them as `error: invalid parameters`, and the GUI path has no guard but the helper's `collect_params` (section 3.8) always supplies the full contract, so no key can be missing.
- The `cal_pulse` fitting pipeline of `sequences/cal_pulse/logic.py` - the module functions `spectrum_from_data` (the exponentially windowed, zero-padded FFT of the even-slot complex samples), `find_resonance_bin`, `resonance_region`, `entropy`, `entropy_phase` (the coarse-to-fine entropy phasing), `resonance_value`, `find_first_peak`, `grid_scores`, and `fit_decaying_sine` (the coarse-to-fine grid search for the damped sine `a + exp(-t/tau) * (b*sin(w*t) + c*cos(w*t))` over the period/tau grid, refined over `FIT_REFINE_PASSES` passes, finishing with the least-squares coefficients).
- `calibrate(results)` - takes the `(time, data)` sweep dictionary, computes the per-point spectra, the entropy phase, and the phase-rotated peak heights, fits the damped sine with `fit_decaying_sine`, and returns `(pw90, widths, heights, fit)` with `fit` the 4-tuple `(x0, period, tau, coefficients)` and `pw90 = period / 4`, or `fit = None` when fewer than four finite points or no first peak is detectable (fewer than three points, or flat heights with zero scale; a non-significant first extremum is still used as the first peak); the per-point log lines of the `run` method use the `step <i+1>/<n>` prefix.
- `params` dict keys (the committed contract of `run`, converted with `int(...)`/`float(...)` inside the logic, with the `pin0` to `pin3` values parsed by `pin_state`): the `[general]` keys of section 3.6 other than `addr` (which the GUI reads directly from `addrValue` and the CLI consumes in the build phase) plus the per-sequence keys, where the contract includes `gain` and `pin0` to `pin3`, consumed by `configure` (section 3.5).
- `stop(self)` - the sequence stop log line plus `SequenceLogic.stop()`.

### 3.8 The sequence UI helpers

The sequence UI helpers `sequences/<name>/ui.py` define subclasses of `SequenceUiHelper` (the shared sequence UI base in `common/sequence_ui.py`, itself a subclass of `PlotWidget`):

- The shared base `SequenceUiHelper` declares the per-sequence class attributes `sequence_name`, `logic_class`, `save_title`, `load_title`, `name_prefix`, and `sequence_settings`, and provides: the per-sequence configuration plumbing `load_config(config)`/`save_config(config)` (read/write the `[sequence]` values of a given `Config` object, data-driven from the `sequence_settings` table; `load_config` uses the two-argument `Config.get`, so a missing key raises `configparser.NoOptionError` (reported by the caller as `error: invalid parameters`), and `load_config` ends with `update_plot_limits()`), the `general_params` reads of the general widgets (`freq`, `rate`, `adc_rate`, `blank`, `polarity`, `delta`, `echo_time`, `read_delay`, `read_time`, `scans`) plus `gain` (`gainValue`) and the four pin checkboxes (`pin0` to `pin3` through `PIN_KEYS`), the lazy `ensure_logic` creation, the `default_name` timestamped file name, the run/save/load orchestration (`start`, `stop`, `save`, `load`, with the `on_step`/`apply_results` hooks), and the `on_motion` readout (with the `motion_x`/`motion_y` hooks, which no sequence overrides). The frame's `apply_config` (section 3.11) calls the loaded helper's `load_config` on sequence load, and the frame's `save_config` calls the helper's `save_config` before saving.
- `__init__(self, main_window, log)` - the `loadUiType` of the per-sequence `layout.ui` (path resolved relative to the sequence directory) runs at module import time; `__init__` calls `super().__init__(main_window, log)`, where the shared base `SequenceUiHelper.__init__(self, main_window=None, log=None)` stores `main_window` (duck-typed; requires `transport` and the general parameter widgets) and `log` (duck-typed; requires `print`) on the base along with `logic = None` and `results = None` (the run result dictionary carried until the next run or a load); the `None` defaults on the shared base make `main_window` and `log` optional there only (the per-sequence `__init__(self, main_window, log)` still requires both); then `setupUi(self)`, and then `setup_plot` with the sequence axis labels and line style. The per-sequence `config.ini` values are not read here: they are applied to the parameter widgets later, when the frame loads the sequence (`apply_config` -> the helper's `load_config`, section 3.11), and the initial plot state is built by the `update_plot_limits` bodies at that point (and again at the start of each run); the calibration helper additionally connects the `startValue`/`stopValue`/`stepValue` `valueChanged` signals to `update_plot_limits`, so the sweep preview is rebuilt live while the user edits those spin boxes.
- `preview_axis(self, reads, delays)` - the shared preview tail of the `FidUiHelper` and `CpmgUiHelper` `update_plot_limits` bodies (the calibration helper's `update_plot_limits` builds the `sweep_values` grid instead): it computes the time axis with the `SequenceLogic.preview` class method (the frame's `adcRateValue` text and `rateValue` index), sets `xdata` to that axis, zeros `data` and `ydata` for the axis length, and calls `update_curve`.
- The calibration helper `CalPulseUiHelper` subclasses `SequenceUiHelper` directly and carries its own `collect_params` (the general parameters plus the `level`, `start`, `stop`, and `step` values), `update_plot_limits` (`clear_fit_curve`, then the `sweep_values` grid of section 3.5 as `xdata` with zeroed `ydata`, then `update_curve`), and `on_step` (the per-point y update and redraw); `FidUiHelper` and `CpmgUiHelper` subclass `SequenceUiHelper` with their own `collect_params` the same way (each helper's `collect_params` is the per-sequence params hook called by `start`); all three helpers define `update_plot_limits` (there is no base implementation; `start()` requires it) - fid via the `preview_axis` call over its read/delays arrays, cpmg via `cpmg_delays`/`cpmg_event_arrays` from its logic module, and the calibration helper via the `sweep_values` grid.
- `start(self)` - called from the frame `run_seq` on the loaded helper: rebuilds the axis/plot state from the current values (`update_plot_limits` is called first), collects `params` from its own widgets and the `main_window` general widgets (mapping of section 3.6), ensures the logic exists (creating it with `main_window.transport` only when absent, via `ensure_logic`) and rebinds `logic.transport` to `main_window.transport` (the frame creates the transport per run, section 3.11, so a persisted logic must track the current run's transport), resets `logic.stopping = False`, and calls `logic.run(params, on_step=self.on_step)`; the `on_step` callback updates the plot per scan or per sweep point; on a non-`None` result it stores `self.results = result` and applies the run result dictionary (the section 3.7 format) to the final plot state via `apply_results`, which also draws the fit curve where applicable; a `None` result leaves `self.results` untouched and returns.
- `apply_results(self, results)` and the `on_step` overrides. The base `apply_results` unpacks `times, data = results[0]` and sets `self.data = data[0::2]`, `self.xdata = times`, `self.ydata = np.abs(self.data)`, and `update_curve()`; `CalPulseUiHelper.apply_results` runs the `calibrate` helper of the logic module (section 3.7), sets `xdata`/`ydata` to the `widths`/`heights`, and, when the fit is non-`None`, draws the damped sine fit curve `a + exp(-(x - x0)/tau) * (b*sin(w*(x - x0)) + c*cos(w*(x - x0)))` on a 200-point grid over the width range with the `90° pulse width = <pw90> µs` label (a failed fit just updates the curve).
- `stop(self)` and `on_motion(self, event)` - inherited from the shared base: `stop` delegates to `self.logic.stop()` only when the logic exists; `on_motion` updates `xdataValue`/`ydataValue` from the snapped `xdata[index]`/`ydata[index]` (through the `motion_x`/`motion_y` hooks).
- `save(self)` and `load(self)` - invoked by the helper's own plot-toolbar data buttons `saveDataButton`/`loadDataButton` (section 3.4). All helpers share the uniform `save()` shape: when `self.results` is `None` or empty, `save()` logs `error: no data to save` and writes nothing; otherwise it opens the save dialog through `save_csv` with the per-sequence title and the `default_name` timestamped file name and, on acceptance, delegates the CSV write to `self.logic.save(self.results, path)`. All helpers share the uniform `load()` shape: `ensure_logic()` first creates the logic exactly as `start()` does (`self.logic = <X>Logic(self.main_window.transport, self.log.print)`) when absent; the `on_load(path)` callback then calls `result = self.logic.load(path)` (the logic-layer load of sections 3.5 and 3.7), returns without changing any state when `result is None` (the plot and `self.results` stay untouched; the `error: <e>` line is already logged by the logic), otherwise stores `self.results = result`, applies the run result dictionary to the plot state via `apply_results`; the dialog opens through `load_csv` with the per-sequence titles. The lazy logic creation makes a `Save data` after a pre-run `Load data` write the loaded data (the saved CSV parses back to exactly the loaded values; a file produced by `Save data` that is re-loaded and re-saved is byte-identical, since both saves go through `np.savetxt`) instead of logging `error: 'NoneType' object has no attribute 'save'` and writing nothing. Behavior note: after any `load()` (run or not) the helper's `self.logic` is non-`None`, so a `stop()` on a helper that loaded data but never ran logs the sequence stop line and sets the logic `stopping` flag; it then sets the transport flag, which raises `AttributeError` when the frame transport is still `None` (no `run_seq` call yet); the frame stop paths are guarded by the `running` state, so no frame behavior changes.
- The UI helpers contain no hardware command logic and no pulse timing logic beyond the preview axis (REQ-02): the fid helper builds its preview over literal read/delays arrays read from the widgets, and the cpmg helper derives its preview delays via `cpmg_delays`/`cpmg_event_arrays` from its logic module (plus the inline `p180 = 2.0 * p90`); the pulse timing and hardware command logic lives in the logic modules.
- Each UI helper imports its logic module as `sequences.<name>.logic` (the intra-package import).
- No module-level import of `app/` (the `main_window` argument is duck-typed; dependency rule of section 4).

### 3.9 app/log_display.py

`class LogDisplay` - the log display:

- `__init__(self, viewer)` - stores the externally owned viewer on `self.viewer`.
- `print(self, text)` - appends one line through `viewer.appendPlainText(text)`.
- `MainWindow.__init__` constructs the component as `self.log = LogDisplay(self.logViewer)` (section 3.11).

### 3.10 Sequence discovery

The sequence discovery functions live in `common/config.py`, which both `app/` modules (`app/main_window.py` and `app/cli_app.py`) already import. The base classes `PlotWidget` (from `common/plot_widget.py`) and `SequenceLogic` (from `common/sequence_logic.py`) are imported at module top, and the `sequences` modules are imported at call time only.

`sequence_dir(name=None)` - the absolute path of `sequences/<name>` when `name` is given, else the `sequences/` directory itself; resolved from the module `__file__`.

`sequence_classes(name)` - the per-name sequence discovery: it imports `sequences.<name>.ui` and `sequences.<name>.logic` via `importlib.import_module` and returns the tuple `(ui_class, logic_class)`. The UI class is the unique subclass of `common.plot_widget.PlotWidget` defined in `sequences.<name>.ui`; the logic class is the unique subclass of `common.sequence_logic.SequenceLogic` defined in `sequences.<name>.logic` (both found by module inspection, matching `cls.__module__` against the module name). A directory missing `ui.py` or `logic.py`, or missing the expected class, fails fast with the raised `ImportError` or `StopIteration`. The call is the automatic validation of a selected sequence directory (section 5).

### 3.11 app/main_window.py

`class MainWindow(QMainWindow)` - the GUI main window frame (the `loadUiType` of `app/main_window.ui`):

- `__init__(self)` - `loadUiType` of `app/main_window.ui` (the frame control panel `controlWidget`/`controlLayout` carries `addrValue` (initial text `192.168.1.100`), `loadSeqButton`, `seqValue` (read-only, initial text `no sequence`), `startSeqButton` (initial text `Start seq.`), `loadCfgButton`, `saveCfgButton`, and the general-parameter widgets; the named layouts are `verticalLayout` (the central layout), `controlLayout`, `pinsLayout`, `seqContainerLayout`, and `logContainerLayout`). Immediately after `setupUi` it sets `self.running = False`, `self.sequence = None`, and `self.transport = None` (no transport at construction; `run_seq` creates one per run and keeps the last run's stopped transport on `self.transport`). The frame layout carries the read-only `logViewer` `QPlainTextEdit` in `logContainerLayout` and the constructor wraps it as `self.log = LogDisplay(self.logViewer)` (section 3.9). Populates `adcRateValue` with the items `122.88` and `125` at default index 1 (125 MSPS), populates `polarityValue` with `neg.`/`pos.` at default index 1, and calls `update_rate_items` to populate `rateValue` from the active table (these calls precede the signal connects, so no connected slot is invoked during construction - the `currentIndexChanged` emissions occur before the connect and are not handled). Sets an `addrValue` regular-expression validator (an IPv4 address or an `rp-<6-hex>.local` name). Wires `loadCfgButton`/`saveCfgButton` to `load_config`/`save_config`, `startSeqButton` to `run_seq`, and `loadSeqButton` to `choose_sequence` (section 5); connects `adcRateValue` `currentIndexChanged` to `update_rate_items` (there are no `gainValue` or `pin0`-`pin3` signal connections - the pin states and the gain are sent as wire commands at run time by the sequence logic's `configure`, section 3.5). The frame widgets start at their `app/main_window.ui` defaults; the `[general]` values are first applied by `load_sequence` from the selected sequence's configuration file (and thereafter by the `load_config` dialog).
- `choose_sequence(self)` - the `loadSeqButton` slot: `directory = QFileDialog.getExistingDirectory(self, "Select sequence directory", str(sequence_dir()))` (the initial directory is the `sequences/` tree); when `directory` is empty (a cancelled dialog) it returns without logging; otherwise it calls `self.load_sequence(Path(directory).name)`. `QFileDialog` is imported at module level (patchable by tests).
- `load_sequence(self, name)` - the dynamic loading mechanism of section 5: (1) validation - when `sequence_dir(name)` is not a directory (a directory outside the `sequences/` tree, or a name that does not exist there), log `error: unknown sequence <name>` and return, loading nothing; when `sequence_classes(name)` raises (a missing `ui.py` or `logic.py`, or a missing expected unique subclass), log `error: <e>` and return, loading nothing (the automatic validation of the selected directory); (2) unload - when a sequence widget is loaded, remove it from `seqContainerLayout`, call `deleteLater()` on it, and clear `self.sequence`; (3) load - instantiate the UI class resolved in step (1) with `(self, self.log)`, add it to `seqContainerLayout`, set `seqValue` to the directory name, and store it in `self.sequence`; (4) apply - `apply_config(Config.sequence_path(name))` (the file's `[general]` values to the frame widgets and its `[sequence]` values to the helper; the apply step is guarded by `except (configparser.Error, ValueError, KeyError, IndexError)` reporting `error: invalid parameters`, and the sequence stays loaded); (5) invariant - at most one sequence is loaded at any time (the previous helper is unloaded first).
- `update_rate_items(self)` - repopulates `rateValue` from the active table (the string forms of the `SequenceLogic.rates_122_88`/`rates_125` lists): the six items `40`, `80`, `160`, `320`, `640`, `1280` when `adcRateValue` is at index 0 (122.88 MSPS), else the six items `25`, `50`, `125`, `250`, `500`, `1250` (125 MSPS), clamping the current index to the new table size.
- `set_controls_enabled(self, enabled)` - sets `enabled` on the loaded sequence's own `controlWidget` (the sequence's parameter panel), then on `loadSeqButton`, `loadCfgButton`, `saveCfgButton`, and the loaded sequence's plot-toolbar data buttons `loadDataButton`/`saveDataButton` (`loadCfgButton` and `saveCfgButton` are the two sequence-configuration buttons); the `startSeqButton` stays untouched (it is the Stop button while a run is in flight), and the frame `controlWidget` is not touched by this method.
- `start_seq(self)` / `finish_seq(self)` - the `running` flag and the `startSeqButton` `Stop seq.`/`Start seq.` text and `clicked` rewire, plus the `set_controls_enabled` call: `start_seq` resets `self.transport.stopping = False` and disables the controls after the button rewire, `finish_seq` re-enables them after restoring the text and the connection.
- `run_seq(self)` - the `running`/no-sequence guard (returns when `running` is `True` or no sequence is loaded); sets `self.running = True` before the connect wait so a second `Start seq.` click during the wait is a no-op (the button is not rewired until `start_seq`); creates `transport = create_transport(self.addrValue.text(), 1001)` and stores it on `self.transport`; when the transport is not connected at construction it waits through the shared `wait_for_connection(transport, CONNECT_TIMEOUT_MS)` of section 3.1, and on a failed wait logs `error: <text>`, stops the transport, clears `running`, and returns without `start_seq`/`finish_seq` (the button text and the control enablement were never changed); otherwise `start_seq`, then the `start()` of the loaded helper (with the logic rebind of section 3.8), inside a `try/finally` that stops the transport and calls `finish_seq` (the frame state - button text, `running` flag, control enablement - is restored even when the helper's `start()` raises). The pin and gain wire commands are sent by the sequence logic's `configure` (section 3.5) during the run, not by the frame. The run stays synchronous on the GUI thread (no locking or threading).
- `stop_seq(self)` - the `stop()` of the loaded helper (sets the stopping flags), guarded by the `running` state (returns when not running) and invoked only when a sequence is loaded (`self.sequence is not None`); the run unwinds at the next stopping check (section 3.5), and the `run_seq` `finally` stops the transport and restores the `Start seq.` state (the graceful stop).
- `apply_config(self, path)` - loads the `Config` at `path`, applies its `[general]` values to the frame widgets (the `addr` line, the table-driven `GENERAL_KEYS` lines with the op dispatch of section 3.5, and the `PIN_KEYS` lines through `pin_state`), and calls the loaded helper's `load_config(config)` (the helper's `sequence_settings` table, ending in `update_plot_limits`); a failure in the apply is caught by `except (configparser.Error, ValueError, KeyError, IndexError)` at its two call sites and reported as `error: invalid parameters` (the sequence stays loaded after `load_sequence`).
- `load_config(self)` / `save_config(self)` - the sequence-configuration file dialogs on `loadCfgButton`/`saveCfgButton`: when no sequence is loaded (`self.sequence is None`) they return without opening a dialog; `load_config` opens `QFileDialog.getOpenFileName(self, "Load configuration", str(Config.sequence_path(self.sequence.sequence_name)), "*.ini")` and, on an accepted path, calls `apply_config(path)` (guarded by `except (configparser.Error, ValueError, KeyError, IndexError)` reporting `error: invalid parameters`); `save_config` opens `QFileDialog.getSaveFileName(self, "Save configuration", str(Config.sequence_path(self.sequence.sequence_name)), "*.ini")` and, on an accepted path, loads that file, writes the `[general]` frame widget values into it (the `addr` line, the table-driven `GENERAL_KEYS` lines with the save mapping of section 3.5, and the `PIN_KEYS` lines), writes the helper's widget values into its `[sequence]` section via the helper's `save_config`, and saves it. A cancelled dialog (empty return) changes nothing and logs nothing; the sequence's default `config.ini` is not written unconditionally by either method; the save dialog's initial file name is the sequence's default `config.ini` at `Config.sequence_path(name)`, so accepting the dialog without renaming overwrites it.

### 3.12 app/cli_app.py

`class CliApp` - the command-line app:

- Module-level `sequence_names()` - the sorted directory names of `sequence_dir()` that are directories and do not start with `__` (the cheap directory listing, no module imports).
- `__init__(self, argv)` - builds `self.sequence_map` by mapping sequence names to their logic classes, failing fast if any sequence is broken (in contrast to the GUI, which validates only the selected directory, on demand, in `load_sequence`). It then uses `argparse` to require a `sequence` name and an `output` filename, exiting the process with status 2 for any parse errors (`argparse` raises `SystemExit(2)`).
- `build_params(self, config)` - reads the raw strings of the `[general]` and `[sequence]` sections with no conversion, guarded per section (a missing section contributes no keys); the logic applies the `int(...)`/`float(...)` conversions of section 3.7 at `run` time.
- `run(self)` - the build phase (load, build, the `addr` read) is guarded by `except (configparser.Error, ValueError, KeyError, IndexError)`, printing `error: invalid parameters` and returning 1. It connects to the specified address via `create_transport`; when the transport is not connected at construction it waits through the shared `wait_for_connection(transport, CONNECT_TIMEOUT_MS)` of section 3.1, printing `error: <text>` (the first collected error) or `error: connection timeout` and returning 1 when the wait fails (unlike the GUI, the CLI does not stop the transport when the wait fails). The pin and gain values ride along in `params` (the raw `build_params` dump, including `gain` and `pin0` to `pin3`) and are sent by `SequenceLogic.configure` (section 3.5) at run time. The logic is instantiated from `sequence_map` with the transport and `print` as the log callable (sequence log lines go to stdout in the CLI). The run phase `logic.run(params)` is guarded by `except (ValueError, KeyError, IndexError)`, printing `error: invalid parameters` and returning 1, and the transport is stopped in a `finally`. A `None` result returns 1. Finally, it saves the result to `args.output` (a save failure is logged as `error: <e>` and still returns 0) and returns 0 on success; the return-1 cases are the ones enumerated above.

### 3.13 Entry points

- `gui.py` - a thin launcher: `QApplication`, the `figure.dpi` rcParam setup, `MainWindow`, `show`, `exec`; imports `sys`, `matplotlib`, `PySide6.QtWidgets.QApplication`, and `app.main_window`.
- `cli.py` - a thin launcher: `sys.exit(CliApp(sys.argv[1:]).run())`; imports `sys` and `app.cli_app`.

## 4. Dependency rules

- The logic modules (`sequences/<seq>/logic.py`) depend only on `common/` (and the standard library and numpy).
- The UI helpers (`sequences/<seq>/ui.py`) depend on their logic module (imported as `sequences.<seq>.logic`) and on `common/` (including the shared sequence UI base `common/sequence_ui.py`, same `common/` layer), plus the standard library, PySide6 (the module-level `loadUiType`), and - for the `fid` and the `cal_pulse` helpers - numpy; no module-level import of `app/`.
- The sequence directories are subdirectories of the `sequences/` directory.
- `common/config.py` depends on `common/` (the base classes `PlotWidget` and `SequenceLogic` at module top) and dynamically imports the `sequences.<name>.ui` and `sequences.<name>.logic` modules at call time only, inside `sequence_classes(name)` (the per-name discovery contract of section 3.10).
- The `app/` modules depend on the sequence modules only through `common.config.sequence_classes` (the per-name discovery of `sequences/`): `app/main_window.py` takes the UI helper class of the selected directory and `app/cli_app.py` the logic classes of the directory listing, and both depend on `common/`.
- The entry points (`gui.py`, `cli.py`) depend on `app/` only (plus the standard library, PySide6, and matplotlib in `gui.py`).
- The `common/` modules depend only on the standard library, numpy, matplotlib (`plot_widget.py`), and PySide6 (`transport.py`, `simulated_transport.py`, `plot_widget.py`; `transport.py` imports `common/simulated_transport` (`SimulatedTransport`) for the `create_transport` factory; `config.py` reaches matplotlib and PySide6 through `plot_widget.py` and numpy through `sequence_logic.py`; `sequence_ui.py` imports `common/sequence_logic` (`PIN_KEYS` and `SequenceLogic`) and `common/plot_widget`; the `sweep_values` grid is imported by the cal_pulse UI helper and its logic module); no `common/` module statically imports a sequence or app module (the call-time imports of `common/config.py` are the documented dynamic exception).
- The graph is a DAG (no cycles): the static chain is entry points -> app/ -> common/ and sequence ui -> sequence logic -> common/, and the app modules reach the sequence UI helper class (`app/main_window.py`) and the logic classes (`app/cli_app.py`) at call time only through `common.config.sequence_classes` (which imports `sequences.<name>.ui` / `sequences.<name>.logic`; the dynamic loading of section 5).

## 5. Dynamic loading mechanism

- There is no startup scan in the GUI and no name-to-class map there: the GUI discovery is per-name and on demand through `common.config.sequence_classes` (section 3.10). The CLI takes its argparse choices from the directory listing of `sequence_dir()` and builds its eager name-to-logic-class `sequence_map` at construction (section 3.12).
- A click of `loadSeqButton` triggers the `MainWindow.choose_sequence` slot, which opens the directory selection dialog `QFileDialog.getExistingDirectory(self, "Select sequence directory", str(sequence_dir()))` (the initial directory is the `sequences/` tree): a cancelled dialog (empty return) changes nothing and logs nothing; a selected directory loads the sequence of the directory name through `MainWindow.load_sequence(name)`.
- `load_sequence(name)` (the full steps are described in section 3.11): (1) validation: when `sequence_dir(name)` is not a directory (a directory outside the `sequences/` tree, or a name that does not exist there), log `error: unknown sequence <name>` and return, loading nothing; when `sequence_classes(name)` raises (a missing `ui.py` or `logic.py`, or a missing expected unique subclass), log `error: <e>` and return, loading nothing (the automatic validation of the selected directory); (2) unload: if a sequence widget is loaded, remove it from `seqContainerLayout`, call `deleteLater()` on it, and clear the loaded helper reference; (3) load: instantiate the UI class resolved in step (1) with `(self, self.log)`, add it to `seqContainerLayout`, set `seqValue` to the directory name, and store it as the loaded helper; (4) apply: `apply_config(Config.sequence_path(name))` (the file's `[general]` values to the frame widgets and its `[sequence]` values to the helper; the apply step is guarded by `except (configparser.Error, ValueError, KeyError, IndexError)` reporting `error: invalid parameters`, and the sequence stays loaded); (5) invariant: at most one sequence is loaded at any time (the previous helper is unloaded first).
- The frame dispatch is the loaded-helper dispatch: the run and stop calls go to the loaded helper (`start()`/`stop()`); the data save/load buttons live on the loaded sequence's own plot toolbar (section 3.4) and call the helper's `save`/`load` directly.

## 6. Transport isolation design

- All program code obtains a transport only through `create_transport` or through constructor injection; no program module instantiates `Transport` or `SimulatedTransport` directly - the only instantiation site is the `create_transport` factory in `common/transport.py`.
- `PULSED_NMR_TRANSPORT=simulated` -> `SimulatedTransport`; any other value or unset -> the TCP `Transport`.
- The logic modules and the app modules use only `send`, `read_samples`, `is_connected`, `start`, `stop`, the `stopping` attribute, and the `connected`/`errorOccurred` signals; both transports expose these with identical names and signatures (behavior simulated where appropriate).
- Test isolation: the test suite sets the environment variable (or injects `SimulatedTransport`), so no test requires a live Red Pitaya device or a network peer (REQ-07); `SimulatedTransport.commands` is the wire-level reference as `(code, data)` integer tuples, whose wire encoding is the packed 64-bit little-endian value `code << 60 | data`.

## 7. Naming conventions

- The configuration sections in use are `[general]` and `[sequence]`.
- Committed class names: `MainWindow`, `LogDisplay`, `CliApp` in `app/`; `Transport`, `SimulatedTransport`, `Config`, `PlotWidget`, `SequenceUiHelper`, `SequenceLogic` in `common/`; the factory function `create_transport` in `common/transport.py`.
- Test file pattern: `test_*.py`, unique file names across the whole `tests/` tree (the four test-level directories carry no `__init__.py`; `tests/` itself carries an empty `__init__.py`); recommended pattern `test_<level>_<topic>.py`.
- Fixtures (shared, in `tests/conftest.py`): `qapp` (session scope), `simulated_env` (autouse, session scope - sets `PULSED_NMR_TRANSPORT=simulated` for the suite), `simulated_transport`, `write_ini`, `config`, `pinned`, `log_display`, `fake_main_window`, `no_qapp` (module scope), `fake_file_dialog`, `inject_hump`, and `inject_nutation`. The same module sets `QT_QPA_PLATFORM=offscreen` at import time (headless GUI) and sorts the collected suite in the order unit -> integration -> system -> acceptance through a `pytest_collection_modifyitems` hook.
- Transport isolation hook: environment variable `PULSED_NMR_TRANSPORT`; the value `simulated` makes `create_transport` return `SimulatedTransport` instead of the TCP transport.

## 8. References

- `README.md` - the project overview and usage.
- `docs/requirements.md` - the requirements document; the requirement IDs `REQ-01` through `REQ-10` cover the entry points, modularity, the GUI, behavior preservation, reuse, the structure, hardware isolation, GUI testability, the Python code style, and defect detection.
- `pyproject.toml` - the project metadata and tool configuration (the pytest `testpaths`, the ruff lint settings, and the black line length).
- `LICENSE` - the license.
