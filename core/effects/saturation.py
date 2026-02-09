"""
Effet Saturation — Hard Clip, Soft Clip, Overdrive unifiés.
Distortion agressive (100 gecs) ou chaude (Charli XCX).

Refactored: une seule fonction saturate() avec paramètre mode.
Les anciennes fonctions hard_clip/soft_clip/overdrive sont conservées
comme aliases pour la rétrocompatibilité.
"""

import numpy as np
from utils.logger import get_logger

_log = get_logger("effect.saturation")


def saturate(audio_data: np.ndarray, start: int, end: int,
             mode: str = "soft", drive: float = 3.0,
             tone: float = 0.5, sr: int = 44100) -> np.ndarray:
    """Saturation unifiée avec 3 modes.

    Args:
        audio_data: Signal audio (mono ou stéréo).
        start: Échantillon de début.
        end: Échantillon de fin.
        mode: 'hard' (écrêtage brutal), 'soft' (tanh chaud),
              'overdrive' (gain + asymétrique + tone).
        drive: Intensité (0.5–20.0). Plus haut = plus saturé.
        tone: Brillance pour overdrive (0.0=sombre, 1.0=brillant).
        sr: Taux d'échantillonnage.

    Returns:
        Audio avec saturation appliquée, clippé à [-1, 1].
    """
    result = audio_data.copy()
    drive = max(0.5, min(20.0, drive))
    segment = result[start:end]

    if mode == "hard":
        threshold = max(0.05, 1.0 / drive)
        result[start:end] = np.clip(segment, -threshold, threshold) / threshold

    elif mode == "overdrive":
        seg = segment.copy() * drive
        # Asymmetric soft clip (more musical character)
        seg = np.where(seg >= 0, np.tanh(seg), np.tanh(seg * 0.8) * 1.2)
        # Tone control via simple moving average
        if tone < 0.5 and seg.ndim >= 1:
            kernel_size = int((1.0 - tone) * 8) + 1
            if seg.ndim == 1:
                seg = np.convolve(seg, np.ones(kernel_size) / kernel_size, mode='same')
            else:
                for ch in range(seg.shape[1]):
                    seg[:, ch] = np.convolve(
                        seg[:, ch], np.ones(kernel_size) / kernel_size, mode='same'
                    )
        result[start:end] = seg

    else:  # "soft" (default)
        result[start:end] = np.tanh(segment * drive)

    _log.debug("Saturation mode=%s drive=%.1f applied to %d samples", mode, drive, end - start)
    return np.clip(result, -1.0, 1.0)


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
