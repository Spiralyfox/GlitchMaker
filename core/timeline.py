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

    @property
    def duration_samples(self) -> int:
        """Retourne la duree du clip en samples."""
        return len(self.audio_data) if self.audio_data is not None else 0

    @property
    def duration_seconds(self) -> float:
        """Retourne la duree du clip en secondes."""
        return self.duration_samples / self.sample_rate if self.sample_rate > 0 else 0.0

    @property
    def end_position(self) -> int:
        """Retourne la position de fin du clip (position + duree)."""
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
        self.clips.append(clip)
        self.sample_rate = sr
        return clip

    def render(self) -> tuple[np.ndarray, int]:
        """Render all clips into a single stereo float32 buffer."""
        if not self.clips:
            return np.zeros((0, 2), dtype=np.float32), self.sample_rate

        self.clips.sort(key=lambda c: c.position)

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
        """Retourne la duree totale en samples (fin du dernier clip)."""
        return max((c.end_position for c in self.clips), default=0)

    @property
    def total_duration_seconds(self) -> float:
        """Retourne la duree totale en secondes."""
        return self.total_duration_samples / self.sample_rate if self.sample_rate > 0 else 0.0
