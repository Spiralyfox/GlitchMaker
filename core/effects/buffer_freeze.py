"""
Buffer Freeze — Gele un court fragment et le repete en boucle.
Cree un drone / texture statique a partir d'un instant precis.
"""

import numpy as np
from core.effects.utils import apply_micro_fade


def buffer_freeze(audio_data: np.ndarray, start: int, end: int,
                  grain_ms: float = 80.0, repeats: int = 0,
                  sr: int = 44100) -> np.ndarray:
    """Capture un grain au debut de la zone et le boucle.
    repeats=0 signifie remplir toute la zone."""
    result = audio_data.copy()
    segment = result[start:end]
    if len(segment) == 0:
        return result

    # Extraire le grain a geler
    grain_len = max(64, int(grain_ms * sr / 1000.0))
    grain_len = min(grain_len, len(segment))
    grain = segment[:grain_len].copy()
    grain = apply_micro_fade(grain, fade_samples=min(32, grain_len // 4))

    # Nombre de repetitions
    target_len = end - start
    if repeats <= 0:
        n_reps = max(1, target_len // grain_len + 1)
    else:
        n_reps = repeats

    # Construire la sortie par repetition du grain
    parts = [grain] * n_reps
    frozen = np.concatenate(parts, axis=0)

    # Ajuster a la taille cible
    if len(frozen) > target_len:
        frozen = frozen[:target_len]
    elif len(frozen) < target_len:
        pad_shape = (target_len - len(frozen),) + frozen.shape[1:]
        frozen = np.concatenate(
            [frozen, np.zeros(pad_shape, dtype=np.float32)], axis=0
        )

    result[start:end] = frozen
    return result
