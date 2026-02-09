"""Automation curve — draw parameter curves over the waveform timeline."""
import numpy as np
from PyQt6.QtWidgets import QWidget, QComboBox, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath, QFont, QCursor
from utils.config import get_colors


class AutomationLane(QWidget):
    """Drawable automation curve. Click to add points, drag to move them."""
    curve_changed = pyqtSignal()  # emitted when user modifies the curve

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        # Points as list of (frac_x: 0-1, frac_y: 0-1) — 0=bottom, 1=top
        self._points: list[tuple[float, float]] = [(0.0, 0.5), (1.0, 0.5)]
        self._param = "volume"
        self._enabled = False
        self._dragging_idx: int | None = None
        self._hover_idx: int | None = None

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, val):
        self._enabled = val
        self.setVisible(val)

    def set_param(self, param: str):
        """Set which parameter is being automated."""
        self._param = param
        self._points = [(0.0, 0.5), (1.0, 0.5)]
        self.update()

    def reset(self):
        """Clear automation to flat line."""
        self._points = [(0.0, 0.5), (1.0, 0.5)]
        self.curve_changed.emit()
        self.update()

    def get_envelope(self, num_samples: int) -> np.ndarray:
        """Generate an envelope array from the curve points.
        Returns values 0.0 to 1.0 for each sample.
        """
        if num_samples < 2 or len(self._points) < 2:
            return np.ones(num_samples, dtype=np.float64) * 0.5
        pts = sorted(self._points, key=lambda p: p[0])
        xs = np.array([p[0] for p in pts])
        ys = np.array([p[1] for p in pts])
        sample_xs = np.linspace(0, 1, num_samples)
        return np.interp(sample_xs, xs, ys)

    def _find_nearest(self, x_frac, y_frac, threshold=0.03):
        """Find point index near cursor, or -1."""
        for i, (px, py) in enumerate(self._points):
            if abs(px - x_frac) < threshold and abs(py - y_frac) < 0.15:
                return i
        return -1

    def mousePressEvent(self, e):
        if not self._enabled:
            return
        w, h = self.width(), self.height()
        xf = e.position().x() / w
        yf = 1.0 - e.position().y() / h  # invert Y
        xf = max(0.0, min(1.0, xf))
        yf = max(0.0, min(1.0, yf))

        if e.button() == Qt.MouseButton.RightButton:
            # Right-click: delete nearest point (if not endpoints)
            idx = self._find_nearest(xf, yf, 0.04)
            if idx > 0 and idx < len(self._points) - 1:
                self._points.pop(idx)
                self.curve_changed.emit()
                self.update()
            return

        idx = self._find_nearest(xf, yf, 0.03)
        if idx >= 0:
            self._dragging_idx = idx
        else:
            # Add new point
            self._points.append((xf, yf))
            self._points.sort(key=lambda p: p[0])
            self._dragging_idx = next(i for i, p in enumerate(self._points) if p == (xf, yf))
            self.curve_changed.emit()
        self.update()

    def mouseMoveEvent(self, e):
        if self._dragging_idx is not None:
            w, h = self.width(), self.height()
            xf = max(0.0, min(1.0, e.position().x() / w))
            yf = max(0.0, min(1.0, 1.0 - e.position().y() / h))
            # Don't allow moving first/last point's X
            if self._dragging_idx == 0:
                xf = 0.0
            elif self._dragging_idx == len(self._points) - 1:
                xf = 1.0
            self._points[self._dragging_idx] = (xf, yf)
            self.update()

    def mouseReleaseEvent(self, e):
        if self._dragging_idx is not None:
            self._dragging_idx = None
            self._points.sort(key=lambda p: p[0])
            self.curve_changed.emit()
            self.update()

    def paintEvent(self, e):
        C = get_colors()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(C['bg_dark']))

        if not self._enabled or len(self._points) < 2:
            p.setPen(QColor(C['text_dim']))
            p.setFont(QFont("Segoe UI", 8))
            p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, "Automation: Off")
            p.end(); return

        # Draw grid lines
        p.setPen(QPen(QColor(C['border']), 1, Qt.PenStyle.DotLine))
        for frac in [0.25, 0.5, 0.75]:
            y = int(h * (1.0 - frac))
            p.drawLine(0, y, w, y)

        # Draw curve
        pts = sorted(self._points, key=lambda pt: pt[0])
        path = QPainterPath()
        path.moveTo(pts[0][0] * w, (1.0 - pts[0][1]) * h)
        for px, py in pts[1:]:
            path.lineTo(px * w, (1.0 - py) * h)

        # Fill under curve
        fill_path = QPainterPath(path)
        fill_path.lineTo(w, h)
        fill_path.lineTo(0, h)
        fill_path.closeSubpath()
        fc = QColor(C['accent'])
        fc.setAlpha(30)
        p.fillPath(fill_path, fc)

        # Curve line
        p.setPen(QPen(QColor(C['accent']), 2))
        p.drawPath(path)

        # Points
        for i, (px, py) in enumerate(pts):
            x, y = int(px * w), int((1.0 - py) * h)
            is_dragging = (i == self._dragging_idx)
            r = 5 if is_dragging else 4
            p.setBrush(QColor("white") if is_dragging else QColor(C['accent']))
            p.setPen(QPen(QColor("white"), 1))
            p.drawEllipse(x - r, y - r, r * 2, r * 2)

        # Label
        p.setPen(QColor(C['text_dim']))
        p.setFont(QFont("Consolas", 7))
        p.drawText(4, 10, f"Auto: {self._param}")

        p.end()


class AutomationBar(QWidget):
    """Toolbar for automation controls: param selector + enable/reset."""
    param_changed = pyqtSignal(str)
    toggled = pyqtSignal(bool)
    reset_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 0, 8, 0)
        lo.setSpacing(4)

        C = get_colors()
        _ss = (f"background: {C['button_bg']}; color: {C['text']};"
               f" border: 1px solid {C['border']}; border-radius: 3px;"
               f" font-size: 9px; padding: 0 6px;")

        lbl = QLabel("AUTOMATION")
        lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px; font-weight: bold;")
        lo.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.addItems(["volume", "filter_cutoff", "pitch", "pan"])
        self.combo.setFixedHeight(20)
        self.combo.setStyleSheet(f"QComboBox {{ {_ss} }}")
        self.combo.currentTextChanged.connect(lambda t: self.param_changed.emit(t))
        lo.addWidget(self.combo)

        lo.addStretch()

        self.btn_toggle = QPushButton("Enable")
        self.btn_toggle.setFixedHeight(20)
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setStyleSheet(
            f"QPushButton {{ {_ss} }}"
            f"QPushButton:checked {{ background: {C['accent']}; color: white; }}")
        self.btn_toggle.clicked.connect(lambda c: self.toggled.emit(c))
        lo.addWidget(self.btn_toggle)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setFixedHeight(20)
        self.btn_reset.setStyleSheet(f"QPushButton {{ {_ss} }}"
                                     f"QPushButton:hover {{ background: {C['accent']}; color: white; }}")
        self.btn_reset.clicked.connect(self.reset_clicked.emit)
        lo.addWidget(self.btn_reset)

        self.setStyleSheet(f"background: {C['bg_medium']};")
