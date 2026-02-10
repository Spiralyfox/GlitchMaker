"""DSP utility functions — fades, normalization, crossfade."""
import numpy as np


def _make_fade_curve(n: int, curve_type: str = "linear") -> np.ndarray:
    """Generate a 0→1 fade curve of n samples."""
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    if curve_type == "exponential":
        return t ** 3
    elif curve_type == "logarithmic":
        return (1.0 - (1.0 - t) ** 3).astype(np.float32)
    elif curve_type == "s_curve":
        return (3 * t ** 2 - 2 * t ** 3).astype(np.float32)
    return t


def fade_in(audio: np.ndarray, duration_samples: int,
            curve_type: str = "linear",
            start_level: float = 0.0, end_level: float = 1.0) -> np.ndarray:
    """Applique un fade in configurable sur les n premiers samples."""
    result = audio.copy()
    n = min(duration_samples, len(result))
    if n <= 0: return result
    curve = _make_fade_curve(n, curve_type)
    curve = start_level + curve * (end_level - start_level)
    if result.ndim == 1:
        result[:n] *= curve
    else:
        for ch in range(result.shape[1]):
            result[:n, ch] *= curve
    return result


def fade_out(audio: np.ndarray, duration_samples: int,
             curve_type: str = "linear",
             start_level: float = 1.0, end_level: float = 0.0) -> np.ndarray:
    """Applique un fade out configurable sur les n derniers samples."""
    result = audio.copy()
    n = min(duration_samples, len(result))
    if n <= 0: return result
    curve = _make_fade_curve(n, curve_type)
    curve = start_level + curve * (end_level - start_level)
    curve = curve[::-1].copy()
    if result.ndim == 1:
        result[-n:] *= curve
    else:
        for ch in range(result.shape[1]):
            result[-n:, ch] *= curve
    return result
