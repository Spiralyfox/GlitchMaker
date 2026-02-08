"""Preset dialogs — Create (dropdown tags + manage), Manage presets, Tag manager."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from utils.config import COLORS

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

EFFECT_NAMES = [
    "Bitcrusher", "Buffer Freeze", "Chorus", "Datamosh", "Delay",
    "Distortion", "Filter", "Granular", "OTT", "Phaser",
    "Pitch Shift", "Reverse", "Ring Mod", "Saturation", "Shuffle",
    "Stutter", "Tape Stop", "Time Stretch", "Tremolo", "Vinyl", "Volume",
]


def _btn(text, bg=COLORS['accent']):
    """Cree un bouton stylise."""
    b = QPushButton(text); b.setFixedHeight(30)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ background: {bg}; color: white; border: none; "
        f"border-radius: 5px; font-weight: bold; font-size: 11px; }} "
        f"QPushButton:hover {{ background: {COLORS['accent_hover']}; }}")
    return b


def _link_btn(text, color=COLORS['selection']):
    """Cree un bouton-lien (texte sans bordure)."""
    b = QPushButton(text); b.setFixedHeight(22)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ color: {color}; background: transparent; "
        f"border: none; font-size: 10px; text-decoration: underline; }} "
        f"QPushButton:hover {{ color: {COLORS['accent']}; }}")
    return b


def _sep():
    """Cree un separateur horizontal."""
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
        t = QLabel("Manage Tags")
        t.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(t)

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
        """Remplit la liste des presets."""
        self.lst.clear()
        for tag in self.pm.get_all_tags():
            count = len(self.pm.get_presets_by_tag(tag))
            it = QListWidgetItem(f"{tag}  ({count} presets)")
            it.setData(Qt.ItemDataRole.UserRole, tag)
            self.lst.addItem(it)

    def _add(self):
        """Ajoute un nouveau preset."""
        tag = self.new_inp.text().strip()
        if not tag:
            return
        existing = self.pm.get_all_tags()
        if tag in existing:
            QMessageBox.information(self, "Glitch Maker", f"Tag '{tag}' already exists.")
            return
        self.pm.add_tag(tag)
        self.changed = True
        self.new_inp.clear()
        self._populate()

    def _delete(self):
        """Supprime le preset selectionne."""
        items = self.lst.selectedItems()
        if not items:
            return
        for it in items:
            tag = it.data(Qt.ItemDataRole.UserRole)
            r = QMessageBox.question(
                self, "Glitch Maker",
                f"Delete tag '{tag}'?\n\n"
                f"It will be removed from all presets.\n"
                f"Presets will remain in 'All' and other tags.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Yes:
                self.pm.delete_tag(tag)
                self.changed = True
        self._populate()


# ═══════════════════════════════════════════════════
#  Create Preset Dialog
# ═══════════════════════════════════════════════════

class PresetCreateDialog(QDialog):
    """Create a new preset — tag via dropdown + Manage Tags button."""
    def __init__(self, all_tags: list[str], parent=None, preset_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Create Preset")
        self.setFixedSize(420, 520); self.setStyleSheet(_SS)
        self.result_preset = None
        self._tags = list(all_tags)
        self._pm = preset_manager

        lo = QVBoxLayout(self); lo.setSpacing(8); lo.setContentsMargins(16, 12, 16, 12)
        t = QLabel("Create Preset")
        t.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(t)

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

        # Tag dropdown + Add button
        tag_row = QHBoxLayout()
        self.tag_combo = QComboBox()
        self._refresh_tag_combo()
        tag_row.addWidget(self.tag_combo, stretch=1)
        btn_add_tag = _btn("Add", COLORS['button_bg'])
        btn_add_tag.setFixedWidth(50)
        btn_add_tag.clicked.connect(self._add_tag)
        tag_row.addWidget(btn_add_tag)
        lo.addLayout(tag_row)

        # Selected tags list
        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(55)
        lo.addWidget(self.tag_list)
        rm_tag_btn = _link_btn("Remove selected tag")
        rm_tag_btn.clicked.connect(self._rm_tag)
        lo.addWidget(rm_tag_btn)

        lo.addWidget(_sep())

        # ── Effects chain ──
        lo.addWidget(QLabel("Effects chain"))
        eff_row = QHBoxLayout()
        self.eff_combo = QComboBox()
        self.eff_combo.addItems(EFFECT_NAMES)
        eff_row.addWidget(self.eff_combo, stretch=1)
        btn_add_eff = _btn("Add", COLORS['button_bg'])
        btn_add_eff.setFixedWidth(50)
        btn_add_eff.clicked.connect(self._add_eff)
        eff_row.addWidget(btn_add_eff)
        lo.addLayout(eff_row)

        self.eff_list = QListWidget()
        self.eff_list.setMaximumHeight(90)
        lo.addWidget(self.eff_list)
        rm_eff_btn = _link_btn("Remove selected effect")
        rm_eff_btn.clicked.connect(self._rm_eff)
        lo.addWidget(rm_eff_btn)

        lo.addStretch()

        # Buttons
        row = QHBoxLayout()
        bc = _btn("Cancel", COLORS['button_bg'])
        bc.clicked.connect(self.reject); row.addWidget(bc)
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
        """Ajoute un tag au preset en cours d edition."""
        tag = self.tag_combo.currentText()
        if tag and not self.tag_list.findItems(tag, Qt.MatchFlag.MatchExactly):
            self.tag_list.addItem(tag)

    def _rm_tag(self):
        """Retire un tag du preset en cours d edition."""
        for it in self.tag_list.selectedItems():
            self.tag_list.takeItem(self.tag_list.row(it))

    def _add_eff(self):
        """Ajoute un effet a la chaine du preset."""
        self.eff_list.addItem(self.eff_combo.currentText())

    def _rm_eff(self):
        """Retire un effet de la chaine du preset."""
        for it in self.eff_list.selectedItems():
            self.eff_list.takeItem(self.eff_list.row(it))

    def _save(self):
        """Sauvegarde le preset edite."""
        name = self.name_inp.text().strip()
        if not name:
            QMessageBox.warning(self, "Glitch Maker", "Name is required.")
            return
        if self.eff_list.count() == 0:
            QMessageBox.warning(self, "Glitch Maker", "Add at least one effect.")
            return
        tags = [self.tag_list.item(i).text() for i in range(self.tag_list.count())]
        effects = [
            {"name": self.eff_list.item(i).text(), "params": {}}
            for i in range(self.eff_list.count())
        ]
        self.result_preset = {
            "name": name,
            "description": self.desc_inp.text().strip(),
            "tags": tags,
            "effects": effects,
        }
        self.accept()


# ═══════════════════════════════════════════════════
#  Manage Presets Dialog
# ═══════════════════════════════════════════════════

class PresetManageDialog(QDialog):
    """Manage presets — view all, delete user presets."""
    def __init__(self, preset_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Presets")
        self.setFixedSize(420, 440); self.setStyleSheet(_SS)
        self.pm = preset_manager
        self.deleted = []

        lo = QVBoxLayout(self); lo.setSpacing(8); lo.setContentsMargins(16, 12, 16, 12)
        t = QLabel("Manage Presets")
        t.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(t)

        self.lst = QListWidget()
        lo.addWidget(self.lst)
        self._populate()

        info = QLabel("★ = built-in (cannot be deleted)")
        info.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        lo.addWidget(info)

        lo.addSpacing(4)
        row = QHBoxLayout()
        bd = _btn("Delete selected", COLORS['selection'])
        bd.clicked.connect(self._delete); row.addWidget(bd)
        bt = _btn("Manage tags", COLORS['button_bg'])
        bt.clicked.connect(self._manage_tags); row.addWidget(bt)
        bc = _btn("Close", COLORS['button_bg'])
        bc.clicked.connect(self.accept); row.addWidget(bc)
        lo.addLayout(row)

    def _populate(self):
        """Remplit la liste des presets."""
        self.lst.clear()
        for p in self.pm.get_all_presets():
            prefix = "★ " if p.get("builtin") else "  "
            tags = ", ".join(p.get("tags", [])) if p.get("tags") else "(no tags)"
            it = QListWidgetItem(f"{prefix}{p['name']}   [{tags}]")
            it.setData(Qt.ItemDataRole.UserRole, p["name"])
            it.setData(Qt.ItemDataRole.UserRole + 1, bool(p.get("builtin")))
            self.lst.addItem(it)

    def _delete(self):
        """Supprime le preset selectionne."""
        for it in self.lst.selectedItems():
            if it.data(Qt.ItemDataRole.UserRole + 1):
                QMessageBox.information(self, "Glitch Maker",
                                        "Cannot delete built-in presets.")
                continue
            name = it.data(Qt.ItemDataRole.UserRole)
            if self.pm.delete_preset(name):
                self.deleted.append(name)
        self._populate()

    def _manage_tags(self):
        """Ouvre le dialogue de gestion des tags."""
        dlg = TagManageDialog(self.pm, self)
        dlg.exec()
        if dlg.changed:
            self._populate()
            # Signal parent to refresh
            self.deleted.append("__tags_changed__")
