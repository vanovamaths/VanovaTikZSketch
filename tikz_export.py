
from __future__ import annotations
from typing import List, Dict
from shapes import Shape, BezierStroke, Line, Arrow, Ellipse, Polygon, TextLabel
import edge_geom

PX_PER_CM = 60.0  # scale factor: 60 canvas px = 1 cm in the figure


def _to_tikz_coords(shapes: List[Shape], px_per_cm: float):
    """Builds the pixel -> cm transform (with y flip)."""
    ys = []
    for s in shapes:
        _, y0, _, y1 = s.bbox()
        ys.extend([y0, y1])
    height = max(ys) if ys else 0.0

    def conv(pt):
        x, y = pt
        return (round(x / px_per_cm, 3), round((height - y) / px_per_cm, 3))

    return conv


def _fmt(pt):
    return f"({pt[0]},{pt[1]})"


def _color_name(hexcolor: str) -> str:
    """Deterministic, LaTeX-safe macro name for a hex color, e.g. '#1e88e5' -> 'gsColor1E88E5'."""
    return "gsColor" + hexcolor.lstrip("#").upper()


def _collect_colors(shapes: List[Shape]) -> Dict[str, str]:
    """Every distinct non-black color actually used (stroke or fill) -> its TikZ color name."""
    color_map: Dict[str, str] = {}
    for s in shapes:
        for hexcolor in (getattr(s, "color", None), getattr(s, "fill_color", None)):
            if hexcolor and hexcolor.lower() != "#000000" and hexcolor not in color_map:
                color_map[hexcolor] = _color_name(hexcolor)
    return color_map


def _color_ref(hexcolor: str, color_map: Dict[str, str]) -> str:
    if not hexcolor or hexcolor.lower() == "#000000":
        return "black"
    return color_map[hexcolor]


def _definecolor_lines(color_map: Dict[str, str]) -> List[str]:
    return [f"\\definecolor{{{name}}}{{HTML}}{{{hexcolor.lstrip('#').upper()}}}"
            for hexcolor, name in color_map.items()]


def _bezier_path(s: BezierStroke, conv) -> str:
    p0 = conv(s.segments[0][0])
    path = f"({p0[0]},{p0[1]})"
    for (P0, C1, C2, P3) in s.segments:
        c1, c2, p3 = conv(C1), conv(C2), conv(P3)
        path += f"\n    .. controls {_fmt(c1)} and {_fmt(c2)} .. {_fmt(p3)}"
    return path


_TIKZ_STYLE = {"dashed": "dashed", "dotted": "dotted"}  # "solid" needs no extra key


def _edge_draw(p0, p1, bend, conv, style: str) -> str:
    """One \\draw command for a straight or curved (quadratic->cubic,
    Bezier-exact) edge from p0 to p1, already in canvas/px coordinates."""
    if bend:
        from edge_geom import control_point, quad_to_cubic
        q = control_point(p0, p1, bend)
        c1, c2 = quad_to_cubic(p0, q, p1)
        P0, C1, C2, P1 = conv(p0), conv(c1), conv(c2), conv(p1)
        path = f"{_fmt(P0)} .. controls {_fmt(C1)} and {_fmt(C2)} .. {_fmt(P1)}"
    else:
        P0, P1 = conv(p0), conv(p1)
        path = f"{_fmt(P0)} -- {_fmt(P1)}"
    return f"\\draw[{style}] {path};"


def _arrow_tip_token(head_style: str) -> str:
    """Quiver-style arrowhead picker -> TikZ arrow tip spec (arrows.meta).
    'classical' deliberately maps to plain '->' (TikZ's own default arrow,
    no arrows.meta tip name needed) so it always compiles even without the
    library loaded."""
    return {
        "stealth": "-{Stealth}",
        "harpoon": "-{Harpoon}",
        "none": "-",
    }.get(head_style, "->")


def _edge_lines(s, conv, color_cmd: str, arrow: bool) -> List[str]:
    tip = _arrow_tip_token(getattr(s, "head_style", "stealth")) if arrow else ""
    base_style = (f"{tip}, " if arrow else "") + color_cmd + f", line width={s.width/2:.2f}pt"
    extra = _TIKZ_STYLE.get(getattr(s, "line_style", "solid"))
    if extra:
        base_style += f", {extra}"
    bend = getattr(s, "bend", 0.0)
    if getattr(s, "double", False):
        gap = max(2.0, 0.9 * s.width + 1.2)
        thin_style = color_cmd + f", line width={max(0.3, s.width * 0.3):.2f}pt"
        if extra:
            thin_style += f", {extra}"
        lines = []
        for sign in (-1, 1):
            q0, q1 = edge_geom.parallel_endpoints(s.p0, s.p1, sign * gap)
            lines.append(_edge_draw(q0, q1, bend, conv, thin_style))
        if arrow:
            # single arrow head on the true (un-offset) centerline, drawn as
            # a short invisible-shaft, visible-head stub near p1
            tail = edge_geom.point_on_quad(0.92, s.p0, edge_geom.control_point(s.p0, s.p1, bend), s.p1) if bend \
                else (s.p0[0] + 0.92 * (s.p1[0] - s.p0[0]), s.p0[1] + 0.92 * (s.p1[1] - s.p0[1]))
            head_line_style = f"{tip}, " + color_cmd + f", line width={s.width/2:.2f}pt"
            lines.append(_edge_draw(tail, s.p1, 0.0, conv, head_line_style))
        return lines
    return [_edge_draw(s.p0, s.p1, bend, conv, base_style)]


def _bezier_variable_width_lines(s: BezierStroke, conv, color_map, px_per_cm) -> List[str]:
    """One \\draw per segment, each with its own line width; optional single
    fill pass first so the interior is painted exactly once."""
    out = []
    stroke_ref = _color_ref(s.color, color_map)
    if getattr(s, "filled", False):
        fill_ref = _color_ref(getattr(s, "fill_color", None) or s.color, color_map)
        out.append(f"\\fill[{fill_ref}] {_bezier_path(s, conv)} -- cycle;")
    w = s.widths
    dash = ", dashed" if getattr(s, "dashed", False) else ""
    for k, (P0, C1, C2, P3) in enumerate(s.segments):
        p0, c1, c2, p3 = conv(P0), conv(C1), conv(C2), conv(P3)
        lw = 0.5 * (w[k] + w[k + 1]) / 2.0  # same px->pt convention as constant case
        out.append(
            f"\\draw[draw={stroke_ref}, line width={lw:.2f}pt, line cap=round{dash}] "
            f"{_fmt(p0)} .. controls {_fmt(c1)} and {_fmt(c2)} .. {_fmt(p3)};"
        )
    if s.closed and s.segments:
        first, last = s.segments[0][0], s.segments[-1][3]
        if abs(first[0] - last[0]) > 1e-6 or abs(first[1] - last[1]) > 1e-6:
            lw = 0.5 * (w[0] + w[-1]) / 2.0
            out.append(
                f"\\draw[draw={stroke_ref}, line width={lw:.2f}pt, line cap=round{dash}] "
                f"{_fmt(conv(last))} -- {_fmt(conv(first))};"
            )
    return out


def shapes_to_tikz_body(shapes: List[Shape], px_per_cm: float = PX_PER_CM) -> str:
    conv = _to_tikz_coords(shapes, px_per_cm)
    color_map = _collect_colors(shapes)
    lines = list(_definecolor_lines(color_map))
    if lines:
        lines.append("")  # blank line between color defs and drawing commands

    for s in shapes:
        stroke_ref = _color_ref(s.color, color_map)
        color_cmd = f"draw={stroke_ref}"

        if isinstance(s, BezierStroke):
            if not s.segments:
                continue
            widths = getattr(s, "widths", None)
            line_style = getattr(s, "line_style", "solid")
            # Variable per-segment width is only exported when the stroke is
            # solid: a dashed/dotted variable-width curve would need N
            # separate \draw commands, each restarting its dash pattern at
            # the segment boundary -- uneven tick marks in the compiled PDF.
            # Dashed/dotted strokes are instead ALWAYS exported as a single
            # constant-width \draw (one continuous path), so TikZ applies
            # the dash pattern by arc length the whole way around -- exactly
            # matching the on-screen fix in render.py.
            if widths and len(widths) == len(s.segments) + 1 and line_style == "solid":
                lines.extend(_bezier_variable_width_lines(s, conv, color_map, px_per_cm))
                continue
            path = _bezier_path(s, conv)
            close = " -- cycle" if (s.closed or getattr(s, "filled", False)) else ""
            style = color_cmd + f", line width={s.width/2:.2f}pt"
            if getattr(s, "filled", False):
                fill_ref = _color_ref(getattr(s, "fill_color", None) or s.color, color_map)
                style += f", fill={fill_ref}"
            extra = _TIKZ_STYLE.get(line_style)
            if extra:
                style += f", {extra}"
            lines.append(f"\\draw[{style}] {path}{close};")

        elif isinstance(s, Arrow):
            lines.extend(_edge_lines(s, conv, color_cmd, arrow=True))

        elif isinstance(s, Line):
            lines.extend(_edge_lines(s, conv, color_cmd, arrow=False))

        elif isinstance(s, Ellipse):
            c = conv((s.cx, s.cy))
            rx = round(s.rx / px_per_cm, 3)
            ry = round(s.ry / px_per_cm, 3)
            style = color_cmd + f", line width={s.width/2:.2f}pt"
            if s.filled:
                fill_ref = _color_ref(s.fill_color or s.color, color_map)
                style += f", fill={fill_ref}"
            extra = _TIKZ_STYLE.get(getattr(s, "line_style", "solid"))
            if extra:
                style += f", {extra}"
            lines.append(f"\\draw[{style}] {_fmt(c)} ellipse ({rx} and {ry});")

        elif isinstance(s, Polygon):
            pts = [conv(p) for p in s.points]
            path = " -- ".join(_fmt(p) for p in pts)
            close = " -- cycle" if s.closed else ""
            style = color_cmd + f", line width={s.width/2:.2f}pt"
            if s.filled:
                fill_ref = _color_ref(s.fill_color or s.color, color_map)
                style += f", fill={fill_ref}"
            extra = _TIKZ_STYLE.get(getattr(s, "line_style", "solid"))
            if extra:
                style += f", {extra}"
            lines.append(f"\\draw[{style}] {path}{close};")

        elif isinstance(s, TextLabel):
            p = conv((s.x, s.y))
            text = s.text if s.latex else s.text.replace("_", r"\_").replace("&", r"\&")
            content = text if (text.startswith("$") or not s.latex) else f"${text}$"
            text_color = f"text={stroke_ref}, " if stroke_ref != "black" else ""
            lines.append(
                f"\\node[{text_color}font=\\fontsize{{{s.fontsize}}}{{{s.fontsize+2}}}\\selectfont] "
                f"at {_fmt(p)} {{{content}}};"
            )

    return "\n".join(lines)


STANDALONE_TEMPLATE = r"""\documentclass[tikz,border=4pt]{{standalone}}
\usepackage{{amsmath,amssymb}}
\usepackage{{xcolor}}
\usetikzlibrary{{arrows.meta}}
\begin{{document}}
\begin{{tikzpicture}}
{body}
\end{{tikzpicture}}
\end{{document}}
"""


def shapes_to_standalone_tex(shapes: List[Shape], px_per_cm: float = PX_PER_CM) -> str:
    body = shapes_to_tikz_body(shapes, px_per_cm)
    return STANDALONE_TEMPLATE.format(body=body)
