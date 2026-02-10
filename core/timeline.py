"""
Timeline model — manages AudioClip instances in sequence.
Auto-assigns visually distinct colors to new clips.
"""

import uuid
import colorsys
import numpy as np
from dataclasses import dataclass, field


# ── Distinct color generator ──
# Uses golden-angle hue rotation for maximum visual separation

_GOLDEN_ANGLE = 137.508  # degrees

def _generate_distinct_color(index: int) -> str:
    """Generate a visually distinct color for clip index using golden-angle hue rotation."""
    hue = (index * _GOLDEN_ANGLE) % 360 / 360.0
    # High saturation + medium-high lightness for dark backgrounds
    sat = 0.65 + (index % 3) * 0.1   # 0.65-0.85
    lit = 0.50 + (index % 2) * 0.08  # 0.50-0.58
    r, g, b = colorsys.hls_to_rgb(hue, lit, sat)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


@dataclass
class AudioClip:
    """A single audio clip in the timeline."""
    name: str
    audio_data: np.ndarray
    sample_rate: int = 44100
    position: int = 0       # sample offset in timeline
    color: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    # Fade parameters (stored so we can re-edit without stacking)
    fade_in_params: dict = field(default_factory=dict)
    fade_out_params: dict = field(default_factory=dict)
    # Original audio before fade was applied (for undo/redo of fade)
    _audio_before_fade_in: np.ndarray | None = field(default=None, repr=False)
    _audio_before_fade_out: np.ndarray | None = field(default=None, repr=False)

    @property
    def duration_samples(self) -> int:
        """Retourne la durée du clip en samples."""
        return len(self.audio_data) if self.audio_data is not None else 0

    @property
    def duration_seconds(self) -> float:
        """Retourne la durée du clip en secondes."""
        return self.duration_samples / self.sample_rate if self.sample_rate > 0 else 0.0

    @property
    def end_position(self) -> int:
        """Retourne la position de fin du clip (position + durée)."""
        return self.position + self.duration_samples


class Timeline:
    """Ordered list of audio clips. Renders to a single stereo buffer."""

    def __init__(self):
        """Initialise la timeline vide."""
        self.clips: list[AudioClip] = []
        self.sample_rate: int = 44100
        self._color_counter: int = 0

    def clear(self):
        """Supprime tous les clips de la timeline."""
        self.clips.clear()

    def remove_clip(self, clip_or_idx):
        """Remove a clip then close gaps."""
        if isinstance(clip_or_idx, int):
            if 0 <= clip_or_idx < len(self.clips):
                self.clips.pop(clip_or_idx)
        elif clip_or_idx in self.clips:
            self.clips.remove(clip_or_idx)
        self.reposition_clips()

    def reposition_clips(self):
        """Place clips end-to-end in current order, closing all gaps."""
        self.clips.sort(key=lambda c: c.position)
        pos = 0
        for c in self.clips:
            c.position = pos
            pos += c.duration_samples

    def add_clip(self, audio_data: np.ndarray, sr: int,
                 name: str = "Clip", position: int | None = None,
                 color: str = "", copy: bool = True):
        """Add a clip. If position is None, append after last clip.
        If color is empty, auto-assigns a distinct color."""
        if position is None:
            position = max((c.end_position for c in self.clips), default=0)

        if not color:
            # Auto-assign distinct color
            color = _generate_distinct_color(self._color_counter)
            self._color_counter += 1

        clip = AudioClip(
            name=name, audio_data=audio_data.copy() if copy else audio_data,
            sample_rate=sr, position=position, color=color
        )
        is_first = len(self.clips) == 0
        self.clips.append(clip)
        if is_first:
            self.sample_rate = sr
        return clip

    def render(self) -> tuple[np.ndarray, int]:
        """Render all clips into a single stereo float32 buffer.
        Resamples any clip whose sample_rate differs from the timeline's."""
        if not self.clips:
            return np.zeros((0, 2), dtype=np.float32), self.sample_rate

        self.clips.sort(key=lambda c: c.position)

        # Resample clips that don't match the target sample rate
        from scipy.signal import resample as scipy_resample
        for clip in self.clips:
            if clip.sample_rate != self.sample_rate and clip.sample_rate > 0 and self.sample_rate > 0:
                new_len = int(len(clip.audio_data) * self.sample_rate / clip.sample_rate)
                if new_len > 0 and new_len != len(clip.audio_data):
                    d = clip.audio_data
                    if d.ndim == 1:
                        clip.audio_data = scipy_resample(d, new_len).astype(np.float32)
                    else:
                        channels = [scipy_resample(d[:, ch], new_len).astype(np.float32)
                                    for ch in range(d.shape[1])]
                        clip.audio_data = np.column_stack(channels)
                clip.sample_rate = self.sample_rate

        # Recalculate positions after potential resample
        self.reposition_clips()

        total = max(c.end_position for c in self.clips)
        out = np.zeros((total, 2), dtype=np.float32)

        for clip in self.clips:
            d = clip.audio_data
            if d is None or len(d) == 0:
                continue
            if d.ndim == 1:
                d = np.column_stack([d, d])
            elif d.shape[1] == 1:
                d = np.column_stack([d[:, 0], d[:, 0]])
            else:
                d = d[:, :2]

            s = clip.position
            e = min(s + len(d), total)
            n = e - s
            out[s:e] += d[:n].astype(np.float32)

        return out, self.sample_rate

    @property
    def total_duration_samples(self) -> int:
        """Retourne la durée totale en samples (fin du dernier clip)."""
        return max((c.end_position for c in self.clips), default=0)

    @property
    def total_duration_seconds(self) -> float:
        """Retourne la durée totale en secondes."""
        return self.total_duration_samples / self.sample_rate if self.sample_rate > 0 else 0.0
