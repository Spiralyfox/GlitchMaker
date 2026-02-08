"""Chorus — doubles the signal with slight pitch/time variations for thickness."""
import numpy as np

def chorus(audio_data: np.ndarray, start: int, end: int,
           depth_ms: float = 5.0, rate_hz: float = 1.5,
           mix: float = 0.5, voices: int = 2, sr: int = 44100) -> np.ndarray:
    """Applique un effet chorus (doublement avec modulation)."""
    out = audio_data.copy()
    seg = out[start:end].astype(np.float64)
    n = len(seg)
    depth_samp = int(depth_ms * sr / 1000.0)
    t_arr = np.arange(n, dtype=np.float64) / sr
    result = seg.copy()
    for v in range(voices):
        phase = 2.0 * np.pi * v / max(voices, 1)
        delay_mod = (depth_samp * (1.0 + np.sin(2.0 * np.pi * rate_hz * t_arr + phase)) / 2.0).astype(int)
        indices = np.arange(n) - delay_mod
        indices = np.clip(indices, 0, n - 1)
        if seg.ndim == 2:
            for ch in range(seg.shape[1]):
                result[:, ch] += seg[indices, ch]
        else:
            result += seg[indices]
    result = result / (1 + voices)
    out[start:end] = (seg * (1 - mix) + result * mix).astype(np.float32)
    return out
