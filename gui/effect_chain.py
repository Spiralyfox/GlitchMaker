"""Effect Chain — Left sidebar panel (below effects).
v4.4 — Shows active ops with toggle, reorder (up/down), delete.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QColor, QPainter, QFont
from utils.config import get_colors, COLORS
from utils.translator import t


class _ChainItem(QWidget):
    toggled = pyqtSignal(str)
    deleted = pyqtSignal(str)
    move_up = pyqtSignal(str)
    move_down = pyqtSignal(str)

    def __init__(self, uid, name, color, enabled=True, parent=None):
        super().__init__(parent)
        self._uid = uid; self._color = color; self._hovered = False
        self.setFixedHeight(26)
        C = get_colors()
        lo = QHBoxLayout(self); lo.setContentsMargins(4,1,4,1); lo.setSpacing(3)

        btn_t = QPushButton("●" if enabled else "○")
        btn_t.setFixedSize(14,14)
        btn_t.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        tc = color if enabled else C['text_dim']
        btn_t.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {tc}; border: none; font-size: 10px; }}"
            f"QPushButton:hover {{ color: {COLORS['accent']}; }}")
        btn_t.clicked.connect(lambda: self.toggled.emit(self._uid))
        lo.addWidget(btn_t)

        ns = f"color: {C['text']};" if enabled else f"color: {C['text_dim']};"
        lbl = QLabel(name); lbl.setStyleSheet(f"{ns} font-size: 10px;")
        lo.addWidget(lbl, stretch=1)

        _bs = (f"QPushButton {{ background: transparent; color: {C['text_dim']};"
               f" border: none; font-size: 9px; padding: 0; }}"
               f"QPushButton:hover {{ color: {COLORS['accent']}; }}")
        for txt, sig in [("▲", self.move_up), ("▼", self.move_down), ("✕", self.deleted)]:
            b = QPushButton(txt); b.setFixedSize(14,14)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setStyleSheet(_bs)
            b.clicked.connect(lambda _, s=sig: s.emit(self._uid))
            lo.addWidget(b)

    def enterEvent(self, e): self._hovered = True; self.update()
    def leaveEvent(self, e): self._hovered = False; self.update()
    def paintEvent(self, e):
        if self._hovered:
            p = QPainter(self); c = QColor(self._color); c.setAlpha(15)
            p.fillRect(0,0,self.width(),self.height(),c); p.end()
        super().paintEvent(e)


class EffectChainWidget(QWidget):
    """Left sidebar chain panel — ops with reorder/toggle/delete."""
    op_toggled = pyqtSignal(str)
    op_deleted = pyqtSignal(str)
    op_moved = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60); self.setMaximumHeight(250)
        C = get_colors()
        lo = QVBoxLayout(self); lo.setContentsMargins(0,0,0,0); lo.setSpacing(0)

        hdr = QWidget(); hdr.setFixedHeight(22)
        hdr.setStyleSheet(f"background: {C['bg_medium']}; border-top: 1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(8,0,8,0)
        title = QLabel(t("chain.title"))
        title.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px; font-weight: bold;")
        hl.addWidget(title); hl.addStretch()
        self._cnt = QLabel("0")
        self._cnt.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px;")
        hl.addWidget(self._cnt)
        lo.addWidget(hdr)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {C['bg_panel']}; border: none; }}"
            f"QScrollBar:vertical {{ background: {C['bg_panel']}; width: 5px; }}"
            f"QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}")
        lo.addWidget(self._scroll)
        self._ops = []; self._rebuild()

    def set_ops(self, ops):
        self._ops = list(ops); self._rebuild()

    def _rebuild(self):
        C = get_colors()
        w = QWidget()
        lo = QVBoxLayout(w); lo.setContentsMargins(2,2,2,2); lo.setSpacing(1)
        for op in self._ops:
            item = _ChainItem(
                uid=op.get('uid',''), name=op.get('name','?'),
                color=op.get('color','#6c5ce7'), enabled=op.get('enabled', True))
            item.toggled.connect(self.op_toggled.emit)
            item.deleted.connect(self.op_deleted.emit)
            item.move_up.connect(lambda uid: self.op_moved.emit(uid, -1))
            item.move_down.connect(lambda uid: self.op_moved.emit(uid, 1))
            lo.addWidget(item)
        if not self._ops:
            lbl = QLabel(t("chain.empty"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px; padding: 8px;")
            lo.addWidget(lbl)
        lo.addStretch()
        self._scroll.setWidget(w)
        self._cnt.setText(str(len(self._ops)))
