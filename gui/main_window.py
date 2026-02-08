"""
Main window — Glitch Maker v3.10
Plugin-based effects, global effects system, metronome, beat grid.
"""

import os
import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QPushButton, QLabel, QApplication,
    QMenu, QSpinBox, QSlider, QDialog, QCheckBox, QScrollBar
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal as Signal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QShortcut, QKeySequence

from gui.waveform_widget import WaveformWidget
from gui.timeline_widget import TimelineWidget
from gui.effects_panel import EffectsPanel
from gui.transport_bar import TransportBar
from gui.dialogs import RecordDialog, AboutDialog
from gui.catalog_dialog import CatalogDialog
from gui.settings_dialog import SettingsDialog
from gui.preset_dialog import PresetCreateDialog, PresetManageDialog, TagManageDialog

from core.audio_engine import (
    load_audio, export_audio, ensure_stereo, get_duration, format_time,
    ffmpeg_available, download_ffmpeg
)
from core.playback import PlaybackEngine
from core.timeline import Timeline, AudioClip
from core.project import save_project, load_project
from core.preset_manager import PresetManager
from core.effects.utils import fade_in, fade_out

from plugins.loader import load_plugins

from utils.config import (
    COLORS, APP_NAME, APP_VERSION, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    AUDIO_EXTENSIONS, ALL_EXTENSIONS, load_settings, save_settings
)
from utils.translator import t, set_language, get_language


# ═══ Background worker for heavy operations ═══

class _EffectWorker(QThread):
    """Runs effect processing off the UI thread."""
    done = Signal(object)   # result numpy array or None
    error = Signal(str)

    def __init__(self, fn, args, kwargs, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        """Telecharge FFmpeg en arriere-plan et emet le signal status."""
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.done.emit(result)
        except Exception as ex:
            self.error.emit(str(ex))


class UndoState:
    """Lightweight undo snapshot — stores references (not copies) since the caller
    replaces self.audio_data rather than mutating in-place. The arrays become
    immutable once stored here. Only clips need real copies because timeline
    may mutate them."""
    __slots__ = ("audio", "sr", "clips", "desc", "base_audio", "global_effects")
    def __init__(self, audio, sr, clips, desc="", base_audio=None, global_effects=None):
        # Store reference — caller must NOT mutate these after push
        self.audio = audio
        self.sr = sr
        self.clips = clips  # list of (name, data, pos, color) — data is a reference
        self.desc = desc
        self.base_audio = base_audio
        self.global_effects = dict(global_effects) if global_effects else {}


class _FFmpegDownloadThread(QThread):
    """Background thread to auto-download FFmpeg on first run."""
    status = Signal(str)

    def run(self):
        """Telecharge FFmpeg en arriere-plan et emet le signal status."""
        try:
            self.status.emit("Downloading FFmpeg...")
            download_ffmpeg(progress_cb=lambda msg: self.status.emit(msg))
            self.status.emit("✓ FFmpeg installed — all formats supported")
        except Exception as e:
            self.status.emit(f"FFmpeg auto-install failed: {e}")


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.setAcceptDrops(True)

        # State
        self.audio_data: np.ndarray | None = None
        self.sample_rate: int = 44100
        self.current_filepath: str = ""
        self.project_filepath: str = ""
        self.timeline = Timeline()
        self.playback = PlaybackEngine()
        self.playback.on_playback_finished = self._on_finished
        self._undo: list[UndoState] = []
        self._redo: list[UndoState] = []
        self._unsaved = False
        self.preset_manager = PresetManager()

        # Global effects: non-destructive effects applied to entire audio
        self._base_audio: np.ndarray | None = None
        self._global_effects: dict[str, dict] = {}  # effect_id -> params
        self._active_worker = None  # ref to prevent GC of background worker

        # Load effect plugins
        self._plugins = load_plugins()

        # Build UI
        self._build_ui()
        self._build_menus()
        self._connect()
        self._setup_shortcuts()
        self._refresh_presets()

        # Playhead timer 30fps
        self._timer = QTimer()
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._upd_playhead)
        self._timer.start()

        # Style
        self.setStyleSheet(f"""
            QMainWindow {{ background: {COLORS['bg_dark']}; }}
            QStatusBar {{ background: {COLORS['bg_medium']}; color: {COLORS['text_dim']}; font-size: 11px; }}
            QMenuBar {{ background: {COLORS['bg_medium']}; color: {COLORS['text']}; font-size: 11px; }}
            QMenuBar::item:selected {{ background: {COLORS['accent']}; }}
            QMenu {{ background: {COLORS['bg_medium']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; font-size: 11px; }}
            QMenu::item {{ padding: 5px 24px 5px 14px; min-width: 120px; }}
            QMenu::item:selected {{ background: {COLORS['accent']}; }}
            QMenu::separator {{ height: 1px; background: {COLORS['border']}; margin: 3px 8px; }}
            QToolTip {{ background: {COLORS['bg_medium']}; color: {COLORS['text']};
                border: 1px solid {COLORS['accent']}; padding: 6px; font-size: 11px; }}
        """)
        self.statusBar().showMessage("Ready")

        # Auto-download FFmpeg in background if not found
        if not ffmpeg_available():
            self._ffmpeg_thread = _FFmpegDownloadThread(self)
            self._ffmpeg_thread.status.connect(lambda msg: self.statusBar().showMessage(msg))
            self._ffmpeg_thread.start()

    # ══════ UI Build ══════

    def _build_ui(self):
        """Construit toute l interface : sidebar effets, toolbar, waveform, timeline, transport."""
        c = QWidget(); self.setCentralWidget(c)
        mlo = QHBoxLayout(c); mlo.setContentsMargins(0, 0, 0, 0); mlo.setSpacing(0)

        # Sidebar
        self.effects_panel = EffectsPanel()
        self.effects_panel.setStyleSheet(f"background: {COLORS['bg_panel']};")
        mlo.addWidget(self.effects_panel)

        # Right area
        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)

        # Toolbar with undo/redo
        tb = QWidget(); tb.setFixedHeight(32)
        tb.setStyleSheet(f"background: {COLORS['bg_medium']};")
        tlo = QHBoxLayout(tb); tlo.setContentsMargins(8, 2, 8, 2); tlo.setSpacing(4)

        self.btn_undo = self._make_toolbar_btn("Undo  (Ctrl+Z)")
        self.btn_undo.setEnabled(False); self.btn_undo.clicked.connect(self._do_undo)
        tlo.addWidget(self.btn_undo)

        self.btn_redo = self._make_toolbar_btn("Redo  (Ctrl+Y)")
        self.btn_redo.setEnabled(False); self.btn_redo.clicked.connect(self._do_redo)
        tlo.addWidget(self.btn_redo)

        tlo.addSpacing(12)
        self.toolbar_info = QLabel("")
        self.toolbar_info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        tlo.addWidget(self.toolbar_info)
        tlo.addStretch()

        _tss = (f"QPushButton {{ background: {COLORS['button_bg']}; color: {COLORS['text']};"
                f" border: 1px solid {COLORS['border']}; border-radius: 4px;"
                f" font-size: 10px; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {COLORS['button_hover']}; border-color: {COLORS['accent']}; }}"
                f"QPushButton:checked {{ background: {COLORS['accent']}; color: white; border-color: {COLORS['accent']}; }}")
        _small = (f"QPushButton {{ background: {COLORS['button_bg']}; color: {COLORS['text']};"
                  f" border: 1px solid {COLORS['border']}; border-radius: 3px;"
                  f" font-size: 12px; font-weight: bold; padding: 0; }}"
                  f"QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}")

        # Metronome toggle
        self.btn_metro = QPushButton("Metronome"); self.btn_metro.setFixedHeight(26)
        self.btn_metro.setCheckable(True); self.btn_metro.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_metro.setStyleSheet(_tss); self.btn_metro.clicked.connect(self._toggle_metronome)
        tlo.addWidget(self.btn_metro)

        # BPM: [-] spinner [+]
        self.btn_bpm_minus = QPushButton("-"); self.btn_bpm_minus.setFixedSize(22, 26)
        self.btn_bpm_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bpm_minus.setStyleSheet(_small)
        self.btn_bpm_minus.setAutoRepeat(True); self.btn_bpm_minus.setAutoRepeatInterval(80)
        self.btn_bpm_minus.clicked.connect(lambda: self._adjust_bpm(-1))
        tlo.addWidget(self.btn_bpm_minus)

        self.bpm_spin = QSpinBox(); self.bpm_spin.setRange(20, 300); self.bpm_spin.setValue(120)
        self.bpm_spin.setSuffix(" BPM"); self.bpm_spin.setFixedSize(82, 26)
        self.bpm_spin.setStyleSheet(
            f"QSpinBox {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; border-radius: 3px;"
            f" font-size: 10px; padding: 0 2px; }}"
            f"QSpinBox:focus {{ border-color: {COLORS['accent']}; }}"
            f"QSpinBox::up-button, QSpinBox::down-button {{ width: 0; height: 0; }}")
        self.bpm_spin.valueChanged.connect(self._on_bpm_changed)
        tlo.addWidget(self.bpm_spin)

        self.btn_bpm_plus = QPushButton("+"); self.btn_bpm_plus.setFixedSize(22, 26)
        self.btn_bpm_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_bpm_plus.setStyleSheet(_small)
        self.btn_bpm_plus.setAutoRepeat(True); self.btn_bpm_plus.setAutoRepeatInterval(80)
        self.btn_bpm_plus.clicked.connect(lambda: self._adjust_bpm(1))
        tlo.addWidget(self.btn_bpm_plus)

        tlo.addSpacing(4)

        # Grid dropdown
        self.btn_grid = QPushButton("Grid: Off"); self.btn_grid.setFixedHeight(26)
        self.btn_grid.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_grid.setStyleSheet(_tss)
        self.btn_grid.clicked.connect(self._show_grid_menu)
        tlo.addWidget(self.btn_grid)

        rl.addWidget(tb)

        # Waveform
        self.waveform = WaveformWidget()
        rl.addWidget(self.waveform, stretch=3)

        # Horizontal scroll bar (visible when zoomed)
        self.wave_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self.wave_scrollbar.setFixedHeight(12)
        self.wave_scrollbar.setVisible(False)
        self.wave_scrollbar.setStyleSheet(f"""
            QScrollBar:horizontal {{
                background: {COLORS['bg_dark']}; height: 12px;
                border: none; border-radius: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {COLORS['accent']}; min-width: 30px;
                border-radius: 4px; margin: 2px 0;
            }}
            QScrollBar::handle:horizontal:hover {{ background: {COLORS['accent_hover']}; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0; height: 0;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: {COLORS['bg_dark']};
            }}
        """)
        self.wave_scrollbar.valueChanged.connect(self._on_wave_scroll)
        rl.addWidget(self.wave_scrollbar)

        # Timeline
        self.timeline_w = TimelineWidget(self.timeline)
        rl.addWidget(self.timeline_w, stretch=1)

        # Transport
        self.transport = TransportBar()
        rl.addWidget(self.transport)

        mlo.addWidget(right, stretch=1)

    def _make_toolbar_btn(self, text):
        """Cree un bouton stylise pour la toolbar (undo/redo etc)."""
        b = QPushButton(text); b.setFixedHeight(26)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['button_bg']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 4px;
                font-size: 10px; padding: 0 10px; }}
            QPushButton:hover {{ background: {COLORS['button_hover']}; border-color: {COLORS['accent']}; }}
            QPushButton:disabled {{ color: {COLORS['text_dim']}; background: {COLORS['bg_dark']}; }}
        """)
        return b

    def _build_menus(self):
        """Build or rebuild the entire menu bar."""
        mb = self.menuBar(); mb.clear()

        # File
        fm = mb.addMenu(t("menu.file"))
        self._menu_action(fm, t("menu.file.open"), "Ctrl+O", self._open)
        self._menu_action(fm, t("menu.file.record"), "", self._record)
        fm.addSeparator()
        self._menu_action(fm, t("menu.file.save"), "Ctrl+S", self._save)
        self._menu_action(fm, t("menu.file.save_as"), "Ctrl+Shift+S", self._save_as)
        fm.addSeparator()
        self._menu_action(fm, t("menu.file.export_wav"), "", lambda: self._export("wav"))
        self._menu_action(fm, t("menu.file.export_mp3"), "", lambda: self._export("mp3"))
        self._menu_action(fm, t("menu.file.export_flac"), "", lambda: self._export("flac"))
        fm.addSeparator()
        self._menu_action(fm, t("menu.file.export_presets"), "", self._export_presets)
        self._menu_action(fm, t("menu.file.import_presets"), "", self._import_presets)
        fm.addSeparator()
        self._menu_action(fm, t("menu.file.quit"), "Ctrl+Q", self.close)

        # Options
        om = mb.addMenu(t("menu.options"))
        self._menu_action(om, t("menu.options.audio"), "", self._settings_audio)
        self._menu_action(om, t("menu.options.language"), "", self._settings_language)
        om.addSeparator()
        self._menu_action(om, "Metronome Settings...", "", self._open_metronome_dialog)
        self._menu_action(om, "Grid...", "", self._show_grid_menu)
        om.addSeparator()
        self._menu_action(om, t("menu.options.select_all"), "Ctrl+A", self._select_all)
        om.addSeparator()
        self._menu_action(om, t("menu.options.import_effect"), "", self._import_effect)

        # Effects (dynamically built from plugins)
        efm = mb.addMenu(t("menu.effects"))
        from plugins.loader import plugins_grouped
        lang = get_language()
        grouped = plugins_grouped(self._plugins, lang)
        for i, (sec_label, sec_plugins) in enumerate(grouped):
            if i > 0:
                efm.addSeparator()
            for plugin in sec_plugins:
                name = plugin.get_name(lang)
                pid = plugin.id
                self._menu_action(efm, name, "", lambda _, pid=pid: self._on_effect(pid))
        efm.addSeparator()
        self._menu_action(efm, t("menu.effects.catalog"), "", self._catalog)
        self._menu_action(efm, t("menu.options.import_effect"), "", self._import_effect)

        # Help
        hm = mb.addMenu(t("menu.help"))
        self._menu_action(hm, t("menu.help.about"), "", lambda: AboutDialog(self).exec())

    def _menu_action(self, menu, text, shortcut, slot) -> QAction:
        """Ajoute une action a un menu avec raccourci optionnel."""
        a = menu.addAction(text)
        if shortcut: a.setShortcut(shortcut)
        a.triggered.connect(slot); return a

    def _setup_shortcuts(self):
        """Configure les raccourcis clavier globaux (space, esc, etc)."""
        for key, slot in [
            (Qt.Key.Key_Space, self._toggle_play),
            (Qt.Key.Key_Escape, self._deselect),
        ]:
            s = QShortcut(QKeySequence(key), self)
            s.setContext(Qt.ShortcutContext.WindowShortcut)
            s.activated.connect(slot)
        for seq, slot in [("Ctrl+Z", self._do_undo), ("Ctrl+Y", self._do_redo)]:
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.ShortcutContext.WindowShortcut)
            s.activated.connect(slot)

    def _connect(self):
        """Connecte tous les signaux/slots entre widgets."""
        self.transport.play_clicked.connect(self._play)
        self.transport.pause_clicked.connect(self._stop)
        self.transport.stop_clicked.connect(self._stop)
        self.transport.volume_changed.connect(self.playback.set_volume)
        self.waveform.position_clicked.connect(self._seek)
        self.waveform.selection_changed.connect(self._on_sel)
        self.waveform.drag_started.connect(self._on_drag_start)
        self.waveform.zoom_changed.connect(self._on_waveform_zoom)
        self.effects_panel.effect_clicked.connect(self._on_effect)
        self.effects_panel.catalog_clicked.connect(self._catalog)
        self.effects_panel.import_clicked.connect(self._import_effect)
        self.effects_panel.preset_clicked.connect(self._on_preset)
        self.effects_panel.preset_new_clicked.connect(self._new_preset)
        self.effects_panel.preset_manage_clicked.connect(self._manage_presets)
        self.timeline_w.clip_selected.connect(self._on_clip_sel)
        self.timeline_w.split_requested.connect(self._split_clip)
        self.timeline_w.duplicate_requested.connect(self._dup_clip)
        self.timeline_w.delete_requested.connect(self._del_clip)
        self.timeline_w.fade_in_requested.connect(self._fi_clip)
        self.timeline_w.fade_out_requested.connect(self._fo_clip)
        self.timeline_w.clips_reordered.connect(self._on_reorder)
        self.timeline_w.seek_requested.connect(self._seek_from_timeline)

    def _update_undo_labels(self):
        """Met a jour les tooltips des boutons undo/redo."""
        hu, hr = bool(self._undo), bool(self._redo)
        self.btn_undo.setEnabled(hu); self.btn_redo.setEnabled(hr)
        if hu:
            self.btn_undo.setText(f"Undo: {self._undo[-1].desc}  (Ctrl+Z)")
            self.toolbar_info.setText(f"{len(self._undo)} action(s)")
        else:
            self.btn_undo.setText("Undo  (Ctrl+Z)")
            self.toolbar_info.setText("")
        self.btn_redo.setText("Redo  (Ctrl+Y)")

    # ══════ Waveform Scroll ══════

    def _on_waveform_zoom(self, zoom, offset):
        """Update scrollbar when waveform zoom/offset changes."""
        if zoom <= 1.01:
            self.wave_scrollbar.setVisible(False)
            return
        self.wave_scrollbar.setVisible(True)
        visible_frac = 1.0 / zoom
        # Scrollbar range: 0 to 10000 for precision
        max_val = 10000
        page = int(visible_frac * max_val)
        self.wave_scrollbar.blockSignals(True)
        self.wave_scrollbar.setRange(0, max_val - page)
        self.wave_scrollbar.setPageStep(page)
        self.wave_scrollbar.setValue(int(offset * max_val))
        self.wave_scrollbar.blockSignals(False)

    def _on_wave_scroll(self, value):
        """Scrollbar dragged — update waveform offset."""
        offset = value / 10000.0
        self.waveform.set_scroll_offset(offset)

    # ══════ Metronome & Grid ══════

    def _toggle_metronome(self):
        """Active/desactive le metronome depuis le bouton toolbar."""
        self.playback.metronome.enabled = self.btn_metro.isChecked()

    def _adjust_bpm(self, delta):
        """Incremente/decremente le BPM de la valeur donnee."""
        self.bpm_spin.setValue(self.bpm_spin.value() + delta)

    def _on_bpm_changed(self, val):
        """Synchronise le BPM du metronome et de la grille."""
        self.playback.metronome.set_bpm(val)
        if self.waveform._grid_enabled:
            self.waveform._grid_bpm = val
            self.waveform.update()

    def _show_grid_menu(self):
        """Affiche le menu dropdown de choix de grille (style FL Studio)."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {COLORS['bg_panel']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; padding: 4px; }}
            QMenu::item {{ padding: 5px 24px 5px 12px; border-radius: 3px; }}
            QMenu::item:selected {{ background: {COLORS['accent']}; color: white; }}
            QMenu::separator {{ height: 1px; background: {COLORS['border']}; margin: 3px 8px; }}
        """)
        opts = [
            ("Off", 0), None,
            ("Bar", -1), ("Beat", 1), None,
            ("1/2", 2), ("1/3", 3), ("1/4", 4),
            ("1/6", 6), ("1/8", 8), ("1/12", 12), ("1/16", 16),
        ]
        for opt in opts:
            if opt is None:
                menu.addSeparator(); continue
            label, subdiv = opt
            a = menu.addAction(label)
            a.triggered.connect(lambda _, l=label, s=subdiv: self._set_grid(l, s))
        pos = self.btn_grid.mapToGlobal(self.btn_grid.rect().bottomLeft())
        menu.exec(pos)

    def _set_grid(self, label, subdiv):
        """Applique la configuration de grille selectionnee."""
        if subdiv == 0:
            self.waveform.set_grid(False)
            self.btn_grid.setText("Grid: Off"); return
        bpm = self.bpm_spin.value()
        beats = self.playback.metronome.beats_per_bar
        if subdiv == -1:  # Bar mode
            self.waveform.set_grid(True, bpm, beats, 1)
            self.waveform._grid_beats_per_bar = 1
            self.waveform._grid_subdiv = 1
            self.waveform.update()
        else:
            self.waveform.set_grid(True, bpm, beats, subdiv)
        self.btn_grid.setText(f"Grid: {label}")

    def _open_metronome_dialog(self):
        """Ouvre le dialogue complet de reglages du metronome."""
        metro = self.playback.metronome
        dlg = QDialog(self)
        dlg.setWindowTitle("Metronome Settings"); dlg.setFixedWidth(300)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {COLORS['bg_panel']}; color: {COLORS['text']}; }}
            QLabel {{ color: {COLORS['text']}; font-size: 11px; }}
            QSpinBox {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; border-radius: 4px;
                padding: 3px 6px; font-size: 11px; }}
            QSlider::groove:horizontal {{ background: {COLORS['bg_dark']}; height: 4px; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {COLORS['accent']}; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px; }}
            QCheckBox {{ color: {COLORS['text']}; font-size: 11px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 3px;
                border: 1px solid {COLORS['border']}; background: {COLORS['bg_dark']}; }}
            QCheckBox::indicator:checked {{ background: {COLORS['accent']}; border-color: {COLORS['accent']}; }}
        """)
        lo = QVBoxLayout(dlg); lo.setSpacing(8); lo.setContentsMargins(16, 12, 16, 12)

        chk = QCheckBox("Enabled"); chk.setChecked(metro.enabled); lo.addWidget(chk)

        r1 = QHBoxLayout(); r1.addWidget(QLabel("BPM"))
        bpm_s = QSpinBox(); bpm_s.setRange(20, 300); bpm_s.setValue(int(metro.bpm))
        r1.addStretch(); r1.addWidget(bpm_s); lo.addLayout(r1)

        r2 = QHBoxLayout(); r2.addWidget(QLabel("Beats / Bar"))
        beats_s = QSpinBox(); beats_s.setRange(1, 12); beats_s.setValue(metro.beats_per_bar)
        r2.addStretch(); r2.addWidget(beats_s); lo.addLayout(r2)

        r3 = QHBoxLayout(); r3.addWidget(QLabel("Volume"))
        vol_sl = QSlider(Qt.Orientation.Horizontal)
        vol_sl.setRange(0, 100); vol_sl.setValue(int(metro.volume * 100))
        vol_lbl = QLabel(f"{int(metro.volume*100)}%"); vol_lbl.setFixedWidth(36)
        vol_sl.valueChanged.connect(lambda v: vol_lbl.setText(f"{v}%"))
        r3.addWidget(vol_sl, stretch=1); r3.addWidget(vol_lbl); lo.addLayout(r3)

        btns = QHBoxLayout(); btns.addStretch()
        for txt, slot in [("Cancel", dlg.reject), ("OK", dlg.accept)]:
            b = QPushButton(txt); b.setFixedHeight(28)
            b.setStyleSheet(f"QPushButton {{ background: {COLORS['button_bg']}; color: {COLORS['text']};"
                            f" border: 1px solid {COLORS['border']}; border-radius: 4px; padding: 0 16px; }}"
                            f"QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}")
            b.clicked.connect(slot); btns.addWidget(b)
        lo.addLayout(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            metro.enabled = chk.isChecked()
            metro.set_bpm(bpm_s.value())
            metro.set_beats(beats_s.value())
            metro.set_volume(vol_sl.value() / 100.0)
            self.btn_metro.setChecked(metro.enabled)
            self.bpm_spin.setValue(int(metro.bpm))

    # ══════ Playback ══════

    def _toggle_play(self):
        """Bascule play/pause."""
        if self.audio_data is None: return
        if self.playback.is_playing:
            self._stop()        # stop → return to anchor
        else:
            self._play()        # play from anchor

    def _play(self):
        """Demarre la lecture depuis la selection ou la position actuelle."""
        if self.audio_data is None: return
        s, e = self._sel_range()
        if s is not None:
            # Selection exists: loop it
            self.playback.set_loop(s, e, looping=True)
            self.playback.play(start_pos=s)
        else:
            # No selection: always start from anchor (or 0)
            self.playback.set_loop(None, None, looping=False)
            anchor = self.waveform._anchor
            start = anchor if anchor is not None else 0
            self.playback.play(start_pos=start)
        self.transport.set_playing(True)

    def _pause(self):
        """Met en pause la lecture."""
        self.playback.pause(); self.transport.set_playing(False)

    def _stop(self):
        """Arrete la lecture et remet le curseur a l ancre."""
        self.playback.stop(); self.transport.set_playing(False)
        # Return playhead to anchor if set, else to 0
        anchor = self.waveform._anchor
        pos = anchor if anchor is not None else 0
        self.playback.seek(pos)
        self.waveform.set_playhead(pos)
        self.timeline_w.set_playhead(pos, self.sample_rate)
        self.timeline_w.set_anchor(anchor)
        if self.audio_data is not None:
            self.transport.set_time(
                format_time(pos / self.sample_rate),
                format_time(get_duration(self.audio_data, self.sample_rate)))

    def _seek(self, pos):
        """Single click on waveform: set blue anchor, sync timeline, clear selection."""
        # If was playing, stop (click = new anchor, not a selection)
        was_playing = self.playback.is_playing
        if was_playing:
            self.playback.stop()
            self.transport.set_playing(False)
        self.playback.seek(pos)
        self.waveform.set_playhead(pos)
        self.timeline_w.set_anchor(pos)
        self.transport.set_selection_info("")
        self.timeline_w._selected_id = None
        self.timeline_w.update()

    def _on_drag_start(self):
        """Mouse down on waveform — pause playback if playing."""
        self._was_playing_before_drag = self.playback.is_playing
        if self._was_playing_before_drag:
            self.playback.pause()

    def _seek_from_timeline(self, pos):
        """Click/drag in timeline: set position in both waveform and timeline."""
        self.playback.seek(pos)
        self.waveform.set_playhead(pos)
        self.waveform.set_anchor(pos)
        self.waveform.selection_start = self.waveform.selection_end = None
        self.transport.set_selection_info("")
        if self.audio_data is not None:
            self.transport.set_time(
                format_time(pos / self.sample_rate),
                format_time(get_duration(self.audio_data, self.sample_rate)))

    def _on_sel(self, s, e):
        """Met a jour la selection et affiche la duree."""
        dur = format_time(abs(e - s) / self.sample_rate)
        self.transport.set_selection_info(f"Sel: {dur}")
        self.waveform._anchor = None
        self.timeline_w.clear_anchor()
        self.timeline_w._selected_id = None
        self.timeline_w.update()
        start = min(s, e)
        end = max(s, e)

        # If was playing before the drag, resume in the new zone
        if getattr(self, '_was_playing_before_drag', False):
            self._was_playing_before_drag = False
            self.playback.set_loop(start, end, looping=True)
            self.playback.play(start_pos=start)
            self.transport.set_playing(True)
        else:
            self.playback.seek(start)
            self.waveform.set_playhead(start)
            self.timeline_w.set_playhead(start, self.sample_rate)

    def _on_finished(self):
        """Callback quand la lecture arrive en fin de fichier."""
        QTimer.singleShot(0, lambda: self.transport.set_playing(False))

    def _upd_playhead(self):
        """Timer callback — met a jour le playhead pendant la lecture."""
        if self.playback.is_playing and self.audio_data is not None:
            pos = self.playback.position
            self.waveform.set_playhead(pos)
            self.timeline_w.set_playhead(pos, self.sample_rate)
            self.transport.set_time(
                format_time(pos / self.sample_rate),
                format_time(get_duration(self.audio_data, self.sample_rate)))

    def _sel_range(self):
        """Retourne la plage de selection (debut, fin) en samples."""
        s, e = self.waveform.selection_start, self.waveform.selection_end
        if s is not None and e is not None and abs(s - e) > 10:
            return min(s, e), max(s, e)
        return None, None

    def _deselect(self):
        """Escape key: clear selection, anchor, clip highlight, reset zoom."""
        self.waveform.clear_all()
        self.waveform.reset_zoom()
        self.transport.set_selection_info("")
        self.timeline_w._selected_id = None
        self.timeline_w.clear_anchor()
        self.timeline_w.update()

    # ══════ Open ══════

    def _open(self):
        """Ouvre un fichier audio ou projet."""
        exts_list = " ".join(["*" + e for e in sorted(ALL_EXTENSIONS)])
        fp, _ = QFileDialog.getOpenFileName(
            self, t("menu.file.open"), "",
            f"Audio & Projects ({exts_list});;All files (*)")
        if not fp:
            return
        ext = os.path.splitext(fp)[1].lower()
        if ext == ".gspi":
            self._load_gspi(fp)
        elif ext in AUDIO_EXTENSIONS:
            self._load_audio(fp)

    def _load_audio(self, fp):
        """Charge un fichier audio dans la timeline."""
        try:
            self._stop()
            data, sr = load_audio(fp)
            st = ensure_stereo(data)
            name = os.path.splitext(os.path.basename(fp))[0]

            if self.audio_data is None:
                self.audio_data, self.sample_rate = st, sr
                self.current_filepath = fp
                self.timeline.clear()
                self.timeline.add_clip(st, sr, name=name, position=0)
            else:
                self._push_undo("Import")
                self.timeline.add_clip(st, sr, name=name)
                self._rebuild_audio()

            # Reset global effects
            self._base_audio = None
            self._global_effects.clear()

            self._refresh_all()
            self._undo.clear(); self._redo.clear(); self._update_undo_labels()
            self._unsaved = True
            self.setWindowTitle(f"{APP_NAME} — {os.path.basename(fp)}")
            self.statusBar().showMessage(f"Loaded: {os.path.basename(fp)}")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, str(e))

    def _load_gspi(self, fp):
        try:
            self._stop()
            tl, sr, src = load_project(fp)
            self.timeline, self.sample_rate = tl, sr
            self.current_filepath = src
            self.project_filepath = fp
            self._base_audio = None
            self._global_effects.clear()
            self._rebuild_audio()
            self._undo.clear(); self._redo.clear(); self._update_undo_labels()
            self._unsaved = False
            self.setWindowTitle(f"{APP_NAME} — {os.path.splitext(os.path.basename(fp))[0]}")
            self.statusBar().showMessage(f"Project: {os.path.basename(fp)}")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, str(e))

    # ══════ Save ══════

    def _save(self):
        if not self.timeline.clips:
            QMessageBox.warning(self, APP_NAME, t("error.empty_timeline")); return
        if self.project_filepath:
            self._do_save(self.project_filepath)
        else:
            self._save_as()

    def _save_as(self):
        if not self.timeline.clips:
            QMessageBox.warning(self, APP_NAME, t("error.empty_timeline")); return
        fp, _ = QFileDialog.getSaveFileName(
            self, t("menu.file.save_as"), "project.gspi", "Glitch Maker (*.gspi)")
        if fp:
            if not fp.endswith(".gspi"):
                fp += ".gspi"
            self._do_save(fp)

    def _do_save(self, fp):
        try:
            save_project(fp, self.timeline, self.sample_rate, self.current_filepath)
            self.project_filepath = fp
            self._unsaved = False
            self.statusBar().showMessage(f"Saved: {os.path.basename(fp)}")
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, str(e))

    # ══════ Export ══════

    def _export(self, fmt):
        if self.audio_data is None:
            QMessageBox.warning(self, APP_NAME, t("error.no_audio")); return
        fmap = {"wav": "WAV (*.wav)", "mp3": "MP3 (*.mp3)", "flac": "FLAC (*.flac)"}
        fp, _ = QFileDialog.getSaveFileName(self, "Export", f"export.{fmt}", fmap.get(fmt, ""))
        if fp:
            try:
                export_audio(self.audio_data, self.sample_rate, fp, fmt)
                self.statusBar().showMessage(f"Exported: {fp}")
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, str(e))

    # ══════ Refresh ══════

    def _refresh_all(self):
        self.timeline_w.timeline = self.timeline
        self.timeline_w.sample_rate = self.sample_rate
        self.timeline_w.update()
        if self.audio_data is not None:
            self.waveform.set_audio(self.audio_data, self.sample_rate)
            self.playback.load(self.audio_data, self.sample_rate)
            self.transport.set_time("00:00.00",
                                    format_time(get_duration(self.audio_data, self.sample_rate)))
        self.transport.set_selection_info("")

    def _rebuild_audio(self):
        rendered, sr = self.timeline.render()
        if len(rendered) > 0:
            self.audio_data, self.sample_rate = rendered, sr
        self._refresh_all()

    # ══════ Clip selection → waveform highlight ══════

    def _on_clip_sel(self, clip_id):
        """Callback quand un clip est selectionne dans la timeline."""
        for c in self.timeline.clips:
            if c.id == clip_id:
                self.waveform.set_clip_highlight(c.position, c.end_position)
                self.waveform.set_selection(c.position, c.end_position)
                # Update transport info directly (don't emit selection_changed
                # which would clear the timeline anchor)
                dur = format_time(c.duration_seconds)
                self.transport.set_selection_info(f"Sel: {dur}")
                # Move playhead to clip start
                self.playback.seek(c.position)
                self.waveform.set_playhead(c.position)
                self.timeline_w.set_playhead(c.position, self.sample_rate)
                return
        self.waveform.set_clip_highlight(None, None)

    # ══════ Effects (plugin-based) ══════

    def _find_plugin(self, effect_id):
        """Find plugin by ID, or try matching by display name for preset compat."""
        if effect_id in self._plugins:
            return self._plugins[effect_id]
        # Fallback: match by name for backward compat with presets
        lang = get_language()
        for pid, plugin in self._plugins.items():
            if plugin.get_name("en") == effect_id or plugin.get_name("fr") == effect_id:
                return plugin
        return None

    def _on_effect(self, effect_id):
        """Ouvre le dialogue d un effet et l applique si confirme."""
        if self.audio_data is None:
            QMessageBox.warning(self, APP_NAME, t("error.no_audio")); return
        plugin = self._find_plugin(effect_id)
        if not plugin:
            return

        # Stop playback AND close the stream to free the audio device for preview
        if self.playback.is_playing:
            self._stop()
        self.playback.suspend_stream()

        s, e = self._sel_range()
        is_global = (s is None)

        d = plugin.dialog_class(self)

        # Inject preview context — segment + process function + output device
        if is_global:
            preview_seg = self.audio_data
        else:
            preview_seg = self.audio_data[s:e]
        if preview_seg is not None and len(preview_seg) > 0:
            d.setup_preview(preview_seg, self.sample_rate, plugin.process_fn,
                            output_device=self.playback.output_device)

        # If global mode and we already have stored params, pre-fill
        if is_global and effect_id in self._global_effects:
            try:
                d.set_params(self._global_effects[effect_id])
            except Exception:
                pass

        accepted = d.exec() == d.DialogCode.Accepted

        # Re-open main stream now that dialog is closed
        self.playback.resume_stream()

        if not accepted:
            return

        params = d.get_params()
        name = plugin.get_name(get_language())

        if is_global:
            self._push_undo(f"{name} (global)")
            self._global_effects[effect_id] = params
            self._run_global_effects_async()
        else:
            self._push_undo(name)
            self._run_local_effect_async(effect_id, params, s, e)

    def _run_plugin(self, effect_id, seg, sr, params):
        """Run plugin's process function on a segment."""
        plugin = self._find_plugin(effect_id)
        if not plugin:
            print(f"[effect] Unknown: {effect_id}")
            return None
        try:
            return plugin.process_fn(seg, 0, len(seg), sr=sr, **params)
        except Exception as ex:
            print(f"[effect] {effect_id} error: {ex}")
            return None

    # ── Async effect processing ──

    def _set_busy(self, busy):
        """Set/restore busy cursor and disable effect interactions."""
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.effects_panel.setEnabled(False)
        else:
            QApplication.restoreOverrideCursor()
            self.effects_panel.setEnabled(True)

    def _run_local_effect_async(self, effect_id, params, s, e):
        """Run local effect in background thread."""
        segment = self.audio_data[s:e].copy()
        if len(segment) == 0:
            return
        self._set_busy(True)

        def _process():
            plugin = self._find_plugin(effect_id)
            if not plugin:
                return None
            return plugin.process_fn(segment, 0, len(segment),
                                     sr=self.sample_rate, **params)

        worker = _EffectWorker(_process, (), {}, self)
        # Store ref to prevent GC
        self._active_worker = worker

        def _on_done(mod):
            self._set_busy(False)
            self._active_worker = None
            if mod is None:
                if self._undo:
                    self._do_undo()
                return
            if mod.dtype != np.float32:
                mod = mod.astype(np.float32)
            # Splice result into audio
            if len(mod) == (e - s):
                new_audio = self.audio_data.copy()
                new_audio[s:e] = mod
                self.audio_data = new_audio
            else:
                before, after = self.audio_data[:s], self.audio_data[e:]
                parts = [p for p in [before, mod, after] if len(p) > 0]
                self.audio_data = np.concatenate(parts, axis=0).astype(np.float32)
            # Also update base_audio if global chain exists
            if self._base_audio is not None:
                try:
                    mod_b = self._run_plugin(effect_id, self._base_audio[s:e].copy(),
                                             self.sample_rate, dict(params))
                    if mod_b is not None:
                        if mod_b.dtype != np.float32:
                            mod_b = mod_b.astype(np.float32)
                        if len(mod_b) == (e - s):
                            new_base = self._base_audio.copy()
                            new_base[s:e] = mod_b
                            self._base_audio = new_base
                        else:
                            before_b, after_b = self._base_audio[:s], self._base_audio[e:]
                            parts_b = [p for p in [before_b, mod_b, after_b] if len(p) > 0]
                            self._base_audio = np.concatenate(parts_b, axis=0).astype(np.float32)
                except Exception:
                    pass
            self._update_clips_from_audio()
            self._refresh_all()
            self._unsaved = True
            plugin = self._find_plugin(effect_id)
            name = plugin.get_name(get_language()) if plugin else effect_id
            self.statusBar().showMessage(f"Applied: {name}")

        def _on_error(msg):
            self._set_busy(False)
            self._active_worker = None
            QMessageBox.critical(self, APP_NAME, f"{effect_id}: {msg}")
            if self._undo:
                self._do_undo()

        worker.done.connect(_on_done)
        worker.error.connect(_on_error)
        worker.start()

    def _run_global_effects_async(self):
        """Run global effect chain in background thread."""
        if self._base_audio is None:
            self._base_audio = self.audio_data.copy()
        base = self._base_audio.copy()
        sr = self.sample_rate
        effects_list = list(self._global_effects.items())
        self._set_busy(True)

        def _process():
            working = base
            for eid, params in effects_list:
                plugin = self._find_plugin(eid)
                if not plugin:
                    continue
                mod = plugin.process_fn(working.copy(), 0, len(working),
                                        sr=sr, **dict(params))
                if mod is not None:
                    working = mod.astype(np.float32) if mod.dtype != np.float32 else mod
            return working

        worker = _EffectWorker(_process, (), {}, self)
        self._active_worker = worker

        def _on_done(result):
            self._set_busy(False)
            self._active_worker = None
            if result is not None:
                self.audio_data = result
                self._update_clips_from_audio()
                self._refresh_all()
                self._unsaved = True
                names = ", ".join(p.get_name(get_language()) for eid in self._global_effects
                                  if (p := self._find_plugin(eid)))
                self.statusBar().showMessage(f"Global: {names}")

        def _on_error(msg):
            self._set_busy(False)
            self._active_worker = None
            QMessageBox.critical(self, APP_NAME, f"Global effect error: {msg}")
            if self._undo:
                self._do_undo()

        worker.done.connect(_on_done)
        worker.error.connect(_on_error)
        worker.start()

    def _update_clips_from_audio(self):
        if not self.timeline.clips:
            return
        total = len(self.audio_data)
        if len(self.timeline.clips) == 1:
            c = self.timeline.clips[0]
            c.audio_data = ensure_stereo(self.audio_data)
            c.position = 0
            return
        old_total = sum(c.duration_samples for c in self.timeline.clips)
        if old_total == 0:
            return
        ratio = total / old_total
        pos = 0
        for c in self.timeline.clips:
            new_len = int(c.duration_samples * ratio)
            new_len = min(new_len, total - pos)
            if new_len > 0:
                c.audio_data = ensure_stereo(self.audio_data[pos:pos + new_len])
            c.position = pos
            pos += new_len
        if pos < total and self.timeline.clips:
            last = self.timeline.clips[-1]
            extra = ensure_stereo(self.audio_data[pos:total])
            last.audio_data = np.concatenate([last.audio_data, extra], axis=0)

    # ══════ Presets ══════

    def _refresh_presets(self):
        all_presets = self.preset_manager.get_all_presets()
        tag_map = {}
        for tag in self.preset_manager.get_all_tags():
            presets = self.preset_manager.get_presets_by_tag(tag)
            if presets:
                tag_map[tag] = presets
        self.effects_panel.set_presets(tag_map, all_presets)

    def _on_preset(self, name):
        """Applique un preset (chaine d effets) a la selection."""
        if self.audio_data is None:
            QMessageBox.warning(self, APP_NAME, t("error.no_audio")); return
        s, e = self._sel_range()
        if s is None:
            QMessageBox.warning(self, APP_NAME, t("preset.need_selection")); return
        preset = self.preset_manager.get_preset(name)
        if not preset:
            return
        self._push_undo(f"Preset: {name}")
        self._set_busy(True)
        QApplication.processEvents()
        try:
            for eff in preset["effects"]:
                try:
                    segment = self.audio_data[s:e].copy()
                    sl = len(segment)
                    if sl == 0:
                        break
                    eff_name = eff["name"]
                    plugin = self._find_plugin(eff_name)
                    if not plugin:
                        self.statusBar().showMessage(f"Unknown effect: {eff_name}")
                        continue
                    mod = self._run_plugin(plugin.id, segment, self.sample_rate, dict(eff["params"]))
                    if mod is not None:
                        if mod.dtype != np.float32:
                            mod = mod.astype(np.float32)
                        before, after = self.audio_data[:s], self.audio_data[e:]
                        self.audio_data = np.concatenate(
                            [p for p in [before, mod, after] if len(p) > 0], axis=0
                        ).astype(np.float32)
                        e = s + len(mod)
                except Exception as ex:
                    self.statusBar().showMessage(f"Error {eff['name']}: {ex}")
                    break
            self._update_clips_from_audio()
            self._refresh_all()
            self._unsaved = True
            self.statusBar().showMessage(f"Preset applied: {name}")
        finally:
            self._set_busy(False)

    def _new_preset(self):
        """Cree un nouveau preset depuis la selection actuelle."""
        tags = self.preset_manager.get_all_tags()
        dlg = PresetCreateDialog(tags, self, preset_manager=self.preset_manager)
        if dlg.exec() == dlg.DialogCode.Accepted and dlg.result_preset:
            r = dlg.result_preset
            self.preset_manager.add_preset(r["name"], r["description"], r["tags"], r["effects"])
            self._refresh_presets()

    def _manage_presets(self):
        """Ouvre le gestionnaire de presets."""
        dlg = PresetManageDialog(self.preset_manager, self)
        dlg.exec()
        if dlg.deleted:
            self._refresh_presets()

    def _export_presets(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, t("menu.file.export_presets"), "",
            "GlitchMaker Presets (*.pspi)")
        if not path:
            return
        if not path.endswith(".pspi"):
            path += ".pspi"
        try:
            self.preset_manager.export_presets(path)
            count = len(self.preset_manager.get_all_presets())
            self.statusBar().showMessage(f"Exported {count} presets → {os.path.basename(path)}")
        except Exception as ex:
            QMessageBox.critical(self, "Export Error", str(ex))

    def _import_presets(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, t("menu.file.import_presets"), "",
            "GlitchMaker Presets (*.pspi)")
        if not path:
            return
        try:
            count, skipped = self.preset_manager.import_presets(path)
            self._refresh_presets()
            msg = f"Imported {count} preset(s)."
            if skipped:
                msg += f"\nSkipped {len(skipped)} duplicate(s): {', '.join(skipped[:5])}"
                if len(skipped) > 5:
                    msg += "..."
            QMessageBox.information(self, "Import", msg)
        except Exception as ex:
            QMessageBox.critical(self, "Import Error", str(ex))

    # ══════ Timeline ops ══════

    def _on_reorder(self):
        try:
            self._push_undo("Reorder")
            self._rebuild_audio()
            self._unsaved = True
        except Exception as e:
            print(f"[reorder] error: {e}")
            self.statusBar().showMessage(f"Reorder error: {e}")

    def _split_clip(self, cid, pos):
        """Coupe un clip en deux a la position donnee."""
        clip = self._find_clip(cid)
        if not clip or pos <= 0 or pos >= clip.duration_samples:
            return
        self._push_undo("Cut")
        idx = self.timeline.clips.index(clip)
        a, b = clip.audio_data[:pos].copy(), clip.audio_data[pos:].copy()
        self.timeline.clips.remove(clip)
        # Part A keeps original color, Part B gets new distinct color
        from core.timeline import _generate_distinct_color
        new_color = _generate_distinct_color(self.timeline._color_counter)
        self.timeline._color_counter += 1
        ca = AudioClip(name=f"{clip.name} (A)", audio_data=a, sample_rate=clip.sample_rate,
                       position=clip.position, color=clip.color)
        cb = AudioClip(name=f"{clip.name} (B)", audio_data=b, sample_rate=clip.sample_rate,
                       position=clip.position + len(a), color=new_color)
        self.timeline.clips.insert(idx, cb)
        self.timeline.clips.insert(idx, ca)
        self._rebuild_audio(); self._unsaved = True

    def _dup_clip(self, cid):
        clip = self._find_clip(cid)
        if not clip:
            return
        self._push_undo("Duplicate")
        end = max(c.end_position for c in self.timeline.clips)
        nc = AudioClip(name=f"{clip.name} (copy)", audio_data=clip.audio_data.copy(),
                       sample_rate=clip.sample_rate, position=end, color=clip.color)
        self.timeline.clips.append(nc)
        self._rebuild_audio(); self._unsaved = True

    def _del_clip(self, cid):
        clip = self._find_clip(cid)
        if not clip or len(self.timeline.clips) <= 1:
            QMessageBox.warning(self, APP_NAME, t("error.cant_delete")); return
        self._push_undo("Delete")
        self.timeline.clips.remove(clip)
        pos = 0
        for c in self.timeline.clips:
            c.position = pos
            pos += c.duration_samples
        self._rebuild_audio(); self._unsaved = True

    def _fi_clip(self, cid):
        clip = self._find_clip(cid)
        if not clip:
            return
        self._push_undo("Fade In")
        n = min(int(0.5 * clip.sample_rate), clip.duration_samples // 2)
        clip.audio_data = fade_in(clip.audio_data, n)
        self._rebuild_audio(); self._unsaved = True

    def _fo_clip(self, cid):
        clip = self._find_clip(cid)
        if not clip:
            return
        self._push_undo("Fade Out")
        n = min(int(0.5 * clip.sample_rate), clip.duration_samples // 2)
        clip.audio_data = fade_out(clip.audio_data, n)
        self._rebuild_audio(); self._unsaved = True

    def _find_clip(self, cid):
        for c in self.timeline.clips:
            if c.id == cid:
                return c
        return None

    # ══════ Undo / Redo ══════

    def _push_undo(self, desc):
        """Empile l etat actuel pour undo (max 30 niveaux)."""
        if self.audio_data is None:
            return
        # Snapshot clip state (references are safe — arrays get replaced, not mutated)
        clips = [(c.name, c.audio_data, c.position, c.color) for c in self.timeline.clips]
        self._undo.append(UndoState(
            self.audio_data, self.sample_rate, clips, desc,
            base_audio=self._base_audio,
            global_effects=self._global_effects))
        if len(self._undo) > 30:
            self._undo.pop(0)
        self._redo.clear()
        self._update_undo_labels()

    def _do_undo(self):
        """Annule la derniere action (Ctrl+Z)."""
        if not self._undo:
            return
        # Save current state to redo (references, no copies)
        cn = [(c.name, c.audio_data, c.position, c.color) for c in self.timeline.clips]
        self._redo.append(UndoState(
            self.audio_data, self.sample_rate, cn, "",
            base_audio=self._base_audio, global_effects=self._global_effects))
        self._restore(self._undo.pop())
        self.statusBar().showMessage("Undo")
        self._update_undo_labels()

    def _do_redo(self):
        """Retablit la derniere action annulee (Ctrl+Y)."""
        if not self._redo:
            return
        cn = [(c.name, c.audio_data, c.position, c.color) for c in self.timeline.clips]
        self._undo.append(UndoState(
            self.audio_data, self.sample_rate, cn, "",
            base_audio=self._base_audio, global_effects=self._global_effects))
        self._restore(self._redo.pop())
        self.statusBar().showMessage("Redo")
        self._update_undo_labels()

    def _restore(self, state):
        self._stop()
        # Take ownership — no copies needed (old refs are in redo stack)
        self.audio_data = state.audio
        self.sample_rate = state.sr
        self._base_audio = state.base_audio
        self._global_effects = dict(state.global_effects) if state.global_effects else {}
        self.timeline.clear()
        for name, data, pos, color in state.clips:
            c = AudioClip(name=name, audio_data=data, sample_rate=state.sr,
                          position=pos, color=color)
            self.timeline.clips.append(c)
        self.timeline.sample_rate = state.sr
        self._refresh_all()

    # ══════ Settings ══════

    def _settings_audio(self):
        """Ouvre les parametres audio."""
        dlg = SettingsDialog(self.playback.output_device, self.playback.input_device, self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self.playback.set_output_device(dlg.selected_output)
            self.playback.set_input_device(dlg.selected_input)
            self.statusBar().showMessage("Audio devices updated")

    def _settings_language(self):
        """Ouvre le dialogue de changement de langue."""
        from PyQt6.QtWidgets import QInputDialog
        langs = ["English", "Français"]
        codes = ["en", "fr"]
        cur_idx = codes.index(get_language()) if get_language() in codes else 0
        choice, ok = QInputDialog.getItem(
            self, "Language", "Select language:", langs, cur_idx, False)
        if ok:
            new_lang = codes[langs.index(choice)]
            if new_lang != get_language():
                set_language(new_lang)
                settings = load_settings()
                settings["language"] = new_lang
                save_settings(settings)
                self._build_menus()
                self._update_undo_labels()
                self.statusBar().showMessage(t("status.lang_changed"))

    def _import_effect(self):
        """Ouvre le dialogue d import de plugin."""
        from gui.import_plugin_dialog import ImportPluginDialog
        dlg = ImportPluginDialog(self)
        dlg.exec()
        if dlg.changed:
            # Reload plugins and rebuild UI
            from plugins.loader import load_plugins
            self._plugins = load_plugins(force_reload=True)
            self._build_menus()
            self.effects_panel.reload_plugins()
            self.statusBar().showMessage("Plugins reloaded")

    # ══════ Misc ══════

    def _record(self):
        d = RecordDialog(input_device=self.playback.input_device, parent=self)
        d.recording_done.connect(self._on_rec)
        d.exec()

    def _on_rec(self, data, sr):
        st = ensure_stereo(data)
        if self.audio_data is None:
            self.audio_data, self.sample_rate = st, sr
        else:
            self._push_undo("Rec")
            self.audio_data = np.concatenate([self.audio_data, st], axis=0).astype(np.float32)
        self.timeline.add_clip(st, sr, name=f"Rec {len(self.timeline.clips) + 1}")
        self._refresh_all()
        self._unsaved = True

    def _select_all(self):
        """Selectionne tout l audio (Ctrl+A)."""
        if self.audio_data is not None:
            self.waveform.set_selection(0, len(self.audio_data))
            self.waveform.selection_changed.emit(0, len(self.audio_data))

    def _catalog(self):
        """Ouvre le catalogue des effets."""
        CatalogDialog(self).exec()

    # ══════ Drag & Drop ══════

    def dragEnterEvent(self, e: QDragEnterEvent):
        """Accepte le drop si c est un fichier audio ou .gspi."""
        if e.mimeData().hasUrls():
            for u in e.mimeData().urls():
                ext = os.path.splitext(u.toLocalFile())[1].lower()
                if ext in ALL_EXTENSIONS:
                    e.acceptProposedAction()
                    return
        e.ignore()

    def dropEvent(self, e: QDropEvent):
        """Charge le fichier droppe."""
        for u in e.mimeData().urls():
            fp = u.toLocalFile()
            ext = os.path.splitext(fp)[1].lower()
            if ext == ".gspi":
                self._load_gspi(fp)
            elif ext in AUDIO_EXTENSIONS:
                self._load_audio(fp)
            return

    # ══════ Close ══════

    def closeEvent(self, e):
        """Demande confirmation si le projet a ete modifie avant de fermer."""
        if self._unsaved and self.audio_data is not None:
            r = QMessageBox.question(
                self, APP_NAME, "Unsaved changes. Save project?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if r == QMessageBox.StandardButton.Save:
                self._save()
                e.accept()
            elif r == QMessageBox.StandardButton.Discard:
                e.accept()
            else:
                e.ignore()
                return
        self.playback.cleanup()
        self._timer.stop()
        e.accept()
