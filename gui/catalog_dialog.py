"""
Effect catalog — beginner-friendly descriptions from lang files.
All 28 effects sorted alphabetically.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QScrollArea,
    QWidget, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush
from utils.config import COLORS
from utils.translator import t

# (letter, color, cat_key) — sorted alphabetically by effect name
ENTRIES = sorted([
    ("\u266a", "#f72585",  "autotune"),
    ("B", "#533483",  "bitcrusher"),
    ("F", "#457b9d",  "buffer_freeze"),
    ("C", "#2a6478",  "chorus"),
    ("Z", "#9b2226",  "datamosh"),
    ("E", "#2a9d8f",  "delay"),
    ("W", "#b5179e",  "distortion"),
    ("L", "#264653",  "filter"),
    ("G", "#7b2d8e",  "granular"),
    ("\u26a1","#ff006e",  "hyper"),
    ("O", "#e76f51",  "ott"),
    ("\u229d", "#2563eb",  "pan"),
    ("A", "#6d597a",  "phaser"),
    ("P", "#16c79a",  "pitch_shift"),
    ("\u3030", "#0ea5e9",  "wave_ondulee"),
    ("R", "#0f3460",  "reverse"),
    ("M", "#6d597a",  "ring_mod"),
    ("\U0001f916","#4a00e0",  "robot"),
    ("D", "#ff6b35",  "saturation"),
    ("K", "#bb3e03",  "shuffle"),
    ("S", "#e94560",  "stutter"),
    ("\U0001f4fc","#6b705c",  "tape_glitch"),
    ("X", "#3d5a80",  "tape_stop"),
    ("T", "#c74b50",  "time_stretch"),
    ("~", "#e07c24",  "tremolo"),
    ("V", "#606c38",  "vinyl"),
    ("\u2702", "#7209b7",  "vocal_chop"),
    ("U", "#4cc9f0",  "volume"),
], key=lambda x: t(f"cat.{x[2]}.name"))


class _IconWidget(QWidget):
    def __init__(self, letter, color, parent=None):
        super().__init__(parent)
        self._l, self._c = letter, color
        self.setFixedSize(32, 32)

    def paintEvent(self, e):
        """Dessine l icone lettre avec la couleur du plugin."""
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(self._c))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(1, 1, 30, 30, 5, 5)
        p.setPen(QColor("white")); p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        p.drawText(1, 1, 30, 30, Qt.AlignmentFlag.AlignCenter, self._l); p.end()


class CatalogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("catalog.window_title"))
        self.setMinimumSize(520, 600)
        self.setStyleSheet(f"QDialog {{ background: {COLORS['bg_medium']}; }}")

        lo = QVBoxLayout(self); lo.setContentsMargins(16, 12, 16, 12)
        title = QLabel(t("catalog.title"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(title)

        sub = QLabel(t("catalog.subtitle"))
        sub.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        sub.setWordWrap(True)
        lo.addWidget(sub)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{ background: {COLORS['bg_dark']}; width: 6px; }}
            QScrollBar::handle:vertical {{ background: {COLORS['scrollbar']}; border-radius: 3px; }}
        """)

        content = QWidget()
        cl = QVBoxLayout(content); cl.setSpacing(6)

        for letter, color, key in ENTRIES:
            row = QHBoxLayout(); row.setSpacing(10)
            row.addWidget(_IconWidget(letter, color))

            tl = QVBoxLayout(); tl.setSpacing(2)
            name_lbl = QLabel(t(f"cat.{key}.name"))
            name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            name_lbl.setStyleSheet(f"color: {COLORS['text']};")
            tl.addWidget(name_lbl)

            short_lbl = QLabel(t(f"cat.{key}.short"))
            short_lbl.setStyleSheet(f"color: {COLORS['accent']}; font-size: 10px; font-weight: bold;")
            short_lbl.setWordWrap(True)
            tl.addWidget(short_lbl)

            detail_lbl = QLabel(t(f"cat.{key}.detail"))
            detail_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
            detail_lbl.setWordWrap(True)
            tl.addWidget(detail_lbl)

            row.addLayout(tl, stretch=1)
            w = QWidget(); w.setLayout(row)
            cl.addWidget(w)

        cl.addStretch()
        scroll.setWidget(content)
        lo.addWidget(scroll)

        btn = QPushButton("Close"); btn.setFixedHeight(32)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['accent']}; color: white;
                border: none; border-radius: 6px; font-weight: bold; }}
            QPushButton:hover {{ background: {COLORS['accent_hover']}; }}
        """)
        btn.clicked.connect(self.accept)
        lo.addWidget(btn)
