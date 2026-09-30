import numpy as np

from common.sequence_logic import SYNC_TIME_US, SequenceLogic


def cpmg_delays(p90, echo_time, blank, read_delay, read_time):
    p180 = 2.0 * p90
    if read_delay + read_time > echo_time - blank - p180:
        read_time = echo_time - blank - p180 - read_delay
    d1 = echo_time / 2.0 - p90 / 2.0 - p180 / 2.0 - blank
    d2 = read_delay
    d3 = echo_time - blank - p180 - read_delay - read_time
    return read_time, d1, d2, d3


def cpmg_event_arrays(delta, blank, p90, p180, d1, d2, d3, read_time, echoes):
    prefix_reads = np.zeros(5, dtype=bool)
    prefix_delays = np.array([delta, SYNC_TIME_US, blank, p90, d1], dtype=np.float32)
    block_reads = np.array([False, False, False, True, False], dtype=bool)
    block_delays = np.array([blank, p180, d2, read_time, d3], dtype=np.float32)
    reads = np.concatenate([prefix_reads, np.tile(block_reads, echoes)])
    delays = np.concatenate([prefix_delays, np.tile(block_delays, echoes)])
    return reads, delays


class CpmgLogic(SequenceLogic):
    def __init__(self, transport, log=None):
        super().__init__(transport)
        self.log = log

    def run(self, params, on_step=None):
        scans = self.configure(params)
        if scans is None:
            return None
        level = int(params["level"])
        delta = int(params["delta"]) * 1e3
        blank = int(params["blank"])
        p90 = int(params["width"])
        p180 = 2.0 * p90
        echo_time = int(params["echo_time"])
        echoes = int(params["echoes"])
        read_delay = int(params["read_delay"])
        read_time = int(params["read_time"])
        read_time, d1, d2, d3 = cpmg_delays(p90, echo_time, blank, read_delay, read_time)
        if not self.check_delays([delta, blank, p90, d1, p180, d2, read_time, d3]):
            return None
        data = None
        for scan in range(scans):
            if self.stopping:
                return None
            events = [
                {"delay": delta},
                {"delay": SYNC_TIME_US, "sync": 1},
                {"delay": blank, "gate": 1},
                {"delay": p90, "gate": 1, "level": level, "tx_phase": (scan % 4) * 90.0},
                {"delay": d1},
            ]
            for _ in range(echoes):
                events.extend(
                    [
                        {"delay": blank, "gate": 1},
                        {"delay": p180, "gate": 1, "level": level, "tx_phase": ((scan + 1) % 4) * 90.0},
                        {"delay": d2},
                        {"delay": read_time, "read": 1, "rx_phase": ((scan + 2) % 4) * 90.0},
                    ]
                )
                if d3 > 0:
                    events.append({"delay": d3})
            self.clear_events()
            for event in events:
                self.add_event(**event)
            data, failed = self.accumulate_step(data, scan, scans, on_step)
            if failed:
                return None
        data /= scans
        self.log_line(f"CPMG sequence completed ({echoes} echoes, {scans} scans)")
        reads, delays = cpmg_event_arrays(delta, blank, p90, p180, d1, d2, d3, read_time, echoes)
        return {0: (self.compute_time(reads, delays), data)}

    def stop(self):
        self.log_line("CPMG sequence stopped")
        super().stop()
