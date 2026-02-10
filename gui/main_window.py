"""Main window — Glitch Maker."""

import os, copy, uuid
from datetime import datetime
import numpy as np
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMessageBox, QPushButton, QLabel, QApplication,
    QMenu, QSpinBox, QSlider, QDialog, QCheckBox, QFrame, QScrollBar
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal as Signal
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QShortcut, QKeySequence

from gui.waveform_widget import WaveformWidget
from gui.timeline_widget import TimelineWidget
from gui.effects_panel import EffectsPanel
from gui.transport_bar import TransportBar
from gui.dialogs import RecordDialog, AboutDialog, FadeDialog
from gui.catalog_dialog import CatalogDialog
from gui.settings_dialog import AudioSettingsDialog, LanguageSettingsDialog, ThemeSettingsDialog
from gui.preset_dialog import (PresetCreateDialog, PresetManageDialog,
    TagManageDialog, ExportPresetDialog, ImportChooserDialog, HelpDialog)
from gui.spectrum_widget import SpectrumWidget
from gui.minimap_widget import MinimapWidget
from gui.effect_history import EffectHistoryPanel
from gui.progress_overlay import ProgressOverlay
from gui.automation_window import AutomationWindow

from core.audio_engine import (
    load_audio, export_audio, ensure_stereo, get_duration, format_time,
    ffmpeg_available, download_ffmpeg
)
from core.playback import PlaybackEngine
from core.timeline import Timeline, AudioClip, _generate_distinct_color
from core.project import save_project, load_project
from core.preset_manager import PresetManager
from core.effects.utils import fade_in, fade_out, apply_envelope_fade

from plugins.loader import load_plugins

from utils.config import (
    COLORS, APP_NAME, APP_VERSION, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    AUDIO_EXTENSIONS, ALL_EXTENSIONS, load_settings, save_settings,
    set_theme, get_theme, checkbox_css
)
from utils.translator import t, set_language, get_language
from utils.logger import get_logger

_log = get_logger("main_window")


# ═══ Background worker for heavy operations ═══

class _EffectWorker(QThread):
    done = Signal(object)
    error = Signal(str)
    def __init__(self, fn, args, kwargs, parent=None):
        super().__init__(parent)
        self.fn, self.args, self.kwargs = fn, args, kwargs
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.done.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _FFmpegDownloadThread(QThread):
    status = Signal(str)
    def run(self):
        try:
            self.status.emit("Downloading FFmpeg...")
            download_ffmpeg()
            self.status.emit("FFmpeg ready ✓")
        except Exception as e:
            self.status.emit(f"FFmpeg : {e}")


# Clip color palette
CLIP_COLORS = ["#533483", "#e94560", "#0f3460", "#16c79a", "#ff6b35",
               "#c74b50", "#00b4d8", "#9b5de5", "#f15bb5", "#00f5d4"]


class MainWindow(QMainWindow):
    _sig_playback_done = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.setAcceptDrops(True)

        # Audio state
        self.audio_data: np.ndarray | None = None
        self.sample_rate: int = 44100
        self.current_filepath: str = ""
        self.project_filepath: str = ""
        self.timeline = Timeline()
        self.playback = PlaybackEngine()
        self._sig_playback_done.connect(self._on_playback_done_gui)
        self.playback.on_playback_finished = lambda: self._sig_playback_done.emit()
        self._unsaved = False
        self._was_playing_before_drag = False
        self.preset_manager = PresetManager()
        self._active_worker = None
        self._last_params: dict[str, dict] = {}

        # ── Non-destructive effect system (v4.4) ──
        self._base_audio: np.ndarray | None = None     # original unmodified audio
        self._effect_ops: list[dict] = []               # list of ALL operations (effects + structural)
        self._ops_undo: list[dict] = []                 # undo stack (ops snapshots)
        self._ops_redo: list[dict] = []                 # redo stack
        self._initial_base_audio: np.ndarray | None = None  # audio at project start
        self._initial_clips: list = []                       # clips at project start
        self._clip_color_idx = 0                        # for different clip colors

        # Load effect plugins
        self._plugins = load_plugins()

        # Load theme
        settings = load_settings()
        if settings.get("theme") == "light":
            set_theme("light")

        self._build_ui()
        self._build_menus()
        self._connect()
        self._setup_shortcuts()
        self._refresh_presets()

        # Playhead timer 30fps
        self._timer = QTimer()
        self._timer.setInterval(16)  # ~60fps for tight audio-visual sync
        self._timer.timeout.connect(self._upd_playhead)
        self._timer.start()

        self.setStyleSheet(f"""
            QMainWindow {{ background: {COLORS['bg_dark']}; }}
            QStatusBar {{ background: {COLORS['bg_medium']}; color: {COLORS['text_dim']}; font-size: 11px; }}
            QMenuBar {{ background: {COLORS['bg_medium']}; color: {COLORS['text']}; font-size: 11px;
                border-bottom: 1px solid {COLORS['border']}; }}
            QMenuBar::item:selected {{ background: {COLORS['accent']}; }}
            QMenu {{ background: {COLORS['bg_medium']}; color: {COLORS['text']};
                border: 1px solid {COLORS['border']}; font-size: 11px; }}
            QMenu::item {{ padding: 5px 24px 5px 14px; min-width: 120px; }}
            QMenu::item:selected {{ background: {COLORS['accent']}; }}
            QMenu::separator {{ height: 1px; background: {COLORS['border']}; margin: 3px 8px; }}
            QToolTip {{ background: {COLORS['bg_medium']}; color: {COLORS['text']};
                border: 1px solid {COLORS['accent']}; padding: 6px; font-size: 11px; }}
            {checkbox_css()}
        """)
        self.statusBar().showMessage("Ready")

        if not ffmpeg_available():
            self._ffmpeg_thread = _FFmpegDownloadThread(self)
            self._ffmpeg_thread.status.connect(lambda msg: self.statusBar().showMessage(msg))
            self._ffmpeg_thread.start()

    # ══════ UI Build ══════

    def _build_ui(self):
        c = QWidget(); self.setCentralWidget(c)
        mlo = QHBoxLayout(c); mlo.setContentsMargins(0, 0, 0, 0); mlo.setSpacing(0)

        # ── Left panel: effects ──
        left_panel = QWidget()
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet(f"background: {COLORS['bg_panel']};")
        left_lo = QVBoxLayout(left_panel)
        left_lo.setContentsMargins(0, 0, 0, 0)
        left_lo.setSpacing(0)

        self.effects_panel = EffectsPanel()
        self.effects_panel.setObjectName("effectsPanel")
        left_lo.addWidget(self.effects_panel)

        mlo.addWidget(left_panel)

        # ─ vertical separator: effects | center ─
        vsep_left = QWidget()
        vsep_left.setFixedWidth(1)
        vsep_left.setStyleSheet(f"background: {COLORS['border']};")
        mlo.addWidget(vsep_left)

        # ── Center area ──
        center = QWidget()
        rl = QVBoxLayout(center); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)

        # Toolbar
        tb = QWidget(); tb.setFixedHeight(36)
        tb.setStyleSheet(f"background: {COLORS['bg_medium']}; border-bottom: 1px solid {COLORS['border']};")
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

        self.btn_metro = QPushButton("Metronome"); self.btn_metro.setFixedHeight(26)
        self.btn_metro.setCheckable(True); self.btn_metro.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_metro.setStyleSheet(_tss); self.btn_metro.clicked.connect(self._toggle_metronome)
        tlo.addWidget(self.btn_metro)

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

        self.btn_grid = QPushButton("Grid : Off"); self.btn_grid.setFixedHeight(26)
        self.btn_grid.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_grid.setStyleSheet(_tss); self.btn_grid.clicked.connect(self._show_grid_menu)
        tlo.addWidget(self.btn_grid)
        rl.addWidget(tb)

        # Minimap
        self.minimap = MinimapWidget()
        rl.addWidget(self.minimap)

        # Waveform
        self.waveform = WaveformWidget()
        rl.addWidget(self.waveform, stretch=3)

        # Spectrum
        self.spectrum = SpectrumWidget()
        self.spectrum.setVisible(False)
        rl.addWidget(self.spectrum)

        # ─ separator waveform | timeline ─
        sep_wt = QFrame(); sep_wt.setFrameShape(QFrame.Shape.HLine)
        sep_wt.setFixedHeight(1)
        sep_wt.setStyleSheet(f"background: {COLORS['border']}; border: none;")
        rl.addWidget(sep_wt)

        # Timeline
        self.timeline_w = TimelineWidget(self.timeline)
        rl.addWidget(self.timeline_w, stretch=1)

        # Timeline horizontal scrollbar
        self._tl_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self._tl_scrollbar.setFixedHeight(10)
        self._tl_scrollbar.setVisible(False)
        self._tl_scrollbar.setStyleSheet(
            f"QScrollBar:horizontal {{ background: {COLORS['bg_dark']}; height: 10px; border: none; }}"
            f"QScrollBar::handle:horizontal {{ background: {COLORS['border']}; border-radius: 4px; min-width: 30px; }}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}"
            f"QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}")
        self._tl_scrollbar.valueChanged.connect(self._on_tl_scroll)
        rl.addWidget(self._tl_scrollbar)

        # ─ separator timeline | transport ─
        sep_tt = QFrame(); sep_tt.setFrameShape(QFrame.Shape.HLine)
        sep_tt.setFixedHeight(1)
        sep_tt.setStyleSheet(f"background: {COLORS['border']}; border: none;")
        rl.addWidget(sep_tt)

        # Transport
        self.transport = TransportBar()
        rl.addWidget(self.transport)

        mlo.addWidget(center, stretch=1)

        # ─ vertical separator: center | history ─
        vsep_right = QWidget()
        vsep_right.setFixedWidth(1)
        vsep_right.setStyleSheet(f"background: {COLORS['border']};")
        mlo.addWidget(vsep_right)

        # ── Right panel: history ──
        self.effect_history = EffectHistoryPanel()
        self.effect_history.setObjectName("effectHistoryPanel")
        mlo.addWidget(self.effect_history)

        # Progress overlay
        self.progress_overlay = ProgressOverlay(center)
        self.progress_overlay.setVisible(False)

        # Automation window (floating, hidden by default)
        self._auto_win = AutomationWindow(self._plugins, parent=self)
        self._auto_win.hide()

    def _make_toolbar_btn(self, text):
        b = QPushButton(text); b.setFixedHeight(26)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton {{ background: {COLORS['button_bg']}; color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; border-radius: 4px;"
            f" font-size: 10px; padding: 0 8px; }}"
            f"QPushButton:hover {{ background: {COLORS['button_hover']}; border-color: {COLORS['accent']}; }}"
            f"QPushButton:disabled {{ color: {COLORS['text_dim']}; }}")
        return b

    def _build_menus(self):
        mb = self.menuBar(); mb.clear()

        # File
        fm = mb.addMenu(t("menu.file"))
        self._menu_action(fm, t("menu.file.new"), "Ctrl+N", self._new_project)
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
        self._menu_action(fm, t("menu.file.export_stems"), "", self._export_stems)
        fm.addSeparator()
        self._menu_action(fm, t("menu.file.export_presets"), "", self._export_presets)
        self._menu_action(fm, t("menu.file.import_presets"), "", self._import_presets)
        fm.addSeparator()
        self._menu_action(fm, t("menu.file.quit"), "Ctrl+Q", self.close)

        # View — all OFF by default
        vm = mb.addMenu(t("menu.view"))
        self._view_actions = {}
        panels = [
            ("spectrum",        t("view.spectrum"),      False),
            ("effect_history",  t("view.history"),       True),
            ("automation",      "Automations",           False),
        ]
        for key, label, default_on in panels:
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(default_on)
            act.toggled.connect(lambda checked, k=key: self._toggle_panel(k, checked))
            vm.addAction(act)
            self._view_actions[key] = act

        # Options
        om = mb.addMenu(t("menu.options"))
        self._menu_action(om, t("menu.options.audio"), "", self._settings_audio)
        self._menu_action(om, t("menu.options.language"), "", self._settings_language)
        self._menu_action(om, t("menu.options.theme"), "", self._settings_theme)
        om.addSeparator()
        self._menu_action(om, t("menu.options.metronome"), "", self._open_metronome_dialog)
        self._menu_action(om, t("menu.options.grid"), "", self._show_grid_menu)
        om.addSeparator()
        self._menu_action(om, t("menu.options.select_all"), "Ctrl+A", self._select_all)
        om.addSeparator()
        self._menu_action(om, t("menu.options.import_effect"), "", self._import_effect)

        # Effects
        efm = mb.addMenu(t("menu.effects"))
        from plugins.loader import plugins_grouped
        lang = get_language()
        grouped = plugins_grouped(self._plugins, lang)
        for i, (sec_label, sec_plugins) in enumerate(grouped):
            if i > 0: efm.addSeparator()
            for plugin in sec_plugins:
                name = plugin.get_name(lang)
                pid = plugin.id
                self._menu_action(efm, name, "", lambda _, pid=pid: self._on_effect(pid))
        efm.addSeparator()
        self._menu_action(efm, t("menu.effects.catalog"), "", self._catalog)
        self._menu_action(efm, t("menu.options.import_effect"), "", self._import_effect)

        # Help
        hm = mb.addMenu(t("menu.help"))
        self._menu_action(hm, t("menu.help.manual"), "", self._open_manual)
        self._menu_action(hm, t("menu.help.about"), "", lambda: AboutDialog(self).exec())

    def _menu_action(self, menu, text, shortcut, slot) -> QAction:
        a = menu.addAction(text)
        if shortcut: a.setShortcut(shortcut)
        a.triggered.connect(slot); return a

    def _setup_shortcuts(self):
        for key, slot in [
            (Qt.Key.Key_Space, self._toggle_play),
            (Qt.Key.Key_Escape, self._deselect),
            (Qt.Key.Key_Delete, self._delete_selected_clip),
        ]:
            s = QShortcut(QKeySequence(key), self)
            s.setContext(Qt.ShortcutContext.WindowShortcut)
            s.activated.connect(slot)
        for seq, slot in [
            ("Ctrl+Z", self._do_undo), ("Ctrl+Y", self._do_redo),
            ("M", self._add_marker_at_cursor),
            ("Ctrl+Right", self._goto_next_marker),
            ("Ctrl+Left", self._goto_prev_marker),
        ]:
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.ShortcutContext.WindowShortcut)
            s.activated.connect(slot)

    def _connect(self):
        self.transport.play_clicked.connect(self._play)
        self.transport.pause_clicked.connect(self._pause)
        self.transport.stop_clicked.connect(self._stop)
        self.transport.volume_changed.connect(self.playback.set_volume)
        self.transport.add_audio_clicked.connect(self._add_audio_to_timeline)
        self.waveform.position_clicked.connect(self._seek)
        self.waveform.selection_changed.connect(self._on_sel)
        self.waveform.drag_started.connect(self._on_drag_start)
        self.waveform.zoom_changed.connect(self._on_waveform_zoom)
        self.waveform.cut_silence_requested.connect(self._cut_replace_silence)
        self.waveform.cut_splice_requested.connect(self._cut_splice)
        self.effects_panel.effect_clicked.connect(self._on_effect)
        self.effects_panel.catalog_clicked.connect(self._catalog)
        self.effects_panel.import_clicked.connect(self._import_effect)
        self.effects_panel.export_clicked.connect(self._export_presets)
        self.effects_panel.preset_clicked.connect(self._on_preset)
        self.effects_panel.preset_new_clicked.connect(self._new_preset)
        self.effects_panel.preset_manage_clicked.connect(self._manage_presets)
        self.effects_panel.quick_apply.connect(self._quick_apply)
        self.timeline_w.clip_selected.connect(self._on_clip_sel)
        self.timeline_w.split_requested.connect(self._split_clip)
        self.timeline_w.duplicate_requested.connect(self._dup_clip)
        self.timeline_w.delete_requested.connect(self._del_clip)
        self.timeline_w.fade_in_requested.connect(self._fi_clip)
        self.timeline_w.fade_out_requested.connect(self._fo_clip)
        self.timeline_w.clips_reordered.connect(self._on_reorder)
        self.timeline_w.seek_requested.connect(self._seek_from_timeline)
        self.timeline_w.zoom_changed.connect(self._on_timeline_zoom)
        self.minimap.region_clicked.connect(self._on_minimap_click)
        # v4.4: non-destructive ops signals
        self.effect_history.op_deleted.connect(self._delete_op)
        self.effect_history.op_toggled.connect(self._toggle_op)
        self.effect_history.clear_all.connect(self._clear_all_ops)

        # Automation window signals
        self._auto_win.automation_added.connect(self._add_automation)
        self._auto_win.automation_edited.connect(self._edit_automation)
        self._auto_win.automation_deleted.connect(self._delete_op)
        self._auto_win.automation_toggled.connect(self._toggle_op)
        self._auto_win.preview_requested.connect(self._preview_automation)
        self._auto_win.preview_base_requested.connect(self._preview_base_region)
        self._auto_win.stop_requested.connect(self._stop)
        self._auto_win.window_closed.connect(self._on_auto_win_closed)
        self._auto_win.set_playback_engine(self.playback)
        self.transport.automations_clicked.connect(self._toggle_auto_window)

    def _update_undo_labels(self):
        has_u = bool(self._ops_undo)
        has_r = bool(self._ops_redo)
        self.btn_undo.setEnabled(has_u)
        self.btn_redo.setEnabled(has_r)
        if has_u:
            desc = self._ops_undo[-1].get("desc", "")
            self.btn_undo.setToolTip(f"Undo : {desc}")
        if has_r:
            desc = self._ops_redo[-1].get("desc", "")
            self.btn_redo.setToolTip(f"Redo : {desc}")

    # ══════ Waveform Scroll ══════

    def _on_waveform_zoom(self, zoom, offset):
        if zoom > 1.01:
            if self.audio_data is not None:
                self.minimap.set_view(zoom, offset)
        else:
            self.minimap.set_view(1.0, 0.0)

    def _on_timeline_zoom(self, zoom, offset):
        """Timeline wheel zoom → update its own scrollbar only."""
        if zoom > 1.01:
            self._tl_scrollbar.setVisible(True)
            self._tl_scrollbar.blockSignals(True)
            visible = 1.0 / zoom
            self._tl_scrollbar.setRange(0, 10000)
            self._tl_scrollbar.setPageStep(int(visible * 10000))
            self._tl_scrollbar.setValue(int(offset / max(1.0 - visible, 0.0001) * 10000))
            self._tl_scrollbar.blockSignals(False)
        else:
            self._tl_scrollbar.setVisible(False)

    def _on_tl_scroll(self, value):
        """Timeline scrollbar → update timeline offset."""
        zoom = self.timeline_w._zoom
        if zoom <= 1.01:
            return
        visible = 1.0 / zoom
        max_offset = 1.0 - visible
        offset = (value / 10000.0) * max_offset
        self.timeline_w.set_zoom(zoom, offset)

    def _on_wave_scroll(self, value):
        """Legacy — no longer used since scrollbar removed."""
        pass

    # ══════ Metronome & Grid ══════

    def _toggle_metronome(self):
        self.playback.toggle_metronome(self.bpm_spin.value())

    def _adjust_bpm(self, delta):
        self.bpm_spin.setValue(self.bpm_spin.value() + delta)

    def _on_bpm_changed(self, val):
        self.playback.bpm = val
        if self.playback.metronome_on:
            self.playback.toggle_metronome(val)
            self.playback.toggle_metronome(val)
        if self.waveform.grid_subdivisions > 0:
            self.waveform.bpm = val
            self.waveform.update()

    def _show_grid_menu(self):
        m = QMenu(self)
        m.setStyleSheet(
            f"QMenu {{ background: {COLORS['bg_medium']}; color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; font-size: 11px; }}"
            f"QMenu::item {{ padding: 5px 16px; }}"
            f"QMenu::item:selected {{ background: {COLORS['accent']}; }}")
        for label, subdiv in [
            ("Off", 0), ("1 bar", 1), ("1/2", 2), ("1/4", 4),
            ("1/8", 8), ("1/16", 16), ("1/32", 32),
        ]:
            a = m.addAction(f"Grid : {label}")
            a.triggered.connect(lambda _, l=label, s=subdiv: self._set_grid(l, s))
        m.exec(self.btn_grid.mapToGlobal(self.btn_grid.rect().bottomLeft()))

    def _set_grid(self, label, subdiv):
        self.btn_grid.setText(f"Grid : {label}")
        bpm = self.bpm_spin.value()
        self.waveform.set_grid(subdiv > 0, bpm, 4, subdiv if subdiv > 0 else 1)
        self.statusBar().showMessage(f"Grid : {label}" if subdiv else "Grid : off")

    def _open_metronome_dialog(self):
        from PyQt6.QtWidgets import QGroupBox
        d = QDialog(self); d.setWindowTitle(t("metro.title")); d.setFixedSize(380, 300)
        d.setStyleSheet(f"QDialog {{ background: {COLORS['bg_medium']}; }}"
                        f" QLabel {{ color: {COLORS['text']}; font-size: 12px; }}"
                        f" {checkbox_css()}")
        lo = QVBoxLayout(d)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(12)

        on_cb = QCheckBox(t("metro.enable")); on_cb.setChecked(self.playback.metronome_on)
        lo.addWidget(on_cb)

        # BPM row: label + editable spin
        bpm_row = QHBoxLayout()
        bpm_lbl = QLabel("BPM:")
        bpm_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: bold;")
        bpm_row.addWidget(bpm_lbl)
        bpm_spin = QSpinBox()
        bpm_spin.setRange(20, 300)
        bpm_spin.setValue(self.bpm_spin.value())
        bpm_spin.setFixedSize(90, 30)
        bpm_spin.setStyleSheet(
            f"QSpinBox {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; border-radius: 4px;"
            f" font-size: 12px; padding: 2px 6px; }}"
            f"QSpinBox:focus {{ border-color: {COLORS['accent']}; }}")
        bpm_row.addWidget(bpm_spin)
        bpm_row.addStretch()
        lo.addLayout(bpm_row)

        # Volume group with slider + percentage
        grp = QGroupBox(t("metro.volume"))
        grp.setStyleSheet(f"QGroupBox {{ color: {COLORS['accent']}; border: 1px solid {COLORS['border']};"
                          f" border-radius: 4px; margin-top: 8px; padding-top: 18px; font-size: 12px; }}"
                          f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; }}")
        gl = QVBoxLayout(grp)
        vol_row = QHBoxLayout()
        vol_slider = QSlider(Qt.Orientation.Horizontal)
        vol_slider.setRange(0, 100); vol_slider.setValue(int(self.playback.metronome_vol * 100))
        vol_row.addWidget(vol_slider)
        vol_pct = QLabel(f"{vol_slider.value()}%")
        vol_pct.setFixedWidth(40)
        vol_pct.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 11px;")
        vol_slider.valueChanged.connect(lambda v: vol_pct.setText(f"{v}%"))
        vol_row.addWidget(vol_pct)
        gl.addLayout(vol_row)
        lo.addWidget(grp)

        lo.addStretch()
        row = QHBoxLayout()
        btn_ok = QPushButton(t("dialog.apply")); btn_ok.setFixedHeight(34)
        btn_ok.setStyleSheet(f"QPushButton {{ background: {COLORS['accent']}; color: white;"
                             f" border: none; border-radius: 5px; font-weight: bold;"
                             f" font-size: 13px; padding: 0 24px; }}"
                             f"QPushButton:hover {{ background: {COLORS['accent_hover']}; }}")
        btn_ok.clicked.connect(d.accept)
        row.addStretch(); row.addWidget(btn_ok)
        lo.addLayout(row)
        if d.exec() == d.DialogCode.Accepted:
            self.playback.metronome_vol = vol_slider.value() / 100.0
            new_bpm = bpm_spin.value()
            self.bpm_spin.setValue(new_bpm)
            if on_cb.isChecked() != self.playback.metronome_on:
                self.playback.toggle_metronome(new_bpm)
            self.btn_metro.setChecked(self.playback.metronome_on)

    # ══════ Playback ══════

    def _toggle_play(self):
        if self.audio_data is None: return
        try:
            if self.playback.is_playing:
                self._pause()
            else:
                self._play()
        except Exception as ex:
            _log.error("Toggle play error: %s", ex)

    def _play(self):
        if self.audio_data is None: return
        try:
            s, e = self._sel_range()
            if self.playback.is_paused:
                # Check if selection changed while paused
                old_loop_s = self.playback.loop_start
                old_loop_e = self.playback.loop_end
                if s is not None and (s != old_loop_s or e != old_loop_e):
                    # New/different selection → play in new zone
                    self.playback.play_selection(s, e)
                elif s is None and old_loop_s is not None:
                    # Selection cleared → resume without loop
                    self.playback.loop_start = None
                    self.playback.loop_end = None
                    self.playback.looping = False
                    self.playback.resume()
                else:
                    # Same selection or no selection → just resume
                    self.playback.resume()
                self.transport.set_playing(True)
                return
            if s is not None:
                self.playback.play_selection(s, e)
            else:
                # Start from anchor (blue bar) if set
                anchor = self.waveform._anchor
                if anchor is not None:
                    self.playback.play(start_pos=anchor)
                else:
                    self.playback.play()
            self.transport.set_playing(True)
        except Exception as ex:
            _log.error("Play error: %s", ex)

    def _pause(self):
        self.playback.pause()
        self.transport.set_playing(False)

    def _stop(self):
        try:
            was_playing = self.playback.is_playing
            self.playback.stop()
            if was_playing:
                # Return to anchor (blue bar) or selection start, or 0
                anchor = self.waveform._anchor
                s, e = self._sel_range()
                pos = anchor if anchor is not None else (s if s is not None else 0)
                self.playback.seek(pos)
                self.waveform.set_playhead(pos)
                self.timeline_w.set_playhead(pos, self.sample_rate)
                self.transport.set_playing(False)
                if self.audio_data is not None:
                    t_str = format_time(pos / self.sample_rate)
                    dur = format_time(get_duration(self.audio_data, self.sample_rate))
                    self.transport.set_time(t_str, dur)
        except Exception as ex:
            _log.error("Stop error: %s", ex)

    def _seek(self, pos):
        """Seek to sample position (pos = sample index from waveform click)."""
        if self.audio_data is None: return
        try:
            total = len(self.audio_data)
            sample = max(0, min(int(pos), total - 1))
            self.playback.seek(sample)
            self.waveform.set_playhead(sample)
            self.waveform.set_anchor(sample)
            self.timeline_w.set_playhead(sample, self.sample_rate)
            self.timeline_w.set_anchor(sample)
            t_str = format_time(sample / self.sample_rate)
            dur = format_time(get_duration(self.audio_data, self.sample_rate))
            self.transport.set_time(t_str, dur)
            # If was playing before click, resume from new anchor
            if getattr(self, '_was_playing_before_drag', False):
                self._was_playing_before_drag = False
                self.playback.play(start_pos=sample)
                self.transport.set_playing(True)
        except Exception as ex:
            _log.error("Seek error: %s", ex)

    def _on_drag_start(self):
        if self.playback.is_playing:
            self._was_playing_before_drag = True
            self._pause()
        else:
            self._was_playing_before_drag = False

    def _seek_from_timeline(self, pos):
        if self.audio_data is None: return
        try:
            total = len(self.audio_data)
            sample = max(0, min(int(pos), total - 1))
            self.playback.seek(sample)
            self.waveform.set_playhead(sample)
            self.waveform.set_anchor(sample)
            self.timeline_w.set_playhead(sample, self.sample_rate)
            t_str = format_time(sample / self.sample_rate)
            dur = format_time(get_duration(self.audio_data, self.sample_rate))
            self.transport.set_time(t_str, dur)
        except Exception as ex:
            _log.error("Timeline seek error: %s", ex)

    def _on_sel(self, s, e):
        """Handle selection from waveform (s, e = sample indices)."""
        if self.audio_data is None: return
        try:
            total = len(self.audio_data)
            s_samp = max(0, min(int(s), total))
            e_samp = max(s_samp, min(int(e), total))
            if e_samp - s_samp < 64:
                self.transport.set_selection_info("")
                # If was playing, resume from click position
                if getattr(self, '_was_playing_before_drag', False):
                    self._was_playing_before_drag = False
                    self.playback.play(start_pos=s_samp)
                    self.transport.set_playing(True)
                return
            self.waveform.set_selection(s_samp, e_samp)
            dur_s = (e_samp - s_samp) / self.sample_rate
            self.transport.set_selection_info(f"Sel : {format_time(dur_s)}")
            fav = getattr(self.effects_panel, 'favorites', [])
            if fav:
                names = []
                for fid in fav[:3]:
                    p = self._find_plugin(fid)
                    if p: names.append(p.get_name(get_language()))
                self.toolbar_info.setText(f"★ {', '.join(names)}")
            # If was playing before drag, resume in selection
            if getattr(self, '_was_playing_before_drag', False):
                self._was_playing_before_drag = False
                self.playback.stop()
                self.playback.play_selection(s_samp, e_samp)
                self.transport.set_playing(True)
        except Exception as ex:
            _log.error("Selection error: %s", ex)

    def _on_playback_done_gui(self):
        """Called on GUI thread when playback finishes (via signal).
        If no selection active, loop from beginning instead of stopping."""
        s, e = self._sel_range()
        if s is None and self.audio_data is not None:
            # No selection → loop from start
            self.playback.play(start_pos=0)
            self.waveform.set_playhead(0)
            self.timeline_w.set_playhead(0, self.sample_rate)
            self.transport.set_playing(True)
            return
        self.transport.set_playing(False)
        self._was_playing = False

    def _upd_playhead(self):
        try:
            if not self.playback.is_playing:
                if hasattr(self, '_was_playing') and self._was_playing:
                    self.transport.set_playing(False)
                    self._was_playing = False
                return
            self._was_playing = True
            pos = self.playback.current_position
            if self.audio_data is not None and len(self.audio_data) > 0:
                self.waveform.set_playhead(pos)
                self.timeline_w.set_playhead(pos, self.sample_rate)
                t_str = format_time(pos / self.sample_rate)
                dur = format_time(get_duration(self.audio_data, self.sample_rate))
                self.transport.set_time(t_str, dur)
                self.transport.set_playing(True)
                chunk = self.audio_data[max(0, pos - 2048):pos + 2048]
                if len(chunk) > 0:
                    self.spectrum.update_spectrum(chunk, self.sample_rate)
        except Exception as ex:
            _log.warning("Update playhead: %s", ex)

    def _sel_range(self):
        s, e = self.waveform.selection_start, self.waveform.selection_end
        if s is not None and e is not None and e > s and (e - s) >= 64:
            return s, e
        return None, None

    def _deselect(self):
        self.waveform.clear_selection()
        self.transport.set_selection_info("")
        self.toolbar_info.setText("")
        for c in self.timeline.clips:
            c._selected = False
        self.timeline_w.update()

    # ══════ Open ══════

    def _check_unsaved(self):
        """If there are unsaved changes, ask user. Returns True if safe to proceed."""
        if not self._unsaved or self.audio_data is None:
            return True
        r = QMessageBox.question(
            self, APP_NAME, t("confirm.unsaved"),
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel)
        if r == QMessageBox.StandardButton.Save:
            self._save()
            return True
        elif r == QMessageBox.StandardButton.Discard:
            return True
        return False  # Cancel

    def _new_project(self):
        """Reset everything to a blank state."""
        if not self._check_unsaved():
            return
        self._stop()
        self.audio_data = None
        self._base_audio = None
        self.sample_rate = 44100
        self.current_filepath = ""
        self.project_filepath = ""
        self.timeline.clear()
        self._effect_ops.clear()
        self._ops_undo.clear()
        self._ops_redo.clear()
        self._clip_color_idx = 0
        self._unsaved = False
        # Clear waveform display
        self.waveform.audio_data = None
        self.waveform._anchor = None
        self.waveform._playhead = 0
        self.waveform.selection_start = None
        self.waveform.selection_end = None
        self.waveform._cache = None
        self.waveform.reset_zoom()
        # Clear minimap
        self.minimap._audio = None
        self.minimap._cache = None
        self.minimap.setVisible(False)
        self.minimap.update()
        # Clear timeline
        self.timeline_w._anchor_sample = None
        self.timeline_w._playhead_sample = 0
        self.timeline_w._zoom = 1.0
        self.timeline_w._offset = 0.0
        self.timeline_w.update()
        self._tl_scrollbar.setVisible(False)
        # Reset transport
        self.transport.set_time("00:00.00", "00:00.00")
        self.transport.set_selection_info("")
        self.transport.set_playing(False)
        # Reset spectrum
        if hasattr(self, 'spectrum'):
            self.spectrum.update()
        self._sync_history_chain()
        self._update_undo_labels()
        self.waveform.update()
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        self.statusBar().showMessage(t("status.new_project"))

    def _open(self):
        if not self._check_unsaved():
            return
        exts_list = " ".join(["*" + e for e in sorted(ALL_EXTENSIONS)])
        fp, _ = QFileDialog.getOpenFileName(
            self, t("menu.file.open"), "",
            f"Audio & Projects ({exts_list});;All files (*)")
        if not fp: return
        ext = os.path.splitext(fp)[1].lower()
        if ext == ".gspi":
            self._load_gspi(fp)
        elif ext in AUDIO_EXTENSIONS:
            self._load_audio(fp)

    def _load_audio(self, fp):
        try:
            self._stop()
            data, sr = load_audio(fp)
            st = ensure_stereo(data)
            name = os.path.splitext(os.path.basename(fp))[0]

            self.audio_data, self.sample_rate = st, sr
            self.current_filepath = fp
            self.timeline.clear()
            self._clip_color_idx = 0
            color = CLIP_COLORS[self._clip_color_idx % len(CLIP_COLORS)]
            self._clip_color_idx += 1
            self.timeline.add_clip(st, sr, name=name, position=0, color=color)
            self._base_audio = st.copy()
            self._effect_ops.clear()
            self._store_initial_state()

            self._ops_undo.clear(); self._ops_redo.clear()
            self._update_undo_labels()
            self.waveform.selection_start = None
            self.waveform.selection_end = None
            self.waveform._anchor = None
            self.transport.set_selection_info("")
            self._refresh_all()
            self._sync_history_chain()
            self._unsaved = False
            self.setWindowTitle(f"{APP_NAME} — {os.path.basename(fp)}")
            self.statusBar().showMessage(t("status.loaded").format(f=os.path.basename(fp)))
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, str(e))

    def _add_audio_to_timeline(self):
        """Add an additional audio file as a new clip appended to the timeline."""
        exts_list = " ".join(["*" + e for e in sorted(AUDIO_EXTENSIONS)])
        fp, _ = QFileDialog.getOpenFileName(
            self, "Add audio to timeline", "",
            f"Audio ({exts_list});;All files (*)")
        if not fp:
            return
        try:
            data, sr = load_audio(fp)
            st = ensure_stereo(data)
            name = os.path.splitext(os.path.basename(fp))[0]
            if self.audio_data is None:
                self._load_audio(fp)
                return
            self._push_undo("Add clip")
            # Resample to match project sample rate if needed
            if sr != self.sample_rate and self.sample_rate > 0:
                from scipy.signal import resample as scipy_resample
                new_len = int(len(st) * self.sample_rate / sr)
                if new_len > 0:
                    channels = []
                    for ch in range(st.shape[1] if st.ndim > 1 else 1):
                        ch_data = st[:, ch] if st.ndim > 1 else st
                        channels.append(scipy_resample(ch_data, new_len))
                    st = np.column_stack(channels).astype(np.float32)
                sr = self.sample_rate
            color = CLIP_COLORS[self._clip_color_idx % len(CLIP_COLORS)]
            self._clip_color_idx += 1
            self.timeline.add_clip(st, sr, name=name, color=color)
            self._rebuild_audio()
            self._base_audio = self.audio_data.copy()
            self._add_structural_op("add_clip", f"➕ {name}")
            self._refresh_all()
            self._unsaved = True
            self.statusBar().showMessage(f"Added: {os.path.basename(fp)}")
        except Exception as e:
            _log.error("Add audio error: %s", e, exc_info=True)
            QMessageBox.critical(self, APP_NAME, str(e))

    def _load_gspi(self, fp):
        try:
            self._stop()
            result = load_project(fp)
            tl = result["timeline"]
            sr = result["sr"]
            self.timeline, self.sample_rate = tl, sr
            self.current_filepath = result.get("source", "")
            self.project_filepath = fp
            self._base_audio = result.get("base_audio")
            self._effect_ops = result.get("effect_ops", [])
            self._ops_undo = result.get("undo_stack", [])
            self._ops_redo = result.get("redo_stack", [])
            self._rebuild_audio()
            self._store_initial_state()
            if self._base_audio is not None and self._effect_ops:
                self._render_from_ops()
            self._update_undo_labels()
            self._sync_history_chain()
            self._unsaved = False
            self.setWindowTitle(
                f"{APP_NAME} — {os.path.splitext(os.path.basename(fp))[0]}")
            self.statusBar().showMessage(t("status.project").format(f=os.path.basename(fp)))
        except Exception as e:
            _log.error("Load project error: %s", e, exc_info=True)
            QMessageBox.critical(self, APP_NAME, str(e))

    # ══════ Save ══════

    def _save(self):
        if not self.timeline.clips: return
        if self.project_filepath:
            self._do_save(self.project_filepath)
        else:
            self._save_as()

    def _save_as(self):
        if not self.timeline.clips: return
        fp, _ = QFileDialog.getSaveFileName(
            self, t("menu.file.save_as"), "project.gspi",
            "Glitch Maker Project (*.gspi)")
        if fp:
            if not fp.endswith(".gspi"): fp += ".gspi"
            self._do_save(fp)

    def _do_save(self, fp):
        try:
            save_project(
                fp, self.timeline, self.sample_rate, self.current_filepath,
                base_audio=self._base_audio,
                effect_ops=self._effect_ops,
                undo_stack=self._ops_undo,
                redo_stack=self._ops_redo)
            self.project_filepath = fp
            self._unsaved = False
            self.statusBar().showMessage(t("status.saved").format(f=os.path.basename(fp)))
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
                self.statusBar().showMessage(t("status.exported").format(f=fp))
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, str(e))

    # ══════ Refresh ══════

    def _refresh_all(self):
        self.timeline_w.timeline = self.timeline
        self.timeline_w.sample_rate = self.sample_rate
        self.timeline_w.update()
        if self.audio_data is not None:
            self.waveform.set_audio(self.audio_data, self.sample_rate)
            self.minimap.set_audio(self.audio_data, self.sample_rate)
            self.playback.load(self.audio_data, self.sample_rate)
            self.transport.set_time(
                "00:00.00",
                format_time(get_duration(self.audio_data, self.sample_rate)))
        self.transport.set_selection_info("")

    def _rebuild_audio(self):
        rendered, sr = self.timeline.render()
        if len(rendered) > 0:
            self.audio_data, self.sample_rate = rendered, sr
        self._refresh_all()

    # ══════ Clip selection → waveform highlight ══════

    def _on_clip_sel(self, clip_id):
        for c in self.timeline.clips:
            if c.id == clip_id:
                self.waveform.set_clip_highlight(c.position, c.end_position)
                self.waveform.set_selection(c.position, c.end_position)
                dur = format_time(c.duration_seconds)
                self.transport.set_selection_info(f"Sel : {dur}")
                self.playback.seek(c.position)
                self.waveform.set_playhead(c.position)
                self.timeline_w.set_playhead(c.position, self.sample_rate)
                return
        self.waveform.set_clip_highlight(None, None)

    # ══════ Effects — Non-destructive ops system (v4.4) ══════

    def _find_plugin(self, effect_id):
        # Direct lookup by id (dict key)
        if effect_id in self._plugins:
            return self._plugins[effect_id]
        # Fallback: match by name
        for p in self._plugins.values():
            for lang in ["en", "fr"]:
                if p.get_name(lang).lower() == effect_id.lower(): return p
        return None

    def _on_effect(self, effect_id):
        """Open effect dialog and add as non-destructive op."""
        if self.audio_data is None:
            QMessageBox.warning(self, APP_NAME, t("error.no_audio")); return
        plugin = self._find_plugin(effect_id)
        if not plugin: return

        try:
            if self.playback.is_playing: self._stop()
            self.playback.suspend_stream()
        except Exception:
            pass

        try:
            s, e = self._sel_range()
            is_global = (s is None)

            d = plugin.dialog_class(self)
            preview_seg = self.audio_data if is_global else self.audio_data[s:e]
            if preview_seg is not None and len(preview_seg) > 0:
                try:
                    d.setup_preview(preview_seg, self.sample_rate, plugin.process_fn,
                                    output_device=self.playback.output_device)
                except Exception as pe:
                    _log.warning("Preview setup failed: %s", pe)

            accepted = d.exec() == d.DialogCode.Accepted
            try:
                self.playback.resume_stream()
            except Exception:
                pass
            if not accepted: return

            params = d.get_params()
            name = plugin.get_name(get_language())
            self._last_params[effect_id] = dict(params)

            # Create op
            op = {
                "uid": str(uuid.uuid4())[:8],
                "effect_id": effect_id,
                "params": dict(params),
                "start": s if not is_global else 0,
                "end": e if not is_global else len(self.audio_data),
                "is_global": is_global,
                "enabled": True,
                "timestamp": datetime.now().strftime("%d/%m %H:%M:%S"),
                "name": name,
                "color": plugin.color,
            }
            self._add_op(op)

        except Exception as e:
            _log.error("Effect error (%s): %s", effect_id, e, exc_info=True)
            try:
                self.playback.resume_stream()
            except Exception:
                pass
            QMessageBox.critical(self, APP_NAME,
                                 f"{t('error.effect_failed')}\n{e}")

    def _add_op(self, op):
        """Add a new effect operation and apply it."""
        self._push_undo(op["name"])
        self._effect_ops.append(op)
        # Apply just this one op on current audio (fast path)
        self._apply_single_op(op)
        self._sync_history_chain()
        self._unsaved = True
        self.statusBar().showMessage(t("status.effect").format(name=op["name"]))

    def _apply_single_op(self, op):
        """Apply a single op on current audio_data (fast, for new ops)."""
        if not op.get("enabled", True) or self.audio_data is None:
            return
        if op.get("type") == "automation":
            self._render_auto_op(op)
            self._update_clips_from_audio()
            self._refresh_all()
            return
        plugin = self._find_plugin(op["effect_id"])
        if not plugin: return
        s = op.get("start", 0)
        e = op.get("end", len(self.audio_data))
        s = max(0, min(s, len(self.audio_data)))
        e = max(s, min(e, len(self.audio_data)))
        if e - s < 1: return
        segment = self.audio_data[s:e].copy()
        try:
            mod = plugin.process_fn(segment, 0, len(segment),
                                    sr=self.sample_rate, **op.get("params", {}))
            if mod is None: return
            if mod.dtype != np.float32:
                mod = mod.astype(np.float32)
            if len(mod) == (e - s):
                self.audio_data[s:e] = mod
            else:
                before = self.audio_data[:s]
                after = self.audio_data[e:]
                parts = [p for p in [before, mod, after] if len(p) > 0]
                self.audio_data = np.concatenate(parts, axis=0).astype(np.float32)
            self._update_clips_from_audio()
            self._refresh_all()
        except Exception as ex:
            _log.error("Apply op error: %s", ex, exc_info=True)

    def _render_from_ops(self):
        """Re-render audio by restoring latest structural state then applying effects."""
        # Find the last enabled structural op
        last_struct_idx = -1
        for i, op in enumerate(self._effect_ops):
            if op.get("enabled", True) and op.get("type", "effect") in self._STRUCTURAL_TYPES:
                last_struct_idx = i

        # Restore base state
        if last_struct_idx >= 0:
            state = self._effect_ops[last_struct_idx].get("_state_after")
            if state:
                self._restore_state_snapshot(state)
                # base_audio from snapshot is already the rendered timeline
                self.audio_data = self._base_audio.copy() if self._base_audio is not None else None
            else:
                # Fallback: use current base_audio (project loaded without snapshots)
                if self._base_audio is None:
                    return
                self.audio_data = self._base_audio.copy()
        elif self._initial_base_audio is not None:
            # No structural ops: restore initial state
            self._restore_initial_state()
            self.audio_data = self._base_audio.copy() if self._base_audio is not None else None
        else:
            # Backward compat: no initial state stored
            if self._base_audio is None:
                return
            self.audio_data = self._base_audio.copy()

        if self.audio_data is None:
            return

        # Apply all enabled effect/automation ops AFTER the last structural op
        for i, op in enumerate(self._effect_ops):
            if i <= last_struct_idx:
                continue  # already baked into structural snapshot
            if not op.get("enabled", True):
                continue
            if op.get("type", "effect") in self._STRUCTURAL_TYPES:
                continue  # disabled structural ops are skipped
            # Automation ops
            if op.get("type") == "automation":
                self._render_auto_op(op)
                continue
            # Effect ops
            plugin = self._find_plugin(op.get("effect_id"))
            if not plugin:
                continue
            if op.get("is_global", False):
                s = 0
                e = len(self.audio_data)
            else:
                s = op.get("start", 0)
                e = op.get("end", len(self.audio_data))
                s = max(0, min(s, len(self.audio_data)))
                e = max(s, min(e, len(self.audio_data)))
            if e - s < 1:
                continue
            segment = self.audio_data[s:e].copy()
            try:
                mod = plugin.process_fn(segment, 0, len(segment),
                                        sr=self.sample_rate, **op.get("params", {}))
                if mod is None:
                    continue
                if mod.dtype != np.float32:
                    mod = mod.astype(np.float32)
                if len(mod) == (e - s):
                    self.audio_data[s:e] = mod
                else:
                    before = self.audio_data[:s]
                    after = self.audio_data[e:]
                    parts = [p for p in [before, mod, after] if len(p) > 0]
                    self.audio_data = np.concatenate(parts, axis=0).astype(np.float32)
            except Exception as ex:
                _log.warning("Render op %s failed: %s", op.get("name"), ex)
        self._update_clips_from_audio()
        self._refresh_all()

    def _render_auto_op(self, op):
        """Render a single automation op on self.audio_data (multi-param)."""
        from core.automation import apply_automation_multi
        plugin = self._find_plugin(op.get("effect_id"))
        if not plugin:
            return
        n = len(self.audio_data)
        s = op.get("start") or 0
        e = op.get("end") or n
        s = max(0, min(int(s), n))
        e = max(s, min(int(e), n))
        if e - s < 1:
            return
        auto_params = op.get("auto_params", [])
        # Legacy single-param fallback
        if not auto_params and op.get("auto_param"):
            auto_params = [{"key": op["auto_param"], "mode": "automated",
                            "default_val": op.get("auto_default", 0),
                            "target_val": op.get("auto_target", 1),
                            "curve_points": op.get("curve_points", [(0, 0), (1, 1)])}]
        if not auto_params:
            return
        try:
            self.audio_data = apply_automation_multi(
                self.audio_data, s, e,
                plugin.process_fn, auto_params, self.sample_rate)
        except Exception as ex:
            _log.warning("Automation render %s failed: %s", op.get("name"), ex)

    def _delete_op(self, uid):
        """Delete an op by uid and re-render.
        - Deleting a structural op: confirmation + truncate from that point.
        - Deleting an effect BEFORE the last structural op: just remove it (it was overridden).
        - Deleting an effect AFTER the last structural op: remove and re-render.
        """
        idx = next((i for i, o in enumerate(self._effect_ops) if o.get("uid") == uid), None)
        if idx is None:
            return
        op = self._effect_ops[idx]
        name = op.get("name", "?")
        is_structural = op.get("type", "effect") in self._STRUCTURAL_TYPES

        # Find the last structural op index
        last_struct_idx = -1
        for i, o in enumerate(self._effect_ops):
            if o.get("type", "effect") in self._STRUCTURAL_TYPES:
                last_struct_idx = i

        if is_structural:
            # Count how many ops will be lost
            ops_after = len(self._effect_ops) - idx - 1
            if ops_after > 0:
                reply = QMessageBox.question(
                    self, APP_NAME,
                    t("history.delete_structural").format(
                        name=name, count=ops_after),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No)
                if reply != QMessageBox.StandardButton.Yes:
                    return
            self._push_undo(f"Delete : {name}")
            self._effect_ops = self._effect_ops[:idx]
        elif idx < last_struct_idx:
            # Effect before the last structural op — it's overridden anyway.
            # Just remove it from the list, no re-render needed.
            self._push_undo(f"Delete : {name}")
            self._effect_ops.pop(idx)
            self._sync_history_chain()
            self._unsaved = True
            self.statusBar().showMessage(f"Removed : {name}")
            return
        else:
            # Effect after the last structural op — remove and re-render
            self._push_undo(f"Delete : {name}")
            self._effect_ops.pop(idx)

        self._render_from_ops()
        self._sync_history_chain()
        self._unsaved = True
        self.statusBar().showMessage(f"Removed : {name}")

    def _clear_all_ops(self):
        """Clear all history ops after confirmation."""
        if not self._effect_ops:
            return
        reply = QMessageBox.question(
            self, APP_NAME,
            t("history.clear_confirm").format(count=len(self._effect_ops)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._push_undo("Clear all history")
        self._effect_ops.clear()
        self._render_from_ops()
        self._sync_history_chain()
        self._unsaved = True
        self.statusBar().showMessage(t("history.cleared"))

    def _toggle_op(self, uid):
        """Toggle an op enabled/disabled and re-render.
        Structural ops cannot be toggled (UI prevents it)."""
        op = next((o for o in self._effect_ops if o.get("uid") == uid), None)
        if op is None: return
        # Structural ops cannot be toggled
        if op.get("type", "effect") in self._STRUCTURAL_TYPES:
            return
        self._push_undo(f"Toggle : {op['name']}")
        op["enabled"] = not op.get("enabled", True)
        self._render_from_ops()
        self._sync_history_chain()
        self._unsaved = True
        state = "ON" if op["enabled"] else "OFF"
        self.statusBar().showMessage(f"{op['name']} : {state}")

    def _move_op(self, uid, direction):
        """Move an op up or down in the chain and re-render.
        Cannot move across structural op boundaries or move structural ops."""
        idx = next((i for i, o in enumerate(self._effect_ops) if o.get("uid") == uid), None)
        if idx is None: return
        op = self._effect_ops[idx]
        # Structural ops cannot be moved
        if op.get("type", "effect") in self._STRUCTURAL_TYPES:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._effect_ops): return
        # Cannot swap with a structural op
        target = self._effect_ops[new_idx]
        if target.get("type", "effect") in self._STRUCTURAL_TYPES:
            return
        self._push_undo(f"Move : {op['name']}")
        self._effect_ops[idx], self._effect_ops[new_idx] = \
            self._effect_ops[new_idx], self._effect_ops[idx]
        self._render_from_ops()
        self._sync_history_chain()
        self._unsaved = True

    def _sync_history_chain(self):
        """Sync history panel and automation window with current ops."""
        # Compute the last structural op index so the panel can dim overridden ops
        last_struct_idx = -1
        for i, op in enumerate(self._effect_ops):
            if op.get("type", "effect") in self._STRUCTURAL_TYPES:
                last_struct_idx = i
        self.effect_history.set_ops(self._effect_ops, last_struct_idx)
        if self._auto_win.isVisible():
            self._auto_win.set_automations(self._effect_ops)
            audio = self.audio_data if self.audio_data is not None else self._base_audio
            if audio is not None:
                self._auto_win.set_audio(audio, self.sample_rate)

    def _sync_auto_audio(self):
        """Push current rendered audio to the automation window.
        Uses the fully-rendered audio_data so the preview reflects prior effects."""
        audio = self.audio_data if self.audio_data is not None else self._base_audio
        if audio is not None:
            self._auto_win.set_audio(audio, self.sample_rate)
            self._auto_win.set_automations(self._effect_ops)

    # ── Structural ops helpers ──

    _STRUCTURAL_TYPES = frozenset({
        "cut_silence", "cut_splice", "fade_in", "fade_out",
        "add_clip", "record", "delete_clip", "split", "duplicate", "reorder",
    })

    def _capture_state(self):
        """Capture current base_audio + clips as a state snapshot."""
        clips = []
        for c in self.timeline.clips:
            clips.append({
                "name": c.name,
                "data": c.audio_data.copy(),
                "position": c.position,
                "color": c.color,
                "fade_in_params": dict(c.fade_in_params) if c.fade_in_params else {},
                "fade_out_params": dict(c.fade_out_params) if c.fade_out_params else {},
                "bfi": c._audio_before_fade_in.copy() if c._audio_before_fade_in is not None else None,
                "bfo": c._audio_before_fade_out.copy() if c._audio_before_fade_out is not None else None,
            })
        return {
            "base": self._base_audio.copy() if self._base_audio is not None else None,
            "clips": clips,
        }

    def _restore_state_snapshot(self, snap):
        """Restore base_audio + clips from a state snapshot."""
        if snap is None:
            return
        self._base_audio = snap["base"].copy() if snap["base"] is not None else None
        self.timeline.clear()
        for cd in snap["clips"]:
            c = AudioClip(name=cd["name"], audio_data=cd["data"].copy(),
                          sample_rate=self.sample_rate,
                          position=cd["position"], color=cd["color"])
            c.fade_in_params = cd.get("fade_in_params", {})
            c.fade_out_params = cd.get("fade_out_params", {})
            c._audio_before_fade_in = cd["bfi"].copy() if cd.get("bfi") is not None else None
            c._audio_before_fade_out = cd["bfo"].copy() if cd.get("bfo") is not None else None
            self.timeline.clips.append(c)

    def _store_initial_state(self):
        """Store the initial project state for history replay."""
        self._initial_base_audio = self._base_audio.copy() if self._base_audio is not None else None
        self._initial_clips = []
        for c in self.timeline.clips:
            self._initial_clips.append({
                "name": c.name,
                "data": c.audio_data.copy(),
                "position": c.position,
                "color": c.color,
            })

    def _restore_initial_state(self):
        """Restore the initial project state."""
        if self._initial_base_audio is None:
            return
        self._base_audio = self._initial_base_audio.copy()
        self.timeline.clear()
        for cd in self._initial_clips:
            c = AudioClip(name=cd["name"], audio_data=cd["data"].copy(),
                          sample_rate=self.sample_rate,
                          position=cd["position"], color=cd["color"])
            self.timeline.clips.append(c)

    def _add_structural_op(self, op_type, name):
        """Add a structural action to the ops history with state snapshot."""
        import uuid as _uuid
        state = self._capture_state()
        op = {
            "uid": str(_uuid.uuid4())[:8],
            "type": op_type,
            "name": name,
            "timestamp": datetime.now().strftime("%d/%m %H:%M:%S"),
            "enabled": True,
            "is_global": True,
            "_state_after": state,
        }
        self._effect_ops.append(op)
        self._sync_history_chain()

    def _add_automation(self, op):
        """Add a new automation as an effect op."""
        import uuid as _uuid
        op["uid"] = str(_uuid.uuid4())[:8]
        op["enabled"] = True
        op["is_global"] = False
        op["color"] = "#7c3aed"
        op["timestamp"] = datetime.now().strftime("%d/%m %H:%M:%S")
        op["params"] = {}
        self._add_op(op)

    def _edit_automation(self, op):
        """Edit an existing automation op (multi-param)."""
        uid = op.get("uid")
        existing = next((o for o in self._effect_ops if o.get("uid") == uid), None)
        if existing is None:
            return
        self._push_undo(f"Edit: {op.get('name', 'Automation')}")
        for k in ("name", "effect_id", "auto_params", "start", "end"):
            if k in op:
                existing[k] = op[k]
        self._render_from_ops()
        self._sync_history_chain()
        self._unsaved = True

    def _preview_automation(self, config, start, end):
        """Preview a multi-param automation on the current audio (with all prior effects)."""
        if self.audio_data is None:
            return
        from core.automation import apply_automation_multi
        plugin = self._find_plugin(config.get("effect_id"))
        if not plugin:
            return
        auto_params = config.get("auto_params", [])
        if not auto_params:
            return
        try:
            preview = self.audio_data.copy()
            s = max(0, min(start, len(preview)))
            e = max(s, min(end, len(preview)))
            if e - s > 0:
                preview = apply_automation_multi(
                    preview, s, e,
                    plugin.process_fn, auto_params, self.sample_rate)
            self.playback.load(preview, self.sample_rate)
            self.playback.play_selection(s, e)
        except Exception as ex:
            _log.error("Automation preview error: %s", ex, exc_info=True)

    def _preview_base_region(self, start, end):
        """Play the current audio in a given region (no additional automation)."""
        audio = self.audio_data if self.audio_data is not None else self._base_audio
        if audio is None:
            return
        try:
            s = max(0, min(start, len(audio)))
            e = max(s, min(end, len(audio)))
            if e - s > 0:
                self.playback.load(audio, self.sample_rate)
                self.playback.play_selection(s, e)
        except Exception as ex:
            _log.error("Base preview error: %s", ex)

    def _run_plugin(self, effect_id, seg, sr, params):
        plugin = self._find_plugin(effect_id)
        if not plugin: return None
        return plugin.process_fn(seg, 0, len(seg), sr=sr, **params)

    def _set_busy(self, busy, text="Processing..."):
        if busy:
            self.progress_overlay.show_progress(text)
            QApplication.processEvents()
        else:
            self.progress_overlay.hide_progress()

    def _update_clips_from_audio(self):
        if not self.timeline.clips: return
        total = len(self.audio_data)
        if len(self.timeline.clips) == 1:
            c = self.timeline.clips[0]
            c.audio_data = ensure_stereo(self.audio_data)
            c.position = 0; return
        old_total = sum(c.duration_samples for c in self.timeline.clips)
        if old_total == 0: return
        ratio = total / old_total
        pos = 0
        for c in self.timeline.clips:
            new_len = int(c.duration_samples * ratio)
            new_len = min(new_len, total - pos)
            if new_len > 0:
                c.audio_data = ensure_stereo(self.audio_data[pos:pos + new_len])
            c.position = pos; pos += new_len
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
            if presets: tag_map[tag] = presets
        self.effects_panel.set_presets(tag_map, all_presets)

    def _on_preset(self, name):
        if self.audio_data is None:
            QMessageBox.warning(self, APP_NAME, t("error.no_audio")); return
        preset = self.preset_manager.get_preset(name)
        if not preset: return
        s, e = self._sel_range()
        if s is None: s, e = 0, len(self.audio_data)
        self._push_undo(f"Preset: {name}")
        self._set_busy(True, f"Preset: {name}")
        QApplication.processEvents()
        try:
            for fx in preset.get("effects", []):
                fx_name = fx["name"]
                params = dict(fx.get("params", {}))
                plugin = self._find_plugin(fx_name)
                if not plugin: continue
                op = {
                    "uid": str(uuid.uuid4())[:8],
                    "effect_id": plugin.id,
                    "params": params,
                    "start": s, "end": e,
                    "is_global": False, "enabled": True,
                    "timestamp": datetime.now().strftime("%d/%m %H:%M:%S"),
                    "name": f"{plugin.get_name(get_language())} ({name})",
                    "color": plugin.color,
                }
                self._effect_ops.append(op)
                self._apply_single_op(op)
            self._sync_history_chain()
            self._unsaved = True
            self.statusBar().showMessage(f"Preset: {name}")
        except Exception as ex:
            _log.error("Preset error: %s", ex)
            QMessageBox.critical(self, APP_NAME, str(ex))
        finally:
            self._set_busy(False)

    def _new_preset(self):
        tags = self.preset_manager.get_all_tags()
        d = PresetCreateDialog(tags, self, self.preset_manager)
        if d.exec() == d.DialogCode.Accepted:
            data = d.result_preset
            if data:
                self.preset_manager.add_preset(
                    data["name"], data.get("description", ""),
                    data.get("tags", []), data.get("effects", [])
                )
        # Always refresh (tags may have been modified even if dialog was cancelled)
        self._refresh_presets()

    def _manage_presets(self):
        d = PresetManageDialog(self.preset_manager, self)
        d.exec()
        self._refresh_presets()

    def _export_presets(self):
        d = ExportPresetDialog(self.preset_manager, self)
        d.exec()
        if d.exported:
            self.statusBar().showMessage("Preset exported")

    def _import_presets(self):
        fp, _ = QFileDialog.getOpenFileName(self, "Import Presets", "", "Presets (*.pspi);;JSON (*.json)")
        if fp:
            try:
                n, skipped = self.preset_manager.import_presets(fp)
                self._refresh_presets()
                msg = f"Imported {n} presets"
                if skipped:
                    msg += f" ({len(skipped)} skipped: already exist)"
                self.statusBar().showMessage(msg)
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, str(e))

    # ══════ Quick Apply ══════

    def _quick_apply(self, effect_id):
        if self.audio_data is None: return
        params = self._last_params.get(effect_id)
        if not params:
            self._on_effect(effect_id); return
        plugin = self._find_plugin(effect_id)
        if not plugin: return
        s, e = self._sel_range()
        if s is None:
            QMessageBox.warning(self, APP_NAME, t("quick_apply.no_selection")); return
        name = plugin.get_name(get_language())
        op = {
            "uid": str(uuid.uuid4())[:8],
            "effect_id": effect_id,
            "params": dict(params),
            "start": s, "end": e,
            "is_global": False, "enabled": True,
            "timestamp": datetime.now().strftime("%d/%m %H:%M:%S"),
            "name": f"{name} ⚡", "color": plugin.color,
        }
        self._add_op(op)

    # ══════ Chain Apply ══════

    # ══════ Markers ══════

    def _add_marker_at_cursor(self):
        if self.audio_data is None: return
        pos = self.playback.current_position
        ts = format_time(pos / self.sample_rate)
        self.waveform.add_marker(ts, pos)
        self.statusBar().showMessage(f"Marker @ {ts}")

    def _goto_next_marker(self):
        markers = sorted([m["position"] for m in self.waveform.get_markers()])
        pos = self.playback.current_position
        for m in markers:
            if m > pos + 100:
                self.playback.seek(m)
                self.waveform.set_playhead(m)
                self.timeline_w.set_playhead(m, self.sample_rate)
                return

    def _goto_prev_marker(self):
        markers = sorted([m["position"] for m in self.waveform.get_markers()], reverse=True)
        pos = self.playback.current_position
        for m in markers:
            if m < pos - 100:
                self.playback.seek(m)
                self.waveform.set_playhead(m)
                self.timeline_w.set_playhead(m, self.sample_rate)
                return

    # ══════ Minimap ══════

    def _on_minimap_click(self, offset):
        self.waveform.set_scroll_offset(offset)
        self.minimap.set_view(self.waveform._zoom, offset)

    # ══════ Panel visibility ══════

    def _on_auto_win_closed(self):
        """Called when user closes the automation window with X."""
        act = self._view_actions.get("automation")
        if act and act.isChecked():
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)

    def _toggle_auto_window(self):
        """Toggle automation window from the transport button."""
        if self._auto_win.isVisible():
            self._auto_win.hide()
            self._on_auto_win_closed()
        else:
            self._auto_win.show()
            self._auto_win.raise_()
            self._sync_auto_audio()
            act = self._view_actions.get("automation")
            if act and not act.isChecked():
                act.blockSignals(True)
                act.setChecked(True)
                act.blockSignals(False)

    def _toggle_panel(self, key, visible):
        panel_map = {
            "spectrum":       [self.spectrum],
            "effect_history": [self.effect_history],
        }
        if key == "automation":
            if visible:
                self._auto_win.show()
                self._auto_win.raise_()
                self._sync_auto_audio()
            else:
                self._auto_win.hide()
            return
        widgets = panel_map.get(key, [])
        for w in widgets:
            w.setVisible(visible)

    # ══════ Timeline ops ══════

    def _on_reorder(self):
        self._push_undo("Reorder")
        self._rebuild_audio()
        self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
        self._add_structural_op("reorder", "↕ Reorder")
        self._unsaved = True

    def _split_clip(self, cid, pos):
        clip = self._find_clip(cid)
        if clip is None: return
        local = pos - clip.position
        if local <= 0 or local >= clip.duration_samples: return
        self._push_undo("Split")
        d1 = clip.audio_data[:local]
        d2 = clip.audio_data[local:]
        idx = self.timeline.clips.index(clip)
        c1 = AudioClip(name=f"{clip.name}_L", audio_data=d1,
                        sample_rate=self.sample_rate, position=clip.position,
                        color=_generate_distinct_color(self.timeline._color_counter))
        self.timeline._color_counter += 1
        c2 = AudioClip(name=f"{clip.name}_R", audio_data=d2,
                        sample_rate=self.sample_rate, position=clip.position + local,
                        color=_generate_distinct_color(self.timeline._color_counter))
        self.timeline._color_counter += 1
        self.timeline.clips[idx:idx+1] = [c1, c2]
        self._rebuild_audio()
        self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
        self._add_structural_op("split", f"✂ Split ({clip.name})")
        self._unsaved = True

    def _dup_clip(self, cid):
        clip = self._find_clip(cid)
        if clip is None: return
        self._push_undo("Duplicate")
        color = CLIP_COLORS[self._clip_color_idx % len(CLIP_COLORS)]
        self._clip_color_idx += 1
        dup = AudioClip(name=f"{clip.name} (dup)", audio_data=clip.audio_data.copy(),
                        sample_rate=self.sample_rate,
                        position=clip.end_position, color=color)
        idx = self.timeline.clips.index(clip)
        self.timeline.clips.insert(idx + 1, dup)
        self._rebuild_audio()
        self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
        self._add_structural_op("duplicate", f"📋 Duplicate ({clip.name})")
        self._unsaved = True

    def _del_clip(self, cid):
        try:
            clip = self._find_clip(cid)
            if clip is None: return
            if len(self.timeline.clips) <= 1:
                QMessageBox.information(self, APP_NAME, t("timeline.last_clip"))
                return
            clip_name = clip.name
            reply = QMessageBox.question(
                self, APP_NAME,
                t("confirm.delete_clip").format(name=clip_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._push_undo("Delete clip")
            self.timeline.remove_clip(clip)
            self._rebuild_audio()
            self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
            self._add_structural_op("delete_clip", f"🗑 {clip_name}")
            self._refresh_all()
            self._unsaved = True
        except Exception as e:
            _log.error("Delete clip error: %s", e, exc_info=True)

    def _cut_replace_silence(self, sel_start, sel_end):
        """Cut selection: replace with silence. Creates 3 clips (before, silence, after) per affected clip."""
        if self.audio_data is None or not self.timeline.clips:
            return
        reply = QMessageBox.question(
            self, APP_NAME, t("confirm.cut_silence"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._push_undo("Cut (silence)")
        new_clips = []
        for clip in list(self.timeline.clips):
            cs, ce = clip.position, clip.end_position
            # No overlap
            if sel_end <= cs or sel_start >= ce:
                new_clips.append(clip)
                continue
            # Overlap range within this clip
            ov_start = max(sel_start, cs) - cs  # local index
            ov_end = min(sel_end, ce) - cs      # local index
            pos = cs
            parts = []
            # Part 1: before
            if ov_start > 0:
                d1 = clip.audio_data[:ov_start].copy()
                c1 = AudioClip(name=f"{clip.name}_A", audio_data=d1,
                               sample_rate=self.sample_rate, position=pos)
                c1.color = _generate_distinct_color(self.timeline._color_counter)
                self.timeline._color_counter += 1
                parts.append(c1)
                pos += len(d1)
            # Part 2: silence
            sil_len = ov_end - ov_start
            if sil_len > 0:
                shape = (sil_len, 2) if clip.audio_data.ndim > 1 else (sil_len,)
                d2 = np.zeros(shape, dtype=np.float32)
                c2 = AudioClip(name=f"{clip.name}_S", audio_data=d2,
                               sample_rate=self.sample_rate, position=pos)
                c2.color = _generate_distinct_color(self.timeline._color_counter)
                self.timeline._color_counter += 1
                parts.append(c2)
                pos += sil_len
            # Part 3: after
            if ov_end < len(clip.audio_data):
                d3 = clip.audio_data[ov_end:].copy()
                c3 = AudioClip(name=f"{clip.name}_B", audio_data=d3,
                               sample_rate=self.sample_rate, position=pos)
                c3.color = _generate_distinct_color(self.timeline._color_counter)
                self.timeline._color_counter += 1
                parts.append(c3)
            new_clips.extend(parts)
        self.timeline.clips = new_clips
        # Recalculate positions
        pos = 0
        for c in self.timeline.clips:
            c.position = pos
            pos += c.duration_samples
        self._rebuild_audio()
        self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
        self._add_structural_op("cut_silence", "✂ Cut (silence)")
        self.waveform.clear_selection()
        self._unsaved = True

    def _cut_splice(self, sel_start, sel_end):
        """Cut selection: remove and splice. Creates 2 clips (before, after) per affected clip."""
        if self.audio_data is None or not self.timeline.clips:
            return
        reply = QMessageBox.question(
            self, APP_NAME, t("confirm.cut_splice"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._push_undo("Cut (splice)")
        new_clips = []
        for clip in list(self.timeline.clips):
            cs, ce = clip.position, clip.end_position
            # No overlap
            if sel_end <= cs or sel_start >= ce:
                new_clips.append(clip)
                continue
            # Overlap range within this clip
            ov_start = max(sel_start, cs) - cs
            ov_end = min(sel_end, ce) - cs
            parts = []
            # Part 1: before
            if ov_start > 0:
                d1 = clip.audio_data[:ov_start].copy()
                c1 = AudioClip(name=f"{clip.name}_A", audio_data=d1,
                               sample_rate=self.sample_rate, position=0)
                c1.color = _generate_distinct_color(self.timeline._color_counter)
                self.timeline._color_counter += 1
                parts.append(c1)
            # Part 2: after (skip the cut section)
            if ov_end < len(clip.audio_data):
                d2 = clip.audio_data[ov_end:].copy()
                c2 = AudioClip(name=f"{clip.name}_B", audio_data=d2,
                               sample_rate=self.sample_rate, position=0)
                c2.color = _generate_distinct_color(self.timeline._color_counter)
                self.timeline._color_counter += 1
                parts.append(c2)
            if parts:
                new_clips.extend(parts)
            # If no parts remain (entire clip was selected), skip it
        # Ensure at least one clip remains
        if not new_clips and self.timeline.clips:
            # Keep a tiny silent clip
            c = AudioClip(name="Empty", audio_data=np.zeros((1, 2), dtype=np.float32),
                          sample_rate=self.sample_rate, position=0)
            c.color = _generate_distinct_color(self.timeline._color_counter)
            self.timeline._color_counter += 1
            new_clips.append(c)
        self.timeline.clips = new_clips
        # Recalculate positions
        pos = 0
        for c in self.timeline.clips:
            c.position = pos
            pos += c.duration_samples
        self._rebuild_audio()
        self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
        self._add_structural_op("cut_splice", "✂ Cut (splice)")
        self.waveform.clear_selection()
        self._unsaved = True

    def _fi_clip(self, cid):
        clip = self._find_clip(cid)
        if clip is None: return
        # Use original audio for preview (before any fade-in was applied)
        original = clip._audio_before_fade_in if clip._audio_before_fade_in is not None else clip.audio_data
        clip_dur_ms = int(len(original) / clip.sample_rate * 1000)
        dlg = FadeDialog("in", clip_dur_ms, parent=self,
                         clip_audio=original.copy(),
                         sample_rate=self.sample_rate,
                         playback_engine=self.playback,
                         existing_params=clip.fade_in_params or None)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        self._push_undo("Fade In")
        params = dlg.get_params()
        # Restore original audio before applying new fade (no stacking)
        if clip._audio_before_fade_in is not None:
            clip.audio_data = clip._audio_before_fade_in.copy()
            # Re-apply fade-out if it exists
            if clip.fade_out_params:
                p = clip.fade_out_params
                fs = int(p["duration_ms"] / 1000.0 * self.sample_rate)
                if "points" in p:
                    clip.audio_data = apply_envelope_fade(
                        clip.audio_data, fs, p["points"], p["bends"], "out")
                else:
                    clip.audio_data = fade_out(clip.audio_data, fs,
                                               p["curve_type"], p["start_level"], p["end_level"],
                                               p.get("curvature", 0.0))
        # Save original for future re-edits
        if clip._audio_before_fade_in is None:
            clip._audio_before_fade_in = clip.audio_data.copy()
        # Apply new fade-in (envelope-based)
        fade_samples = int(params["duration_ms"] / 1000.0 * self.sample_rate)
        clip.audio_data = apply_envelope_fade(
            clip.audio_data, fade_samples,
            params["points"], params["bends"], "in")
        clip.fade_in_params = params
        self._rebuild_audio()
        self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
        self._add_structural_op("fade_in", f"🔊 Fade In ({clip.name})")
        if self._effect_ops and any(op.get("type", "effect") not in self._STRUCTURAL_TYPES for op in self._effect_ops):
            self._render_from_ops()
        self._unsaved = True

    def _fo_clip(self, cid):
        clip = self._find_clip(cid)
        if clip is None: return
        # Use original audio for preview (before any fade-out was applied)
        original = clip._audio_before_fade_out if clip._audio_before_fade_out is not None else clip.audio_data
        clip_dur_ms = int(len(original) / clip.sample_rate * 1000)
        dlg = FadeDialog("out", clip_dur_ms, parent=self,
                         clip_audio=original.copy(),
                         sample_rate=self.sample_rate,
                         playback_engine=self.playback,
                         existing_params=clip.fade_out_params or None)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        self._push_undo("Fade Out")
        params = dlg.get_params()
        # Restore original audio before applying new fade (no stacking)
        if clip._audio_before_fade_out is not None:
            clip.audio_data = clip._audio_before_fade_out.copy()
            # Re-apply fade-in if it exists
            if clip.fade_in_params:
                p = clip.fade_in_params
                fs = int(p["duration_ms"] / 1000.0 * self.sample_rate)
                if "points" in p:
                    clip.audio_data = apply_envelope_fade(
                        clip.audio_data, fs, p["points"], p["bends"], "in")
                else:
                    clip.audio_data = fade_in(clip.audio_data, fs,
                                              p["curve_type"], p["start_level"], p["end_level"],
                                              p.get("curvature", 0.0))
        # Save original for future re-edits
        if clip._audio_before_fade_out is None:
            clip._audio_before_fade_out = clip.audio_data.copy()
        # Apply new fade-out (envelope-based)
        fade_samples = int(params["duration_ms"] / 1000.0 * self.sample_rate)
        clip.audio_data = apply_envelope_fade(
            clip.audio_data, fade_samples,
            params["points"], params["bends"], "out")
        clip.fade_out_params = params
        self._rebuild_audio()
        self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
        self._add_structural_op("fade_out", f"🔉 Fade Out ({clip.name})")
        if self._effect_ops and any(op.get("type", "effect") not in self._STRUCTURAL_TYPES for op in self._effect_ops):
            self._render_from_ops()
        self._unsaved = True

    def _find_clip(self, cid):
        for c in self.timeline.clips:
            if c.id == cid: return c
        return None

    def _delete_selected_clip(self):
        """Delete the currently selected clip in the timeline (Delete key)."""
        try:
            sel_id = getattr(self.timeline_w, '_selected_id', None)
            if sel_id:
                self._del_clip(sel_id)
        except Exception as e:
            _log.warning("Delete selected clip: %s", e)

    # ══════ Undo / Redo (ops-based, v4.4) ══════

    def _push_undo(self, desc=""):
        """Push current state to undo stack (ops + base + clips, no rendered audio)."""
        snapshot = {
            "desc": desc,
            "ops": self._copy_ops(self._effect_ops),
            "base_audio": self._base_audio.copy() if self._base_audio is not None else None,
            "clips": [(c.name, c.audio_data.copy(), c.position, c.color)
                      for c in self.timeline.clips] if self.timeline.clips else [],
        }
        self._ops_undo.append(snapshot)
        if len(self._ops_undo) > 20:
            self._ops_undo.pop(0)
        self._ops_redo.clear()
        self._update_undo_labels()

    @staticmethod
    def _copy_ops(ops):
        """Copy ops list, sharing heavy _state_after references (immutable snapshots)."""
        result = []
        for op in ops:
            d = {}
            for k, v in op.items():
                if k == "_state_after":
                    d[k] = v  # shared ref — never mutated
                elif isinstance(v, dict):
                    d[k] = dict(v)
                elif isinstance(v, list):
                    d[k] = list(v)
                else:
                    d[k] = v
            result.append(d)
        return result

    def _do_undo(self):
        if not self._ops_undo: return
        # Save current state to redo
        current = {
            "desc": "",
            "ops": self._copy_ops(self._effect_ops),
            "base_audio": self._base_audio.copy() if self._base_audio is not None else None,
            "clips": [(c.name, c.audio_data.copy(), c.position, c.color)
                      for c in self.timeline.clips] if self.timeline.clips else [],
        }
        self._ops_redo.append(current)
        # Restore from undo
        snapshot = self._ops_undo.pop()
        self._restore_snapshot(snapshot)
        self.statusBar().showMessage(t("status.undo"))
        self._update_undo_labels()

    def _do_redo(self):
        if not self._ops_redo: return
        current = {
            "desc": "",
            "ops": self._copy_ops(self._effect_ops),
            "base_audio": self._base_audio.copy() if self._base_audio is not None else None,
            "clips": [(c.name, c.audio_data.copy(), c.position, c.color)
                      for c in self.timeline.clips] if self.timeline.clips else [],
        }
        self._ops_undo.append(current)
        snapshot = self._ops_redo.pop()
        self._restore_snapshot(snapshot)
        self.statusBar().showMessage(t("status.redo"))
        self._update_undo_labels()

    def _restore_snapshot(self, snapshot):
        self._stop()
        self._effect_ops = snapshot.get("ops", [])
        # Restore base_audio if present
        base = snapshot.get("base_audio")
        if base is not None:
            self._base_audio = base
        # Restore clips
        clips = snapshot.get("clips", [])
        if clips:
            self.timeline.clear()
            for name, data, pos, color in clips:
                c = AudioClip(name=name, audio_data=data,
                              sample_rate=self.sample_rate,
                              position=pos, color=color)
                self.timeline.clips.append(c)
            self.timeline.sample_rate = self.sample_rate
        # Re-render audio from ops (handles both structural and effect ops)
        if self._effect_ops:
            self._render_from_ops()
        elif self._base_audio is not None:
            self.audio_data = self._base_audio.copy()
            self._refresh_all()
        elif clips:
            self._rebuild_audio()
        else:
            self.audio_data = None
            self._refresh_all()
        self._sync_history_chain()

    # ══════ Export Stems ══════

    def _export_stems(self):
        if not self.timeline.clips:
            QMessageBox.warning(self, APP_NAME, t("error.no_audio")); return
        if len(self.timeline.clips) < 2:
            QMessageBox.information(self, APP_NAME, t("stems.single")); return
        folder = QFileDialog.getExistingDirectory(self, t("stems.choose_folder"))
        if not folder: return
        try:
            exported = 0
            for i, clip in enumerate(self.timeline.clips):
                name = clip.name or f"stem_{i+1}"
                safe = "".join(c for c in name if c.isalnum() or c in " _-")[:50]
                fp = os.path.join(folder, f"{safe}.wav")
                export_audio(clip.audio_data, clip.sample_rate, fp, "wav")
                exported += 1
            self.statusBar().showMessage(t("stems.done").format(n=exported))
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, str(e))

    # ══════ Settings ══════

    def _settings_audio(self):
        d = AudioSettingsDialog(
            current_output=self.playback.output_device,
            current_input=getattr(self.playback, 'input_device', None),
            parent=self)
        if d.exec() == d.DialogCode.Accepted:
            old_out = self.playback.output_device
            self.playback.output_device = d.selected_output
            self.playback.input_device = d.selected_input
            if d.selected_output != old_out:
                self.playback.refresh_device()
            self.statusBar().showMessage(t("status.devices_updated"))

    def _settings_language(self):
        d = LanguageSettingsDialog(parent=self)
        if d.exec() == d.DialogCode.Accepted:
            if d.selected_language != get_language():
                set_language(d.selected_language)
                save_settings({"language": d.selected_language})
                self._build_menus()
                QMessageBox.information(self, APP_NAME, t("settings.restart"))

    def _settings_theme(self):
        d = ThemeSettingsDialog(parent=self)
        if d.exec() == d.DialogCode.Accepted:
            if d.selected_theme != get_theme():
                set_theme(d.selected_theme)
                save_settings({"theme": d.selected_theme})
                QMessageBox.information(self, APP_NAME, t("settings.restart"))

    def _import_effect(self):
        """Import chooser: Effect plugin, Preset, or Help."""
        d = ImportChooserDialog(self)
        if d.exec() != d.DialogCode.Accepted or not d.choice:
            return
        if d.choice == ImportChooserDialog.CHOICE_EFFECT:
            from gui.import_plugin_dialog import ImportPluginDialog
            dlg = ImportPluginDialog(self)
            if dlg.exec() == dlg.DialogCode.Accepted:
                self._plugins = load_plugins(force_reload=True)
                self._build_menus()
                self.effects_panel.reload_plugins()
                self.statusBar().showMessage("Plugin imported")
        elif d.choice == ImportChooserDialog.CHOICE_PRESET:
            self._import_presets()
        elif d.choice == ImportChooserDialog.CHOICE_HELP:
            HelpDialog(self).exec()

    # ══════ Misc ══════

    def _record(self):
        d = RecordDialog(input_device=self.playback.input_device, parent=self)
        d.recording_done.connect(self._on_rec)
        d.exec()

    def _on_rec(self, data, sr):
        st = ensure_stereo(data)
        name = f"Recording {datetime.now().strftime('%H:%M:%S')}"
        if self.audio_data is None:
            self.audio_data, self.sample_rate = st, sr
            self.timeline.clear()
            self.timeline.sample_rate = sr
            color = CLIP_COLORS[self._clip_color_idx % len(CLIP_COLORS)]
            self._clip_color_idx += 1
            self.timeline.add_clip(st, sr, name=name, position=0, color=color)
            self._base_audio = st.copy()
            self._store_initial_state()
        else:
            self._push_undo("Record")
            # Resample recording to match project sample rate if needed
            if sr != self.sample_rate and self.sample_rate > 0:
                from scipy.signal import resample as scipy_resample
                new_len = int(len(st) * self.sample_rate / sr)
                if new_len > 0:
                    channels = []
                    for ch in range(st.shape[1] if st.ndim > 1 else 1):
                        ch_data = st[:, ch] if st.ndim > 1 else st
                        channels.append(scipy_resample(ch_data, new_len))
                    st = np.column_stack(channels).astype(np.float32)
                sr = self.sample_rate
            color = CLIP_COLORS[self._clip_color_idx % len(CLIP_COLORS)]
            self._clip_color_idx += 1
            self.timeline.add_clip(st, sr, name=name, color=color)
            self._rebuild_audio()
            self._base_audio = self.audio_data.copy() if self.audio_data is not None else None
            self._add_structural_op("record", f"🎙 {name}")
        self._refresh_all()
        self._unsaved = True

    def _select_all(self):
        if self.audio_data is not None:
            self.waveform.set_selection(0, len(self.audio_data))
            dur = format_time(get_duration(self.audio_data, self.sample_rate))
            self.transport.set_selection_info(f"Sel : {dur}")

    def _open_manual(self):
        import webbrowser
        lang = get_language()
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        manual = os.path.join(base, "assets", f"manual_{lang}.html")
        if not os.path.exists(manual):
            manual = os.path.join(base, "assets", "manual_en.html")
        if os.path.exists(manual):
            webbrowser.open(f"file://{manual}")
        else:
            QMessageBox.information(self, APP_NAME, "Manual not found")

    def _catalog(self):
        d = CatalogDialog(self)
        d.exec()

    # ══════ Drag & Drop ══════

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                fp = url.toLocalFile()
                ext = os.path.splitext(fp)[1].lower()
                if ext in AUDIO_EXTENSIONS or ext == ".gspi":
                    e.acceptProposedAction(); return
        e.ignore()

    def dropEvent(self, e: QDropEvent):
        for url in e.mimeData().urls():
            fp = url.toLocalFile()
            ext = os.path.splitext(fp)[1].lower()
            if ext == ".gspi":
                self._load_gspi(fp); return
            elif ext in AUDIO_EXTENSIONS:
                self._load_audio(fp); return

    # ══════ Close ══════

    def closeEvent(self, e):
        if self._unsaved and self.audio_data is not None:
            r = QMessageBox.question(
                self, APP_NAME, t("confirm.unsaved"),
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel)
            if r == QMessageBox.StandardButton.Save:
                self._save()
            elif r == QMessageBox.StandardButton.Cancel:
                e.ignore(); return
        self.playback.stop()
        e.accept()
