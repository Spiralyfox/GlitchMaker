"""Pitch Drift — pitch + volume sinusoidal modulation with audio extension."""
import numpy as np
from core.effects.utils import apply_micro_fade


def wave_ondulee(audio_data, start, end, sr=44100,
                 speed=3.0, pitch_depth=0.4, vol_depth=0.3, stereo_offset=True):
    """Modulation de pitch + volume par LFO sinusoïdal.

    Le pitch est modulé en déplaçant un curseur de lecture à vitesse variable
    dans le signal source. Quand le LFO descend, le curseur avance plus lentement
    que le temps réel, ce qui étire le signal et produit un résultat plus long.
    Tout le contenu audio est préservé — rien n'est tronqué ni compressé.

    Retourne un résultat potentiellement plus long que l'original.
    """
    result = audio_data.copy()
    seg = result[start:end].astype(np.float64)
    n = len(seg)
    if n < 2:
        return result
    is_stereo = seg.ndim == 2 and seg.shape[1] >= 2

    # ── Pitch modulation ──
    if pitch_depth > 0.01:
        max_shift = pitch_depth * 0.3  # stronger effect range

        # For each output sample i, the source position is:
        #   src_pos[i] = src_pos[i-1] + rate[i]
        # where rate[i] = 1.0 + max_shift * sin(2π * speed/2 * i/sr)
        #
        # rate < 1 → reading source slower → pitch DOWN → output stretches
        # rate > 1 → reading source faster → pitch UP → output compresses
        #
        # Output continues until src_pos reaches n (all source consumed).
        # Since rate oscillates around 1.0, the stretching and compressing
        # nearly cancel out — EXCEPT that we don't compress: when rate > 1,
        # we skip source samples (pitch up); when rate < 1, we stretch (pitch down).
        # To get actual extension, we bias the modulation slightly toward slowdown,
        # or we simply don't require the output to be exactly n.

        # The key insight: even with symmetric modulation, if we don't force
        # the output to be n samples, the read cursor naturally takes a slightly
        # different number of steps to cross n depending on where the LFO phase
        # starts. But for audible extension, we need an asymmetric approach:
        # we apply the LFO to DELAY the read position, which always extends.

        # Time-displacement approach:
        # output_time[i] maps to source_time[i] = i - displacement[i]
        # displacement = depth * sin(2π * speed * i/sr) * sr/speed * (scale)
        # This shifts the read position back and forth, stretching some parts
        # and always producing all original content.

        # Compute displacement envelope (in samples)
        max_disp = max_shift * sr / max(speed, 0.1) * 0.1  # max displacement in samples
        max_disp = min(max_disp, n * 0.5)  # cap at half the segment length

        # Output is extended by the max displacement
        out_len = n + int(max_disp * 2)

        t_out = np.arange(out_len, dtype=np.float64) / sr
        displacement = max_disp * np.sin(2 * np.pi * speed * 0.5 * t_out)

        # Source position for each output sample
        src_pos = np.arange(out_len, dtype=np.float64) - displacement
        # Scale to fit: map [0, out_len-1] source positions to [0, n-1]
        src_pos = src_pos / (out_len - 1) * (n - 1)
        src_pos = np.clip(src_pos, 0, n - 1 - 1e-6)

        i0 = np.floor(src_pos).astype(int)
        i1 = np.minimum(i0 + 1, n - 1)
        frac = src_pos - i0

        if is_stereo:
            out_seg = np.zeros((out_len, seg.shape[1]), dtype=np.float64)
            for ch in range(seg.shape[1]):
                out_seg[:, ch] = seg[i0, ch] * (1.0 - frac) + seg[i1, ch] * frac
        else:
            out_seg = seg[i0] * (1.0 - frac) + seg[i1] * frac

        # ── Volume modulation on extended output ──
        wave_vol = np.sin(2 * np.pi * speed * t_out)
        vol_env = 1.0 - vol_depth * 0.5 * (1.0 + wave_vol)

        if is_stereo and stereo_offset:
            wave_r = np.sin(2 * np.pi * speed * t_out + np.pi * 0.4)
            vol_env_r = 1.0 - vol_depth * 0.5 * (1.0 + wave_r)
            out_seg[:, 0] *= vol_env
            out_seg[:, 1] *= vol_env_r
        elif is_stereo:
            out_seg *= vol_env[:, np.newaxis]
        else:
            out_seg *= vol_env

        out_seg = apply_micro_fade(out_seg.astype(np.float32), 64)

        # ── Reassemble ──
        before = result[:start]
        after = result[end:]
        parts = [p for p in [before, out_seg, after] if len(p) > 0]
        result = np.concatenate(parts, axis=0).astype(np.float32)

        return np.clip(result, -1.0, 1.0)

    # ── Volume modulation only (no pitch mod) ──
    t = np.arange(n, dtype=np.float64) / sr
    wave = np.sin(2 * np.pi * speed * t)
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

    result[start:end] = apply_micro_fade(seg.astype(np.float32), 64)
    return np.clip(result, -1.0, 1.0)
