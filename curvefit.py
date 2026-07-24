
from __future__ import annotations
import numpy as np


def _chord_length_parameterize(points):
    u = [0.0]
    for i in range(1, len(points)):
        u.append(u[-1] + np.linalg.norm(points[i] - points[i - 1]))
    total = u[-1] if u[-1] > 1e-9 else 1.0
    return [ui / total for ui in u]


def _bezier(t, ctrl):
    mt = 1 - t
    return (mt ** 3) * ctrl[0] + 3 * (mt ** 2) * t * ctrl[1] + 3 * mt * (t ** 2) * ctrl[2] + (t ** 3) * ctrl[3]


def _bezier_deriv(t, ctrl):
    mt = 1 - t
    return 3 * (mt ** 2) * (ctrl[1] - ctrl[0]) + 6 * mt * t * (ctrl[2] - ctrl[1]) + 3 * (t ** 2) * (ctrl[3] - ctrl[2])


def _q(ctrl, t):
    return _bezier(t, ctrl)


def _reparameterize(points, u, ctrl):
    new_u = []
    for i, p in enumerate(points):
        new_u.append(_newton_raphson_root_find(ctrl, p, u[i]))
    return new_u


def _newton_raphson_root_find(ctrl, point, u):
    d = _q(ctrl, u) - point
    qp = _bezier_deriv(u, ctrl)
    qpp = 6 * (1 - u) * (ctrl[2] - 2 * ctrl[1] + ctrl[0]) + 6 * u * (ctrl[3] - 2 * ctrl[2] + ctrl[1])
    denom = np.dot(qp, qp) + np.dot(d, qpp)
    if abs(denom) < 1e-9:
        return u
    return u - np.dot(d, qp) / denom


def _generate_bezier(points, u, t_hat1, t_hat2):
    n = len(points)
    A = np.zeros((n, 2, 2))
    for i, t in enumerate(u):
        A[i][0] = t_hat1 * 3 * (1 - t) ** 2 * t
        A[i][1] = t_hat2 * 3 * (1 - t) * t ** 2

    C = np.zeros((2, 2))
    Xv = np.zeros(2)
    p0, p3 = points[0], points[-1]
    for i, t in enumerate(u):
        C[0][0] += np.dot(A[i][0], A[i][0])
        C[0][1] += np.dot(A[i][0], A[i][1])
        C[1][0] = C[0][1]
        C[1][1] += np.dot(A[i][1], A[i][1])
        base = _bezier(t, (p0, p0, p3, p3)) - points[i]
        Xv[0] -= np.dot(A[i][0], base)
        Xv[1] -= np.dot(A[i][1], base)

    det_C0C1 = C[0][0] * C[1][1] - C[1][0] * C[0][1]
    alpha_l = alpha_r = 0.0
    if abs(det_C0C1) > 1e-12:
        det_C0X = C[0][0] * Xv[1] - C[1][0] * Xv[0]
        det_XC1 = Xv[0] * C[1][1] - Xv[1] * C[0][1]
        alpha_l = det_XC1 / det_C0C1
        alpha_r = det_C0X / det_C0C1

    # seg_len (straight p0->p3 distance) degenerates to ~0 on a CLOSED curve's
    # very first fit attempt, since points[0] and points[-1] are (nearly) the
    # same point even though the arc between them is the whole loop. When
    # that happens the classic Schneider "too small -> fall back to seg_len/3"
    # guard never fires (eps collapses to ~0 too), so an ill-conditioned
    # linear system (near-singular det_C0C1) can hand back an enormous or
    # negative alpha and the control points shoot off far outside the
    # drawing's bounding box. Use the polyline's actual arc length as a
    # size reference instead, and clamp alpha on BOTH sides (too small AND
    # too large), not just the too-small side.
    seg_len = np.linalg.norm(p0 - p3)
    arc_len = 0.0
    for i in range(1, len(points)):
        arc_len += np.linalg.norm(points[i] - points[i - 1])
    # Bound alpha by the SPAN of this point subset (its bounding-box
    # diagonal), not by arc_len: on a closed loop's first fit attempt
    # arc_len is the whole circumference while the chord p0->p3 is ~0, and
    # neither of those is the right yardstick for "how far a control point
    # may reasonably sit from its endpoint" -- a control point should never
    # need to reach further than the region the points themselves occupy.
    diag = float(np.hypot(points[:, 0].max() - points[:, 0].min(),
                           points[:, 1].max() - points[:, 1].min()))
    ref_len = seg_len if seg_len > 1e-6 else (arc_len / 3.0 if arc_len > 1e-6 else 1.0)
    fallback = ref_len / 3.0
    max_alpha = max(diag, ref_len, 1e-6)
    eps = 1e-6 * ref_len if ref_len > 0 else 1e-6
    if alpha_l < eps or alpha_r < eps or alpha_l > max_alpha or alpha_r > max_alpha:
        alpha_l = alpha_r = fallback

    c1 = p0 + t_hat1 * alpha_l
    c2 = p3 + t_hat2 * alpha_r
    return (p0, c1, c2, p3)


def _compute_max_error(points, u, ctrl):
    max_dist = 0.0
    split_point = len(points) // 2
    for i, p in enumerate(points):
        d = _q(ctrl, u[i]) - p
        dist = np.dot(d, d)
        if dist > max_dist:
            max_dist = dist
            split_point = i
    return max_dist, split_point


def _fit_cubic(points, t_hat1, t_hat2, error, out):
    if len(points) == 2:
        dist = np.linalg.norm(points[0] - points[1]) / 3.0
        p0, p3 = points[0], points[1]
        out.append((p0, p0 + t_hat1 * dist, p3 + t_hat2 * dist, p3))
        return

    u = _chord_length_parameterize(points)
    ctrl = _generate_bezier(points, u, t_hat1, t_hat2)
    max_err, split_point = _compute_max_error(points, u, ctrl)
    if max_err < error:
        out.append(ctrl)
        return

    for _ in range(4):
        u = _reparameterize(points, u, ctrl)
        ctrl = _generate_bezier(points, u, t_hat1, t_hat2)
        max_err, split_point = _compute_max_error(points, u, ctrl)
        if max_err < error:
            out.append(ctrl)
            return

    if split_point < 2:
        split_point = 2
    if split_point > len(points) - 2:
        split_point = len(points) - 2

    t_hat_center = points[split_point - 1] - points[split_point + 1]
    norm = np.linalg.norm(t_hat_center)
    t_hat_center = t_hat_center / norm if norm > 1e-9 else np.array([0.0, 0.0])

    _fit_cubic(points[: split_point + 1], t_hat1, t_hat_center, error, out)
    _fit_cubic(points[split_point:], -t_hat_center, t_hat2, error, out)


def _unit_tangent(a, b):
    v = b - a
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else np.array([0.0, 0.0])


def adaptive_max_error(points_xy, ratio: float = 0.012, lo: float = 1.2, hi: float = 22.0) -> float:
    """
    "Smooth finish" support: a fixed pixel max_error (e.g. 3.0) means a big
    drawing gets fit with lots of short segments (looks hand-drawn / jittery)
    while a tiny drawing gets over-simplified. Scaling the tolerance to the
    stroke's own size gives a consistent, size-independent result: fewer,
    longer, cleaner curve segments -- closer to what a vector-tracing tool
    (Illustrator "Image Trace", potrace...) would produce -- regardless of
    whether the design is drawn small or large on the canvas.
    """
    pts = np.array([[float(x), float(y)] for (x, y) in points_xy], dtype=float)
    if len(pts) < 2:
        return lo
    diag = float(np.hypot(pts[:, 0].max() - pts[:, 0].min(), pts[:, 1].max() - pts[:, 1].min()))
    err = ratio * diag
    return float(min(max(err, lo), hi))


def _fit_curve_closed(core: "np.ndarray", max_error: float, n_split: int = 4):
    """Fits a CLOSED loop (core[0] is meant to reconnect to core[-1]) by
    pre-splitting it into a handful of open arcs and fitting each one
    separately, instead of handing the whole loop to _fit_cubic as one
    piece. A single full-loop fit is degenerate for Schneider's algorithm:
    the start/end points are the same point while the chord between them is
    the entire circumference, so the least-squares tangent-scale solve
    (alpha_l/alpha_r) can become ill-conditioned and place control points
    far outside the drawing. Splitting first means every piece _fit_cubic
    ever sees has a genuine, non-degenerate chord."""
    m = len(core)
    n_split = max(2, min(n_split, m // 3)) if m >= 6 else 1
    idxs = [int(round(i * m / n_split)) for i in range(n_split)]
    out = []
    for k in range(n_split):
        i0 = idxs[k]
        if k < n_split - 1:
            i1 = idxs[k + 1]
            seg_pts = core[i0:i1 + 1]
        else:
            seg_pts = np.vstack([core[i0:], core[0:1]])  # wrap back to the start
        if len(seg_pts) < 2:
            continue
        t_hat1 = _unit_tangent(seg_pts[0], seg_pts[1])
        t_hat2 = _unit_tangent(seg_pts[-1], seg_pts[-2])
        _fit_cubic(seg_pts, t_hat1, t_hat2, max_error, out)
    return out


def fit_curve(points_xy, max_error: float = 4.0):
    """
    points_xy : liste de (x, y) capturee sur le canvas (deja simplifiee/filtree).
    max_error : erreur quadratique max toleree (en pixels^2 approx).
    Retourne une liste de segments (P0, C1, C2, P3) avec P0,C1,C2,P3 = tuples (x,y).
    """
    pts = np.array([[float(x), float(y)] for (x, y) in points_xy], dtype=float)
    dedup = [pts[0]]
    for p in pts[1:]:
        if np.linalg.norm(p - dedup[-1]) > 1e-6:
            dedup.append(p)
    pts = np.array(dedup)
    if len(pts) < 2:
        p = tuple(pts[0]) if len(pts) else (0.0, 0.0)
        return [(p, p, p, p)]

    # A CLOSED stroke is passed in here with its first and last points
    # coincident (the caller duplicates the start point to close the loop).
    # That's the degenerate case _fit_curve_closed exists for.
    if len(pts) >= 6 and np.linalg.norm(pts[0] - pts[-1]) < 1e-3:
        out = _fit_curve_closed(pts[:-1], max_error)
        return [tuple(tuple(map(float, pt)) for pt in seg) for seg in out]

    t_hat1 = _unit_tangent(pts[0], pts[1])
    t_hat2 = _unit_tangent(pts[-1], pts[-2])

    out = []
    _fit_cubic(pts, t_hat1, t_hat2, max_error, out)
    return [tuple(tuple(map(float, pt)) for pt in seg) for seg in out]

