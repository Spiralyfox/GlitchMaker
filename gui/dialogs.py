"""Record and About dialogs."""
import numpy as np, sounddevice as sd, math, threading
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QWidget, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor, QBrush, QPen, QLinearGradient, QPainterPath
from utils.config import COLORS, RECORDING_SAMPLE_RATE, RECORDING_CHANNELS, APP_NAME, APP_VERSION
from utils.translator import t


class _WaveVisualizer(QWidget):
    """Smooth animated wave that responds to audio level."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self._level = 0.0
        self._smooth_level = 0.0
        self._phase = 0.0
        self._active = False
        self._history = [0.0] * 8

    def set_level(self, val: float):
        raw = max(0.0, min(1.0, val))
        boosted = min(1.0, raw * 2.5) if raw < 0.4 else raw
        self._history.pop(0)
        self._history.append(boosted)
        self._level = max(self._history)
        self._active = True
        self._phase += 0.12
        target = self._level
        if target > self._smooth_level:
            self._smooth_level = self._smooth_level * 0.2 + target * 0.8
        else:
            self._smooth_level = self._smooth_level * 0.85 + target * 0.15
        self.update()

    def set_idle_animate(self, active: bool):
        """Idle breathing animation when playing back."""
        self._active = active
        if not active:
            self._smooth_level = 0.0
            self._level = 0.0
            self._history = [0.0] * 8

    def advance_idle(self):
        """Tick for idle/playback animation."""
        self._phase += 0.08
        self.update()

    def reset(self):
        self._level = 0.0
        self._smooth_level = 0.0
        self._active = False
        self._history = [0.0] * 8
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2.0

        # Background
        p.fillRect(0, 0, w, h, QColor(COLORS['bg_medium']))

        if not self._active and self._smooth_level < 0.01:
            # Flat line when idle
            p.setPen(QPen(QColor(COLORS['text_dim']), 1.5))
            p.drawLine(8, int(cy), w - 8, int(cy))
            p.end()
            return

        amp = max(0.08, self._smooth_level) if self._active else 0.0
        # Draw multiple layered waves
        layers = [
            (1.0, 0.08, COLORS['accent'], 160),
            (1.8, 0.05, COLORS['accent'], 90),
            (0.6, 0.12, COLORS['recording'], 70),
        ]
        for freq_mult, speed_mult, color_hex, alpha in layers:
            path = QPainterPath()
            points = []
            n_pts = w
            for xi in range(n_pts):
                x = xi
                nx = xi / float(w)
                # Envelope: fade edges
                env = math.sin(nx * math.pi) ** 0.6
                # Composite wave
                y1 = math.sin(self._phase * (2.0 + speed_mult * 10) + nx * 6.0 * freq_mult)
                y2 = math.sin(self._phase * (3.0 + speed_mult * 8) + nx * 10.0 * freq_mult + 1.5) * 0.4
                y3 = math.sin(self._phase * (1.5 + speed_mult * 6) + nx * 3.5 * freq_mult + 3.0) * 0.25
                val = (y1 + y2 + y3) / 1.65
                y = cy + val * amp * (h * 0.42) * env
                points.append((x, y))
            path.moveTo(points[0][0], points[0][1])
            for x, y in points[1:]:
                path.lineTo(x, y)
            ch = color_hex.lstrip('#')
            cr, cg, cb = int(ch[0:2], 16), int(ch[2:4], 16), int(ch[4:6], 16)
            p.setPen(QPen(QColor(cr, cg, cb, alpha), 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # Glow on center line
        grad = QLinearGradient(0, cy - 2, 0, cy + 2)
        ac = COLORS['accent'].lstrip('#')
        ar, ag, ab = int(ac[0:2], 16), int(ac[2:4], 16), int(ac[4:6], 16)
        glow_alpha = int(40 + amp * 60)
        grad.setColorAt(0, QColor(ar, ag, ab, 0))
        grad.setColorAt(0.5, QColor(ar, ag, ab, glow_alpha))
        grad.setColorAt(1, QColor(ar, ag, ab, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawRect(0, int(cy - 3), w, 6)

        p.end()


class RecordDialog(QDialog):
    recording_done = pyqtSignal(np.ndarray, int)

    def __init__(self, input_device=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("record.title"))
        self.setFixedSize(480, 440)
        self.setStyleSheet(f"QDialog {{ background: {COLORS['bg_dark']}; }}")
        self._recording = False
        self._playing = False
        self._play_stream = None
        self._play_thread = None
        self._data = []
        self._stream = None
        self._level = 0.0
        self._input_device = input_device
        self._actual_sr = RECORDING_SAMPLE_RATE
        self._elapsed = 0.0
        self._blink_on = True

        lo = QVBoxLayout(self)
        lo.setSpacing(0)
        lo.setContentsMargins(0, 0, 0, 0)

        # ── Header ──
        hdr = QWidget()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(f"background: {COLORS['bg_medium']};")
        hl = QVBoxLayout(hdr)
        hl.setContentsMargins(24, 10, 24, 10)
        hl.setSpacing(2)
        lbl_title = QLabel(t("record.title"))
        lbl_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl_title.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        hl.addWidget(lbl_title)
        lbl_sub = QLabel(t("record.subtitle"))
        lbl_sub.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; background: transparent;")
        hl.addWidget(lbl_sub)
        lo.addWidget(hdr)

        # ── Body ──
        body = QWidget()
        body.setStyleSheet(f"background: {COLORS['bg_dark']};")
        blo = QVBoxLayout(body)
        blo.setContentsMargins(28, 16, 28, 16)
        blo.setSpacing(12)

        # Status + timer row
        srow = QHBoxLayout()
        srow.setSpacing(8)
        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        self._dot.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px; background: transparent;")
        srow.addWidget(self._dot)
        self._lbl_status = QLabel(t("record.idle"))
        self._lbl_status.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px; background: transparent;")
        srow.addWidget(self._lbl_status)
        srow.addStretch()
        self._lbl_timer = QLabel("00:00.0")
        self._lbl_timer.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
        self._lbl_timer.setStyleSheet(f"color: {COLORS['text']}; background: transparent;")
        srow.addWidget(self._lbl_timer)
        blo.addLayout(srow)

        # Wave visualizer
        self._wave = _WaveVisualizer()
        self._wave.setStyleSheet(f"border-radius: 8px;")
        blo.addWidget(self._wave)

        blo.addSpacing(6)

        # ── Row 1: Record + Listen ──
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        self._btn_rec = QPushButton(t("record.start"))
        self._btn_rec.setFixedHeight(44)
        self._btn_rec.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_rec.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._btn_rec.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._set_rec_style_idle()
        self._btn_rec.clicked.connect(self._toggle)
        row1.addWidget(self._btn_rec, 3)

        self._btn_play = QPushButton(t("record.listen"))
        self._btn_play.setFixedHeight(44)
        self._btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_play.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._btn_play.setEnabled(False)
        self._btn_play.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._set_play_style_idle()
        self._btn_play.clicked.connect(self._toggle_play)
        row1.addWidget(self._btn_play, 2)

        blo.addLayout(row1)

        # ── Row 2: Add to timeline (full width) ──
        self._btn_done = QPushButton(t("record.use"))
        self._btn_done.setFixedHeight(44)
        self._btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_done.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._btn_done.setEnabled(False)
        self._btn_done.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']}; color: white;
                border: none; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {COLORS['accent_hover']}; }}
            QPushButton:disabled {{
                background: {COLORS['button_bg']}; color: {COLORS['text_dim']};
            }}
        """)
        self._btn_done.clicked.connect(self._finish)
        blo.addWidget(self._btn_done)

        # Cancel
        btn_cancel = QPushButton(t("dialog.cancel"))
        btn_cancel.setFixedHeight(28)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLORS['text_dim']};
                border: none; font-size: 11px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        blo.addWidget(btn_cancel, alignment=Qt.AlignmentFlag.AlignCenter)

        lo.addWidget(body)

        # Timers
        self._timer = QTimer()
        self._timer.timeout.connect(self._upd)
        self._timer.setInterval(40)
        self._blink_timer = QTimer()
        self._blink_timer.timeout.connect(self._blink)
        self._blink_timer.setInterval(500)
        self._play_anim_timer = QTimer()
        self._play_anim_timer.timeout.connect(self._play_anim_tick)
        self._play_anim_timer.setInterval(40)

    # ── Styles ──

    def _set_rec_style_idle(self):
        self._btn_rec.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['recording']}; color: white;
                border: none; border-radius: 8px;
            }}
            QPushButton:hover {{ background: #ff5566; }}
        """)

    def _set_rec_style_active(self):
        self._btn_rec.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_medium']}; color: {COLORS['recording']};
                border: 2px solid {COLORS['recording']}; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {COLORS['bg_dark']}; }}
        """)

    def _set_play_style_idle(self):
        self._btn_play.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['button_bg']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 8px;
            }}
            QPushButton:hover {{
                background: {COLORS['button_hover']}; border-color: {COLORS['accent']};
            }}
            QPushButton:disabled {{
                background: {COLORS['button_bg']}; color: {COLORS['text_dim']};
                border-color: {COLORS['border']};
            }}
        """)

    def _set_play_style_active(self):
        self._btn_play.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['bg_medium']}; color: {COLORS['accent']};
                border: 2px solid {COLORS['accent']}; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {COLORS['bg_dark']}; }}
        """)

    # ── Recording ──

    def _toggle(self):
        if not self._recording:
            self._start()
        else:
            self._stop_rec()

    def _start(self):
        self._stop_play()
        self._data.clear()
        self._recording = True
        self._elapsed = 0.0
        self._actual_sr = RECORDING_SAMPLE_RATE
        self._btn_rec.setText(t("record.stop"))
        self._set_rec_style_active()
        self._lbl_status.setText(t("record.recording"))
        self._lbl_status.setStyleSheet(
            f"color: {COLORS['recording']}; font-size: 12px; background: transparent;")
        self._dot.setText("●")
        self._dot.setStyleSheet(
            f"color: {COLORS['recording']}; font-size: 11px; background: transparent;")
        self._btn_done.setEnabled(False)
        self._btn_play.setEnabled(False)
        self._blink_timer.start()
        try:
            self._stream = sd.InputStream(
                samplerate=RECORDING_SAMPLE_RATE, channels=RECORDING_CHANNELS,
                dtype="float32", callback=self._cb, blocksize=1024,
                device=self._input_device)
            self._actual_sr = int(self._stream.samplerate)
            self._stream.start()
            self._timer.start()
        except Exception as e:
            self._lbl_status.setText(f"Error : {e}")
            self._recording = False
            self._blink_timer.stop()

    def _stop_rec(self):
        self._recording = False
        self._timer.stop()
        self._blink_timer.stop()
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._btn_rec.setText(t("record.start"))
        self._set_rec_style_idle()
        self._lbl_status.setText(t("record.done"))
        self._lbl_status.setStyleSheet(
            f"color: #00b894; font-size: 12px; background: transparent;")
        self._dot.setText("✓")
        self._dot.setStyleSheet(
            f"color: #00b894; font-size: 11px; background: transparent;")
        has_data = len(self._data) > 0
        self._btn_done.setEnabled(has_data)
        self._btn_play.setEnabled(has_data)
        self._wave.reset()

    def _cb(self, indata, frames, ti, status):
        if self._recording:
            self._data.append(indata.copy())
            self._level = float(np.max(np.abs(indata)))

    def _upd(self):
        self._wave.set_level(self._level)
        self._elapsed += 0.04
        m = int(self._elapsed // 60)
        s = self._elapsed % 60
        self._lbl_timer.setText(f"{m:02d}:{s:04.1f}")

    def _blink(self):
        self._blink_on = not self._blink_on
        col = COLORS['recording'] if self._blink_on else "transparent"
        self._dot.setStyleSheet(
            f"color: {col}; font-size: 11px; background: transparent;")

    # ── Playback ──

    def _toggle_play(self):
        if self._playing:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self):
        if not self._data:
            return
        self._stop_play()
        audio = np.concatenate(self._data, axis=0)
        self._playing = True
        self._btn_play.setText(t("record.stop_listen"))
        self._set_play_style_active()
        # Visual: show playback state
        self._lbl_status.setText(t("record.listening"))
        self._lbl_status.setStyleSheet(
            f"color: {COLORS['accent']}; font-size: 12px; background: transparent;")
        self._dot.setText("●")
        self._dot.setStyleSheet(
            f"color: {COLORS['accent']}; font-size: 11px; background: transparent;")
        # Animate wave during playback
        self._wave.set_idle_animate(True)
        self._wave._smooth_level = 0.4
        self._play_anim_timer.start()
        self._play_blink_on = True
        try:
            ch = audio.shape[1] if audio.ndim > 1 else 1
            self._play_stream = sd.OutputStream(
                samplerate=self._actual_sr, channels=ch, dtype="float32")
            self._play_stream.start()
            # Play in a thread to avoid blocking
            self._play_thread = threading.Thread(
                target=self._play_worker, args=(audio,), daemon=True)
            self._play_thread.start()
        except Exception:
            self._playing = False
            self._btn_play.setText(t("record.listen"))
            self._set_play_style_idle()
            self._play_anim_timer.stop()
            self._wave.set_idle_animate(False)

    def _play_worker(self, audio):
        """Write audio to output stream in a background thread."""
        try:
            if self._play_stream is not None:
                self._play_stream.write(audio)
        except Exception:
            pass
        # Signal end on main thread
        QTimer.singleShot(0, self._on_play_done)

    def _play_anim_tick(self):
        """Animate wave and blink dot during playback."""
        if self._playing:
            self._wave._smooth_level = 0.3 + 0.15 * math.sin(self._wave._phase * 0.7)
            self._wave.advance_idle()
            # Blink the dot
            self._play_blink_on = not getattr(self, '_play_blink_on', True)
            col = COLORS['accent'] if self._play_blink_on else "transparent"
            self._dot.setStyleSheet(
                f"color: {col}; font-size: 11px; background: transparent;")

    def _stop_play(self):
        was_playing = self._playing
        self._playing = False
        self._play_anim_timer.stop()
        if self._play_stream is not None:
            try:
                self._play_stream.stop()
                self._play_stream.close()
            except Exception:
                pass
            self._play_stream = None
        self._play_thread = None
        self._btn_play.setText(t("record.listen"))
        self._set_play_style_idle()
        self._wave.set_idle_animate(False)
        self._wave.reset()
        # Restore status to "done" if we were playing
        if was_playing and self._data:
            self._lbl_status.setText(t("record.done"))
            self._lbl_status.setStyleSheet(
                f"color: #00b894; font-size: 12px; background: transparent;")
            self._dot.setText("✓")
            self._dot.setStyleSheet(
                f"color: #00b894; font-size: 11px; background: transparent;")

    def _on_play_done(self):
        if not self._playing:
            return
        self._stop_play()

    def _finish(self):
        self._stop_play()
        if self._data:
            self.recording_done.emit(
                np.concatenate(self._data, axis=0), self._actual_sr)
        self.accept()

    def closeEvent(self, e):
        self._stop_play()
        if self._recording:
            self._stop_rec()
        e.accept()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("about.title").format(name=APP_NAME)); self.setFixedSize(400, 380)
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
        gh_url = "https://github.com/Spiralyfox/GlitchMaker"
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

        issue_url = "https://github.com/Spiralyfox/GlitchMaker/issues"
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




# ═══════════════════════════════════════════
# FadeDialog — DAW-style envelope on waveform
# ═══════════════════════════════════════════

from PyQt6.QtWidgets import QSlider, QSpinBox, QSizePolicy
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush, QPixmap
from core.playback import PlaybackEngine


class _FadeEnvelopeEditor(QWidget):
    """Waveform + envelope editor with Points / Bend modes.

    Envelope value v ∈ [0,1].
      top-half Y = mid_y - v * scale
      bot-half Y = mid_y + v * scale
    Both halves respond to clicks. Bends are clamped to [0,1].
    """
    curve_changed = pyqtSignal()
    MODE_POINTS = 0
    MODE_BEND = 1
    PAD = 6
    PAD_B = 16

    def __init__(self, fade_type="in", parent=None):
        super().__init__(parent)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._ft = fade_type
        self._audio: np.ndarray | None = None
        self._sr = 44100
        self._dur_ms = 500
        self._mode = self.MODE_POINTS

        if fade_type == "in":
            self._pts: list[list[float]] = [[0.0, 0.0], [1.0, 1.0]]
        else:
            self._pts = [[0.0, 1.0], [1.0, 0.0]]
        self._bends: list[float] = [0.0]

        self._drag = None
        self._hover_pt: int | None = None
        self._play_pos = -1.0

        # Performance caches
        self._pk_hi: np.ndarray | None = None
        self._pk_lo: np.ndarray | None = None
        self._pk_aw = 0
        self._bg_pm: QPixmap | None = None
        self._bg_key = None

        self.setMouseTracking(True)

    # ── public API ──

    def set_mode(self, m):
        self._mode = m; self._drag = None; self._hover_pt = None
        self.setCursor(Qt.CursorShape.CrossCursor if m == self.MODE_POINTS
                       else Qt.CursorShape.SizeVerCursor)
        self.update()

    def set_audio(self, audio, sr):
        self._audio = audio; self._sr = sr
        self._pk_hi = self._pk_lo = None; self._pk_aw = 0
        self._bg_pm = None; self.update()

    def set_dur_ms(self, ms):
        self._dur_ms = ms; self._bg_pm = None; self.update()

    def set_play_pos(self, p):
        if self._play_pos != p:
            self._play_pos = p; self.update()

    def get_points(self):
        return sorted([tuple(p) for p in self._pts], key=lambda p: p[0])

    def get_bends(self):
        return list(self._bends)

    def set_state(self, points, bends):
        self._pts = [list(p) for p in points] if points else [[0.0, 0.0], [1.0, 1.0]]
        self._bends = list(bends) if bends else [0.0] * max(0, len(self._pts) - 1)
        self._sync_bends(); self._bg_pm = None; self.update()

    def make_curve(self, n):
        from core.effects.utils import make_envelope_curve
        return make_envelope_curve(n, self.get_points(), self._bends)

    # ── internal geometry ──

    def _sync_bends(self):
        need = max(0, len(self._pts) - 1)
        while len(self._bends) < need: self._bends.append(0.0)
        while len(self._bends) > need: self._bends.pop()

    def _L(self):
        P = self.PAD
        ax, ay = P, P
        aw = self.width() - 2 * P
        ah = self.height() - P - self.PAD_B
        return ax, ay, aw, ah, ay + ah / 2, ah / 2 * 0.90

    def _zone_px(self):
        ax, ay, aw, ah, _, _ = self._L()
        if self._audio is None:
            return ax, ax + aw
        n = self._audio.shape[0] if self._audio.ndim > 1 else len(self._audio)
        ds = min(max(1, int(self._dur_ms / 1000.0 * self._sr)), n)
        if self._ft == "in":
            return ax, ax + max(1, int(ds / n * aw))
        else:
            return ax + aw - max(1, int(ds / n * aw)), ax + aw

    def _n2s(self, nx, ny):
        _, _, _, _, mid_y, scale = self._L()
        zx0, zx1 = self._zone_px()
        return zx0 + nx * max(1, zx1 - zx0), mid_y - ny * scale

    def _s2n(self, sx, sy):
        _, _, _, _, mid_y, scale = self._L()
        zx0, zx1 = self._zone_px()
        zw = max(1, zx1 - zx0)
        return (max(0.0, min(1.0, (sx - zx0) / zw)),
                max(0.0, min(1.0, abs(mid_y - sy) / scale)))

    def _is_locked(self, idx):
        pos = self._sorted_pos(idx)
        return pos == 0 or pos == len(self._pts) - 1

    def _near_pt(self, px, py, rad=14):
        _, _, _, _, mid_y, scale = self._L()
        best, best_d = None, rad * rad
        for i, (x, y) in enumerate(self._pts):
            sx, sy_t = self._n2s(x, y)
            sy_b = mid_y + y * scale
            d = min((px - sx)**2 + (py - sy_t)**2,
                    (px - sx)**2 + (py - sy_b)**2)
            if d < best_d:
                best_d = d; best = i
        return best

    def _near_seg(self, px, py, rad=18):
        pts = sorted(self._pts, key=lambda p: p[0])
        _, _, _, _, mid_y, scale = self._L()
        from core.effects.utils import _bezier_y
        for si in range(len(pts) - 1):
            x0, y0 = pts[si]; x1, y1 = pts[si + 1]
            sx0, _ = self._n2s(x0, y0); sx1, _ = self._n2s(x1, y1)
            if not (sx0 - 8 <= px <= sx1 + 8) or (sx1 - sx0) < 3:
                continue
            t = max(0.05, min(0.95, (px - sx0) / (sx1 - sx0)))
            bd = self._bends[si] if si < len(self._bends) else 0.0
            by = max(0.0, _bezier_y(y0, y1, bd, t))
            sy_t = mid_y - by * scale
            sy_b = mid_y + by * scale
            if abs(py - sy_t) < rad or abs(py - sy_b) < rad:
                return si, t
        return None

    def _sorted_pos(self, idx):
        order = sorted(range(len(self._pts)), key=lambda i: self._pts[i][0])
        return order.index(idx)

    def _clamp_bend(self, si, bend):
        pts = sorted(self._pts, key=lambda p: p[0])
        if si + 1 >= len(pts):
            return max(-0.5, min(0.5, bend))
        y0, y1 = pts[si][1], pts[si + 1][1]
        mid = (y0 + y1) / 2.0
        return max(-mid, min(1.0 - mid, bend))

    # ── mouse — POINTS ──

    def _press_pts(self, px, py, btn):
        if btn == Qt.MouseButton.LeftButton:
            pi = self._near_pt(px, py)
            if pi is not None:
                self._drag = ('pt', pi); return
            zx0, zx1 = self._zone_px()
            if not (zx0 - 5 <= px <= zx1 + 5): return
            nx, ny = self._s2n(px, py)
            if nx < 0.01 or nx > 0.99: return
            spts = sorted(self._pts, key=lambda p: p[0])
            seg = 0
            for i in range(len(spts) - 1):
                if spts[i][0] <= nx <= spts[i + 1][0]:
                    seg = i; break
            self._pts.append([nx, ny])
            self._pts.sort(key=lambda p: p[0])
            self._bends[seg:seg + 1] = [0.0, 0.0]
            self._sync_bends()
            ni = next(i for i, p in enumerate(self._pts) if p == [nx, ny])
            self._drag = ('pt', ni)
            self._bg_pm = None
            self.curve_changed.emit(); self.update()
        elif btn == Qt.MouseButton.RightButton:
            self._try_delete(px, py)

    def _move_pts(self, px, py):
        if self._drag and self._drag[0] == 'pt':
            idx = self._drag[1]
            if self._is_locked(idx): return
            nx, ny = self._s2n(px, py)
            self._pts[idx] = [nx, ny]
            self._bg_pm = None; self.update()
        else:
            old = self._hover_pt
            self._hover_pt = self._near_pt(px, py)
            if self._hover_pt != old: self.update()

    def _release_pts(self):
        if self._drag and self._drag[0] == 'pt':
            self._pts.sort(key=lambda p: p[0]); self._sync_bends()
            self._drag = None; self._bg_pm = None
            self.curve_changed.emit(); self.update()

    # ── mouse — BEND ──

    def _press_bend(self, px, py, btn):
        if btn != Qt.MouseButton.LeftButton: return
        seg = self._near_seg(px, py, 22)
        if seg is None: return
        si, t0 = seg
        pts = sorted(self._pts, key=lambda p: p[0])
        y0, y1 = pts[si][1], pts[si + 1][1]
        self._drag = ('bend', si, t0, y0 + t0 * (y1 - y0))

    def _move_bend(self, px, py):
        if not (self._drag and self._drag[0] == 'bend'): return
        si, t0, sy0 = self._drag[1], self._drag[2], self._drag[3]
        _, ny = self._s2n(px, py)
        denom = 2.0 * t0 * (1.0 - t0)
        if abs(denom) < 0.01: return
        self._bends[si] = self._clamp_bend(si, (ny - sy0) / denom)
        self._bg_pm = None; self.update()

    def _release_bend(self):
        if self._drag and self._drag[0] == 'bend':
            self._drag = None; self._bg_pm = None
            self.curve_changed.emit(); self.update()

    # ── delete (Points mode only) ──

    def _try_delete(self, px, py):
        if len(self._pts) <= 2: return
        pi = self._near_pt(px, py, 16)
        if pi is None or self._is_locked(pi): return
        pos = self._sorted_pos(pi)
        if 0 < pos <= len(self._bends):
            self._bends[pos - 1:pos + 1] = [0.0]
        self._pts.pop(pi); self._sync_bends()
        self._bg_pm = None
        self.curve_changed.emit(); self.update()

    # ── mouse dispatch ──

    def mousePressEvent(self, e):
        px, py = e.position().x(), e.position().y()
        if self._mode == self.MODE_POINTS:
            self._press_pts(px, py, e.button())
        else:
            self._press_bend(px, py, e.button())

    def mouseMoveEvent(self, e):
        px, py = e.position().x(), e.position().y()
        if self._mode == self.MODE_POINTS:
            self._move_pts(px, py)
        else:
            self._move_bend(px, py)

    def mouseReleaseEvent(self, e):
        if self._mode == self.MODE_POINTS:
            self._release_pts()
        else:
            self._release_bend()

    # ── peak cache (vectorized) ──

    def _ensure_peaks(self, aw):
        if self._pk_hi is not None and self._pk_aw == aw:
            return
        if self._audio is None or aw < 2:
            self._pk_hi = self._pk_lo = None; return
        mono = self._audio.mean(axis=1) if self._audio.ndim > 1 else self._audio
        n = len(mono)
        idx = np.linspace(0, n, aw + 1, dtype=np.int64)
        hi = np.empty(aw, dtype=np.float32)
        lo = np.empty(aw, dtype=np.float32)
        for x in range(aw):
            s = mono[idx[x]:idx[x + 1]]
            if len(s) == 0:
                hi[x] = lo[x] = 0.0
            else:
                hi[x] = s.max(); lo[x] = s.min()
        self._pk_hi, self._pk_lo, self._pk_aw = hi, lo, aw

    # ── painting ──

    def _build_env_path(self, pts, mid_y, scale, sign):
        ax, _, aw, _, _, _ = self._L()
        zx0, zx1 = self._zone_px(); zw = max(1, zx1 - zx0)
        path = QPainterPath()
        first_v = pts[0][1]
        pre_v = first_v if self._ft == "in" else 1.0
        path.moveTo(ax, mid_y + sign * pre_v * scale)
        if self._ft == "out":
            path.lineTo(zx0, mid_y + sign * first_v * scale)
        for si in range(len(pts) - 1):
            x0, y0 = pts[si]; x1, y1 = pts[si + 1]
            sxe = zx0 + x1 * zw; sye = mid_y + sign * y1 * scale
            bd = self._bends[si] if si < len(self._bends) else 0.0
            if abs(bd) < 0.005:
                path.lineTo(sxe, sye)
            else:
                cx = (x0 + x1) / 2
                cy = max(0.0, min(1.0, (y0 + y1) / 2 + bd))
                path.quadTo(zx0 + cx * zw, mid_y + sign * cy * scale, sxe, sye)
        if self._ft == "in":
            path.lineTo(ax + aw, mid_y + sign * 1.0 * scale)
        return path

    def _mk_key(self, aw, ah):
        ph = tuple(tuple(p) for p in sorted(self._pts, key=lambda p: p[0]))
        return (aw, ah, self._dur_ms, ph, tuple(round(b, 4) for b in self._bends))

    def _render_bg(self):
        """Background pixmap : waveform + envelope + labels (cached)."""
        ax, ay, aw, ah, mid_y, scale = self._L()
        w, h = self.width(), self.height()
        pm = QPixmap(w, h); pm.fill(QColor(COLORS['bg_dark']))
        p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)

        pts = sorted(self._pts, key=lambda pt: pt[0])
        has_audio = self._audio is not None and aw > 2

        if has_audio:
            self._ensure_peaks(aw)
            if self._pk_hi is None:
                has_audio = False

        if has_audio:
            n = self._audio.shape[0] if self._audio.ndim > 1 else len(self._audio)
            ds = min(max(1, int(self._dur_ms / 1000.0 * self._sr)), n)
            env_curve = self.make_curve(ds)
            full_env = np.ones(n, dtype=np.float32)
            if self._ft == "in":
                full_env[:ds] = env_curve
            else:
                full_env[-ds:] = env_curve
            env_px = np.interp(np.linspace(0, n - 1, aw),
                               np.arange(n), full_env).astype(np.float32)

            # Ghost waveform (original)
            dim_c = QColor(COLORS['text_dim']); dim_c.setAlpha(40)
            p.setPen(QPen(dim_c, 1))
            for x in range(aw):
                p.drawLine(ax + x, int(mid_y - self._pk_hi[x] * scale),
                           ax + x, int(mid_y - self._pk_lo[x] * scale))

            # Faded waveform
            p.setPen(QPen(QColor("#9d6dff"), 1))
            for x in range(aw):
                ev = env_px[x]
                y1 = int(mid_y - self._pk_hi[x] * ev * scale)
                y2 = int(mid_y - self._pk_lo[x] * ev * scale)
                if y2 <= y1: y2 = y1 + 1
                p.drawLine(ax + x, y1, ax + x, y2)

        if len(pts) >= 2:
            top_path = self._build_env_path(pts, mid_y, scale, -1)
            bot_path = self._build_env_path(pts, mid_y, scale, +1)
            mask_c = QColor(COLORS['bg_dark']); mask_c.setAlpha(150)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(mask_c))
            tm = QPainterPath()
            tm.moveTo(ax, ay); tm.lineTo(ax + aw, ay)
            tm.connectPath(top_path.toReversed()); tm.closeSubpath()
            p.drawPath(tm)
            bm = QPainterPath(bot_path)
            bm.lineTo(ax + aw, ay + ah); bm.lineTo(ax, ay + ah); bm.closeSubpath()
            p.drawPath(bm)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#e94560"), 2.0))
            p.drawPath(top_path); p.drawPath(bot_path)
            if has_audio:
                zx0, zx1 = self._zone_px()
                bx = zx1 if self._ft == "in" else zx0
                p.setPen(QPen(QColor("#e9456050"), 1, Qt.PenStyle.DashLine))
                p.drawLine(int(bx), ay, int(bx), ay + ah)

        # Labels
        p.setPen(QColor(COLORS['text_dim']))
        fnt = p.font(); fnt.setPixelSize(9); p.setFont(fnt)
        if has_audio:
            n_t = self._audio.shape[0] if self._audio.ndim > 1 else len(self._audio)
            ds2 = min(max(1, int(self._dur_ms / 1000.0 * self._sr)), n_t)
            p.drawText(ax + 2, ay + ah + 12, f"Fade : {ds2 / self._sr:.2f}s")
            p.drawText(ax + aw - 66, ay + ah + 12, f"Total : {n_t / self._sr:.2f}s")
        p.end()
        return pm

    def paintEvent(self, e):
        ax, ay, aw, ah, mid_y, scale = self._L()
        key = self._mk_key(aw, ah)
        if self._bg_pm is None or self._bg_key != key:
            self._bg_pm = self._render_bg()
            self._bg_key = key

        p = QPainter(self)
        p.drawPixmap(0, 0, self._bg_pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Control points (live overlay)
        pts = sorted(self._pts, key=lambda pt: pt[0])
        zx0, zx1 = self._zone_px(); zw = max(1, zx1 - zx0)
        for i, (cx, cy) in enumerate(pts):
            sx = zx0 + cx * zw
            sy_t = mid_y - cy * scale; sy_b = mid_y + cy * scale
            locked = (i == 0 or i == len(pts) - 1)
            is_hl = (i == self._hover_pt) or (
                self._drag and self._drag[0] == 'pt'
                and self._drag[1] < len(self._pts)
                and i == self._sorted_pos(self._drag[1]))
            if locked:
                sz = 4
                col = QColor("#b8a9e8") if is_hl else QColor("#8b7dc8")
                p.setPen(QPen(QColor("#d4d0e8"), 1.2))
            else:
                sz = 7 if is_hl else 5
                col = QColor("#ff6b6b") if is_hl else QColor("#e94560")
                p.setPen(QPen(QColor("white"), 1.5))
            p.setBrush(QBrush(col))
            p.drawEllipse(QPointF(sx, sy_t), sz, sz)
            p.drawEllipse(QPointF(sx, sy_b), sz, sz)

        # Playback cursor
        if 0 <= self._play_pos <= 1:
            pp = ax + int(self._play_pos * aw)
            p.setPen(QPen(QColor("#00d2ff"), 2))
            p.drawLine(pp, ay, pp, ay + ah)

        # Mode hint
        fnt = p.font(); fnt.setPixelSize(8); p.setFont(fnt)
        hc = QColor(COLORS['text_dim']); hc.setAlpha(140); p.setPen(hc)
        txt = ("Clic = ajouter  |  Glisser = déplacer  |  Clic droit = supprimer"
               if self._mode == self.MODE_POINTS
               else "Glissez un segment pour le courber")
        p.drawText(QRectF(ax, ay + 2, aw, 12), Qt.AlignmentFlag.AlignCenter, txt)

        p.setPen(QPen(QColor(COLORS['border']), 1)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)
        p.end()


class FadeDialog(QDialog):
    """Fade In / Fade Out dialog with private PlaybackEngine."""

    def __init__(self, fade_type="in", clip_duration_ms=5000, parent=None,
                 clip_audio=None, sample_rate=44100, playback_engine=None,
                 existing_params=None):
        super().__init__(parent)
        self._fade_type = fade_type
        self._clip_dur_ms = max(clip_duration_ms, 100)
        self._clip_audio = clip_audio
        self._sample_rate = sample_rate
        # Private engine — isolated from the main playback
        self._pb = PlaybackEngine()
        # Inherit the output device from the main engine so preview plays on the right device
        self._main_pb = playback_engine
        if playback_engine is not None and playback_engine.output_device is not None:
            self._pb.output_device = playback_engine.output_device
        self._pb_ready = False
        self._is_playing = False
        title = f"Fade {'In' if fade_type == 'in' else 'Out'}"
        self.setWindowTitle(title)
        self.setFixedSize(520, 440)
        self.setStyleSheet(f"QDialog {{ background: {COLORS['bg_medium']}; }}")

        self.duration_ms = min(500, clip_duration_ms)
        if fade_type == "in":
            pts = [(0.0, 0.0), (1.0, 1.0)]
        else:
            pts = [(0.0, 1.0), (1.0, 0.0)]
        bends = [0.0]
        if existing_params:
            self.duration_ms = existing_params.get("duration_ms", self.duration_ms)
            pts = existing_params.get("points", pts)
            bends = existing_params.get("bends", bends)

        self._tick_tmr = QTimer(self)
        self._tick_tmr.timeout.connect(self._tick)
        self._build(pts, bends)

        # Pre-init the stream once so play is instant
        if self._clip_audio is not None:
            self._init_stream()

    def _init_stream(self):
        """Pre-create the audio stream so first play is instant."""
        try:
            audio = self._clip_audio
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            self._pb.load(audio.copy(), self._sample_rate)
            self._pb.stop()
            self._pb_ready = True
        except Exception:
            self._pb_ready = False

    def _build(self, pts, bends):
        C = COLORS
        lo = QVBoxLayout(self); lo.setSpacing(6); lo.setContentsMargins(14, 10, 14, 10)

        # ── Header : Title … [Points] [Bend] [Play] ──
        tr = QHBoxLayout(); tr.setSpacing(6)
        lbl = QLabel(self.windowTitle())
        lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C['accent']};")
        tr.addWidget(lbl); tr.addStretch()

        # Button styles — OFF state is clearly clickable (light text + border)
        self._css_on = (f"QPushButton {{ background: {C['accent']}; color: white;"
                        f" border: none; border-radius: 4px; font-size: 10px;"
                        f" font-weight: bold; padding: 4px 12px; }}")
        self._css_off = (f"QPushButton {{ background: {C['button_bg']}; color: #c0c0d8;"
                         f" border: 1px solid #4a4a6a; border-radius: 4px; font-size: 10px;"
                         f" padding: 4px 12px; }}"
                         f" QPushButton:hover {{ background: {C['accent_secondary']};"
                         f" color: white; border-color: {C['accent']}; }}")
        self._css_play = (f"QPushButton {{ background: #1e6b3a; color: #b0f0c0;"
                          f" border: 1px solid #2a8a4a; border-radius: 4px; font-size: 10px;"
                          f" font-weight: bold; padding: 4px 12px; }}"
                          f" QPushButton:hover {{ background: #28854a; color: white; }}")
        self._css_stop = (f"QPushButton {{ background: #8b2030; color: #ffb0b0;"
                          f" border: 1px solid #a03040; border-radius: 4px; font-size: 10px;"
                          f" font-weight: bold; padding: 4px 12px; }}"
                          f" QPushButton:hover {{ background: #a53040; color: white; }}")

        self._btn_pts = QPushButton("Points")
        self._btn_pts.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pts.setFixedHeight(26)
        self._btn_pts.clicked.connect(lambda: self._set_mode(0))
        tr.addWidget(self._btn_pts)

        self._btn_bend = QPushButton("Bend")
        self._btn_bend.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_bend.setFixedHeight(26)
        self._btn_bend.clicked.connect(lambda: self._set_mode(1))
        tr.addWidget(self._btn_bend)

        self._btn_play = QPushButton("Play")
        self._btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_play.setFixedHeight(26); self._btn_play.setFixedWidth(56)
        self._btn_play.clicked.connect(self._toggle)
        self._btn_play.setStyleSheet(self._css_play)
        tr.addWidget(self._btn_play)

        lo.addLayout(tr)

        # ── Editor ──
        self._editor = _FadeEnvelopeEditor(self._fade_type)
        if self._clip_audio is not None:
            self._editor.set_audio(self._clip_audio, self._sample_rate)
        self._editor.set_state(pts, bends)
        lo.addWidget(self._editor, stretch=1)

        # ── Duration ──
        css_sp = (f"QSpinBox {{ background: {C['bg_dark']}; color: {C['text']};"
                  f" border: 1px solid {C['border']}; border-radius: 4px;"
                  f" padding: 2px 6px; font-size: 11px; }}")
        css_sl = (f"QSlider::groove:horizontal {{ background: {C['bg_dark']}; height: 5px; border-radius: 2px; }}"
                  f" QSlider::handle:horizontal {{ background: {C['accent']}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}"
                  f" QSlider::sub-page:horizontal {{ background: {C['accent_secondary']}; border-radius: 2px; }}")
        mx = self._clip_dur_ms
        dr = QHBoxLayout()
        dl = QLabel("Duration"); dl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px;"); dl.setFixedWidth(60)
        dr.addWidget(dl)
        self._sl = QSlider(Qt.Orientation.Horizontal); self._sl.setRange(10, mx)
        self._sl.setValue(min(self.duration_ms, mx)); self._sl.setStyleSheet(css_sl)
        self._sl.valueChanged.connect(self._on_sl); dr.addWidget(self._sl, stretch=1)
        self._sp = QSpinBox(); self._sp.setRange(10, mx)
        self._sp.setValue(min(self.duration_ms, mx)); self._sp.setSuffix(" ms")
        self._sp.setStyleSheet(css_sp); self._sp.setFixedWidth(110)
        self._sp.valueChanged.connect(self._on_sp); dr.addWidget(self._sp)
        lo.addLayout(dr)

        ht = QLabel("Espace = lecture / stop")
        ht.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px;")
        ht.setAlignment(Qt.AlignmentFlag.AlignCenter); lo.addWidget(ht)

        # ── Bottom ──
        br = QHBoxLayout(); br.setSpacing(10)
        for txt, slot, bg in [("Cancel", self.reject, C['button_bg']),
                               ("Apply", self._apply, C['accent'])]:
            b = QPushButton(txt); b.setFixedHeight(34); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background: {bg}; color: white; border: none;"
                f" border-radius: 6px; font-weight: bold; font-size: 12px; padding: 0 24px; }}"
                f" QPushButton:hover {{ background: {C['accent_hover']}; }}")
            b.clicked.connect(slot); br.addWidget(b)
        lo.addLayout(br)
        self._set_mode(0); self._sync()

    def _set_mode(self, m):
        self._editor.set_mode(m)
        self._btn_pts.setStyleSheet(self._css_on if m == 0 else self._css_off)
        self._btn_bend.setStyleSheet(self._css_on if m == 1 else self._css_off)

    def _on_sl(self, v):
        self._sp.blockSignals(True); self._sp.setValue(v); self._sp.blockSignals(False); self._sync()

    def _on_sp(self, v):
        self._sl.blockSignals(True); self._sl.setValue(v); self._sl.blockSignals(False); self._sync()

    def _sync(self):
        self._editor.set_dur_ms(self._sp.value())

    # ── Playback (isolated private engine) ──

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space:
            e.accept(); self._toggle()
        else:
            super().keyPressEvent(e)

    def _toggle(self):
        if self._is_playing:
            self._stop_play()
        else:
            self._start_play()

    def _start_play(self):
        if self._clip_audio is None:
            return
        # Suspend the main playback engine to free the audio device
        if self._main_pb is not None:
            self._main_pb.suspend_stream()
        # Build faded audio
        from core.effects.utils import apply_envelope_fade
        ds = int(self._sp.value() / 1000.0 * self._sample_rate)
        src = self._clip_audio
        if src.dtype != np.float32:
            src = src.astype(np.float32)
        faded = apply_envelope_fade(src.copy(), ds,
                                    self._editor.get_points(),
                                    self._editor.get_bends(),
                                    self._fade_type)
        # Ensure stereo consistency
        if faded.ndim == 1:
            faded = faded.reshape(-1, 1)

        try:
            # Always reload to ensure stream is fresh and matches current audio
            self._pb.load(faded, self._sample_rate)
            self._pb.play()
            self._pb_ready = True
        except Exception:
            return

        self._is_playing = True
        self._btn_play.setText("Stop")
        self._btn_play.setStyleSheet(self._css_stop)
        self._tick_tmr.start(30)

    def _stop_play(self):
        try:
            self._pb.is_playing = False
            self._pb.position = 0
        except Exception:
            pass
        self._is_playing = False
        self._tick_tmr.stop()
        self._btn_play.setText("Play")
        self._btn_play.setStyleSheet(self._css_play)
        self._editor.set_play_pos(-1)
        # Resume the main playback engine
        if self._main_pb is not None:
            self._main_pb.resume_stream()

    def _tick(self):
        if self._pb.is_playing:
            ad = self._pb.audio_data
            if ad is not None:
                n = ad.shape[0] if ad.ndim > 1 else len(ad)
                self._editor.set_play_pos(self._pb.position / max(1, n))
        else:
            self._stop_play()

    def _cleanup_pb(self):
        try:
            self._pb.is_playing = False
            if self._pb._stream is not None:
                self._pb._stream.close()
                self._pb._stream = None
        except Exception:
            pass
        self._pb_ready = False
        # Resume the main playback engine
        if self._main_pb is not None:
            self._main_pb.resume_stream()

    def closeEvent(self, e):
        self._stop_play(); self._cleanup_pb(); super().closeEvent(e)

    def reject(self):
        self._stop_play(); self._cleanup_pb(); super().reject()

    def _apply(self):
        self._stop_play(); self._cleanup_pb()
        self.duration_ms = self._sp.value(); self.accept()

    def get_params(self):
        return {"duration_ms": self.duration_ms,
                "points": self._editor.get_points(),
                "bends": self._editor.get_bends()}
