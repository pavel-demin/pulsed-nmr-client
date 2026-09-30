from common.sequence_logic import SYNC_TIME_US, SequenceLogic


class FidLogic(SequenceLogic):
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
        read_delay = int(params["read_delay"])
        read_time = int(params["read_time"])
        events = [
            {"delay": delta},
            {"delay": SYNC_TIME_US, "sync": 1},
            {"delay": blank, "gate": 1},
            {"delay": p90, "gate": 1, "level": level},
            {"delay": read_delay},
            {"delay": read_time, "read": 1},
        ]
        if not self.check_delays([delta, blank, p90, read_delay, read_time]):
            return None
        self.clear_events()
        for event in events:
            self.add_event(**event)
        data = self.accumulate(scans, on_step)
        if data is None:
            return None
        reads, delays = self.event_arrays(events)
        self.log_line(f"FID sequence completed (read time {read_time} µs, {scans} scans)")
        return {0: (self.compute_time(reads, delays), data)}

    def stop(self):
        self.log_line("FID sequence stopped")
        super().stop()
