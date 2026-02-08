"""Tremolo — rhythmic volume wobble."""
import numpy as np

def tremolo(audio_data: np.ndarray, start: int, end: int,
            rate_hz: float = 5.0, depth: float = 0.7,
            shape: str = "sine", sr: int = 44100) -> np.ndarray:
    """Modulation d amplitude periodique."""
    out = audio_data.copy()
    seg = out[start:end].astype(np.float64)
    n = len(seg)
    t_arr = np.arange(n, dtype=np.float64) / sr
    if shape == "sine":
        lfo = 0.5 * (1.0 + np.sin(2.0 * np.pi * rate_hz * t_arr))
    elif shape == "square":
        lfo = (np.sin(2.0 * np.pi * rate_hz * t_arr) >= 0).astype(np.float64)
    elif shape == "triangle":
        lfo = 2.0 * np.abs(2.0 * (rate_hz * t_arr - np.floor(rate_hz * t_arr + 0.5)))
    else:
        lfo = np.mod(rate_hz * t_arr, 1.0)
    envelope = 1.0 - depth * (1.0 - lfo)
    if seg.ndim == 2:
        envelope = envelope.reshape(-1, 1)
    out[start:end] = (seg * envelope).astype(np.float32)
    return out
