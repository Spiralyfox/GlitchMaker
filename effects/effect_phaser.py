# ══════════════════════════════════════════════════
# Effect Metadata (edit these to customize)
# ══════════════════════════════════════════════════
EFFECT_ID      = "phaser"
EFFECT_ICON    = "A"
EFFECT_COLOR   = "#6d597a"
EFFECT_SECTION = "Modulation"

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
        super().__init__("Phaser", p)
        self.rt = _slider_float(self._lo, "Rate (Hz)", 0.05, 10, 0.5, 0.1, 2, " Hz", 100)
        self.dp = _slider_float(self._lo, "Depth", 0, 1, 0.7, 0.1, 2)
        self.st = _slider_int(self._lo, "Stages", 1, 12, 4)
        self.fb = _slider_float(self._lo, "Feedback", 0, 0.95, 0.3, 0.05, 2)
        self.mx = _slider_float(self._lo, "Mix", 0, 1, 0.7, 0.1, 2)
        self._finish()
    def get_params(self): return {"rate_hz": self.rt.value(), "depth": self.dp.value(), "stages": self.st.value(), "feedback": self.fb.value(), "mix": self.mx.value()}
    def set_params(self, p):
        self.rt.setValue(p.get("rate_hz", 0.5)); self.dp.setValue(p.get("depth", 0.7))
        self.st.setValue(p.get("stages", 4)); self.fb.setValue(p.get("feedback", 0.3))
        self.mx.setValue(p.get("mix", 0.7))
# ══════════════════════════════════════════════════
# DSP / Process
# ══════════════════════════════════════════════════

from scipy.signal import lfilter

def process(audio_data, start, end, sr=44100, **kw):
    from core.effects.phaser import phaser
    return phaser(audio_data, start, end,
                  rate_hz=kw.get("rate_hz", 0.5),
                  depth=kw.get("depth", 0.7),
                  stages=kw.get("stages", 4),
                  feedback=kw.get("feedback", 0.3),
                  mix=kw.get("mix", 0.7),
                  sr=sr)
