"""Minimap — shows full waveform overview with visible region indicator."""
import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QImage
from utils.config import get_colors


class MinimapWidget(QWidget):
    """Miniature overview of the full waveform. Click or drag to scroll."""
    region_clicked = pyqtSignal(float)  # offset 0-1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setVisible(False)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._audio: np.ndarray | None = None
        self._sr = 44100
        self._zoom = 1.0
        self._offset = 0.0
        self._cache: QImage | None = None
        self._cache_w = 0
        self._dragging = False

    def set_audio(self, data, sr):
        self._audio = data
        self._sr = sr
        self._cache = None
        self.update()

    def set_view(self, zoom, offset):
        self._zoom = zoom
        self._offset = offset
        self.setVisible(zoom > 1.05)
        self.update()

    def _offset_from_x(self, x):
        """Calculate offset so the viewport is centered on x."""
        frac = x / max(self.width(), 1)
        visible = 1.0 / self._zoom
        return max(0.0, min(frac - visible / 2, 1.0 - visible))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            offset = self._offset_from_x(e.position().x())
            self.region_clicked.emit(offset)

    def mouseMoveEvent(self, e):
        if self._dragging:
            offset = self._offset_from_x(e.position().x())
            self.region_clicked.emit(offset)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paintEvent(self, ev):
        C = get_colors()
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(C['bg_medium']))

        if self._audio is not None and len(self._audio) > 0:
            # Draw mini waveform
            if self._cache is None or self._cache_w != w:
                self._cache = self._render(w, h)
                self._cache_w = w
            p.drawImage(0, 0, self._cache)

            # Draw visible region rectangle
            visible = 1.0 / self._zoom
            x1 = int(self._offset * w)
            x2 = int((self._offset + visible) * w)
            rc = QColor(C['accent'])
            rc.setAlpha(40)
            p.fillRect(x1, 0, x2 - x1, h, rc)
            p.setPen(QPen(QColor(C['accent']), 1))
            p.drawRect(x1, 0, x2 - x1 - 1, h - 1)

        # Border
        p.setPen(QPen(QColor(C['border']), 1))
        p.drawLine(0, h - 1, w, h - 1)
        p.end()

    def _render(self, w, h):
        C = get_colors()
        buf = np.zeros((h, w, 4), dtype=np.uint8)
        bg = QColor(C['bg_medium'])
        buf[:, :, 0] = bg.blue()
        buf[:, :, 1] = bg.green()
        buf[:, :, 2] = bg.red()
        buf[:, :, 3] = 255

        mono = np.mean(self._audio, axis=1) if self._audio.ndim > 1 else self._audio
        n = len(mono)
        step = max(1, n // w)
        cols = min(w, n // step)
        if cols <= 0:
            return QImage(buf.data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()

        usable = cols * step
        reshaped = mono[:usable].reshape(cols, step)
        mins = np.min(reshaped, axis=1)
        maxs = np.max(reshaped, axis=1)
        mid = h // 2
        yt = np.clip((mid - maxs * mid * 0.85).astype(int), 0, h - 1)
        yb = np.clip((mid - mins * mid * 0.85).astype(int), 0, h - 1)

        ac = QColor(C['accent'])
        r, g, b = ac.red(), ac.green(), ac.blue()
        rows = np.arange(h).reshape(h, 1)
        mask = (rows >= np.minimum(yt, yb)) & (rows <= np.maximum(yt, yb))
        buf[:, :cols, 0] = np.where(mask[:, :cols], b, buf[:, :cols, 0])
        buf[:, :cols, 1] = np.where(mask[:, :cols], g, buf[:, :cols, 1])
        buf[:, :cols, 2] = np.where(mask[:, :cols], r, buf[:, :cols, 2])

        return QImage(buf.data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()
