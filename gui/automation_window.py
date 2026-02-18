"""Automation Window — FL Studio-style parameter automation over time.

Floating resizable window accessible via View menu.
Multi-parameter support: each param can be automated (curve) or constant (fixed).
"""
from utils.logger import get_logger
_log = get_logger("auto_win")

import numpy as np
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QWidget, QFrame, QLineEdit,
    QCheckBox, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QTimer
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QCursor, QPainterPath,
    QMouseEvent, QPaintEvent
)
from utils.config import COLORS, get_colors, checkbox_css
from utils.translator import t
from core.automation import AUTOMATABLE_PARAMS, interpolate_curve


# ═══════════════════════════════════════
# Mini Waveform (display + selection)
# ═══════════════════════════════════════

class _MiniWaveform(QWidget):
    """Compact waveform display. Selection only enabled when unlocked."""
    selection_changed = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(70)
        self.setMaximumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.audio_data: np.ndarray | None = None
        self.sample_rate = 44100
        self.sel_start: int | None = None
        self.sel_end: int | None = None
        self._dragging = False
        self._playhead = 0
        self._selection_locked = False  # selection always enabled
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def set_audio(self, audio, sr):
        self.audio_data = audio
        self.sample_rate = sr
        self.sel_start = None
        self.sel_end = None
        self.update()

    def set_playhead(self, pos):
        self._playhead = pos
        self.update()

    def unlock_selection(self):
        self._selection_locked = False
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def lock_selection(self):
        self._selection_locked = True
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _pos_to_sample(self, x):
        if self.audio_data is None or self.width() == 0:
            return 0
        frac = max(0, min(1, x / self.width()))
        return int(frac * len(self.audio_data))

    def mousePressEvent(self, e: QMouseEvent):
        if self._selection_locked:
            return
        if e.button() == Qt.MouseButton.LeftButton and self.audio_data is not None:
            self._dragging = True
            s = self._pos_to_sample(e.position().x())
            self.sel_start = s
            self.sel_end = s
            self.update()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._selection_locked:
            return
        if self._dragging and self.audio_data is not None:
            self.sel_end = self._pos_to_sample(e.position().x())
            self.update()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._selection_locked:
            return
        if self._dragging:
            self._dragging = False
            if self.sel_start is not None and self.sel_end is not None:
                s, en = min(self.sel_start, self.sel_end), max(self.sel_start, self.sel_end)
                if en - s > 100:
                    self.sel_start, self.sel_end = s, en
                    self.selection_changed.emit(s, en)
                else:
                    self.sel_start = self.sel_end = None
            self.update()

    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        C = get_colors()
        p.fillRect(0, 0, w, h, QColor(C['bg_dark']))

        if self.audio_data is None or len(self.audio_data) == 0:
            p.setPen(QColor(C['text_dim']))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No audio loaded")
            p.end(); return

        data = self.audio_data
        if data.ndim > 1:
            data = data.mean(axis=1)
        n = len(data)
        step = max(1, n // w)
        p.setPen(QPen(QColor(C['accent']), 1))
        mid = h / 2
        for x in range(w):
            idx = int(x * n / w)
            end_idx = min(idx + step, n)
            chunk = data[idx:end_idx]
            if len(chunk) == 0:
                continue
            lo_val = float(np.min(chunk))
            hi_val = float(np.max(chunk))
            y1 = int(mid - hi_val * mid * 0.9)
            y2 = int(mid - lo_val * mid * 0.9)
            p.drawLine(x, y1, x, y2)

        if self.sel_start is not None and self.sel_end is not None:
            s = min(self.sel_start, self.sel_end)
            en = max(self.sel_start, self.sel_end)
            x1 = int(s / n * w)
            x2 = int(en / n * w)
            sel_c = QColor("#e94560"); sel_c.setAlpha(50)
            p.fillRect(x1, 0, x2 - x1, h, sel_c)
            p.setPen(QPen(QColor("#e94560"), 1))
            p.drawLine(x1, 0, x1, h)
            p.drawLine(x2, 0, x2, h)

        if self._playhead > 0 and n > 0:
            px = int(self._playhead / n * w)
            p.setPen(QPen(QColor(C.get('playhead', '#00d2ff')), 2))
            p.drawLine(px, 0, px, h)

        # Unlock indicator
        if not self._selection_locked:
            p.setPen(QColor("#e94560"))
            fnt = p.font(); fnt.setPixelSize(10); fnt.setBold(True); p.setFont(fnt)
            p.drawText(QRectF(0, 0, w, 14), Qt.AlignmentFlag.AlignCenter, "-- Selection mode --")

        p.end()


# ═══════════════════════════════════════
# Automation Preview Waveform (processed)
# ═══════════════════════════════════════

class _AutoPreviewWaveform(QWidget):
    """Shows the selected region waveform: dim original + bright processed overlay.
    Updated in real-time when automation curves or parameters change."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMaximumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._original: np.ndarray | None = None
        self._processed: np.ndarray | None = None
        self._sr = 44100
        # Peak caches
        self._orig_hi: np.ndarray | None = None
        self._orig_lo: np.ndarray | None = None
        self._proc_hi: np.ndarray | None = None
        self._proc_lo: np.ndarray | None = None
        self._orig_w = 0
        self._proc_w = 0

    def set_original(self, audio, sr):
        """Set the base (unprocessed) region audio."""
        self._original = audio
        self._sr = sr
        self._orig_hi = self._orig_lo = None
        self._orig_w = 0
        if self._processed is None:
            self._processed = audio
            self._proc_hi = self._proc_lo = None
            self._proc_w = 0
        self.update()

    def set_processed(self, audio):
        """Set the automation-processed region audio."""
        self._processed = audio
        self._proc_hi = self._proc_lo = None
        self._proc_w = 0
        self.update()

    def clear(self):
        self._original = self._processed = None
        self._orig_hi = self._orig_lo = None
        self._proc_hi = self._proc_lo = None
        self._orig_w = self._proc_w = 0
        self.update()

    def _compute_peaks(self, data, w):
        """Downsample audio to w peak values (hi/lo)."""
        if data is None or len(data) == 0 or w < 2:
            return None, None
        mono = data.mean(axis=1) if data.ndim > 1 else data
        n = len(mono)
        idx = np.linspace(0, n, w + 1, dtype=np.int64)
        hi = np.empty(w, dtype=np.float32)
        lo = np.empty(w, dtype=np.float32)
        for x in range(w):
            s = mono[idx[x]:idx[x + 1]]
            if len(s) == 0:
                hi[x] = lo[x] = 0.0
            else:
                hi[x] = s.max(); lo[x] = s.min()
        return hi, lo

    def _ensure_peaks(self, w):
        if self._orig_w != w or self._orig_hi is None:
            self._orig_hi, self._orig_lo = self._compute_peaks(self._original, w)
            self._orig_w = w
        if self._proc_w != w or self._proc_hi is None:
            self._proc_hi, self._proc_lo = self._compute_peaks(self._processed, w)
            self._proc_w = w

    def paintEvent(self, e: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        C = get_colors()
        p.fillRect(0, 0, w, h, QColor(C['bg_dark']))

        if self._original is None or len(self._original) == 0:
            p.setPen(QColor(C['text_dim']))
            fnt = p.font(); fnt.setPixelSize(9); p.setFont(fnt)
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                       "Preview : select a region & configure an effect")
            p.end(); return

        self._ensure_peaks(w)
        mid = h / 2
        scale = mid * 0.9

        # Draw original (dim ghost)
        if self._orig_hi is not None:
            dim_c = QColor(C['text_dim']); dim_c.setAlpha(40)
            p.setPen(QPen(dim_c, 1))
            for x in range(min(w, len(self._orig_hi))):
                y1 = int(mid - self._orig_hi[x] * scale)
                y2 = int(mid - self._orig_lo[x] * scale)
                p.drawLine(x, y1, x, y2)

        # Draw processed (bright)
        if self._proc_hi is not None:
            p.setPen(QPen(QColor("#9d6dff"), 1))
            for x in range(min(w, len(self._proc_hi))):
                y1 = int(mid - self._proc_hi[x] * scale)
                y2 = int(mid - self._proc_lo[x] * scale)
                if y2 <= y1:
                    y2 = y1 + 1
                p.drawLine(x, y1, x, y2)

        # Label
        p.setPen(QColor(C['text_dim']))
        fnt = p.font(); fnt.setPixelSize(9); p.setFont(fnt)
        dur_s = len(self._original) / max(1, self._sr)
        p.drawText(4, h - 3, f"Preview : {dur_s:.2f}s")

        # Border
        p.setPen(QPen(QColor(C['border']), 1))
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()


# ═══════════════════════════════════════
# Curve Editor Widget
# ═══════════════════════════════════════

class _CurveEditor(QWidget):
    """Editable automation curve with draggable control points and Bézier bends.

    Two editing modes (like FL Studio / FadeDialog):
      MODE_POINTS — add / move / delete control points (straight lines)
      MODE_BEND   — drag a segment to curve it (quadratic Bézier)
    """
    curve_changed = pyqtSignal()
    MODE_POINTS = 0
    MODE_BEND = 1
    MODE_DRAW = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._points: list[list[float]] = [[0.0, 0.0], [1.0, 1.0]]
        self._bends: list[float] = [0.0]
        self._mode = self.MODE_POINTS
        self._drag = None          # ('pt', idx) or ('bend', seg_idx, t0, interp_y0)
        self._hover_idx: int | None = None
        self._hover_mode: int | None = None   # which mode tab is hovered

        # Draw Mode state
        self._draw_path: list[tuple[float, float]] = []
        self._is_drawing = False

        # Undo/Redo
        self._undo_stack = []
        self._redo_stack = []

        self._param_name = "Parameter"
        self._target_label = ""
        self._default_label = ""
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def keyPressEvent(self, e):
        # Undo / Redo
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if e.key() == Qt.Key.Key_Z:
                if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.redo()
                else:
                    self.undo()
                return
            elif e.key() == Qt.Key.Key_Y:
                self.redo()
                return
        super().keyPressEvent(e)

    def _push_undo(self):
        # State = (deep copy of points, copy of bends)
        pts = [list(p) for p in self._points]
        bends = list(self._bends)
        self._undo_stack.append((pts, bends))
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self):
        if not self._undo_stack:
            return
        # Save current for redo
        curr_pts = [list(p) for p in self._points]
        curr_bends = list(self._bends)
        self._redo_stack.append((curr_pts, curr_bends))
        
        # Pop undo
        pts, bends = self._undo_stack.pop()
        self._points = pts
        self._bends = bends
        self.curve_changed.emit()
        self.update()

    def redo(self):
        if not self._redo_stack:
            return
        # Save current for undo
        curr_pts = [list(p) for p in self._points]
        curr_bends = list(self._bends)
        self._undo_stack.append((curr_pts, curr_bends))

        # Pop redo
        pts, bends = self._redo_stack.pop()
        self._points = pts
        self._bends = bends
        self.curve_changed.emit()
        self.update()

    # ── public API ──

    def set_mode(self, m):
        self._mode = m
        self._drag = None
        self._hover_idx = None
        self.setCursor(Qt.CursorShape.CrossCursor if m == self.MODE_POINTS
                       else Qt.CursorShape.SizeVerCursor)
        self.update()

    def set_labels(self, param_name, default_val, target_val):
        self._param_name = param_name
        self._default_label = str(round(default_val, 2))
        self._target_label = str(round(target_val, 2))
        self.update()

    def get_points(self):
        return sorted([tuple(p) for p in self._points], key=lambda p: p[0])

    def get_bends(self):
        return list(self._bends)

    def set_points(self, pts):
        self._points = [list(p) for p in pts] if pts else [[0.0, 0.0], [1.0, 1.0]]
        self._sync_bends()
        self.update()

    def set_bends(self, bends):
        self._bends = list(bends) if bends else [0.0] * max(0, len(self._points) - 1)
        self._sync_bends()
        self.update()

    def reset_linear(self):
        self._points = [[0.0, 0.0], [1.0, 1.0]]
        self._bends = [0.0]
        self.curve_changed.emit()
        self.update()

    # ── geometry helpers ──

    def _sync_bends(self):
        need = max(0, len(self._points) - 1)
        while len(self._bends) < need:
            self._bends.append(0.0)
        while len(self._bends) > need:
            self._bends.pop()

    def _pad(self):
        return 40, 54, 16, 24   # left, top (room for mode bar + spacing), right, bottom

    def _to_pixel(self, nx, ny):
        l, t, r, b = self._pad()
        dw = self.width() - l - r
        dh = self.height() - t - b
        return l + nx * dw, t + (1 - ny) * dh

    def _from_pixel(self, px, py):
        l, t, r, b = self._pad()
        dw = self.width() - l - r
        dh = self.height() - t - b
        if dw == 0 or dh == 0:
            return 0, 0
        # Clamp py within the graph area
        py = max(t, min(self.height() - b, py))
        nx = max(0, min(1, (px - l) / dw))
        ny = max(0, min(1, 1 - (py - t) / dh))
        return nx, ny

    def _sorted_pos(self, idx):
        order = sorted(range(len(self._points)), key=lambda i: self._points[i][0])
        return order.index(idx)

    def _is_endpoint(self, idx):
        pos = self._sorted_pos(idx)
        return pos == 0 or pos == len(self._points) - 1

    def _near_pt(self, px, py, rad=12):
        best, best_d = None, rad * rad
        for i, (x, y) in enumerate(self._points):
            sx, sy = self._to_pixel(x, y)
            d = (px - sx) ** 2 + (py - sy) ** 2
            if d < best_d:
                best_d = d
                best = i
        return best

    def _near_seg(self, px, py, rad=16):
        from core.automation import _bezier_y
        pts = sorted(self._points, key=lambda p: p[0])
        for si in range(len(pts) - 1):
            x0, y0 = pts[si]
            x1, y1 = pts[si + 1]
            sx0, _ = self._to_pixel(x0, y0)
            sx1, _ = self._to_pixel(x1, y1)
            if not (sx0 - 8 <= px <= sx1 + 8) or (sx1 - sx0) < 3:
                continue
            t = max(0.05, min(0.95, (px - sx0) / (sx1 - sx0)))
            bd = self._bends[si] if si < len(self._bends) else 0.0
            by = _bezier_y(y0, y1, bd, t)
            _, sy_curve = self._to_pixel(0, by)
            if abs(py - sy_curve) < rad:
                return si, t
        return None

    # ── mouse — POINTS mode ──

    def _press_pts(self, px, py, btn):
        _, t, _, b = self._pad()
        if btn == Qt.MouseButton.LeftButton:
            pi = self._near_pt(px, py)
            if pi is not None:
                self._push_undo()
                self._drag = ('pt', pi)
                return
            # Only add points if clicking inside the graph area
            if py < t or py > self.height() - b:
                return
            
            self._push_undo()
            nx, ny = self._from_pixel(px, py)
            # Find which segment we're inserting into
            spts = sorted(self._points, key=lambda p: p[0])
            seg = 0
            for i in range(len(spts) - 1):
                if spts[i][0] <= nx <= spts[i + 1][0]:
                    seg = i
                    break
            self._points.append([nx, ny])
            self._points.sort(key=lambda p: p[0])
            # Split the bend of that segment into two zero-bends
            self._bends[seg:seg + 1] = [0.0, 0.0]
            self._sync_bends()
            ni = next(i for i, p in enumerate(self._points) if p == [nx, ny])
            self._drag = ('pt', ni)
            self.curve_changed.emit()
            self.update()
        elif btn == Qt.MouseButton.RightButton:
            self._try_delete(px, py)

    def _move_pts(self, px, py):
        if self._drag and self._drag[0] == 'pt':
            idx = self._drag[1]
            nx, ny = self._from_pixel(px, py)
            self._points[idx] = [nx, ny]
            self.curve_changed.emit()
            self.update()
        else:
            old = self._hover_idx
            self._hover_idx = self._near_pt(px, py)
            if self._hover_idx != old:
                self.update()

    def _release_pts(self):
        if self._drag and self._drag[0] == 'pt':
            self._points.sort(key=lambda p: p[0])
            self._sync_bends()
            self._drag = None
            self.curve_changed.emit()
            self.update()

    def _try_delete(self, px, py):
        if len(self._points) <= 2:
            return
        pi = self._near_pt(px, py, 14)
        if pi is None or self._is_endpoint(pi):
            return
        
        self._push_undo()
        pos = self._sorted_pos(pi)
        if 0 < pos <= len(self._bends):
            self._bends[pos - 1:pos + 1] = [0.0]
        self._points.pop(pi)
        self._sync_bends()
        self.curve_changed.emit()
        self.update()

    # ── mouse — BEND mode ──

    def _press_bend(self, px, py, btn):
        if btn != Qt.MouseButton.LeftButton:
            return
        seg = self._near_seg(px, py, 20)
        if seg is None:
            return
        
        self._push_undo()
        si, t0 = seg
        pts = sorted(self._points, key=lambda p: p[0])
        y0, y1 = pts[si][1], pts[si + 1][1]
        interp_y0 = y0 + t0 * (y1 - y0)
        self._drag = ('bend', si, t0, interp_y0)

    # ... (move_bend, release_bend unchanged) ...

    def _move_bend(self, px, py):
        if not (self._drag and self._drag[0] == 'bend'):
            return
        si, t0, interp_y0 = self._drag[1], self._drag[2], self._drag[3]
        _, ny = self._from_pixel(px, py)
        denom = 2.0 * t0 * (1.0 - t0)
        if abs(denom) < 0.01:
            return
        new_bend = (ny - interp_y0) / denom
        # Clamp: control point = (y0+y1)/2 + bend must stay within
        # [min(y0,y1), max(y0,y1)] AND [0, 1]
        pts = sorted(self._points, key=lambda p: p[0])
        y0, y1 = pts[si][1], pts[si + 1][1]
        mid = (y0 + y1) / 2.0
        lo = max(0.0, min(y0, y1))
        hi = min(1.0, max(y0, y1))
        new_bend = max(lo - mid, min(hi - mid, new_bend))
        self._bends[si] = new_bend
        self.curve_changed.emit()
        self.update()

    def _release_bend(self):
        if self._drag and self._drag[0] == 'bend':
            self._drag = None
            self.curve_changed.emit()
            self.update()

    # ── DRAW Mode ──

    def _press_draw(self, px, py, btn):
        if btn == Qt.MouseButton.LeftButton:
            self._push_undo()
            self._is_drawing = True
            self._draw_path = []
            nx, ny = self._from_pixel(px, py)
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))
            self._draw_path.append((nx, ny))
            self.update()

    def _move_draw(self, px, py):
        if self._is_drawing:
            nx, ny = self._from_pixel(px, py)
            nx = max(0.0, min(1.0, nx))
            ny = max(0.0, min(1.0, ny))
            if not self._draw_path or abs(nx - self._draw_path[-1][0]) > 0.005:
                 self._draw_path.append((nx, ny))
            self.update()

    def _release_draw(self):
        if self._is_drawing:
            self._is_drawing = False
            if len(self._draw_path) < 2: return

            self._draw_path.sort(key=lambda p: p[0])
            # Finer simplification for detailed curves
            simplified = self._rdp_simplify(self._draw_path, epsilon=0.004)
            
            # Ensure start/end at 0 and 1
            if simplified[0][0] > 0.0: simplified.insert(0, (0.0, simplified[0][1]))
            else: simplified[0] = (0.0, simplified[0][1])
            if simplified[-1][0] < 1.0: simplified.append((1.0, simplified[-1][1]))
            else: simplified[-1] = (1.0, simplified[-1][1])

            self._points = [[float(x), float(y)] for x, y in simplified]
            self._bends = [0.0] * (len(self._points) - 1)
            self._draw_path = []
            self.curve_changed.emit()
            self.update()

    def _rdp_simplify(self, points, epsilon):
        if len(points) < 3: return points
        dmax = 0.0
        index = 0
        end = len(points) - 1
        p1 = points[0]; p2 = points[end]
        dx = p2[0] - p1[0]; dy = p2[1] - p1[1]
        align_dist = (dx*dx + dy*dy)**0.5
        
        if align_dist == 0: return [points[0]]

        for i in range(1, end):
             p = points[i]
             d = abs(dy*p[0] - dx*p[1] + p2[0]*p1[1] - p2[1]*p1[0]) / align_dist
             if d > dmax:
                 index = i; dmax = d

        if dmax > epsilon:
            rec1 = self._rdp_simplify(points[:index+1], epsilon)
            rec2 = self._rdp_simplify(points[index:], epsilon)
            return rec1[:-1] + rec2
        else:
            return [points[0], points[end]]

    # ── mouse dispatch ──

    def mousePressEvent(self, e: QMouseEvent):
        px, py = e.position().x(), e.position().y()
        # Check mode bar (y=8, h=22)
        if 8 <= py <= 30:
            l, _, r, _ = self._pad()
            dw = self.width() - l - r
            bar_w = min(180, dw)
            bar_x = l + (dw - bar_w) // 2
            btn_w = (bar_w - 12) // 3
            if bar_x <= px <= bar_x + btn_w:
                self.set_mode(self.MODE_POINTS); return
            elif bar_x + btn_w + 6 <= px <= bar_x + 2 * btn_w + 6:
                self.set_mode(self.MODE_BEND); return
            elif bar_x + 2 * btn_w + 12 <= px <= bar_x + 3 * btn_w + 12:
                self.set_mode(self.MODE_DRAW); return
        
        # Graph bounds check
        l, t, r, b = self._pad()
        if not (l <= px <= self.width() - r and t <= py <= self.height() - b): return

        if self._mode == self.MODE_POINTS:
            self._press_pts(px, py, e.button())
        elif self._mode == self.MODE_BEND:
            self._press_bend(px, py, e.button())
        elif self._mode == self.MODE_DRAW:
            self._press_draw(px, py, e.button())

    def mouseMoveEvent(self, e: QMouseEvent):
        px, py = e.position().x(), e.position().y()
        # Track hover over mode toolbar
        old_hm = self._hover_mode
        if 8 <= py <= 30:
            l, _, r, _ = self._pad()
            dw = self.width() - l - r
            bar_w = min(180, dw)
            bar_x = l + (dw - bar_w) // 2
            btn_w = (bar_w - 12) // 3
            in_pts = bar_x <= px <= bar_x + btn_w
            in_bend = bar_x + btn_w + 6 <= px <= bar_x + 2 * btn_w + 6
            in_draw = bar_x + 2 * btn_w + 12 <= px <= bar_x + 3 * btn_w + 12
            self._hover_mode = 0 if in_pts else (1 if in_bend else (2 if in_draw else None))
            self.setCursor(Qt.CursorShape.PointingHandCursor if self._hover_mode is not None else Qt.CursorShape.ArrowCursor)
        else:
            self._hover_mode = None
            if self._mode == self.MODE_POINTS: self.setCursor(Qt.CursorShape.CrossCursor)
            elif self._mode == self.MODE_DRAW: self.setCursor(Qt.CursorShape.ArrowCursor) # Pen cursor ideally
            else: self.setCursor(Qt.CursorShape.SizeAllCursor)
        if old_hm != self._hover_mode: self.update()

        if self._mode == self.MODE_POINTS: self._move_pts(px, py)
        elif self._mode == self.MODE_BEND: self._move_bend(px, py)
        elif self._mode == self.MODE_DRAW: self._move_draw(px, py)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._mode == self.MODE_POINTS: self._release_pts()
        elif self._mode == self.MODE_BEND: self._release_bend()
        elif self._mode == self.MODE_DRAW: self._release_draw()

    # ── painting ──

    def paintEvent(self, e: QPaintEvent):
        from core.automation import _bezier_y
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        C = get_colors()
        l, t, r, b = self._pad()
        dw, dh = w - l - r, h - t - b
        p.fillRect(0, 0, w, h, QColor(C['bg_dark']))

        # ── Mode toolbar ──
        # ── Mode toolbar ──
        bar_h = 22
        bar_y = 8
        bar_w = min(180, dw)
        bar_x = l + (dw - bar_w) // 2
        gap = 6
        # 3 buttons: Points, Bend, Draw
        btn_w = (bar_w - 2 * gap) // 3
        
        modes = ["Points", "Bend", "Draw"]
        for idx, label in enumerate(modes):
            bx = bar_x + idx * (btn_w + gap)
            brect = QRectF(bx, bar_y, btn_w, bar_h)
            
            is_active = (idx == self._mode)
            is_hover = (idx == self._hover_mode)
            
            # Background
            if is_active:
                bg = QColor("#7c3aed"); bg.setAlpha(180)
            elif is_hover:
                bg = QColor(C['accent_hover']); bg.setAlpha(140)
            else:
                bg = QColor(C['button_bg'])
                
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(bg))
            p.drawRoundedRect(brect, 4, 4)
            
            # Text
            tc = QColor("white") if (is_active or is_hover) else QColor(C['text_dim'])
            p.setPen(tc)
            fnt = p.font(); fnt.setBold(is_active)
            fnt.setPixelSize(10 if is_active else 9)
            p.setFont(fnt)
            p.drawText(brect, Qt.AlignmentFlag.AlignCenter, label)

        # ── Draw Path (raw) ──
        if self._is_drawing and len(self._draw_path) > 1:
            p.setPen(QPen(QColor(C['accent']), 2, Qt.PenStyle.DotLine))
            path = QPainterPath()
            sx, sy = self._to_pixel(*self._draw_path[0])
            path.moveTo(sx, sy)
            for nx, ny in self._draw_path[1:]:
                sx, sy = self._to_pixel(nx, ny)
                path.lineTo(sx, sy)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # ── Grid ──
        p.setPen(QPen(QColor(C['border']), 1, Qt.PenStyle.DotLine))
        for frac in [0.25, 0.5, 0.75]:
            y = int(t + dh * (1 - frac))
            p.drawLine(l, y, w - r, y)
            x = int(l + dw * frac)
            p.drawLine(x, t, x, h - b)

        p.setPen(QPen(QColor(C['text_dim']), 1))
        p.drawLine(l, t, l, h - b)
        p.drawLine(l, h - b, w - r, h - b)

        # ── Axis labels ──
        fnt = p.font()
        fnt.setPixelSize(9)
        fnt.setBold(False)
        p.setFont(fnt)
        p.setPen(QColor(C['text_dim']))
        p.drawText(2, t + 4, self._target_label or "max")
        p.drawText(2, h - b + 3, self._default_label or "min")
        fnt.setPixelSize(10)
        p.setFont(fnt)
        p.setPen(QColor(C['accent']))
        p.drawText(QRectF(l, bar_y + bar_h + 1, dw, 12),
                   Qt.AlignmentFlag.AlignCenter, self._param_name)

        # ── Curve rendering ──
        sorted_pts = sorted(self._points, key=lambda pt: pt[0])
        if len(sorted_pts) >= 2:
            # Fill path (area under curve)
            fill_path = QPainterPath()
            sx, sy = self._to_pixel(sorted_pts[0][0], sorted_pts[0][1])
            fill_path.moveTo(sx, t + dh)
            fill_path.lineTo(sx, sy)
            for si in range(len(sorted_pts) - 1):
                x0, y0 = sorted_pts[si]
                x1, y1 = sorted_pts[si + 1]
                sx1, sy1 = self._to_pixel(x1, y1)
                bd = self._bends[si] if si < len(self._bends) else 0.0
                if abs(bd) < 0.005:
                    fill_path.lineTo(sx1, sy1)
                else:
                    cx = (x0 + x1) / 2
                    cy = (y0 + y1) / 2 + bd
                    cpx, cpy = self._to_pixel(cx, cy)
                    fill_path.quadTo(cpx, cpy, sx1, sy1)
            ex, ey = self._to_pixel(sorted_pts[-1][0], sorted_pts[-1][1])
            fill_path.lineTo(ex, t + dh)
            fill_path.closeSubpath()
            fc = QColor("#7c3aed")
            fc.setAlpha(30)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(fc))
            p.drawPath(fill_path)

            # Curve line
            curve_path = QPainterPath()
            sx, sy = self._to_pixel(sorted_pts[0][0], sorted_pts[0][1])
            curve_path.moveTo(sx, sy)
            for si in range(len(sorted_pts) - 1):
                x0, y0 = sorted_pts[si]
                x1, y1 = sorted_pts[si + 1]
                sx1, sy1 = self._to_pixel(x1, y1)
                bd = self._bends[si] if si < len(self._bends) else 0.0
                if abs(bd) < 0.005:
                    curve_path.lineTo(sx1, sy1)
                else:
                    cx = (x0 + x1) / 2
                    cy = (y0 + y1) / 2 + bd
                    cpx, cpy = self._to_pixel(cx, cy)
                    curve_path.quadTo(cpx, cpy, sx1, sy1)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#7c3aed"), 2.5))
            p.drawPath(curve_path)

        # ── Control points ──
        for i, (x, y) in enumerate(sorted_pts):
            px2, py2 = self._to_pixel(x, y)
            is_hover = (i == self._hover_idx) or (
                self._drag and self._drag[0] == 'pt'
                and self._drag[1] < len(self._points)
                and i == self._sorted_pos(self._drag[1]))
            is_endpoint = (i == 0 or i == len(sorted_pts) - 1)
            if is_endpoint:
                sz = 5 if is_hover else 4
                color = QColor("#b8a9e8") if is_hover else QColor("#8b7dc8")
                p.setPen(QPen(QColor("#d4d0e8"), 1.2))
            else:
                sz = 8 if is_hover else 6
                color = QColor("#e94560") if is_hover else QColor("#7c3aed")
                p.setPen(QPen(QColor("white"), 1.5))
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(px2, py2), sz, sz)

        # ── Mode hint ──
        fnt = p.font()
        fnt.setPixelSize(8)
        fnt.setBold(False)
        p.setFont(fnt)
        hc = QColor(C['text_dim'])
        hc.setAlpha(140)
        p.setPen(hc)
        if self._mode == self.MODE_POINTS:
            hint = "Clic = ajouter  |  Glisser = déplacer  |  Clic droit = supprimer"
        else:
            hint = "Glissez un segment pour ajuster la courbure"
        p.drawText(QRectF(l, h - 12, dw, 12), Qt.AlignmentFlag.AlignCenter, hint)

        p.end()


# ═══════════════════════════════════════
# Automation List Item (no emojis)
# ═══════════════════════════════════════

class _AutoItem(QWidget):
    edit_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    toggle_clicked = pyqtSignal(str)

    def __init__(self, uid, index, name, effect_name, param_summary,
                 enabled=True, color="#7c3aed", parent=None):
        super().__init__(parent)
        self._uid = uid
        self._hovered = False
        self.setFixedHeight(52)
        C = get_colors()

        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 4, 8, 4)
        lo.setSpacing(6)

        btn_t = QPushButton("ON" if enabled else "OFF")
        btn_t.setFixedSize(32, 20)
        btn_t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_t.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        tc = color if enabled else C['text_dim']
        btn_t.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {tc}; border: 1px solid {tc};"
            f" border-radius: 3px; font-size: 9px; font-weight: bold; }}"
            f"QPushButton:hover {{ color: {COLORS['accent']}; border-color: {COLORS['accent']}; }}")
        btn_t.clicked.connect(lambda: self.toggle_clicked.emit(self._uid))
        lo.addWidget(btn_t)

        col = QVBoxLayout(); col.setSpacing(0)
        ns = f"color: {C['text']};" if enabled else f"color: {C['text_dim']}; text-decoration: line-through;"
        lbl_name = QLabel(f"{index + 1}. {name}")
        lbl_name.setStyleSheet(f"{ns} font-size: 11px; font-weight: bold;")
        col.addWidget(lbl_name)
        meta = QLabel(f"{effect_name} | {param_summary}")
        meta.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px;")
        col.addWidget(meta)
        lo.addLayout(col, stretch=1)

        btn_e = QPushButton("Edit")
        btn_e.setFixedSize(40, 22)
        btn_e.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_e.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_e.setStyleSheet(
            f"QPushButton {{ background: {C['button_bg']}; color: {C['text']};"
            f" border: none; border-radius: 3px; font-size: 10px; }}"
            f"QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}")
        btn_e.clicked.connect(lambda: self.edit_clicked.emit(self._uid))
        lo.addWidget(btn_e)

        btn_d = QPushButton("Del")
        btn_d.setFixedSize(34, 22)
        btn_d.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn_d.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_d.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C['text_dim']};"
            f" border: 1px solid {C['text_dim']}; border-radius: 3px; font-size: 10px; }}"
            f"QPushButton:hover {{ color: #e94560; border-color: #e94560; }}")
        btn_d.clicked.connect(lambda: self.delete_clicked.emit(self._uid))
        lo.addWidget(btn_d)

    def enterEvent(self, e):
        self._hovered = True; self.update()
    def leaveEvent(self, e):
        self._hovered = False; self.update()
    def paintEvent(self, e):
        if self._hovered:
            p = QPainter(self)
            c = QColor("#7c3aed"); c.setAlpha(15)
            p.fillRect(self.rect(), c); p.end()


# ═══════════════════════════════════════
# Per-parameter config row
# ═══════════════════════════════════════

class _ParamRow(QWidget):
    """One row for a parameter: checkbox + mode (Automated/Constant) + value fields."""
    changed = pyqtSignal()

    def __init__(self, pkey, pname, pmin, pmax, pdef, pstep, parent=None):
        super().__init__(parent)
        self.pkey = pkey
        self.pname = pname
        self.pmin, self.pmax, self.pdef, self.pstep = pmin, pmax, pdef, pstep
        C = get_colors()
        css_input = (f"QLineEdit {{ background: {C['bg_dark']}; color: {C['text']};"
                     f" border: 1px solid {C['border']}; border-radius: 3px;"
                     f" padding: 2px 5px; font-size: 10px; }}")
        css_combo = (f"QComboBox {{ background: {C['bg_dark']}; color: {C['text']};"
                     f" border: 1px solid {C['border']}; border-radius: 3px;"
                     f" padding: 2px 5px; font-size: 10px; }}"
                     f" QComboBox QAbstractItemView {{ background: {C['bg_dark']};"
                     f" color: {C['text']}; selection-background-color: {C['accent']}; }}")
        lbl_css = f"color: {C['text_dim']}; font-size: 10px;"

        lo = QHBoxLayout(self)
        lo.setContentsMargins(0, 2, 0, 2)
        lo.setSpacing(4)

        self._chk = QCheckBox(pname)
        self._chk.setStyleSheet(checkbox_css(C))
        self._chk.setChecked(False)
        self._chk.toggled.connect(self._on_toggle)
        lo.addWidget(self._chk)

        self._combo_mode = QComboBox()
        self._combo_mode.addItems(["Automated", "Constant"])
        self._combo_mode.setStyleSheet(css_combo)
        self._combo_mode.setFixedWidth(85)
        self._combo_mode.currentIndexChanged.connect(self._on_mode)
        lo.addWidget(self._combo_mode)

        # Default value
        lbl_def = QLabel("From:")
        lbl_def.setStyleSheet(lbl_css); lbl_def.setFixedWidth(32)
        lo.addWidget(lbl_def)
        self._inp_default = QLineEdit(str(pdef))
        self._inp_default.setStyleSheet(css_input)
        self._inp_default.setFixedWidth(55)
        self._inp_default.textChanged.connect(lambda: self.changed.emit())
        lo.addWidget(self._inp_default)

        # Target value (for automated)
        lbl_tgt = QLabel("To:")
        lbl_tgt.setStyleSheet(lbl_css); lbl_tgt.setFixedWidth(20)
        lo.addWidget(lbl_tgt)
        self._lbl_to = lbl_tgt
        # Smart default: if default == max, target should go to min instead
        target_default = pmin if pdef == pmax else pmax
        self._inp_target = QLineEdit(str(target_default))
        self._inp_target.setStyleSheet(css_input)
        self._inp_target.setFixedWidth(55)
        self._inp_target.textChanged.connect(lambda: self.changed.emit())
        lo.addWidget(self._inp_target)

        lbl_range = QLabel(f"[{pmin} .. {pmax}]")
        lbl_range.setStyleSheet(f"color: {C['text_dim']}; font-size: 9px;")
        lo.addWidget(lbl_range)
        lo.addStretch()

        self._on_toggle(False)

    def _on_toggle(self, on):
        for w in [self._combo_mode, self._inp_default, self._inp_target, self._lbl_to]:
            w.setEnabled(on)
        self._on_mode()
        self.changed.emit()

    def _on_mode(self, _=None):
        is_auto = self._combo_mode.currentText() == "Automated"
        self._inp_target.setVisible(is_auto and self._chk.isChecked())
        self._lbl_to.setVisible(is_auto and self._chk.isChecked())
        self.changed.emit()

    def is_enabled(self):
        return self._chk.isChecked()

    def get_mode(self):
        return "automated" if self._combo_mode.currentText() == "Automated" else "constant"

    def get_default(self):
        try: return float(self._inp_default.text())
        except ValueError: return self.pdef

    def get_target(self):
        try: return float(self._inp_target.text())
        except ValueError: return self.pmax

    def get_value(self):
        """For constant mode, returns the 'from' field as the constant value."""
        return self.get_default()

    def load_data(self, data):
        """Load from saved auto_params entry."""
        self._chk.setChecked(True)
        mode = data.get("mode", "automated")
        idx = 0 if mode == "automated" else 1
        self._combo_mode.setCurrentIndex(idx)
        if mode == "constant":
            self._inp_default.setText(str(data.get("value", self.pdef)))
        else:
            self._inp_default.setText(str(data.get("default_val", self.pdef)))
            self._inp_target.setText(str(data.get("target_val", self.pmax)))


# ═══════════════════════════════════════
# Automation Editor (multi-param)
# ═══════════════════════════════════════

class _AutoEditor(QWidget):
    saved = pyqtSignal(dict)
    cancelled = pyqtSignal()
    play_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    preview_base_requested = pyqtSignal(int, int)
    redefine_region_requested = pyqtSignal()

    def __init__(self, plugins, parent=None):
        super().__init__(parent)
        self._plugins = plugins
        self._editing_uid = None
        self._param_rows: list[_ParamRow] = []
        self._curve_editors: dict[str, _CurveEditor] = {}
        C = get_colors()
        css_combo = (f"QComboBox {{ background: {C['bg_dark']}; color: {C['text']};"
                     f" border: 1px solid {C['border']}; border-radius: 4px;"
                     f" padding: 4px 8px; font-size: 11px; }}"
                     f" QComboBox QAbstractItemView {{ background: {C['bg_dark']};"
                     f" color: {C['text']}; selection-background-color: {C['accent']}; }}")
        css_input = (f"QLineEdit {{ background: {C['bg_dark']}; color: {C['text']};"
                     f" border: 1px solid {C['border']}; border-radius: 4px;"
                     f" padding: 4px 8px; font-size: 11px; }}")
        lbl_css = f"color: {C['text_dim']}; font-size: 11px;"

        lo = QVBoxLayout(self)
        lo.setSpacing(6)
        lo.setContentsMargins(0, 0, 0, 0)

        # Name
        r_name = QHBoxLayout()
        r_name.addWidget(self._mk_lbl("Name", lbl_css))
        self._inp_name = QLineEdit()
        self._inp_name.setPlaceholderText("Automation name...")
        self._inp_name.setStyleSheet(css_input)
        r_name.addWidget(self._inp_name)
        lo.addLayout(r_name)

        # Effect combo
        r_eff = QHBoxLayout()
        r_eff.addWidget(self._mk_lbl("Effect", lbl_css))
        self._combo_effect = QComboBox()
        self._combo_effect.setStyleSheet(css_combo)
        self._combo_effect.currentIndexChanged.connect(self._on_effect_changed)
        r_eff.addWidget(self._combo_effect, stretch=1)
        lo.addLayout(r_eff)

        # Parameters container
        lbl_params = QLabel("Parameters (check to include):")
        lbl_params.setStyleSheet(f"color: {C['accent']}; font-size: 11px; font-weight: bold;")
        lo.addWidget(lbl_params)

        self._params_container = QVBoxLayout()
        self._params_container.setSpacing(2)
        lo.addLayout(self._params_container)

        # Curve editors scroll
        self._curves_scroll = QScrollArea()
        self._curves_scroll.setWidgetResizable(True)
        self._curves_scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollBar:vertical {{ background: {C['bg_dark']}; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 3px; }}")
        self._curves_widget = QWidget()
        self._curves_layout = QVBoxLayout(self._curves_widget)
        self._curves_layout.setSpacing(4)
        self._curves_layout.setContentsMargins(0, 0, 0, 0)
        self._curves_scroll.setWidget(self._curves_widget)
        lo.addWidget(self._curves_scroll, stretch=1)

        # Preview waveform (processed in real-time)
        self._preview_wave = _AutoPreviewWaveform()
        lo.addWidget(self._preview_wave)

        # Debounce timer for preview updates
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._update_preview)

        # Audio data for preview
        self._region_audio: np.ndarray | None = None
        self._region_sr = 44100

        # Redefine region + transport
        region_row = QHBoxLayout()
        region_row.setSpacing(6)

        btn_redefine = self._mk_btn("Redefine region", C['button_bg'])
        btn_redefine.setFixedWidth(120)
        btn_redefine.clicked.connect(self.redefine_region_requested.emit)
        region_row.addWidget(btn_redefine)

        btn_preview_base = self._mk_btn("Preview base", C['button_bg'])
        btn_preview_base.setFixedWidth(100)
        btn_preview_base.clicked.connect(lambda: self.preview_base_requested.emit(0, 0))
        region_row.addWidget(btn_preview_base)

        region_row.addStretch()
        lo.addLayout(region_row)

        # Transport + actions
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._btn_play = self._mk_btn("Play", C['accent'])
        self._btn_play.setFixedWidth(60)
        self._btn_play.clicked.connect(self.play_requested.emit)
        btn_row.addWidget(self._btn_play)

        self._btn_stop = self._mk_btn("Stop", C['button_bg'])
        self._btn_stop.setFixedWidth(50)
        self._btn_stop.clicked.connect(self.stop_requested.emit)
        btn_row.addWidget(self._btn_stop)

        btn_reset = self._mk_btn("Reset curves", C['button_bg'])
        btn_reset.setFixedWidth(90)
        btn_reset.clicked.connect(self._reset_all_curves)
        btn_row.addWidget(btn_reset)

        btn_row.addStretch()

        btn_cancel = self._mk_btn("Cancel", C['button_bg'])
        btn_cancel.setFixedWidth(70)
        btn_cancel.clicked.connect(self.cancelled.emit)
        btn_row.addWidget(btn_cancel)

        btn_save = self._mk_btn("Save", C['accent'])
        btn_save.setFixedWidth(70)
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        lo.addLayout(btn_row)
        self._populate_effects()

    def _mk_lbl(self, text, css):
        lbl = QLabel(text); lbl.setStyleSheet(css); lbl.setFixedWidth(55)
        return lbl

    def _mk_btn(self, text, bg):
        b = QPushButton(text); b.setFixedHeight(28)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: white; border: none;"
            f" border-radius: 4px; font-weight: bold; font-size: 10px; padding: 0 8px; }}"
            f" QPushButton:hover {{ background: {COLORS['accent_hover']}; }}")
        return b

    def _populate_effects(self):
        self._combo_effect.blockSignals(True)
        self._combo_effect.clear()
        for eid in sorted(AUTOMATABLE_PARAMS.keys()):
            plugin = self._plugins.get(eid)
            name = plugin.get_name() if plugin else eid.replace("_", " ").title()
            self._combo_effect.addItem(name, eid)
        self._combo_effect.blockSignals(False)
        if self._combo_effect.count() > 0:
            self._on_effect_changed(0)

    def _on_effect_changed(self, _idx):
        eid = self._combo_effect.currentData()
        params = AUTOMATABLE_PARAMS.get(eid, [])

        # Clear old param rows
        for row in self._param_rows:
            row.setParent(None); row.deleteLater()
        self._param_rows.clear()
        self._curve_editors.clear()

        for pkey, pname, pmin, pmax, pdef, pstep in params:
            row = _ParamRow(pkey, pname, pmin, pmax, pdef, pstep)
            row.changed.connect(self._rebuild_curves)
            self._params_container.addWidget(row)
            self._param_rows.append(row)

        self._rebuild_curves()

    def _rebuild_curves(self):
        """Show a _CurveEditor for each automated param, hide for constant."""
        # Clear curves layout
        while self._curves_layout.count():
            item = self._curves_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        new_editors = {}
        for row in self._param_rows:
            if not row.is_enabled():
                continue
            if row.get_mode() != "automated":
                continue
            # Reuse existing editor if same key
            ce = self._curve_editors.get(row.pkey)
            if ce is None:
                ce = _CurveEditor()
            ce.set_labels(row.pname, row.get_default(), row.get_target())
            # Connect curve changes to preview updates
            try: ce.curve_changed.disconnect(self._schedule_preview)
            except Exception: pass
            ce.curve_changed.connect(self._schedule_preview)
            new_editors[row.pkey] = ce
            self._curves_layout.addWidget(ce)

        self._curve_editors = new_editors
        if not new_editors:
            C = get_colors()
            hint = QLabel("Enable a parameter in Automated mode to see its curve.")
            hint.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; padding: 12px;")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setWordWrap(True)
            self._curves_layout.addWidget(hint)
        self._curves_layout.addStretch()
        self._schedule_preview()

    def _reset_all_curves(self):
        for ce in self._curve_editors.values():
            ce.reset_linear()

    def load_automation(self, op):
        self._editing_uid = op.get("uid")
        self._inp_name.setText(op.get("name", ""))

        eid = op.get("effect_id", "")
        idx = self._combo_effect.findData(eid)
        if idx >= 0:
            self._combo_effect.setCurrentIndex(idx)

        # Load multi-param config
        auto_params = op.get("auto_params", [])
        # Also support legacy single-param format
        if not auto_params and op.get("auto_param"):
            auto_params = [{"key": op["auto_param"], "mode": "automated",
                            "default_val": op.get("auto_default", 0),
                            "target_val": op.get("auto_target", 1),
                            "curve_points": op.get("curve_points", [(0,0),(1,1)])}]

        for ap in auto_params:
            key = ap.get("key")
            for row in self._param_rows:
                if row.pkey == key:
                    row.load_data(ap)
                    break

        self._rebuild_curves()

        # Load curve points and bends
        for ap in auto_params:
            key = ap.get("key")
            if ap.get("mode") == "automated" and key in self._curve_editors:
                pts = ap.get("curve_points", [(0,0),(1,1)])
                bends = ap.get("curve_bends")
                self._curve_editors[key].set_points(pts)
                if bends:
                    self._curve_editors[key].set_bends(bends)

    def new_automation(self):
        self._editing_uid = None
        self._inp_name.setText("")
        if self._combo_effect.count() > 0:
            self._combo_effect.setCurrentIndex(0)
        for row in self._param_rows:
            row._chk.setChecked(False)
        self._rebuild_curves()

    def _save(self):
        name = self._inp_name.text().strip()
        if not name:
            name = f"Auto : {self._combo_effect.currentText()}"

        eid = self._combo_effect.currentData()
        auto_params = []
        for row in self._param_rows:
            if not row.is_enabled():
                continue
            mode = row.get_mode()
            entry = {"key": row.pkey, "mode": mode,
                     "step": row.pstep, "pmin": row.pmin, "pmax": row.pmax}
            if mode == "constant":
                entry["value"] = row.get_value()
            else:
                entry["default_val"] = row.get_default()
                entry["target_val"] = row.get_target()
                ce = self._curve_editors.get(row.pkey)
                entry["curve_points"] = ce.get_points() if ce else [(0,0),(1,1)]
                entry["curve_bends"] = ce.get_bends() if ce else [0.0]
            auto_params.append(entry)

        if not auto_params:
            C = get_colors()
            QMessageBox.warning(self, "Automation", "Please enable at least one parameter.")
            return

        op = {
            "uid": self._editing_uid,
            "effect_id": eid,
            "name": name,
            "auto_params": auto_params,
            "type": "automation",
        }
        self.saved.emit(op)

    def get_current_auto_config(self):
        eid = self._combo_effect.currentData()
        auto_params = []
        for row in self._param_rows:
            if not row.is_enabled():
                continue
            mode = row.get_mode()
            entry = {"key": row.pkey, "mode": mode,
                     "step": row.pstep, "pmin": row.pmin, "pmax": row.pmax}
            if mode == "constant":
                entry["value"] = row.get_value()
            else:
                entry["default_val"] = row.get_default()
                entry["target_val"] = row.get_target()
                ce = self._curve_editors.get(row.pkey)
                entry["curve_points"] = ce.get_points() if ce else [(0,0),(1,1)]
                entry["curve_bends"] = ce.get_bends() if ce else [0.0]
            auto_params.append(entry)
        return {"effect_id": eid, "auto_params": auto_params}

    def set_region_audio(self, audio, sr):
        """Set the audio region for real-time preview."""
        self._region_audio = audio
        self._region_sr = sr
        if audio is not None and len(audio) > 0:
            self._preview_wave.set_original(audio, sr)
            self._schedule_preview()
        else:
            self._preview_wave.clear()

    def _schedule_preview(self):
        """Debounce preview update."""
        self._preview_timer.start()

    def _update_preview(self):
        """Recompute the processed audio and update the preview waveform."""
        if self._region_audio is None or len(self._region_audio) == 0:
            return
        config = self.get_current_auto_config()
        auto_params = config.get("auto_params", [])
        if not auto_params:
            # No params configured: show original as-is
            self._preview_wave.set_processed(self._region_audio)
            return
        eid = config.get("effect_id")
        plugin = self._plugins.get(eid)
        if not plugin:
            self._preview_wave.set_processed(self._region_audio)
            return
        try:
            from core.automation import apply_automation_multi
            region = self._region_audio.copy()
            processed = apply_automation_multi(
                region, 0, len(region),
                plugin.process_fn, auto_params, self._region_sr)
            self._preview_wave.set_processed(processed)
        except Exception as ex:
            _log.debug("Preview waveform error: %s", ex)
            self._preview_wave.set_processed(self._region_audio)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space:
            self.play_requested.emit()
        else:
            super().keyPressEvent(e)


# ═══════════════════════════════════════
# Main Automation Window
# ═══════════════════════════════════════

class AutomationWindow(QDialog):
    automation_added = pyqtSignal(dict)
    automation_edited = pyqtSignal(dict)
    automation_deleted = pyqtSignal(str)
    automation_toggled = pyqtSignal(str)
    preview_requested = pyqtSignal(dict, int, int)
    preview_base_requested = pyqtSignal(int, int)
    stop_requested = pyqtSignal()
    window_closed = pyqtSignal()  # emitted when user closes with X

    def __init__(self, plugins, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Automations")
        self.setMinimumSize(560, 480)
        self.resize(660, 580)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        C = get_colors()
        self.setStyleSheet(f"QDialog {{ background: {C['bg_medium']}; }}")

        self._plugins = plugins
        self._automations: list[dict] = []
        self._redefine_mode = False  # True when redefining selection
        self._playback_ref = None    # reference to main playback engine
        self._is_previewing = False
        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._tick_preview)

        lo = QVBoxLayout(self)
        lo.setSpacing(6)
        lo.setContentsMargins(10, 8, 10, 8)

        # Mini waveform
        self._wave = _MiniWaveform()
        self._wave.selection_changed.connect(self._on_selection)
        lo.addWidget(self._wave)

        # Redefine region bar (hidden by default)
        self._redefine_bar = QWidget()
        rbar_lo = QHBoxLayout(self._redefine_bar)
        rbar_lo.setContentsMargins(0, 4, 0, 4)
        rbar_lo.setSpacing(6)
        rbar_lbl = QLabel("Drag on the waveform to select a new region")
        rbar_lbl.setStyleSheet(f"color: #e94560; font-size: 10px; font-weight: bold;")
        rbar_lo.addWidget(rbar_lbl)
        rbar_lo.addStretch()

        btn_base_preview = QPushButton("Preview base sound")
        btn_base_preview.setFixedHeight(24)
        btn_base_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_base_preview.setStyleSheet(
            f"QPushButton {{ background: {C['button_bg']}; color: {C['text']};"
            f" border: none; border-radius: 4px; font-size: 10px; padding: 0 8px; }}"
            f" QPushButton:hover {{ background: {COLORS['accent']}; color: white; }}")
        btn_base_preview.clicked.connect(self._preview_base_region)
        rbar_lo.addWidget(btn_base_preview)

        btn_accept = QPushButton("Accept")
        btn_accept.setFixedHeight(24)
        btn_accept.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_accept.setStyleSheet(
            f"QPushButton {{ background: {C['accent']}; color: white;"
            f" border: none; border-radius: 4px; font-size: 10px; font-weight: bold; padding: 0 12px; }}"
            f" QPushButton:hover {{ background: {COLORS['accent_hover']}; }}")
        btn_accept.clicked.connect(self._accept_redefine)
        rbar_lo.addWidget(btn_accept)

        btn_cancel_r = QPushButton("Cancel")
        btn_cancel_r.setFixedHeight(24)
        btn_cancel_r.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_cancel_r.setStyleSheet(
            f"QPushButton {{ background: {C['button_bg']}; color: {C['text']};"
            f" border: none; border-radius: 4px; font-size: 10px; padding: 0 12px; }}"
            f" QPushButton:hover {{ background: #e94560; color: white; }}")
        btn_cancel_r.clicked.connect(self._cancel_redefine)
        rbar_lo.addWidget(btn_cancel_r)

        self._redefine_bar.hide()
        lo.addWidget(self._redefine_bar)

        # Stacked views
        self._stack_list = QWidget()
        self._stack_editor = QWidget()

        # ── List view ──
        list_lo = QVBoxLayout(self._stack_list)
        list_lo.setContentsMargins(0, 0, 0, 0)
        list_lo.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel("Automations")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C['accent']};")
        hdr.addWidget(title)
        hdr.addStretch()
        self._lbl_count = QLabel("0")
        self._lbl_count.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
        hdr.addWidget(self._lbl_count)
        list_lo.addLayout(hdr)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {C['bg_panel']}; border: 1px solid {C['border']}; border-radius: 4px; }}"
            f"QScrollBar:vertical {{ background: {C['bg_panel']}; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {C['border']}; border-radius: 3px; }}")
        list_lo.addWidget(self._scroll, stretch=1)

        # Add button row (list view)
        btn_add_row = QHBoxLayout()
        btn_add_row.addStretch()
        self._lbl_hint = QLabel("Drag on the waveform above to select a region")
        self._lbl_hint.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
        btn_add_row.addWidget(self._lbl_hint)

        self._btn_add = QPushButton("Add Automation")
        self._btn_add.setFixedHeight(32)
        self._btn_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_add.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_add.setEnabled(False)
        self._btn_add.setStyleSheet(
            f"QPushButton {{ background: {C['accent']}; color: white; border: none;"
            f" border-radius: 6px; font-weight: bold; font-size: 11px; padding: 0 16px; }}"
            f" QPushButton:hover {{ background: {C['accent_hover']}; }}"
            f" QPushButton:disabled {{ background: {C['button_bg']}; color: {C['text_dim']}; }}")
        self._btn_add.clicked.connect(self._start_new)
        btn_add_row.addWidget(self._btn_add)

        self._btn_close = QPushButton("Close")
        self._btn_close.setFixedHeight(32)
        self._btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_close.setStyleSheet(
            f"QPushButton {{ background: {C['button_bg']}; color: {C['text']}; border: none;"
            f" border-radius: 6px; font-size: 11px; padding: 0 16px; }}"
            f" QPushButton:hover {{ background: #e94560; color: white; }}")
        self._btn_close.clicked.connect(self.close)
        btn_add_row.addWidget(self._btn_close)
        list_lo.addLayout(btn_add_row)

        # ── Editor view ──
        editor_lo = QVBoxLayout(self._stack_editor)
        editor_lo.setContentsMargins(0, 0, 0, 0)
        self._editor = _AutoEditor(plugins)
        self._editor.saved.connect(self._on_editor_save)
        self._editor.cancelled.connect(self._show_list)
        self._editor.play_requested.connect(self._on_preview_play)
        self._editor.stop_requested.connect(self.stop_requested.emit)
        self._editor.preview_base_requested.connect(self._on_preview_base)
        self._editor.redefine_region_requested.connect(self._start_redefine)
        editor_lo.addWidget(self._editor)

        lo.addWidget(self._stack_list)
        lo.addWidget(self._stack_editor)

        self._sel_start: int | None = None
        self._sel_end: int | None = None
        self._prev_sel_start: int | None = None
        self._prev_sel_end: int | None = None

        self._show_list()
        # Install event filter on the application to catch space key
        # from any child widget within this window
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Intercept space key from any child widget to prevent button activation."""
        from PyQt6.QtCore import QEvent
        if (event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Space
                and self.isVisible()
                and self._is_descendant(obj)):
            if self._is_previewing:
                self._stop_preview()
            elif self._stack_editor.isVisible():
                self._on_preview_play()
            return True  # consume the event
        return super().eventFilter(obj, event)

    def _is_descendant(self, widget):
        """Check if widget is a child of this window."""
        w = widget
        while w is not None:
            if w is self:
                return True
            w = w.parent() if hasattr(w, 'parent') else None
        return False

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space:
            if self._is_previewing:
                self._stop_preview()
            elif self._stack_editor.isVisible():
                self._on_preview_play()
            return
        super().keyPressEvent(e)

    def set_playback_engine(self, pb):
        """Store reference to main playback engine for tracking."""
        self._playback_ref = pb

    def start_preview_tracking(self):
        """Start polling playback position to update waveform playhead."""
        self._is_previewing = True
        self._play_timer.start(30)

    def _tick_preview(self):
        """Poll playback position and update waveform cursor."""
        pb = self._playback_ref
        if pb and pb.is_playing:
            self._wave.set_playhead(pb.position)
        else:
            self._stop_preview()

    def _stop_preview(self):
        """Stop playback and reset playhead."""
        self._play_timer.stop()
        self._is_previewing = False
        if self._playback_ref and self._playback_ref.is_playing:
            self._playback_ref.stop()
        self._wave.set_playhead(0)
        self._wave.update()

    def set_audio(self, audio, sr):
        self._wave.set_audio(audio, sr)

    def set_playhead(self, pos):
        self._wave.set_playhead(pos)

    def set_automations(self, ops):
        self._automations = [op for op in ops if op.get("type") == "automation"]
        self._rebuild_list()

    def _on_selection(self, s, e):
        self._sel_start = s
        self._sel_end = e
        self._btn_add.setEnabled(True)
        sr = self._wave.sample_rate or 44100
        dur_ms = int((e - s) / sr * 1000)
        self._lbl_hint.setText(f"Selected : {dur_ms} ms")

    def _show_list(self):
        self._stack_editor.hide()
        self._stack_list.show()
        self._redefine_bar.hide()
        self._redefine_mode = False

    def _show_editor(self):
        self._stack_list.hide()
        self._stack_editor.show()

    def _start_new(self):
        s, e = self._wave.sel_start, self._wave.sel_end
        if s is None or e is None: return
        _log.info("Action: New automation started for region %d-%d", s, e)
        self._sel_start = s
        self._sel_end = e
        self._editor.new_automation()
        self._push_region_audio()
        self._show_editor()

    def _start_edit(self, uid):
        op = next((a for a in self._automations if a.get("uid") == uid), None)
        if op is None: return
        self._sel_start = op.get("start", 0)
        self._sel_end = op.get("end", 0)
        self._wave.sel_start = self._sel_start
        self._wave.sel_end = self._sel_end
        self._wave.update()
        self._editor.load_automation(op)
        self._push_region_audio()
        self._show_editor()

    def _push_region_audio(self):
        """Extract the selected region and send it to the editor for preview."""
        audio = self._wave.audio_data
        sr = self._wave.sample_rate or 44100
        if audio is not None and self._sel_start is not None and self._sel_end is not None:
            s = max(0, min(self._sel_start, len(audio)))
            e = max(s, min(self._sel_end, len(audio)))
            if e - s > 0:
                self._editor.set_region_audio(audio[s:e].copy(), sr)
                return
        self._editor.set_region_audio(None, sr)

    def _start_redefine(self):
        """Enter redefine-region mode from editor."""
        self._prev_sel_start = self._sel_start
        self._prev_sel_end = self._sel_end
        self._redefine_bar.show()
        self._redefine_mode = True

    def _accept_redefine(self):
        if self._wave.sel_start is not None and self._wave.sel_end is not None:
            s = min(self._wave.sel_start, self._wave.sel_end)
            e = max(self._wave.sel_start, self._wave.sel_end)
            if e - s > 100:
                self._sel_start = s
                self._sel_end = e
                self._btn_add.setEnabled(True)
        self._redefine_bar.hide()
        self._redefine_mode = False
        self._push_region_audio()

    def _cancel_redefine(self):
        self._sel_start = self._prev_sel_start
        self._sel_end = self._prev_sel_end
        if self._sel_start is not None and self._sel_end is not None:
            self._wave.sel_start = self._sel_start
            self._wave.sel_end = self._sel_end
        self._wave.update()
        self._redefine_bar.hide()
        self._redefine_mode = False

    def _preview_base_region(self):
        if self._wave.sel_start is not None and self._wave.sel_end is not None:
            s = min(self._wave.sel_start, self._wave.sel_end)
            e = max(self._wave.sel_start, self._wave.sel_end)
            self.preview_base_requested.emit(s, e)

    def _on_editor_save(self, op):
        if self._sel_start is None or self._sel_end is None:
            QMessageBox.warning(self, "Automation",
                                "No region selected. Please select a region on the waveform first.")
            return
        op["start"] = self._sel_start
        op["end"] = self._sel_end
        if op.get("uid") is None:
            _log.info("Action: Automation created: %s", op.get('name', 'unnamed'))
            self.automation_added.emit(op)
        else:
            _log.info("Action: Automation edited: %s [%s]", op.get('name', 'unnamed'), op['uid'])
            self.automation_edited.emit(op)
        self._show_list()

    def _on_preview_play(self):
        if self._sel_start is None or self._sel_end is None:
            return
        config = self._editor.get_current_auto_config()
        self.preview_requested.emit(config, self._sel_start, self._sel_end)
        self.start_preview_tracking()

    def _on_preview_base(self, _s, _e):
        if self._sel_start is not None and self._sel_end is not None:
            self.preview_base_requested.emit(self._sel_start, self._sel_end)
            self.start_preview_tracking()

    def _rebuild_list(self):
        C = get_colors()
        w = QWidget()
        w.setStyleSheet(f"background: {C['bg_panel']};")
        lo = QVBoxLayout(w)
        lo.setContentsMargins(4, 4, 4, 4)
        lo.setSpacing(0)

        for i, op in enumerate(self._automations):
            if i > 0:
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {C['border']};")
                lo.addWidget(sep)

            eid = op.get("effect_id", "")
            plugin = self._plugins.get(eid)
            eff_name = plugin.get_name() if plugin else eid

            # Build param summary
            auto_params = op.get("auto_params", [])
            if not auto_params and op.get("auto_param"):
                auto_params = [{"key": op["auto_param"], "mode": "automated"}]
            parts = []
            for ap in auto_params:
                k = ap.get("key", "?")
                if ap.get("mode") == "constant":
                    parts.append(f"{k}={ap.get('value','?')}")
                else:
                    parts.append(f"{k} (curve)")
            param_summary = ", ".join(parts) if parts else "no params"

            item = _AutoItem(
                uid=op.get("uid", ""), index=i,
                name=op.get("name", "Automation"),
                effect_name=eff_name, param_summary=param_summary,
                enabled=op.get("enabled", True),
                color=op.get("color", "#7c3aed"))
            item.edit_clicked.connect(self._start_edit)
            item.delete_clicked.connect(lambda uid: self.automation_deleted.emit(uid))
            item.toggle_clicked.connect(lambda uid: self.automation_toggled.emit(uid))
            lo.addWidget(item)

        if not self._automations:
            msg = (
                "No automations yet.\n\n"
                "1. Select a region on the waveform above.\n"
                "2. Click 'Add Automation'.\n"
                "3. Choose an effect and parameter.\n"
                "4. Enable 'Automated' mode to draw curves."
            )
            lbl = QLabel(msg)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; padding: 24px;")
            lbl.setWordWrap(True); lo.addWidget(lbl)

        lo.addStretch()
        self._scroll.setWidget(w)
        self._lbl_count.setText(str(len(self._automations)))

    def closeEvent(self, e):
        """When closed with X, emit signal so main window can update View menu."""
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().removeEventFilter(self)
        self.window_closed.emit()
        e.accept()
