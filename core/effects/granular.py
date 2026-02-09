"""
Granular Glitch — Decoupe en micro-grains et rearrange aleatoirement.
Textures impredictibles, signature dariacore / experimental.
"""

import numpy as np
from core.effects.utils import apply_micro_fade


def granular(audio_data: np.ndarray, start: int, end: int,
             grain_size_ms: float = 50.0, density: float = 1.0,
             randomize: float = 0.5, sr: int = 44100) -> np.ndarray:
    """Decoupe la zone en grains et les repositionne aleatoirement."""
    result = audio_data.copy()
    segment = result[start:end].copy()
    if len(segment) == 0:
        return result

    # Taille du grain en samples
    grain_samples = max(64, int(grain_size_ms * sr / 1000.0))
    n_grains = max(1, len(segment) // grain_samples)

    # Extraire les grains
    grains = []
    for i in range(n_grains):
        s = i * grain_samples
        e = min(s + grain_samples, len(segment))
        g = segment[s:e].copy()
        g = apply_micro_fade(g, fade_samples=min(32, len(g) // 4))
        grains.append(g)

    if not grains:
        return result

    # Reorganiser selon le niveau de randomisation
    rng = np.random.default_rng()
    indices = np.arange(len(grains))

    if randomize > 0:
        # Melange partiel : plus randomize est haut, plus c'est chaotique
        n_swaps = int(len(grains) * randomize)
        for _ in range(n_swaps):
            i, j = rng.integers(0, len(grains), size=2)
            indices[i], indices[j] = indices[j], indices[i]

    # Reconstruire avec densite (repetition de grains)
    output_grains = []
    for idx in indices:
        output_grains.append(grains[idx])
        # Densite > 1 = repete certains grains
        if density > 1.0 and rng.random() < (density - 1.0):
            output_grains.append(grains[idx])

    output = np.concatenate(output_grains, axis=0)

    # Ajuster a la taille originale (couper ou padder)
    target_len = end - start
    if len(output) > target_len:
        output = output[:target_len]
    elif len(output) < target_len:
        pad = np.zeros((target_len - len(output),) + output.shape[1:],
                        dtype=np.float32)
        output = np.concatenate([output, pad], axis=0)

    result[start:end] = output
    return result
