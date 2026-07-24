"""
beautify.py  (v4.1)
"Machine finish": one global pass that re-idealizes EVERY shape of the
drawing so the final figure looks produced by design software, not traced
by hand.

Per shape:
- BezierStroke: re-sampled and re-classified. A near-circle becomes a perfect
  Ellipse, a near-straight stroke becomes a Line, a cornered outline becomes
  a Polygon. Anything organic (genus-g silhouette, handle, lens...) is
  cleaned, fully symmetrized, then FAIRED with Taubin smoothing (lambda/mu
  scheme: smooths curvature without shrinking the shape -- the classic
  'French curve' look) and refit with a tight tolerance into a few long,
  confident Bezier curves of constant width.
- Line / Arrow: the angle is snapped to the nearest 15 degrees when it is
  within 4 degrees of it (rotation around the midpoint, length preserved) --
  almost-horizontal lines become exactly horizontal, etc.
- Ellipse / Text: already ideal, kept as-is.

Everything is deterministic geometry (least squares + smoothing), no AI model.
"""
from __future__ import annotations
import math
from typing import List

import numpy as np

from shapes import Shape, BezierStroke, Line, Arrow, Ellipse, Polygon, TextLabel
from shape_recognition import classify_stroke
from smoothing import clean_stroke, symmetrize_closed_curve
from curvefit import fit_curve, adaptive_max_error
from erasing import _sample_bezier_stroke

SNAP_STEP_DEG = 15.0   # lines snap to multiples of this angle...
SNAP_TOL_DEG = 4.0     # ...when within this tolerance


def taubin_fair(points_xy, closed: bool, passes: int = 25, step: float = 0.5):
    """Curvature fairing without shrinkage: strong Laplacian smoothing (kills
    the hand-drawn ripple), then the curve is rescaled around its centroid so
    its mean radius is exactly the original one -- a circle stays the same
    size, only the wobble disappears. Open curves keep their endpoints
    pinned (no size drift there)."""
    P = np.array([(float(x), float(y)) for (x, y) in points_xy], dtype=float)
    n = len(P)
    if n < 5:
        return [tuple(p) for p in P]
    # drop a duplicated closing point during fairing, restore it after
    dup = closed and np.linalg.norm(P[0] - P[-1]) < 1e-9
    if dup:
        P = P[:-1]
    orig = P.copy()
    for _ in range(passes):
        if closed:
            L = 0.5 * (np.roll(P, 1, axis=0) + np.roll(P, -1, axis=0))
            P = P + step * (L - P)
        else:
            Q = P.copy()
            Q[1:-1] = P[1:-1] + step * (0.5 * (P[:-2] + P[2:]) - P[1:-1])
            P = Q
    if closed:
        c_o = orig.mean(axis=0)
        c_s = P.mean(axis=0)
        r_o = float(np.linalg.norm(orig - c_o, axis=1).mean())
        r_s = float(np.linalg.norm(P - c_s, axis=1).mean())
        if r_s > 1e-9:
            P = c_o + (P - c_s) * (r_o / r_s)
    out = [tuple(p) for p in P]
    if dup:
        out.append(out[0])
    return out


def _snap_endpoints(p0, p1):
    """Snap the segment's direction to the nearest SNAP_STEP_DEG multiple if
    close enough; rotate around the midpoint, keep the length."""
    x0, y0 = p0
    x1, y1 = p1
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    target = round(ang / SNAP_STEP_DEG) * SNAP_STEP_DEG
    if abs(ang - target) < 1e-9 or abs(ang - target) > SNAP_TOL_DEG:
        return p0, p1
    length = math.hypot(x1 - x0, y1 - y0)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    t = math.radians(target)
    dx, dy = 0.5 * length * math.cos(t), 0.5 * length * math.sin(t)
    return (mx - dx, my - dy), (mx + dx, my + dy)


def machine_finish_shape(shape: Shape) -> Shape:
    """Returns the machine-idealized version of one shape (never mutates the
    input). Unknown/already-perfect types are returned unchanged."""
    if isinstance(shape, (Arrow, Line)) and not isinstance(shape, BezierStroke):
        cls = Arrow if isinstance(shape, Arrow) else Line
        if getattr(shape, "bend", 0.0):
            return shape  # a curved (Quiver-style) edge: leave the arc as drawn
        p0, p1 = _snap_endpoints(shape.p0, shape.p1)
        return cls(p0, p1, color=shape.color, width=shape.width,
                  line_style=shape.line_style, double=shape.double)

    if isinstance(shape, BezierStroke) and shape.segments:
        pts = _sample_bezier_stroke(shape.segments, 24)
        closed = shape.closed or (
            math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6)

        # try to promote the stroke to a perfect primitive first
        try:
            res = classify_stroke(pts)
        except Exception:
            res = None
        if res is not None:
            kind = res[0]
            if kind == "line":
                _, p0, p1 = res
                p0, p1 = _snap_endpoints(tuple(p0), tuple(p1))
                return Line(p0, p1, color=shape.color, width=shape.width,
                            dashed=shape.dashed)
            if kind == "ellipse":
                _, cx, cy, rx, ry = res
                # a near-circle becomes an exact circle
                if abs(rx - ry) < 0.08 * max(rx, ry):
                    rx = ry = 0.5 * (rx + ry)
                return Ellipse(cx, cy, max(rx, 1), max(ry, 1), color=shape.color,
                               width=shape.width, filled=shape.filled,
                               fill_color=shape.fill_color)
            if kind == "polygon":
                _, corners = res
                return Polygon([tuple(c) for c in corners], color=shape.color,
                               width=shape.width, closed=True, filled=shape.filled,
                               fill_color=shape.fill_color, dashed=shape.dashed)

        # organic outline: strong clean + full symmetrization + fairing
        cleaned = clean_stroke(pts, closed=closed, n_samples=160, passes=12)
        if closed:
            cleaned = symmetrize_closed_curve(cleaned, strength=1.0)
            cleaned = clean_stroke(cleaned, closed=True, n_samples=160, passes=6)
        cleaned = taubin_fair(cleaned, closed, passes=25)
        err = adaptive_max_error(cleaned, ratio=0.006, lo=0.8, hi=10.0)
        segments = fit_curve(cleaned, max_error=err)
        # constant width on purpose: uniform ink is the machine look
        return BezierStroke(segments, color=shape.color, width=shape.width,
                            closed=closed, filled=shape.filled,
                            fill_color=shape.fill_color, dashed=shape.dashed)

    return shape


def machine_finish(shapes: List[Shape]) -> List[Shape]:
    """Machine-idealize a whole drawing. Never raises: a shape that fails to
    process is kept unchanged (an imperfect shape is better than a crash)."""
    out = []
    for s in shapes:
        try:
            out.append(machine_finish_shape(s))
        except Exception:
            out.append(s)
    return out
