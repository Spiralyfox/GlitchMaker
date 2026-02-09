"""Progress overlay — shows animated progress during effect processing."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QFont
from utils.config import get_colors


class ProgressOverlay(QWidget):
    """Semi-transparent overlay with animated progress bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        C = get_colors()
        lo = QVBoxLayout(self)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel("Processing...")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            f"color: {C['text']}; font-size: 13px; font-weight: bold;"
            f" background: transparent;")
        lo.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setFixedSize(240, 8)
        self._bar.setRange(0, 0)  # indeterminate by default
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C['bg_dark']}; border: 1px solid {C['border']};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {C['accent']}; border-radius: 3px;
            }}
        """)
        lo.addWidget(self._bar, alignment=Qt.AlignmentFlag.AlignCenter)

        self._detail = QLabel("")
        self._detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
        lo.addWidget(self._detail)

        # Pulse timer for indeterminate animation
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(100)
        self._dots = 0
        self._pulse_timer.timeout.connect(self._pulse)

    def show_progress(self, text: str = "Processing...", detail: str = ""):
        """Show the overlay with given text."""
        self._label.setText(text)
        self._detail.setText(detail)
        self._bar.setRange(0, 0)  # indeterminate
        self._dots = 0
        self.setVisible(True)
        self._pulse_timer.start()
        self.raise_()

    def set_progress(self, value: int, maximum: int = 100):
        """Set determinate progress."""
        self._bar.setRange(0, maximum)
        self._bar.setValue(value)

    def hide_progress(self):
        """Hide the overlay."""
        self._pulse_timer.stop()
        self.setVisible(False)

    def _pulse(self):
        """Animate dots on the label."""
        self._dots = (self._dots + 1) % 4
        base = self._label.text().rstrip(".")
        if base.endswith(".."):
            base = base.rstrip(".")
        if not base.endswith("ing"):
            parts = base.split("...")
            base = parts[0]
        self._label.setText(base + "." * self._dots)

    def paintEvent(self, e):
        """Draw semi-transparent background."""
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 140))
        p.end()
        super().paintEvent(e)

    def resizeEvent(self, e):
        """Keep overlay the same size as parent."""
        if self.parent():
            self.setGeometry(self.parent().rect())
