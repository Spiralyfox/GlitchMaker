"""
Robotic — Granular robotic voice effect.
Creates a metallic, granular sound via micro-grain resynthesis + ring modulation.
"""
import numpy as np
from core.effects.utils import apply_micro_fade


def robot(audio_data, start, end, sr=44100,
          grain_ms=8, robot_amount=0.7, metallic=0.4,
          monotone=0.0, pitch_hz=150):
    """
    Robotic voice processing.
    grain_ms: grain size (smaller = more robotic, 3–30 ms)
    robot_amount: overall effect intensity
    metallic: ring modulation amount (metallic resonance)
    monotone: 0.0 = keep pitch variation, 1.0 = flatten to fixed pitch
    pitch_hz: fixed pitch when monotone > 0
    """
    result = audio_data.copy()
    seg = result[start:end].copy().astype(np.float64)
    n = len(seg)
    if n < 64:
        return result
    is_stereo = seg.ndim == 2

    dry = seg.copy()

    # ── 1. Micro-grain resynthesis (creates robotic texture) ──
    grain_size = max(16, int(grain_ms / 1000 * sr))
    grain_size = min(grain_size, n)
    hop = grain_size // 2
    window = np.hanning(grain_size).astype(np.float64)
    output = np.zeros_like(seg)
    weight = np.zeros(n, dtype=np.float64)

    for i in range(0, n - grain_size, hop):
        if is_stereo:
            grain = seg[i:i + grain_size].copy()
            for ch in range(grain.shape[1]):
                grain[:, ch] *= window
            output[i:i + grain_size] += grain
        else:
            grain = seg[i:i + grain_size] * window
            output[i:i + grain_size] += grain
        weight[i:i + grain_size] += window

    # Normalize overlap-add
    if is_stereo:
        w = np.maximum(weight, 1e-8)[:, np.newaxis]
        seg = output / w
    else:
        seg = output / np.maximum(weight, 1e-8)

    # ── 2. Monotone pitch flattening ──
    if monotone > 0.1:
        t = np.arange(n, dtype=np.float64) / sr
        carrier = np.sin(2 * np.pi * pitch_hz * t)
        # Extract envelope
        if is_stereo:
            for ch in range(seg.shape[1]):
                env = np.abs(seg[:, ch])
                # Smooth envelope
                kernel_size = max(1, int(sr * 0.005))
                if kernel_size > 1:
                    kernel = np.ones(kernel_size) / kernel_size
                    env = np.convolve(env, kernel, mode='same')
                mono_signal = env * carrier
                seg[:, ch] = seg[:, ch] * (1.0 - monotone) + mono_signal * monotone
        else:
            env = np.abs(seg)
            kernel_size = max(1, int(sr * 0.005))
            if kernel_size > 1:
                kernel = np.ones(kernel_size) / kernel_size
                env = np.convolve(env, kernel, mode='same')
            mono_signal = env * carrier
            seg = seg * (1.0 - monotone) + mono_signal * monotone

    # ── 3. Metallic ring modulation ──
    if metallic > 0.01:
        t = np.arange(n, dtype=np.float64) / sr
        # Use multiple harmonically related frequencies
        ring = (0.5 * np.sin(2 * np.pi * 180 * t) +
                0.3 * np.sin(2 * np.pi * 320 * t) +
                0.2 * np.sin(2 * np.pi * 520 * t))
        if is_stereo:
            ring2d = ring[:, np.newaxis]
            seg = seg * (1.0 - metallic) + seg * ring2d * metallic
        else:
            seg = seg * (1.0 - metallic) + seg * ring * metallic

    # ── Mix dry/wet ──
    amount = np.clip(robot_amount, 0.0, 1.0)
    seg = dry * (1.0 - amount) + seg * amount

    result[start:end] = apply_micro_fade(seg.astype(np.float32), 128)
    return np.clip(result, -1.0, 1.0)
