"""
shapes.py
Modele de donnees des objets geometriques dessines.
Chaque forme sait se serialiser (to_dict/from_dict) et s'auto-dessiner sur un QPainter.

v4 : BezierStroke supporte une epaisseur variable par noeud (`widths`),
alimentee par la pression du stylet de la tablette graphique.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Optional
import json

Point = Tuple[float, float]

LINE_STYLES = ("solid", "dashed", "dotted")


class _LineStyleMixin:
    """
    Shared solid/dashed/dotted stroke style, usable on ANY shape (not just
    Line/Arrow) so a hand-drawn closed curve, polygon, or circle can be
    marked dashed/dotted too -- e.g. the hidden 'waist' curve of a torus.
    `dashed` is kept as a legacy bool alias of `line_style` for backward
    compatibility with older project files and other modules.
    """

    def _init_line_style(self, dashed: bool, line_style: Optional[str]):
        self._line_style = line_style if line_style in LINE_STYLES else ("dashed" if dashed else "solid")

    @property
    def line_style(self) -> str:
        return self._line_style

    @line_style.setter
    def line_style(self, value: str):
        self._line_style = value if value in LINE_STYLES else "solid"

    @property
    def dashed(self) -> bool:
        return self._line_style == "dashed"

    @dashed.setter
    def dashed(self, value: bool):
        self._line_style = "dashed" if value else ("solid" if self._line_style == "dashed" else self._line_style)


class Shape:
    """Classe de base. type_name doit etre redefini."""
    type_name = "shape"

    def __init__(self, color: str = "#000000", width: float = 2.0):
        self.color = color
        self.width = width
        self.selected = False

    # -- a redefinir --
    def bbox(self):
        raise NotImplementedError

    def translate(self, dx: float, dy: float):
        raise NotImplementedError

    def to_dict(self) -> dict:
        raise NotImplementedError

    @staticmethod
    def from_dict(d: dict) -> "Shape":
        cls_map = {
            "stroke": BezierStroke,
            "line": Line,
            "ellipse": Ellipse,
            "arrow": Arrow,
            "text": TextLabel,
            "polygon": Polygon,
        }
        return cls_map[d["type"]].from_dict(d)


class BezierStroke(_LineStyleMixin, Shape):
    """
    Trait lisse compose d'une suite de segments de Bezier cubiques.
    segments: liste de (P0, C1, C2, P3).
    widths (optionnel): epaisseur du trait a chaque noeud (longueur =
    len(segments)+1) -- epaisseur variable pilotee par la pression du stylet.
    Si None, l'epaisseur constante `width` est utilisee.
    IMPORTANT : quand le trait est dashed/dotted, `widths` est ignore au
    rendu ET a l'export (render.py / tikz_export.py) -- un trait pointille a
    epaisseur variable produirait des tirets de tailles/espacements
    incoherents (chaque segment de Bezier redemarre son propre motif). Un
    trait dashed/dotted est donc toujours trace a epaisseur CONSTANTE, en un
    seul chemin continu, ce qui garantit des tirets parfaitement reguliers
    -- meme distance, meme taille -- a l'ecran comme dans le TikZ exporte.
    filled/fill_color : permet de refermer et remplir le trait.
    """
    type_name = "stroke"

    def __init__(self, segments: List[Tuple[Point, Point, Point, Point]],
                 color: str = "#000000", width: float = 2.0, closed: bool = False,
                 filled: bool = False, fill_color: Optional[str] = None, dashed: bool = False,
                 widths: Optional[List[float]] = None, line_style: Optional[str] = None):
        super().__init__(color, width)
        self.segments = segments
        self.closed = closed
        self.filled = filled
        self.fill_color = fill_color
        self._init_line_style(dashed, line_style)
        # sanity: widths must match the node count, otherwise ignore them
        if widths is not None and len(widths) != len(segments) + 1:
            widths = None
        self.widths = widths

    def max_width(self) -> float:
        return max(self.widths) if self.widths else self.width

    def bbox(self):
        xs, ys = [], []
        for seg in self.segments:
            for (x, y) in seg:
                xs.append(x)
                ys.append(y)
        return min(xs), min(ys), max(xs), max(ys)

    def translate(self, dx, dy):
        self.segments = [
            tuple((x + dx, y + dy) for (x, y) in seg) for seg in self.segments
        ]

    def to_dict(self):
        return {
            "type": self.type_name,
            "segments": self.segments,
            "color": self.color,
            "width": self.width,
            "closed": self.closed,
            "filled": self.filled,
            "fill_color": self.fill_color,
            "dashed": self.dashed,
            "line_style": self.line_style,
            "widths": self.widths,
        }

    @staticmethod
    def from_dict(d):
        segs = [tuple(tuple(pt) for pt in seg) for seg in d["segments"]]
        widths = d.get("widths")
        if widths is not None:
            widths = [float(w) for w in widths]
        return BezierStroke(segs, d.get("color", "#000000"), d.get("width", 2.0),
                             d.get("closed", False), d.get("filled", False),
                             d.get("fill_color"), d.get("dashed", False),
                             widths=widths, line_style=d.get("line_style"))


HEAD_STYLES = ("stealth", "classical", "harpoon", "none")


class Line(_LineStyleMixin, Shape):
    """
    v4.4: Quiver-style edge controls.
    - bend: curvature in [-1, 1] (0 = straight; the edge is drawn as a
      quadratic Bezier P0 -> Q -> P1 with Q offset sideways -- see
      edge_geom.py). Positive bends to the left of the P0->P1 direction.
    - line_style: "solid" / "dashed" / "dotted" (see _LineStyleMixin).
    - double: draws two thin parallel strokes instead of one (mono/faithful
      arrow style), like Quiver's double-line edge option.
    - head_style (v4.12, Arrow only in practice): "stealth" (filled Stealth
      tip, the default) / "classical" (plain LaTeX-style open V) / "harpoon"
      (single barb, one-sided) / "none" (no arrowhead at all -- an Arrow
      that reads as a plain line) -- Quiver's arrowhead-style picker.
    """
    type_name = "line"

    def __init__(self, p0: Point, p1: Point, color="#000000", width=2.0, dashed=False,
                 bend: float = 0.0, line_style: str = None, double: bool = False,
                 head_style: str = "stealth"):
        super().__init__(color, width)
        self.p0 = p0
        self.p1 = p1
        self.bend = float(max(-1.0, min(1.0, bend)))
        self.double = bool(double)
        self.head_style = head_style if head_style in HEAD_STYLES else "stealth"
        self._init_line_style(dashed, line_style)

    def bbox(self):
        return min(self.p0[0], self.p1[0]), min(self.p0[1], self.p1[1]), \
               max(self.p0[0], self.p1[0]), max(self.p0[1], self.p1[1])

    def translate(self, dx, dy):
        self.p0 = (self.p0[0] + dx, self.p0[1] + dy)
        self.p1 = (self.p1[0] + dx, self.p1[1] + dy)

    def reverse(self):
        self.p0, self.p1 = self.p1, self.p0
        self.bend = -self.bend  # keep the visual arc on the same side

    def to_dict(self):
        return {"type": self.type_name, "p0": self.p0, "p1": self.p1,
                "color": self.color, "width": self.width, "dashed": self.dashed,
                "bend": self.bend, "line_style": self.line_style, "double": self.double,
                "head_style": self.head_style}

    @staticmethod
    def from_dict(d):
        return Line(tuple(d["p0"]), tuple(d["p1"]), d.get("color", "#000000"),
                    d.get("width", 2.0), d.get("dashed", False),
                    d.get("bend", 0.0), d.get("line_style"), d.get("double", False),
                    d.get("head_style", "stealth"))


class Arrow(Line):
    type_name = "arrow"

    def to_dict(self):
        d = super().to_dict()
        d["type"] = self.type_name
        return d

    @staticmethod
    def from_dict(d):
        return Arrow(tuple(d["p0"]), tuple(d["p1"]), d.get("color", "#000000"),
                     d.get("width", 2.0), d.get("dashed", False),
                     d.get("bend", 0.0), d.get("line_style"), d.get("double", False),
                     d.get("head_style", "stealth"))


class Ellipse(_LineStyleMixin, Shape):
    type_name = "ellipse"

    def __init__(self, cx: float, cy: float, rx: float, ry: float,
                 color="#000000", width=2.0, filled=False, fill_color: Optional[str] = None,
                 dashed: bool = False, line_style: Optional[str] = None):
        super().__init__(color, width)
        self.cx, self.cy, self.rx, self.ry = cx, cy, rx, ry
        self.filled = filled
        self.fill_color = fill_color
        self._init_line_style(dashed, line_style)

    def bbox(self):
        return self.cx - self.rx, self.cy - self.ry, self.cx + self.rx, self.cy + self.ry

    def translate(self, dx, dy):
        self.cx += dx
        self.cy += dy

    def to_dict(self):
        return {"type": self.type_name, "cx": self.cx, "cy": self.cy,
                "rx": self.rx, "ry": self.ry, "color": self.color,
                "width": self.width, "filled": self.filled, "fill_color": self.fill_color,
                "dashed": self.dashed, "line_style": self.line_style}

    @staticmethod
    def from_dict(d):
        return Ellipse(d["cx"], d["cy"], d["rx"], d["ry"], d.get("color", "#000000"),
                       d.get("width", 2.0), d.get("filled", False), d.get("fill_color"),
                       d.get("dashed", False), d.get("line_style"))


class Polygon(_LineStyleMixin, Shape):
    type_name = "polygon"

    def __init__(self, points: List[Point], color="#000000", width=2.0, filled=False,
                 closed=True, fill_color: Optional[str] = None, dashed: bool = False,
                 line_style: Optional[str] = None):
        super().__init__(color, width)
        self.points = points
        self.filled = filled
        self.closed = closed
        self.fill_color = fill_color
        self._init_line_style(dashed, line_style)

    def bbox(self):
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def translate(self, dx, dy):
        self.points = [(x + dx, y + dy) for (x, y) in self.points]

    def to_dict(self):
        return {"type": self.type_name, "points": self.points, "color": self.color,
                "width": self.width, "filled": self.filled, "closed": self.closed,
                "fill_color": self.fill_color, "dashed": self.dashed, "line_style": self.line_style}

    @staticmethod
    def from_dict(d):
        return Polygon([tuple(p) for p in d["points"]], d.get("color", "#000000"),
                       d.get("width", 2.0), d.get("filled", False), d.get("closed", True),
                       d.get("fill_color"), d.get("dashed", False), d.get("line_style"))


class TextLabel(Shape):
    type_name = "text"

    def __init__(self, x: float, y: float, text: str, latex: bool = True,
                 color="#000000", fontsize: int = 12):
        super().__init__(color, 1.0)
        self.x, self.y, self.text, self.latex, self.fontsize = x, y, text, latex, fontsize

    def bbox(self):
        w = max(20, 8 * len(self.text))
        return self.x, self.y - 10, self.x + w, self.y + 10

    def translate(self, dx, dy):
        self.x += dx
        self.y += dy

    def to_dict(self):
        return {"type": self.type_name, "x": self.x, "y": self.y, "text": self.text,
                "latex": self.latex, "color": self.color, "fontsize": self.fontsize}

    @staticmethod
    def from_dict(d):
        return TextLabel(d["x"], d["y"], d["text"], d.get("latex", True),
                         d.get("color", "#000000"), d.get("fontsize", 12))


def save_project(shapes: List[Shape], path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([s.to_dict() for s in shapes], f, indent=2, ensure_ascii=False)


def load_project(path: str) -> List[Shape]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Shape.from_dict(d) for d in data]
