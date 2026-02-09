"""Distortion — waveshaping distortion with multiple algorithms."""
import numpy as np

def distortion(audio_data: np.ndarray, start: int, end: int,
               drive: float = 5.0, tone: float = 0.5,
               mode: str = "tube") -> np.ndarray:
    """Applique une distortion (fuzz, overdrive, crunch)."""
    out = audio_data.copy()
    seg = out[start:end].astype(np.float64) * drive
    if mode == "tube":
        seg = np.sign(seg) * (1.0 - np.exp(-np.abs(seg)))
    elif mode == "fuzz":
        seg = np.tanh(seg * 2.0) * np.sign(seg + 0.001)
    elif mode == "digital":
        seg = np.clip(seg, -1.0, 1.0)
        steps = max(2, int(16 / drive))
        seg = np.round(seg * steps) / steps
    elif mode == "scream":
        seg = np.tanh(seg * 3.0)
        seg = np.sign(seg) * np.power(np.abs(seg), 0.3)
    # Tone filter (simple 1-pole lowpass)
    if tone < 0.95:
        alpha = tone * 0.99
        for i in range(1, len(seg)):
            if seg.ndim == 2:
                seg[i] = alpha * seg[i-1] + (1 - alpha) * seg[i]
            else:
                seg[i] = alpha * seg[i-1] + (1 - alpha) * seg[i]
    out[start:end] = np.clip(seg, -1.0, 1.0).astype(np.float32)
    return out
