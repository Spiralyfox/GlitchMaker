"""Transport bar — Play, Pause, Stop, Volume, Time."""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from utils.config import COLORS

class TransportBar(QWidget):
    play_clicked = pyqtSignal(); pause_clicked = pyqtSignal(); stop_clicked = pyqtSignal()
    volume_changed = pyqtSignal(float); add_audio_clicked = pyqtSignal()
    automations_clicked = pyqtSignal()

    def __init__(self, parent=None):
        """Initialise la barre de transport (play/stop/volume/temps)."""
        super().__init__(parent); self.setFixedHeight(46); self._playing = False; self._build()

    def _build(self):
        """Construit les widgets de la barre de transport."""
        lo = QHBoxLayout(self); lo.setContentsMargins(10, 4, 10, 4); lo.setSpacing(6)
        self.btn_stop = self._btn("STOP", 50, COLORS['button_bg'])
        self.btn_stop.clicked.connect(self.stop_clicked.emit); lo.addWidget(self.btn_stop)
        self.btn_play = self._btn("PLAY", 60, COLORS['accent'], bold=True)
        self.btn_play.clicked.connect(self._on_play); lo.addWidget(self.btn_play)
        self.lbl_time = QLabel("00:00.00 / 00:00.00")
        self.lbl_time.setStyleSheet(f"color: {COLORS['text']}; font-family: Consolas, monospace; font-size: 12px;")
        self.lbl_time.setFixedWidth(160); lo.addWidget(self.lbl_time); lo.addStretch()
        self.lbl_sel = QLabel(""); self.lbl_sel.setStyleSheet(f"color: {COLORS['accent']}; font-size: 10px;")
        lo.addWidget(self.lbl_sel); lo.addStretch()
        vol_lbl = QLabel("Vol"); vol_lbl.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;"); lo.addWidget(vol_lbl)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal); self.vol_slider.setRange(0, 100); self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(90)
        self.vol_slider.valueChanged.connect(lambda v: self.volume_changed.emit(v / 100.0))
        self.vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background: {COLORS['bg_dark']}; height: 5px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {COLORS['accent']}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
            QSlider::sub-page:horizontal {{ background: {COLORS['accent_secondary']}; border-radius: 2px; }}
        """); lo.addWidget(self.vol_slider)
        self.lbl_vol = QLabel("80%"); self.lbl_vol.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;"); self.lbl_vol.setFixedWidth(30)
        self.vol_slider.valueChanged.connect(lambda v: self.lbl_vol.setText(f"{v}%")); lo.addWidget(self.lbl_vol)
        lo.addSpacing(8)
        self.btn_auto = self._btn("Automations", 90, COLORS['button_bg'])
        self.btn_auto.setToolTip("Open Automations window")
        self.btn_auto.clicked.connect(self.automations_clicked.emit); lo.addWidget(self.btn_auto)
        lo.addSpacing(4)
        self.btn_add = self._btn("＋", 36, COLORS['button_bg'])
        self.btn_add.setToolTip("Add audio to timeline")
        self.btn_add.clicked.connect(self.add_audio_clicked.emit); lo.addWidget(self.btn_add)

    def _btn(self, text, width, bg, bold=False):
        """Crée un bouton stylisé pour la barre de transport."""
        b = QPushButton(text); b.setFixedSize(width, 32); b.setCursor(Qt.CursorShape.PointingHandCursor)
        bw = "bold" if bold else "normal"
        b.setStyleSheet(f"QPushButton {{ background: {bg}; color: white; border: none; border-radius: 5px; font-size: 13px; font-weight: {bw}; }} QPushButton:hover {{ background: {COLORS['accent_hover']}; }}")
        return b

    """Emet play ou pause selon l etat actuel."""
    def _on_play(self): (self.pause_clicked if self._playing else self.play_clicked).emit()
    """Met a jour l affichage play/pause."""
    def set_playing(self, p): self._playing = p; self.btn_play.setText("PAUSE" if p else "PLAY")
    """Met a jour l affichage du temps courant/total."""
    def set_time(self, c, t): self.lbl_time.setText(f"{c} / {t}")
    """Affiche l info de selection dans la barre."""
    def set_selection_info(self, t): self.lbl_sel.setText(t)
