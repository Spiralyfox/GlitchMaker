"""
Effet Reverse — Inverse une zone du sample.
"""

import numpy as np
from core.effects.utils import apply_micro_fade


def reverse(audio_data: np.ndarray, start: int, end: int) -> np.ndarray:
    """Inverse la zone [start:end]."""
    result = audio_data.copy()
    result[start:end] = result[start:end][::-1]
    # Micro fade pour éviter les clics aux jointures
    fade = min(64, (end - start) // 4)
    if fade > 0:
        result[start:start+fade] = apply_micro_fade(
            result[start:start+fade], fade_samples=fade
        )
    return result
