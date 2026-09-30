import numpy as np

SYNC_TIME_US = 1

ADC_RATE_122_88 = 122.88
ADC_RATE_125 = 125

GENERAL_KEYS = [
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
PIN_KEYS = [("pin0", 0), ("pin1", 1), ("pin2", 2), ("pin3", 3)]


def pin_state(value):
    return str(value).strip().lower() in ("1", "true")


def sweep_values(start, stop, step):
    return np.arange(start, stop + step, step, dtype=np.float32)


class SequenceLogic:
    rates_122_88 = [40, 80, 160, 320, 640, 1280]
    rates_125 = [25, 50, 125, 250, 500, 1250]

    def __init__(self, transport):
        self.transport = transport
        self.adc_rate = ADC_RATE_125
        self.cic_rate = 50
        self.last_delay = 0
        self.last_read = 0
        self.size = 0
        self.stopping = False
        self.polarity = 1
        self.log = None

    def log_line(self, text):
        if self.log is not None:
            self.log(text)

    def rate_for(self, index):
        if index < 0:
            raise IndexError(index)
        if self.adc_rate == ADC_RATE_122_88:
            return self.rates_122_88[index]
        return self.rates_125[index]

    def cic_rate_for(self, index):
        return int(self.adc_rate * 1e3 / self.rate_for(index) / 2)

    @classmethod
    def preview(cls, adc_rate, rate_index):
        base = cls(None)
        base.adc_rate = adc_rate
        base.cic_rate = base.cic_rate_for(rate_index)
        return base

    def set_freq(self, value):
        freq = int(value * 1e6 + 0.5)
        self.transport.send(0, freq << 30 | freq)

    def set_rates(self, adc_rate, rate_index):
        self.adc_rate = adc_rate
        self.cic_rate = self.cic_rate_for(rate_index)
        self.transport.send(1, self.cic_rate)

    def set_gain(self, gain):
        self.transport.send(2, int(gain / 50.0 * 4095 + 0.5))

    def set_pin(self, pin, checked):
        self.transport.send(4 if pin_state(checked) else 5, pin)

    def configure(self, params):
        self.set_freq(float(params["freq"]))
        self.set_rates(float(params["adc_rate"]), int(params["rate"]))
        for key, index in PIN_KEYS:
            self.set_pin(index, params[key])
        self.set_gain(int(params["gain"]))
        self.polarity = int(params["polarity"])
        scans = int(params["scans"])
        if scans < 1:
            self.log_line("error: invalid parameters")
            return None
        return scans

    def sweep_results(self, params, points, on_point):
        scans = int(params["scans"])
        level = int(params["level"])
        delta = int(params["delta"]) * 1e3
        blank = int(params["blank"])
        read_delay = int(params["read_delay"])
        read_time = int(params["read_time"])
        results = {}
        for i, sweep_value in enumerate(points):
            if self.stopping:
                return None
            events = [
                {"delay": delta},
                {"delay": SYNC_TIME_US, "sync": 1},
                {"delay": blank, "gate": 1},
                {"delay": sweep_value, "gate": 1, "level": level},
                {"delay": read_delay},
                {"delay": read_time, "read": 1},
            ]
            self.clear_events()
            for event in events:
                self.add_event(**event)
            data = None
            for _ in range(scans):
                if self.stopping:
                    return None
                samples = self.read_scan(i + 1)
                if samples is None:
                    return None
                data = self.accumulate_into(data, samples)
            data /= scans
            reads, delays = self.event_arrays(events)
            results[float(sweep_value)] = (self.compute_time(reads, delays), data)
            on_point(i, points.size, sweep_value, data)
        return results

    def clear_events(self):
        self.last_delay = int(self.adc_rate * self.cic_rate * 2.0 + 0.5)
        self.last_read = 0
        self.size = 0
        self.transport.send(6, 0)

    def update_size(self):
        sz = int(self.last_delay / (self.cic_rate * 2.0) + 0.5)
        if sz > 0:
            self.transport.send(9, self.last_read << 40 | (sz - 1))
        if self.last_read:
            self.size += sz
        self.last_delay = 0
        self.last_read = 0

    def add_event(self, delay, sync=0, gate=0, read=0, level=0, tx_phase=0, rx_phase=0):
        dly = int(delay * self.adc_rate + 0.5)
        lvl = int(level / 100.0 * 32766 + 0.5)
        txp = int(tx_phase / 360.0 * 0x3FFFFFFF + 0.5)
        rxp = int(rx_phase / 360.0 * 0x3FFFFFFF + 0.5)
        if self.polarity == 0:
            gate = 1 - gate
        self.transport.send(7, lvl << 44 | gate << 41 | sync << 40 | (dly - 1))
        self.transport.send(8, rxp << 30 | txp)
        if self.last_read == read:
            self.last_delay += dly
        else:
            self.update_size()
            self.last_delay = dly
            self.last_read = read

    def compute_time(self, reads, delays):
        if reads.size == 0:
            return np.empty(0, dtype=np.float32)
        changes = np.diff(reads, prepend=reads[0])
        group_id = np.cumsum(changes != 0)
        group_start = np.r_[0, np.where(np.diff(group_id) != 0)[0] + 1]
        merged_reads = reads[np.r_[group_start[1:] - 1, reads.size - 1]]
        dly = np.floor(np.asarray(delays, dtype=np.float64) * self.adc_rate + 0.5).astype(np.int64)
        merged_dly = np.add.reduceat(dly, group_start)
        sz = np.floor(merged_dly / (self.cic_rate * 2.0) + 0.5).astype(np.int64)
        skip = int(int(self.adc_rate * self.cic_rate * 2.0 + 0.5) / (self.cic_rate * 2.0) + 0.5)
        skip = np.full(sz.shape, skip, dtype=sz.dtype)
        keep = np.cumsum(np.where(merged_reads, sz, 0)) - np.where(merged_reads, sz, 0)
        skip += np.cumsum(np.where(~merged_reads, sz, 0)) - np.where(~merged_reads, sz, 0)
        read_sizes = sz[merged_reads]
        read_starts = keep[merged_reads] + skip[merged_reads]
        size = int(read_sizes.sum())
        if size == 0:
            return np.empty(0, dtype=np.float32)
        chunks = [np.arange(start, start + length, dtype=np.float32) for start, length in zip(read_starts, read_sizes)]
        time = np.concatenate(chunks, dtype=np.float32)
        return time * (self.cic_rate * 2.0 / self.adc_rate)

    def read_data(self):
        self.update_size()
        if self.size == 0:
            return None
        return self.transport.read_samples(self.size)

    def read_scan(self, point=None):
        samples = self.read_data()
        if samples is None:
            if point is None:
                self.log_line("error: failed to read data")
            else:
                self.log_line(f"error: failed to read data at point {point}")
            return None
        return samples

    def accumulate_into(self, data, samples):
        if data is None:
            return samples
        return data + samples

    def accumulate_step(self, data, scan, scans, on_step):
        samples = self.read_scan()
        if samples is None:
            return data, True
        data = self.accumulate_into(data, samples)
        if on_step is not None:
            on_step(scan, scans, data[0::2] / (scan + 1))
        self.log_line(f"scan {scan + 1}/{scans} completed")
        return data, False

    def accumulate(self, scans, on_step):
        data = None
        for scan in range(scans):
            if self.stopping:
                return None
            data, failed = self.accumulate_step(data, scan, scans, on_step)
            if failed:
                return None
        data /= scans
        return data

    def event_arrays(self, events):
        reads = np.array([bool(event.get("read", 0)) for event in events], dtype=bool)
        delays = np.array([event["delay"] for event in events], dtype=np.float32)
        return reads, delays

    def check_delays(self, delays):
        for value in delays:
            if value < 0:
                self.log_line(f"error: negative delay = {value} µs")
                return False
        return True

    def stop(self):
        self.stopping = True
        self.transport.stopping = True

    def save_file(self, path, columns, header):
        try:
            np.savetxt(path, columns, delimiter=",", header=header, comments="")
            self.log_line(f"saved data to {path}")
        except Exception as e:
            self.log_line(f"error: {e}")

    def save(self, results, path):
        if not results:
            self.log_line("error: no data to save")
            return
        times, data = results[0]
        samples = data[0::2]
        self.save_file(path, np.column_stack((times, samples.real, samples.imag)), "time,real,imag")

    def read_csv_rows(self, path):
        try:
            return np.loadtxt(path, delimiter=",", skiprows=1)
        except Exception as e:
            self.log_line(f"error: {e}")
            return None

    def load(self, path):
        loaded = self.read_csv_rows(path)
        if loaded is None:
            return None
        try:
            times = loaded[:, 0].astype(np.float32)
            samples = (loaded[:, 1] + 1j * loaded[:, 2]).astype(np.complex64)
            data = np.zeros(2 * samples.size, dtype=np.complex64)
            data[0::2] = samples
        except Exception as e:
            self.log_line(f"error: {e}")
            return None
        self.log_line(f"loaded data from {path}")
        return {0: (times, data)}

    def sweep_save(self, results, path):
        if not results:
            self.log_line("error: no data to save")
            return
        chunks = []
        for sweep_value, (times, data) in results.items():
            real_data = data[::2].real
            imag_data = data[::2].imag
            sweep_data = np.full(times.size, sweep_value, dtype=np.float32)
            chunks.append(np.column_stack((sweep_data, times, real_data, imag_data)))
        output = np.concatenate(chunks, axis=0)
        self.save_file(path, output, "pulse_width,time,real,imag")

    def sweep_load(self, path):
        loaded = self.read_csv_rows(path)
        if loaded is None:
            return None
        try:
            sweep_values = loaded[:, 0].astype(np.float32)
            times = loaded[:, 1].astype(np.float32)
            samples = (loaded[:, 2] + 1j * loaded[:, 3]).astype(np.complex64)
            results = {}
            for sweep_value in np.unique(sweep_values):
                mask = sweep_values == sweep_value
                sweep_times = times[mask]
                sweep_samples = samples[mask]
                data = np.zeros(2 * sweep_samples.size, dtype=np.complex64)
                data[0::2] = sweep_samples
                results[sweep_value] = (sweep_times, data)
        except Exception as e:
            self.log_line(f"error: {e}")
            return None
        self.log_line(f"loaded data from {path}")
        return results
