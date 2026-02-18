"""
Digital Noise — bit reduction + digital artifacts.
Réduit la résolution en bits et ajoute du bruit numérique pour créer
des textures digitales, lo-fi et cassées.
"""
import numpy as np
from core.effects.utils import apply_micro_fade


def digital_noise(audio_data, start, end, sr=44100,
                  bit_reduction=0.5, noise_amount=0.3, sample_hold=1):
    """
    Digital noise / bit-crushing effect.

    Args:
        bit_reduction: intensity of bit-depth reduction (0.0–1.0).
            0 = full resolution (256 levels), 1 = extreme (4 levels).
        noise_amount: amplitude of added digital noise artifacts (0.0–1.0).
        sample_hold: sample-and-hold factor (1 = off, higher = more steppy/aliased).
    """
    result = audio_data.copy()
    seg = result[start:end].copy().astype(np.float64)
    n = len(seg)
    if n < 2:
        return result

    is_stereo = seg.ndim == 2
    dry = seg.copy()

    # ── 1. Bit-depth reduction ──
    if bit_reduction > 0.01:
        # Map 0..1 to 256..4 quantization levels
        levels = max(4, int(256 * (1.0 - bit_reduction * 0.95)))
        seg = np.round(seg * levels) / levels

    # ── 2. Sample-and-hold (aliasing effect) ──
    if sample_hold > 1:
        sh = int(max(2, min(64, sample_hold)))
        if is_stereo:
            for ch in range(seg.shape[1]):
                for i in range(0, n - sh, sh):
                    seg[i:i + sh, ch] = seg[i, ch]
        else:
            for i in range(0, n - sh, sh):
                seg[i:i + sh] = seg[i]

    # ── 3. Digital noise injection ──
    if noise_amount > 0.01:
        noise_amp = noise_amount * 0.08
        if is_stereo:
            noise = np.random.uniform(-noise_amp, noise_amp, seg.shape)
        else:
            noise = np.random.uniform(-noise_amp, noise_amp, n)
        seg = seg + noise

    result[start:end] = apply_micro_fade(seg.astype(np.float32), 64)
    return np.clip(result, -1.0, 1.0)
