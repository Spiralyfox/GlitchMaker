"""
Datamosh Audio — Corruption de donnees audio.
Traite l'audio comme des donnees brutes et les corrompt.
Equivalent audio du datamoshing video.
"""

import numpy as np


def datamosh(audio_data: np.ndarray, start: int, end: int,
             intensity: float = 0.5, block_size: int = 512,
             mode: str = "swap") -> np.ndarray:
    """Corrompt l'audio en manipulant les données brutes.
    Modes: swap (echange de blocs), repeat (repete des blocs),
           zero (met des blocs a zero), noise (injecte du bruit)."""
    result = audio_data.copy()
    segment = result[start:end].copy()
    if len(segment) == 0:
        return result

    rng = np.random.default_rng()
    seg_len = len(segment)
    n_blocks = max(1, seg_len // block_size)
    n_affected = max(1, int(n_blocks * intensity))

    if mode == "swap":
        # Echange des blocs aleatoirement
        for _ in range(n_affected):
            i = rng.integers(0, n_blocks)
            j = rng.integers(0, n_blocks)
            s1, e1 = i * block_size, min((i + 1) * block_size, seg_len)
            s2, e2 = j * block_size, min((j + 1) * block_size, seg_len)
            block_len = min(e1 - s1, e2 - s2)
            tmp = segment[s1:s1 + block_len].copy()
            segment[s1:s1 + block_len] = segment[s2:s2 + block_len]
            segment[s2:s2 + block_len] = tmp

    elif mode == "repeat":
        # Repete un bloc source sur d'autres positions
        src_idx = rng.integers(0, n_blocks)
        src_s = src_idx * block_size
        src_e = min(src_s + block_size, seg_len)
        src_block = segment[src_s:src_e].copy()

        for _ in range(n_affected):
            dst_idx = rng.integers(0, n_blocks)
            dst_s = dst_idx * block_size
            dst_e = min(dst_s + len(src_block), seg_len)
            block_len = dst_e - dst_s
            segment[dst_s:dst_e] = src_block[:block_len]

    elif mode == "zero":
        # Met des blocs a zero (silences brusques)
        for _ in range(n_affected):
            idx = rng.integers(0, n_blocks)
            s = idx * block_size
            e = min(s + block_size, seg_len)
            segment[s:e] = 0

    elif mode == "noise":
        # Injecte du bruit dans des blocs
        for _ in range(n_affected):
            idx = rng.integers(0, n_blocks)
            s = idx * block_size
            e = min(s + block_size, seg_len)
            shape = segment[s:e].shape
            segment[s:e] = rng.uniform(-0.5, 0.5, size=shape).astype(np.float32)

    result[start:end] = np.clip(segment, -1.0, 1.0)
    return result
