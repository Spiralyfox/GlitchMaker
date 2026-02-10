"""History panel — Right sidebar.
Displays all actions (effects, cuts, fades, recordings, clip adds, automations, etc.)
with toggle, individual delete, and visual "overridden" state for ops
that precede the last structural action.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QColor, QPainter, QFont, QBrush
from utils.config import get_colors, COLORS
from utils.translator import t


# ── Action type metadata: icon, default color ──
_ACTION_META = {
    "effect":       ("🎛", "#6c5ce7"),
    "automation":   ("📈", "#7c3aed"),
    "cut_silence":  ("✂", "#e17055"),
    "cut_splice":   ("✂", "#e17055"),
    "fade_in":      ("🔊", "#00b894"),
    "fade_out":     ("🔉", "#00b894"),
    "add_clip":     ("➕", "#0984e3"),
    "record":       ("🎙", "#d63031"),
    "delete_clip":  ("🗑", "#636e72"),
    "normalize":    ("📊", "#fdcb6e"),
    "split":        ("✂", "#e17055"),
    "duplicate":    ("📋", "#0984e3"),
    "reorder":      ("↕", "#636e72"),
}

# Types that are structural (modify timeline, not toggleable)
_STRUCTURAL_TYPES = frozenset({
    "cut_silence", "cut_splice", "fade_in", "fade_out",
    "add_clip", "record", "delete_clip", "split", "duplicate", "reorder",
})


def _get_action_icon(op: dict) -> str:
    action_type = op.get("type", "effect")
    meta = _ACTION_META.get(action_type, _ACTION_META["effect"])
    return meta[0]


def _get_action_color(op: dict) -> str:
    if op.get("color"):
        return op["color"]
    action_type = op.get("type", "effect")
    meta = _ACTION_META.get(action_type, _ACTION_META["effect"])
    return meta[1]


def _get_scope_label(op: dict) -> str:
    action_type = op.get("type", "effect")
    if action_type in _STRUCTURAL_TYPES:
        return ""
    if op.get("is_global"):
        return "global"
    return "local"


class _HistItem(QWidget):
    delete_clicked = pyqtSignal(str)
    toggle_clicked = pyqtSignal(str)

    def __init__(self, uid, index, name, scope, color="#6c5ce7",
                 timestamp="", enabled=True, icon="🎛",
                 toggleable=True, overridden=False, parent=None):
        super().__init__(parent)
        self._uid = uid; self._color = color; self._hovered = False
        self._overridden = overridden
        self.setFixedHeight(44); self.setMinimumWidth(180)
        C = get_colors()
        lo = QHBoxLayout(self); lo.setContentsMargins(8, 4, 8, 4); lo.setSpacing(6)

        # Icon label
        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(20, 20)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        opacity = "0.35" if overridden else "1.0"
        icon_lbl.setStyleSheet(f"font-size: 13px; background: transparent; opacity: {opacity};")
        lo.addWidget(icon_lbl)

        # Toggle button (only for toggleable, non-overridden effects)
        if toggleable and not overridden:
            btn_t = QPushButton("●" if enabled else "○")
            btn_t.setFixedSize(20, 20)
            btn_t.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            tc = color if enabled else C['text_dim']
            btn_t.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {tc}; border: none; font-size: 14px; }}"
                f"QPushButton:hover {{ color: {COLORS['accent']}; }}")
            btn_t.clicked.connect(lambda: self.toggle_clicked.emit(self._uid))
            lo.addWidget(btn_t)

        # Name + meta
        col = QVBoxLayout(); col.setSpacing(0); col.setContentsMargins(0, 0, 0, 0)
        if overridden:
            ns = f"color: {C['text_dim']}; font-style: italic;"
        elif not enabled:
            ns = f"color: {C['text_dim']}; text-decoration: line-through;"
        else:
            ns = f"color: {C['text']};"
        lbl = QLabel(f"{index + 1}. {name}")
        lbl.setStyleSheet(f"{ns} font-size: 11px; font-weight: bold;")
        col.addWidget(lbl)
        parts = [s for s in [scope, timestamp] if s]
        if overridden:
            parts.append(t("history.overridden"))
        if parts:
            meta = QLabel(" · ".join(parts))
            meta.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px;")
            col.addWidget(meta)
        lo.addLayout(col, stretch=1)

        # Delete button
        btn_d = QPushButton("✕"); btn_d.setFixedSize(22, 22)
        btn_d.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_d.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C['text_dim']}; border: none; font-size: 12px; }}"
            f"QPushButton:hover {{ color: #e94560; }}")
        btn_d.clicked.connect(lambda: self.delete_clicked.emit(self._uid))
        lo.addWidget(btn_d)

    def enterEvent(self, e): self._hovered = True; self.update()
    def leaveEvent(self, e): self._hovered = False; self.update()
    def paintEvent(self, e):
        if self._hovered:
            p = QPainter(self); c = QColor(self._color)
            c.setAlpha(10 if self._overridden else 20)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(QBrush(c))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(0, 0, self.width(), self.height(), 4, 4)
            p.end()
        super().paintEvent(e)


class EffectHistoryPanel(QWidget):
    """Right sidebar — displays all actions with toggle/delete."""
    op_deleted = pyqtSignal(str)
    op_toggled = pyqtSignal(str)
    clear_all = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(220); self.setMaximumWidth(300)
        C = get_colors()

        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(pal.ColorRole.Window, QColor(C['bg_panel']))
        self.setPalette(pal)

        lo = QVBoxLayout(self); lo.setContentsMargins(0, 0, 0, 0); lo.setSpacing(0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(36)
        hdr.setAutoFillBackground(True)
        hdr_pal = hdr.palette()
        hdr_pal.setColor(hdr_pal.ColorRole.Window, QColor(C['bg_medium']))
        hdr.setPalette(hdr_pal)
        hdr.setStyleSheet(f"border-bottom: 1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(10, 0, 10, 0)
        title = QLabel(t("view.history"))
        title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C['text']}; background: transparent;")
        hl.addWidget(title); hl.addStretch()
        self._count = QLabel("0")
        self._count.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
        hl.addWidget(self._count)

        # Clear all button
        self._btn_clear = QPushButton("⟲")
        self._btn_clear.setFixedSize(22, 22)
        self._btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_clear.setToolTip(t("history.clear_all"))
        self._btn_clear.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C['text_dim']}; border: none; font-size: 13px; }}"
            f"QPushButton:hover {{ color: #e94560; }}")
        self._btn_clear.clicked.connect(self.clear_all.emit)
        self._btn_clear.setVisible(False)
        hl.addWidget(self._btn_clear)
        lo.addWidget(hdr)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {C['bg_panel']}; border: none; }}"
            f"QScrollBar:vertical {{ background: {C['bg_panel']}; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 3px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}")
        lo.addWidget(self._scroll)
        self._ops = []
        self._last_struct_idx = -1
        self._rebuild()

    def set_ops(self, ops, last_struct_idx=-1):
        self._ops = list(ops)
        self._last_struct_idx = last_struct_idx
        self._rebuild()

    def _rebuild(self):
        C = get_colors()
        w = QWidget()
        w.setStyleSheet(f"background: {C['bg_panel']};")
        lo = QVBoxLayout(w); lo.setContentsMargins(4, 4, 4, 4); lo.setSpacing(0)

        last_si = self._last_struct_idx

        for i, op in enumerate(self._ops):
            if i > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {C['border']}; margin: 0 4px;")
                lo.addWidget(sep)

            action_type = op.get("type", "effect")
            icon = _get_action_icon(op)
            color = _get_action_color(op)
            scope = _get_scope_label(op)

            is_structural = action_type in _STRUCTURAL_TYPES
            toggleable = action_type in ("effect", "automation")

            # An effect/automation is "overridden" if it comes BEFORE the last
            # structural op (since structural ops reset the audio state).
            overridden = (not is_structural and i < last_si)

            item = _HistItem(
                uid=op.get('uid', ''), index=i,
                name=op.get('name', '?'),
                scope=scope,
                color=color,
                timestamp=op.get('timestamp', ''),
                enabled=op.get('enabled', True),
                icon=icon,
                toggleable=toggleable,
                overridden=overridden)
            item.delete_clicked.connect(self.op_deleted.emit)
            item.toggle_clicked.connect(self.op_toggled.emit)
            lo.addWidget(item)

        if not self._ops:
            lbl = QLabel(t("history.empty"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; padding: 24px;")
            lbl.setWordWrap(True); lo.addWidget(lbl)
        lo.addStretch()
        self._scroll.setWidget(w)
        self._count.setText(str(len(self._ops)))
        self._btn_clear.setVisible(len(self._ops) > 0)
