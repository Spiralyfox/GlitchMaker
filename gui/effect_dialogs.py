"""Effect parameter dialogs for all 22 effects.
Small-range params use Slider + SpinBox combo.
"""
from utils.logger import get_logger
_log = get_logger("dialogs")
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QSpinBox, QDoubleSpinBox, QComboBox,
    QPushButton, QCheckBox, QDial
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from utils.config import COLORS
import numpy as np

_SS = f"""
QDialog {{ background: {COLORS['bg_medium']}; }}
QLabel {{ color: {COLORS['text']}; font-size: 11px; }}
QSlider::groove:horizontal {{ background: {COLORS['bg_dark']}; height: 5px; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {COLORS['accent']}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
QSlider::sub-page:horizontal {{ background: {COLORS['accent_secondary']}; border-radius: 2px; }}
QSpinBox, QDoubleSpinBox, QComboBox {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
    border: 1px solid {COLORS['border']}; border-radius: 4px; padding: 4px; font-size: 11px; }}
QCheckBox {{ color: {COLORS['text']}; font-size: 11px; }}
QDial {{ background: transparent; }}
"""

def _btn(text, bg=COLORS['accent']):
    """Cree un bouton stylise pour le dialogue d effet."""
    b = QPushButton(text); b.setFixedHeight(30)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(f"QPushButton {{ background: {bg}; color: white; border: none; border-radius: 5px; font-weight: bold; }} QPushButton:hover {{ background: {COLORS['accent_hover']}; }}")
    return b


def _slider_int(lo_layout, label, lo_val, hi_val, default, suffix=""):
    """Create a horizontal slider + spinbox for integer ranges."""
    lo_layout.addWidget(QLabel(label))
    row = QHBoxLayout()
    sl = QSlider(Qt.Orientation.Horizontal)
    sl.setRange(lo_val, hi_val); sl.setValue(default)
    sb = QSpinBox(); sb.setRange(lo_val, hi_val); sb.setValue(default)
    if suffix: sb.setSuffix(suffix)
    sb.setFixedWidth(70)
    sl.valueChanged.connect(sb.setValue); sb.valueChanged.connect(sl.setValue)
    row.addWidget(sl, stretch=1); row.addWidget(sb)
    lo_layout.addLayout(row)
    return sb


def _slider_float(lo_layout, label, lo_val, hi_val, default, step=0.1, decimals=2, suffix="", mult=100):
    """Create a horizontal slider + double spinbox for float ranges.
    Slider uses integer (value*mult), spinbox shows actual float."""
    lo_layout.addWidget(QLabel(label))
    row = QHBoxLayout()
    sl = QSlider(Qt.Orientation.Horizontal)
    sl.setRange(int(lo_val * mult), int(hi_val * mult))
    sl.setValue(int(default * mult))
    sb = QDoubleSpinBox()
    sb.setRange(lo_val, hi_val); sb.setValue(default)
    sb.setSingleStep(step); sb.setDecimals(decimals)
    if suffix: sb.setSuffix(suffix)
    sb.setFixedWidth(80)
    sl.valueChanged.connect(lambda v: sb.setValue(v / mult))
    sb.valueChanged.connect(lambda v: sl.setValue(int(v * mult)))
    row.addWidget(sl, stretch=1); row.addWidget(sb)
    lo_layout.addLayout(row)
    return sb


class _PreviewWorker(QThread):
    """Processes effect in background thread for preview."""
    done = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, fn, segment, sr, params, parent=None):
        """Initialise les sliders de parametres pour _PreviewWorker."""
        super().__init__(parent)
        self._fn, self._seg, self._sr, self._params = fn, segment, sr, params

    def run(self):
        """Affiche le dialogue modal et retourne les parametres si OK."""
        try:
            result = self._fn(self._seg.copy(), 0, len(self._seg),
                              sr=self._sr, **self._params)
            self.done.emit(result)
        except Exception as ex:
            self.error.emit(str(ex))


class _Base(QDialog):
    def __init__(self, title, parent=None):
        """Initialise les sliders de parametres pour _Base."""
        super().__init__(parent)
        self.setWindowTitle(title); self.setFixedWidth(380); self.setStyleSheet(_SS)
        self._lo = QVBoxLayout(self); self._lo.setSpacing(8); self._lo.setContentsMargins(16, 12, 16, 12)
        t = QLabel(title); t.setStyleSheet(f"color: {COLORS['accent']}; font-size: 14px; font-weight: bold;"); self._lo.addWidget(t)
        self._pv_segment = None
        self._pv_sr = 44100
        self._pv_process_fn = None
        self._pv_worker = None
        self._pv_playing = False
        self._pv_device = None   # will receive playback.output_device

    """Ajoute une rangee de widgets au layout."""
    """Ajoute une rangee label + widget au layout du dialogue."""
    def _row(self, label): self._lo.addWidget(QLabel(label))

    def setup_preview(self, segment, sr, process_fn, output_device=None):
        """Inject audio context + output device for live preview."""
        self._pv_segment = segment
        self._pv_sr = sr
        self._pv_process_fn = process_fn
        self._pv_device = output_device

    def _finish(self):
        """Finalise le dialogue — ajoute les boutons OK/Cancel/Preview."""
        r = QHBoxLayout()
        bc = _btn("Cancel", COLORS['button_bg']); bc.clicked.connect(self.reject); r.addWidget(bc)
        # Randomize button (step 51)
        self._rnd_btn = _btn("🎲", "#7209b7")
        self._rnd_btn.setFixedWidth(40)
        self._rnd_btn.setToolTip("Randomize parameters")
        self._rnd_btn.clicked.connect(self._randomize_params)
        r.addWidget(self._rnd_btn)
        self._pv_btn = _btn("▶ Preview", "#2563eb")
        self._pv_btn.setFixedWidth(100)
        self._pv_btn.clicked.connect(self._toggle_preview)
        self._pv_btn.setVisible(False)
        r.addWidget(self._pv_btn)
        ba = _btn("Apply"); ba.clicked.connect(self._on_accept); r.addWidget(ba)
        self._lo.addLayout(r)

    def showEvent(self, e):
        """Charge les params au premier affichage du dialogue."""
        super().showEvent(e)
        if self._pv_segment is not None and self._pv_process_fn is not None:
            self._pv_btn.setVisible(True)

    def _toggle_preview(self):
        """Lance ou arrete la preview audio de l effet."""
        if self._pv_playing:
            self._stop_preview()
        else:
            self._start_preview()

    def _start_preview(self):
        """Lance le calcul de preview dans un thread separe."""
        if self._pv_segment is None or self._pv_process_fn is None:
            return
        try:
            self._stop_preview()
            self._pv_btn.setText("⏳ ...")
            self._pv_btn.setEnabled(False)
            params = self.get_params()
            # Cap at 5 seconds max
            seg = self._pv_segment
            max_n = self._pv_sr * 5
            if len(seg) > max_n:
                seg = seg[:max_n]
            worker = _PreviewWorker(self._pv_process_fn, seg,
                                    self._pv_sr, params, self)
            self._pv_worker = worker
            worker.done.connect(self._on_preview_ready)
            worker.error.connect(self._on_preview_error)
            worker.start()
        except Exception as ex:
            _log.error("Preview start error: %s", ex)
            self._pv_btn.setText("▶ Preview"); self._pv_btn.setEnabled(True)

    def _on_preview_ready(self, result):
        """Callback quand la preview est prete — lance la lecture."""
        self._pv_worker = None
        if result is None:
            self._pv_btn.setText("▶ Preview"); self._pv_btn.setEnabled(True); return
        try:
            import sounddevice as sd
            audio = np.asarray(result, dtype=np.float32)
            audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)
            audio = np.clip(audio, -1.0, 1.0)
            if audio.ndim == 1:
                audio = np.column_stack([audio, audio])
            elif audio.ndim > 1 and audio.shape[1] > 2:
                audio = audio[:, :2]
            if len(audio) == 0:
                self._pv_btn.setText("▶ Preview"); self._pv_btn.setEnabled(True); return
            # sd.play — simple, reliable, uses the SAME device as main playback
            sd.stop()
            sd.play(audio, samplerate=self._pv_sr, device=self._pv_device)
            self._pv_playing = True
            self._pv_btn.setText("⏹ Stop"); self._pv_btn.setEnabled(True)
            # Auto-reset when finished
            dur_ms = int(len(audio) / self._pv_sr * 1000) + 300
            self._pv_timer = QTimer(self)
            self._pv_timer.setSingleShot(True)
            self._pv_timer.timeout.connect(self._on_preview_done)
            self._pv_timer.start(dur_ms)
        except Exception as ex:
            _log.error("Preview playback error: %s", ex)
            self._pv_btn.setText("▶ Preview"); self._pv_btn.setEnabled(True)
            self._pv_playing = False

    def _on_preview_done(self):
        """Callback quand la lecture de preview est terminee."""
        self._pv_playing = False
        self._pv_btn.setText("▶ Preview"); self._pv_btn.setEnabled(True)

    def _on_preview_error(self, msg):
        """Callback en cas d erreur pendant la preview."""
        self._pv_worker = None
        self._pv_btn.setText("▶ Preview"); self._pv_btn.setEnabled(True)
        _log.error("Preview error: %s", msg)

    def _stop_preview(self):
        """Arrete la preview et restaure le stream principal."""
        self._pv_playing = False
        if hasattr(self, '_pv_timer') and self._pv_timer:
            self._pv_timer.stop()
        try:
            import sounddevice as sd; sd.stop()
        except Exception: pass
        if self._pv_worker is not None:
            try: self._pv_worker.quit(); self._pv_worker.wait(500)
            except: pass
            self._pv_worker = None
        self._pv_btn.setText("▶ Preview"); self._pv_btn.setEnabled(True)

    def _randomize_params(self):
        """Randomize all parameter widgets (Step 51).
        Discovers QSpinBox, QDoubleSpinBox, QSlider, QComboBox and sets random values.
        """
        import random
        for w in self.findChildren(QSpinBox):
            lo, hi = w.minimum(), w.maximum()
            w.setValue(random.randint(lo, hi))
        for w in self.findChildren(QDoubleSpinBox):
            lo, hi = w.minimum(), w.maximum()
            w.setValue(round(random.uniform(lo, hi), w.decimals()))
        for w in self.findChildren(QSlider):
            lo, hi = w.minimum(), w.maximum()
            w.setValue(random.randint(lo, hi))
        for w in self.findChildren(QComboBox):
            if w.count() > 1:
                w.setCurrentIndex(random.randint(0, w.count() - 1))
        # Don't touch QCheckBox — too disruptive

    def _on_accept(self):
        """Arrete la preview et accepte le dialogue."""
        self._stop_preview(); self.accept()

    def reject(self):
        """Arrete la preview et rejette le dialogue."""
        self._stop_preview(); super().reject()

    def closeEvent(self, e):
        """Arrete la preview quand le dialogue est ferme."""
        self._stop_preview(); super().closeEvent(e)

    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self) -> dict: return {}
    """Charge les parametres depuis un dict."""
    def set_params(self, p: dict): pass


# ─── Basics ───

class ReverseDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Reverse."""
        super().__init__("Reverse", p)
        self._lo.addWidget(QLabel("Reverses the selected audio."))
        self._finish()

class VolumeDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Volume."""
        super().__init__("Volume", p)
        self.inp = _slider_int(self._lo, "Gain (%)", 0, 1000, 100, " %")
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"gain_pct": self.inp.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.inp.setValue(int(p.get("gain_pct", 100)))

class FilterDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Filter."""
        super().__init__("Filter", p)
        self._row("Type"); self.tp = QComboBox(); self.tp.addItems(["lowpass", "highpass", "bandpass"]); self._lo.addWidget(self.tp)
        self.cf = _slider_int(self._lo, "Cutoff (Hz)", 20, 20000, 1000, " Hz")
        self.rs = _slider_float(self._lo, "Resonance", 0.1, 20, 1.0, 0.5, 1, "", 10)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"filter_type": self.tp.currentText(), "cutoff_hz": self.cf.value(), "resonance": self.rs.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        idx = self.tp.findText(p.get("filter_type", "lowpass"))
        if idx >= 0: self.tp.setCurrentIndex(idx)
        self.cf.setValue(int(p.get("cutoff_hz", 1000)))
        self.rs.setValue(p.get("resonance", 1.0))

# ─── Pitch & Time ───

class PitchShiftDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour PitchShift."""
        super().__init__("Pitch Shift", p)
        self.st = _slider_float(self._lo, "Semitones", -24, 24, 0, 1, 1, " st", 10)
        self.simple = QCheckBox("Simple mode (faster)"); self._lo.addWidget(self.simple)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"semitones": self.st.value(), "simple": self.simple.isChecked()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.st.setValue(p.get("semitones", 0)); self.simple.setChecked(p.get("simple", False))

class TimeStretchDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour TimeStretch."""
        super().__init__("Time Stretch", p)
        self.f = _slider_float(self._lo, "Factor (0.25=faster, 4.0=slower)", 0.1, 8, 1.0, 0.1, 2, "x", 100)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"factor": self.f.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.f.setValue(p.get("factor", 1.0))

class TapeStopDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour TapeStop."""
        super().__init__("Tape Stop", p)
        self.d = _slider_int(self._lo, "Duration (ms)", 100, 5000, 1500, " ms")
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"duration_ms": self.d.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.d.setValue(int(p.get("duration_ms", 1500)))

# ─── Distortion ───

class SaturationDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Saturation."""
        super().__init__("Saturation", p)
        self._row("Type"); self.tp = QComboBox(); self.tp.addItems(["hard", "soft", "overdrive"]); self._lo.addWidget(self.tp)
        self.dr = _slider_float(self._lo, "Drive", 1, 20, 3, 0.5, 1, "", 10)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"type": self.tp.currentText(), "drive": self.dr.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        idx = self.tp.findText(p.get("type", "soft"))
        if idx >= 0: self.tp.setCurrentIndex(idx)
        self.dr.setValue(p.get("drive", 3.0))

class DistortionDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Distortion."""
        super().__init__("Distortion", p)
        self._row("Mode"); self.md = QComboBox(); self.md.addItems(["tube", "fuzz", "digital", "scream"]); self._lo.addWidget(self.md)
        self.dr = _slider_float(self._lo, "Drive", 1, 20, 5, 0.5, 1, "", 10)
        self.tn = _slider_float(self._lo, "Tone", 0, 1, 0.5, 0.05, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"drive": self.dr.value(), "tone": self.tn.value(), "mode": self.md.currentText()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        idx = self.md.findText(p.get("mode", "tube"))
        if idx >= 0: self.md.setCurrentIndex(idx)
        self.dr.setValue(p.get("drive", 5.0))
        self.tn.setValue(p.get("tone", 0.5))

class BitcrusherDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Bitcrusher."""
        super().__init__("Bitcrusher", p)
        self.bd = _slider_int(self._lo, "Bit depth", 1, 24, 8)
        self.ds = _slider_int(self._lo, "Downsample factor", 1, 32, 1)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"bit_depth": self.bd.value(), "downsample": self.ds.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.bd.setValue(p.get("bit_depth", 8)); self.ds.setValue(p.get("downsample", 1))

# ─── Modulation ───

class ChorusDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Chorus."""
        super().__init__("Chorus", p)
        self.dp = _slider_float(self._lo, "Depth (ms)", 0.5, 30, 5, 0.5, 1, " ms", 10)
        self.rt = _slider_float(self._lo, "Rate (Hz)", 0.1, 10, 1.5, 0.1, 1, " Hz", 10)
        self.vc = _slider_int(self._lo, "Voices", 1, 8, 2)
        self.mx = _slider_float(self._lo, "Mix", 0, 1, 0.5, 0.1, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"depth_ms": self.dp.value(), "rate_hz": self.rt.value(), "voices": self.vc.value(), "mix": self.mx.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.dp.setValue(p.get("depth_ms", 5)); self.rt.setValue(p.get("rate_hz", 1.5))
        self.vc.setValue(p.get("voices", 2)); self.mx.setValue(p.get("mix", 0.5))

class PhaserDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Phaser."""
        super().__init__("Phaser", p)
        self.rt = _slider_float(self._lo, "Rate (Hz)", 0.05, 10, 0.5, 0.1, 2, " Hz", 100)
        self.dp = _slider_float(self._lo, "Depth", 0, 1, 0.7, 0.1, 2)
        self.st = _slider_int(self._lo, "Stages", 1, 12, 4)
        self.mx = _slider_float(self._lo, "Mix", 0, 1, 0.7, 0.1, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"rate_hz": self.rt.value(), "depth": self.dp.value(), "stages": self.st.value(), "mix": self.mx.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.rt.setValue(p.get("rate_hz", 0.5)); self.dp.setValue(p.get("depth", 0.7))
        self.st.setValue(p.get("stages", 4)); self.mx.setValue(p.get("mix", 0.7))

class TremoloDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Tremolo."""
        super().__init__("Tremolo", p)
        self.rt = _slider_float(self._lo, "Rate (Hz)", 0.1, 30, 5, 0.5, 1, " Hz", 10)
        self.dp = _slider_float(self._lo, "Depth", 0, 1, 0.7, 0.1, 2)
        self._row("Shape"); self.sh = QComboBox(); self.sh.addItems(["sine", "square", "triangle", "saw"]); self._lo.addWidget(self.sh)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"rate_hz": self.rt.value(), "depth": self.dp.value(), "shape": self.sh.currentText()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.rt.setValue(p.get("rate_hz", 5)); self.dp.setValue(p.get("depth", 0.7))
        idx = self.sh.findText(p.get("shape", "sine"))
        if idx >= 0: self.sh.setCurrentIndex(idx)

class RingModDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour RingMod."""
        super().__init__("Ring Mod", p)
        self.f = _slider_int(self._lo, "Frequency (Hz)", 1, 5000, 440, " Hz")
        self.mx = _slider_float(self._lo, "Mix", 0, 1, 0.5, 0.1, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"frequency": self.f.value(), "mix": self.mx.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.f.setValue(int(p.get("frequency", 440))); self.mx.setValue(p.get("mix", 0.5))

# ─── Space & Texture ───

class DelayDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Delay."""
        super().__init__("Delay", p)
        self.d = _slider_int(self._lo, "Delay (ms)", 10, 2000, 300, " ms")
        self.fb = _slider_float(self._lo, "Feedback", 0, 0.95, 0.4, 0.05, 2)
        self.mx = _slider_float(self._lo, "Mix", 0, 1, 0.5, 0.1, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"delay_ms": self.d.value(), "feedback": self.fb.value(), "mix": self.mx.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.d.setValue(int(p.get("delay_ms", 300))); self.fb.setValue(p.get("feedback", 0.4)); self.mx.setValue(p.get("mix", 0.5))

class VinylDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Vinyl."""
        super().__init__("Vinyl", p)
        self.a = _slider_float(self._lo, "Amount", 0, 1, 0.5, 0.1, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"amount": self.a.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.a.setValue(p.get("amount", 0.5))

class OTTDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour OTT."""
        super().__init__("OTT", p)
        self.d = _slider_float(self._lo, "Depth", 0, 1, 0.5, 0.1, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"depth": self.d.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.d.setValue(p.get("depth", 0.5))

# ─── Glitch ───

class StutterDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Stutter."""
        super().__init__("Stutter", p)
        self.rep = _slider_int(self._lo, "Repeats", 1, 64, 4)
        self.dec = _slider_float(self._lo, "Decay", 0, 1, 0.0, 0.1, 2)
        self._row("Mode"); self.md = QComboBox(); self.md.addItems(["normal", "halving", "reverse_alt"]); self._lo.addWidget(self.md)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"repeats": self.rep.value(), "decay": self.dec.value(), "stutter_mode": self.md.currentText()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.rep.setValue(p.get("repeats", 4)); self.dec.setValue(p.get("decay", 0.0))
        idx = self.md.findText(p.get("stutter_mode", "normal"))
        if idx >= 0: self.md.setCurrentIndex(idx)

class GranularDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Granular."""
        super().__init__("Granular", p)
        self.gs = _slider_int(self._lo, "Grain size (ms)", 5, 500, 50, " ms")
        self.dn = _slider_int(self._lo, "Density", 1, 16, 4)
        self.ch = _slider_float(self._lo, "Chaos", 0, 1, 0.5, 0.1, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"grain_ms": self.gs.value(), "density": self.dn.value(), "chaos": self.ch.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.gs.setValue(p.get("grain_ms", 50)); self.dn.setValue(p.get("density", 4)); self.ch.setValue(p.get("chaos", 0.5))

class ShuffleDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Shuffle."""
        super().__init__("Shuffle", p)
        self.n = _slider_int(self._lo, "Number of slices", 2, 64, 8)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"num_slices": self.n.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.n.setValue(p.get("num_slices", 8))

class BufferFreezeDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour BufferFreeze."""
        super().__init__("Buffer Freeze", p)
        self.bs = _slider_int(self._lo, "Buffer size (ms)", 10, 500, 50, " ms")
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"buffer_ms": self.bs.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.bs.setValue(p.get("buffer_ms", 50))

class DatamoshDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Datamosh."""
        super().__init__("Datamosh", p)
        self.bs = _slider_int(self._lo, "Block size", 64, 8192, 512)
        self.ch = _slider_float(self._lo, "Chaos", 0, 1, 0.5, 0.1, 2)
        self._finish()
    """Retourne les parametres actuels sous forme de dict."""
    def get_params(self): return {"block_size": self.bs.value(), "chaos": self.ch.value()}
    """Charge les parametres depuis un dict."""
    def set_params(self, p): self.bs.setValue(p.get("block_size", 512)); self.ch.setValue(p.get("chaos", 0.5))

# ─── Pan & Stereo ───

class PanDialog(_Base):
    """Pan with a rotary knob + mono checkbox."""
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Pan."""
        super().__init__("Pan / Stereo", p)
        self._lo.addWidget(QLabel("Turn the knob to pan L ↔ R"))

        # Dial (knob) — properly centered with L / R labels
        dial_row = QHBoxLayout()
        dial_row.addStretch()

        lbl_l = QLabel("L")
        lbl_l.setStyleSheet(f"color: {COLORS['text_dim']}; font-weight: bold; font-size: 14px;")
        lbl_l.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        lbl_l.setFixedWidth(20)
        dial_row.addWidget(lbl_l)
        dial_row.addSpacing(8)

        self.dial = QDial()
        self.dial.setRange(-100, 100); self.dial.setValue(0)
        self.dial.setFixedSize(72, 72)
        self.dial.setNotchesVisible(True)
        self.dial.setWrapping(False)
        self.dial.setStyleSheet(f"""
            QDial {{
                background: {COLORS['bg_dark']};
                border: 2px solid {COLORS['border']};
                border-radius: 36px;
            }}
        """)
        dial_row.addWidget(self.dial)

        dial_row.addSpacing(8)
        lbl_r = QLabel("R")
        lbl_r.setStyleSheet(f"color: {COLORS['text_dim']}; font-weight: bold; font-size: 14px;")
        lbl_r.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        lbl_r.setFixedWidth(20)
        dial_row.addWidget(lbl_r)
        dial_row.addStretch()
        self._lo.addLayout(dial_row)

        # Value display + slider
        self.pan_sb = _slider_float(self._lo, "Pan value (-1.0 L ... +1.0 R)", -1, 1, 0, 0.05, 2, "", 100)
        # Sync dial <-> spinbox
        self.dial.valueChanged.connect(lambda v: self.pan_sb.setValue(v / 100))
        self.pan_sb.valueChanged.connect(lambda v: self.dial.setValue(int(v * 100)))

        self._lo.addSpacing(8)
        self.mono = QCheckBox("Convert to Mono (same on both sides)")
        self._lo.addWidget(self.mono)
        self._finish()

    def get_params(self):
        """Retourne les parametres actuels sous forme de dict."""
        return {"pan": self.pan_sb.value(), "mono": self.mono.isChecked()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.pan_sb.setValue(p.get("pan", 0))
        self.dial.setValue(int(p.get("pan", 0) * 100))
        self.mono.setChecked(p.get("mono", False))


# ─── New: Pitch & Time ───

class WaveOnduleeDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour WaveOndulee."""
        super().__init__("Pitch Drift", p)
        self.sp = _slider_float(self._lo, "Speed (Hz)", 0.1, 15.0, 3.0, 0.1, 1, " Hz", 10)
        self.pd = _slider_float(self._lo, "Pitch depth", 0.0, 1.0, 0.4, 0.05, 2)
        self.vd = _slider_float(self._lo, "Volume depth", 0.0, 1.0, 0.3, 0.05, 2)
        self.st = QCheckBox("Stereo offset"); self.st.setChecked(True); self._lo.addWidget(self.st)
        self._finish()
    def get_params(self):
        """Retourne les parametres actuels sous forme de dict."""
        return {"speed": self.sp.value(), "pitch_depth": self.pd.value(),
                "vol_depth": self.vd.value(), "stereo_offset": self.st.isChecked()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.sp.setValue(p.get("speed", 3.0)); self.pd.setValue(p.get("pitch_depth", 0.4))
        self.vd.setValue(p.get("vol_depth", 0.3)); self.st.setChecked(p.get("stereo_offset", True))

class AutotuneDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Autotune."""
        super().__init__("Autotune", p)
        self.sp = _slider_float(self._lo, "Speed (0=soft, 1=hard T-Pain)", 0.0, 1.0, 0.8, 0.05, 2)
        self._row("Key")
        self.key = QComboBox()
        self.key.addItems(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])
        self._lo.addWidget(self.key)
        self._row("Scale")
        self.scale = QComboBox()
        self.scale.addItems(["chromatic", "major", "minor", "pentatonic", "blues", "dorian", "mixolydian"])
        self._lo.addWidget(self.scale)
        self.mx = _slider_float(self._lo, "Mix", 0.0, 1.0, 1.0, 0.05, 2)
        self._finish()
    def get_params(self):
        """Retourne les parametres actuels sous forme de dict."""
        return {"speed": self.sp.value(), "key": self.key.currentText(),
                "scale": self.scale.currentText(), "mix": self.mx.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.sp.setValue(p.get("speed", 0.8))
        idx = self.key.findText(p.get("key", "C"))
        if idx >= 0: self.key.setCurrentIndex(idx)
        idx = self.scale.findText(p.get("scale", "chromatic"))
        if idx >= 0: self.scale.setCurrentIndex(idx)
        self.mx.setValue(p.get("mix", 1.0))


# ─── New: Space & Texture ───

class RobotDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Robot."""
        super().__init__("Robotic Voice", p)
        self.gr = _slider_int(self._lo, "Grain size (ms)", 3, 50, 8, " ms")
        self.am = _slider_float(self._lo, "Robot amount", 0.0, 1.0, 0.7, 0.05, 2)
        self.mt = _slider_float(self._lo, "Metallic", 0.0, 1.0, 0.4, 0.05, 2)
        self.dn = _slider_float(self._lo, "Digital noise", 0.0, 1.0, 0.15, 0.05, 2)
        self.mo = _slider_float(self._lo, "Monotone", 0.0, 1.0, 0.0, 0.05, 2)
        self.ph = _slider_int(self._lo, "Pitch (Hz, for monotone)", 50, 500, 150, " Hz")
        self._finish()
    def get_params(self):
        """Retourne les parametres actuels sous forme de dict."""
        return {"grain_ms": self.gr.value(), "robot_amount": self.am.value(),
                "metallic": self.mt.value(), "digital_noise": self.dn.value(),
                "monotone": self.mo.value(), "pitch_hz": self.ph.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.gr.setValue(p.get("grain_ms", 8)); self.am.setValue(p.get("robot_amount", 0.7))
        self.mt.setValue(p.get("metallic", 0.4)); self.dn.setValue(p.get("digital_noise", 0.15))
        self.mo.setValue(p.get("monotone", 0.0)); self.ph.setValue(p.get("pitch_hz", 150))

class HyperDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour Hyper."""
        super().__init__("Hyper", p)
        self._lo.addWidget(QLabel("One-knob hyperpop processor"))
        self.it = _slider_float(self._lo, "Intensity", 0.0, 1.0, 0.6, 0.05, 2)
        self.sh = _slider_float(self._lo, "Shimmer (octave up)", 0.0, 1.0, 0.3, 0.05, 2)
        self.br = _slider_float(self._lo, "Brightness", 0.0, 1.0, 0.5, 0.05, 2)
        self.cr = _slider_float(self._lo, "Digital crush", 0.0, 1.0, 0.0, 0.05, 2)
        self.wd = _slider_float(self._lo, "Stereo width", 0.0, 1.0, 0.5, 0.05, 2)
        self._finish()
    def get_params(self):
        """Retourne les parametres actuels sous forme de dict."""
        return {"intensity": self.it.value(), "shimmer": self.sh.value(),
                "brightness": self.br.value(), "crush": self.cr.value(), "width": self.wd.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.it.setValue(p.get("intensity", 0.6)); self.sh.setValue(p.get("shimmer", 0.3))
        self.br.setValue(p.get("brightness", 0.5)); self.cr.setValue(p.get("crush", 0.0))
        self.wd.setValue(p.get("width", 0.5))


# ─── New: Glitch ───

class VocalChopDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour VocalChop."""
        super().__init__("Vocal Chop", p)
        self.bpm = _slider_int(self._lo, "BPM", 60, 220, 140, " bpm")
        self._row("Pattern")
        self.pat = QComboBox()
        self.pat.addItems(["straight", "dotted", "triplet", "glitch", "staccato",
                           "syncopated", "chaos", "rapid"])
        self.pat.setCurrentText("glitch")
        self._lo.addWidget(self.pat)
        self.gs = _slider_float(self._lo, "Gate shape", 0.1, 1.0, 0.8, 0.05, 2)
        self.pv = _slider_float(self._lo, "Pitch variation", 0.0, 1.0, 0.0, 0.05, 2)
        self.rv = QCheckBox("Reverse every other hit"); self._lo.addWidget(self.rv)
        self._finish()
    def get_params(self):
        """Retourne les parametres actuels sous forme de dict."""
        return {"bpm": self.bpm.value(), "pattern": self.pat.currentText(),
                "gate_shape": self.gs.value(), "pitch_variation": self.pv.value(),
                "reverse_hits": self.rv.isChecked()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.bpm.setValue(p.get("bpm", 140))
        idx = self.pat.findText(p.get("pattern", "glitch"))
        if idx >= 0: self.pat.setCurrentIndex(idx)
        self.gs.setValue(p.get("gate_shape", 0.8)); self.pv.setValue(p.get("pitch_variation", 0.0))
        self.rv.setChecked(p.get("reverse_hits", False))

class TapeGlitchDialog(_Base):
    def __init__(self, p=None):
        """Initialise les sliders de parametres pour TapeGlitch."""
        super().__init__("Tape Glitch", p)
        self.gr = _slider_float(self._lo, "Glitch rate", 0.0, 1.0, 0.4, 0.05, 2)
        self.dr = _slider_float(self._lo, "Dropout chance", 0.0, 1.0, 0.15, 0.05, 2)
        self.wo = _slider_float(self._lo, "Wow (slow wobble)", 0.0, 1.0, 0.3, 0.05, 2)
        self.fl = _slider_float(self._lo, "Flutter (fast)", 0.0, 1.0, 0.4, 0.05, 2)
        self.ns = _slider_float(self._lo, "Tape hiss", 0.0, 1.0, 0.1, 0.05, 2)
        self._finish()
    def get_params(self):
        """Retourne les parametres actuels sous forme de dict."""
        return {"glitch_rate": self.gr.value(), "dropout_chance": self.dr.value(),
                "wow": self.wo.value(), "flutter": self.fl.value(), "noise": self.ns.value()}
    def set_params(self, p):
        """Charge les parametres depuis un dict."""
        self.gr.setValue(p.get("glitch_rate", 0.4)); self.dr.setValue(p.get("dropout_chance", 0.15))
        self.wo.setValue(p.get("wow", 0.3)); self.fl.setValue(p.get("flutter", 0.4))
        self.ns.setValue(p.get("noise", 0.1))
