"""
Effet Stutter / Repeat — Répète une zone pour créer un bégaiement.
Le fameux "Bonjou-ou-ou-ou-r" du glitchcore.
"""

import numpy as np
from core.effects.utils import apply_micro_fade


def stutter(audio_data: np.ndarray, start: int, end: int,
            repeats: int = 4, decay: float = 0.0,
            stutter_mode: str = "normal") -> np.ndarray:
    """
    Prend la zone [start:end] et la répète.
    
    Args:
        audio_data: Array audio complet
        start: Sample de début de la zone
        end: Sample de fin de la zone
        repeats: Nombre de répétitions (2-32)
        decay: Diminution du volume par répétition (0.0 = pas de decay, 0.5 = -50% par rep)
        stutter_mode: 
            "normal" = répète le segment tel quel
            "halving" = chaque répétition fait la moitié de la précédente
            "reverse_alt" = alterne normal et inversé
    
    Returns:
        Audio avec l'effet stutter appliqué
    """
    segment = audio_data[start:end].copy()
    
    if len(segment) == 0:
        return audio_data.copy()
    
    # Appliquer micro fade pour éviter les clics
    segment = apply_micro_fade(segment, fade_samples=min(64, len(segment) // 4))
    
    parts = []
    
    for i in range(repeats):
        if stutter_mode == "halving":
            # Chaque répétition est 2x plus courte
            length = max(64, len(segment) // (2 ** i))
            part = segment[:length].copy()
        elif stutter_mode == "reverse_alt":
            # Alterne normal / inversé
            if i % 2 == 0:
                part = segment.copy()
            else:
                part = segment[::-1].copy()
        else:
            part = segment.copy()
        
        # Appliquer le decay
        if decay > 0:
            volume = (1.0 - decay) ** i
            part = part * volume
        
        # Micro fade
        part = apply_micro_fade(part, fade_samples=min(32, len(part) // 4))
        parts.append(part)
    
    stuttered = np.concatenate(parts, axis=0)
    
    # Reconstruire l'audio : avant + stutter + après
    before = audio_data[:start]
    after = audio_data[end:]
    
    result = np.concatenate([before, stuttered, after], axis=0)
    return result


def quick_stutter(audio_data: np.ndarray, start: int, end: int,
                  slice_count: int = 8) -> np.ndarray:
    """
    Stutter rapide : découpe la zone en N tranches et répète chacune 2x.
    Crée un effet de bégaiement rapide type glitchcore.
    """
    segment = audio_data[start:end]
    if len(segment) == 0:
        return audio_data.copy()
    
    slice_len = max(64, len(segment) // slice_count)
    parts = []
    
    for i in range(slice_count):
        s = i * slice_len
        e = min(s + slice_len, len(segment))
        if s >= len(segment):
            break
        sl = segment[s:e].copy()
        sl = apply_micro_fade(sl, fade_samples=min(16, len(sl) // 4))
        parts.append(sl)
        parts.append(sl)  # Répète chaque tranche
    
    stuttered = np.concatenate(parts, axis=0)
    
    before = audio_data[:start]
    after = audio_data[end:]
    return np.concatenate([before, stuttered, after], axis=0)
