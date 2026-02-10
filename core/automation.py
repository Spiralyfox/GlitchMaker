"""Automation system — automate effect parameters over time (multi-param)."""
import numpy as np
from utils.logger import get_logger

_log = get_logger("automation")

# ── Automatable parameters per effect ──
# (param_key, display_name, min, max, default, step)
AUTOMATABLE_PARAMS = {
    "volume":     [("gain_pct",  "Gain (%)",       0,   1000,  100,   1)],
    "filter":     [("cutoff_hz", "Cutoff (Hz)",    20,  20000, 1000,  10),
                   ("resonance", "Resonance",       0.1, 20,    1.0,   0.1)],
    "pan":        [("pan",       "Pan",            -1.0, 1.0,   0.0,   0.01)],
    "pitch_shift":[("semitones", "Semitones",      -24,  24,    0,     0.5)],
    "saturation": [("drive",     "Drive",           0,   100,   20,    1)],
    "distortion": [("drive",     "Drive",           0,   100,   50,    1),
                   ("tone",      "Tone",            0,   100,   50,    1)],
    "bitcrusher": [("bit_depth", "Bit Depth",       2,   16,    16,    1),
                   ("downsample","Downsample",       1,   64,    1,     1)],
    "chorus":     [("depth_ms",  "Depth (ms)",      0.1, 20,    5,     0.1),
                   ("rate_hz",   "Rate (Hz)",       0.1, 10,    1.5,   0.1),
                   ("mix",       "Mix",             0,   1,     0.5,   0.01)],
    "phaser":     [("rate_hz",   "Rate (Hz)",       0.05, 5,    0.5,   0.05),
                   ("depth",     "Depth",           0,   1,     0.5,   0.01),
                   ("mix",       "Mix",             0,   1,     0.5,   0.01)],
    "tremolo":    [("rate_hz",   "Rate (Hz)",       0.5, 30,    5,     0.5),
                   ("depth",     "Depth",           0,   1,     0.7,   0.01)],
    "ring_mod":   [("frequency", "Frequency (Hz)",  20,  5000,  440,   1),
                   ("mix",       "Mix",             0,   1,     0.5,   0.01)],
    "delay":      [("delay_ms",  "Delay (ms)",      10,  2000,  300,   10),
                   ("feedback",  "Feedback",         0,   0.95,  0.4,   0.05),
                   ("mix",       "Mix",             0,   1,     0.5,   0.01)],
    "vinyl":      [("amount",    "Amount",          0,   1,     0.5,   0.01)],
    "ott":        [("depth",     "Depth",           0,   1,     0.5,   0.01)],
    "stutter":    [("repeats",   "Repeats",         1,   32,    4,     1)],
    "granular":   [("grain_ms",  "Grain (ms)",      5,   200,   50,    1),
                   ("density",   "Density",         0.1, 10,    2,     0.1),
                   ("chaos",     "Chaos",           0,   1,     0.3,   0.01)],
}


def interpolate_curve(points: list, x: float) -> float:
    """Interpolate y value at normalized x (0-1) from sorted control points."""
    if not points:
        return 0.0
    if len(points) == 1:
        return points[0][1]
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return points[-1][1]


def apply_automation_multi(audio: np.ndarray, start: int, end: int,
                           process_fn, auto_params: list, sr: int,
                           chunk_size: int = 2048) -> np.ndarray:
    """Apply an effect with multiple automated/constant parameters.

    auto_params: list of dicts, each with:
      - key: parameter name
      - mode: "automated" or "constant"
      For "automated": default_val, target_val, curve_points
      For "constant": value
    """
    result = audio.copy()
    start = int(start)
    end = int(end)
    chunk_size = int(chunk_size)
    region_len = end - start
    if region_len < 1:
        return result

    pos = start
    while pos < end:
        c_end = min(pos + chunk_size, end)
        norm_x = (pos - start) / region_len if region_len > 0 else 0

        chunk_params = {}
        for ap in auto_params:
            key = ap["key"]
            if ap.get("mode") == "constant":
                chunk_params[key] = ap["value"]
            else:
                curve = ap.get("curve_points", [(0, 0), (1, 1)])
                ny = interpolate_curve(curve, norm_x)
                dv = ap.get("default_val", 0)
                tv = ap.get("target_val", 1)
                chunk_params[key] = dv + ny * (tv - dv)

        seg_len = c_end - pos
        segment = result[pos:c_end].copy()
        try:
            processed = process_fn(segment, 0, seg_len, sr=sr, **chunk_params)
            if processed is not None and len(processed) == seg_len:
                result[pos:c_end] = processed
        except Exception as ex:
            _log.debug("Automation chunk error at %d: %s", pos, ex)
        pos = c_end

    return result


# Backward compat
def apply_automation(audio, start, end, process_fn, base_params,
                     param_name, default_val, target_val,
                     curve_points, sr, chunk_size=2048):
    ap = [{"key": param_name, "mode": "automated",
           "default_val": default_val, "target_val": target_val,
           "curve_points": curve_points}]
    return apply_automation_multi(audio, start, end, process_fn, ap, sr, chunk_size)
