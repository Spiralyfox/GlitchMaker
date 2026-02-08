"""
Settings dialog — audio devices + language selection (separate).
"""

import sounddevice as sd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from utils.config import COLORS
from utils.translator import t, get_language

_SS = f"""
    QDialog {{ background: {COLORS['bg_medium']}; }}
    QLabel {{ color: {COLORS['text']}; font-size: 12px; }}
    QComboBox {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
        border: 1px solid {COLORS['border']}; border-radius: 4px;
        padding: 5px 8px; font-size: 11px; min-height: 26px; }}
    QComboBox QAbstractItemView {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
        selection-background-color: {COLORS['accent']}; }}
    QGroupBox {{ color: {COLORS['accent']}; font-size: 12px; font-weight: bold;
        border: 1px solid {COLORS['border']}; border-radius: 6px;
        margin-top: 8px; padding-top: 14px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}
"""


class SettingsDialog(QDialog):
    def __init__(self, current_output=None, current_input=None, parent=None):
        """Dialogue de parametres audio (entree/sortie/taux)."""
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(460, 400)
        self.setStyleSheet(_SS)
        self.selected_output = current_output
        self.selected_input = current_input
        self.selected_language = get_language()

        lo = QVBoxLayout(self); lo.setSpacing(10); lo.setContentsMargins(20, 16, 20, 16)

        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(title)

        # ── Audio section ──
        audio_grp = QGroupBox("Audio Devices")
        alo = QVBoxLayout(audio_grp); alo.setSpacing(6)

        devices = sd.query_devices()
        default_out = sd.default.device[1]  # default output index
        default_in = sd.default.device[0]   # default input index
        out_devs = [(i, d['name']) for i, d in enumerate(devices) if d['max_output_channels'] > 0]
        in_devs = [(i, d['name']) for i, d in enumerate(devices) if d['max_input_channels'] > 0]

        alo.addWidget(QLabel("Output"))
        self.combo_out = QComboBox()
        for idx, name in out_devs:
            suffix = " ★" if idx == default_out else ""
            self.combo_out.addItem(f"{name}{suffix}", idx)
            # Select current or system default
            if current_output is not None:
                if current_output == idx:
                    self.combo_out.setCurrentIndex(self.combo_out.count() - 1)
            elif idx == default_out:
                self.combo_out.setCurrentIndex(self.combo_out.count() - 1)
        alo.addWidget(self.combo_out)

        alo.addWidget(QLabel("Input"))
        self.combo_in = QComboBox()
        for idx, name in in_devs:
            suffix = " ★" if idx == default_in else ""
            self.combo_in.addItem(f"{name}{suffix}", idx)
            if current_input is not None:
                if current_input == idx:
                    self.combo_in.setCurrentIndex(self.combo_in.count() - 1)
            elif idx == default_in:
                self.combo_in.setCurrentIndex(self.combo_in.count() - 1)
        alo.addWidget(self.combo_in)

        lo.addWidget(audio_grp)

        # ── Language section ──
        lang_grp = QGroupBox("Language")
        llo = QVBoxLayout(lang_grp); llo.setSpacing(6)

        self.combo_lang = QComboBox()
        self.combo_lang.addItem("English", "en")
        self.combo_lang.addItem("Français", "fr")
        cur = get_language()
        if cur == "fr":
            self.combo_lang.setCurrentIndex(1)
        llo.addWidget(self.combo_lang)
        lo.addWidget(lang_grp)

        lo.addStretch()

        # Buttons
        row = QHBoxLayout()
        for txt, slot, bg in [
            ("Cancel", self.reject, COLORS['button_bg']),
            ("Apply", self._apply, COLORS['accent']),
        ]:
            b = QPushButton(txt); b.setFixedHeight(32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{ background: {bg}; color: white; border: none;
                    border-radius: 6px; font-weight: bold; font-size: 12px; }}
                QPushButton:hover {{ background: {COLORS['accent_hover']}; }}
            """)
            b.clicked.connect(slot); row.addWidget(b)
        lo.addLayout(row)

    def _apply(self):
        """Applique les parametres selectionnes et ferme le dialog."""
        self.selected_output = self.combo_out.currentData()
        self.selected_input = self.combo_in.currentData()
        self.selected_language = self.combo_lang.currentData()
        self.accept()
