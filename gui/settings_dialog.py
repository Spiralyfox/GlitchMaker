"""
Settings dialogs — separate windows for Audio, Language, and Theme.
v5.9 — 3 separate dialogs. No separator lines — spacing-based design.
"""

import sounddevice as sd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from utils.config import COLORS, get_theme
from utils.translator import t, get_language


def _combo_style():
    return (f"QComboBox {{ background: {COLORS['bg_medium']}; color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; border-radius: 5px;"
            f" padding: 6px 10px; font-size: 12px; min-height: 28px; }}"
            f" QComboBox QAbstractItemView {{ background: {COLORS['bg_medium']};"
            f" color: {COLORS['text']}; selection-background-color: {COLORS['accent']}; }}"
            f" QComboBox::drop-down {{ border: none; width: 24px; }}")


def _button_row(dialog, cancel_slot, apply_slot):
    row = QHBoxLayout()
    row.setSpacing(12)
    for txt, slot, bg in [
        (t("dialog.cancel"), cancel_slot, COLORS['button_bg']),
        (t("dialog.apply"), apply_slot, COLORS['accent']),
    ]:
        b = QPushButton(txt)
        b.setFixedHeight(36)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{ background: {bg}; color: white; border: none;
                border-radius: 6px; font-weight: bold; font-size: 13px;
                padding: 0 28px; }}
            QPushButton:hover {{ background: {COLORS['accent_hover']}; }}
        """)
        b.clicked.connect(slot)
        row.addWidget(b)
    return row


def _dialog_style():
    return f"""
        QDialog {{ background: {COLORS['bg_dark']}; }}
        QLabel {{ color: {COLORS['text']}; }}
    """


def _title_label(text):
    title = QLabel(text)
    title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
    title.setStyleSheet(f"color: {COLORS['accent']}; margin-bottom: 16px;")
    return title


def _field_label(text):
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; margin-top: 2px;")
    return lbl


class AudioSettingsDialog(QDialog):
    """Audio device selection with refresh button."""

    def __init__(self, current_output=None, current_input=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings.audio_title"))
        self.setFixedSize(480, 360)
        self.setStyleSheet(_dialog_style())
        self.selected_output = current_output
        self.selected_input = current_input
        self._current_output = current_output
        self._current_input = current_input

        lo = QVBoxLayout(self)
        lo.setSpacing(0)
        lo.setContentsMargins(28, 24, 28, 24)

        lo.addWidget(_title_label(t("settings.audio_title")))

        refresh_row = QHBoxLayout()
        refresh_row.addStretch()
        self._btn_refresh = QPushButton(t("settings.refresh"))
        self._btn_refresh.setFixedHeight(32)
        self._btn_refresh.setMinimumWidth(120)
        self._btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['bg_medium']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 6px;
                font-size: 12px; font-weight: bold; padding: 0 16px; }}
            QPushButton:hover {{ color: {COLORS['accent']}; border-color: {COLORS['accent']}; }}
        """)
        self._btn_refresh.clicked.connect(self._refresh_devices)
        refresh_row.addWidget(self._btn_refresh)
        lo.addLayout(refresh_row)
        lo.addSpacing(18)

        lo.addWidget(_field_label(t("settings.output")))
        lo.addSpacing(6)
        self.combo_out = QComboBox()
        self.combo_out.setStyleSheet(_combo_style())
        lo.addWidget(self.combo_out)
        lo.addSpacing(20)

        lo.addWidget(_field_label(t("settings.input")))
        lo.addSpacing(6)
        self.combo_in = QComboBox()
        self.combo_in.setStyleSheet(_combo_style())
        lo.addWidget(self.combo_in)

        self._populate_devices()

        lo.addStretch()
        lo.addSpacing(16)
        lo.addLayout(_button_row(self, self.reject, self._apply))

    def _populate_devices(self):
        self.combo_out.clear()
        self.combo_in.clear()
        try:
            devices = sd.query_devices()
            default_out = sd.default.device[1]
            default_in = sd.default.device[0]
        except Exception:
            devices = []
            default_out = default_in = -1

        # Deduplicate by name — keep first occurrence, prefer default
        seen_out = {}
        for i, d in enumerate(devices):
            if d['max_output_channels'] > 0:
                name = d['name']
                if name not in seen_out or i == default_out:
                    seen_out[name] = i

        seen_in = {}
        for i, d in enumerate(devices):
            if d['max_input_channels'] > 0:
                name = d['name']
                if name not in seen_in or i == default_in:
                    seen_in[name] = i

        for name, idx in sorted(seen_out.items(), key=lambda x: x[0]):
            suffix = " ★" if idx == default_out else ""
            self.combo_out.addItem(f"{name}{suffix}", idx)
            if self._current_output is not None:
                if self._current_output == idx:
                    self.combo_out.setCurrentIndex(self.combo_out.count() - 1)
            elif idx == default_out:
                self.combo_out.setCurrentIndex(self.combo_out.count() - 1)

        for name, idx in sorted(seen_in.items(), key=lambda x: x[0]):
            suffix = " ★" if idx == default_in else ""
            self.combo_in.addItem(f"{name}{suffix}", idx)
            if self._current_input is not None:
                if self._current_input == idx:
                    self.combo_in.setCurrentIndex(self.combo_in.count() - 1)
            elif idx == default_in:
                self.combo_in.setCurrentIndex(self.combo_in.count() - 1)

    def _refresh_devices(self):
        self._current_output = self.combo_out.currentData()
        self._current_input = self.combo_in.currentData()
        self._populate_devices()

    def _apply(self):
        self.selected_output = self.combo_out.currentData()
        self.selected_input = self.combo_in.currentData()
        self.accept()


class LanguageSettingsDialog(QDialog):
    """Language selection only."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings.lang_title"))
        self.setFixedSize(360, 200)
        self.setStyleSheet(_dialog_style())
        self.selected_language = get_language()

        lo = QVBoxLayout(self)
        lo.setSpacing(0)
        lo.setContentsMargins(24, 20, 24, 20)

        lo.addWidget(_title_label(t("settings.lang_title")))

        lo.addWidget(_field_label(t("settings.language")))
        lo.addSpacing(6)
        self.combo_lang = QComboBox()
        self.combo_lang.setStyleSheet(_combo_style())
        self.combo_lang.addItem("English", "en")
        self.combo_lang.addItem("Français", "fr")
        if get_language() == "fr":
            self.combo_lang.setCurrentIndex(1)
        lo.addWidget(self.combo_lang)

        lo.addStretch()
        lo.addLayout(_button_row(self, self.reject, self._apply))

    def _apply(self):
        self.selected_language = self.combo_lang.currentData()
        self.accept()


class ThemeSettingsDialog(QDialog):
    """Theme selection only."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("settings.theme_title"))
        self.setFixedSize(360, 200)
        self.setStyleSheet(_dialog_style())
        self.selected_theme = get_theme()

        lo = QVBoxLayout(self)
        lo.setSpacing(0)
        lo.setContentsMargins(24, 20, 24, 20)

        lo.addWidget(_title_label(t("settings.theme_title")))

        lo.addWidget(_field_label(t("settings.theme")))
        lo.addSpacing(6)
        self.combo_theme = QComboBox()
        self.combo_theme.setStyleSheet(_combo_style())
        self.combo_theme.addItem(t("settings.theme.dark"), "dark")
        self.combo_theme.addItem(t("settings.theme.light"), "light")
        if get_theme() == "light":
            self.combo_theme.setCurrentIndex(1)
        lo.addWidget(self.combo_theme)

        lo.addStretch()
        lo.addLayout(_button_row(self, self.reject, self._apply))

    def _apply(self):
        self.selected_theme = self.combo_theme.currentData()
        self.accept()


# Backward compatibility alias
SettingsDialog = AudioSettingsDialog
