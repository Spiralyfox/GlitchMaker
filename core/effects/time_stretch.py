"""
Effet Time Stretch — Étire ou compresse le temps.
"""

import numpy as np
from scipy.signal import resample
from core.effects.utils import apply_micro_fade


def time_stretch(audio_data: np.ndarray, start: int, end: int,
                 factor: float = 1.5) -> np.ndarray:
    """
    Étire ou compresse le temps sans changer le pitch.
    
    Args:
        factor: >1.0 = plus lent/long, <1.0 = plus rapide/court
    """
    result_before = audio_data[:start].copy()
    segment = audio_data[start:end].copy()
    result_after = audio_data[end:].copy()
    
    if len(segment) == 0:
        return audio_data.copy()
    
    new_len = max(64, int(len(segment) * factor))
    
    if segment.ndim == 1:
        stretched = resample(segment, new_len).astype(np.float32)
    else:
        channels = []
        for ch in range(segment.shape[1]):
            channels.append(resample(segment[:, ch], new_len))
        stretched = np.column_stack(channels).astype(np.float32)
    
    stretched = apply_micro_fade(stretched, fade_samples=64)
    
    return np.concatenate([result_before, stretched, result_after], axis=0)
