"""Record and About dialogs."""
import numpy as np, sounddevice as sd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from utils.config import COLORS, RECORDING_SAMPLE_RATE, RECORDING_CHANNELS, APP_NAME, APP_VERSION
from utils.translator import t

class RecordDialog(QDialog):
    recording_done = pyqtSignal(np.ndarray, int)

    def __init__(self, input_device=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("record.title")); self.setFixedSize(380, 250)
        self.setStyleSheet(f"QDialog {{ background: {COLORS['bg_medium']}; }}")
        self._recording = False; self._data = []; self._stream = None; self._level = 0.0
        self._input_device = input_device

        lo = QVBoxLayout(self); lo.setSpacing(12); lo.setContentsMargins(20, 16, 20, 16)
        title = QLabel(t("record.title")); title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); lo.addWidget(title)

        self.lbl_status = QLabel(t("record.ready")); self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px;"); lo.addWidget(self.lbl_status)

        self.level_bar = QProgressBar(); self.level_bar.setRange(0, 100); self.level_bar.setFixedHeight(12)
        self.level_bar.setStyleSheet(f"QProgressBar {{ background: {COLORS['bg_dark']}; border: none; border-radius: 4px; }} QProgressBar::chunk {{ background: {COLORS['accent']}; border-radius: 4px; }}")
        lo.addWidget(self.level_bar)

        self.lbl_timer = QLabel("00:00"); self.lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_timer.setStyleSheet(f"color: {COLORS['text']}; font-family: Consolas; font-size: 24px;"); lo.addWidget(self.lbl_timer)

        row = QHBoxLayout()
        self.btn_rec = QPushButton("REC"); self.btn_rec.setFixedHeight(36)
        self.btn_rec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rec.setStyleSheet(f"QPushButton {{ background: {COLORS['recording']}; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 13px; }} QPushButton:hover {{ background: #ff5566; }}")
        self.btn_rec.clicked.connect(self._toggle); row.addWidget(self.btn_rec)

        self.btn_done = QPushButton(t("record.finish")); self.btn_done.setFixedHeight(36); self.btn_done.setEnabled(False)
        self.btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_done.setStyleSheet(f"QPushButton {{ background: {COLORS['accent']}; color: white; border: none; border-radius: 6px; font-weight: bold; }} QPushButton:hover {{ background: {COLORS['accent_hover']}; }} QPushButton:disabled {{ background: {COLORS['button_bg']}; color: {COLORS['text_dim']}; }}")
        self.btn_done.clicked.connect(self._finish); row.addWidget(self.btn_done)
        lo.addLayout(row)

        self._timer = QTimer(); self._timer.timeout.connect(self._upd); self._timer.setInterval(50); self._elapsed = 0.0

    def _toggle(self):
        """Bascule entre enregistrement et arret."""
        if not self._recording: self._start()
        else: self._stop_rec()

    def _start(self):
        """Demarre l enregistrement micro via sounddevice."""
        self._data.clear(); self._recording = True; self._elapsed = 0.0
        self.btn_rec.setText("STOP"); self.lbl_status.setText(t("record.recording"))
        self.lbl_status.setStyleSheet(f"color: {COLORS['recording']}; font-size: 12px;")
        try:
            self._stream = sd.InputStream(samplerate=RECORDING_SAMPLE_RATE, channels=RECORDING_CHANNELS,
                dtype="float32", callback=self._cb, blocksize=1024, device=self._input_device)
            self._stream.start(); self._timer.start()
        except Exception as e:
            self.lbl_status.setText(f"Error: {e}"); self._recording = False

    def _stop_rec(self):
        """Arrete l enregistrement et ferme le dialog."""
        self._recording = False; self._timer.stop()
        if self._stream: self._stream.stop(); self._stream.close(); self._stream = None
        self.btn_rec.setText("REC"); self.lbl_status.setText(t("record.done"))
        self.lbl_status.setStyleSheet(f"color: {COLORS['playhead']}; font-size: 12px;")
        self.btn_done.setEnabled(len(self._data) > 0)

    def _cb(self, indata, frames, ti, status):
        """Callback audio appele par sounddevice pour chaque buffer."""
        if self._recording: self._data.append(indata.copy()); self._level = float(np.max(np.abs(indata)))

    def _upd(self):
        """Met a jour l affichage du temps d enregistrement."""
        self.level_bar.setValue(int(self._level * 100)); self._elapsed += 0.05
        self.lbl_timer.setText(f"{int(self._elapsed//60):02d}:{int(self._elapsed%60):02d}")

    def _finish(self):
        """Termine l enregistrement, concatene les buffers."""
        if self._data: self.recording_done.emit(np.concatenate(self._data, axis=0), RECORDING_SAMPLE_RATE)
        self.accept()

    def closeEvent(self, e):
        """Arrete l enregistrement si le dialog est ferme."""
        if self._recording: self._stop_rec(); e.accept()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}"); self.setFixedSize(400, 380)
        self.setStyleSheet(f"QDialog {{ background: {COLORS['bg_medium']}; }}")
        lo = QVBoxLayout(self); lo.setSpacing(10); lo.setContentsMargins(24, 24, 24, 24)

        title = QLabel(APP_NAME); title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(title)

        v = QLabel(f"v{APP_VERSION}"); v.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter); lo.addWidget(v)

        lo.addSpacing(6)
        d = QLabel(t("about.desc")); d.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter); d.setWordWrap(True); lo.addWidget(d)

        lo.addSpacing(6)
        gh_url = "https://github.com/Spiralyfox/Glitch-Maker"
        gh = QLabel(f'<a href="{gh_url}" style="color: {COLORS["accent"]};">{gh_url}</a>')
        gh.setOpenExternalLinks(True)
        gh.setAlignment(Qt.AlignmentFlag.AlignCenter); gh.setWordWrap(True)
        lo.addWidget(gh)

        gh_hint = QLabel(t("about.github_hint"))
        gh_hint.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        gh_hint.setAlignment(Qt.AlignmentFlag.AlignCenter); gh_hint.setWordWrap(True)
        lo.addWidget(gh_hint)

        lo.addSpacing(6)
        bug_lbl = QLabel(t("about.bug_report"))
        bug_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
        bug_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); bug_lbl.setWordWrap(True)
        lo.addWidget(bug_lbl)

        issue_url = "https://github.com/Spiralyfox"
        issue_lbl = QLabel(f'<a href="{issue_url}" style="color: {COLORS["accent"]};">{issue_url}</a>')
        issue_lbl.setOpenExternalLinks(True)
        issue_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(issue_lbl)

        lo.addStretch()

        # Credits
        sep = QLabel("─" * 30); sep.setStyleSheet(f"color: {COLORS['border']}; font-size: 8px;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter); lo.addWidget(sep)

        author = QLabel(t("about.by")); author.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        author.setStyleSheet(f"color: {COLORS['text']};")
        author.setAlignment(Qt.AlignmentFlag.AlignCenter); lo.addWidget(author)

        tech = QLabel(t("about.tech")); tech.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        tech.setAlignment(Qt.AlignmentFlag.AlignCenter); lo.addWidget(tech)
