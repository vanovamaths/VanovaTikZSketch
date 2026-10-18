"""
shape_recognition.py
"Vectorisation auto" : reconnaissance geometrique classique (pas un reseau de
neurones — il n'y a pas d'acces internet/API IA dans cet environnement) qui
analyse un trait a main levee et le remplace, si la forme voulue est claire,
par un objet PARFAIT (ligne bien droite, cercle/ellipse exact, polygone a
angles nets). Sinon, on garde le lissage Bezier habituel (curvefit.py).

Methode : ajustement par moindres carres (droite via PCA, cercle via Kasa),
ajustement d'ellipse par boite englobante, simplification polygonale par
Douglas-Peucker. Standard, robuste, rapide (aucune dependance externe hormis
numpy).
"""
from __future__ import annotations
import numpy as np


def _bbox_diag(pts):
    x, y = pts[:, 0], pts[:, 1]
    return float(np.hypot(x.max() - x.min(), y.max() - y.min()))


def _fit_line(pts):
    mean = pts.mean(axis=0)
    centered = pts - mean
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    direction = vt[0]
    proj = centered @ direction
    residual = centered - np.outer(proj, direction)
    rms = float(np.sqrt(np.mean(np.sum(residual ** 2, axis=1))))
    p0 = mean + proj.min() * direction
    p1 = mean + proj.max() * direction
    return {"p0": tuple(p0), "p1": tuple(p1), "residual": rms}


def _fit_ellipse_bbox(pts):
    x, y = pts[:, 0], pts[:, 1]
    cx, cy = (x.max() + x.min()) / 2, (y.max() + y.min()) / 2
    rx, ry = max((x.max() - x.min()) / 2, 1e-6), max((y.max() - y.min()) / 2, 1e-6)
    val = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
    residual = float(np.sqrt(np.mean((val - 1.0) ** 2)) * (rx + ry) / 2)
    return {"cx": cx, "cy": cy, "rx": rx, "ry": ry, "residual": residual}


def _fit_circle_kasa(pts):
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([2 * x, 2 * y, np.ones_like(x)])
    b = x ** 2 + y ** 2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy, c = sol
    r2 = c + cx ** 2 + cy ** 2
    r = float(np.sqrt(max(r2, 1e-9)))
    dist = np.hypot(x - cx, y - cy)
    residual = float(np.mean(np.abs(dist - r)))
    return {"cx": float(cx), "cy": float(cy), "r": r, "residual": residual}


def rdp(points, epsilon):
    """Douglas-Peucker : simplifie une polyligne en gardant les angles nets.
    Version ITERATIVE (pile explicite) — un trait de tablette peut contenir
    plusieurs centaines/milliers de points, et la version recursive naive
    peut depasser la limite de recursion Python et planter l'application."""
    if len(points) < 3:
        return list(points)

    arr = np.asarray(points, dtype=float)
    n = len(arr)
    keep = np.zeros(n, dtype=bool)
    keep[0] = True
    keep[-1] = True

    stack = [(0, n - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        p0, p1 = arr[start], arr[end]
        line_vec = p1 - p0
        line_len = np.linalg.norm(line_vec)
        seg = arr[start + 1:end]
        if line_len < 1e-9:
            dists = np.linalg.norm(seg - p0, axis=1)
        else:
            cross = line_vec[0] * (seg[:, 1] - p0[1]) - line_vec[1] * (seg[:, 0] - p0[0])
            dists = np.abs(cross) / line_len
        if len(dists) == 0:
            continue
        local_idx = int(np.argmax(dists))
        max_dist = float(dists[local_idx])
        idx = start + 1 + local_idx
        if max_dist > epsilon:
            keep[idx] = True
            stack.append((start, idx))
            stack.append((idx, end))

    return [tuple(p) for p in arr[keep]]


def classify_stroke(points_xy, tol_ratio: float = 0.05):
    """
    Tente de reconnaitre une primitive parfaite dans un trait a main levee.
    Retourne un tuple decrivant la forme, ou None si aucune primitive nette
    n'est detectee (le trait reste alors une courbe Bezier lissee normale) :
      ("line", p0, p1)
      ("ellipse", cx, cy, rx, ry)
      ("polygon", [pts...])
    """
    pts = np.array([(float(x), float(y)) for (x, y) in points_xy])
    if len(pts) < 4:
        return None
    diag = _bbox_diag(pts)
    if diag < 1e-3:
        return None
    tol = tol_ratio * diag

    closed = float(np.hypot(pts[0, 0] - pts[-1, 0], pts[0, 1] - pts[-1, 1])) < tol * 1.5

    if not closed:
        line = _fit_line(pts)
        if line["residual"] < tol * 0.6:
            return ("line", line["p0"], line["p1"])
        return None

    # trait ferme : cercle, ellipse ou polygone
    circle = _fit_circle_kasa(pts)
    if circle["residual"] < tol * 0.5:
        return ("ellipse", circle["cx"], circle["cy"], circle["r"], circle["r"])

    ell = _fit_ellipse_bbox(pts)
    if ell["residual"] < tol * 0.6:
        return ("ellipse", ell["cx"], ell["cy"], ell["rx"], ell["ry"])

    # Epsilon volontairement resserre : on ne veut PAS qu'une silhouette
    # organique lisse (ex: contour a bosses d'une surface de genre g) soit
    # confondue avec un polygone. Un vrai polygone dessine a la main garde
    # des angles nets meme avec un epsilon serre.
    simplified = rdp([tuple(p) for p in pts], tol * 0.25)
    if simplified and simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    corners = simplified[:-1] if len(simplified) > 1 else simplified

    if 3 <= len(corners) <= 10 and _has_sharp_corners(corners) and _fits_polygon_edges(pts, corners, tol * 0.5):
        return ("polygon", corners)

    return None


def _has_sharp_corners(corners, min_angle_deg: float = 28.0) -> bool:
    """Vrai seulement si CHAQUE sommet marque un virage net (angle de deviation
    superieur au seuil) — rejette les polygones "plats" issus d'une simplification
    trop genereuse d'une courbe lisse."""
    n = len(corners)
    if n < 3:
        return False
    arr = np.array(corners)
    for i in range(n):
        prev = arr[(i - 1) % n]
        cur = arr[i]
        nxt = arr[(i + 1) % n]
        v1, v2 = cur - prev, nxt - cur
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 < 1e-6 or n2 < 1e-6:
            return False
        cos_a = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
        turn_deg = np.degrees(np.arccos(cos_a))
        if turn_deg < min_angle_deg:
            return False
    return True


def _fits_polygon_edges(pts, corners, tol) -> bool:
    """Verifie que TOUS les points originaux du trait restent proches des
    aretes droites du polygone simplifie (et pas seulement les sommets
    retenus par Douglas-Peucker) — rejette les courbes lisses approximees
    en gros par une simplification trop laxiste."""
    corners = np.array(corners)
    n = len(corners)
    max_dist = 0.0
    for p in pts:
        best = min(
            _point_segment_dist(p, corners[i], corners[(i + 1) % n])
            for i in range(n)
        )
        max_dist = max(max_dist, best)
    return max_dist < tol


def _point_segment_dist(p, a, b):
    p, a, b = np.array(p), np.array(a), np.array(b)
    ab = b - a
    denom = np.dot(ab, ab)
    if denom < 1e-9:
        return float(np.linalg.norm(p - a))
    t = np.clip(np.dot(p - a, ab) / denom, 0.0, 1.0)
    proj = a + t * ab
    return float(np.linalg.norm(p - proj))

