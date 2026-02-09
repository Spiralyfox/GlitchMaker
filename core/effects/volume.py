"""Volume / Gain — adjust loudness from 0% to 10000%."""
import numpy as np

def volume(audio_data: np.ndarray, start: int, end: int,
           gain_pct: float = 100.0) -> np.ndarray:
    """Change le volume du segment."""
    out = audio_data.copy()
    g = gain_pct / 100.0
    out[start:end] = (out[start:end] * g).clip(-1.0, 1.0)
    return out
