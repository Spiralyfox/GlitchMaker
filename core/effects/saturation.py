"""
Effet Saturation — 3 modes avec des caractères sonores distincts.

- Soft : saturation douce à base d'arctangente, harmoniques paires, son chaud
- Hard : écrêtage dur avec pre-gain et DC offset asymétrique, son agressif
- Overdrive : saturation tube avec courbe asymétrique + filtre tone résonant
"""

import numpy as np
from utils.logger import get_logger

_log = get_logger("effect.saturation")


def saturate(audio_data: np.ndarray, start: int, end: int,
             mode: str = "soft", drive: float = 3.0,
             tone: float = 0.5, sr: int = 44100) -> np.ndarray:
    """Saturation unifiée avec 3 modes aux caractères sonores distincts.

    Args:
        audio_data: Signal audio (mono ou stéréo).
        start: Échantillon de début.
        end: Échantillon de fin.
        mode: 'soft' (chaud/doux), 'hard' (brutal/agressif),
              'overdrive' (tube/musical).
        drive: Intensité (0.5–20.0). Plus haut = plus saturé.
        tone: Brillance (0.0 = sombre, 1.0 = brillant). Actif sur les 3 modes.
        sr: Taux d'échantillonnage.

    Returns:
        Audio avec saturation appliquée, clippé à [-1, 1].
    """
    result = audio_data.copy()
    drive = max(0.5, min(20.0, drive))
    tone = max(0.0, min(1.0, tone))
    segment = result[start:end].copy().astype(np.float64)

    if mode == "hard":
        seg = _hard_mode(segment, drive)
    elif mode == "overdrive":
        seg = _overdrive_mode(segment, drive)
    else:
        seg = _soft_mode(segment, drive)

    # ── Tone filter (all modes) ──
    seg = _apply_tone(seg, tone, sr)

    # ── Output gain compensation ──
    peak = np.max(np.abs(seg))
    if peak > 1.0:
        seg /= peak * 1.02  # slight headroom

    result[start:end] = seg.astype(np.float32)
    _log.debug("Saturation mode=%s drive=%.1f tone=%.1f applied to %d samples",
               mode, drive, tone, end - start)
    return np.clip(result, -1.0, 1.0)


def _soft_mode(seg: np.ndarray, drive: float) -> np.ndarray:
    """Saturation douce — arctangente avec harmoniques paires.
    Son chaud, musical, légère compression. Idéal pour épaissir un son."""
    gained = seg * drive
    # Arctangent produces mostly odd harmonics; we add even harmonics
    # via subtle asymmetry for warmth
    sat = np.arctan(gained) * (2 / np.pi)  # normalize to [-1, 1]
    # Add even harmonics via half-wave rectification blend
    even_harm = np.arctan(gained + 0.3 * np.abs(gained)) * (2 / np.pi)
    result = sat * 0.7 + even_harm * 0.3
    return result


def _hard_mode(seg: np.ndarray, drive: float) -> np.ndarray:
    """Écrêtage dur — tranchant et agressif avec distorsion asymétrique.
    Peaks tranchés net, beaucoup d'harmoniques impaires, son abrasif."""
    gained = seg * drive
    # Hard clip with asymmetric thresholds for more character
    pos_thresh = max(0.08, 1.0 / (drive * 0.8))
    neg_thresh = max(0.08, 1.0 / (drive * 1.2))  # asymmetric for odd+even harmonics
    clipped = np.where(gained >= 0,
                       np.minimum(gained, pos_thresh),
                       np.maximum(gained, -neg_thresh))
    # Normalize
    max_val = max(pos_thresh, neg_thresh)
    result = clipped / max_val if max_val > 0 else clipped
    # Add subtle fold-back distortion for more edge
    excess = np.maximum(np.abs(gained) - max_val, 0.0)
    foldback = np.sin(excess * np.pi * 2) * 0.15
    result = result + foldback * np.sign(gained)
    return result


def _overdrive_mode(seg: np.ndarray, drive: float) -> np.ndarray:
    """Saturation tube — courbe asymétrique chaude avec compression naturelle.
    Émule l'étage de gain d'un ampli à tubes. Son gras et musical."""
    gained = seg * drive
    # Tube-style asymmetric waveshaping:
    # Positive half: soft knee compression (triode-like)
    # Negative half: harder clipping (push-pull asymmetry)
    pos = gained * (gained >= 0)
    neg = gained * (gained < 0)
    # Positive: polynomial soft clip (warm, compressive)
    pos_sat = np.where(pos <= 1.0 / 3,
                       2.0 * pos,
                       np.where(pos <= 2.0 / 3,
                                (3.0 - (2.0 - 3.0 * pos) ** 2) / 3.0,
                                1.0))
    # Negative: tanh for slightly harder character
    neg_sat = np.tanh(neg * 1.5) / np.tanh(1.5)
    result = pos_sat + neg_sat
    # Add subtle 2nd harmonic (tube warmth)
    result = result + 0.1 * result ** 2
    return result


def _apply_tone(seg: np.ndarray, tone: float, sr: int) -> np.ndarray:
    """Filtre tone 1-pole : tone < 0.5 = coupe les aigus, tone > 0.5 = boost les aigus."""
    if abs(tone - 0.5) < 0.02:
        return seg  # neutral

    if tone < 0.5:
        # Low-pass: darker tone
        alpha = 0.05 + (1.0 - 2 * tone) * 0.4  # higher alpha = more LP
        return _one_pole_lp(seg, alpha)
    else:
        # High-shelf boost: brighter tone
        # Apply LP then subtract to get HP, blend with original
        alpha = 0.1 + (2 * (tone - 0.5)) * 0.3
        lp = _one_pole_lp(seg, alpha)
        hp = seg - lp
        boost = 1.0 + (tone - 0.5) * 3.0  # up to 2.5x HP boost
        return seg + hp * (boost - 1.0)


def _one_pole_lp(seg: np.ndarray, alpha: float) -> np.ndarray:
    """Filtre passe-bas 1-pole simple. alpha ∈ [0,1] : 0 = pas de filtre, 1 = très filtré."""
    a = max(0.01, min(0.99, alpha))
    result = seg.copy()
    if result.ndim == 1:
        for i in range(1, len(result)):
            result[i] = result[i - 1] * a + result[i] * (1 - a)
    else:
        for ch in range(result.shape[1]):
            for i in range(1, len(result)):
                result[i, ch] = result[i - 1, ch] * a + result[i, ch] * (1 - a)
    return result


# ── Rétrocompatibilité ──

def hard_clip(audio_data, start, end, threshold=0.5, **kw):
    """Alias rétrocompat → saturate(mode='hard')."""
    drive = max(0.5, 1.0 / max(0.05, threshold))
    return saturate(audio_data, start, end, mode="hard", drive=drive)


def soft_clip(audio_data, start, end, drive=3.0, **kw):
    """Alias rétrocompat → saturate(mode='soft')."""
    return saturate(audio_data, start, end, mode="soft", drive=drive)


def overdrive(audio_data, start, end, gain=5.0, tone=0.5, **kw):
    """Alias rétrocompat → saturate(mode='overdrive')."""
    return saturate(audio_data, start, end, mode="overdrive", drive=gain, tone=tone)
