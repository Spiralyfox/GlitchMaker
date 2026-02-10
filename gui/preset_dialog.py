"""Preset dialogs — Create (with param editing + audio test), Manage presets,
Tag manager, Export selector, Import chooser, Help docs."""
import os, sys, threading, traceback, webbrowser
import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QMessageBox, QFrame, QScrollArea, QWidget, QTextBrowser,
    QFileDialog, QGroupBox, QTabWidget, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from utils.config import COLORS, APP_NAME
from utils.translator import t
from utils.logger import get_logger

_log = get_logger("preset_dialog")

_SS = f"""
QDialog {{ background: {COLORS['bg_medium']}; }}
QLabel {{ color: {COLORS['text']}; font-size: 11px; }}
QLineEdit, QComboBox {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
    border: 1px solid {COLORS['border']}; border-radius: 4px; padding: 5px; font-size: 11px; }}
QComboBox QAbstractItemView {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
    selection-background-color: {COLORS['accent']}; }}
QListWidget {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
    border: 1px solid {COLORS['border']}; border-radius: 4px; font-size: 11px; }}
QListWidget::item {{ padding: 4px; }}
QListWidget::item:selected {{ background: {COLORS['accent']}; }}
"""

# ── Effect name → plugin ID mapping (all 28 effects) ──
EFFECT_MAP = {
    "Autotune": "autotune",
    "Bitcrusher": "bitcrusher",
    "Buffer Freeze": "buffer_freeze",
    "Chorus": "chorus",
    "Datamosh": "datamosh",
    "Delay": "delay",
    "Distortion": "distortion",
    "Filter": "filter",
    "Granular": "granular",
    "Hyper": "hyper",
    "OTT": "ott",
    "Pan": "pan",
    "Phaser": "phaser",
    "Pitch Drift": "wave_ondulee",
    "Pitch Shift": "pitch_shift",
    "Reverse": "reverse",
    "Ring Mod": "ring_mod",
    "Robotic Voice": "robot",
    "Saturation": "saturation",
    "Shuffle": "shuffle",
    "Stutter": "stutter",
    "Tape Glitch": "tape_glitch",
    "Tape Stop": "tape_stop",
    "Time Stretch": "time_stretch",
    "Tremolo": "tremolo",
    "Vinyl": "vinyl",
    "Vocal Chop": "vocal_chop",
    "Volume": "volume",
}
EFFECT_NAMES = sorted(EFFECT_MAP.keys())


def _btn(text, bg=COLORS['accent']):
    """Crée un bouton stylisé."""
    b = QPushButton(text); b.setFixedHeight(30)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ background: {bg}; color: white; border: none; "
        f"border-radius: 5px; font-weight: bold; font-size: 11px; }} "
        f"QPushButton:hover {{ background: {COLORS['accent_hover']}; }}")
    return b


def _link_btn(text, color=COLORS['selection']):
    """Crée un bouton-lien (texte sans bordure)."""
    b = QPushButton(text); b.setFixedHeight(22)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ color: {color}; background: transparent; "
        f"border: none; font-size: 10px; text-decoration: underline; }} "
        f"QPushButton:hover {{ color: {COLORS['accent']}; }}")
    return b


def _sep():
    """Crée un séparateur horizontal."""
    s = QFrame(); s.setFrameShape(QFrame.Shape.HLine)
    s.setStyleSheet(f"color: {COLORS['border']};"); return s


# ═══════════════════════════════════════════════════
#  Tag Manager Dialog
# ═══════════════════════════════════════════════════

class TagManageDialog(QDialog):
    """Manage tags — add new, delete existing. Deleting cascades to presets."""
    def __init__(self, preset_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Tags")
        self.setFixedSize(360, 400); self.setStyleSheet(_SS)
        self.pm = preset_manager
        self.changed = False

        lo = QVBoxLayout(self); lo.setSpacing(8); lo.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Manage Tags")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(title)

        lo.addWidget(QLabel("Existing tags:"))
        self.lst = QListWidget()
        lo.addWidget(self.lst)
        self._populate()

        info = QLabel("Deleting a tag removes it from all presets.\n"
                       "Presets stay in 'All' and their other tags.")
        info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        info.setWordWrap(True)
        lo.addWidget(info)

        lo.addWidget(_sep())

        lo.addWidget(QLabel("Add new tag:"))
        add_row = QHBoxLayout()
        self.new_inp = QLineEdit()
        self.new_inp.setPlaceholderText("Tag name")
        self.new_inp.returnPressed.connect(self._add)
        add_row.addWidget(self.new_inp, stretch=1)
        ba = _btn("Add", COLORS['accent']); ba.setFixedWidth(60)
        ba.clicked.connect(self._add)
        add_row.addWidget(ba)
        lo.addLayout(add_row)

        lo.addSpacing(6)
        row = QHBoxLayout()
        bd = _btn("Delete selected", COLORS['selection'])
        bd.clicked.connect(self._delete); row.addWidget(bd)
        bc = _btn("Done", COLORS['button_bg'])
        bc.clicked.connect(self.accept); row.addWidget(bc)
        lo.addLayout(row)

    def _populate(self):
        """Remplit la liste des tags."""
        self.lst.clear()
        for tag in self.pm.get_all_tags():
            count = len(self.pm.get_presets_by_tag(tag))
            it = QListWidgetItem(f"{tag}  ({count} presets)")
            it.setData(Qt.ItemDataRole.UserRole, tag)
            self.lst.addItem(it)

    def _add(self):
        """Ajoute un nouveau tag."""
        tag = self.new_inp.text().strip()
        if not tag:
            return
        existing = self.pm.get_all_tags()
        if tag in existing:
            QMessageBox.information(self, APP_NAME, f"Tag '{tag}' already exists.")
            return
        self.pm.add_tag(tag)
        self.changed = True
        self.new_inp.clear()
        self._populate()

    def _delete(self):
        """Supprime le tag sélectionné."""
        items = self.lst.selectedItems()
        if not items:
            return
        for it in items:
            tag = it.data(Qt.ItemDataRole.UserRole)
            r = QMessageBox.question(
                self, APP_NAME,
                f"Delete tag '{tag}'?\n\n"
                f"It will be removed from all presets.\n"
                f"Presets will remain in 'All' and other tags.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Yes:
                self.pm.delete_tag(tag)
                self.changed = True
        self._populate()


# ═══════════════════════════════════════════════════
#  Create Preset Dialog (with effect parameter editing)
# ═══════════════════════════════════════════════════

class PresetCreateDialog(QDialog):
    """Create a new preset — tags, effects chain with configurable parameters."""
    def __init__(self, all_tags: list[str], parent=None, preset_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Create Preset")
        self.setFixedSize(480, 780); self.setStyleSheet(_SS)
        self.result_preset = None
        self._tags = list(all_tags)
        self._pm = preset_manager
        self._effects_data = []  # list of {"name": str, "params": dict}
        self._plugins = None
        self._test_audio = None   # numpy array for test playback
        self._test_sr = 44100
        self._playing = False
        self._play_stream = None
        # Try to get plugins and audio from parent (MainWindow)
        if parent and hasattr(parent, '_plugins'):
            self._plugins = parent._plugins

        lo = QVBoxLayout(self); lo.setSpacing(8); lo.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Create Preset")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(title)

        # Name
        lo.addWidget(QLabel("Name"))
        self.name_inp = QLineEdit()
        self.name_inp.setPlaceholderText("My preset")
        lo.addWidget(self.name_inp)

        # Description
        lo.addWidget(QLabel("Description"))
        self.desc_inp = QLineEdit()
        self.desc_inp.setPlaceholderText("Short description")
        lo.addWidget(self.desc_inp)

        # ── Tags section ──
        tag_header = QHBoxLayout()
        tag_header.addWidget(QLabel("Tags"))
        tag_header.addStretch()
        manage_tags_btn = _link_btn("Manage tags", COLORS['accent'])
        manage_tags_btn.clicked.connect(self._open_tag_manager)
        tag_header.addWidget(manage_tags_btn)
        lo.addLayout(tag_header)

        tag_row = QHBoxLayout()
        self.tag_combo = QComboBox()
        self._refresh_tag_combo()
        tag_row.addWidget(self.tag_combo, stretch=1)
        btn_add_tag = _btn("Add", COLORS['button_bg'])
        btn_add_tag.setFixedWidth(50)
        btn_add_tag.clicked.connect(self._add_tag)
        tag_row.addWidget(btn_add_tag)
        lo.addLayout(tag_row)

        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(50)
        lo.addWidget(self.tag_list)
        rm_tag_btn = _link_btn("Remove selected tag")
        rm_tag_btn.clicked.connect(self._rm_tag)
        lo.addWidget(rm_tag_btn)

        lo.addWidget(_sep())

        # ── Effects chain ──
        lo.addWidget(QLabel("Effects chain (click Settings to configure parameters)"))
        eff_row = QHBoxLayout()
        self.eff_combo = QComboBox()
        self.eff_combo.addItems(EFFECT_NAMES)
        eff_row.addWidget(self.eff_combo, stretch=1)
        btn_add_eff = _btn("Add", COLORS['button_bg'])
        btn_add_eff.setFixedWidth(50)
        btn_add_eff.clicked.connect(self._add_eff)
        eff_row.addWidget(btn_add_eff)
        lo.addLayout(eff_row)

        # Effects list with Settings buttons
        self._eff_scroll = QScrollArea()
        self._eff_scroll.setWidgetResizable(True)
        self._eff_scroll.setMaximumHeight(140)
        self._eff_scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {COLORS['border']}; "
            f"border-radius: 4px; background: {COLORS['bg_dark']}; }}")
        self._eff_container = QWidget()
        self._eff_lo = QVBoxLayout(self._eff_container)
        self._eff_lo.setContentsMargins(4, 4, 4, 4)
        self._eff_lo.setSpacing(3)
        self._eff_lo.addStretch()
        self._eff_scroll.setWidget(self._eff_container)
        lo.addWidget(self._eff_scroll)

        rm_eff_btn = _link_btn("Remove selected effect")
        rm_eff_btn.clicked.connect(self._rm_eff)
        lo.addWidget(rm_eff_btn)

        lo.addWidget(_sep())

        # ── Test preset section ──
        test_grp = QGroupBox("Test Preset")
        test_grp.setStyleSheet(
            f"QGroupBox {{ color: {COLORS['accent']}; font-size: 11px; font-weight: bold; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px; "
            f"margin-top: 6px; padding-top: 14px; }} "
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}")
        tlo = QVBoxLayout(test_grp); tlo.setSpacing(5); tlo.setContentsMargins(8, 8, 8, 8)

        # Audio source buttons
        src_row = QHBoxLayout(); src_row.setSpacing(4)
        btn_import_audio = _btn("Load audio file", COLORS['button_bg'])
        btn_import_audio.clicked.connect(self._test_import_audio)
        src_row.addWidget(btn_import_audio)
        btn_project_audio = _btn("Use project audio", COLORS['button_bg'])
        btn_project_audio.clicked.connect(self._test_use_project)
        src_row.addWidget(btn_project_audio)
        tlo.addLayout(src_row)

        self._test_label = QLabel("No audio loaded")
        self._test_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        tlo.addWidget(self._test_label)

        # Playback buttons
        play_row = QHBoxLayout(); play_row.setSpacing(4)
        self._btn_play_orig = _btn("Play original", COLORS['button_bg'])
        self._btn_play_orig.clicked.connect(self._test_play_original)
        self._btn_play_orig.setEnabled(False)
        play_row.addWidget(self._btn_play_orig)
        self._btn_play_preset = _btn("Play with preset", COLORS['accent'])
        self._btn_play_preset.clicked.connect(self._test_play_preset)
        self._btn_play_preset.setEnabled(False)
        play_row.addWidget(self._btn_play_preset)
        self._btn_stop = _btn("Stop", COLORS['selection'])
        self._btn_stop.clicked.connect(self._test_stop)
        self._btn_stop.setEnabled(False)
        self._btn_stop.setFixedWidth(50)
        play_row.addWidget(self._btn_stop)
        tlo.addLayout(play_row)

        lo.addWidget(test_grp)

        lo.addSpacing(4)

        # Buttons
        row = QHBoxLayout()
        bc = _btn("Cancel", COLORS['button_bg'])
        bc.clicked.connect(self._on_cancel); row.addWidget(bc)
        bs = _btn("Save")
        bs.clicked.connect(self._save); row.addWidget(bs)
        lo.addLayout(row)

    def _refresh_tag_combo(self):
        """Refresh tag dropdown from preset manager or stored list."""
        self.tag_combo.clear()
        if self._pm:
            self._tags = self._pm.get_all_tags()
        self.tag_combo.addItems(self._tags)

    def _open_tag_manager(self):
        """Open the Manage Tags dialog, then refresh dropdown."""
        if not self._pm:
            return
        dlg = TagManageDialog(self._pm, self)
        dlg.exec()
        if dlg.changed:
            self._refresh_tag_combo()

    def _add_tag(self):
        """Ajoute un tag au preset en cours d'édition."""
        tag = self.tag_combo.currentText()
        if tag and not self.tag_list.findItems(tag, Qt.MatchFlag.MatchExactly):
            self.tag_list.addItem(tag)

    def _rm_tag(self):
        """Retire un tag du preset en cours d'édition."""
        for it in self.tag_list.selectedItems():
            self.tag_list.takeItem(self.tag_list.row(it))

    def _add_eff(self):
        """Ajoute un effet à la chaîne (pas de doublons)."""
        name = self.eff_combo.currentText()
        existing = [e["name"] for e in self._effects_data]
        if name in existing:
            QMessageBox.information(self, APP_NAME,
                f"\"{name}\" is already in the chain.")
            return
        self._effects_data.append({"name": name, "params": {}})
        self._rebuild_eff_list()

    def _rm_eff(self):
        """Retire l'effet sélectionné de la chaîne."""
        # Find which row is "selected" (has focus)
        if not self._effects_data:
            return
        # Remove last item if nothing specific selected
        idx = len(self._effects_data) - 1
        # Try to find focused row
        for i, (row_w, _) in enumerate(self._eff_rows):
            if row_w.property("selected"):
                idx = i
                break
        if 0 <= idx < len(self._effects_data):
            self._effects_data.pop(idx)
            self._rebuild_eff_list()

    def _rebuild_eff_list(self):
        """Reconstruit la liste visuelle des effets avec boutons Settings."""
        # Clear old widgets
        while self._eff_lo.count() > 0:
            item = self._eff_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._eff_rows = []
        for i, eff in enumerate(self._effects_data):
            row_w = QWidget()
            row_lo = QHBoxLayout(row_w)
            row_lo.setContentsMargins(2, 1, 2, 1)
            row_lo.setSpacing(4)

            # Number
            num = QLabel(f"{i+1}.")
            num.setFixedWidth(20)
            num.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
            row_lo.addWidget(num)

            # Effect name
            name_lbl = QLabel(eff["name"])
            name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px; font-weight: bold;")
            row_lo.addWidget(name_lbl, stretch=1)

            # Params summary
            params = eff.get("params", {})
            if params:
                summary = ", ".join(f"{k}={v}" for k, v in list(params.items())[:3])
                if len(params) > 3:
                    summary += "..."
                p_lbl = QLabel(summary)
                p_lbl.setStyleSheet(f"color: {COLORS['accent']}; font-size: 9px;")
                p_lbl.setMaximumWidth(150)
                row_lo.addWidget(p_lbl)

            # Settings button
            settings_btn = QPushButton("Settings")
            settings_btn.setFixedSize(60, 22)
            settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            settings_btn.setStyleSheet(
                f"QPushButton {{ background: {COLORS['button_bg']}; color: {COLORS['text']}; "
                f"border: none; border-radius: 3px; font-size: 10px; }} "
                f"QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}")
            idx = i  # capture
            settings_btn.clicked.connect(lambda checked, ii=idx: self._edit_params(ii))
            row_lo.addWidget(settings_btn)

            # Remove button
            rm_btn = QPushButton("X")
            rm_btn.setFixedSize(22, 22)
            rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            rm_btn.setStyleSheet(
                f"QPushButton {{ background: {COLORS['selection']}; color: white; "
                f"border: none; border-radius: 3px; font-size: 10px; font-weight: bold; }} "
                f"QPushButton:hover {{ background: #ff4444; }}")
            rm_btn.clicked.connect(lambda checked, ii=idx: self._remove_at(ii))
            row_lo.addWidget(rm_btn)

            row_w.setStyleSheet(
                f"background: {COLORS['bg_medium']}; border-radius: 3px;")
            self._eff_lo.addWidget(row_w)
            self._eff_rows.append((row_w, eff))

        self._eff_lo.addStretch()

    def _remove_at(self, idx):
        """Retire l'effet à l'index donné."""
        if 0 <= idx < len(self._effects_data):
            self._effects_data.pop(idx)
            self._rebuild_eff_list()

    def _edit_params(self, idx):
        """Ouvre le dialog de l'effet pour editer ses parametres."""
        if idx < 0 or idx >= len(self._effects_data):
            return
        eff = self._effects_data[idx]
        name = eff["name"]
        plugin_id = EFFECT_MAP.get(name)
        if not plugin_id:
            QMessageBox.information(self, APP_NAME, f"Unknown effect: {name}")
            return

        plugin = None
        if self._plugins and plugin_id in self._plugins:
            plugin = self._plugins[plugin_id]

        if not plugin or not plugin.dialog_class:
            QMessageBox.information(self, APP_NAME,
                f"{name} has no configurable parameters.")
            return

        try:
            # Create dialog with NO args (default params), then set_params
            dlg = plugin.dialog_class()
            if hasattr(dlg, 'set_params') and eff.get("params"):
                dlg.set_params(eff["params"])
            if dlg.exec() == dlg.DialogCode.Accepted:
                if hasattr(dlg, 'get_params'):
                    eff["params"] = dlg.get_params()
                    self._rebuild_eff_list()
        except Exception as ex:
            _log.error("Settings dialog error for %s: %s\n%s",
                       name, ex, traceback.format_exc())
            QMessageBox.warning(self, APP_NAME, f"Could not open settings:\n{ex}")

    def _save(self):
        """Sauvegarde le preset."""
        self._test_stop()
        name = self.name_inp.text().strip()
        if not name:
            QMessageBox.warning(self, APP_NAME, "Please enter a preset name.")
            return
        if len(self._effects_data) == 0:
            QMessageBox.warning(self, APP_NAME, "Please add at least one effect.")
            return
        # Check duplicate name (unless editing the same preset)
        if self._pm:
            existing = self._pm.get_preset(name)
            edit_name = getattr(self, '_editing_name', None)
            if existing and name != edit_name:
                QMessageBox.warning(self, APP_NAME,
                    f"A preset named \"{name}\" already exists.\nChoose a different name.")
                return
        tags = [self.tag_list.item(i).text() for i in range(self.tag_list.count())]
        self.result_preset = {
            "name": name,
            "description": self.desc_inp.text().strip(),
            "tags": tags,
            "effects": self._effects_data,
        }
        self.accept()

    def load_preset(self, preset_data: dict):
        """Load an existing preset into the form for editing."""
        self._editing_name = preset_data.get("name", "")
        self.setWindowTitle(f"Edit Preset — {self._editing_name}")
        self.name_inp.setText(preset_data.get("name", ""))
        self.desc_inp.setText(preset_data.get("description", ""))
        # Tags
        self.tag_list.clear()
        for tag in preset_data.get("tags", []):
            self.tag_list.addItem(tag)
        # Effects
        self._effects_data = []
        for eff in preset_data.get("effects", []):
            self._effects_data.append({
                "name": eff.get("name", ""),
                "params": dict(eff.get("params", {})),
            })
        self._rebuild_eff_list()

    def _on_cancel(self):
        """Stop playback and close."""
        self._test_stop()
        self.reject()

    # ── Test preset methods ──

    def _test_import_audio(self):
        """Import an audio file for testing."""
        try:
            import soundfile as sf
        except ImportError:
            QMessageBox.warning(self, APP_NAME, "soundfile not installed.")
            return
        fp, _ = QFileDialog.getOpenFileName(
            self, "Load test audio", "",
            "Audio (*.wav *.mp3 *.flac *.ogg);;All (*)")
        if not fp:
            return
        try:
            from core.audio_engine import load_audio
            data, sr = load_audio(fp)
            if data is not None:
                self._test_audio = data
                self._test_sr = sr
                dur = len(data) / sr
                name = os.path.basename(fp)
                self._test_label.setText(f"{name} ({dur:.1f}s, {sr}Hz)")
                self._test_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
                self._btn_play_orig.setEnabled(True)
                self._btn_play_preset.setEnabled(True)
                _log.info("Test audio loaded: %s (%.1fs)", name, dur)
        except Exception as ex:
            _log.error("Failed to load test audio: %s\n%s", ex, traceback.format_exc())
            QMessageBox.warning(self, APP_NAME, f"Failed to load audio:\n{ex}")

    def _test_use_project(self):
        """Use the current project audio for testing."""
        parent = self.parent()
        if not parent or not hasattr(parent, 'audio_data') or parent.audio_data is None:
            QMessageBox.information(self, APP_NAME,
                "No audio loaded in project. Load a file first.")
            return
        self._test_audio = parent.audio_data.copy()
        self._test_sr = parent.sample_rate
        dur = len(self._test_audio) / self._test_sr
        self._test_label.setText(f"Project audio ({dur:.1f}s, {self._test_sr}Hz)")
        self._test_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
        self._btn_play_orig.setEnabled(True)
        self._btn_play_preset.setEnabled(True)
        _log.info("Test audio: using project audio (%.1fs)", dur)

    def _test_play_original(self):
        """Play original audio without effects."""
        if self._test_audio is None:
            return
        self._test_stop()
        self._play_audio(self._test_audio, self._test_sr)

    def _test_play_preset(self):
        """Apply preset effects then play."""
        if self._test_audio is None:
            return
        if not self._effects_data:
            QMessageBox.information(self, APP_NAME, "Add effects to the chain first.")
            return
        self._test_stop()
        try:
            audio = self._test_audio.copy()
            sr = self._test_sr
            s, e = 0, len(audio)
            for eff in self._effects_data:
                name = eff["name"]
                params = dict(eff.get("params", {}))
                plugin_id = EFFECT_MAP.get(name)
                if not plugin_id or not self._plugins:
                    continue
                plugin = self._plugins.get(plugin_id)
                if not plugin or not plugin.process_fn:
                    continue
                try:
                    audio = plugin.process_fn(audio, s, e, sr=sr, **params)
                except Exception as ex:
                    _log.error("Test preset - effect %s failed: %s", name, ex)
            self._play_audio(audio, sr)
        except Exception as ex:
            _log.error("Test preset playback error: %s\n%s", ex, traceback.format_exc())
            QMessageBox.warning(self, APP_NAME, f"Playback error:\n{ex}")

    def _play_audio(self, data, sr):
        """Play audio data using sounddevice."""
        try:
            import sounddevice as sd
            self._test_stop()
            # Normalize to prevent clipping
            peak = np.max(np.abs(data))
            if peak > 0:
                audio = data / max(peak, 1.0)
            else:
                audio = data
            audio = np.ascontiguousarray(audio.astype(np.float32))
            self._playing = True
            self._btn_stop.setEnabled(True)
            sd.play(audio, sr)
        except Exception as ex:
            _log.error("Playback error: %s\n%s", ex, traceback.format_exc())
            QMessageBox.warning(self, APP_NAME, f"Playback error:\n{ex}")

    def _test_stop(self):
        """Stop test playback."""
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        self._playing = False
        if hasattr(self, '_btn_stop') and self._btn_stop:
            self._btn_stop.setEnabled(False)


# ═══════════════════════════════════════════════════
#  Manage Presets Dialog
# ═══════════════════════════════════════════════════

_TREE_SS = f"""
QTreeWidget {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
    border: 1px solid {COLORS['border']}; border-radius: 4px; font-size: 11px; }}
QTreeWidget::item {{ padding: 3px 6px; }}
QTreeWidget::item:selected {{ background: {COLORS['accent']}; }}
QTreeWidget::branch {{ background: {COLORS['bg_dark']}; }}
QHeaderView::section {{ background: {COLORS['bg_medium']}; color: {COLORS['text']};
    border: none; padding: 4px; font-weight: bold; font-size: 11px; }}
"""

_TAB_SS = f"""
QTabWidget::pane {{ border: 1px solid {COLORS['border']}; border-radius: 4px;
    background: {COLORS['bg_dark']}; }}
QTabBar::tab {{ background: {COLORS['button_bg']}; color: {COLORS['text']};
    padding: 6px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px;
    margin-right: 2px; font-size: 11px; }}
QTabBar::tab:selected {{ background: {COLORS['accent']}; color: white; font-weight: bold; }}
"""


class PresetManageDialog(QDialog):
    """Manage presets — tabbed view (User / Built-in), sorted by tags."""
    def __init__(self, preset_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Presets")
        self.setFixedSize(480, 520); self.setStyleSheet(_SS)
        self.pm = preset_manager
        self._parent = parent
        self.deleted = []

        lo = QVBoxLayout(self); lo.setSpacing(8); lo.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Manage Presets")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(title)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(_TAB_SS)

        # ── User presets tab ──
        user_w = QWidget()
        ulo = QVBoxLayout(user_w); ulo.setContentsMargins(4, 8, 4, 4); ulo.setSpacing(6)
        self.user_tree = QTreeWidget()
        self.user_tree.setHeaderLabels(["Name", "Description"])
        self.user_tree.setColumnWidth(0, 200)
        self.user_tree.setRootIsDecorated(True)
        self.user_tree.setStyleSheet(_TREE_SS)
        ulo.addWidget(self.user_tree)
        urow = QHBoxLayout(); urow.setSpacing(4)
        be = _btn("Edit", COLORS['accent'])
        be.clicked.connect(self._edit_user); urow.addWidget(be)
        bd = _btn("Delete", COLORS['selection'])
        bd.clicked.connect(self._delete_user); urow.addWidget(bd)
        bt = _btn("Manage tags", COLORS['button_bg'])
        bt.clicked.connect(self._manage_tags); urow.addWidget(bt)
        ulo.addLayout(urow)
        self.tabs.addTab(user_w, "My Presets")

        # ── Built-in presets tab ──
        builtin_w = QWidget()
        blo = QVBoxLayout(builtin_w); blo.setContentsMargins(4, 8, 4, 4); blo.setSpacing(6)
        self.builtin_tree = QTreeWidget()
        self.builtin_tree.setHeaderLabels(["Name", "Description"])
        self.builtin_tree.setColumnWidth(0, 200)
        self.builtin_tree.setRootIsDecorated(True)
        self.builtin_tree.setStyleSheet(_TREE_SS)
        blo.addWidget(self.builtin_tree)
        info = QLabel("Built-in presets cannot be modified or deleted.")
        info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        blo.addWidget(info)
        self.tabs.addTab(builtin_w, "Built-in")

        lo.addWidget(self.tabs)

        # Close
        bc = _btn("Close", COLORS['button_bg'])
        bc.clicked.connect(self.accept)
        lo.addWidget(bc)

        self._populate()

    def _populate(self):
        """Build both trees, grouped by tags, sorted alphabetically."""
        self.user_tree.clear()
        self.builtin_tree.clear()
        all_presets = self.pm.get_all_presets()
        user_presets = [p for p in all_presets if not p.get("builtin")]
        builtin_presets = [p for p in all_presets if p.get("builtin")]
        self._fill_tree(self.user_tree, user_presets)
        self._fill_tree(self.builtin_tree, builtin_presets)

    def _fill_tree(self, tree, presets):
        """Fill a tree widget with presets grouped by tag."""
        # Group by tag
        tag_map = {}
        no_tag = []
        for p in presets:
            tags = p.get("tags", [])
            if not tags:
                no_tag.append(p)
            else:
                for t_name in tags:
                    tag_map.setdefault(t_name, []).append(p)

        # Add tag groups (sorted)
        for tag in sorted(tag_map.keys()):
            tag_item = QTreeWidgetItem([f"[{tag}]", f"{len(tag_map[tag])} presets"])
            tag_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            tag_item.setForeground(0, _qcolor(COLORS['accent']))
            tag_item.setExpanded(True)
            seen = set()
            for p in sorted(tag_map[tag], key=lambda x: x["name"].lower()):
                if p["name"] in seen:
                    continue
                seen.add(p["name"])
                child = QTreeWidgetItem([p["name"], p.get("description", "")])
                child.setData(0, Qt.ItemDataRole.UserRole, p["name"])
                tag_item.addChild(child)
            tree.addTopLevelItem(tag_item)

        # Untagged
        if no_tag:
            tag_item = QTreeWidgetItem(["[No tag]", f"{len(no_tag)} presets"])
            tag_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
            tag_item.setForeground(0, _qcolor(COLORS['text_dim']))
            tag_item.setExpanded(True)
            for p in sorted(no_tag, key=lambda x: x["name"].lower()):
                child = QTreeWidgetItem([p["name"], p.get("description", "")])
                child.setData(0, Qt.ItemDataRole.UserRole, p["name"])
                tag_item.addChild(child)
            tree.addTopLevelItem(tag_item)

    def _get_selected_user(self):
        """Get selected preset name from user tree."""
        items = self.user_tree.selectedItems()
        if not items:
            return None
        item = items[0]
        name = item.data(0, Qt.ItemDataRole.UserRole)
        return name  # None if tag header selected

    def _edit_user(self):
        """Open PresetCreateDialog pre-filled with existing preset for editing."""
        name = self._get_selected_user()
        if not name:
            QMessageBox.information(self, APP_NAME, "Select a user preset to edit.")
            return
        preset = self.pm.get_preset(name)
        if not preset:
            return
        # Open create dialog in edit mode
        tags = self.pm.get_all_tags()
        dlg = PresetCreateDialog(tags, self._parent, self.pm)
        dlg.load_preset(preset)
        if dlg.exec() == dlg.DialogCode.Accepted and dlg.result_preset:
            data = dlg.result_preset
            # Delete old, add new (in case name changed)
            self.pm.delete_preset(name)
            self.pm.add_preset(
                data["name"], data.get("description", ""),
                data.get("tags", []), data.get("effects", []))
            self.deleted.append("__edited__")
            self._populate()

    def _delete_user(self):
        """Delete selected user preset."""
        name = self._get_selected_user()
        if not name:
            QMessageBox.information(self, APP_NAME, "Select a user preset to delete.")
            return
        r = QMessageBox.question(
            self, APP_NAME, f"Delete preset \"{name}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            if self.pm.delete_preset(name):
                self.deleted.append(name)
                self._populate()

    def _manage_tags(self):
        """Ouvre le dialogue de gestion des tags."""
        dlg = TagManageDialog(self.pm, self)
        dlg.exec()
        if dlg.changed:
            self._populate()
            self.deleted.append("__tags_changed__")


def _qcolor(hex_str):
    """Convert hex color string to QColor."""
    from PyQt6.QtGui import QColor
    return QColor(hex_str)


# ═══════════════════════════════════════════════════
#  Export Preset Selector Dialog
# ═══════════════════════════════════════════════════

class ExportPresetDialog(QDialog):
    """Select a user preset to export as .pspi."""
    def __init__(self, preset_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Preset")
        self.setFixedSize(400, 380); self.setStyleSheet(_SS)
        self.pm = preset_manager
        self.exported = False

        lo = QVBoxLayout(self); lo.setSpacing(8); lo.setContentsMargins(16, 12, 16, 12)
        title = QLabel("Export Preset")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(title)

        lo.addWidget(QLabel("Select a user preset to export as .pspi file:"))

        self.lst = QListWidget()
        lo.addWidget(self.lst)
        self._populate()

        info = QLabel("Only user presets can be exported (not built-in).")
        info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        lo.addWidget(info)

        lo.addSpacing(4)
        row = QHBoxLayout()
        be = _btn("Export")
        be.clicked.connect(self._export); row.addWidget(be)
        bc = _btn("Cancel", COLORS['button_bg'])
        bc.clicked.connect(self.reject); row.addWidget(bc)
        lo.addLayout(row)

    def _populate(self):
        self.lst.clear()
        for p in self.pm.get_all_presets():
            if p.get("builtin"):
                continue
            tags = ", ".join(p.get("tags", [])) if p.get("tags") else ""
            label = p["name"]
            if tags:
                label += f"  [{tags}]"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, p["name"])
            self.lst.addItem(it)
        if self.lst.count() == 0:
            it = QListWidgetItem("  (no user presets)")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.lst.addItem(it)

    def _export(self):
        item = self.lst.currentItem()
        if not item or not item.data(Qt.ItemDataRole.UserRole):
            QMessageBox.warning(self, APP_NAME, "Please select a preset to export.")
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        fp, _ = QFileDialog.getSaveFileName(
            self, "Export Preset", f"{name}.pspi", "Preset (*.pspi)")
        if not fp:
            return
        try:
            self.pm.export_presets(fp, [name])
            QMessageBox.information(self, APP_NAME,
                f"Preset \"{name}\" exported to:\n{fp}")
            self.exported = True
            self.accept()
        except Exception as ex:
            QMessageBox.critical(self, APP_NAME, f"Export failed:\n{ex}")


# ═══════════════════════════════════════════════════
#  Import Chooser Dialog (Effect / Preset / Help)
# ═══════════════════════════════════════════════════

class ImportChooserDialog(QDialog):
    """Choose between importing an Effect plugin, a Preset file, or reading Help."""
    CHOICE_EFFECT = "effect"
    CHOICE_PRESET = "preset"
    CHOICE_HELP = "help"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import")
        self.setFixedSize(360, 280); self.setStyleSheet(_SS)
        self.choice = None

        lo = QVBoxLayout(self); lo.setSpacing(12); lo.setContentsMargins(24, 20, 24, 20)
        title = QLabel("Import")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(title)

        lo.addWidget(QLabel(t("import.choose_prompt")))
        lo.addSpacing(4)

        b1 = _btn(t("import.effect_plugin"))
        b1.clicked.connect(lambda: self._choose(self.CHOICE_EFFECT))
        lo.addWidget(b1)

        b2 = _btn(t("import.preset"))
        b2.clicked.connect(lambda: self._choose(self.CHOICE_PRESET))
        lo.addWidget(b2)

        lo.addSpacing(4)
        b3 = _btn(t("import.help"), COLORS['button_bg'])
        b3.clicked.connect(lambda: self._choose(self.CHOICE_HELP))
        lo.addWidget(b3)

        lo.addStretch()
        bc = _btn(t("dialog.cancel"), COLORS['button_bg'])
        bc.clicked.connect(self.reject)
        lo.addWidget(bc)

    def _choose(self, c):
        self.choice = c
        self.accept()


# ═══════════════════════════════════════════════════
#  Help Dialog — How to create Effects & Presets
# ═══════════════════════════════════════════════════

_HELP_FR = """
<h2 style="color: #7c5cfc;">Comment créer et importer des Effets &amp; Presets</h2>

<h3 style="color: #a78bfa;">Créer un Effet personnalisé (.py)</h3>
<p>Un effet est un fichier Python (<code>.py</code>) qui doit contenir :</p>
<ol>
<li><b>Métadonnées</b> en haut du fichier :
<pre style="background: #1a1a30; padding: 8px; border-radius: 4px;">
EFFECT_ID      = "mon_effet"      # identifiant unique
EFFECT_ICON    = "M"              # lettre affichée dans l'icône
EFFECT_COLOR   = "#ff6b35"        # couleur hex
EFFECT_SECTION = "Custom"         # catégorie (Basics, Distortion, etc.)
</pre>
</li>
<li><b>Une classe Dialog</b> héritant de <code>_Base</code> :
<pre style="background: #1a1a30; padding: 8px; border-radius: 4px;">
from gui.effect_dialogs import _Base, _slider_int

class Dialog(_Base):
    def __init__(self, p=None):
        super().__init__("Mon Effet", p)
        self.param1 = _slider_int(self._lo, "Param", 0, 100, 50)
        self._finish()
    def get_params(self):
        return {"param1": self.param1.value()}
    def set_params(self, p):
        self.param1.setValue(p.get("param1", 50))
</pre>
</li>
<li><b>Une fonction <code>process()</code></b> :
<pre style="background: #1a1a30; padding: 8px; border-radius: 4px;">
def process(audio_data, start, end, sr=44100, **kw):
    result = audio_data.copy()
    # Modifier result[start:end] selon kw
    return result
</pre>
</li>
</ol>
<p><b>Fichier de traduction (optionnel)</b> : un fichier <code>.json</code> avec les clés
<code>cat.mon_effet.name</code>, <code>cat.mon_effet.short</code>, <code>cat.mon_effet.detail</code>
en <code>"en"</code> et <code>"fr"</code>.</p>
<p>Importez via <b>Import &gt; Import Effect Plugin</b> en sélectionnant le .py et optionnellement le .json.</p>

<hr style="border-color: #2a2a4a;">

<h3 style="color: #a78bfa;">Créer et exporter un Preset (.pspi)</h3>
<p>Un preset est une chaîne d'effets sauvegardée avec des paramètres préconfigurés.</p>
<ol>
<li>Cliquez sur <b>New Preset</b> dans le panneau d'effets</li>
<li>Donnez un nom, une description, des tags</li>
<li>Ajoutez des effets à la chaîne</li>
<li>Cliquez sur <b>Settings</b> à côté de chaque effet pour configurer ses paramètres</li>
<li>Cliquez sur <b>Save</b></li>
</ol>
<p><b>Exporter</b> : cliquez sur <b>Export</b>, sélectionnez un preset utilisateur, et choisissez un emplacement
pour le fichier <code>.pspi</code>.</p>
<p><b>Importer</b> : cliquez sur <b>Import &gt; Import Preset</b> et sélectionnez un fichier <code>.pspi</code>.
Les presets importés apparaissent dans la vue PR du panneau d'effets.</p>
<p>Le format .pspi est un fichier JSON contenant la liste des effets et leurs paramètres.
Vous pouvez le partager avec d'autres utilisateurs de Glitch Maker.</p>
"""

_HELP_EN = """
<h2 style="color: #7c5cfc;">How to create and import Effects &amp; Presets</h2>

<h3 style="color: #a78bfa;">Creating a custom Effect (.py)</h3>
<p>An effect is a Python file (<code>.py</code>) that must contain:</p>
<ol>
<li><b>Metadata</b> at the top of the file:
<pre style="background: #1a1a30; padding: 8px; border-radius: 4px;">
EFFECT_ID      = "my_effect"      # unique identifier
EFFECT_ICON    = "M"              # letter shown in the icon
EFFECT_COLOR   = "#ff6b35"        # hex color
EFFECT_SECTION = "Custom"         # category (Basics, Distortion, etc.)
</pre>
</li>
<li><b>A Dialog class</b> inheriting from <code>_Base</code>:
<pre style="background: #1a1a30; padding: 8px; border-radius: 4px;">
from gui.effect_dialogs import _Base, _slider_int

class Dialog(_Base):
    def __init__(self, p=None):
        super().__init__("My Effect", p)
        self.param1 = _slider_int(self._lo, "Param", 0, 100, 50)
        self._finish()
    def get_params(self):
        return {"param1": self.param1.value()}
    def set_params(self, p):
        self.param1.setValue(p.get("param1", 50))
</pre>
</li>
<li><b>A <code>process()</code> function</b>:
<pre style="background: #1a1a30; padding: 8px; border-radius: 4px;">
def process(audio_data, start, end, sr=44100, **kw):
    result = audio_data.copy()
    # Modify result[start:end] based on kw
    return result
</pre>
</li>
</ol>
<p><b>Translation file (optional)</b>: a <code>.json</code> file with keys
<code>cat.my_effect.name</code>, <code>cat.my_effect.short</code>, <code>cat.my_effect.detail</code>
in <code>"en"</code> and <code>"fr"</code>.</p>
<p>Import via <b>Import &gt; Import Effect Plugin</b> by selecting the .py and optionally the .json.</p>

<hr style="border-color: #2a2a4a;">

<h3 style="color: #a78bfa;">Creating and exporting a Preset (.pspi)</h3>
<p>A preset is a saved effects chain with preconfigured parameters.</p>
<ol>
<li>Click <b>New Preset</b> in the effects panel</li>
<li>Enter a name, description, and tags</li>
<li>Add effects to the chain</li>
<li>Click <b>Settings</b> next to each effect to configure its parameters</li>
<li>Click <b>Save</b></li>
</ol>
<p><b>Export</b>: click <b>Export</b>, select a user preset, and choose a location
for the <code>.pspi</code> file.</p>
<p><b>Import</b>: click <b>Import &gt; Import Preset</b> and select a <code>.pspi</code> file.
Imported presets appear in the PR view of the effects panel.</p>
<p>The .pspi format is a JSON file containing the list of effects and their parameters.
You can share it with other Glitch Maker users.</p>
"""


class HelpDialog(QDialog):
    """Bilingual help on creating effects and presets."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help — Effects & Presets")
        self.setFixedSize(800, 640)
        self.setStyleSheet(f"QDialog {{ background: {COLORS['bg_medium']}; }}")

        lo = QVBoxLayout(self); lo.setContentsMargins(16, 12, 16, 12)

        # Language toggle + example button
        lang_row = QHBoxLayout(); lang_row.setSpacing(6)
        self._btn_fr = _btn("Francais", COLORS['accent'])
        self._btn_fr.setFixedWidth(100)
        self._btn_en = _btn("English", COLORS['button_bg'])
        self._btn_en.setFixedWidth(100)
        self._btn_fr.clicked.connect(lambda: self._set_lang("fr"))
        self._btn_en.clicked.connect(lambda: self._set_lang("en"))
        lang_row.addWidget(self._btn_fr)
        lang_row.addWidget(self._btn_en)
        lang_row.addSpacing(12)
        btn_example = _btn("Example Effect Code", COLORS['button_bg'])
        btn_example.setFixedWidth(180)
        btn_example.clicked.connect(self._open_example)
        lang_row.addWidget(btn_example)
        lang_row.addStretch()
        lo.addLayout(lang_row)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background: {COLORS['bg_dark']}; color: {COLORS['text']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px; "
            f"padding: 14px 20px 14px 14px; font-size: 12px; }}")
        lo.addWidget(self._browser)

        bc = _btn("Close", COLORS['button_bg'])
        bc.clicked.connect(self.accept)
        lo.addWidget(bc)

        from utils.translator import get_language
        self._set_lang(get_language())

    def _set_lang(self, lang):
        _active = (f"QPushButton {{ background: {COLORS['accent']}; color: white; "
                   f"border: none; border-radius: 5px; font-weight: bold; font-size: 11px; }}")
        _inactive = (f"QPushButton {{ background: {COLORS['button_bg']}; color: white; "
                     f"border: none; border-radius: 5px; font-weight: bold; font-size: 11px; }}")
        if lang == "fr":
            self._browser.setHtml(_HELP_FR)
            self._btn_fr.setStyleSheet(_active)
            self._btn_en.setStyleSheet(_inactive)
        else:
            self._browser.setHtml(_HELP_EN)
            self._btn_en.setStyleSheet(_active)
            self._btn_fr.setStyleSheet(_inactive)

    def _open_example(self):
        """Open the effect example HTML page in the default browser."""
        from utils.config import get_data_dir
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(os.path.join(__file__, "..")))
        html_path = os.path.join(base, "assets", "effect_example.html")
        if os.path.isfile(html_path):
            webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")
        else:
            QMessageBox.warning(self, APP_NAME,
                f"Example file not found:\n{html_path}")
