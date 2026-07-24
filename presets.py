"""
presets.py
Library of ready-made "preset" shapes/small diagrams, built from perfect
primitives (Ellipse/Polygon/BezierStroke), inserted centered on the canvas
and then repositioned with the Select tool. Includes typical topology/
geometry diagram templates (torus, handle, genus-2 surface) in the style of
hand-drawn topology sketches.
"""
from __future__ import annotations
import math
from typing import List
from shapes import Shape, Ellipse, Line, Arrow, Polygon, BezierStroke, TextLabel

PRESET_NAMES = [
    # basic Euclidean shapes
    "circle", "ellipse", "square", "rectangle", "triangle", "pentagon",
    "hexagon", "star", "rhombus", "trapezoid", "parallelogram", "sector",
    "annulus", "cross", "double_arrow", "right_angle_mark",
    # topology / degeneracy-locus marks
    "lens", "handle", "torus", "genus2_surface", "genus2_curves_tau_sigma",
    "cusp_mark", "mobius_strip", "klein_bottle",
    # charts / atlases
    "chart_single", "chart_atlas_two",
    # differential geometry objects
    "tangent_vector", "normal_vector", "vector_field",
    "fiber_bundle", "lie_groupoid", "commutative_square", "foliation",
]

PRESET_LABELS = {
    "circle": "Perfect circle",
    "ellipse": "Perfect ellipse",
    "square": "Square",
    "rectangle": "Perfect rectangle",
    "triangle": "Equilateral triangle",
    "pentagon": "Regular pentagon",
    "hexagon": "Regular hexagon",
    "star": "5-point star",
    "rhombus": "Rhombus / diamond",
    "trapezoid": "Trapezoid",
    "parallelogram": "Parallelogram",
    "sector": "Circular sector (pie slice)",
    "annulus": "Annulus (ring)",
    "cross": "Cross / plus mark",
    "double_arrow": "Double-headed arrow",
    "right_angle_mark": "Right-angle mark",
    "lens": "Lens / eye mark (Dj style)",
    "handle": "Handle (with hatch marks)",
    "torus": "Torus (meridian + longitude)",
    "genus2_surface": "Genus-2 surface (sketch)",
    "genus2_curves_tau_sigma": "Genus-2 surface with tau/sigma/tau1/tau2 curves",
    "cusp_mark": "Cusp / fold singularity mark",
    "mobius_strip": "Mobius strip (sketch)",
    "klein_bottle": "Klein bottle (sketch)",
    "chart_single": "Chart map (manifold, U, phi, tilde U)",
    "chart_atlas_two": "Atlas: two charts + transition map",
    "tangent_vector": "Tangent vector T_pM at a point",
    "normal_vector": "Normal vector at a point",
    "vector_field": "Vector field along a curve",
    "fiber_bundle": "Fiber bundle (E, pi, B, fiber F)",
    "lie_groupoid": "Lie groupoid (G rightrightarrows M)",
    "commutative_square": "Commutative diagram (square)",
    "foliation": "Foliation / symplectic leaves",
}


PRESET_DESCRIPTIONS = {
    "circle": "Cercle euclidien standard. Sert de base pour tout disque, "
        "boule 2D, ou point epaissi dans un diagramme.",
    "ellipse": "Ellipse standard -- utilisee comme base perspective d'un "
        "disque/cercle vu en 3D (ex. base d'un cylindre, section d'une "
        "surface de revolution).",
    "square": "Carre -- cellule de base d'un pavage, ou fondamental domain "
        "carre (ex. le carre [0,1]^2 dont on identifie les bords pour "
        "obtenir un tore).",
    "rectangle": "Rectangle -- domaine fondamental generique, boite "
        "englobante, ou support d'un graphique/axe.",
    "triangle": "Triangle equilateral -- simplexe standard en dimension 2 "
        "(2-simplexe), brique de base d'une triangulation/complexe simplicial.",
    "pentagon": "Pentagone regulier -- polygone fondamental pour certaines "
        "surfaces hyperboliques compactes (pavages du plan hyperbolique).",
    "hexagon": "Hexagone regulier -- cellule du pavage hexagonal du plan, "
        "domaine fondamental du reseau triangulaire/tore hexagonal.",
    "star": "Etoile a 5 branches -- marqueur decoratif ou point remarquable "
        "(ex. singularite, point critique) a mettre en evidence.",
    "rhombus": "Losange -- parallelogramme a cotes egaux ; cellule d'un "
        "reseau rhombique, ou domaine fondamental d'un tore oblique.",
    "trapezoid": "Trapeze -- utilise pour des projections/perspectives, ou "
        "comme domaine fondamental d'un feuilletage lineaire par morceaux.",
    "parallelogram": "Parallelogramme -- domaine fondamental typique d'un "
        "reseau Z^2 dans R^2 (le tore T^2 = R^2/Z^2 se represente ainsi).",
    "sector": "Secteur circulaire (part de tarte) -- portion d'angle donne "
        "d'un disque ; utile pour illustrer un angle, une carte en "
        "coordonnees polaires, ou une orbifold conique.",
    "annulus": "Anneau (deux cercles concentriques) -- exemple standard de "
        "surface de genre 0 a deux bords ; domaine fondamental d'un "
        "cylindre plat S^1 x [0,1].",
    "cross": "Croix -- repere/marqueur de point, ou symbole de "
        "transversalite entre deux courbes.",
    "double_arrow": "Fleche double -- notation pour une bijection ou un "
        "isomorphisme reciproque (A <-> B), ou pour indiquer une distance/"
        "mesure entre deux points.",
    "right_angle_mark": "Marque d'angle droit -- symbole standard pour "
        "indiquer l'orthogonalite entre deux segments/courbes dans une "
        "figure geometrique.",
    "lens": "Marque en 'lentille' (vesica) -- symbole utilise pour marquer "
        "un point de degenerescence D1 sur le lieu singulier D d'une "
        "structure de Poisson log-symplectique (classification a la Radko "
        "d'un feuilletage symplectique sur une surface orientable).",
    "handle": "Anse (handle) -- brique de base de la decomposition en anses "
        "d'une surface : coller une anse a une sphere fait monter le genre "
        "de 1 (utilise pour construire un tore, un genre-2, etc.).",
    "torus": "Tore (meridien + longitude) -- surface de genre 1, "
        "T^2 = S^1 x S^1. Les deux cercles dessines sont les generateurs "
        "standards \\alpha (meridien) et \\beta (longitude) de "
        "\\pi_1(T^2) = Z^2.",
    "genus2_surface": "Surface de genre 2 (bretzel a deux anses) -- exemple "
        "canonique de surface fermee orientable avec \\chi = -2 ; utilisee "
        "pour illustrer la classification des surfaces ou un espace de "
        "modules M_2.",
    "genus2_curves_tau_sigma": "Surface de genre 2 vue comme somme connexe "
        "de deux tores, avec ses courbes standards annotees : "
        "\\tau_1, \\tau_2 les meridiens (courbes non separantes) de chaque "
        "anse, \\sigma la courbe separante au niveau du 'cou' de la somme "
        "connexe (\\Sigma_2 = T^2 \\# T^2), et \\tau une courbe non "
        "separante passant par les deux anses. Utile pour illustrer une "
        "twist de Dehn ou un element du mapping class group Mod(\\Sigma_2).",
    "cusp_mark": "Marque de point de rebroussement (cusp/fold) -- symbole "
        "pour un point singulier ou deux branches d'une courbe se "
        "rencontrent tangentiellement (singularite de type cusp dans la "
        "theorie des singularites/catastrophes).",
    "mobius_strip": "Ruban de Mobius (schema) -- surface non-orientable a "
        "un bord et un seul cote, obtenue par un demi-tour dans "
        "l'identification d'un rectangle. Exemple de base de fibre non "
        "trivial (fibre en droites sur S^1).",
    "klein_bottle": "Bouteille de Klein (schema) -- surface fermee non "
        "orientable sans bord ; ne se plonge pas dans R^3 sans "
        "auto-intersection (le croisement dessine est une convention de "
        "projection 2D, la vraie construction demande la dimension 4).",
    "chart_single": "Carte locale (chart) -- ouvert U d'une variete M "
        "envoye par un homeomorphisme \\varphi sur un ouvert "
        "\\widetilde U de R^n : la brique de base de la definition d'une "
        "variete differentiable.",
    "chart_atlas_two": "Atlas a deux cartes -- deux ouverts U_1, U_2 qui se "
        "recouvrent, avec leurs cartes \\varphi_1, \\varphi_2 et "
        "l'application de changement de cartes (transition map) "
        "\\varphi_{12} = \\varphi_2 \\circ \\varphi_1^{-1}, qui doit etre "
        "un diffeomorphisme pour que l'atlas soit lisse.",
    "tangent_vector": "Vecteur tangent T_pM en un point p -- element de "
        "l'espace tangent, represente comme une fleche le long de la "
        "direction de deplacement infinitesimal d'une courbe passant "
        "par p.",
    "normal_vector": "Vecteur normal en un point -- vecteur orthogonal au "
        "plan/espace tangent en p, utilise pour orienter une hypersurface "
        "ou definir une courbure normale.",
    "vector_field": "Champ de vecteurs le long d'une courbe -- assignation "
        "lisse d'un vecteur tangent en chaque point ; utilise pour "
        "illustrer un flot, une equation differentielle, ou une section "
        "d'un fibre tangent.",
    "fiber_bundle": "Fibre (fiber bundle) -- espace total E, base B, "
        "projection \\pi : E -> B, et fibre type F = \\pi^{-1}(b). "
        "Structure centrale de la geometrie differentielle (fibre "
        "vectoriel, fibre principal, etc.).",
    "lie_groupoid": "Groupoide de Lie G \\rightrightarrows M -- deux "
        "varietes G (fleches/morphismes) et M (objets/unites) reliees par "
        "des submersions source s et but t, avec une multiplication "
        "partielle ; generalise a la fois un groupe de Lie (M = point) et "
        "une variete (G = M). Central en geometrie de Poisson (groupoides "
        "symplectiques).",
    "commutative_square": "Diagramme commutatif (carre) -- quatre objets "
        "A, B, C, D et quatre morphismes f, g, h, k tels que "
        "h \\circ f = k \\circ g, i.e. les deux chemins A -> D coincident. "
        "Notation standard en algebre/theorie des categories (style Quiver).",
    "foliation": "Feuilletage / feuilles symplectiques -- une variete de "
        "Poisson se decompose canoniquement en une union disjointe de "
        "sous-varietes symplectiques immergees, ses feuilles symplectiques "
        "(theoreme de decomposition de Weinstein) ; un feuilletage "
        "symplectique regulier correspond exactement a une structure de "
        "Poisson reguliere.",
}


def _regular_polygon(cx, cy, r, n, rotation=0.0):
    return [
        (cx + r * math.cos(rotation + 2 * math.pi * i / n),
         cy + r * math.sin(rotation + 2 * math.pi * i / n))
        for i in range(n)
    ]


def _catmull_rom_closed_bezier(anchors, tension=1.0):
    """Standard uniform Catmull-Rom -> cubic Bezier conversion for a CLOSED
    loop through the given anchor points: smooth, deterministic, no
    hand-tuning per shape needed. Used to build the organic "blob" outlines
    (manifold/chart region silhouettes) seen in topology textbook figures."""
    n = len(anchors)
    segments = []
    for i in range(n):
        p0 = anchors[(i - 1) % n]
        p1 = anchors[i % n]
        p2 = anchors[(i + 1) % n]
        p3 = anchors[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6 * tension, p1[1] + (p2[1] - p0[1]) / 6 * tension)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6 * tension, p2[1] - (p3[1] - p1[1]) / 6 * tension)
        segments.append((p1, c1, c2, p2))
    return segments


_DEFAULT_WOBBLE = [1.0, 0.84, 1.08, 0.88, 1.14, 0.8, 1.06, 0.92]


def _blob_segments(cx, cy, rx, ry, radius_factors=None, rotation=0.0):
    """An irregular but clean closed outline (an ellipse perturbed by a
    deterministic wobble pattern) -- the generic "blob" silhouette used for
    a manifold or a chart region U in textbook atlas diagrams."""
    factors = radius_factors or _DEFAULT_WOBBLE
    n = len(factors)
    anchors = [
        (cx + rx * f * math.cos(rotation + 2 * math.pi * i / n),
         cy + ry * f * math.sin(rotation + 2 * math.pi * i / n))
        for i, f in enumerate(factors)
    ]
    return _catmull_rom_closed_bezier(anchors)


def _small_loop_icon(cx, cy, s=1.0):
    """A tiny loop mark (like the little handle/genus doodle drawn inside a
    manifold's silhouette in atlas figures, hinting 'there's a handle here'
    without drawing the whole handle)."""
    segs = _blob_segments(cx, cy, 13 * s, 8 * s, radius_factors=[1.0, 0.35, 1.0, 0.35, 1.0, 0.35])
    return segs


def _star_points(cx, cy, r_out, r_in, n_points=5, rotation=-math.pi / 2):
    pts = []
    for i in range(n_points * 2):
        r = r_out if i % 2 == 0 else r_in
        ang = rotation + math.pi * i / n_points
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def _coord_axes(cx, cy, length, color, width):
    """A little R^n coordinate cross: one horizontal + one vertical arrow,
    as seen under every chart-image plane (~U, phi(U)...) in atlas figures."""
    return [
        Arrow((cx - length * 0.12, cy), (cx + length, cy), color=color, width=width * 0.75),
        Arrow((cx, cy + length * 0.12), (cx, cy - length), color=color, width=width * 0.75),
    ]


def build_preset(name: str, cx: float, cy: float, scale: float = 1.0,
                  color: str = "#000000", width: float = 2.5) -> List[Shape]:
    if name == "circle":
        r = 60 * scale
        return [Ellipse(cx, cy, r, r, color=color, width=width)]

    if name == "ellipse":
        return [Ellipse(cx, cy, 90 * scale, 55 * scale, color=color, width=width)]

    if name == "rectangle":
        w, h = 120 * scale, 80 * scale
        pts = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
               (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "triangle":
        pts = _regular_polygon(cx, cy, 70 * scale, 3, rotation=-math.pi / 2)
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "square":
        half = 55 * scale
        pts = [(cx - half, cy - half), (cx + half, cy - half),
               (cx + half, cy + half), (cx - half, cy + half)]
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "pentagon":
        pts = _regular_polygon(cx, cy, 70 * scale, 5, rotation=-math.pi / 2)
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "hexagon":
        pts = _regular_polygon(cx, cy, 70 * scale, 6)
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "star":
        pts = _star_points(cx, cy, 75 * scale, 30 * scale)
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "rhombus":
        s = scale
        pts = [(cx, cy - 70 * s), (cx + 45 * s, cy), (cx, cy + 70 * s), (cx - 45 * s, cy)]
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "trapezoid":
        s = scale
        pts = [(cx - 70 * s, cy + 40 * s), (cx + 70 * s, cy + 40 * s),
               (cx + 40 * s, cy - 40 * s), (cx - 40 * s, cy - 40 * s)]
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "parallelogram":
        s = scale
        pts = [(cx - 70 * s, cy + 35 * s), (cx + 40 * s, cy + 35 * s),
               (cx + 70 * s, cy - 35 * s), (cx - 40 * s, cy - 35 * s)]
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "sector":
        # A circular sector (pie slice): approximated by sampling the arc
        # densely with straight segments, which renders visually as a smooth
        # curved edge once drawn -- no separate "arc" primitive needed.
        s = scale
        r = 75 * s
        a0, a1 = math.radians(-35), math.radians(35)
        n = 24
        pts = [(cx, cy)] + [
            (cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)
        ]
        return [Polygon(pts, color=color, width=width, closed=True)]

    if name == "annulus":
        s = scale
        return [
            Ellipse(cx, cy, 70 * s, 70 * s, color=color, width=width),
            Ellipse(cx, cy, 35 * s, 35 * s, color=color, width=width),
        ]

    if name == "cross":
        s = scale
        return [
            Line((cx - 45 * s, cy), (cx + 45 * s, cy), color=color, width=width),
            Line((cx, cy - 45 * s), (cx, cy + 45 * s), color=color, width=width),
        ]

    if name == "double_arrow":
        s = scale
        p0, p1 = (cx - 75 * s, cy), (cx + 75 * s, cy)
        return [Arrow(p0, p1, color=color, width=width), Arrow(p1, p0, color=color, width=width)]

    if name == "right_angle_mark":
        s = scale
        size = 14 * s
        pts = [(cx, cy - size), (cx + size, cy - size), (cx + size, cy)]
        return [Polygon(pts, color=color, width=width * 0.7, closed=False)]

    if name == "lens":
        # A perfectly symmetric lens/vesica ("eye") mark, exactly the shape
        # used for D1, D2, D3-style degeneracy-locus markings on a Radko
        # surface diagram: two symmetric arcs meeting at two sharp tips.
        # Inserting this instead of freehand-drawing a tiny mark guarantees
        # a clean, machine-made look with zero hand-drawn wobble.
        a, b = 26 * scale, 9 * scale  # half-length, half-width
        k = 0.9  # arc bulge factor (bigger = rounder lens)
        top = BezierStroke(
            [((cx - a, cy), (cx - a * k, cy - b), (cx + a * k, cy - b), (cx + a, cy))],
            color=color, width=width)
        bottom = BezierStroke(
            [((cx - a, cy), (cx - a * k, cy + b), (cx + a * k, cy + b), (cx + a, cy))],
            color=color, width=width)
        return [top, bottom]

    if name == "handle":
        # a "handle" as seen in topology diagrams: a lens/eye shape sitting
        # on a segment, with a couple of small hatch marks for the handle.
        rx, ry = 45 * scale, 20 * scale
        top = BezierStroke(
            [((cx - rx, cy), (cx - rx * 0.4, cy - ry), (cx + rx * 0.4, cy - ry), (cx + rx, cy))],
            color=color, width=width)
        base = Line((cx - rx * 1.6, cy), (cx + rx * 1.6, cy), color=color, width=width)
        hatch1 = Line((cx - rx * 0.5, cy - 6 * scale), (cx - rx * 0.5, cy + 6 * scale), color=color, width=width * 0.7)
        hatch2 = Line((cx, cy - 6 * scale), (cx, cy + 6 * scale), color=color, width=width * 0.7)
        hatch3 = Line((cx + rx * 0.5, cy - 6 * scale), (cx + rx * 0.5, cy + 6 * scale), color=color, width=width * 0.7)
        return [base, top, hatch1, hatch2, hatch3]

    if name == "torus":
        outer = Ellipse(cx, cy, 100 * scale, 55 * scale, color=color, width=width)
        inner = Ellipse(cx, cy, 45 * scale, 22 * scale, color=color, width=width)
        meridian = Ellipse(cx, cy, 25 * scale, 55 * scale, color=color, width=width * 0.8)
        return [outer, inner, meridian]

    if name == "genus2_surface":
        # "peanut" silhouette (two humps) + two handles, in the style of
        # hand-drawn topology diagrams (see reference sketches).
        s = scale
        body = BezierStroke([
            ((cx - 160 * s, cy), (cx - 160 * s, cy - 70 * s), (cx - 90 * s, cy - 80 * s), (cx - 40 * s, cy - 55 * s)),
            ((cx - 40 * s, cy - 55 * s), (cx - 10 * s, cy - 40 * s), (cx + 10 * s, cy - 40 * s), (cx + 40 * s, cy - 55 * s)),
            ((cx + 40 * s, cy - 55 * s), (cx + 90 * s, cy - 80 * s), (cx + 160 * s, cy - 70 * s), (cx + 160 * s, cy)),
            ((cx + 160 * s, cy), (cx + 160 * s, cy + 70 * s), (cx + 90 * s, cy + 80 * s), (cx + 40 * s, cy + 55 * s)),
            ((cx + 40 * s, cy + 55 * s), (cx + 10 * s, cy + 40 * s), (cx - 10 * s, cy + 40 * s), (cx - 40 * s, cy + 55 * s)),
            ((cx - 40 * s, cy + 55 * s), (cx - 90 * s, cy + 80 * s), (cx - 160 * s, cy + 70 * s), (cx - 160 * s, cy)),
        ], color=color, width=width, closed=True)

        def handle(hx, hy):
            rx, ry = 30 * s, 14 * s
            top = BezierStroke(
                [((hx - rx, hy), (hx - rx * 0.4, hy - ry), (hx + rx * 0.4, hy - ry), (hx + rx, hy))],
                color=color, width=width)
            h1 = Line((hx - rx * 0.4, hy - 5 * s), (hx - rx * 0.4, hy + 5 * s), color=color, width=width * 0.7)
            h2 = Line((hx + rx * 0.4, hy - 5 * s), (hx + rx * 0.4, hy + 5 * s), color=color, width=width * 0.7)
            return [top, h1, h2]

        shapes = [body]
        shapes += handle(cx - 90 * s, cy - 20 * s)
        shapes += handle(cx + 90 * s, cy - 20 * s)
        return shapes

    if name == "genus2_curves_tau_sigma":
        # Same "peanut" genus-2 silhouette as genus2_surface, plus the
        # standard curves used when Sigma_2 is presented as the connect sum
        # of two tori T^2 # T^2: tau_1, tau_2 (the non-separating meridian
        # of each handle/torus summand) and sigma (the separating curve at
        # the "neck" of the connect sum). tau is drawn as a longer
        # non-separating curve threading through both handles -- the usual
        # extra generator shown alongside sigma/tau_1/tau_2 when discussing
        # a Dehn twist or a mapping-class-group element on Sigma_2.
        s = scale
        body = BezierStroke([
            ((cx - 160 * s, cy), (cx - 160 * s, cy - 70 * s), (cx - 90 * s, cy - 80 * s), (cx - 40 * s, cy - 55 * s)),
            ((cx - 40 * s, cy - 55 * s), (cx - 10 * s, cy - 40 * s), (cx + 10 * s, cy - 40 * s), (cx + 40 * s, cy - 55 * s)),
            ((cx + 40 * s, cy - 55 * s), (cx + 90 * s, cy - 80 * s), (cx + 160 * s, cy - 70 * s), (cx + 160 * s, cy)),
            ((cx + 160 * s, cy), (cx + 160 * s, cy + 70 * s), (cx + 90 * s, cy + 80 * s), (cx + 40 * s, cy + 55 * s)),
            ((cx + 40 * s, cy + 55 * s), (cx + 10 * s, cy + 40 * s), (cx - 10 * s, cy + 40 * s), (cx - 40 * s, cy + 55 * s)),
            ((cx - 40 * s, cy + 55 * s), (cx - 90 * s, cy + 80 * s), (cx - 160 * s, cy + 70 * s), (cx - 160 * s, cy)),
        ], color=color, width=width, closed=True)

        def handle(hx, hy):
            rx, ry = 30 * s, 14 * s
            top = BezierStroke(
                [((hx - rx, hy), (hx - rx * 0.4, hy - ry), (hx + rx * 0.4, hy - ry), (hx + rx, hy))],
                color=color, width=width)
            h1 = Line((hx - rx * 0.4, hy - 5 * s), (hx - rx * 0.4, hy + 5 * s), color=color, width=width * 0.7)
            h2 = Line((hx + rx * 0.4, hy - 5 * s), (hx + rx * 0.4, hy + 5 * s), color=color, width=width * 0.7)
            return [top, h1, h2]

        left_hx, left_hy = cx - 90 * s, cy - 20 * s
        right_hx, right_hy = cx + 90 * s, cy - 20 * s

        shapes = [body]
        shapes += handle(left_hx, left_hy)
        shapes += handle(right_hx, right_hy)

        # tau_1: meridian loop encircling the left handle
        tau1 = Ellipse(left_hx, left_hy - 2 * s, 20 * s, 34 * s, color=color, width=width * 0.85)
        # tau_2: meridian loop encircling the right handle
        tau2 = Ellipse(right_hx, right_hy - 2 * s, 20 * s, 34 * s, color=color, width=width * 0.85)
        # sigma: the separating curve at the neck of the connect sum --
        # a vertical loop pinching the surface between the two humps
        sigma = Ellipse(cx, cy, 14 * s, 70 * s, color=color, width=width * 0.85)
        # tau: a single non-separating curve threading through both handles
        tau = BezierStroke([
            ((cx - 90 * s, cy + 34 * s), (cx - 70 * s, cy + 60 * s), (cx - 20 * s, cy + 60 * s), (cx, cy + 34 * s)),
            ((cx, cy + 34 * s), (cx + 20 * s, cy + 8 * s), (cx + 70 * s, cy + 8 * s), (cx + 90 * s, cy + 34 * s)),
        ], color=color, width=width * 0.85, line_style="dashed")

        label_tau1 = TextLabel(left_hx, left_hy - 45 * s, r"$\tau_1$", color=color, latex=True)
        label_tau2 = TextLabel(right_hx, right_hy - 45 * s, r"$\tau_2$", color=color, latex=True)
        label_sigma = TextLabel(cx, cy - 90 * s, r"$\sigma$", color=color, latex=True)
        label_tau = TextLabel(cx, cy + 68 * s, r"$\tau$", color=color, latex=True)

        shapes += [tau1, tau2, sigma, tau, label_tau1, label_tau2, label_sigma, label_tau]
        return shapes

    if name == "cusp_mark":
        # A small pointed cusp/fold-singularity mark: two arcs meeting at a
        # sharp point, as seen at the fold lines of a degeneracy locus.
        s = scale
        left = BezierStroke(
            [((cx - 22 * s, cy - 22 * s), (cx - 14 * s, cy), (cx - 6 * s, cy + 14 * s), (cx, cy + 24 * s))],
            color=color, width=width)
        right = BezierStroke(
            [((cx, cy + 24 * s), (cx + 6 * s, cy + 14 * s), (cx + 14 * s, cy), (cx + 22 * s, cy - 22 * s))],
            color=color, width=width)
        return [left, right]

    if name == "mobius_strip":
        # Schematic (not a literal parametric embedding) of a Mobius band:
        # a twisted-loop outline, with an inner line marking where the
        # strip's two edges cross at the half-twist, plus small arrows
        # hinting at the orientation reversal -- the usual hand-sketch
        # convention for a Mobius strip in a topology paper.
        s = scale
        outer = BezierStroke(_blob_segments(cx, cy, 110 * s, 55 * s,
                                             radius_factors=[1.0, 0.95, 1.05, 0.9, 1.08, 0.92]),
                              color=color, width=width, closed=True)
        twist = BezierStroke(
            [((cx - 90 * s, cy - 12 * s), (cx - 30 * s, cy + 30 * s), (cx + 30 * s, cy - 30 * s), (cx + 90 * s, cy + 12 * s))],
            color=color, width=width * 0.9)
        arrow1 = Arrow((cx - 55 * s, cy - 2 * s), (cx - 40 * s, cy + 12 * s), color=color, width=width * 0.8)
        arrow2 = Arrow((cx + 55 * s, cy + 2 * s), (cx + 40 * s, cy - 12 * s), color=color, width=width * 0.8)
        return [outer, twist, arrow1, arrow2]

    if name == "klein_bottle":
        # Schematic Klein-bottle doodle: a bulb-shaped body with a neck that
        # bends around and re-enters the side of the bulb (drawn as a
        # visual crossing, the usual 2D-projection convention -- a true
        # embedding needs 4 dimensions).
        s = scale
        body = BezierStroke(_blob_segments(cx, cy + 25 * s, 55 * s, 80 * s,
                                            radius_factors=[1.0, 0.92, 1.06, 0.9, 1.1, 0.9, 1.06, 0.92]),
                             color=color, width=width, closed=True)
        neck_outer = BezierStroke([
            ((cx - 8 * s, cy - 55 * s), (cx + 45 * s, cy - 70 * s), (cx + 70 * s, cy - 30 * s), (cx + 45 * s, cy)),
            ((cx + 45 * s, cy), (cx + 20 * s, cy + 22 * s), (cx + 5 * s, cy + 10 * s), (cx + 12 * s, cy - 10 * s)),
        ], color=color, width=width)
        neck_inner = BezierStroke([
            ((cx + 6 * s, cy - 50 * s), (cx + 38 * s, cy - 60 * s), (cx + 55 * s, cy - 30 * s), (cx + 35 * s, cy - 5 * s)),
        ], color=color, width=width * 0.85)
        return [body, neck_outer, neck_inner]

    if name == "chart_single":
        # Standard "chart map" figure: a manifold M with a hint of genus
        # (small loop), a dashed sub-region U, an arrow phi to its image
        # tilde-U in a coordinate plane R^n. The classic single-chart
        # picture used to introduce local coordinates on a manifold.
        s = scale
        manifold_cx, manifold_cy = cx - 140 * s, cy

        shapes: List[Shape] = []
        shapes.append(BezierStroke(_blob_segments(manifold_cx, manifold_cy, 95 * s, 68 * s),
                                    color=color, width=width, closed=True))
        shapes.append(BezierStroke(_small_loop_icon(manifold_cx - 48 * s, manifold_cy - 26 * s, s),
                                    color=color, width=width * 0.8, closed=True))

        u_cx, u_cy = manifold_cx + 32 * s, manifold_cy + 6 * s
        shapes.append(BezierStroke(
            _blob_segments(u_cx, u_cy, 36 * s, 28 * s, radius_factors=[1.0, 0.9, 1.05, 0.85, 1.1, 0.95]),
            color=color, width=width * 0.85, closed=True, dashed=True))
        shapes.append(TextLabel(u_cx + 6 * s, u_cy - 40 * s, "U", color=color, fontsize=max(10, int(15 * s))))

        p0 = (u_cx + 40 * s, u_cy)
        p1 = (cx + 40 * s, cy)
        shapes.append(Arrow(p0, p1, color=color, width=width))
        shapes.append(TextLabel((p0[0] + p1[0]) / 2 - 6 * s, (p0[1] + p1[1]) / 2 - 20 * s,
                                 r"\varphi", color=color, fontsize=max(10, int(15 * s))))

        v_cx, v_cy = cx + 150 * s, cy
        shapes.append(BezierStroke(
            _blob_segments(v_cx, v_cy, 55 * s, 42 * s, radius_factors=[1.0, 0.92, 1.05, 0.9, 1.08, 0.95]),
            color=color, width=width, closed=True, dashed=True))
        shapes.append(TextLabel(v_cx + 8 * s, v_cy - 48 * s, r"\widetilde{U}",
                                 color=color, fontsize=max(10, int(15 * s))))
        shapes.extend(_coord_axes(v_cx - 10 * s, v_cy + 8 * s, 32 * s, color, width))
        return shapes

    if name == "chart_atlas_two":
        # Standard "two overlapping charts + transition map" atlas figure:
        # manifold X with a couple of genus hints, two overlapping dashed
        # regions U1/U2, arrows phi1/phi2 down to their coordinate images,
        # and the transition map phi_12 = phi2 o phi1^-1 between them.
        s = scale
        top_cy = cy - 95 * s
        bottom_cy = cy + 95 * s

        shapes: List[Shape] = []
        shapes.append(BezierStroke(
            _blob_segments(cx, top_cy, 175 * s, 62 * s,
                            radius_factors=[1.0, 0.9, 1.05, 0.85, 1.1, 0.9, 1.05, 0.88]),
            color=color, width=width, closed=True))
        shapes.append(BezierStroke(_small_loop_icon(cx - 150 * s, top_cy - 18 * s, s),
                                    color=color, width=width * 0.8, closed=True))
        shapes.append(BezierStroke(_small_loop_icon(cx + 155 * s, top_cy - 10 * s, s * 0.9),
                                    color=color, width=width * 0.8, closed=True))
        shapes.append(TextLabel(cx - 178 * s, top_cy - 70 * s, "X", color=color, fontsize=max(10, int(16 * s))))

        u1_cx, u1_cy = cx - 55 * s, top_cy
        u2_cx, u2_cy = cx + 30 * s, top_cy
        shapes.append(BezierStroke(
            _blob_segments(u1_cx, u1_cy, 52 * s, 36 * s, radius_factors=[1.0, 0.9, 1.06, 0.88, 1.1, 0.94]),
            color=color, width=width * 0.85, closed=True, dashed=True))
        shapes.append(TextLabel(u1_cx - 20 * s, u1_cy - 44 * s, "U_1", color=color, fontsize=max(10, int(14 * s))))
        shapes.append(BezierStroke(
            _blob_segments(u2_cx, u2_cy, 52 * s, 36 * s, radius_factors=[1.0, 0.92, 1.05, 0.9, 1.08, 0.95]),
            color=color, width=width * 0.85, closed=True, dashed=True))
        shapes.append(TextLabel(u2_cx + 30 * s, u2_cy - 44 * s, "U_2", color=color, fontsize=max(10, int(14 * s))))

        box1_cx, box2_cx = cx - 115 * s, cx + 115 * s
        shapes.append(Arrow((u1_cx - 5 * s, u1_cy + 32 * s), (box1_cx + 10 * s, bottom_cy - 42 * s),
                             color=color, width=width))
        shapes.append(TextLabel((u1_cx + box1_cx) / 2 - 30 * s, (u1_cy + bottom_cy) / 2 - 6 * s,
                                 r"\varphi_1", color=color, fontsize=max(10, int(14 * s))))
        shapes.append(Arrow((u2_cx + 5 * s, u2_cy + 32 * s), (box2_cx - 10 * s, bottom_cy - 42 * s),
                             color=color, width=width))
        shapes.append(TextLabel((u2_cx + box2_cx) / 2 + 30 * s, (u2_cy + bottom_cy) / 2 - 6 * s,
                                 r"\varphi_2", color=color, fontsize=max(10, int(14 * s))))

        shapes.extend(_coord_axes(box1_cx - 12 * s, bottom_cy + 10 * s, 60 * s, color, width))
        shapes.append(TextLabel(box1_cx - 22 * s, bottom_cy - 58 * s, r"\varphi_1(U_1)",
                                 color=color, fontsize=max(10, int(13 * s))))
        shapes.extend(_coord_axes(box2_cx - 12 * s, bottom_cy + 10 * s, 60 * s, color, width))
        shapes.append(TextLabel(box2_cx - 22 * s, bottom_cy - 58 * s, r"\varphi_2(U_2)",
                                 color=color, fontsize=max(10, int(13 * s))))

        shapes.append(Arrow((box1_cx + 48 * s, bottom_cy), (box2_cx - 48 * s, bottom_cy),
                             color=color, width=width))
        shapes.append(TextLabel((box1_cx + box2_cx) / 2 - 20 * s, bottom_cy - 18 * s,
                                 r"\varphi_{12}", color=color, fontsize=max(10, int(14 * s))))
        return shapes

    if name == "tangent_vector":
        # A generic curve/manifold slice with a point p, and the tangent
        # vector T_pM drawn as an arrow along the curve's direction at p.
        s = scale
        curve = BezierStroke(
            [((cx - 100 * s, cy + 35 * s), (cx - 40 * s, cy - 35 * s), (cx + 40 * s, cy - 15 * s), (cx + 100 * s, cy + 30 * s))],
            color=color, width=width)
        p = (cx - 2 * s, cy - 22 * s)
        dot = Ellipse(p[0], p[1], 3.5 * s, 3.5 * s, color=color, width=width, filled=True, fill_color=color)
        arrow = Arrow(p, (p[0] + 60 * s, p[1] + 8 * s), color=color, width=width)
        label_p = TextLabel(p[0] - 14 * s, p[1] + 14 * s, "p", color=color, fontsize=max(10, int(14 * s)))
        label_v = TextLabel(p[0] + 66 * s, p[1] + 4 * s, "T_pM", color=color, fontsize=max(10, int(14 * s)))
        return [curve, dot, arrow, label_p, label_v]

    if name == "normal_vector":
        # Same generic curve + point p, but with the NORMAL vector (arrow
        # perpendicular to the tangent) drawn instead.
        s = scale
        curve = BezierStroke(
            [((cx - 100 * s, cy + 35 * s), (cx - 40 * s, cy - 35 * s), (cx + 40 * s, cy - 15 * s), (cx + 100 * s, cy + 30 * s))],
            color=color, width=width)
        p = (cx - 2 * s, cy - 22 * s)
        dot = Ellipse(p[0], p[1], 3.5 * s, 3.5 * s, color=color, width=width, filled=True, fill_color=color)
        # tangent direction ~ (60, 8) at p -> perpendicular is ~ (-8, 60)
        arrow = Arrow(p, (p[0] - 10 * s, p[1] - 55 * s), color=color, width=width)
        label_p = TextLabel(p[0] - 14 * s, p[1] + 14 * s, "p", color=color, fontsize=max(10, int(14 * s)))
        label_n = TextLabel(p[0] - 26 * s, p[1] - 62 * s, "n", color=color, fontsize=max(10, int(14 * s)))
        return [curve, dot, arrow, label_p, label_n]

    if name == "vector_field":
        # A curve with several small arrows attached at intervals, the
        # standard way to sketch a vector field along a 1-manifold.
        s = scale
        curve = BezierStroke(
            [((cx - 140 * s, cy), (cx - 60 * s, cy - 25 * s), (cx + 60 * s, cy + 25 * s), (cx + 140 * s, cy))],
            color=color, width=width)
        shapes: List[Shape] = [curve]
        offsets = [-120, -65, -5, 55, 115]
        directions = [(-25, -40), (10, -45), (30, -35), (10, -45), (-15, -40)]
        for ox, (dx, dy) in zip(offsets, directions):
            px, py = cx + ox * s, cy
            shapes.append(Arrow((px, py), (px + dx * s * 0.5, py + dy * s * 0.5), color=color, width=width * 0.85))
        return shapes

    if name == "fiber_bundle":
        # Classic fiber-bundle sketch: total space E (blob) projecting via
        # pi down onto the base B (line), with several fibers and one
        # highlighted fiber F.
        s = scale
        e_cx, e_cy = cx, cy - 60 * s
        b_y = cy + 90 * s
        e_blob = BezierStroke(_blob_segments(e_cx, e_cy, 115 * s, 45 * s,
                                              radius_factors=[1.0, 0.92, 1.06, 0.9, 1.08, 0.94]),
                               color=color, width=width, closed=True)
        e_label = TextLabel(e_cx - 130 * s, e_cy - 55 * s, "E", color=color, fontsize=max(10, int(16 * s)))
        base_line = Line((cx - 100 * s, b_y), (cx + 100 * s, b_y), color=color, width=width)
        b_label = TextLabel(cx + 108 * s, b_y, "B", color=color, fontsize=max(10, int(16 * s)))
        shapes = [e_blob, e_label, base_line, b_label]
        for fx in (-70, -20, 60):
            shapes.append(Line((cx + fx * s, e_cy + 25 * s), (cx + fx * s, b_y - 3 * s),
                                color=color, width=width * 0.7))
        shapes.append(Line((cx + 20 * s, e_cy - 40 * s), (cx + 20 * s, b_y - 3 * s), color=color, width=width * 1.2))
        shapes.append(TextLabel(cx + 28 * s, e_cy - 48 * s, "F", color=color, fontsize=max(10, int(14 * s))))
        pi_arrow = Arrow((cx - 20 * s, e_cy + 30 * s), (cx - 20 * s, b_y - 10 * s), color=color, width=width)
        shapes.append(pi_arrow)
        shapes.append(TextLabel(cx - 40 * s, (e_cy + b_y) / 2, r"\pi", color=color, fontsize=max(10, int(14 * s))))
        return shapes

    if name == "lie_groupoid":
        # G rightrightarrows M: a Lie groupoid's arrows manifold G on top,
        # units/objects manifold M on the bottom, with source (s) and
        # target (t) arrows between them.
        s = scale
        g_cx, g_cy = cx, cy - 75 * s
        m_cx, m_cy = cx, cy + 75 * s
        g_shape = Ellipse(g_cx, g_cy, 90 * s, 35 * s, color=color, width=width)
        m_shape = Ellipse(m_cx, m_cy, 90 * s, 30 * s, color=color, width=width)
        g_label = TextLabel(g_cx - 108 * s, g_cy, "G", color=color, fontsize=max(10, int(16 * s)))
        m_label = TextLabel(m_cx - 108 * s, m_cy, "M", color=color, fontsize=max(10, int(16 * s)))
        s_arrow = Arrow((g_cx - 25 * s, g_cy + 30 * s), (m_cx - 25 * s, m_cy - 26 * s), color=color, width=width)
        t_arrow = Arrow((g_cx + 25 * s, g_cy + 30 * s), (m_cx + 25 * s, m_cy - 26 * s), color=color, width=width)
        s_label = TextLabel(g_cx - 50 * s, (g_cy + m_cy) / 2, "s", color=color, fontsize=max(10, int(14 * s)))
        t_label = TextLabel(g_cx + 42 * s, (g_cy + m_cy) / 2, "t", color=color, fontsize=max(10, int(14 * s)))
        return [g_shape, m_shape, g_label, m_label, s_arrow, t_arrow, s_label, t_label]

    if name == "commutative_square":
        # A commutative diagram: 4 objects at the corners of a square, 4
        # arrows f, g, h, k with A -> B -> D and A -> C -> D commuting.
        s = scale
        A = (cx - 75 * s, cy - 75 * s)
        B = (cx + 75 * s, cy - 75 * s)
        C = (cx - 75 * s, cy + 75 * s)
        D = (cx + 75 * s, cy + 75 * s)
        fs = max(10, int(15 * s))
        shapes = [
            TextLabel(A[0] - 14 * s, A[1] - 10 * s, "A", color=color, fontsize=fs),
            TextLabel(B[0] + 6 * s, B[1] - 10 * s, "B", color=color, fontsize=fs),
            TextLabel(C[0] - 14 * s, C[1] + 6 * s, "C", color=color, fontsize=fs),
            TextLabel(D[0] + 6 * s, D[1] + 6 * s, "D", color=color, fontsize=fs),
            Arrow((A[0] + 14 * s, A[1]), (B[0] - 14 * s, B[1]), color=color, width=width),
            Arrow((A[0], A[1] + 14 * s), (C[0], C[1] - 14 * s), color=color, width=width),
            Arrow((B[0], B[1] + 14 * s), (D[0], D[1] - 14 * s), color=color, width=width),
            Arrow((C[0] + 14 * s, C[1]), (D[0] - 14 * s, D[1]), color=color, width=width),
            TextLabel((A[0] + B[0]) / 2 - 6 * s, A[1] - 16 * s, "f", color=color, fontsize=fs),
            TextLabel(A[0] - 20 * s, (A[1] + C[1]) / 2, "g", color=color, fontsize=fs),
            TextLabel(D[0] + 10 * s, (B[1] + D[1]) / 2, "h", color=color, fontsize=fs),
            TextLabel((C[0] + D[0]) / 2 - 6 * s, D[1] + 14 * s, "k", color=color, fontsize=fs),
        ]
        return shapes

    if name == "foliation":
        # A stack of parallel wavy leaves -- the standard sketch for a
        # foliated manifold (or, in Poisson geometry, the symplectic
        # leaves of a Poisson structure).
        s = scale
        shapes: List[Shape] = []
        for i, dy in enumerate((-70, -35, 0, 35, 70)):
            wob = 18 * s * (1 if i % 2 == 0 else -1) * 0.6
            leaf = BezierStroke([
                ((cx - 130 * s, cy + dy * s), (cx - 45 * s, cy + dy * s - wob),
                 (cx + 45 * s, cy + dy * s + wob), (cx + 130 * s, cy + dy * s)),
            ], color=color, width=width * (1.3 if i == 2 else 0.85))
            shapes.append(leaf)
        return shapes

    return []

