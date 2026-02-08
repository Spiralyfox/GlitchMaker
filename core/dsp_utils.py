"""DSP utility functions — fades, normalization, crossfade."""
import numpy as np


def fade_in(audio: np.ndarray, duration_samples: int) -> np.ndarray:
    """Applique un fade in lineaire sur les n premiers samples."""
    result = audio.copy()
    n = min(duration_samples, len(result))
    if n <= 0: return result
    curve = np.linspace(0.0, 1.0, n, dtype=np.float32)
    if result.ndim == 1: result[:n] *= curve
    else:
        for ch in range(result.shape[1]): result[:n, ch] *= curve
    return result


def fade_out(audio: np.ndarray, duration_samples: int) -> np.ndarray:
    """Applique un fade out lineaire sur les n derniers samples."""
    result = audio.copy()
    n = min(duration_samples, len(result))
    if n <= 0: return result
    curve = np.linspace(1.0, 0.0, n, dtype=np.float32)
    if result.ndim == 1: result[-n:] *= curve
    else:
        for ch in range(result.shape[1]): result[-n:, ch] *= curve
    return result
