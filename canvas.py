
from __future__ import annotations
import copy
import math
from typing import List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import Qt, QPointF, QRectF, QRect, QSize, pyqtSignal
from PyQt5.QtGui import (QPainter, QPen, QColor, QPainterPath, QBrush,
                          QTabletEvent, QMouseEvent, QFont, QImage, QPixmap, QKeySequence)
from PyQt5.QtWidgets import QWidget, QInputDialog, QApplication

from shapes import Shape, BezierStroke, Line, Arrow, Ellipse, Polygon, TextLabel
from curvefit import fit_curve, adaptive_max_error
from shape_recognition import classify_stroke
from smoothing import clean_stroke, symmetrize_closed_curve
from presets import build_preset
from erasing import erase_shape, _sample_bezier_stroke
from render import paint_shape, paint_shapes, draw_arrow_head, shapes_bbox
from beautify import machine_finish, taubin_fair
import shape_transform

TOOLS = ["pen", "line", "arrow", "ellipse", "polygon", "bezier", "text", "eraser", "select"]

# input conditioning
MIN_POINT_DISTANCE = 1.2      # px: drop tablet points closer than this
PRESSURE_SMOOTHING = 0.35     # EMA factor (0 = frozen, 1 = raw)


MIN_ZOOM, MAX_ZOOM = 0.1, 8.0


class DrawingCanvas(QWidget):
    status_message = pyqtSignal(str)
    shapes_changed = pyqtSignal()
    selection_changed = pyqtSignal(object)    # selected Shape or None
    view_changed = pyqtSignal(float)          # current zoom factor

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TabletTracking, True)
        self.setMouseTracking(True)
        self.setMinimumSize(1100, 780)
        self.setStyleSheet("background-color: white; border-radius: 6px;")
        self.setFocusPolicy(Qt.StrongFocus)

        # navigation: pan/zoom view transform (Quiver-style fast navigation).
        # World coordinates (= shape/export coordinates) are unaffected --
        # only the on-screen mapping changes.
        self.view_scale = 1.0
        self.view_offset = QPointF(0.0, 0.0)
        self._panning = False
        self._pan_last: Optional[QPointF] = None
        self._space_held = False

        self.shapes: List[Shape] = []
        self._undo_stack: List[list] = []
        self._redo_stack: List[list] = []

        self.tool = "pen"
        self.color = "#000000"
        self.stroke_width = 2.5
        self.snap_to_grid = False
        self.grid_size = 20

        # fill / auto-finish (recognition + smoothing)
        self.fill_enabled = False
        self.fill_color = "#cfe8ff"
        self.auto_vectorize = True  # on by default: clean drawing from the start
        self.smooth_finish = True   # "traced by pro design software" simplification
        self.pressure_enabled = True  # pen pressure -> variable stroke width

        # eraser
        self.eraser_radius = 16.0
        self._erasing_active = False

        # freehand pen state: (x, y, pressure) triples
        self._raw_points: List[Tuple[float, float, float]] = []
        self._drawing_stroke = False
        self._pressure_ema: float = 1.0

        # 2-point shape state (line / arrow / ellipse)
        self._drag_start: Optional[QPointF] = None
        self._drag_current: Optional[QPointF] = None

        # polygon state (successive clicks)
        self._poly_points: List[Tuple[float, float]] = []

        # pen/bezier tool state (Illustrator-style)
        self._pen_anchors: List[dict] = []
        self._pen_dragging_handle = False
        self._pen_anchor_start: Optional[QPointF] = None

        # selection
        self._selected_index: Optional[int] = None
        self._move_last: Optional[QPointF] = None

        # shape clipboard (Copy / Paste / Duplicate)
        self._clipboard: Optional[Shape] = None

        # backing-store cache of committed shapes (HiDPI-aware)
        self._cache: Optional[QPixmap] = None

        # imported photo shown as a tracing layer (never exported)
        self.bg_image: Optional[QImage] = None
        self.bg_opacity: float = 0.35
        self.show_bg: bool = True

    # ---------------------------------------------------------- public API
    def set_tool(self, tool: str):
        self._finish_pending()
        self.tool = tool
        self.status_message.emit(f"Tool: {tool}")
        self.update()

    def set_color(self, color_hex: str):
        self.color = color_hex

    def set_width(self, w: float):
        self.stroke_width = w

    def set_fill_enabled(self, enabled: bool):
        self.fill_enabled = enabled

    def set_fill_color(self, color_hex: str):
        self.fill_color = color_hex

    def set_eraser_radius(self, radius: float):
        self.eraser_radius = radius

    def set_snap_to_grid(self, enabled: bool):
        self.snap_to_grid = enabled
        self._invalidate_cache()
        self.update()

    def set_pressure_enabled(self, enabled: bool):
        self.pressure_enabled = enabled
        self.status_message.emit(
            "Pen pressure enabled: stroke width follows stylus pressure."
            if enabled else "Pen pressure disabled: constant stroke width."
        )

    def set_auto_vectorize(self, enabled: bool):
        self.auto_vectorize = enabled
        self.status_message.emit(
            "Auto-finish enabled: strokes are cleaned up / turned into perfect shapes."
            if enabled else "Auto-finish disabled (raw stroke, simply smoothed)."
        )

    def set_smooth_finish(self, enabled: bool):
        self.smooth_finish = enabled
        self.status_message.emit(
            "Smooth finish enabled: curves are re-traced with size-adaptive tolerance "
            "for a clean, professional-software look."
            if enabled else "Smooth finish disabled (fixed-tolerance curve fitting)."
        )

    # ----------------------------------------------------- backing store
    def _invalidate_cache(self):
        self._cache = None

    def _ensure_cache(self):
        if self._cache is not None:
            return
        dpr = self.devicePixelRatioF()
        pm = QPixmap(max(int(self.width() * dpr), 1), max(int(self.height() * dpr), 1))
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor("white"))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        if self.bg_image is not None and self.show_bg:
            self._draw_background(p)
        p.save()
        p.translate(self.view_offset)
        p.scale(self.view_scale, self.view_scale)
        if self.snap_to_grid:
            self._draw_grid(p)
        for i, shape in enumerate(self.shapes):
            if i == self._selected_index:
                continue  # selected shape is drawn live in the overlay
            paint_shape(p, shape)
        p.restore()
        p.end()
        self._cache = pm

    def resizeEvent(self, event):
        self._invalidate_cache()
        super().resizeEvent(event)

    # ----------------------------------------------------- navigation (pan/zoom)
    def _to_world(self, pos) -> QPointF:
        """Widget pixel position -> world/shape coordinates (inverse of the
        current pan/zoom view transform)."""
        p = QPointF(pos)
        return QPointF((p.x() - self.view_offset.x()) / self.view_scale,
                       (p.y() - self.view_offset.y()) / self.view_scale)

    def _world_rect_to_widget(self, x0, y0, x1, y1) -> QRect:
        s, o = self.view_scale, self.view_offset
        return QRect(int(x0 * s + o.x()), int(y0 * s + o.y()),
                    int((x1 - x0) * s) + 1, int((y1 - y0) * s) + 1)

    def _set_view(self, scale: float, offset: QPointF):
        self.view_scale = max(MIN_ZOOM, min(MAX_ZOOM, scale))
        self.view_offset = offset
        self._invalidate_cache()
        self.view_changed.emit(self.view_scale)
        self.update()

    def zoom_at(self, widget_pos, factor: float):
        """Zoom in/out keeping the point under `widget_pos` fixed on screen
        (mouse-wheel zoom, like Quiver's Zoom in/out)."""
        new_scale = max(MIN_ZOOM, min(MAX_ZOOM, self.view_scale * factor))
        if abs(new_scale - self.view_scale) < 1e-9:
            return
        wx, wy = widget_pos.x(), widget_pos.y()
        # keep (wx,wy) mapping to the same world point before and after
        world = self._to_world(widget_pos)
        new_offset = QPointF(wx - world.x() * new_scale, wy - world.y() * new_scale)
        self._set_view(new_scale, new_offset)

    def zoom_in(self):
        self.zoom_at(QPointF(self.width() / 2, self.height() / 2), 1.25)

    def zoom_out(self):
        self.zoom_at(QPointF(self.width() / 2, self.height() / 2), 1 / 1.25)

    def reset_zoom(self):
        self._set_view(1.0, QPointF(0.0, 0.0))
        self.status_message.emit("Zoom reset to 100%.")

    def fit_to_drawing(self):
        """Frame the whole drawing in the visible canvas (Quiver's 'Centre
        view'), with a comfortable margin."""
        bbox = shapes_bbox(self.shapes)
        if bbox is None:
            self.reset_zoom()
            return
        x0, y0, x1, y1 = bbox
        w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
        margin = 60
        avail_w, avail_h = max(self.width() - 2 * margin, 10), max(self.height() - 2 * margin, 10)
        scale = max(MIN_ZOOM, min(MAX_ZOOM, min(avail_w / w, avail_h / h)))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        offset = QPointF(self.width() / 2 - cx * scale, self.height() / 2 - cy * scale)
        self._set_view(scale, offset)
        self.status_message.emit("View fitted to the drawing.")

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.zoom_at(event.position() if hasattr(event, "position") else QPointF(event.pos()), factor)

    def _begin_pan(self, pos):
        self._panning = True
        self._pan_last = QPointF(pos)
        self.setCursor(Qt.ClosedHandCursor)

    def _continue_pan(self, pos):
        p = QPointF(pos)
        dx, dy = p.x() - self._pan_last.x(), p.y() - self._pan_last.y()
        self._pan_last = p
        self._set_view(self.view_scale, QPointF(self.view_offset.x() + dx, self.view_offset.y() + dy))

    def _end_pan(self):
        self._panning = False
        self._pan_last = None
        self.setCursor(Qt.OpenHandCursor if self._space_held else Qt.ArrowCursor)

    def _shapes_mutated(self, emit: bool = True):
        """Single funnel for 'the committed drawing changed'."""
        self._invalidate_cache()
        if emit:
            self.shapes_changed.emit()

    # -------------------------------------------------------- image export
    def render_to_image(self, scale: float = 3.0) -> Optional[QImage]:
        """
        Clean, publication-quality raster snapshot: white background, no grid,
        no selection highlight, no in-progress overlay -- just the finished
        shapes, rendered at `scale`x resolution (antialiased).
        """
        bbox = shapes_bbox(self.shapes)
        if bbox is None:
            return None
        x0, y0, x1, y1 = bbox
        margin = 40
        w = (x1 - x0) + 2 * margin
        h = (y1 - y0) + 2 * margin
        img = QImage(max(int(w * scale), 1), max(int(h * scale), 1), QImage.Format_ARGB32)
        img.fill(QColor("white"))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(scale, scale)
        painter.translate(margin - x0, margin - y0)
        paint_shapes(painter, self.shapes)
        painter.end()
        return img

    def export_image(self, path: str, scale: float = 3.0) -> bool:
        img = self.render_to_image(scale)
        if img is None:
            return False
        return img.save(path)

    def export_svg(self, path: str) -> bool:
        """True vector export (SVG): infinite resolution, editable in
        Inkscape/Illustrator, exact same rendering code as the canvas."""
        from PyQt5.QtSvg import QSvgGenerator
        bbox = shapes_bbox(self.shapes)
        if bbox is None:
            return False
        x0, y0, x1, y1 = bbox
        margin = 40
        w = (x1 - x0) + 2 * margin
        h = (y1 - y0) + 2 * margin
        gen = QSvgGenerator()
        gen.setFileName(path)
        gen.setSize(QSize(int(w), int(h)))
        gen.setViewBox(QRectF(0, 0, w, h))
        gen.setTitle("VanovaTikZSketch figure")
        gen.setDescription("Vector figure exported from VanovaTikZSketch")
        gen.setResolution(96)
        painter = QPainter(gen)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(margin - x0, margin - y0)
        paint_shapes(painter, self.shapes)
        painter.end()
        return True

    # ------------------------------------------------- imported photo layer
    def _bg_rect(self) -> Optional[QRectF]:
        """Where the tracing photo is displayed: fit-to-canvas, centered."""
        if self.bg_image is None:
            return None
        iw, ih = self.bg_image.width(), self.bg_image.height()
        if iw <= 0 or ih <= 0:
            return None
        margin = 30
        aw, ah = max(self.width() - 2 * margin, 10), max(self.height() - 2 * margin, 10)
        s = min(aw / iw, ah / ih)
        w, h = iw * s, ih * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _draw_background(self, painter: QPainter):
        rect = self._bg_rect()
        if rect is None:
            return
        painter.save()
        painter.setOpacity(self.bg_opacity)
        painter.drawImage(rect, self.bg_image)
        painter.restore()

    def set_background_image(self, qimage: QImage):
        self.bg_image = qimage
        self.show_bg = True
        self._invalidate_cache()
        self.update()
        self.status_message.emit(
            "Photo placed as a tracing layer (faded, never exported). "
            "Draw over it; hide/remove it from the toolbar.")

    def clear_background(self):
        self.bg_image = None
        self._invalidate_cache()
        self.update()
        self.status_message.emit("Tracing photo removed.")

    def set_show_background(self, show: bool):
        self.show_bg = show
        self._invalidate_cache()
        self.update()

    def set_background_opacity(self, opacity: float):
        self.bg_opacity = float(min(max(opacity, 0.05), 1.0))
        self._invalidate_cache()
        self.update()

    def insert_traced_shapes(self, new_shapes: List[Shape]) -> int:
        """Drop shapes extracted from an imported photo onto the canvas as
        normal, fully editable objects (one undo step)."""
        if not new_shapes:
            return 0
        self._push_undo()
        self.shapes.extend(new_shapes)
        self._shapes_mutated()
        self.update()
        return len(new_shapes)

    def insert_preset(self, name: str):
        """Insert a preset (template) centered on the visible canvas."""
        self._push_undo()
        center = self._to_world(QPointF(self.width() / 2, self.height() / 2))
        cx, cy = center.x(), center.y()
        new_shapes = build_preset(name, cx, cy, scale=1.0, color=self.color, width=self.stroke_width)
        self.shapes.extend(new_shapes)
        self._shapes_mutated()
        self.update()

    def _clear_selection(self):
        if self._selected_index is not None:
            self._selected_index = None
            self.selection_changed.emit(None)

    def clear(self):
        self._push_undo()
        self.shapes.clear()
        self._clear_selection()
        self._shapes_mutated()
        self.update()

    def undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(copy.deepcopy(self.shapes))
        self.shapes = self._undo_stack.pop()
        self._clear_selection()
        self._shapes_mutated()
        self.update()

    def redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(copy.deepcopy(self.shapes))
        self.shapes = self._redo_stack.pop()
        self._clear_selection()
        self._shapes_mutated()
        self.update()

    def delete_selected(self):
        if self._selected_index is not None:
            self._push_undo()
            del self.shapes[self._selected_index]
            self._clear_selection()
            self._shapes_mutated()
            self.update()

    def label_selected(self):
        """
        Type a name straight onto the selected object (press L or toolbar
        button) -- keyboard only, Quiver-diagram style: type real LaTeX like
        \\varphi or f_1, it's shown as the corresponding symbol on the canvas
        (see latex_render.py) and kept as real LaTeX for export.
        For a Line/Arrow (a morphism, in the Quiver philosophy) the label is
        centered just above the segment's midpoint, like an arrow label in a
        commutative diagram. For any other shape it's anchored beside it.
        """
        if self._selected_index is None:
            self.status_message.emit("Select a shape first (Select tool), then press L to name it.")
            return
        shape = self.shapes[self._selected_index]
        text, ok = QInputDialog.getText(
            self, "Name this object",
            "Label (real LaTeX -- e.g. \\varphi, \\Sigma_g, f_1, x^2, \\to):")
        if not (ok and text):
            return
        self._push_undo()
        if isinstance(shape, Line):  # covers Arrow too
            mx, my = (shape.p0[0] + shape.p1[0]) / 2, (shape.p0[1] + shape.p1[1]) / 2
            dx, dy = shape.p1[0] - shape.p0[0], shape.p1[1] - shape.p0[1]
            # canonicalize the direction (independent of which endpoint was
            # clicked first) so the label always ends up on the same side
            if dx < 0 or (dx == 0 and dy < 0):
                dx, dy = -dx, -dy
            length = math.hypot(dx, dy) or 1.0
            # unit normal pointing towards the top of the screen (canvas y
            # grows downward), so the label sits ABOVE the segment like an
            # arrow label in a commutative diagram
            nx, ny = dy / length, -dx / length
            if ny > 0:
                nx, ny = -nx, -ny
            label_x, label_y = mx + nx * 14, my + ny * 14
        else:
            x0, y0, x1, y1 = shape.bbox()
            label_x, label_y = x1 + 10, (y0 + y1) / 2
        self.shapes.append(TextLabel(label_x, label_y, text, latex=True,
                                      color=getattr(shape, "color", self.color), fontsize=16))
        self._shapes_mutated()
        self.update()
        self.status_message.emit(f"Labeled selected shape: {text}")

    def _push_undo(self):
        self._undo_stack.append(copy.deepcopy(self.shapes))
        self._undo_stack = self._undo_stack[-100:]
        self._redo_stack.clear()

    def _finish_pending(self):
        """Cleanly finish whatever interactive tool is in progress."""
        if self._pen_anchors and len(self._pen_anchors) >= 2:
            self._commit_pen_path()
        self._pen_anchors = []
        if self._poly_points and len(self._poly_points) >= 2:
            self._commit_polygon(closed=False)
        self._poly_points = []
        self._drawing_stroke = False
        self._raw_points = []
        self._drag_start = None
        self._erasing_active = False
        self.update()

    # -------------------------------------------------------- events
    # All these entry points convert the raw widget pixel position to WORLD
    # coordinates via self._to_world() before handing off to the tool logic
    # below (_begin_action/_continue_action/_end_action/...), which is
    # unchanged and keeps operating purely in world/shape space -- panning
    # and zooming only affect how that space is mapped onto the screen.
    def tabletEvent(self, event: QTabletEvent):
        # Crash guard (macOS + PyQt5): if any modal dialog is open (Photo
        # URL, color picker, save/open, the LaTeX label box...), the OS can
        # keep delivering raw tablet-proximity/move events to this widget
        # underneath the dialog. If those events were allowed to run drawing
        # actions, and a tool that itself opens a dialog (e.g. Text/LaTeX)
        # got triggered from inside another dialog's nested event loop, Qt's
        # event loops nest without bound and macOS aborts the app ("Too many
        # nested CFRunLoopRuns"). Simplest, robust fix: while a modal dialog
        # is active, the canvas ignores tablet input entirely.
        if QApplication.activeModalWidget() is not None:
            event.ignore()
            return
        pos = self._to_world(event.posF())  # sub-pixel precision from the tablet driver
        pressure = max(0.15, event.pressure())
        if event.type() == QTabletEvent.TabletPress:
            self._pressure_ema = pressure
            self._begin_action(pos, pressure)
            self.update()
        elif event.type() == QTabletEvent.TabletMove:
            # exponential smoothing kills pressure jitter without lag
            self._pressure_ema += PRESSURE_SMOOTHING * (pressure - self._pressure_ema)
            self._continue_action(pos, self._pressure_ema)
        elif event.type() == QTabletEvent.TabletRelease:
            self._end_action(pos)
            self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if QApplication.activeModalWidget() is not None:
            event.ignore()
            return
        self.setFocus()
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space_held):
            self._begin_pan(event.pos())
            return
        if event.button() == Qt.LeftButton:
            self._begin_action(self._to_world(event.pos()), 1.0)
        elif event.button() == Qt.RightButton:
            self._finish_pending()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            self._continue_pan(event.pos())
        elif event.buttons() & Qt.LeftButton:
            self._continue_action(self._to_world(event.pos()), 1.0)
        else:
            self._drag_current = self._to_world(event.pos())
            if self._pen_anchors or self.tool == "eraser":
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._panning and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._end_pan()
            return
        if event.button() == Qt.LeftButton:
            self._end_action(self._to_world(event.pos()))

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if QApplication.activeModalWidget() is not None:
            event.ignore()
            return
        if self.tool == "bezier":
            self._commit_pen_path()
        elif self.tool == "polygon":
            self._commit_polygon(closed=True)
        elif self.tool == "text":
            self._add_text(self._to_world(event.pos()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            if not self._panning:
                self.setCursor(Qt.OpenHandCursor)
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._finish_pending()
        elif event.key() == Qt.Key_Escape:
            self._pen_anchors = []
            self._poly_points = []
            self.update()
        elif event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
        elif event.key() == Qt.Key_L:
            self.label_selected()
        elif event.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key_0:
            self.reset_zoom()
        elif event.matches(QKeySequence.Copy):
            self.copy_selected()
        elif event.matches(QKeySequence.Paste):
            self.paste_shape()
        elif event.key() == Qt.Key_D and event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            self.duplicate_selected()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            if not self._panning:
                self.setCursor(Qt.ArrowCursor)

    # -------------------------------------------------------- tool logic
    def _snap(self, p: QPointF) -> QPointF:
        if not self.snap_to_grid:
            return p
        g = self.grid_size
        return QPointF(round(p.x() / g) * g, round(p.y() / g) * g)

    def _begin_action(self, pos, pressure):
        pos = self._snap(QPointF(pos))
        if self.tool == "pen":
            self._drawing_stroke = True
            self._raw_points = [(pos.x(), pos.y(), pressure)]
        elif self.tool in ("line", "arrow", "ellipse"):
            self._drag_start = pos
            self._drag_current = pos
        elif self.tool == "polygon":
            self._poly_points.append((pos.x(), pos.y()))
        elif self.tool == "bezier":
            self._pen_anchor_start = pos
            self._pen_dragging_handle = True
            self._pen_anchors.append({"p": (pos.x(), pos.y()), "h_out": (pos.x(), pos.y()), "h_in": (pos.x(), pos.y())})
        elif self.tool == "eraser":
            self._erasing_active = True
            self._push_undo()
            self._erase_partial(pos)
        elif self.tool == "select":
            self._select_at(pos)
            self._move_last = pos
        elif self.tool == "text":
            self._add_text(pos)

    def _continue_action(self, pos, pressure):
        pos = self._snap(QPointF(pos))
        if self.tool == "pen" and self._drawing_stroke:
            lx, ly, _ = self._raw_points[-1]
            dx, dy = pos.x() - lx, pos.y() - ly
            if dx * dx + dy * dy < MIN_POINT_DISTANCE * MIN_POINT_DISTANCE:
                return  # ignore micro-moves: less jitter, fewer points, less CPU
            self._raw_points.append((pos.x(), pos.y(), pressure))
            # dirty-rect repaint (in world coords, mapped through the current
            # pan/zoom to widget pixels): only the region around the new
            # segment is repainted, not the whole canvas
            m = self.stroke_width * 2.5 + 8
            self.update(self._world_rect_to_widget(
                min(lx, pos.x()) - m, min(ly, pos.y()) - m,
                max(lx, pos.x()) + m, max(ly, pos.y()) + m))
        elif self.tool in ("line", "arrow", "ellipse") and self._drag_start is not None:
            self._drag_current = pos
            self.update()
        elif self.tool == "bezier" and self._pen_dragging_handle and self._pen_anchors:
            anchor = self._pen_anchors[-1]
            ax, ay = anchor["p"]
            anchor["h_out"] = (pos.x(), pos.y())
            anchor["h_in"] = (2 * ax - pos.x(), 2 * ay - pos.y())
            self.update()
        elif self.tool == "eraser" and self._erasing_active:
            self._drag_current = pos
            self._erase_partial(pos)
        elif self.tool == "select" and self._selected_index is not None and self._move_last is not None:
            dx, dy = pos.x() - self._move_last.x(), pos.y() - self._move_last.y()
            self.shapes[self._selected_index].translate(dx, dy)
            self._move_last = pos
            # selected shape lives in the overlay, cache untouched -> fast move
            self.update()

    def _end_action(self, pos):
        pos = self._snap(QPointF(pos))
        if self.tool == "pen" and self._drawing_stroke:
            self._drawing_stroke = False
            if len(self._raw_points) >= 2:
                self._commit_freehand(self._raw_points)
            self._raw_points = []
        elif self.tool in ("line", "arrow", "ellipse") and self._drag_start is not None:
            self._commit_two_point_shape(self._drag_start, pos)
            self._drag_start = None
        elif self.tool == "bezier":
            self._pen_dragging_handle = False
        elif self.tool == "eraser":
            self._erasing_active = False
        elif self.tool == "select":
            self._move_last = None
            self._shapes_mutated()  # refresh TikZ code after a move
        self.update()

    # -------------------------------------------------------- shape creation
    @staticmethod
    def _xy(pts3):
        return [(x, y) for (x, y, _p) in pts3]

    def _node_widths(self, pts3, node_points) -> Optional[List[float]]:
        """
        Map stylus pressure onto the fitted curve: for each Bezier node, take
        the pressure of the nearest raw input point and convert it to a width.
        Returns None when pressure is off / flat (mouse input).
        """
        if not self.pressure_enabled:
            return None
        pr = np.array([p for (_x, _y, p) in pts3], dtype=float)
        if len(pr) < 2 or float(pr.max() - pr.min()) < 0.04:
            return None  # mouse or near-constant pressure: constant width
        # light smoothing of the pressure profile
        if len(pr) >= 5:
            kernel = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
            kernel /= kernel.sum()
            pr = np.convolve(np.pad(pr, 2, mode="edge"), kernel, mode="valid")
        arr = np.array([[x, y] for (x, y, _p) in pts3], dtype=float)
        base = self.stroke_width
        widths = []
        for (nx, ny) in node_points:
            d2 = (arr[:, 0] - nx) ** 2 + (arr[:, 1] - ny) ** 2
            p = float(pr[int(np.argmin(d2))])
            widths.append(float(np.clip(base * (0.45 + 1.1 * p), 0.4, base * 2.2)))
        return widths

    @staticmethod
    def _segment_nodes(segments):
        nodes = [segments[0][0]]
        for seg in segments:
            nodes.append(seg[3])
        return nodes

    def _commit_freehand(self, pts3):
        self._push_undo()

        # A high-frequency tablet stroke can contain thousands of points;
        # subsample before analysis (perf + robustness).
        if len(pts3) > 400:
            step = len(pts3) // 400 + 1
            pts3 = pts3[::step] + [pts3[-1]]

        if self.auto_vectorize:
            try:
                self._commit_freehand_smart(pts3)
                return
            except Exception as exc:
                # Safety net: an error in recognition/smoothing must NEVER
                # crash the app. Fall back to plain Bezier smoothing.
                self.status_message.emit(f"Auto-finish unavailable for this stroke ({exc}) -> simple smoothing.")

        pts = self._xy(pts3)
        err = adaptive_max_error(pts, ratio=0.02, lo=1.5, hi=30.0) if self.smooth_finish else 6.0
        segments = fit_curve(pts, max_error=err)
        widths = self._node_widths(pts3, self._segment_nodes(segments)) if segments else None
        self.shapes.append(BezierStroke(segments, color=self.color, width=self.stroke_width,
                                         widths=widths))
        self._shapes_mutated()

    def _commit_freehand_smart(self, pts3):
        pts = self._xy(pts3)
        result = classify_stroke(pts)
        if result is not None:
            kind = result[0]
            if kind == "line":
                _, p0, p1 = result
                self.shapes.append(Line(p0, p1, color=self.color, width=self.stroke_width))
                self._shapes_mutated()
                self.status_message.emit("Auto-finish -> perfect line")
                return
            if kind == "ellipse":
                _, cx, cy, rx, ry = result
                self.shapes.append(Ellipse(cx, cy, max(rx, 1), max(ry, 1), color=self.color,
                                            width=self.stroke_width, filled=self.fill_enabled,
                                            fill_color=self.fill_color if self.fill_enabled else None))
                self._shapes_mutated()
                self.status_message.emit("Auto-finish -> perfect circle/ellipse")
                return
            if kind == "polygon":
                _, corners = result
                self.shapes.append(Polygon(corners, color=self.color, width=self.stroke_width,
                                            closed=True, filled=self.fill_enabled,
                                            fill_color=self.fill_color if self.fill_enabled else None))
                self._shapes_mutated()
                self.status_message.emit("Auto-finish -> sharp-cornered polygon")
                return

        # No clean primitive detected (organic outline: silhouette, handle...)
        # -> ONLY correct the stroke (jitter removal + curvature fairing).
        # Auto-finish must never change the shape you actually drew -- no
        # forced bilateral symmetry here. Full symmetrization is a distinct,
        # DELIBERATE action (Idealize / Machine finish), never automatic.
        arr = np.array(pts)
        closed = bool(np.hypot(arr[0, 0] - arr[-1, 0], arr[0, 1] - arr[-1, 1]) < 0.06 * (
            np.hypot(arr[:, 0].max() - arr[:, 0].min(), arr[:, 1].max() - arr[:, 1].min()) or 1.0))
        cleaned = clean_stroke(pts, closed=closed, n_samples=140, passes=12)
        cleaned = taubin_fair(cleaned, closed, passes=15)  # fair curvature, no shrink
        err = adaptive_max_error(cleaned, ratio=0.008, lo=1.0, hi=14.0) if self.smooth_finish else 3.0
        segments = fit_curve(cleaned, max_error=err)
        widths = self._node_widths(pts3, self._segment_nodes(segments)) if segments else None
        self.shapes.append(BezierStroke(segments, color=self.color, width=self.stroke_width,
                                         closed=closed, filled=self.fill_enabled and closed,
                                         fill_color=self.fill_color if (self.fill_enabled and closed) else None,
                                         widths=widths))
        self._shapes_mutated()
        self.status_message.emit("Auto-finish -> stroke corrected (jitter removed, curvature smoothed)")

    def idealize_selected(self):
        """
        Manual "make this look machine-made" action: re-runs a STRONGER
        clean-up + full symmetrization pass on the selected shape. The result
        is a constant-width, fully machine-looking outline (pressure profile
        intentionally dropped).
        """
        if self._selected_index is None:
            self.status_message.emit("Select a shape first (Select tool), then Idealize.")
            return
        shape = self.shapes[self._selected_index]
        if not isinstance(shape, BezierStroke) or not shape.segments:
            self.status_message.emit("Idealize only applies to freehand/pen strokes.")
            return

        self._push_undo()
        pts = _sample_bezier_stroke(shape.segments, 24)
        closed = shape.closed or bool(np.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6)
        cleaned = clean_stroke(pts, closed=closed, n_samples=140, passes=14)
        if closed:
            cleaned = symmetrize_closed_curve(cleaned, strength=1.0)
            cleaned = clean_stroke(cleaned, closed=True, n_samples=140, passes=6)
        err = adaptive_max_error(cleaned, ratio=0.008, lo=1.0, hi=12.0) if self.smooth_finish else 2.0
        segments = fit_curve(cleaned, max_error=err)
        self.shapes[self._selected_index] = BezierStroke(
            segments, color=shape.color, width=shape.width, closed=closed,
            filled=shape.filled, fill_color=shape.fill_color,
        )
        self._shapes_mutated()
        self.update()
        self.status_message.emit("Shape idealized (symmetrized and cleaned up).")

    # -------------------------------------------------------- edge/style controls
    # Quiver-style live editing of the currently selected shape: solid/
    # dashed/dotted style works on ANY shape (BezierStroke, Line/Arrow,
    # Ellipse, Polygon); curve (bend), reverse and double stroke are
    # Line/Arrow-only. Each mutates in place and refreshes the cache/TikZ
    # code immediately. Dashed/dotted is always rendered/exported as a
    # single continuous, constant-width path (render.py / tikz_export.py),
    # which is what guarantees perfectly even dash size and spacing -- the
    # fix for a hand-drawn stroke whose dashes would otherwise come out
    # uneven at each Bezier segment boundary.
    def _selected_edge(self):
        if self._selected_index is None:
            return None
        shape = self.shapes[self._selected_index]
        return shape if isinstance(shape, Line) else None  # Arrow is-a Line

    def _selected_styleable(self):
        if self._selected_index is None:
            return None
        shape = self.shapes[self._selected_index]
        return shape if hasattr(shape, "line_style") else None

    def set_selected_bend(self, bend: float):
        edge = self._selected_edge()
        if edge is None:
            return
        edge.bend = float(max(-1.0, min(1.0, bend)))
        self._shapes_mutated()
        self.update()

    def set_selected_line_style(self, style: str):
        shape = self._selected_styleable()
        if shape is None:
            return
        shape.line_style = style
        self._shapes_mutated()
        self.update()
        if style != "solid":
            self.status_message.emit(f"Style set to {style} -- evenly spaced automatically.")

    def set_selected_head_style(self, style: str):
        """Quiver-style arrowhead picker (Stealth/Classical/Harpoon/None) --
        only meaningful on an Arrow (a plain Line never draws a head), but
        harmless to store on any edge."""
        edge = self._selected_edge()
        if edge is None:
            return
        edge.head_style = style
        self._shapes_mutated()
        self.update()

    def set_selected_double(self, enabled: bool):
        edge = self._selected_edge()
        if edge is None:
            return
        edge.double = bool(enabled)
        self._shapes_mutated()
        self.update()

    def reverse_selected_edge(self):
        edge = self._selected_edge()
        if edge is None:
            self.status_message.emit("Select a Line/Arrow first, then Reverse.")
            return
        self._push_undo()
        edge.reverse()
        self._shapes_mutated()
        self.update()
        self.selection_changed.emit(edge)  # refresh the edge panel's endpoints-dependent state
        self.status_message.emit("Edge reversed.")

    # -------------------------------------------------------- copy / paste / duplicate
    def copy_selected(self):
        """Copy the selected shape to an internal clipboard (a deep copy, so
        later edits to the original never leak into the copy or vice versa)."""
        if self._selected_index is None:
            self.status_message.emit("Select a shape first, then Copy.")
            return
        self._clipboard = copy.deepcopy(self.shapes[self._selected_index])
        self.status_message.emit("Shape copied.")

    def paste_shape(self):
        """Paste the clipboard shape, nudged slightly so it doesn't sit
        exactly on top of the original, and select the new copy."""
        if self._clipboard is None:
            self.status_message.emit("Clipboard is empty -- Copy a shape first.")
            return
        self._push_undo()
        new_shape = copy.deepcopy(self._clipboard)
        new_shape.translate(16, 16)
        self.shapes.append(new_shape)
        self._selected_index = len(self.shapes) - 1
        self.selection_changed.emit(new_shape)
        self._shapes_mutated()
        self.update()
        self.status_message.emit("Shape pasted.")

    def duplicate_selected(self):
        """Copy + paste in one step (Ctrl/Cmd+D), the standard 'Duplicate'
        shortcut in vector-illustration apps."""
        if self._selected_index is None:
            self.status_message.emit("Select a shape first, then Duplicate.")
            return
        self._push_undo()
        new_shape = copy.deepcopy(self.shapes[self._selected_index])
        new_shape.translate(16, 16)
        self.shapes.append(new_shape)
        self._selected_index = len(self.shapes) - 1
        self.selection_changed.emit(new_shape)
        self._shapes_mutated()
        self.update()
        self.status_message.emit("Shape duplicated.")

    # -------------------------------------------------------- z-order (Arrange)
    def bring_to_front(self):
        self._reorder_selected(lambda shapes, i: (shapes.append(shapes.pop(i)), len(shapes) - 1)[1])

    def send_to_back(self):
        self._reorder_selected(lambda shapes, i: (shapes.insert(0, shapes.pop(i)), 0)[1])

    def bring_forward(self):
        self._reorder_selected(lambda shapes, i: self._swap_index(shapes, i, min(i + 1, len(shapes) - 1)))

    def send_backward(self):
        self._reorder_selected(lambda shapes, i: self._swap_index(shapes, i, max(i - 1, 0)))

    @staticmethod
    def _swap_index(shapes, i, j):
        shapes[i], shapes[j] = shapes[j], shapes[i]
        return j

    def _reorder_selected(self, reorder_fn):
        if self._selected_index is None:
            self.status_message.emit("Select a shape first, then use Arrange.")
            return
        self._push_undo()
        new_index = reorder_fn(self.shapes, self._selected_index)
        self._selected_index = new_index
        self._shapes_mutated()
        self.update()

    # -------------------------------------------------------- flip / rotate
    def _replace_selected(self, new_shape):
        self._push_undo()
        self.shapes[self._selected_index] = new_shape
        self._shapes_mutated()
        self.update()
        self.selection_changed.emit(new_shape)

    def flip_selected_horizontal(self):
        if self._selected_index is None:
            self.status_message.emit("Select a shape first, then Flip.")
            return
        self._replace_selected(shape_transform.flip_horizontal(self.shapes[self._selected_index]))
        self.status_message.emit("Shape flipped horizontally.")

    def flip_selected_vertical(self):
        if self._selected_index is None:
            self.status_message.emit("Select a shape first, then Flip.")
            return
        self._replace_selected(shape_transform.flip_vertical(self.shapes[self._selected_index]))
        self.status_message.emit("Shape flipped vertically.")

    def rotate_selected_90(self):
        if self._selected_index is None:
            self.status_message.emit("Select a shape first, then Rotate.")
            return
        self._replace_selected(shape_transform.rotate90(self.shapes[self._selected_index]))
        self.status_message.emit("Shape rotated 90°.")

    def machine_finish_all(self):
        """
        Global "make the WHOLE drawing look machine-made" pass: every shape
        is re-idealized at once (near-circles -> perfect circles, near-lines
        -> straight lines snapped to standard angles, organic outlines ->
        symmetrized + faired constant-width curves). One click, one undo step.
        """
        if not self.shapes:
            self.status_message.emit("Nothing to finish yet -- draw something first.")
            return
        self._push_undo()
        self.shapes = machine_finish(self.shapes)
        self._clear_selection()
        self._shapes_mutated()
        self.update()
        self.status_message.emit(
            "Machine finish applied to the whole drawing (undo with Ctrl+Z if too strong).")

    def _commit_two_point_shape(self, p0: QPointF, p1: QPointF):
        self._push_undo()
        if self.tool == "line":
            self.shapes.append(Line((p0.x(), p0.y()), (p1.x(), p1.y()), color=self.color, width=self.stroke_width))
        elif self.tool == "arrow":
            self.shapes.append(Arrow((p0.x(), p0.y()), (p1.x(), p1.y()), color=self.color, width=self.stroke_width))
        elif self.tool == "ellipse":
            cx, cy = (p0.x() + p1.x()) / 2, (p0.y() + p1.y()) / 2
            rx, ry = abs(p1.x() - p0.x()) / 2, abs(p1.y() - p0.y()) / 2
            self.shapes.append(Ellipse(cx, cy, max(rx, 1), max(ry, 1), color=self.color, width=self.stroke_width,
                                        filled=self.fill_enabled,
                                        fill_color=self.fill_color if self.fill_enabled else None))
        self._shapes_mutated()

    def _commit_polygon(self, closed: bool):
        if len(self._poly_points) < 2:
            self._poly_points = []
            return
        self._push_undo()
        self.shapes.append(Polygon(list(self._poly_points), color=self.color, width=self.stroke_width, closed=closed,
                                    filled=self.fill_enabled and closed,
                                    fill_color=self.fill_color if (self.fill_enabled and closed) else None))
        self._poly_points = []
        self._shapes_mutated()

    def _commit_pen_path(self):
        if len(self._pen_anchors) < 2:
            self._pen_anchors = []
            return
        self._push_undo()
        segments = []
        for i in range(len(self._pen_anchors) - 1):
            a, b = self._pen_anchors[i], self._pen_anchors[i + 1]
            segments.append((a["p"], a["h_out"], b["h_in"], b["p"]))
        self.shapes.append(BezierStroke(segments, color=self.color, width=self.stroke_width))
        self._pen_anchors = []
        self._shapes_mutated()

    def _add_text(self, pos):
        text, ok = QInputDialog.getText(self, "Text / LaTeX", "Content (LaTeX, e.g. \\Sigma_g or $x^2$):")
        if ok and text:
            self._push_undo()
            self.shapes.append(TextLabel(pos.x(), pos.y(), text, latex=True, color=self.color, fontsize=16))
            self._shapes_mutated()
            self.update()

    # -------------------------------------------------------- eraser (real partial erase)
    def _erase_partial(self, pos: QPointF):
        center = (pos.x(), pos.y())
        radius = self.eraser_radius
        changed = False
        new_shapes = []
        for shape in self.shapes:
            x0, y0, x1, y1 = shape.bbox()
            if pos.x() < x0 - radius or pos.x() > x1 + radius or pos.y() < y0 - radius or pos.y() > y1 + radius:
                new_shapes.append(shape)
                continue

            result = erase_shape(shape, center, radius)

            if result is None:
                # Unsupported type for partial erase (Ellipse, Text label):
                # fall back to whole-shape delete if the eraser is over it.
                if x0 - 8 <= pos.x() <= x1 + 8 and y0 - 8 <= pos.y() <= y1 + 8:
                    changed = True
                    continue
                new_shapes.append(shape)
                continue

            if len(result) == 1 and result[0] is shape:
                new_shapes.append(shape)
                continue

            changed = True
            new_shapes.extend(result)

        if changed:
            self.shapes = new_shapes
            if self._selected_index is not None and self._selected_index >= len(self.shapes):
                self._selected_index = None
            self._shapes_mutated()
            self.update()

    def _select_at(self, pos: QPointF):
        old = self._selected_index
        self._selected_index = None
        for i in reversed(range(len(self.shapes))):
            x0, y0, x1, y1 = self.shapes[i].bbox()
            pad = 6
            if x0 - pad <= pos.x() <= x1 + pad and y0 - pad <= pos.y() <= y1 + pad:
                self._selected_index = i
                break
        if self._selected_index != old:
            self._invalidate_cache()  # selection is excluded from the cache
            sel = self.shapes[self._selected_index] if self._selected_index is not None else None
            self.selection_changed.emit(sel)
        self.update()

    # -------------------------------------------------------- rendering
    def paintEvent(self, event):
        self._ensure_cache()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # committed shapes: one blit of the HiDPI backing store (already
        # baked in at the current pan/zoom -- see _ensure_cache)
        painter.drawPixmap(0, 0, self._cache)

        # everything below is drawn fresh each frame in WORLD coordinates,
        # so it's wrapped in the same pan/zoom transform as the cache
        painter.save()
        painter.translate(self.view_offset)
        painter.scale(self.view_scale, self.view_scale)

        # selected shape drawn live (excluded from the cache -> instant moves)
        if self._selected_index is not None and self._selected_index < len(self.shapes):
            paint_shape(painter, self.shapes[self._selected_index], highlight=True)

        # in-progress live ink
        if self._drawing_stroke and len(self._raw_points) >= 2:
            self._paint_live_stroke(painter)

        painter.setPen(QPen(QColor(self.color), self.stroke_width, Qt.SolidLine))
        if self._drag_start is not None and self._drag_current is not None:
            p0, p1 = self._drag_start, self._drag_current
            if self.tool in ("line", "arrow"):
                painter.drawLine(p0, p1)
                if self.tool == "arrow":
                    draw_arrow_head(painter, p0, p1, QColor(self.color),
                                    size=max(9.0, 3.2 * self.stroke_width))
            elif self.tool == "ellipse":
                rect = QRectF(min(p0.x(), p1.x()), min(p0.y(), p1.y()), abs(p1.x() - p0.x()), abs(p1.y() - p0.y()))
                painter.drawEllipse(rect)

        if self._poly_points:
            path = QPainterPath()
            path.moveTo(*self._poly_points[0])
            for x, y in self._poly_points[1:]:
                path.lineTo(x, y)
            painter.setPen(QPen(QColor(self.color), self.stroke_width, Qt.DashLine))
            painter.drawPath(path)

        if self._pen_anchors:
            painter.setPen(QPen(QColor("#3388ff"), 1.5, Qt.DashLine))
            path = QPainterPath()
            path.moveTo(*self._pen_anchors[0]["p"])
            pts = self._pen_anchors
            for i in range(len(pts) - 1):
                a, b = pts[i], pts[i + 1]
                path.cubicTo(QPointF(*a["h_out"]), QPointF(*b["h_in"]), QPointF(*b["p"]))
            if self._drag_current is not None:
                last = pts[-1]
                path.cubicTo(QPointF(*last["h_out"]), self._drag_current, self._drag_current)
            painter.drawPath(path)
            painter.setBrush(QBrush(QColor("#3388ff")))
            for a in pts:
                painter.drawEllipse(QPointF(*a["p"]), 3, 3)
                painter.drawLine(QPointF(*a["h_in"]), QPointF(*a["h_out"]))

        if self.tool == "eraser" and self._drag_current is not None:
            painter.setPen(QPen(QColor("#ff5500"), 1.2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self._drag_current, self.eraser_radius, self.eraser_radius)

        painter.restore()
        painter.end()

    def _paint_live_stroke(self, painter: QPainter):
        """Live ink preview. With pressure enabled, each polyline segment is
        drawn at its own width so what you see while drawing matches the
        committed variable-width stroke."""
        pen = QPen(QColor(self.color), self.stroke_width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        pts = self._raw_points
        pressures = [p for (_x, _y, p) in pts]
        variable = self.pressure_enabled and (max(pressures) - min(pressures) > 0.04)
        if not variable:
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(pts[0][0], pts[0][1])
            for (x, y, _p) in pts[1:]:
                path.lineTo(x, y)
            painter.drawPath(path)
            return
        base = self.stroke_width
        for i in range(len(pts) - 1):
            x0, y0, p0 = pts[i]
            x1, y1, p1 = pts[i + 1]
            w = base * (0.45 + 1.1 * 0.5 * (p0 + p1))
            pen.setWidthF(max(0.4, min(w, base * 2.2)))
            painter.setPen(pen)
            painter.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    def _draw_grid(self, painter):
        painter.setPen(QPen(QColor("#eeeeee"), 1))
        for x in range(0, self.width(), self.grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), self.grid_size):
            painter.drawLine(0, y, self.width(), y)
