"""Effects panel — sidebar with search, effects & presets.
Redesigned: better buttons with hover tooltips, collapsible preset sections (closed by default).
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QToolTip, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QCursor, QColor, QFont, QPainter, QBrush, QPen

from utils.config import COLORS
from utils.translator import get_language, t
from plugins.loader import load_plugins, plugins_grouped
from plugins import preview_player


# ═══ Effect Button (redesigned) ═══

class EffectButton(QWidget):
    """Styled effect button with colored badge, name, and hover tooltip."""
    clicked = pyqtSignal()

    def __init__(self, letter, color, name, eid, short_desc="", preview_path=None, parent=None):
        super().__init__(parent)
        self._eid = eid
        self._preview_path = preview_path
        self._color = color
        self._hovered = False
        self.setFixedHeight(34)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        if short_desc:
            self.setToolTip(f"<b>{name}</b><br><span style='color: #aaa;'>{short_desc}</span>")

        lo = QHBoxLayout(self)
        lo.setContentsMargins(6, 2, 6, 2)
        lo.setSpacing(8)

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
        self._prev_btn.setToolTip("Preview audio")
        self._prev_btn.clicked.connect(self._on_preview)
        lo.addWidget(self._prev_btn)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def enterEvent(self, e):
        self._hovered = True
        self.update()
        if self._preview_path:
            self._prev_btn.setVisible(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False
        self.update()
        self._prev_btn.setVisible(False)
        super().leaveEvent(e)

    def paintEvent(self, e):
        if self._hovered:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen)
            # Subtle colored tint on hover
            c = QColor(self._color)
            c.setAlpha(25)
            p.setBrush(QBrush(c))
            p.drawRoundedRect(0, 0, self.width(), self.height(), 6, 6)
            # Left accent bar
            p.setBrush(QBrush(QColor(self._color)))
            p.drawRoundedRect(0, 4, 3, self.height() - 8, 1, 1)
            p.end()
        super().paintEvent(e)

    def _on_preview(self):
        if self._preview_path:
            if preview_player.is_playing():
                preview_player.stop_preview()
            else:
                preview_player.play_preview(self._preview_path)


# ═══ Collapsible Section ═══

class CollapsibleSection(QWidget):
    def __init__(self, title, start_expanded=True, parent=None):
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
        arrow = "\u25be" if self._expanded else "\u25b8"
        cnt = f"  ({self._count})" if self._count > 0 else ""
        self._header.setText(f"{arrow}  {self._title}{cnt}")

    def _toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._update_header()

    def add_widget(self, w):
        self._clo.addWidget(w)
        self._count += 1
        self._update_header()


# ═══ Preset Item (compact — colored dot, tooltip, hover accent) ═══

_TAG_COLORS = {
    "Autotune": "#f72585", "Hyperpop": "#ff006e", "Digicore": "#7209b7",
    "Emocore": "#e94560", "Glitch": "#9b2226", "Vocal": "#4cc9f0",
    "Ambient": "#2a9d8f", "Lo-fi": "#606c38", "Aggressive": "#bb3e03",
    "Experimental": "#b5179e", "Electro": "#0ea5e9", "Tape": "#6b705c",
    "Clean": "#16c79a", "Subtle": "#457b9d", "Dariacore": "#c74b50",
    "Rhythmic": "#e07c24", "Psychedelic": "#6d597a", "Bass": "#264653",
    "Cinematic": "#3d5a80",
}


class PresetItem(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, name, desc, tags=None, parent=None):
        super().__init__(parent)
        self._name = name
        self._hovered = False
        self._color = COLORS['accent']
        if tags:
            for tg in tags:
                if tg in _TAG_COLORS:
                    self._color = _TAG_COLORS[tg]; break
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
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)

    def enterEvent(self, e):
        self._hovered = True; self.update(); super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovered = False; self.update(); super().leaveEvent(e)

    def paintEvent(self, e):
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self._plugins = {}
        self._tag_presets = {}
        self._all_presets = []
        self._search_text = ""
        self._show_effects = True
        self._show_presets = True

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(36)
        hdr.setStyleSheet(
            f"background: {COLORS['bg_medium']}; "
            f"border-bottom: 1px solid {COLORS['border']};"
        )
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
        hl.addWidget(self._btn_fx)
        hl.addWidget(self._btn_pr)
        lo.addWidget(hdr)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("\U0001f50d Search...")
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {COLORS['bg_dark']}; color: {COLORS['text']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 4px; "
            f"padding: 4px 8px; font-size: 11px; margin: 4px 8px; }}"
            f"QLineEdit:focus {{ border: 1px solid {COLORS['accent']}; }}"
        )
        self._search.textChanged.connect(self._on_search)
        lo.addWidget(self._search)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {COLORS['bg_medium']}; border: none; }}"
            f"QScrollBar:vertical {{ background: {COLORS['bg_dark']}; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {COLORS['border']}; "
            f"border-radius: 3px; min-height: 20px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
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

    def reload_plugins(self):
        self._plugins = load_plugins(force_reload=True)
        self._rebuild()

    def set_presets(self, tag_map, all_presets):
        self._tag_presets = tag_map
        self._all_presets = all_presets
        self._rebuild()

    def _tab(self, text, active):
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
        self._show_effects = self._btn_fx.isChecked()
        self._rebuild()

    def _toggle_pr(self):
        self._show_presets = self._btn_pr.isChecked()
        self._rebuild()

    def _on_search(self, text):
        self._search_text = text.strip().lower()
        self._rebuild()

    def _rebuild(self):
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(2)
        lang = get_language()
        q = self._search_text

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
                        short = plugin.get_short(lang)
                        btn = EffectButton(
                            plugin.icon, plugin.color, name, plugin.id,
                            short_desc=short,
                            preview_path=plugin.get_preview_path()
                        )
                        btn.clicked.connect(
                            lambda pid=plugin.id: self.effect_clicked.emit(pid)
                        )
                        cl.addWidget(btn)
            else:
                for sec_label, sec_plugins in grouped:
                    section = CollapsibleSection(sec_label, start_expanded=True)
                    for plugin in sec_plugins:
                        name = plugin.get_name(lang)
                        short = plugin.get_short(lang)
                        btn = EffectButton(
                            plugin.icon, plugin.color, name, plugin.id,
                            short_desc=short,
                            preview_path=plugin.get_preview_path()
                        )
                        btn.clicked.connect(
                            lambda pid=plugin.id: self.effect_clicked.emit(pid)
                        )
                        section.add_widget(btn)
                    cl.addWidget(section)

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
                for tag, presets in sorted(self._tag_presets.items()):
                    section = CollapsibleSection(tag, start_expanded=False)
                    for p in presets:
                        item = PresetItem(p["name"], p.get("description", ""), p.get("tags", []))
                        item.clicked.connect(self.preset_clicked.emit)
                        section.add_widget(item)
                    cl.addWidget(section)

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
        l = QLabel(text)
        l.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 9px; "
            f"font-weight: bold; padding: 6px 8px 2px 8px; letter-spacing: 1px;"
        )
        return l

    def _sep(self):
        s = QFrame()
        s.setFrameShape(QFrame.Shape.HLine)
        s.setStyleSheet(f"color: {COLORS['border']};")
        s.setFixedHeight(1)
        return s
