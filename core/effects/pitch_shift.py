"""
Effet Pitch Shift — Monte ou descend le pitch.
Voix "anime" digicore, ou grave/démoniaque.
"""

import numpy as np
from scipy.signal import resample
from core.effects.utils import apply_micro_fade


def pitch_shift(audio_data: np.ndarray, start: int, end: int,
                semitones: float = 3.0, sr: int = 44100) -> np.ndarray:
    """
    Change le pitch sans (trop) changer la durée.
    Utilise resample + time correction.
    
    Args:
        semitones: Demi-tons (-12 = une octave en bas, +12 = une octave en haut)
        sr: Sample rate
    """
    result = audio_data.copy()
    segment = result[start:end].copy()
    
    if len(segment) == 0:
        return result
    
    # Facteur de pitch
    factor = 2.0 ** (semitones / 12.0)
    original_len = len(segment)
    
    # Resample pour changer le pitch
    new_len = int(original_len / factor)
    if new_len < 2:
        return result
    
    if segment.ndim == 1:
        shifted = resample(segment, new_len)
        # Re-resample pour retrouver la durée originale
        shifted = resample(shifted, original_len)
    else:
        channels = []
        for ch in range(segment.shape[1]):
            ch_shifted = resample(segment[:, ch], new_len)
            ch_shifted = resample(ch_shifted, original_len)
            channels.append(ch_shifted)
        shifted = np.column_stack(channels)
    
    shifted = apply_micro_fade(shifted.astype(np.float32), fade_samples=64)
    result[start:end] = shifted[:len(result[start:end])]
    return np.clip(result, -1.0, 1.0)


def pitch_shift_simple(audio_data: np.ndarray, start: int, end: int,
                       semitones: float = 3.0) -> np.ndarray:
    """
    Pitch shift simple (change aussi la durée) — effet "chipmunk" ou "ralenti".
    Plus rapide et plus glitchy que le pitch shift corrigé.
    """
    result_before = audio_data[:start].copy()
    segment = audio_data[start:end].copy()
    result_after = audio_data[end:].copy()
    
    if len(segment) == 0:
        return audio_data.copy()
    
    factor = 2.0 ** (semitones / 12.0)
    new_len = int(len(segment) / factor)
    if new_len < 2:
        return audio_data.copy()
    
    if segment.ndim == 1:
        shifted = resample(segment, new_len)
    else:
        channels = []
        for ch in range(segment.shape[1]):
            channels.append(resample(segment[:, ch], new_len))
        shifted = np.column_stack(channels)
    
    shifted = apply_micro_fade(shifted.astype(np.float32), fade_samples=64)
    
    return np.concatenate([result_before, shifted, result_after], axis=0)
