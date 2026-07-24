
from __future__ import annotations
import math
from typing import List, Optional

from shapes import Shape, BezierStroke, Line, Arrow, Polygon
from curvefit import fit_curve
import edge_geom

MIN_RUN_POINTS = 2


def _sample_line(p0, p1, n=40):
    return [
        (p0[0] + (p1[0] - p0[0]) * t / (n - 1), p0[1] + (p1[1] - p0[1]) * t / (n - 1))
        for t in range(n)
    ]


def _sample_polygon(points, closed, n_per_edge=14):
    pts = list(points)
    edges = list(zip(pts, pts[1:])) + ([(pts[-1], pts[0])] if closed else [])
    out = []
    for a, b in edges:
        out.extend(_sample_line(a, b, n_per_edge)[:-1])
    if not closed:
        out.append(pts[-1])
    return out


def _bezier_point(t, p0, c1, c2, p3):
    mt = 1 - t
    x = (mt**3)*p0[0] + 3*(mt**2)*t*c1[0] + 3*mt*(t**2)*c2[0] + (t**3)*p3[0]
    y = (mt**3)*p0[1] + 3*(mt**2)*t*c1[1] + 3*mt*(t**2)*c2[1] + (t**3)*p3[1]
    return (x, y)


def _sample_bezier_stroke(segments, n_per_seg=16):
    out = []
    for (p0, c1, c2, p3) in segments:
        for i in range(n_per_seg):
            t = i / n_per_seg
            out.append(_bezier_point(t, p0, c1, c2, p3))
    if segments:
        out.append(segments[-1][3])
    return out


def _sample_stroke_widths(widths, n_segments, n_per_seg=16):
   
    out = []
    for k in range(n_segments):
        w0, w1 = widths[k], widths[k + 1]
        for i in range(n_per_seg):
            t = i / n_per_seg
            out.append(w0 + (w1 - w0) * t)
    out.append(widths[-1])
    return out


def _split_runs(points: List[tuple], keep_mask: List[bool]):
    """Returns list of (points_in_run, start_index, end_index) for each
    contiguous kept run of length >= MIN_RUN_POINTS."""
    runs, current, current_start = [], [], None
    for i, (p, keep) in enumerate(zip(points, keep_mask)):
        if keep:
            if current_start is None:
                current_start = i
            current.append(p)
        else:
            if len(current) >= MIN_RUN_POINTS:
                runs.append((current, current_start, i - 1))
            current, current_start = [], None
    if len(current) >= MIN_RUN_POINTS:
        runs.append((current, current_start, len(points) - 1))
    return runs


def erase_shape(shape: Shape, center: tuple, radius: float) -> Optional[List[Shape]]:
   
    cx, cy = center

    if isinstance(shape, Arrow):
       
        pts = edge_geom.sample_edge(shape.p0, shape.p1, getattr(shape, "bend", 0.0), 50)
        mask = [math.hypot(x - cx, y - cy) > radius for (x, y) in pts]
        if all(mask):
            return [shape]
        last_idx = len(pts) - 1
        out = []
        for run, start_i, end_i in _split_runs(pts, mask):
            if end_i == last_idx:
                out.append(Arrow(run[0], run[-1], color=shape.color, width=shape.width,
                                 line_style=shape.line_style))
            else:
                out.append(Line(run[0], run[-1], color=shape.color, width=shape.width,
                                line_style=shape.line_style))
        return out

    if isinstance(shape, Line):
        pts = edge_geom.sample_edge(shape.p0, shape.p1, getattr(shape, "bend", 0.0), 50)
        mask = [math.hypot(x - cx, y - cy) > radius for (x, y) in pts]
        if all(mask):
            return [shape]
        return [Line(run[0], run[-1], color=shape.color, width=shape.width,
                    line_style=shape.line_style)
                for run, _, _ in _split_runs(pts, mask)]

    if isinstance(shape, Polygon):
        pts = _sample_polygon(shape.points, shape.closed, 14)
        mask = [math.hypot(x - cx, y - cy) > radius for (x, y) in pts]
        if all(mask):
            return [shape]
        return [Polygon(run, color=shape.color, width=shape.width, closed=False, filled=False)
                for run, _, _ in _split_runs(pts, mask)]

    if isinstance(shape, BezierStroke):
        pts = _sample_bezier_stroke(shape.segments, 16)
        mask = [math.hypot(x - cx, y - cy) > radius for (x, y) in pts]
        if all(mask):
            return [shape]
        widths = getattr(shape, "widths", None)
        sample_w = None
        if widths and len(widths) == len(shape.segments) + 1:
            sample_w = _sample_stroke_widths(widths, len(shape.segments), 16)
        out = []
        for run, start_i, end_i in _split_runs(pts, mask):
            segs = fit_curve(run, max_error=2.0)
            if sample_w is not None:
                frag_w = sum(sample_w[start_i:end_i + 1]) / max(end_i - start_i + 1, 1)
            else:
                frag_w = shape.width
            out.append(BezierStroke(segs, color=shape.color, width=frag_w, closed=False, filled=False))
        return out

    return None
