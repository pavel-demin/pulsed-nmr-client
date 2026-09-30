import numpy as np

from common.sequence_logic import SequenceLogic, sweep_values

LINE_BROADENING = 0.5
FFT_OVERRSAMPLE = 2

PHASE_STEPS = 180
PHASE_REFINEMENTS = 3
RESONANCE_HALF_WIDTH = 3
PHASE_HALF_WIDTH = 20
ENTROPY_BINS = 64
BASELINE_EDGE_WIDTH = 5

FIRST_PEAK_MAX_WIDTH = 40.0
PEAK_SIGNIFICANCE = 0.10

FIT_WIDTH_MAX = 100.0
FIT_PERIOD_MIN = 4.0
FIT_PERIOD_MAX_FACTOR = 4.0
FIT_PERIOD_POINTS = 250
FIT_TAU_POINTS = 50
FIT_REFINE_PERIOD_POINTS = 40
FIT_REFINE_TAU_POINTS = 30
FIT_REFINE_PASSES = 2


def spectrum_from_data(data):
    fids = data[0::2]
    size = fids.size
    if size > 1:
        n = np.arange(size, dtype=float)
        window = np.exp(-np.pi * LINE_BROADENING * n / (size - 1))
        fids = fids * window
    padded = np.zeros(FFT_OVERRSAMPLE * size, dtype=complex)
    padded[:size] = fids
    return np.fft.fftshift(np.fft.fft(padded))


def find_resonance_bin(spectra):
    magnitude = np.abs(spectra)
    maxima = np.max(magnitude, axis=1)
    normalized = np.zeros_like(magnitude, dtype=float)
    valid = maxima > 0.0
    normalized[valid] = magnitude[valid] / maxima[valid, None]
    profile = np.median(normalized, axis=0)
    return int(np.argmax(profile))


def resonance_region(spectrum, peak_bin):
    start = max(0, peak_bin - PHASE_HALF_WIDTH)
    stop = min(spectrum.size, peak_bin + PHASE_HALF_WIDTH + 1)
    region = spectrum[start:stop]
    edge_width = min(BASELINE_EDGE_WIDTH, region.size // 2)
    if edge_width <= 0:
        return region
    baseline = np.median(np.concatenate((region[:edge_width], region[-edge_width:])))
    return region - baseline


def entropy(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.inf
    lo, hi = x.min(), x.max()
    if hi <= lo:
        return 0.0
    counts, _ = np.histogram(x, bins=ENTROPY_BINS, range=(lo, hi))
    total = counts.sum()
    if total == 0:
        return np.inf
    p = counts.astype(float) / total
    p = p[p > 0]
    return float(-np.sum(p * np.log(p)))


def entropy_phase(spectrum, peak_bin):
    region = resonance_region(spectrum, peak_bin)
    if region.size == 0:
        return 0.0
    lo, hi = 0.0, np.pi
    best_phase = 0.0
    for _ in range(PHASE_REFINEMENTS):
        phases = np.linspace(lo, hi, PHASE_STEPS, endpoint=False)
        scores = np.empty(PHASE_STEPS)
        for i, phase in enumerate(phases):
            real = (region * np.exp(-1j * phase)).real
            scores[i] = entropy(real)
        k = int(np.argmin(scores))
        best_phase = float(phases[k])
        step = (hi - lo) / PHASE_STEPS
        lo = max(0.0, best_phase - step)
        hi = min(np.pi, best_phase + step)
    return best_phase


def resonance_value(spectrum, peak_bin):
    real = spectrum.real
    n = real.size
    start = max(0, peak_bin - RESONANCE_HALF_WIDTH)
    stop = min(n, peak_bin + RESONANCE_HALF_WIDTH + 1)
    left_start = max(0, start - BASELINE_EDGE_WIDTH - 3)
    left_stop = start - 3
    right_start = stop + 3
    right_stop = min(n, right_start + BASELINE_EDGE_WIDTH)
    baseline_values = []
    if left_stop > left_start:
        baseline_values.extend(real[left_start:left_stop])
    if right_stop > right_start:
        baseline_values.extend(real[right_start:right_stop])
    baseline = np.median(baseline_values) if baseline_values else 0.0
    return float(np.mean(real[start:stop] - baseline))


def find_first_peak(heights):
    y = np.asarray(heights, dtype=float)
    if y.size < 3:
        return None
    baseline = np.median(y)
    y0 = y - baseline
    scale = float(np.max(np.abs(y0)))
    if scale <= 0.0:
        return None
    d = np.diff(y0)
    peaks = (d[:-1] >= 0.0) & (d[1:] <= 0.0)
    mins = (d[:-1] <= 0.0) & (d[1:] >= 0.0)
    extrema = np.where(peaks | mins)[0] + 1
    if extrema.size == 0:
        return int(np.argmax(np.abs(y0)))
    significant = extrema[np.abs(y0[extrema]) >= PEAK_SIGNIFICANCE * scale]
    if significant.size:
        return int(significant[0])
    return int(extrema[0])


def grid_scores(periods, taus, t, y):
    omega = (2.0 * np.pi / periods)[:, None]
    sin = np.sin(omega * t[None, :])
    cos = np.cos(omega * t[None, :])
    y2 = float(np.dot(y, y))
    eye3 = np.eye(3)
    scores = np.empty((taus.size, periods.size))
    for j, tau in enumerate(taus):
        env = np.exp(-t / tau)
        m = np.stack(
            (np.ones_like(sin), env[None, :] * sin, env[None, :] * cos),
            axis=2,
        )
        g = np.einsum("pni,pnj->pij", m, m)
        b = np.einsum("pni,n->pi", m, y)
        g = g + 1e-12 * float(np.abs(g).max()) * eye3
        coeff = np.linalg.solve(g, b[..., None])[..., 0]
        scores[j] = y2 - np.einsum("pi,pi->p", b, coeff)
    return scores


def fit_decaying_sine(widths, heights):
    x = np.asarray(widths, dtype=float)
    y = np.asarray(heights, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]

    if x.size < 4:
        return 0.0, 0.0, 1.0, None

    order = np.argsort(x)
    x, y = x[order], y[order]
    x0 = x.min()
    t = x - x0
    span = t.max()
    differences = np.diff(x)
    positive = differences[differences > 0]
    spacing = np.median(positive) if positive.size else span
    period_min = max(FIT_PERIOD_MIN, 2.0 * spacing)
    period_max = max(period_min * 2.0, FIT_PERIOD_MAX_FACTOR * span)
    tau_min = max(span / 20.0, 1e-6)
    tau_max = max(span * 20.0, tau_min * 10.0)

    periods = np.linspace(period_min, period_max, FIT_PERIOD_POINTS)
    taus = np.geomspace(tau_min, tau_max, FIT_TAU_POINTS)

    best_rss = np.inf
    best_period = float(periods[0])
    best_tau = float(taus[0])

    for pass_no in range(1 + FIT_REFINE_PASSES):
        scores = grid_scores(periods, taus, t, y)
        j, k = np.unravel_index(int(np.argmin(scores)), scores.shape)

        if scores[j, k] < best_rss:
            best_rss = float(scores[j, k])
            best_period = float(periods[k])
            best_tau = float(taus[j])

        if pass_no == FIT_REFINE_PASSES:
            break

        p_step = (periods[-1] - periods[0]) / max(periods.size - 1, 1)
        t_factor = 2.0 ** (1.0 / (2.0**pass_no))

        lo_p = max(period_min, best_period - 2.0 * p_step)
        hi_p = min(period_max, best_period + 2.0 * p_step)
        lo_t = max(tau_min, best_tau / t_factor)
        hi_t = min(tau_max, best_tau * t_factor)

        if hi_p > lo_p:
            periods = np.linspace(lo_p, hi_p, FIT_REFINE_PERIOD_POINTS)
        if hi_t > lo_t:
            taus = np.geomspace(lo_t, hi_t, FIT_REFINE_TAU_POINTS)

    omega = 2.0 * np.pi / best_period
    env = np.exp(-t / best_tau)
    matrix = np.column_stack((np.ones_like(t), env * np.sin(omega * t), env * np.cos(omega * t)))

    coefficients, _, _, _ = np.linalg.lstsq(matrix, y, rcond=None)

    return x0, best_period, best_tau, coefficients


def calibrate(results):
    widths = np.array(list(results), dtype=float)
    if widths.size == 0:
        return 0.0, np.empty(0, dtype=float), np.empty(0, dtype=float), None
    spectra = np.asarray([spectrum_from_data(value[1]) for value in results.values()], dtype=complex)
    peak_bin = find_resonance_bin(spectra)
    early = np.where(widths <= FIRST_PEAK_MAX_WIDTH)[0]

    if early.size == 0:
        early = np.arange(widths.size)

    strengths = np.asarray([np.max(np.abs(resonance_region(spectra[i], peak_bin))) for i in early])
    initial_reference = int(early[np.argmax(strengths)])
    phase = entropy_phase(spectra[initial_reference], peak_bin)
    rotated = spectra * np.exp(-1j * phase)
    heights = np.asarray([resonance_value(rotated[i], peak_bin) for i in range(rotated.shape[0])])
    first_peak = find_first_peak(heights)

    if first_peak is None:
        return 0.0, widths, heights, None

    if heights[first_peak] < 0.0:
        phase = (phase + np.pi) % (2.0 * np.pi)
        rotated = spectra * np.exp(-1j * phase)
        heights = np.asarray([resonance_value(rotated[i], peak_bin) for i in range(rotated.shape[0])])

    x0, period, tau, coefficients = fit_decaying_sine(widths, heights)

    if coefficients is None:
        return 0.0, widths, heights, None

    return period / 4.0, widths, heights, (x0, period, tau, coefficients)


class CalPulseLogic(SequenceLogic):
    def __init__(self, transport, log=None):
        super().__init__(transport)
        self.log = log

    def run(self, params, on_step=None):
        scans = self.configure(params)
        if scans is None:
            return None
        sweep_start = int(params["start"])
        sweep_stop = int(params["stop"])
        sweep_step = int(params["step"])
        points = sweep_values(sweep_start, sweep_stop, sweep_step)
        fixed_delays = [
            int(params["delta"]) * 1e3,
            int(params["blank"]),
            int(params["read_delay"]),
            int(params["read_time"]),
        ]
        if not self.check_delays(fixed_delays + list(points)):
            return None

        def on_point(i, count, sweep_value, data):
            peak = float(np.abs(spectrum_from_data(data)).max())
            if on_step is not None:
                on_step(i, count, peak)
            self.log_line(f"step {i + 1}/{count}: width={sweep_value:.3f} µs, peak={peak:.3f}")

        results = self.sweep_results(params, points, on_point)
        if results is None:
            return None
        if points.size > 0:
            pw90, _, _, _ = calibrate(results)
            self.log_line(f"calibrated 90° pulse width: {pw90:.3f} µs")
        self.log_line(f"pulse calibration completed ({points.size} points)")
        return results

    def stop(self):
        self.log_line("pulse calibration stopped")
        super().stop()

    def save(self, results, path):
        self.sweep_save(results, path)

    def load(self, path):
        return self.sweep_load(path)
