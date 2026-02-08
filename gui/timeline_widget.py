"""Timeline widget — drag-to-reorder clips, draggable blue anchor, cut-at-anchor."""
import numpy as np
from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPolygonF
from utils.config import COLORS
from utils.translator import t

ANCHOR_GRAB_PX = 7  # pixels tolerance for grabbing the anchor line


class TimelineWidget(QWidget):
    clip_selected = pyqtSignal(str)
    split_requested = pyqtSignal(str, int)
    duplicate_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    fade_in_requested = pyqtSignal(str)
    fade_out_requested = pyqtSignal(str)
    clips_reordered = pyqtSignal()
    seek_requested = pyqtSignal(int)  # sample position

    def __init__(self, timeline=None, parent=None):
        """Initialise le widget timeline avec la reference au modele Timeline."""
        super().__init__(parent)
        self.timeline = timeline
        self.sample_rate = 44100
        self.setMinimumHeight(70); self.setMaximumHeight(100)
        self._selected_id: str | None = None
        self._playhead_sample: int = 0
        self._anchor_sample: int | None = None  # blue cursor

        # Drag state
        self._drag_src = None        # clip being dragged (reorder)
        self._drag_x = 0
        self._dragging_clip = False  # True = dragging a clip to reorder
        self._dragging_anchor = False  # True = dragging the blue anchor
        self._press_x = 0
        self._did_action = False

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx_menu)
        self.setMouseTracking(True)  # for cursor changes near anchor

    # ── Setters ──

    def set_playhead(self, sample_pos, sr):
        """Met a jour la position du playhead sur la timeline."""
        self.sample_rate = sr
        self._playhead_sample = sample_pos
        self.update()

    def set_anchor(self, sample_pos):
        """Definit la position du curseur ancre."""
        self._anchor_sample = sample_pos
        self.update()

    def clear_anchor(self):
        """Efface le curseur ancre."""
        self._anchor_sample = None
        self.update()

    # ── Coordinate helpers ──

    def _x_to_sample(self, x):
        """Convertit pixel X en position sample sur la timeline."""
        if not self.timeline:
            return 0
        total = self.timeline.total_duration_samples
        if total <= 0:
            return 0
        return int(max(0, min(x / self.width(), 1.0)) * total)

    def _sample_to_x(self, sample_pos):
        """Convertit position sample en pixel X."""
        if not self.timeline:
            return 0
        total = self.timeline.total_duration_samples
        if total <= 0:
            return 0
        return int(sample_pos / total * self.width())

    def _clip_at(self, x):
        """Retourne le clip a la position sample donnee (ou None)."""
        if not self.timeline or not self.timeline.clips: return None
        total = self.timeline.total_duration_samples
        if total == 0: return None
        for c in self.timeline.clips:
            x1 = int(c.position / total * self.width())
            x2 = int(c.end_position / total * self.width())
            if x1 <= x <= x2: return c
        return None

    def _near_anchor(self, x):
        """Is x within grab range of the blue anchor?"""
        if self._anchor_sample is None:
            return False
        ax = self._sample_to_x(self._anchor_sample)
        return abs(x - ax) <= ANCHOR_GRAB_PX

    def _clip_for_sample(self, sample_pos):
        """Find the clip containing sample_pos."""
        if not self.timeline:
            return None
        for c in self.timeline.clips:
            if c.position <= sample_pos < c.end_position:
                return c
        return None

    # ── Mouse events ──

    def mousePressEvent(self, e):
        """Clic gauche = select clip, clic droit = menu contextuel."""
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._press_x = int(e.position().x())
        self._did_action = False
        self._dragging_clip = False
        self._dragging_anchor = False
        self._drag_src = None

        # Priority 1: grab existing anchor line → start anchor drag
        if self._near_anchor(self._press_x):
            self._dragging_anchor = True
            self.update()
            return

        # Priority 2: click on a clip → select it
        if self.timeline and self.timeline.clips:
            clip = self._clip_at(self._press_x)
            if clip:
                self._selected_id = clip.id
                self._drag_src = clip
                self.clip_selected.emit(clip.id)
                self._did_action = True
            else:
                # Empty space → place anchor
                self._drag_src = None
                self._selected_id = None
                sample_pos = self._x_to_sample(self._press_x)
                self._anchor_sample = sample_pos
                self._dragging_anchor = True  # allow immediate drag
                self._did_action = True
                self.seek_requested.emit(sample_pos)

        self.update()

    def mouseMoveEvent(self, e):
        """Drag d un clip sur la timeline."""
        mx = int(e.position().x())

        # Anchor dragging
        if self._dragging_anchor:
            sample_pos = self._x_to_sample(mx)
            self._anchor_sample = sample_pos
            self.seek_requested.emit(sample_pos)
            self.update()
            return

        # Clip reorder dragging
        if self._drag_src and abs(mx - self._press_x) > 8:
            self._dragging_clip = True
            self._drag_x = mx
            self.update()
            return

        # Hover: change cursor near anchor
        if self._near_anchor(mx):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        # Clip reorder
        """Fin du drag — repositionne le clip."""
        if self._dragging_clip and self._drag_src and self.timeline:
            try:
                target = self._clip_at(int(e.position().x()))
                if target and target.id != self._drag_src.id:
                    clips = self.timeline.clips
                    if self._drag_src in clips and target in clips:
                        src_idx = clips.index(self._drag_src)
                        tgt_idx = clips.index(target)
                        clip = clips.pop(src_idx)
                        if src_idx < tgt_idx:
                            tgt_idx -= 1
                        clips.insert(tgt_idx, clip)
                        pos = 0
                        for c in clips:
                            c.position = pos
                            pos += c.duration_samples
                        self.clips_reordered.emit()
            except (ValueError, IndexError, RuntimeError) as ex:
                print(f"[timeline] drag error: {ex}")

        # Simple click on clip (no drag) → set anchor but DON'T clear clip selection
        # (clip_selected already set the waveform selection in _on_clip_sel)
        if not self._dragging_clip and not self._dragging_anchor and self._drag_src:
            # Just set anchor visually, don't clear the selection
            sample_pos = self._x_to_sample(self._press_x)
            self._anchor_sample = sample_pos

        self._drag_src = None
        self._dragging_clip = False
        self._dragging_anchor = False
        self.update()

    # ── Context menu ──

    def _ctx_menu(self, pos):
        """Affiche le menu contextuel d un clip (split, delete, fade, etc)."""
        clip = self._clip_at(pos.x())
        if not clip: return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background: {COLORS['bg_medium']}; color: {COLORS['text']}; border: 1px solid {COLORS['border']}; font-size: 11px; }}
            QMenu::item {{ padding: 5px 20px; }} QMenu::item:selected {{ background: {COLORS['accent']}; }}
        """)
        cid = clip.id
        total = self.timeline.total_duration_samples

        # Cut position: use blue anchor if it's inside this clip, else use click position
        if (self._anchor_sample is not None
                and clip.position < self._anchor_sample < clip.end_position):
            cut_pos = self._anchor_sample - clip.position
            cut_label = "✂ Cut at cursor"
        else:
            cut_pos = int(pos.x() / self.width() * total) - clip.position if total > 0 else 0
            cut_label = "✂ Cut here"

        menu.addAction(cut_label, lambda: self.split_requested.emit(cid, max(1, cut_pos)))
        menu.addAction("Duplicate", lambda: self.duplicate_requested.emit(cid))
        menu.addSeparator()
        menu.addAction("Fade In", lambda: self.fade_in_requested.emit(cid))
        menu.addAction("Fade Out", lambda: self.fade_out_requested.emit(cid))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self.delete_requested.emit(cid))
        menu.exec(self.mapToGlobal(pos))

    # ── Paint ──

    def paintEvent(self, e):
        """Dessine les clips, le playhead et le curseur."""
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(COLORS['bg_medium']))

        # Time ruler
        p.setPen(QColor(COLORS['text_dim'])); p.setFont(QFont("Consolas", 8))
        total_s = self.timeline.total_duration_seconds if self.timeline else 0
        if total_s <= 0: total_s = 8
        step = max(1, int(total_s / 8))
        for s in range(0, int(total_s) + 1, step):
            x = int(s / total_s * w) if total_s > 0 else 0
            p.drawText(x + 2, 10, f"{s//60:02d}:{s%60:02d}.00")
            p.drawLine(x, 12, x, h)

        if not self.timeline or not self.timeline.clips:
            p.setPen(QColor(COLORS['text_dim'])); p.setFont(QFont("Segoe UI", 10))
            p.drawText(0, 14, w, h - 14, Qt.AlignmentFlag.AlignCenter, t("timeline.empty"))
            p.end(); return

        total = self.timeline.total_duration_samples
        if total == 0: p.end(); return
        y0 = 14

        for i, c in enumerate(self.timeline.clips):
            x1 = int(c.position / total * w)
            x2 = int(c.end_position / total * w)
            cw = max(x2 - x1, 2)
            col = QColor(c.color if c.color else "#533483")
            col.setAlpha(160)
            p.fillRect(x1, y0, cw, h - y0 - 2, col)

            # Mini waveform
            if c.audio_data is not None and len(c.audio_data) > 0 and cw > 4:
                mono = np.mean(c.audio_data, axis=1) if c.audio_data.ndim > 1 else c.audio_data
                step_w = max(1, len(mono) // cw)
                mid = y0 + (h - y0 - 2) // 2
                ah = (h - y0 - 2) // 2 - 2
                p.setPen(QPen(QColor(255, 255, 255, 120), 1))
                for x in range(cw):
                    i0 = x * step_w; i1 = min(i0 + step_w, len(mono))
                    if i0 >= len(mono): break
                    pk = float(np.max(np.abs(mono[i0:i1])))
                    hy = int(pk * ah)
                    p.drawLine(x1 + x, mid - hy, x1 + x, mid + hy)

            # Label
            p.setPen(QColor("white")); p.setFont(QFont("Segoe UI", 8))
            dur = c.duration_seconds
            label = f"{c.name} ({dur:.1f}s)"
            p.drawText(x1 + 4, y0 + 12, label)

            # Selection border
            if c.id == self._selected_id:
                p.setPen(QPen(QColor(COLORS['accent']), 2))
                p.drawRect(x1, y0, cw, h - y0 - 2)

        # Drag ghost (clip reorder)
        if self._dragging_clip and self._drag_src:
            p.fillRect(self._drag_x - 20, y0, 40, h - y0 - 2, QColor(108, 92, 231, 80))
            p.setPen(QPen(QColor(COLORS['accent']), 2, Qt.PenStyle.DashLine))
            p.drawLine(self._drag_x, y0, self._drag_x, h - 2)

        # Blue anchor cursor (draggable)
        if self._anchor_sample is not None:
            ax = self._sample_to_x(self._anchor_sample)
            if 0 <= ax <= w:
                p.setPen(QPen(QColor("#3b82f6"), 2))
                p.drawLine(ax, 0, ax, h)
                # Triangle marker at top
                p.setBrush(QColor("#3b82f6"))
                p.setPen(Qt.PenStyle.NoPen)
                tri = QPolygonF([QPointF(ax - 5, 0), QPointF(ax + 5, 0), QPointF(ax, 7)])
                p.drawPolygon(tri)
                # Small grab handle at bottom
                tri2 = QPolygonF([QPointF(ax - 5, h), QPointF(ax + 5, h), QPointF(ax, h - 7)])
                p.drawPolygon(tri2)

        # Green playhead
        px = self._sample_to_x(self._playhead_sample)
        p.setPen(QPen(QColor(COLORS['playhead']), 2))
        p.drawLine(px, 0, px, h)
        p.end()
