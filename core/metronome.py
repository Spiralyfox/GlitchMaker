"""Metronome — génère des clics de tempo mixés dans le callback audio."""
import numpy as np


def _make_click(sr, freq=1000.0, dur_ms=15.0, vol=0.5):
    """Génère un burst sinusoïdal avec décroissance exponentielle (un seul clic)."""
    n = int(sr * dur_ms / 1000.0)
    t = np.arange(n, dtype=np.float32) / sr
    return (np.sin(2 * np.pi * freq * t) * np.exp(-t * 300) * vol).astype(np.float32)


class Metronome:
    """Moteur de métronome — produit des clics synchronisés avec la position de lecture."""

    def __init__(self, sr=44100):
        """Initialise le métronome avec un sample rate, désactivé par défaut."""
        self.enabled = False
        self.bpm = 120.0
        self.volume = 0.5
        self.beats_per_bar = 4
        self.sr = sr
        self._rebuild()

    def _rebuild(self):
        """Reconstruit les buffers de clics (normal + accent) après changement de paramètres."""
        self._click = _make_click(self.sr, 1000.0, 15.0, self.volume)
        self._accent = _make_click(self.sr, 1500.0, 18.0, self.volume * 1.3)

    def set_bpm(self, bpm):
        """Change le tempo (20-300 BPM)."""
        self.bpm = max(20.0, min(300.0, bpm))

    def set_volume(self, v):
        """Change le volume des clics (0.0-1.0), reconstruit les buffers."""
        self.volume = max(0.0, min(1.0, v)); self._rebuild()

    def set_beats(self, n):
        """Change le nombre de temps par mesure (1-12)."""
        self.beats_per_bar = max(1, min(12, n))

    def set_sr(self, sr):
        """Met a jour le sample rate et reconstruit les clics si change."""
        if sr != self.sr: self.sr = sr; self._rebuild()

    def samples_per_beat(self):
        """Retourne le nombre de samples par temps au BPM actuel."""
        return int(self.sr * 60.0 / self.bpm) if self.bpm > 0 else 0

    def mix_into(self, outdata, position, frames):
        """Mixe les clics dans le buffer de sortie audio.
        Calcule quels beats tombent dans [position, position+frames]
        et ajoute les clics. Temps 1 = clic accentue (plus aigu, plus fort)."""
        if not self.enabled or self.bpm <= 0:
            return
        spb = self.samples_per_beat()
        if spb <= 0:
            return
        ch = outdata.shape[1] if outdata.ndim > 1 else 1
        max_cl = max(len(self._click), len(self._accent))

        # Queue d'un clic commence dans le buffer precedent
        bp = position % spb
        if 0 < bp < max_cl:
            bn = (position // spb) % self.beats_per_bar
            click = self._accent if bn == 0 else self._click
            if bp < len(click):
                tail = click[bp:]
                ml = min(len(tail), frames)
                for c in range(min(ch, 2)):
                    outdata[:ml, c] += tail[:ml]

        # Parcours des beats qui tombent dans ce buffer
        first = position if position % spb == 0 else ((position // spb) + 1) * spb
        beat = first
        while beat < position + frames:
            off = beat - position
            if off >= 0:
                bn = (beat // spb) % self.beats_per_bar
                click = self._accent if bn == 0 else self._click
                ml = min(len(click), frames - off)
                if ml > 0:
                    for c in range(min(ch, 2)):
                        outdata[off:off + ml, c] += click[:ml]
            beat += spb
