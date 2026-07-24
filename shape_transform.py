
from __future__ import annotations
import copy
from typing import Tuple

from shapes import Shape, BezierStroke, Line, Arrow, Ellipse, Polygon, TextLabel

Point = Tuple[float, float]


def _center(shape: Shape) -> Point:
    x0, y0, x1, y1 = shape.bbox()
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def flip_horizontal(shape: Shape) -> Shape:
    """Mirror the shape left-right about its own vertical center axis."""
    s = copy.deepcopy(shape)
    cx, _ = _center(shape)
    fx = lambda x: 2 * cx - x
    if isinstance(s, BezierStroke):
        s.segments = [tuple((fx(x), y) for (x, y) in seg) for seg in s.segments]
    elif isinstance(s, Line):  # covers Arrow too
        s.p0 = (fx(s.p0[0]), s.p0[1])
        s.p1 = (fx(s.p1[0]), s.p1[1])
        s.bend = -s.bend  # mirroring flips which side the arc bulges to
    elif isinstance(s, Ellipse):
        s.cx = fx(s.cx)
    elif isinstance(s, Polygon):
        s.points = [(fx(x), y) for (x, y) in s.points]
    elif isinstance(s, TextLabel):
        s.x = fx(s.x)
    return s


def flip_vertical(shape: Shape) -> Shape:
    """Mirror the shape top-bottom about its own horizontal center axis."""
    s = copy.deepcopy(shape)
    _, cy = _center(shape)
    fy = lambda y: 2 * cy - y
    if isinstance(s, BezierStroke):
        s.segments = [tuple((x, fy(y)) for (x, y) in seg) for seg in s.segments]
    elif isinstance(s, Line):
        s.p0 = (s.p0[0], fy(s.p0[1]))
        s.p1 = (s.p1[0], fy(s.p1[1]))
        s.bend = -s.bend
    elif isinstance(s, Ellipse):
        s.cy = fy(s.cy)
    elif isinstance(s, Polygon):
        s.points = [(x, fy(y)) for (x, y) in s.points]
    elif isinstance(s, TextLabel):
        s.y = fy(s.y)
    return s


def rotate90(shape: Shape, clockwise: bool = True) -> Shape:
    """Rotate the shape 90 degrees around its own bounding-box center."""
    s = copy.deepcopy(shape)
    cx, cy = _center(shape)
    sign = 1 if clockwise else -1

    def rot(x: float, y: float) -> Point:
        dx, dy = x - cx, y - cy
        # 90 degree rotation in a y-down screen coordinate system
        return (cx - sign * dy, cy + sign * dx)

    if isinstance(s, BezierStroke):
        s.segments = [tuple(rot(x, y) for (x, y) in seg) for seg in s.segments]
    elif isinstance(s, Line):
        s.p0 = rot(*s.p0)
        s.p1 = rot(*s.p1)
    elif isinstance(s, Ellipse):
        s.rx, s.ry = s.ry, s.rx  # a 90-deg-rotated ellipse swaps its axes
    elif isinstance(s, Polygon):
        s.points = [rot(x, y) for (x, y) in s.points]
    elif isinstance(s, TextLabel):
        s.x, s.y = rot(s.x, s.y)
    return s
