
from __future__ import annotations
import math
from typing import List, Optional, Tuple

import numpy as np

from shapes import BezierStroke
from smoothing import clean_stroke
from curvefit import fit_curve, adaptive_max_error
from beautify import taubin_fair

MAX_ANALYSIS_DIM = 900     # photos are downscaled to this size for tracing
                            # (was 640 -- raised so extracted outlines keep
                            # more of the source photo's real detail instead
                            # of looking like a different, blurrier image)
MIN_CONTOUR_LEN = 24       # px (analysis scale): shorter loops are noise
MAX_TRACE_STEPS = 100000   # hard safety bound for one boundary walk
DEFAULT_LEVELS = 5         # luminance bands for multilevel color extraction


# --------------------------------------------------------------- numpy core
def _downscale(gray: np.ndarray, max_dim: int = MAX_ANALYSIS_DIM) -> np.ndarray:
    h, w = gray.shape
    k = int(np.ceil(max(h, w) / max_dim))
    if k <= 1:
        return gray
    h2, w2 = h - h % k, w - w % k
    return gray[:h2, :w2].reshape(h2 // k, k, w2 // k, k).mean(axis=(1, 3))


def _downscale_rgb(rgb: np.ndarray, max_dim: int = MAX_ANALYSIS_DIM) -> np.ndarray:
    
    h, w, _ = rgb.shape
    k = int(np.ceil(max(h, w) / max_dim))
    if k <= 1:
        return rgb
    h2, w2 = h - h % k, w - w % k
    return rgb[:h2, :w2, :].reshape(h2 // k, k, w2 // k, k, 3).mean(axis=(1, 3))


def _gaussian_blur(gray: np.ndarray, sigma: float = 1.2) -> np.ndarray:
    r = max(1, int(3 * sigma))
    x = np.arange(-r, r + 1, dtype=float)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    k /= k.sum()
    out = np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, mode="valid"), 0, gray)
    out = np.apply_along_axis(lambda m: np.convolve(np.pad(m, r, mode="edge"), k, mode="valid"), 1, out)
    return out


def _otsu_threshold(gray: np.ndarray) -> float:
    hist, edges = np.histogram(gray, bins=256, range=(0.0, 1.0))
    hist = hist.astype(float)
    total = hist.sum()
    if total <= 0:
        return 0.5
    centers = 0.5 * (edges[:-1] + edges[1:])
    w0 = np.cumsum(hist)
    w1 = total - w0
    m0 = np.cumsum(hist * centers) / np.maximum(w0, 1e-12)
    m_total = (hist * centers).sum() / total
    m1 = (m_total * total - np.cumsum(hist * centers)) / np.maximum(w1, 1e-12)
    var_between = w0 * w1 * (m0 - m1) ** 2
    return float(centers[int(np.argmax(var_between))])


def _box_mean(gray: np.ndarray, radius: int) -> np.ndarray:
    """Fast O(H*W) local average over a (2*radius+1)-square window at every
    pixel, via an integral image (no scipy dependency)."""
    r = max(1, int(radius))
    pad = np.pad(gray, r, mode="edge")
    ii = np.zeros((pad.shape[0] + 1, pad.shape[1] + 1))
    ii[1:, 1:] = np.cumsum(np.cumsum(pad, axis=0), axis=1)
    size = 2 * r + 1
    H, W = gray.shape
    total = (ii[size:size + H, size:size + W]
             - ii[0:H, size:size + W]
             - ii[size:size + H, 0:W]
             + ii[0:H, 0:W])
    return total / (size * size)


def binarize(gray: np.ndarray) -> np.ndarray:
    
    g = _gaussian_blur(gray, sigma=1.0)
    h, w = g.shape
    radius = max(9, int(round(min(h, w) / 30)))
    local_mean = _box_mean(g, radius)
    offset = 0.05
    dark = g < (local_mean - offset)
    if dark.mean() > 0.5:
        dark = ~dark
    return dark


# 8 neighbors, clockwise, starting from West: (dy, dx)
_NB = [(0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1)]


def _trace_one(mask: np.ndarray, sy: int, sx: int) -> List[Tuple[int, int]]:
   
    H, W = mask.shape
    contour = [(sx, sy)]
    p = (sy, sx)
    b = (sy, sx - 1)  # backtrack: the background pixel we came from
    seen = {(p, b)}
    for _ in range(MAX_TRACE_STEPS):
        py, px = p
        try:
            idx = _NB.index((b[0] - py, b[1] - px))
        except ValueError:
            idx = 0
        nxt = None
        prev = b
        for k in range(1, 9):
            j = (idx + k) % 8
            ny, nx = py + _NB[j][0], px + _NB[j][1]
            if 0 <= ny < H and 0 <= nx < W and mask[ny, nx]:
                nxt = (ny, nx)
                break
            prev = (ny, nx)
        if nxt is None:
            break  # isolated pixel
        b = prev
        p = nxt
        if (p, b) in seen:
            break  # closed the loop
        seen.add((p, b))
        contour.append((p[1], p[0]))
    return contour


def extract_contours(mask: np.ndarray) -> List[List[Tuple[int, int]]]:
    """All boundary loops of the mask (outer silhouettes and holes)."""
    H, W = mask.shape
    used = np.zeros_like(mask, dtype=bool)
    contours = []
    for y in range(H):
        row = mask[y]
        for x in range(W):
            if not row[x] or used[y, x]:
                continue
            if x > 0 and row[x - 1]:
                continue  # only start where the West neighbor is background
            c = _trace_one(mask, y, x)
            for (cx, cy) in c:
                used[cy, cx] = True
            if len(c) >= MIN_CONTOUR_LEN:
                contours.append(c)
    return contours


def _contour_area(c) -> float:
    xs = [p[0] for p in c]
    ys = [p[1] for p in c]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def _shoelace_area(c) -> float:
    """True enclosed polygon area (not the bbox proxy _contour_area uses for
    sorting) -- needed for a real compactness/spikiness measure."""
    n = len(c)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        x0, y0 = c[i]
        x1, y1 = c[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return abs(total) / 2.0


def _perimeter(c) -> float:
    n = len(c)
    if n < 2:
        return 0.0
    total = 0.0
    for i in range(n):
        x0, y0 = c[i]
        x1, y1 = c[(i + 1) % n]
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def _compactness(c) -> float:
    
    area = _shoelace_area(c)
    per = _perimeter(c)
    if per <= 1e-6:
        return 1.0
    return float(4.0 * math.pi * area / (per * per))


def _rgb_to_hex(rgb: np.ndarray) -> str:
    r, g, b = (int(round(np.clip(c, 0.0, 1.0) * 255)) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _mean_color_at(rgb: np.ndarray, contour, fallback: str) -> str:
    
    if rgb is None or not contour:
        return fallback
    H, W, _ = rgb.shape
    xs = np.clip([p[0] for p in contour], 0, W - 1)
    ys = np.clip([p[1] for p in contour], 0, H - 1)
    samples = rgb[ys, xs]
    return _rgb_to_hex(samples.mean(axis=0))


def _interior_color_sample(rgb: np.ndarray, contour):
    
    if rgb is None or not contour:
        return None
    H, W, _ = rgb.shape
    xs = np.array([p[0] for p in contour], dtype=float)
    ys = np.array([p[1] for p in contour], dtype=float)
    cx, cy = xs.mean(), ys.mean()
    step = max(1, len(contour) // 24)  # ~24 boundary directions
    bxs, bys = xs[::step], ys[::step]
    all_samples = []
    for frac in (0.25, 0.45, 0.65):
        sx = np.clip(np.round(cx + frac * (bxs - cx)).astype(int), 0, W - 1)
        sy = np.clip(np.round(cy + frac * (bys - cy)).astype(int), 0, H - 1)
        all_samples.append(rgb[sy, sx])
    return np.concatenate(all_samples, axis=0).mean(axis=0)


def _shift(mask: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """mask shifted by (dy, dx), zero-padded (no wraparound)."""
    out = np.zeros_like(mask)
    h, w = mask.shape
    sy0, sy1 = max(0, -dy), h - max(0, dy)
    dy0, dy1 = max(0, dy), h - max(0, -dy)
    sx0, sx1 = max(0, -dx), w - max(0, dx)
    dx0, dx1 = max(0, dx), w - max(0, -dx)
    if sy1 > sy0 and sx1 > sx0:
        out[dy0:dy1, dx0:dx1] = mask[sy0:sy1, sx0:sx1]
    return out


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    out = mask.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius and (dx or dy):
                out |= _shift(mask, dy, dx)
    return out


def _erode(mask: np.ndarray, radius: int) -> np.ndarray:
    out = mask.copy()
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx * dx + dy * dy <= radius * radius and (dx or dy):
                out &= _shift(mask, dy, dx)
    return out


def _close_gaps(mask: np.ndarray, radius: int = 3) -> np.ndarray:
    
    return _erode(_dilate(mask, radius), radius)


def _declutter_small_clusters(contours: List[List[Tuple[int, int]]],
                              overall_diag: float) -> set:
    
    if len(contours) <= 1 or overall_diag <= 0:
        return set()
    CLUSTER_RATIO = 0.22
    COMPACT_FLOOR = 0.14
    skip_ids = set()
    for c in contours:
        xs = [p[0] for p in c]
        ys = [p[1] for p in c]
        cx0, cx1, cy0, cy1 = min(xs), max(xs), min(ys), max(ys)
        diag = math.hypot(cx1 - cx0, cy1 - cy0)
        small = diag < CLUSTER_RATIO * overall_diag
        
        spiky = _compactness(c) < COMPACT_FLOOR
        if small or spiky:
            skip_ids.add(id(c))
    return skip_ids


def _is_line_art(gray: np.ndarray) -> bool:
    
    midtone = (gray > 0.15) & (gray < 0.85)
    return float(midtone.mean()) < 0.12


def trace_gray(gray: np.ndarray, target_box: Tuple[float, float, float, float],
               color: str = "#000000", width: float = 2.5,
               max_shapes: int = 40, smooth: bool = True,
               rgb: Optional[np.ndarray] = None, levels: int = DEFAULT_LEVELS,
               use_source_colors: bool = True) -> List[BezierStroke]:
   
    g = _downscale(np.asarray(gray, dtype=float))
    rgb_small = _downscale_rgb(np.asarray(rgb, dtype=float)) if rgb is not None else None
    line_art = _is_line_art(g)

    if rgb_small is not None and use_source_colors and not line_art:
        all_contours = []
        edges = np.quantile(g, np.linspace(0.0, 1.0, levels + 1))
        per_level_cap = max(3, max_shapes // levels)
        for i in range(levels):
            lo, hi = edges[i], edges[i + 1]
            band = (g >= lo) & (g <= hi if i == levels - 1 else g < hi)
            if band.mean() < 0.002:  # negligible band, skip
                continue
            band_contours = extract_contours(band)
            band_contours.sort(key=_contour_area, reverse=True)
            all_contours.extend(band_contours[:per_level_cap])
        
        contours = all_contours[:max_shapes]
        contours.sort(key=_contour_area, reverse=True)
        heavy_ids = set()
    elif rgb_small is not None and use_source_colors:
        
        polarity_dark = g.mean() > 0.5  # usual case: dark design on light background
        ink_mask = (g < 0.35) if polarity_dark else (g > 0.65)
        fill_mask = ((g >= 0.35) & (g < 0.85)) if polarity_dark else ((g <= 0.65) & (g > 0.15))
        # Bridge gaps between individual hatch/cross-hatch strokes so a
        # hand-shaded region traces as one clean blob (see _close_gaps).
        fill_mask = _close_gaps(fill_mask, radius=max(2, int(round(g.shape[0] / 150))))

        ink_contours = extract_contours(ink_mask)
        ink_contours.sort(key=_contour_area, reverse=True)
        fill_contours = extract_contours(fill_mask)
        fill_contours.sort(key=_contour_area, reverse=True)

        half = max(1, max_shapes // 2)
        contours = ink_contours[:half] + fill_contours[:half]
        contours = contours[:max_shapes]
        
        heavy_ids = {id(c) for c in fill_contours[:half]}
        contours.sort(key=_contour_area, reverse=True)
    else:
        mask = binarize(g)
        contours = extract_contours(mask)
        contours.sort(key=_contour_area, reverse=True)
        contours = contours[:max_shapes]
        heavy_ids = set()

    if not contours:
        return []

    # common transform: fit ALL kept contours together into target_box,
    # preserving their relative positions and aspect ratio
    all_x = [p[0] for c in contours for p in c]
    all_y = [p[1] for c in contours for p in c]
    x0, x1 = min(all_x), max(all_x)
    y0, y1 = min(all_y), max(all_y)
    bw, bh = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    tx, ty, tw, th = target_box
    s = min(tw / bw, th / bh)
    ox = tx + (tw - bw * s) / 2 - x0 * s
    oy = ty + (th - bh * s) / 2 - y0 * s

   
    cluster_skip_ids: set = set()
    if not use_source_colors:
        overall_diag = math.hypot(bw, bh)
        cluster_skip_ids = _declutter_small_clusters(contours, overall_diag)

    have_colors = rgb_small is not None and use_source_colors
    shapes: List[BezierStroke] = []
    for c in contours:
        if id(c) in cluster_skip_ids:
            continue
        stroke_color = _mean_color_at(rgb_small, c, color) if have_colors else color
        interior_rgb = _interior_color_sample(rgb_small, c) if have_colors else None
        is_fill = interior_rgb is not None and interior_rgb.mean() < 0.92  # not near-white
        fill_color = _rgb_to_hex(interior_rgb) if is_fill else None

        pts = [(p[0] * s + ox, p[1] * s + oy) for p in c]
        n_samples = int(min(260, max(60, len(pts) // 2)))
        if smooth:
            if id(c) in heavy_ids:
               
                pts = clean_stroke(pts, closed=True, n_samples=min(n_samples, 90), passes=14)
                pts = taubin_fair(pts, closed=True, passes=20)
            else:
                
                pts = clean_stroke(pts, closed=True, n_samples=n_samples, passes=3)
        err = adaptive_max_error(pts, ratio=0.003, lo=0.5, hi=5.0)
        segments = _fit_curve_safe(pts, err)
        if segments:
            shapes.append(BezierStroke(
                segments, color=stroke_color, width=width, closed=True,
                filled=is_fill, fill_color=fill_color,
            ))

    return _drop_noise_fragments(shapes)


def _segments_sane(segments, pts) -> bool:
    """Schneider's iterative Bezier fit can occasionally become numerically
    ill-conditioned on a dense, near-circular point cloud at a tight error
    tolerance (nearly-collinear tangent estimates blow up a control point
    to a wild coordinate) -- this is what used to produce a shape whose
    bounding box was hundreds of pixels outside the actual drawing. Sanity
    check: every control point must stay within a generous margin around
    the SOURCE point cloud's own bounding box."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    
    mx, my = 0.2 * w, 0.2 * h
    lo_x, hi_x, lo_y, hi_y = x0 - mx, x1 + mx, y0 - my, y1 + my
    for seg in segments:
        for (px, py) in seg:
            if not (lo_x <= px <= hi_x and lo_y <= py <= hi_y):
                return False
    return True


def _polyline_as_bezier(pts):
    """Last-resort, always-correct fallback: turns the (already smoothed)
    point list into a chain of degenerate/near-degenerate cubic Bezier
    segments that simply follow the points directly (control points placed
    a third of the way along each straight sub-chord). Not as visually
    smooth as a proper curve fit, but by construction it can never leave
    the point cloud's own bounding box -- used only if every fit_curve
    attempt in _fit_curve_safe fails its sanity check."""
    segs = []
    n = len(pts)
    if n < 2:
        return segs
    for i in range(n - 1):
        p0 = np.array(pts[i], dtype=float)
        p3 = np.array(pts[i + 1], dtype=float)
        c1 = p0 + (p3 - p0) / 3.0
        c2 = p0 + (p3 - p0) * 2.0 / 3.0
        segs.append((tuple(p0), tuple(c1), tuple(c2), tuple(p3)))
    return segs


def _fit_curve_safe(pts, err: float):
   
    for candidate_err in (err, max(err * 4, 6.0), 20.0, 60.0):
        segments = fit_curve(pts, max_error=candidate_err)
        if segments and _segments_sane(segments, pts):
            return segments
    return _polyline_as_bezier(pts)


def _bbox_diag(shape: BezierStroke) -> float:
    x0, y0, x1, y1 = shape.bbox()
    return math.hypot(x1 - x0, y1 - y0)


def _drop_noise_fragments(shapes: List[BezierStroke]) -> List[BezierStroke]:
    
    if len(shapes) <= 1:
        return shapes
    diags = [_bbox_diag(s) for s in shapes]
    biggest = max(diags) or 1.0
    floor = max(2.0, 0.04 * biggest)
    return [s for s, d in zip(shapes, diags) if d >= floor or not getattr(s, "closed", True)]


# ------------------------------------------------------------------ Qt glue
def qimage_to_gray(qimage) -> Optional[np.ndarray]:
    """QImage -> grayscale numpy array in [0, 1]."""
    from PyQt5.QtGui import QImage
    if qimage is None or qimage.isNull():
        return None
    img = qimage.convertToFormat(QImage.Format_Grayscale8)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    ptr.setsize(img.byteCount())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, img.bytesPerLine())[:, :w]
    return arr.astype(float) / 255.0


def qimage_to_rgb(qimage) -> Optional[np.ndarray]:
    """QImage -> RGB numpy array in [0, 1], shape (H, W, 3). Used to sample
    each extracted contour's real color from the source photo, instead of
    the extraction always coming out in a single flat color."""
    from PyQt5.QtGui import QImage
    if qimage is None or qimage.isNull():
        return None
    img = qimage.convertToFormat(QImage.Format_RGB888)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    ptr.setsize(img.byteCount())
    stride = img.bytesPerLine()
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, stride)[:, : w * 3].reshape(h, w, 3)
    return arr.astype(float) / 255.0


def load_qimage_from_url(url: str, timeout: float = 20.0):
    """Download a photo from the web -> QImage (or None on failure)."""
    import urllib.request
    from PyQt5.QtGui import QImage
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (VanovaTikZSketch)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    img = QImage.fromData(data)
    return None if img.isNull() else img


def trace_qimage(qimage, target_box, color="#000000", width=2.5,
                 max_shapes: int = 40, use_source_colors: bool = True) -> List[BezierStroke]:
    gray = qimage_to_gray(qimage)
    if gray is None:
        return []
    rgb = qimage_to_rgb(qimage) if use_source_colors else None
    return trace_gray(gray, target_box, color=color, width=width, max_shapes=max_shapes,
                       rgb=rgb, use_source_colors=use_source_colors)
