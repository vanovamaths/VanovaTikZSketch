
from __future__ import annotations
import math
from typing import List, Optional, Tuple

import numpy as np

from shapes import Shape, BezierStroke, Line, Arrow, Ellipse, Polygon, TextLabel
from erasing import _sample_line, _sample_polygon, _sample_bezier_stroke

PX_PER_CM = 60.0


def _sample_ellipse(cx, cy, rx, ry, n=240):
    return [(cx + rx * math.cos(t), cy + ry * math.sin(t))
            for t in np.linspace(0, 2 * math.pi, n)]


def shape_boundary_points(shape: Shape, n: int = 240) -> List[Tuple[float, float]]:
    """Dense polyline sample of a shape's outline, for any supported type."""
    if isinstance(shape, Ellipse):
        return _sample_ellipse(shape.cx, shape.cy, shape.rx, shape.ry, n)
    if isinstance(shape, BezierStroke):
        if not shape.segments:
            raise ValueError("empty stroke")
        per_seg = max(4, n // max(1, len(shape.segments)))
        return _sample_bezier_stroke(shape.segments, per_seg)
    if isinstance(shape, Polygon):
        per_edge = max(4, n // max(1, len(shape.points)))
        return _sample_polygon(shape.points, shape.closed, per_edge)
    if isinstance(shape, (Line, Arrow)):
        return _sample_line(shape.p0, shape.p1, max(2, n))
    raise ValueError(f"3D revolution isn't supported for {type(shape).__name__}")


def compute_revolution_profile(shape: Shape, n_profile: int = 40):
    """
    Returns (axis_x, heights[n_profile], radii[n_profile]): the shape's own
    vertical mid-axis, and the silhouette radius measured at each of
    n_profile evenly spaced height levels spanning the shape.
    """
    pts = np.array(shape_boundary_points(shape), dtype=float)
    xs, ys = pts[:, 0], pts[:, 1]
    axis_x = (xs.min() + xs.max()) / 2.0
    y0, y1 = float(ys.min()), float(ys.max())
    if y1 - y0 < 1e-6:
        y1 = y0 + 1.0

    heights = np.linspace(y0, y1, n_profile)
    band = max((y1 - y0) / n_profile, 1e-6) * 1.5
    radii = np.empty(n_profile)
    dist = np.abs(xs - axis_x)
    for i, h in enumerate(heights):
        mask = np.abs(ys - h) <= band
        if mask.any():
            radii[i] = max(dist[mask].max(), 1e-3)
        else:
            idx = int(np.argmin(np.abs(ys - h)))
            radii[i] = max(dist[idx], 1e-3)

    return axis_x, heights, radii


def revolve_to_mesh(shape: Shape, n_theta: int = 28, n_profile: int = 40,
                     px_per_cm: float = PX_PER_CM) -> List[List[Tuple[float, float, float]]]:
    """
    Builds the 3D surface-of-revolution mesh, in cm, centered on its own
    vertical axis: a list of n_profile "rows" (height levels), each a list
    of n_theta points (x, y, z) going around the axis once.
    """
    axis_x, heights, radii = compute_revolution_profile(shape, n_profile)
    y_mid = (heights[0] + heights[-1]) / 2.0
    thetas = np.linspace(0, 2 * math.pi, n_theta, endpoint=True)

    grid = []
    for h, r in zip(heights, radii):
        r_cm = r / px_per_cm
        z_cm = (y_mid - h) / px_per_cm  # screen y grows downward -> flip so "up" is up in 3D
        row = [(r_cm * math.cos(t), r_cm * math.sin(t), z_cm) for t in thetas]
        grid.append(row)
    return grid


def _color_name(hexcolor: str) -> str:
    return "gsColor" + hexcolor.lstrip("#").upper()


def mesh_to_pgfplots_body(grid, color_hex: str = "#000000", view: str = "{60}{20}") -> str:
    """
    The \\addplot3[surf] block (+ optional \\definecolor), ready to paste
    inside a tikzpicture/axis, or use mesh_to_standalone_tex for a full,
    directly-compilable .tex file.
    """
    lines = []
    color_hex = color_hex or "#000000"
    if color_hex.lower() != "#000000":
        name = _color_name(color_hex)
        lines.append(f"\\definecolor{{{name}}}{{HTML}}{{{color_hex.lstrip('#').upper()}}}")
        lines.append("")
        fill_color = f"{name}!45"
        draw_color = name
    else:
        fill_color = "gray!35"
        draw_color = "black"

    lines.append(f"\\begin{{axis}}[hide axis, axis equal image, view={view}]")
    lines.append(f"\\addplot3[surf, shader=faceted, mesh/rows={len(grid)}, "
                 f"color={fill_color}, faceted color={draw_color}] coordinates {{")
    for row in grid:
        lines.append(" ".join(f"({x:.4f},{y:.4f},{z:.4f})" for (x, y, z) in row))
        lines.append("")
    lines.append("};")
    lines.append("\\end{axis}")
    return "\n".join(lines)


STANDALONE_3D_TEMPLATE = r"""\documentclass[tikz,border=4pt]{{standalone}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.17}}
\begin{{document}}
\begin{{tikzpicture}}
{body}
\end{{tikzpicture}}
\end{{document}}
"""


def mesh_to_standalone_tex(grid, color_hex: str = "#000000") -> str:
    body = mesh_to_pgfplots_body(grid, color_hex)
    return STANDALONE_3D_TEMPLATE.format(body=body)

