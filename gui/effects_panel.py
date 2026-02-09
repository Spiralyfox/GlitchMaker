"""Effects panel — sidebar with search, effects & presets.
Redesigned: better buttons with hover tooltips, collapsible preset sections (closed by default).
Features: favorites (★), right-click quick apply.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QToolTip, QGraphicsDropShadowEffect,
    QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor, QColor, QFont, QPainter, QBrush, QPen

from utils.translator import t
from utils.config import COLORS, TAG_COLORS, FAVORITE_STAR, load_settings, save_settings
from utils.translator import get_language, t
from plugins.loader import load_plugins, plugins_grouped
from plugins import preview_player


# ═══ Effect Button (redesigned with favorites + right-click + checkbox) ═══

class EffectButton(QWidget):
    """Styled effect button with colored badge, name, and hover tooltip."""
    clicked = pyqtSignal()
    right_clicked = pyqtSignal(str)       # step 38: right-click preview
    fav_toggled = pyqtSignal(str, bool)   # step 37: favorite toggle

    def __init__(self, letter, color, name, eid, short_desc="", preview_path=None,
                 is_fav=False, parent=None):
        """Initialise le widget EffectButton."""
        super().__init__(parent)
        self._eid = eid
        self._preview_path = preview_path
        self._color = color
        self._hovered = False
        self._is_fav = is_fav
        self.setFixedHeight(34)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if short_desc:
            self.setToolTip(f"<b>{name}</b><br><span style='color: #aaa;'>{short_desc}</span>")

        lo = QHBoxLayout(self)
        lo.setContentsMargins(6, 2, 6, 2)
        lo.setSpacing(6)

        # Colored icon badge
        self._icon = QLabel(letter)
        self._icon.setFixedSize(24, 24)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"background: {color}; color: white; border-radius: 5px; "
            f"font-weight: bold; font-size: 11px; font-family: 'Consolas', monospace;"
        )
        lo.addWidget(self._icon)

        # Name
        self._name = QLabel(name)
        self._name.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
        lo.addWidget(self._name, stretch=1)

        # Favorite star (step 37)
        self._fav_btn = QPushButton("★" if is_fav else "☆")
        self._fav_btn.setFixedSize(20, 20)
        self._fav_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._fav_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {FAVORITE_STAR if is_fav else COLORS['text_dim']};"
            f" border: none; font-size: 13px; padding: 0; }}"
            f"QPushButton:hover {{ color: {FAVORITE_STAR}; }}")
        self._fav_btn.clicked.connect(self._toggle_fav)
        lo.addWidget(self._fav_btn)

        # Preview button (hidden by default)
        self._prev_btn = QPushButton("\u266b")
        self._prev_btn.setFixedSize(20, 20)
        self._prev_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._prev_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {COLORS['text_dim']}; "
            f"border: none; border-radius: 3px; font-size: 11px; padding: 0; }}"
            f"QPushButton:hover {{ background: {color}; color: white; }}"
        )
        self._prev_btn.setVisible(False)
        self._prev_btn.setToolTip(t("effects.preview_tip"))
        self._prev_btn.clicked.connect(self._on_preview)
        lo.addWidget(self._prev_btn)

    def _toggle_fav(self):
        self._is_fav = not self._is_fav
        self._fav_btn.setText("★" if self._is_fav else "☆")
        self._fav_btn.setStyleSheet(
            f"QPushButton {{ background: transparent;"
            f" color: {FAVORITE_STAR if self._is_fav else COLORS['text_dim']};"
            f" border: none; font-size: 13px; padding: 0; }}"
            f"QPushButton:hover {{ color: {FAVORITE_STAR}; }}")
        self.fav_toggled.emit(self._eid, self._is_fav)

    def mousePressEvent(self, e):
        """Clic gauche emet le signal clicked avec le nom du preset."""
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def contextMenuEvent(self, e):
        """Step 38: Right-click context menu for quick preview."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {COLORS['bg_panel']}; color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; font-size: 11px; }}"
            f"QMenu::item {{ padding: 4px 16px; }}"
            f"QMenu::item:selected {{ background: {COLORS['accent']}; color: white; }}")
        a_quick = menu.addAction("⚡ Quick Apply (last params)")
        a_fav = menu.addAction("★ Toggle Favorite")
        action = menu.exec(e.globalPos())
        if action == a_quick:
            self.right_clicked.emit(self._eid)
        elif action == a_fav:
            self._toggle_fav()

    def enterEvent(self, e):
        """Active l etat hover (fond colore + barre accent)."""
        self._hovered = True
        self.update()
        if self._preview_path:
            self._prev_btn.setVisible(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        """Desactive l etat hover."""
        self._hovered = False
        self.update()
        self._prev_btn.setVisible(False)
        super().leaveEvent(e)

    def paintEvent(self, e):
        """Dessine le fond hover colore et la barre d accent a gauche."""
        if self._hovered:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            c = QColor(self._color)
            c.setAlpha(25)
            p.setBrush(QBrush(c))
            p.drawRoundedRect(0, 0, self.width(), self.height(), 6, 6)
            p.setBrush(QBrush(QColor(self._color)))
            p.drawRoundedRect(0, 4, 3, self.height() - 8, 1, 1)
            p.end()
        super().paintEvent(e)

    def _on_preview(self):
        """Lance la preview audio d un effet."""
        if self._preview_path:
            if preview_player.is_playing():
                preview_player.stop_preview()
            else:
                preview_player.play_preview(self._preview_path)


# ═══ Collapsible Section ═══

class CollapsibleSection(QWidget):
    def __init__(self, title, start_expanded=True, parent=None):
        """Initialise le widget CollapsibleSection."""
        super().__init__(parent)
        self._expanded = start_expanded
        self._count = 0
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        self._title = title
        self._header = QPushButton()
        self._header.setFlat(True)
        self._header.setStyleSheet(
            f"QPushButton {{ color: {COLORS['text_dim']}; font-size: 10px; font-weight: bold; "
            f"text-align: left; padding: 6px 8px; border: none; letter-spacing: 1px; }}"
            f"QPushButton:hover {{ color: {COLORS['text']}; background: {COLORS['bg_dark']}; "
            f"border-radius: 4px; }}"
        )
        self._header.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._header.clicked.connect(self._toggle)
        self._update_header()
        lo.addWidget(self._header)

        self._content = QWidget()
        self._clo = QVBoxLayout(self._content)
        self._clo.setContentsMargins(0, 0, 0, 2)
        self._clo.setSpacing(1)
        self._content.setVisible(self._expanded)
        lo.addWidget(self._content)

    def _update_header(self):
        """Met a jour le texte du header avec fleche et compteur."""
        arrow = "\u25be" if self._expanded else "\u25b8"
        cnt = f"  ({self._count})" if self._count > 0 else ""
        self._header.setText(f"{arrow}  {self._title}{cnt}")

    def _toggle(self):
        """Bascule l affichage du contenu de la section."""
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._update_header()

    def add_widget(self, w):
        """Ajoute un widget dans la section et incremente le compteur."""
        self._clo.addWidget(w)
        self._count += 1
        self._update_header()


# ═══ Preset Item ═══
# TAG_COLORS now imported from utils.config (step 46)


class PresetItem(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, name, desc, tags=None, parent=None):
        """Initialise le widget PresetItem."""
        super().__init__(parent)
        self._name = name
        self._hovered = False
        self._color = COLORS['accent']
        if tags:
            for tg in tags:
                if tg in TAG_COLORS:
                    self._color = TAG_COLORS[tg]; break
        self.setFixedHeight(26)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if desc:
            self.setToolTip(f"<b>{name}</b><br><span style='color:#aaa'>{desc}</span>")

        lo = QHBoxLayout(self)
        lo.setContentsMargins(10, 0, 10, 0)
        lo.setSpacing(6)

        dot = QLabel()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f"background: {self._color}; border-radius: 3px;")
        lo.addWidget(dot)

        lbl = QLabel(name)
        lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
        lo.addWidget(lbl, stretch=1)

    def mousePressEvent(self, e):
        """Clic gauche emet le signal clicked avec le nom du preset."""
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)

    def enterEvent(self, e):
        """Active l etat hover (fond colore + barre accent)."""
        self._hovered = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        """Desactive l etat hover."""
        self._hovered = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, e):
        """Dessine le fond hover colore et la barre d accent a gauche."""
        if self._hovered:
            p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            c = QColor(self._color); c.setAlpha(20)
            p.setBrush(QBrush(c))
            p.drawRoundedRect(0, 0, self.width(), self.height(), 5, 5)
            p.setBrush(QBrush(QColor(self._color)))
            p.drawRoundedRect(0, 3, 2, self.height() - 6, 1, 1)
            p.end()
        super().paintEvent(e)


# ═══ Main Effects Panel ═══

class EffectsPanel(QWidget):
    effect_clicked = pyqtSignal(str)
    catalog_clicked = pyqtSignal()
    preset_clicked = pyqtSignal(str)
    preset_new_clicked = pyqtSignal()
    preset_manage_clicked = pyqtSignal()
    import_clicked = pyqtSignal()
    quick_apply = pyqtSignal(str)         # step 38: right-click quick apply

    def __init__(self, parent=None):
        """Initialise le widget EffectsPanel."""
        super().__init__(parent)
        self.setFixedWidth(220)
        self._plugins = {}
        self._tag_presets = {}
        self._all_presets = []
        self._search_text = ""
        self._show_effects = True
        self._show_presets = True
        self._favorites: set[str] = set()   # step 37
        self._load_favorites()

        # Base background for the panel
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(pal.ColorRole.Window, QColor(COLORS['bg_panel']))
        self.setPalette(pal)

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # Header — forced bg_medium via palette (not stylesheet cascade)
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setAutoFillBackground(True)
        hdr_pal = hdr.palette()
        hdr_pal.setColor(hdr_pal.ColorRole.Window, QColor(COLORS['bg_medium']))
        hdr.setPalette(hdr_pal)
        hdr.setStyleSheet(f"border-bottom: 1px solid {COLORS['border']};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(8, 0, 8, 0)
        tt = QLabel("EFFECTS")
        tt.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 11px; "
            f"font-weight: bold; letter-spacing: 1px;"
        )
        hl.addWidget(tt)
        self._btn_fx = self._tab("FX", True)
        self._btn_fx.clicked.connect(self._toggle_fx)
        self._btn_pr = self._tab("PR", True)
        self._btn_pr.clicked.connect(self._toggle_pr)
        # Multi-select toggle (step 40)
        hl.addWidget(self._btn_fx)
        hl.addWidget(self._btn_pr)
        lo.addWidget(hdr)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("\U0001f50d Search...")
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {COLORS['bg_panel']}; color: {COLORS['text']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; "
            f"padding: 4px 8px; font-size: 11px; margin: 4px 8px; }}"
            f"QLineEdit:focus {{ border: 1px solid {COLORS['accent']}; }}"
        )
        self._search.textChanged.connect(self._on_search)
        lo.addWidget(self._search)

        # Separator below search (same style as header border)
        sep_search = QFrame()
        sep_search.setFrameShape(QFrame.Shape.HLine)
        sep_search.setFrameShadow(QFrame.Shadow.Plain)
        sep_search.setFixedHeight(1)
        sep_search.setStyleSheet(f"background: {COLORS['border']}; border: none;")
        lo.addWidget(sep_search)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {COLORS['bg_panel']}; border: none; }}"
            f"QScrollBar:vertical {{ background: {COLORS['bg_panel']}; width: 8px;"
            f" margin: 0; border: none; }}"
            f"QScrollBar::handle:vertical {{ background: {COLORS['border']};"
            f" border-radius: 4px; min-height: 30px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: {COLORS['accent']}; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: {COLORS['bg_panel']}; }}"
        )
        lo.addWidget(self._scroll)

        # Footer
        foot = QWidget()
        foot.setFixedHeight(32)
        foot.setStyleSheet(
            f"background: {COLORS['bg_medium']}; "
            f"border-top: 1px solid {COLORS['border']};"
        )
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(4, 0, 4, 0)
        fl.setSpacing(2)
        self._btn_catalog = self._sbtn("\U0001f4d6 Catalog")
        self._btn_catalog.clicked.connect(self.catalog_clicked.emit)
        self._btn_import = self._sbtn("⬇ Import")
        self._btn_import.clicked.connect(self.import_clicked.emit)
        self._btn_new = self._sbtn("\uff0b Preset")
        self._btn_new.clicked.connect(self.preset_new_clicked.emit)
        self._btn_manage = self._sbtn("\u2699")
        self._btn_manage.clicked.connect(self.preset_manage_clicked.emit)
        fl.addWidget(self._btn_catalog)
        fl.addWidget(self._btn_import)
        fl.addWidget(self._btn_new)
        fl.addWidget(self._btn_manage)
        lo.addWidget(foot)

        self.reload_plugins()

    def _load_favorites(self):
        """Load favorites from settings."""
        s = load_settings()
        self._favorites = set(s.get("favorites", []))

    def _save_favorites(self):
        """Save favorites to settings."""
        s = load_settings()
        s["favorites"] = list(self._favorites)
        save_settings(s)

    def _on_fav_toggle(self, eid, is_fav):
        """Handle favorite toggle."""
        if is_fav:
            self._favorites.add(eid)
        else:
            self._favorites.discard(eid)
        self._save_favorites()
        self._rebuild()

    def reload_plugins(self):
        """Recharge la liste des plugins apres import."""
        self._plugins = load_plugins(force_reload=True)
        self._rebuild()

    def set_presets(self, tag_map, all_presets):
        """Met a jour la liste des presets affichee."""
        self._tag_presets = tag_map
        self._all_presets = all_presets
        self._rebuild()

    def _tab(self, text, active):
        """Cree un bouton d onglet (Effets / Presets)."""
        b = QPushButton(text)
        b.setFixedSize(28, 22)
        b.setCheckable(True)
        b.setChecked(active)
        b.setStyleSheet(
            f"QPushButton {{ background: {COLORS['bg_dark']}; color: {COLORS['text_dim']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 3px; "
            f"font-size: 9px; font-weight: bold; }}"
            f"QPushButton:checked {{ background: {COLORS['accent']}; color: white; border: none; }}"
        )
        return b

    def _sbtn(self, text):
        """Cree un petit bouton pour la section presets."""
        b = QPushButton(text)
        b.setFixedHeight(24)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(
            f"QPushButton {{ background: {COLORS['button_bg']}; color: {COLORS['text']}; "
            f"border: none; border-radius: 3px; font-size: 10px; padding: 0 6px; }}"
            f"QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}"
        )
        return b

    def _toggle_fx(self):
        """Bascule sur l onglet Effets."""
        self._show_effects = self._btn_fx.isChecked()
        self._rebuild()

    def _toggle_pr(self):
        """Bascule sur l onglet Presets."""
        self._show_presets = self._btn_pr.isChecked()
        self._rebuild()

    def _on_search(self, text):
        """Filtre les effets selon le texte de recherche."""
        self._search_text = text.strip().lower()
        self._rebuild()

    def _rebuild(self):
        """Reconstruit la liste des effets apres changement de langue."""
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(2)
        lang = get_language()
        q = self._search_text

        def _make_btn(plugin):
            name = plugin.get_name(lang)
            short = plugin.get_short(lang)
            is_fav = plugin.id in self._favorites
            btn = EffectButton(
                plugin.icon, plugin.color, name, plugin.id,
                short_desc=short,
                preview_path=plugin.get_preview_path(),
                is_fav=is_fav,
            )
            btn.clicked.connect(lambda pid=plugin.id: self.effect_clicked.emit(pid))
            btn.fav_toggled.connect(self._on_fav_toggle)
            btn.right_clicked.connect(lambda pid: self.quick_apply.emit(pid))
            return btn

        # ── Effects ──
        if self._show_effects and self._plugins:
            grouped = plugins_grouped(self._plugins, lang)
            if q:
                matching = [
                    (p, p.get_name(lang))
                    for p in self._plugins.values()
                    if q in p.get_name(lang).lower() or q in p.id
                ]
                if matching:
                    cl.addWidget(self._slabel("EFFECTS"))
                    for plugin, name in sorted(matching, key=lambda x: x[1]):
                        cl.addWidget(_make_btn(plugin))
            else:
                # Favorites section first (step 37)
                first_section = True
                if self._favorites:
                    fav_plugins = [p for p in self._plugins.values() if p.id in self._favorites]
                    if fav_plugins:
                        section = CollapsibleSection(t("effects.favorites"), start_expanded=True)
                        for plugin in sorted(fav_plugins, key=lambda p: p.get_name(lang)):
                            section.add_widget(_make_btn(plugin))
                        cl.addWidget(section)
                        first_section = False

                # Regular sections
                for sec_label, sec_plugins in grouped:
                    if not first_section:
                        cl.addWidget(self._sep())
                    section = CollapsibleSection(sec_label, start_expanded=True)
                    for plugin in sec_plugins:
                        section.add_widget(_make_btn(plugin))
                    cl.addWidget(section)
                    first_section = False

        # ── Presets (collapsible, CLOSED by default) ──
        if self._show_presets and self._all_presets:
            cl.addWidget(self._sep())
            cl.addWidget(self._slabel("PRESETS"))

            if q:
                mp = [
                    p for p in self._all_presets
                    if q in p["name"].lower() or q in p.get("description", "").lower()
                ]
                for p in mp:
                    item = PresetItem(p["name"], p.get("description", ""), p.get("tags", []))
                    item.clicked.connect(self.preset_clicked.emit)
                    cl.addWidget(item)
            else:
                first_preset = True
                for tag, presets in sorted(self._tag_presets.items()):
                    if not first_preset:
                        cl.addWidget(self._sep())
                    section = CollapsibleSection(tag, start_expanded=False)
                    for p in presets:
                        item = PresetItem(p["name"], p.get("description", ""), p.get("tags", []))
                        item.clicked.connect(self.preset_clicked.emit)
                        section.add_widget(item)
                    cl.addWidget(section)
                    first_preset = False

                # Untagged presets
                tagged = set()
                for presets in self._tag_presets.values():
                    for p in presets:
                        tagged.add(p["name"])
                untagged = [p for p in self._all_presets if p["name"] not in tagged]
                if untagged:
                    section = CollapsibleSection("Other", start_expanded=False)
                    for p in untagged:
                        item = PresetItem(p["name"], p.get("description", ""), p.get("tags", []))
                        item.clicked.connect(self.preset_clicked.emit)
                        section.add_widget(item)
                    cl.addWidget(section)

        cl.addStretch()
        self._scroll.setWidget(container)

    def _slabel(self, text):
        """Cree un label de section."""
        l = QLabel(text)
        l.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 9px; "
            f"font-weight: bold; padding: 6px 8px 2px 8px; letter-spacing: 1px;"
        )
        return l

    def _sep(self):
        """Cree un separateur horizontal fin, meme style que sous le header EFFECTS."""
        s = QFrame()
        s.setFrameShape(QFrame.Shape.HLine)
        s.setFrameShadow(QFrame.Shadow.Plain)
        s.setFixedHeight(1)
        s.setStyleSheet(f"background: {COLORS['border']}; border: none; margin: 2px 8px;")
        return s
