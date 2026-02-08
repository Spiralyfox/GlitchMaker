"""Wave Ondulée — pitch + volume sinusoidal modulation."""
import numpy as np
from core.effects.utils import apply_micro_fade


def wave_ondulee(audio_data, start, end, sr=44100,
                 speed=3.0, pitch_depth=0.4, vol_depth=0.3, stereo_offset=True):
    """Modulation de pitch par LFO sinusoidal."""
    result = audio_data.copy()
    seg = result[start:end].astype(np.float64)
    n = len(seg)
    if n < 2:
        return result
    is_stereo = seg.ndim == 2 and seg.shape[1] >= 2
    t = np.arange(n, dtype=np.float64) / sr
    wave = np.sin(2 * np.pi * speed * t)

    # Volume modulation
    vol_env = 1.0 - vol_depth * 0.5 * (1.0 + wave)
    if is_stereo and stereo_offset:
        wave_r = np.sin(2 * np.pi * speed * t + np.pi * 0.4)
        vol_env_r = 1.0 - vol_depth * 0.5 * (1.0 + wave_r)
        seg[:, 0] *= vol_env
        seg[:, 1] *= vol_env_r
    elif is_stereo:
        seg *= vol_env[:, np.newaxis]
    else:
        seg *= vol_env

    # Pitch modulation via variable-rate resampling
    if pitch_depth > 0.01:
        max_shift = pitch_depth * 0.15
        speed_mod = 1.0 + max_shift * np.sin(2 * np.pi * speed * 0.5 * t)
        read_idx = np.cumsum(speed_mod)
        read_idx = read_idx / read_idx[-1] * (n - 1)
        i0 = np.floor(read_idx).astype(int)
        i1 = np.minimum(i0 + 1, n - 1)
        frac = read_idx - i0
        if is_stereo:
            for ch in range(seg.shape[1]):
                seg[:, ch] = seg[i0, ch] * (1.0 - frac) + seg[i1, ch] * frac
        else:
            seg = seg[i0] * (1.0 - frac) + seg[i1] * frac

    result[start:end] = apply_micro_fade(seg.astype(np.float32), 64)
    return np.clip(result, -1.0, 1.0)
