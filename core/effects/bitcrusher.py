"""
Effet Bitcrusher — Réduit la résolution en bits et/ou le sample rate.
Son lo-fi digital crunchy, signature PC Music / SOPHIE.
"""

import numpy as np


def bitcrush(audio_data: np.ndarray, start: int, end: int,
             bit_depth: int = 8, downsample: int = 4) -> np.ndarray:
    """
    Réduit la résolution du signal.
    
    Args:
        audio_data: Array audio complet
        start: Sample de début
        end: Sample de fin
        bit_depth: Profondeur en bits (1-16, 8 = lo-fi classique, 4 = très écrasé)
        downsample: Facteur de réduction du sample rate (1=pas de réduction, 8=très écrasé)
    
    Returns:
        Audio avec bitcrusher appliqué sur la zone
    """
    result = audio_data.copy()
    segment = result[start:end].copy()
    
    if len(segment) == 0:
        return result
    
    # Réduction de bits (quantification)
    bit_depth = max(1, min(16, bit_depth))
    levels = 2 ** bit_depth
    segment = np.round(segment * levels) / levels
    
    # Réduction de sample rate (sample & hold)
    downsample = max(1, min(64, downsample))
    if downsample > 1:
        if segment.ndim == 1:
            held = np.repeat(segment[::downsample], downsample)
            segment = held[:len(result[start:end])]
        else:
            for ch in range(segment.shape[1]):
                held = np.repeat(segment[::downsample, ch], downsample)
                segment[:len(held), ch] = held[:len(segment)]
    
    result[start:end] = segment[:len(result[start:end])]
    return result
