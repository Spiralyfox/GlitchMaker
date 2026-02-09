"""Frequency spectrum — real-time FFT display below waveform."""
import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont, QPen
from utils.config import get_colors


class SpectrumWidget(QWidget):
    """Mini frequency spectrum display, updated during playback."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._spectrum: np.ndarray | None = None
        self._sr = 44100
        self._num_bars = 48
        self._bar_values = np.zeros(self._num_bars)
        self._peak_values = np.zeros(self._num_bars)
        self._decay = 0.92

    def update_spectrum(self, audio_chunk: np.ndarray, sr: int = 44100):
        """Feed a new audio chunk to compute the FFT spectrum."""
        self._sr = sr
        if audio_chunk is None or len(audio_chunk) < 64:
            self._bar_values *= self._decay
            self.update()
            return
        mono = np.mean(audio_chunk, axis=1) if audio_chunk.ndim == 2 else audio_chunk
        # Windowed FFT
        n = min(2048, len(mono))
        windowed = mono[:n] * np.hanning(n)
        fft = np.abs(np.fft.rfft(windowed))
        fft = fft[:len(fft) // 2]  # first half only
        if len(fft) < self._num_bars:
            self._bar_values *= self._decay
            self.update()
            return
        # Log-spaced frequency bins
        log_bins = np.logspace(np.log10(1), np.log10(len(fft) - 1),
                               self._num_bars + 1).astype(int)
        new_bars = np.zeros(self._num_bars)
        for i in range(self._num_bars):
            s, e = log_bins[i], log_bins[i + 1]
            if s >= e:
                e = s + 1
            new_bars[i] = np.mean(fft[s:e]) if e <= len(fft) else 0
        # Normalize to 0-1
        mx = np.max(new_bars)
        if mx > 0.001:
            new_bars /= mx
        # Smooth with decay
        self._bar_values = np.maximum(new_bars, self._bar_values * self._decay)
        # Peak hold
        self._peak_values = np.maximum(new_bars, self._peak_values * 0.98)
        self.update()

    def clear(self):
        """Reset spectrum to zero."""
        self._bar_values = np.zeros(self._num_bars)
        self._peak_values = np.zeros(self._num_bars)
        self.update()

    def paintEvent(self, e):
        C = get_colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(C['bg_dark']))

        if self._bar_values is None:
            p.end(); return

        bar_w = max(2, (w - 4) / self._num_bars - 1)
        gap = 1

        for i in range(self._num_bars):
            val = self._bar_values[i]
            bar_h = int(val * (h - 6))
            x = int(2 + i * (bar_w + gap))
            y = h - 3 - bar_h
            if bar_h < 1:
                continue
            # Gradient from accent to green
            grad = QLinearGradient(x, h - 3, x, y)
            grad.setColorAt(0.0, QColor(C['accent']))
            grad.setColorAt(1.0, QColor("#00d4aa"))
            p.setBrush(grad)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(int(x), y, int(bar_w), bar_h, 1, 1)
            # Peak dot
            peak = self._peak_values[i]
            peak_y = h - 3 - int(peak * (h - 6))
            if peak_y < y - 2:
                p.setBrush(QColor(255, 255, 255, 180))
                p.drawRect(int(x), peak_y, int(bar_w), 1)

        # Frequency labels
        p.setPen(QColor(C['text_dim']))
        p.setFont(QFont("Consolas", 7))
        labels = [(0.05, "100"), (0.25, "500"), (0.5, "1k"), (0.75, "5k"), (0.95, "16k")]
        for frac, txt in labels:
            p.drawText(int(frac * w), 9, txt)

        p.end()
