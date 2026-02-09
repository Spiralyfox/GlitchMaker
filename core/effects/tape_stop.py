"""
Tape Stop — Ralentissement progressif style arret de cassette.
Le son descend en pitch et ralentit jusqu'a l'arret complet.
"""

import numpy as np
from scipy.signal import resample


def tape_stop(audio_data: np.ndarray, start: int, end: int,
              duration_pct: float = 0.5, sr: int = 44100) -> np.ndarray:
    """Simule l'arret d'un lecteur cassette sur la zone."""
    result = audio_data.copy()
    segment = result[start:end].copy()
    if len(segment) == 0:
        return result

    seg_len = len(segment)
    # Duree de l'effet (portion du segment affecte)
    effect_len = max(256, int(seg_len * duration_pct))

    # Partie non affectee au debut
    clean_len = seg_len - effect_len
    if clean_len < 0:
        clean_len = 0
        effect_len = seg_len

    clean_part = segment[:clean_len].copy()
    effect_part = segment[clean_len:].copy()

    # Construire le ralentissement : vitesse 1.0 -> 0.0
    n_chunks = 64
    chunk_size = max(1, len(effect_part) // n_chunks)
    output_chunks = []

    for i in range(n_chunks):
        s = i * chunk_size
        e = min(s + chunk_size, len(effect_part))
        if s >= len(effect_part):
            break

        chunk = effect_part[s:e].copy()
        # Vitesse decroissante (1.0 -> 0.05)
        speed = max(0.05, 1.0 - (i / n_chunks) * 0.95)
        new_len = max(4, int(len(chunk) / speed))

        if chunk.ndim == 1:
            stretched = resample(chunk, new_len).astype(np.float32)
        else:
            cols = []
            for ch in range(chunk.shape[1]):
                cols.append(resample(chunk[:, ch], new_len))
            stretched = np.column_stack(cols).astype(np.float32)

        # Volume decroissant aussi
        volume = max(0.0, 1.0 - (i / n_chunks) * 0.8)
        stretched *= volume
        output_chunks.append(stretched)

    if output_chunks:
        effect_out = np.concatenate(output_chunks, axis=0)
    else:
        effect_out = effect_part

    # Ajuster a la taille du segment original
    combined = np.concatenate([clean_part, effect_out], axis=0)
    if len(combined) > seg_len:
        combined = combined[:seg_len]
    elif len(combined) < seg_len:
        pad_shape = (seg_len - len(combined),) + combined.shape[1:]
        combined = np.concatenate(
            [combined, np.zeros(pad_shape, dtype=np.float32)], axis=0
        )

    result[start:end] = combined
    return result
