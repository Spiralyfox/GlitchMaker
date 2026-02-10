"""
Fonctions DSP utilitaires communes a tous les effets.
Micro-fades, normalisation, fade in/out, crossfade.
"""

import numpy as np


def apply_micro_fade(audio: np.ndarray, fade_samples: int = 64) -> np.ndarray:
    """Micro fade-in/out anti-clic aux jointures."""
    result = audio.copy()
    n = min(fade_samples, len(result) // 2)
    if n == 0:
        return result
    fade_in = np.linspace(0, 1, n, dtype=np.float32)
    fade_out = np.linspace(1, 0, n, dtype=np.float32)
    if result.ndim == 1:
        result[:n] *= fade_in
        result[-n:] *= fade_out
    else:
        for ch in range(result.shape[1]):
            result[:n, ch] *= fade_in
            result[-n:, ch] *= fade_out
    return result


def normalize(audio: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Normalise au pic donne."""
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio
    return audio * (target_peak / peak)


def _make_fade_curve(n: int, curve_type: str = "linear",
                     curvature: float = 0.0) -> np.ndarray:
    """Generate a 0→1 fade curve of n samples.
    curvature: -100..100 where 0=linear, >0=exponential(convex), <0=logarithmic(concave).
    curve_type is kept for legacy compat but curvature takes priority if non-zero.
    """
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    if curvature != 0.0:
        # Map curvature [-100..100] to exponent [0.1..10]
        # 0 → exponent 1 (linear), +100 → exponent ~4, -100 → exponent ~0.25
        exp = 2.0 ** (curvature / 33.33)
        return np.power(t, exp).astype(np.float32)
    if curve_type == "exponential":
        return t ** 3
    elif curve_type == "logarithmic":
        return (1.0 - (1.0 - t) ** 3).astype(np.float32)
    elif curve_type == "s_curve":
        return (3 * t ** 2 - 2 * t ** 3).astype(np.float32)
    return t


def fade_in(audio: np.ndarray, duration_samples: int,
            curve_type: str = "linear",
            start_level: float = 0.0, end_level: float = 1.0,
            curvature: float = 0.0) -> np.ndarray:
    """Fade-in configurable avec type de courbe et niveaux."""
    result = audio.copy()
    n = min(duration_samples, len(result))
    if n <= 0:
        return result
    curve = _make_fade_curve(n, curve_type, curvature)
    curve = start_level + curve * (end_level - start_level)
    if result.ndim == 1:
        result[:n] *= curve
    else:
        for ch in range(result.shape[1]):
            result[:n, ch] *= curve
    return result


def fade_out(audio: np.ndarray, duration_samples: int,
             curve_type: str = "linear",
             start_level: float = 1.0, end_level: float = 0.0,
             curvature: float = 0.0) -> np.ndarray:
    """Fade-out configurable avec type de courbe et niveaux."""
    result = audio.copy()
    n = min(duration_samples, len(result))
    if n <= 0:
        return result
    curve = _make_fade_curve(n, curve_type, curvature)
    curve = start_level + curve * (end_level - start_level)
    curve = curve[::-1].copy()
    if result.ndim == 1:
        result[-n:] *= curve
    else:
        for ch in range(result.shape[1]):
            result[-n:, ch] *= curve
    return result


def crossfade(audio_a: np.ndarray, audio_b: np.ndarray,
              overlap_samples: int) -> np.ndarray:
    """Fusionne deux segments avec un crossfade."""
    overlap = min(overlap_samples, len(audio_a), len(audio_b))
    if overlap <= 0:
        return np.concatenate([audio_a, audio_b], axis=0)
    fade_o = np.linspace(1.0, 0.0, overlap, dtype=np.float32)
    fade_i = np.linspace(0.0, 1.0, overlap, dtype=np.float32)
    part_a = audio_a[:-overlap].copy()
    mix_a = audio_a[-overlap:].copy()
    mix_b = audio_b[:overlap].copy()
    part_b = audio_b[overlap:].copy()
    if mix_a.ndim == 1:
        mixed = mix_a * fade_o + mix_b * fade_i
    else:
        mixed = np.zeros_like(mix_a)
        for ch in range(mix_a.shape[1]):
            mixed[:, ch] = mix_a[:, ch] * fade_o + mix_b[:, ch] * fade_i
    return np.concatenate([part_a, mixed, part_b], axis=0)


# ──────────────────────────────────────────────────
# Bezier envelope — advanced fade curve editor
# ──────────────────────────────────────────────────

def _bezier_y(y0: float, y1: float, bend: float, t: float) -> float:
    """Quadratic bezier Y at parameter *t* with control-point shifted by *bend*."""
    if abs(bend) < 0.005:
        return y0 + t * (y1 - y0)
    cy = (y0 + y1) / 2.0 + bend
    u = 1.0 - t
    return u * u * y0 + 2.0 * u * t * cy + t * t * y1


def eval_envelope(pts: list, bends: list, x: float) -> float:
    """Evaluate envelope value at normalised *x* in [0, 1]."""
    if not pts:
        return 0.0
    if len(pts) == 1:
        return pts[0][1]
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 <= x <= x1:
            dx = x1 - x0
            if dx < 1e-9:
                return y0
            t = (x - x0) / dx
            b = bends[i] if i < len(bends) else 0.0
            return _bezier_y(y0, y1, b, t)
    return pts[-1][1]


def make_envelope_curve(n: int, points: list, bends: list) -> np.ndarray:
    """Build an *n*-sample volume envelope from control points + bends."""
    pts = sorted(points, key=lambda p: p[0])
    if not bends:
        bends = [0.0] * max(0, len(pts) - 1)
    curve = np.empty(n, dtype=np.float32)
    for i in range(n):
        x = i / max(1, n - 1)
        curve[i] = eval_envelope(pts, bends, x)
    return np.clip(curve, 0.0, 1.0)


def apply_envelope_fade(audio: np.ndarray, duration_samples: int,
                        points: list, bends: list,
                        fade_type: str = "in") -> np.ndarray:
    """Apply a fade using an envelope defined by control points + bends."""
    result = audio.copy()
    n_total = len(result) if result.ndim == 1 else result.shape[0]
    n = min(duration_samples, n_total)
    if n <= 1:
        return result
    curve = make_envelope_curve(n, points, bends)
    if fade_type == "in":
        if result.ndim == 1:
            result[:n] *= curve
        else:
            result[:n] *= curve[:, np.newaxis]
    else:
        if result.ndim == 1:
            result[-n:] *= curve
        else:
            result[-n:] *= curve[:, np.newaxis]
    return result
