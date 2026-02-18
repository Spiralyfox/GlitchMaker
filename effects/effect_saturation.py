# ══════════════════════════════════════════════════
# Effect Metadata (edit these to customize)
# ══════════════════════════════════════════════════
EFFECT_ID      = "saturation"
EFFECT_ICON    = "D"
EFFECT_COLOR   = "#ff6b35"
EFFECT_SECTION = "Distortion"

# ══════════════════════════════════════════════════
# Dialog (UI for effect parameters)
# ══════════════════════════════════════════════════
import numpy as np
from PyQt6.QtWidgets import QLabel, QComboBox, QCheckBox, QHBoxLayout, QDial
from PyQt6.QtCore import Qt
from gui.effect_dialogs import _Base, _slider_int, _slider_float, _btn
from utils.config import COLORS

class Dialog(_Base):
    def __init__(self, p=None):
        super().__init__("Saturation", p)
        self._row("Type"); self.tp = QComboBox(); self.tp.addItems(["soft", "hard", "overdrive"]); self._lo.addWidget(self.tp)
        self.dr = _slider_float(self._lo, "Drive", 0.5, 20, 3.0, 0.5, 1, "", 10)
        self.tn = _slider_float(self._lo, "Tone", 0, 1, 0.5, 0.05, 2)
        self._finish()
    def get_params(self): return {"type": self.tp.currentText(), "drive": self.dr.value(), "tone": self.tn.value()}
    def set_params(self, p):
        idx = self.tp.findText(p.get("type", "soft"))
        if idx >= 0: self.tp.setCurrentIndex(idx)
        self.dr.setValue(p.get("drive", 3.0))
        self.tn.setValue(p.get("tone", 0.5))
# ══════════════════════════════════════════════════
# DSP / Process
# ══════════════════════════════════════════════════

def process(audio_data, start, end, sr=44100, **kw):
    from core.effects.saturation import saturate
    return saturate(audio_data, start, end,
                    mode=kw.get("type", "soft"),
                    drive=kw.get("drive", 3.0),
                    tone=kw.get("tone", 0.5),
                    sr=sr)
