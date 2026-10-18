"""
render.py
Shared shape-painting logic used by both the interactive drawing canvas
(canvas.py) and the read-only live preview panel (preview_widget.py), so the
preview always shows exactly what will be exported, without duplicating the
drawing code.

v4:
- BezierStroke supports variable width per node (pen pressure): each cubic
  segment is stroked with its own width (round caps make it continuous).
- Arrow heads are now filled triangles (crisper, machine-made look).
"""
from __future__ import annotations
import math

from PyQt5.QtCore import Qt, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QPainterPath, QBrush, QFont

from shapes import Shape, BezierStroke, Line, Arrow, Ellipse, Polygon, TextLabel
from latex_render import latex_to_display
import edge_geom

_QT_STYLE = {"solid": Qt.SolidLine, "dashed": Qt.DashLine, "dotted": Qt.DotLine}


def paint_shapes(painter: QPainter, shapes, highlight_index=None):
    for i, shape in enumerate(shapes):
        paint_shape(painter, shape, highlight=(i == highlight_index))


def _stroke_path(shape: BezierStroke) -> QPainterPath:
    path = QPainterPath()
    if shape.segments:
        path.moveTo(*shape.segments[0][0])
        for (P0, C1, C2, P3) in shape.segments:
            path.cubicTo(QPointF(*C1), QPointF(*C2), QPointF(*P3))
    if getattr(shape, "filled", False) or getattr(shape, "closed", False):
        path.closeSubpath()
    return path


def _paint_bezier_variable(painter: QPainter, shape: BezierStroke, pen: QPen):
    """Variable-width stroke: fill first (single closed path), then stroke
    each cubic segment with its own pen width. RoundCap keeps the joints
    invisible, so the width transition reads as one continuous ink line."""
    if getattr(shape, "filled", False):
        fill_path = _stroke_path(shape)
        fc = shape.fill_color or shape.color
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(fc)))
        painter.drawPath(fill_path)
        painter.restore()

    painter.setBrush(Qt.NoBrush)
    w = shape.widths
    for k, (P0, C1, C2, P3) in enumerate(shape.segments):
        seg_pen = QPen(pen)
        seg_pen.setWidthF(max(0.3, 0.5 * (w[k] + w[k + 1])))
        painter.setPen(seg_pen)
        seg = QPainterPath()
        seg.moveTo(*P0)
        seg.cubicTo(QPointF(*C1), QPointF(*C2), QPointF(*P3))
        painter.drawPath(seg)
    if shape.closed and shape.segments:
        # close the visual outline with a small joining segment if needed
        first = shape.segments[0][0]
        last = shape.segments[-1][3]
        if abs(first[0] - last[0]) > 1e-6 or abs(first[1] - last[1]) > 1e-6:
            seg_pen = QPen(pen)
            seg_pen.setWidthF(max(0.3, 0.5 * (w[0] + w[-1])))
            painter.setPen(seg_pen)
            painter.drawLine(QPointF(*last), QPointF(*first))


def _edge_path(p0, p1, bend: float) -> QPainterPath:
    path = QPainterPath()
    path.moveTo(*p0)
    if bend:
        q = edge_geom.control_point(p0, p1, bend)
        path.quadTo(QPointF(*q), QPointF(*p1))
    else:
        path.lineTo(*p1)
    return path


def _paint_edge_body(painter: QPainter, shape, pen: QPen, highlight: bool):
    """Draws a Line/Arrow's stroke: straight or curved (bend), single or
    double (two thin parallel strokes -- Quiver's 'double line' edge style).
    The arrow head itself is drawn separately by the caller."""
    p0, p1 = shape.p0, shape.p1
    bend = getattr(shape, "bend", 0.0)
    if getattr(shape, "double", False) and not highlight:
        gap = max(2.0, 0.9 * shape.width + 1.2)
        thin = QPen(pen)
        thin.setWidthF(max(0.6, shape.width * 0.6))
        painter.setPen(thin)
        for sign in (-1, 1):
            q0, q1 = edge_geom.parallel_endpoints(p0, p1, sign * gap)
            painter.drawPath(_edge_path(q0, q1, bend))
        painter.setPen(pen)
    else:
        painter.drawPath(_edge_path(p0, p1, bend))


def paint_shape(painter: QPainter, shape: Shape, highlight: bool = False):
    pen = QPen(QColor(shape.color), shape.width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    if highlight:
        pen.setColor(QColor("#ff5500"))
        pen.setStyle(Qt.DashLine)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if isinstance(shape, BezierStroke):
        style = getattr(shape, "line_style", "solid")
        if style != "solid" and not highlight:
            pen.setStyle(_QT_STYLE.get(style, Qt.SolidLine))
            painter.setPen(pen)
        # Dashed/dotted strokes are ALWAYS drawn at constant width, as one
        # single continuous QPainterPath: Qt (and TikZ) apply the dash
        # pattern by arc length along a single stroke call, so this is what
        # guarantees perfectly even dash size/spacing all the way around --
        # e.g. a hand-drawn 'hidden waist curve' of a torus. Per-segment
        # variable-width drawing would restart the dash pattern at every
        # Bezier segment boundary and look broken/uneven.
        if shape.widths and style == "solid" and not highlight:
            _paint_bezier_variable(painter, shape, pen)
            return
        path = _stroke_path(shape)
        if getattr(shape, "filled", False):
            fc = shape.fill_color or shape.color
            painter.setBrush(QBrush(QColor(fc)))
        painter.drawPath(path)

    elif isinstance(shape, Arrow):
        if not highlight:
            pen.setStyle(_QT_STYLE.get(getattr(shape, "line_style", "solid"), Qt.SolidLine))
            painter.setPen(pen)
        _paint_edge_body(painter, shape, pen, highlight)
        p0, p1, bend = shape.p0, shape.p1, getattr(shape, "bend", 0.0)
        head_len = max(9.0, 3.2 * shape.width)
        if bend:
            q = edge_geom.control_point(p0, p1, bend)
            tx, ty = edge_geom.tangent_on_quad(1.0, p0, q, p1)
        else:
            tx, ty = p1[0] - p0[0], p1[1] - p0[1]
        tlen = math.hypot(tx, ty) or 1.0
        # a point just behind p1, along the travel direction (tangent at the
        # curve's end for a bent arrow) -- gives draw_arrow_head() the right heading
        behind = QPointF(p1[0] - tx / tlen, p1[1] - ty / tlen)
        draw_arrow_head(painter, behind, QPointF(*p1), pen.color(), size=head_len,
                        style=getattr(shape, "head_style", "stealth"))

    elif isinstance(shape, Line):
        if not highlight:
            pen.setStyle(_QT_STYLE.get(getattr(shape, "line_style", "solid"), Qt.SolidLine))
            painter.setPen(pen)
        _paint_edge_body(painter, shape, pen, highlight)

    elif isinstance(shape, Ellipse):
        if not highlight:
            pen.setStyle(_QT_STYLE.get(getattr(shape, "line_style", "solid"), Qt.SolidLine))
            painter.setPen(pen)
        if shape.filled:
            fc = shape.fill_color or shape.color
            painter.setBrush(QBrush(QColor(fc)))
        # a native single drawEllipse() call -> Qt applies the dash pattern
        # by arc length in one continuous stroke, so it's always perfectly
        # even -- no special-casing needed here (unlike multi-segment strokes)
        painter.drawEllipse(QPointF(shape.cx, shape.cy), shape.rx, shape.ry)

    elif isinstance(shape, Polygon):
        if not highlight:
            pen.setStyle(_QT_STYLE.get(getattr(shape, "line_style", "solid"), Qt.SolidLine))
            painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(*shape.points[0])
        for p in shape.points[1:]:
            path.lineTo(*p)
        if shape.closed:
            path.closeSubpath()
        if shape.filled:
            fc = shape.fill_color or shape.color
            painter.setBrush(QBrush(QColor(fc)))
        painter.drawPath(path)

    elif isinstance(shape, TextLabel):
        font = QFont("Georgia")
        font.setPointSize(shape.fontsize)
        font.setItalic(True)
        painter.setFont(font)
        display_text = latex_to_display(shape.text) if shape.latex else shape.text
        painter.drawText(QPointF(shape.x, shape.y), display_text)


def draw_arrow_head(painter: QPainter, p0: QPointF, p1: QPointF, color: QColor,
                    size: float = 10.0, style: str = "stealth"):
    """Arrow head, Quiver-style pickable tip: 'stealth' (filled concave
    triangle, was the only option before v4.12), 'classical' (plain open
    LaTeX-style V, two bare strokes), 'harpoon' (single one-sided barb), or
    'none' (no head at all -- an Arrow that reads as a plain line)."""
    if style == "none":
        return

    angle = math.atan2(p1.y() - p0.y(), p1.x() - p0.x())

    if style == "harpoon":
        a1 = angle + math.radians(153)
        p_a = QPointF(p1.x() + size * math.cos(a1), p1.y() + size * math.sin(a1))
        painter.save()
        pen = QPen(color, max(1.4, size * 0.16))
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(p1, p_a)
        painter.restore()
        return

    a1 = angle + math.radians(153)
    a2 = angle - math.radians(153)
    p_a = QPointF(p1.x() + size * math.cos(a1), p1.y() + size * math.sin(a1))
    p_b = QPointF(p1.x() + size * math.cos(a2), p1.y() + size * math.sin(a2))

    if style == "classical":
        # plain open V (bare strokes), like a default (non-Stealth) LaTeX arrow
        painter.save()
        pen = QPen(color, max(1.4, size * 0.16))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(pen)
        painter.drawLine(p1, p_a)
        painter.drawLine(p1, p_b)
        painter.restore()
        return

    # "stealth" (default): filled concave triangle
    back = QPointF(p1.x() + size * 0.55 * math.cos(angle + math.pi),
                   p1.y() + size * 0.55 * math.sin(angle + math.pi))
    path = QPainterPath()
    path.moveTo(p1)
    path.lineTo(p_a)
    path.lineTo(back)
    path.lineTo(p_b)
    path.closeSubpath()
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(color))
    painter.drawPath(path)
    painter.restore()


def shapes_bbox(shapes):
    """Overall bounding box of a list of shapes, or None if empty."""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for s in shapes:
        x0, y0, x1, y1 = s.bbox()
        xs0.append(x0); ys0.append(y0); xs1.append(x1); ys1.append(y1)
    if not xs0:
        return None
    return min(xs0), min(ys0), max(xs1), max(ys1)
