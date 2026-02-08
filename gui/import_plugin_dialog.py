"""Import & manage user effect plugins dialog."""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QMessageBox, QGroupBox, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from utils.config import COLORS
from utils.translator import t


_SS = f"""
    QDialog {{ background: {COLORS['bg_medium']}; }}
    QLabel {{ color: {COLORS['text']}; font-size: 11px; }}
    QGroupBox {{ color: {COLORS['accent']}; font-size: 12px; font-weight: bold;
        border: 1px solid {COLORS['border']}; border-radius: 6px;
        margin-top: 8px; padding-top: 14px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 6px; }}
    QListWidget {{ background: {COLORS['bg_dark']}; color: {COLORS['text']};
        border: 1px solid {COLORS['border']}; border-radius: 4px;
        font-size: 11px; padding: 4px; }}
    QListWidget::item {{ padding: 4px 6px; border-radius: 3px; }}
    QListWidget::item:selected {{ background: {COLORS['accent']}; color: white; }}
    QListWidget::item:hover {{ background: {COLORS['button_bg']}; }}
"""


def _btn(text, bg=COLORS['accent']):
    """Cree un bouton stylise pour le dialogue."""
    b = QPushButton(text)
    b.setFixedHeight(30)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ background: {bg}; color: white; border: none; "
        f"border-radius: 5px; font-weight: bold; font-size: 11px; padding: 0 12px; }}"
        f"QPushButton:hover {{ background: {COLORS['accent_hover']}; }}"
    )
    return b


class ImportPluginDialog(QDialog):
    """Dialog to import a new plugin and manage installed user plugins."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Effects Plugins")
        self.setFixedSize(500, 460)
        self.setStyleSheet(_SS)
        self._changed = False  # track if we installed/removed anything

        lo = QVBoxLayout(self)
        lo.setSpacing(10)
        lo.setContentsMargins(20, 16, 20, 16)

        title = QLabel("🧩 Effect Plugins")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']};")
        lo.addWidget(title)

        # ── Import section ──
        imp_grp = QGroupBox("Import New Effect")
        ilo = QVBoxLayout(imp_grp)
        ilo.setSpacing(8)

        desc = QLabel(
            "Import a custom effect from a <b>.py</b> file.\n"
            "Optionally add a <b>.json</b> file for translations (en/fr)."
        )
        desc.setWordWrap(True)
        ilo.addWidget(desc)

        # File selectors
        self._py_path = None
        self._json_path = None

        py_row = QHBoxLayout()
        self._py_label = QLabel("No .py file selected")
        self._py_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        py_btn = _btn("📄 Select .py", COLORS['button_bg'])
        py_btn.clicked.connect(self._pick_py)
        py_row.addWidget(self._py_label, stretch=1)
        py_row.addWidget(py_btn)
        ilo.addLayout(py_row)

        json_row = QHBoxLayout()
        self._json_label = QLabel("No .json file (optional)")
        self._json_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        json_btn = _btn("🌐 Select .json", COLORS['button_bg'])
        json_btn.clicked.connect(self._pick_json)
        json_row.addWidget(self._json_label, stretch=1)
        json_row.addWidget(json_btn)
        ilo.addLayout(json_row)

        install_btn = _btn("⬇ Install Effect")
        install_btn.clicked.connect(self._install)
        ilo.addWidget(install_btn)

        lo.addWidget(imp_grp)

        # ── Installed section ──
        inst_grp = QGroupBox("Installed User Effects")
        inst_lo = QVBoxLayout(inst_grp)
        inst_lo.setSpacing(6)

        self._list = QListWidget()
        self._list.setMinimumHeight(100)
        inst_lo.addWidget(self._list)

        rm_row = QHBoxLayout()
        rm_btn = _btn("🗑 Remove Selected", "#9b2226")
        rm_btn.clicked.connect(self._remove)
        rm_row.addStretch()
        rm_row.addWidget(rm_btn)
        inst_lo.addLayout(rm_row)

        lo.addWidget(inst_grp)

        # ── Close ──
        lo.addStretch()
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = _btn("Close", COLORS['button_bg'])
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        lo.addLayout(close_row)

        self._refresh_list()

    @property
    def changed(self):
        """Retourne True si des plugins ont ete ajoutes/supprimes."""
        return self._changed

    def _pick_py(self):
        """Ouvre un dialogue pour selectionner le fichier .py du plugin."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select effect .py file", "",
            "Python files (*.py)")
        if path:
            self._py_path = path
            self._py_label.setText(os.path.basename(path))
            self._py_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")

    def _pick_json(self):
        """Ouvre un dialogue pour selectionner le fichier i18n du plugin."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select translations .json file", "",
            "JSON files (*.json)")
        if path:
            self._json_path = path
            self._json_label.setText(os.path.basename(path))
            self._json_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")

    def _install(self):
        """Installe le plugin dans le dossier user_plugins."""
        if not self._py_path:
            QMessageBox.warning(self, "Import", "Please select a .py file first.")
            return

        try:
            from plugins.user_loader import install_plugin
            entry = install_plugin(self._py_path, self._json_path)
            self._changed = True
            QMessageBox.information(
                self, "Import",
                f"✅ Effect \"{entry['name']}\" installed!\n"
                f"It will appear in the '{entry['section']}' section."
            )
            self._py_path = None
            self._json_path = None
            self._py_label.setText("No .py file selected")
            self._py_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
            self._json_label.setText("No .json file (optional)")
            self._json_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
            self._refresh_list()
        except Exception as ex:
            QMessageBox.critical(self, "Import Error", f"Failed to install plugin:\n{ex}")

    def _remove(self):
        """Desinstalle un plugin utilisateur."""
        item = self._list.currentItem()
        if not item:
            QMessageBox.warning(self, "Remove", "Select a plugin to remove.")
            return

        pid = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()
        reply = QMessageBox.question(
            self, "Remove Plugin",
            f"Remove \"{name}\"?\nThis will delete the plugin files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from plugins.user_loader import uninstall_plugin
            uninstall_plugin(pid)
            self._changed = True
            self._refresh_list()

    def _refresh_list(self):
        """Rafraichit la liste des plugins installes."""
        self._list.clear()
        from plugins.user_loader import list_installed
        for entry in list_installed():
            item = QListWidgetItem(
                f"{entry.get('icon', '?')}  {entry.get('name', entry.get('id', '?'))}  "
                f"— {entry.get('section', 'Custom')}"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry.get("id"))
            self._list.addItem(item)

        if self._list.count() == 0:
            item = QListWidgetItem("  (no user effects installed)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(item)
