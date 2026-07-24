"""
smoothing.py
"Finition automatique" : nettoie un trait a main levee (jitter du poignet,
petites cassures, epaisseur irreguliere du contour) AVANT de le vectoriser,
meme quand ce n'est ni une ligne, ni un cercle, ni un polygone net — le cas
d'un contour organique ferme (silhouette de surface, anse/lentille...) comme
sur tes schemas de topologie.

Principe (classique, deterministe, pas de reseau de neurones) :
1. Reechantillonnage a pas curviligne constant (elimine les zones ou le
   stylet a ralenti/accelere, source de jitter).
2. Lissage circulaire (moyenne glissante ponderee, plusieurs passes) qui
   attenue les petites irregularites sans deformer la forme generale.
3. Pour un contour FERME : lissage periodique (le debut et la fin du trait
   sont recollees proprement, plus de "decalage" au point de fermeture).
"""
from __future__ import annotations
import numpy as np


def _cumulative_length(pts):
    d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(d)])


def resample_open(pts: np.ndarray, n: int) -> np.ndarray:
    if len(pts) < 2:
        return pts
    s = _cumulative_length(pts)
    total = s[-1]
    if total < 1e-6:
        return pts
    targets = np.linspace(0, total, n)
    out = np.empty((n, 2))
    out[:, 0] = np.interp(targets, s, pts[:, 0])
    out[:, 1] = np.interp(targets, s, pts[:, 1])
    return out


def resample_closed(pts: np.ndarray, n: int) -> np.ndarray:
    if len(pts) < 3:
        return pts
    if np.linalg.norm(pts[0] - pts[-1]) > 1e-6:
        pts = np.vstack([pts, pts[0]])
    return resample_open(pts, n + 1)[:-1]


def _smooth_periodic(pts: np.ndarray, iterations: int, kernel) -> np.ndarray:
    n = len(pts)
    half = len(kernel) // 2
    out = pts.copy()
    for _ in range(iterations):
        new = np.zeros_like(out)
        for i in range(n):
            acc = np.zeros(2)
            for k, w in enumerate(kernel):
                idx = (i + k - half) % n
                acc += w * out[idx]
            new[i] = acc
        out = new
    return out


def _smooth_open(pts: np.ndarray, iterations: int, kernel) -> np.ndarray:
    n = len(pts)
    half = len(kernel) // 2
    out = pts.copy()
    for _ in range(iterations):
        new = out.copy()
        for i in range(half, n - half):
            acc = np.zeros(2)
            for k, w in enumerate(kernel):
                acc += w * out[i + k - half]
            new[i] = acc
        out = new
    return out


_KERNEL = np.array([1, 2, 4, 6, 4, 2, 1], dtype=float)
_KERNEL /= _KERNEL.sum()


def clean_stroke(points_xy, closed: bool, n_samples: int = 110, passes: int = 10):
    """
    "Finition automatique" generique : renvoie une liste de points (x,y)
    propres (jitter attenue, espacement regulier), prete a etre passee a
    curvefit.fit_curve() pour obtenir un beau contour lisse.
    """
    pts = np.array([(float(x), float(y)) for (x, y) in points_xy])
    if len(pts) < 4:
        return [tuple(p) for p in pts]

    if closed:
        rs = resample_closed(pts, n_samples)
        sm = _smooth_periodic(rs, passes, _KERNEL)
        return [tuple(p) for p in sm] + [tuple(sm[0])]
    else:
        rs = resample_open(pts, n_samples)
        sm = _smooth_open(rs, passes, _KERNEL)
        sm[0] = rs[0]
        sm[-1] = rs[-1]
        return [tuple(p) for p in sm]


def symmetrize_closed_curve(points_xy, strength: float = 0.7, n_samples: int = 160):
    """
    Forces a closed, roughly star-shaped outline (a hand-drawn blob, a
    genus-g silhouette, a lens/eye mark...) to become bilaterally symmetric
    about its principal axis — this is the single biggest visual tell that a
    diagram was drawn by hand rather than made "by a machine": real hand
    strokes are never quite symmetric.

    Method: express the boundary in polar coordinates around its centroid,
    r(theta); average r(theta) with r(reflected theta) about the PCA
    principal axis; rebuild the point cloud from the symmetrized radius.
    `strength` in [0, 1] controls how fully symmetry is enforced (1.0 =
    perfectly symmetric, 0.0 = unchanged). Correspondence-free: point order
    is preserved so the result can go straight into clean_stroke/fit_curve.
    """
    pts = np.array([(float(x), float(y)) for (x, y) in points_xy])
    if len(pts) < 8:
        return [tuple(p) for p in pts]

    center = pts.mean(axis=0)
    centered = pts - center
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    axis_angle = float(np.arctan2(vt[0, 1], vt[0, 0]))

    theta = np.arctan2(centered[:, 1], centered[:, 0])
    r = np.hypot(centered[:, 0], centered[:, 1])

    order = np.argsort(theta)
    theta_sorted, r_sorted = theta[order], r[order]
    theta_ext = np.concatenate([theta_sorted - 2 * np.pi, theta_sorted, theta_sorted + 2 * np.pi])
    r_ext = np.tile(r_sorted, 3)

    def r_at(angles):
        return np.interp(angles, theta_ext, r_ext)

    reflected_theta = 2 * axis_angle - theta
    r_reflected = r_at(reflected_theta)
    r_sym = r + strength * (0.5 * (r + r_reflected) - r)

    new_pts = np.column_stack([
        center[0] + r_sym * np.cos(theta),
        center[1] + r_sym * np.sin(theta),
    ])
    return [tuple(p) for p in new_pts]

