"""Waveform display — zoom via mouse wheel, pixel buffer rendering, anchor cursor, markers."""
from utils.logger import get_logger
_log = get_logger("waveform")
import numpy as np
from PyQt6.QtWidgets import QWidget, QScrollBar, QInputDialog
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QImage, QFont, QPolygonF
from utils.config import COLORS
from utils.translator import t


def _parse_color(hex_str):
    """Convertit un code hex (#RRGGBB) en tuple (R,G,B)."""
    h = hex_str.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class WaveformWidget(QWidget):
    position_clicked = pyqtSignal(int)   # click → set anchor
    selection_changed = pyqtSignal(int, int)  # drag → selection
    drag_started = pyqtSignal()  # mouse down starts a drag
    zoom_changed = pyqtSignal(float, float)  # (zoom, offset) — for external scrollbar
    marker_added = pyqtSignal(str, int)  # (name, position)
    cut_silence_requested = pyqtSignal(int, int)  # (start, end) — replace with silence
    cut_splice_requested = pyqtSignal(int, int)   # (start, end) — remove and splice

    def __init__(self, parent=None):
        """Initialise le widget waveform avec zoom, grille, selection, marqueurs."""
        super().__init__(parent)
        self.audio_data: np.ndarray | None = None
        self.sample_rate = 44100
        self.selection_start: int | None = None
        self.selection_end: int | None = None
        self._clip_hl_start: int | None = None
        self._clip_hl_end: int | None = None
        self._playhead: int = 0
        self._anchor: int | None = None
        self._dragging = False
        self._cache: QImage | None = None
        self._cache_w = 0
        self._cache_h = 0
        self._cache_zoom = 0
        self._cache_offset = 0

        # Zoom state
        self._zoom: float = 1.0
        self._offset: float = 0.0
        self._max_zoom: float = 100.0

        # Beat grid
        self._grid_enabled = False
        self._grid_bpm = 120.0
        self._grid_beats_per_bar = 4
        self._grid_subdiv = 1
        self._grid_offset_ms = 0.0

        # Markers (step 36)
        self._markers: list[dict] = []  # [{name, position, color}]
        self._marker_colors = ["#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff",
                                "#ff85a1", "#48bfe3", "#e07c24", "#b5179e"]
        self._marker_idx = 0

        # Precompute colors
        self._wave_rgb = _parse_color(COLORS['accent'])
        self._bg_rgb = _parse_color(COLORS['bg_dark'])
        self._border_rgb = _parse_color(COLORS['border'])
        self.setMinimumHeight(120)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_grid(self, enabled, bpm=120.0, beats=4, subdiv=1, offset_ms=0.0):
        """Configure la grille de temps (activer, BPM, beats, subdivisions)."""
        self._grid_enabled = enabled
        self._grid_bpm = max(20, bpm)
        self._grid_beats_per_bar = max(1, beats)
        self._grid_subdiv = max(1, subdiv)
        self._grid_offset_ms = offset_ms
        self.update()

    def set_scroll_offset(self, offset):
        """Set offset from external scrollbar (0.0–1.0)."""
        visible = 1.0 / self._zoom
        new_off = max(0.0, min(offset, 1.0 - visible))
        if abs(new_off - self._offset) > 0.0001:
            self._offset = new_off
            self._cache = None
            self.update()

    def set_audio(self, data, sr):
        """Charge les données audio à afficher et réinitialise le zoom."""
        self.audio_data = data
        self.sample_rate = sr
        self._cache = None
        self.update()

    def set_playhead(self, pos):
        """Met a jour la position du playhead (ligne verte)."""
        self._playhead = pos
        self.update()

    def set_selection(self, s, e):
        """Definit la zone de selection (debut, fin en samples). Accepte None."""
        self.selection_start = s if s is not None else None
        self.selection_end = e if e is not None else None
        self.update()

    def set_clip_highlight(self, s, e):
        """Met en surbrillance un clip (bordure verte pointillée)."""
        self._clip_hl_start, self._clip_hl_end = s, e
        self.update()

    def set_anchor(self, pos):
        """Definit la position du curseur ancre (ligne bleue)."""
        self._anchor = pos
        self.update()

    def clear_all(self):
        """Reinitialise la waveform (supprime audio, selection, zoom)."""
        self.selection_start = self.selection_end = None
        self._anchor = None
        self._clip_hl_start = self._clip_hl_end = None
        self.update()

    def clear_selection(self):
        """Efface la selection sans toucher au reste."""
        self.selection_start = self.selection_end = None
        self.update()

    @property
    def bpm(self):
        return self._grid_bpm

    @bpm.setter
    def bpm(self, val):
        self._grid_bpm = max(20, val)
        self._cache = None
        self.update()

    @property
    def grid_subdivisions(self):
        return self._grid_subdiv

    @grid_subdivisions.setter
    def grid_subdivisions(self, val):
        self._grid_subdiv = max(1, val)
        self._cache = None
        self.update()

    def reset_zoom(self):
        """Reset zoom to full view."""
        self._zoom = 1.0
        self._offset = 0.0
        self._cache = None
        self.update()
        self.zoom_changed.emit(self._zoom, self._offset)

    # ── Markers (step 36) ──

    def add_marker(self, name: str, position: int, color: str | None = None):
        """Add a named marker at a sample position."""
        if color is None:
            color = self._marker_colors[self._marker_idx % len(self._marker_colors)]
            self._marker_idx += 1
        self._markers.append({"name": name, "position": position, "color": color})
        self.marker_added.emit(name, position)
        self.update()

    def remove_marker(self, name: str):
        """Remove a marker by name."""
        self._markers = [m for m in self._markers if m["name"] != name]
        self.update()

    def clear_markers(self):
        """Remove all markers."""
        self._markers.clear()
        self._marker_idx = 0
        self.update()

    def get_markers(self) -> list[dict]:
        """Return sorted marker list."""
        return sorted(self._markers, key=lambda m: m["position"])

    def next_marker(self) -> int | None:
        """Return position of next marker after current anchor/playhead."""
        pos = self._anchor if self._anchor is not None else self._playhead
        markers = sorted(self._markers, key=lambda m: m["position"])
        for m in markers:
            if m["position"] > pos + 100:
                return m["position"]
        return markers[0]["position"] if markers else None

    def prev_marker(self) -> int | None:
        """Return position of previous marker before current anchor/playhead."""
        pos = self._anchor if self._anchor is not None else self._playhead
        markers = sorted(self._markers, key=lambda m: m["position"], reverse=True)
        for m in markers:
            if m["position"] < pos - 100:
                return m["position"]
        return markers[0]["position"] if markers else None

    # ── Zoom coordinate mapping ──

    def _visible_range(self):
        """Return (start_sample, end_sample) of the currently visible portion."""
        if self.audio_data is None:
            return 0, 0
        n = len(self.audio_data)
        visible_frac = 1.0 / self._zoom
        start_frac = self._offset
        end_frac = min(start_frac + visible_frac, 1.0)
        return int(start_frac * n), int(end_frac * n)

    def _pos_to_sample(self, x):
        """Convert widget x to sample index (accounting for zoom)."""
        if self.audio_data is None:
            return 0
        n = len(self.audio_data)
        vs, ve = self._visible_range()
        visible_len = max(ve - vs, 1)
        frac = max(0.0, min(x / self.width(), 1.0))
        return int(vs + frac * visible_len)

    def _sample_to_x(self, s):
        """Convert sample index to widget x (accounting for zoom)."""
        if self.audio_data is None or len(self.audio_data) == 0:
            return 0
        vs, ve = self._visible_range()
        visible_len = max(ve - vs, 1)
        return int((s - vs) / visible_len * self.width())

    # ── Mouse events ──

    def mousePressEvent(self, e):
        """Debut de selection ou positionnement du curseur."""
        if e.button() == Qt.MouseButton.LeftButton and self.audio_data is not None:
            self._dragging = True
            pos = self._pos_to_sample(e.position().x())
            self.selection_start = pos
            self.selection_end = pos
            self._clip_hl_start = None
            self._clip_hl_end = None
            self.drag_started.emit()
            self.update()

    def mouseMoveEvent(self, e):
        """Mise a jour de la selection pendant le drag."""
        if self._dragging and self.audio_data is not None:
            self.selection_end = self._pos_to_sample(e.position().x())
            self.update()

    def mouseReleaseEvent(self, e):
        """Fin du drag — emet selection_changed ou position_clicked."""
        if self._dragging:
            self._dragging = False
            if self.selection_start is not None and self.selection_end is not None:
                s = min(self.selection_start, self.selection_end)
                en = max(self.selection_start, self.selection_end)
                if abs(en - s) < 10:
                    self._anchor = s
                    self.selection_start = self.selection_end = None
                    self.position_clicked.emit(s)
                else:
                    self.selection_start, self.selection_end = s, en
                    self._anchor = None
                    self.selection_changed.emit(s, en)
            self.update()

    def contextMenuEvent(self, e):
        """Right-click: add marker, or cut if inside a selection."""
        if self.audio_data is None:
            return
        pos = self._pos_to_sample(e.pos().x())
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {COLORS['bg_panel']}; color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; }}"
            f"QMenu::item {{ padding: 4px 16px; }}"
            f"QMenu::item:selected {{ background: {COLORS['accent']}; color: white; }}")

        # ── Cut options if inside a red selection ──
        a_cut_silence = None
        a_cut_splice = None
        has_sel = (self.selection_start is not None and self.selection_end is not None
                   and abs(self.selection_end - self.selection_start) > 10)
        if has_sel:
            s = min(self.selection_start, self.selection_end)
            en = max(self.selection_start, self.selection_end)
            if s <= pos <= en:
                a_cut_silence = menu.addAction("✂ " + t("cut.replace_silence"))
                a_cut_splice = menu.addAction("✂ " + t("cut.splice"))
                menu.addSeparator()

        # ── Marker options ──
        a_add = menu.addAction("📌 " + t("marker.add_title"))
        a_del = None
        near = None
        for m in self._markers:
            mx = self._sample_to_x(m["position"])
            if abs(mx - e.pos().x()) < 10:
                near = m; break
        if near:
            a_del = menu.addAction(f"✕ Remove '{near['name']}'")
        menu.addSeparator()
        a_clear = menu.addAction(t("marker.clear_all"))

        action = menu.exec(e.globalPos())
        if action is None:
            return
        if action == a_cut_silence and has_sel:
            s = min(self.selection_start, self.selection_end)
            en = max(self.selection_start, self.selection_end)
            self.cut_silence_requested.emit(s, en)
        elif action == a_cut_splice and has_sel:
            s = min(self.selection_start, self.selection_end)
            en = max(self.selection_start, self.selection_end)
            self.cut_splice_requested.emit(s, en)
        elif action == a_add:
            name, ok = QInputDialog.getText(self, t("marker.add_title"),
                                            t("marker.add_prompt"),
                                            text=f"M{len(self._markers)+1}")
            if ok and name:
                self.add_marker(name, pos)
        elif action == a_del and near:
            self.remove_marker(near["name"])
        elif action == a_clear:
            self.clear_markers()

    def wheelEvent(self, e):
        """Mouse wheel → zoom in/out, centered on cursor position."""
        if self.audio_data is None:
            return
        delta = e.angleDelta().y()
        if delta == 0:
            return

        # Cursor position as fraction of visible range
        cursor_x_frac = e.position().x() / max(self.width(), 1)

        old_zoom = self._zoom
        factor = 1.2 if delta > 0 else 1.0 / 1.2
        new_zoom = max(1.0, min(self._zoom * factor, self._max_zoom))

        if new_zoom == old_zoom:
            return

        # Keep the sample under cursor at the same screen position
        old_visible = 1.0 / old_zoom
        new_visible = 1.0 / new_zoom
        cursor_sample_frac = self._offset + cursor_x_frac * old_visible
        new_offset = cursor_sample_frac - cursor_x_frac * new_visible
        new_offset = max(0.0, min(new_offset, 1.0 - new_visible))

        self._zoom = new_zoom
        self._offset = new_offset
        self._cache = None
        self.update()
        self.zoom_changed.emit(self._zoom, self._offset)
        e.accept()

    # ── Paint ──

    def paintEvent(self, e):
        """Dessine la waveform, grille, selection, playhead, curseur."""
        p = QPainter(self)
        try:
            w, h = self.width(), self.height()
            p.fillRect(0, 0, w, h, QColor(COLORS['bg_dark']))

            if self.audio_data is None or len(self.audio_data) == 0:
                p.setPen(QColor(COLORS['text_dim']))
                p.setFont(QFont("Segoe UI", 11))
                p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, t("waveform.empty"))
                return

            # Cache waveform image
            if (self._cache is None or self._cache_w != w or self._cache_h != h
                    or self._cache_zoom != self._zoom or self._cache_offset != self._offset):
                self._cache = self._render_wave(w, h)
                self._cache_w = w
                self._cache_h = h
                self._cache_zoom = self._zoom
                self._cache_offset = self._offset
            p.drawImage(0, 0, self._cache)

            # ── Beat grid ──
            if self._grid_enabled and self.audio_data is not None and self._grid_bpm > 0:
                vs, ve = self._visible_range()
                sr = self.sample_rate
                spb = sr * 60.0 / self._grid_bpm
                sp_sub = spb / self._grid_subdiv
                off = int(self._grid_offset_ms * sr / 1000.0)

                if sp_sub > 1:
                    # High-visibility grid colors
                    bar_pen = QPen(QColor(255, 255, 255, 80), 1)
                    beat_pen = QPen(QColor(255, 255, 255, 45), 1)
                    sub_pen = QPen(QColor(255, 255, 255, 28), 1)
                    font = QFont("Consolas", 7)
                    p.setFont(font)

                    adj_vs = vs - off
                    first_sub = int((adj_vs / sp_sub)) * sp_sub + off
                    if first_sub < vs:
                        first_sub += int(sp_sub)
                    gp = first_sub

                    while gp <= ve:
                        x = self._sample_to_x(int(gp))
                        if 0 <= x <= w:
                            beat_in_song = (gp - off) / spb
                            bar_num = int(beat_in_song / self._grid_beats_per_bar)
                            beat_in_bar = beat_in_song - bar_num * self._grid_beats_per_bar
                            is_bar = abs(beat_in_bar) < 0.01 or abs(beat_in_bar - self._grid_beats_per_bar) < 0.01
                            is_beat = abs(beat_in_bar - round(beat_in_bar)) < 0.01

                            if is_bar:
                                p.setPen(bar_pen)
                                p.drawLine(x, 0, x, h)
                                p.setPen(QColor(255, 255, 255, 70))
                                p.drawText(x + 3, 10, str(bar_num + 1))
                            elif is_beat:
                                p.setPen(beat_pen)
                                p.drawLine(x, 0, x, h)
                            else:
                                p.setPen(sub_pen)
                                p.drawLine(x, 0, x, h)
                        gp += sp_sub

            # Clip highlight (green, dashed)
            if self._clip_hl_start is not None and self._clip_hl_end is not None:
                x1 = self._sample_to_x(self._clip_hl_start)
                x2 = self._sample_to_x(self._clip_hl_end)
                if x2 > 0 and x1 < w:
                    p.fillRect(max(x1, 0), 0, min(x2, w) - max(x1, 0), h, QColor(22, 199, 154, 30))
                    p.setPen(QPen(QColor(COLORS['clip_highlight']), 1, Qt.PenStyle.DashLine))
                    if 0 <= x1 <= w: p.drawLine(x1, 0, x1, h)
                    if 0 <= x2 <= w: p.drawLine(x2, 0, x2, h)

            # Selection (red)
            if self.selection_start is not None and self.selection_end is not None:
                s = min(self.selection_start, self.selection_end)
                en = max(self.selection_start, self.selection_end)
                x1, x2 = self._sample_to_x(s), self._sample_to_x(en)
                if x2 > 0 and x1 < w:
                    p.fillRect(max(x1, 0), 0, min(x2, w) - max(x1, 0), h, QColor(233, 69, 96, 40))
                    p.setPen(QPen(QColor(COLORS['selection']), 1))
                    if 0 <= x1 <= w: p.drawLine(x1, 0, x1, h)
                    if 0 <= x2 <= w: p.drawLine(x2, 0, x2, h)

            # Blue anchor cursor
            has_selection = (self.selection_start is not None and self.selection_end is not None
                             and abs(self.selection_end - self.selection_start) > 10)
            if self._anchor is not None and not has_selection:
                ax = self._sample_to_x(self._anchor)
                if -5 <= ax <= w + 5:
                    p.setPen(QPen(QColor("#3b82f6"), 2))
                    p.drawLine(ax, 0, ax, h)
                    p.setBrush(QColor("#3b82f6"))
                    p.setPen(Qt.PenStyle.NoPen)
                    tri = QPolygonF([QPointF(ax - 4, 0), QPointF(ax + 4, 0), QPointF(ax, 6)])
                    p.drawPolygon(tri)

            # Green playhead
            px = self._sample_to_x(self._playhead)
            if -2 <= px <= w + 2:
                p.setPen(QPen(QColor(COLORS['playhead']), 2))
                p.drawLine(px, 0, px, h)

            # ── Markers (step 36) ──
            if self._markers:
                marker_font = QFont("Segoe UI", 7, QFont.Weight.Bold)
                p.setFont(marker_font)
                for m in self._markers:
                    mx = self._sample_to_x(m["position"])
                    if -5 <= mx <= w + 5:
                        mc = QColor(m["color"])
                        # Vertical line
                        p.setPen(QPen(mc, 1, Qt.PenStyle.DashDotLine))
                        p.drawLine(mx, 0, mx, h)
                        # Flag at top
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(mc)
                        flag_w = min(50, max(20, len(m["name"]) * 6 + 8))
                        p.drawRoundedRect(mx, 0, flag_w, 14, 2, 2)
                        # Text
                        p.setPen(QColor("white"))
                        p.drawText(mx + 3, 10, m["name"])

            # Zoom level indicator (bottom-right text)
            if self._zoom > 1.01:
                p.setPen(QColor(COLORS['text_dim']))
                p.setFont(QFont("Consolas", 8))
                p.drawText(w - 60, h - 4, f"x{self._zoom:.1f}")

        except Exception as ex:
            _log.warning("Waveform paintEvent: %s", ex)
        finally:
            p.end()

    def _render_wave(self, w, h):
        """Render waveform of the visible range using numpy pixel buffer."""
        buf = np.zeros((h, w, 4), dtype=np.uint8)
        br, bg, bb = self._bg_rgb
        buf[:, :, 0] = bb
        buf[:, :, 1] = bg
        buf[:, :, 2] = br
        buf[:, :, 3] = 255

        if self.audio_data is None or len(self.audio_data) == 0:
            img = QImage(buf.data, w, h, w * 4, QImage.Format.Format_ARGB32)
            return img.copy()

        # Extract visible portion
        vs, ve = self._visible_range()
        visible = self.audio_data[vs:ve]
        if len(visible) == 0:
            img = QImage(buf.data, w, h, w * 4, QImage.Format.Format_ARGB32)
            return img.copy()

        mono = np.mean(visible, axis=1) if visible.ndim > 1 else visible
        n = len(mono)
        mid = h // 2

        step = max(1, n // w)
        cols = min(w, n // step if step > 0 else w)
        if cols <= 0:
            img = QImage(buf.data, w, h, w * 4, QImage.Format.Format_ARGB32)
            return img.copy()

        usable = cols * step
        reshaped = mono[:usable].reshape(cols, step)
        mins = np.min(reshaped, axis=1)
        maxs = np.max(reshaped, axis=1)

        y_top = np.clip((mid - maxs * mid * 0.9).astype(np.int32), 0, h - 1)
        y_bot = np.clip((mid - mins * mid * 0.9).astype(np.int32), 0, h - 1)
        yt = np.minimum(y_top, y_bot)
        yb = np.maximum(y_top, y_bot)

        # Vectorized fill
        wr, wg, wb = self._wave_rgb
        rows = np.arange(h, dtype=np.int32).reshape(h, 1)
        mask = (rows >= yt[np.newaxis, :cols]) & (rows <= yb[np.newaxis, :cols])
        buf[:, :cols, 0] = np.where(mask, wb, buf[:, :cols, 0])
        buf[:, :cols, 1] = np.where(mask, wg, buf[:, :cols, 1])
        buf[:, :cols, 2] = np.where(mask, wr, buf[:, :cols, 2])

        # Center line (dotted)
        bb2, bg2, br2 = self._border_rgb[2], self._border_rgb[1], self._border_rgb[0]
        buf[mid, ::2, 0] = bb2
        buf[mid, ::2, 1] = bg2
        buf[mid, ::2, 2] = br2

        img = QImage(buf.data, w, h, w * 4, QImage.Format.Format_ARGB32)
        return img.copy()

    def resizeEvent(self, e):
        """Invalide le cache waveform quand le widget est redimensionne."""
        self._cache = None
        super().resizeEvent(e)
