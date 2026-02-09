"""
Shuffle — Decoupe en tranches et les melange aleatoirement.
Style dariacore / mashcore : reorganisation rythmique chaotique.
"""

import numpy as np
from core.effects.utils import apply_micro_fade


def shuffle(audio_data: np.ndarray, start: int, end: int,
            slices: int = 8, mode: str = "random") -> np.ndarray:
    """Decoupe la zone en N tranches et les melange.
    Modes: random (ordre aleatoire), reverse (ordre inverse),
           interleave (1,3,5,7,2,4,6,8)."""
    result = audio_data.copy()
    segment = result[start:end].copy()
    if len(segment) == 0:
        return result

    seg_len = len(segment)
    slice_len = max(64, seg_len // slices)
    rng = np.random.default_rng()

    # Decouper en tranches
    chunks = []
    for i in range(slices):
        s = i * slice_len
        e = min(s + slice_len, seg_len)
        if s >= seg_len:
            break
        chunk = segment[s:e].copy()
        chunk = apply_micro_fade(chunk, fade_samples=min(16, len(chunk) // 4))
        chunks.append(chunk)

    if not chunks:
        return result

    # Reordonner
    if mode == "random":
        rng.shuffle(chunks)
    elif mode == "reverse":
        chunks.reverse()
    elif mode == "interleave":
        odds = chunks[0::2]
        evens = chunks[1::2]
        chunks = odds + evens

    # Recombiner
    output = np.concatenate(chunks, axis=0)

    # Ajuster a la taille originale
    target_len = end - start
    if len(output) > target_len:
        output = output[:target_len]
    elif len(output) < target_len:
        pad_shape = (target_len - len(output),) + output.shape[1:]
        output = np.concatenate(
            [output, np.zeros(pad_shape, dtype=np.float32)], axis=0
        )

    result[start:end] = output
    return result
