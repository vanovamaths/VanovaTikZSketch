"""
image_trace.py  (v4.2)
Import a photo (local file or straight from a web URL) and EXTRACT ITS DESIGN
as editable vector shapes: the main contours of the image are detected and
converted into the same closed Bezier strokes the pen tool produces, dropped
onto the canvas where they can be selected, moved, erased, recolored,
idealized or machine-finished like any hand-drawn shape.

Pipeline (deterministic, no AI model, numpy only):
1. grayscale + downscale (max ~640 px) + Gaussian blur,
2. Otsu threshold -> binary design/background mask (polarity auto-detected),
3. Moore-neighbor boundary tracing -> one closed polyline per contour
   (outer silhouettes AND holes, e.g. the hole of a torus),
4. keep the N largest contours, clean/resample them (smoothing.py),
5. Schneider fit (curvefit.py) -> closed BezierStroke shapes, scaled and
   centered on the canvas.

The glue that touches Qt (QImage <-> numpy, URL download) is kept in thin
functions at the bottom so the geometric pipeline stays testable headless.
"""
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
    """Same block-mean downscale as _downscale, applied to each of the 3
    color channels -- keeps the RGB array in exact pixel alignment with the
    grayscale array so a contour traced on one lines up with the other."""
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
    """Design/background mask; the design is assumed to be the minority side
    (dark strokes on a light photo, or the reverse -- auto-detected).

    v4.16: uses a LOCAL (adaptive) threshold instead of one single global
    Otsu cutoff. A real phone photo almost never has perfectly even
    lighting -- a shadow across one corner of the page, a slight vignette,
    glare -- and a single global threshold either swallows the dim side of
    the page as "ink" or loses faint strokes on the bright side, which is
    exactly the "the whole outline looks nothing like my drawing" failure.
    Comparing every pixel to the LOCAL average around it (a box roughly a
    few strokes wide) tracks slow lighting gradients automatically while
    still picking out a stroke that's genuinely darker than its immediate
    surroundings -- the standard adaptive-threshold technique used by real
    scanning apps."""
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
    """Moore-neighbor boundary tracing from a start pixel whose West neighbor
    is background. Returns the boundary as a list of (x, y) pixels.
    Termination: stop as soon as a (pixel, backtrack) STATE repeats -- the
    walk is a deterministic function of that state, so a repeat means the
    loop is closed. This is Jacob's criterion generalized, and it guarantees
    termination on every possible mask (finite state space)."""
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
    """Isoperimetric ratio 4*pi*Area/Perimeter^2, ~1.0 for a smooth round
    blob, close to 0 for a spiky/fractal boundary. A cluster of crossing
    thin strokes has a boundary that hugs every stroke -- huge perimeter for
    almost no enclosed area -- so this stays low regardless of how big the
    cluster's own bounding box happens to be, unlike a pure size threshold."""
    area = _shoelace_area(c)
    per = _perimeter(c)
    if per <= 1e-6:
        return 1.0
    return float(4.0 * math.pi * area / (per * per))


def _rgb_to_hex(rgb: np.ndarray) -> str:
    r, g, b = (int(round(np.clip(c, 0.0, 1.0) * 255)) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _mean_color_at(rgb: np.ndarray, contour, fallback: str) -> str:
    """Average source-photo color sampled at the contour's own pixels -- the
    boundary of a region is a good, cheap proxy for that region's color, and
    this is what lets the extracted shapes actually look like the photo
    instead of a plain black-outline trace."""
    if rgb is None or not contour:
        return fallback
    H, W, _ = rgb.shape
    xs = np.clip([p[0] for p in contour], 0, W - 1)
    ys = np.clip([p[1] for p in contour], 0, H - 1)
    samples = rgb[ys, xs]
    return _rgb_to_hex(samples.mean(axis=0))


def _interior_color_sample(rgb: np.ndarray, contour):
    """Robust estimate of what's INSIDE the shape -- unlike _mean_color_at
    (which averages the boundary/ink color), this looks at the fill. For a
    shape that is just an outline (e.g. the silhouette of a diagram, or a
    big region drawn as a closed curve but not meant to be solid), the
    interior sits on the plain background and comes back near-white. For a
    genuinely solid/shaded region (a filled gray lens, a colored patch), the
    interior comes back as that fill's real color.

    A single centroid pixel is fragile (an unrelated shape can coincidentally
    sit exactly at another shape's centroid, or -- for a hatched/textured
    fill -- the centroid could land in a gap between strokes), so many
    points are sampled at several radii between the centroid and the
    boundary, and the MEAN color is taken: robust to a handful of unlucky
    samples, and correctly averages a partially-covered (hatched) region
    into a mid-tone rather than flipping between pure fill and pure gap."""
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
    """Morphological closing (dilate then erode), pure numpy -- bridges the
    small gaps BETWEEN individual hand-drawn hatch/cross-hatch strokes so a
    shaded region traces as ONE clean blob instead of dozens of separate
    hatch-stroke-sized fragments."""
    return _erode(_dilate(mask, radius), radius)


def _declutter_small_clusters(contours: List[List[Tuple[int, int]]],
                              overall_diag: float) -> set:
    """Identifies contours that are a small tangle of crossing strokes
    (hatch marks, a dashed curve's individual dashes...) rather than one of
    the drawing's real closed silhouettes.

    An earlier version of this tried to rebuild those clusters from their
    medial-axis skeleton into clean open lines -- geometrically the "right"
    answer, but real hand-drawn crossings turn out to be pixel-messy enough
    (rough edges, uneven stroke width) that a skeleton graph fractures into
    dozens of tiny disconnected stubs instead of a few clean lines, which
    looked WORSE than the original spiky blob it was meant to replace.

    So instead: these small/spiky clusters are simply DROPPED. Per the
    "extract a blank outline, I'll add the details myself" design (v4.16),
    that's the right tradeoff anyway -- the big, reliable body outlines
    come through cleanly, and small decorative marks (hatching, dashes,
    labels) are exactly the kind of thing meant to be redrawn by hand
    afterward with the pen tool, which takes a few seconds per mark and
    never looks like a garbled artifact."""
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
        # A crossing-stroke tangle has a boundary that hugs every individual
        # stroke -- huge perimeter for almost no enclosed area -- so it
        # stays spiky (low compactness) even when its bbox is NOT small
        # relative to the drawing (e.g. hatching spread across a big shaded
        # region). Catching that case here is what a size-only threshold
        # misses.
        spiky = _compactness(c) < COMPACT_FLOOR
        if small or spiky:
            skip_ids.add(id(c))
    return skip_ids


def _is_line_art(gray: np.ndarray) -> bool:
    """True for a diagram/line drawing (mostly flat background + thin dark
    strokes, e.g. any math figure), False for a real photo (broad continuous
    tone distribution). Line art has almost no midtone pixels -- everything
    is either background or the (thin, so few pixels) ink; a photo's
    histogram is spread out. This decides which extraction strategy to use:
    multilevel posterization works well on photos but badly fragments the
    thin strokes of a diagram into scattered, self-crossing artifacts."""
    midtone = (gray > 0.15) & (gray < 0.85)
    return float(midtone.mean()) < 0.12


def trace_gray(gray: np.ndarray, target_box: Tuple[float, float, float, float],
               color: str = "#000000", width: float = 2.5,
               max_shapes: int = 40, smooth: bool = True,
               rgb: Optional[np.ndarray] = None, levels: int = DEFAULT_LEVELS,
               use_source_colors: bool = True) -> List[BezierStroke]:
    """
    Full headless pipeline: grayscale array in [0,1] (+ optional matching RGB
    array in [0,1], same H,W) -> list of closed, editable BezierStroke shapes
    scaled/centered into target_box (x, y, w, h in canvas coordinates), a
    faithful reproduction of the original design.

    Two strategies, auto-selected by `_is_line_art`:
    - Diagram / line art (a math figure, most drawings, mostly flat
      background + thin dark strokes -- the common case in this app): ONE
      Otsu binary mask, exactly like the outline the source drawing actually
      has. Multilevel posterization badly fragments thin strokes into
      scattered self-crossing artifacts on this kind of image, so it is
      deliberately NOT used here.
    - Photo (broad continuous tone distribution): the image is split into
      `levels` luminance bands (posterization) so several distinct
      tone/color regions are captured instead of one silhouette.

    Either way, every shape's color is sampled from the real source image
    (never a flat placeholder), and a shape is only solid-filled if its own
    CENTROID sits on genuinely shaded/colored pixels -- a shape whose
    centroid is on the plain background is treated as an outline instead
    (this is what keeps a diagram's outer silhouette a plain outline rather
    than turning it into one big opaque blob).
    """
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
        # Truncate FIRST (keeps a diverse mix across all tone bands, so
        # small foreground details from a minority band aren't crowded out
        # by one big band), THEN sort largest-first for the draw order: big
        # background regions get painted first (bottom), smaller foreground
        # details after (on top) -- otherwise a big fill could cover them.
        contours = all_contours[:max_shapes]
        contours.sort(key=_contour_area, reverse=True)
        heavy_ids = set()
    elif rgb_small is not None and use_source_colors:
        # Line-art path with real colors available: TWO fixed (not
        # quantile-based) bands -- ink (near-black strokes/outlines) and
        # fill (mid-gray/colored shaded regions) -- so a shaded region like
        # a filled lens/circle in a math diagram is captured as its own
        # shape instead of being missed by a single global Otsu threshold.
        # Fixed thresholds (not adaptive/quantile) are deliberate: quantile
        # bands are sized by PIXEL COUNT, which on a mostly-background image
        # cuts arbitrarily through the antialiasing gradient of thin lines
        # and fragments them into scattered, self-crossing artifacts.
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
        # A shaded/hatched region's traced boundary hugs every individual
        # hatch stroke, coming out spiky and jagged (not a hand-drawn wobble
        # -- a genuine dense fractal-ish contour), so these contours need
        # MUCH heavier smoothing/fairing than a clean ink outline to read as
        # the intended shape instead of a jagged gray splat.
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

    # "vide"/outline-only import (use_source_colors=False, the app default
    # since v4.16): a small cluster of crossing strokes -- hatch marks, one
    # dash of a dashed curve -- boundary-traces as a single jagged
    # "starburst" blob (the union of several thin strokes really does have a
    # spiky outline). Those clusters are dropped rather than kept as a
    # garbled shape -- see _declutter_small_clusters.
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
                # shaded/hatched region: the raw traced boundary hugs every
                # hatch stroke and comes out spiky -- heavy smoothing +
                # curvature fairing (no shrink) so it reads as the intended
                # blob shape instead of a jagged gray splat.
                pts = clean_stroke(pts, closed=True, n_samples=min(n_samples, 90), passes=14)
                pts = taubin_fair(pts, closed=True, passes=20)
            else:
                # ink/outline: lighter smoothing -- the goal here is only to
                # remove pixel-grid staircasing, not to round off real detail
                # the way a freehand-jitter cleanup would.
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
    # A real Bezier fit can legitimately bulge a little past the point
    # cloud's own bbox (control points aren't ON the curve), but never by
    # much -- 20% of the shape's own size is already generous. The old 2x
    # margin here was so loose it let genuinely broken control points
    # (hundreds of px outside the drawing) through as "sane".
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
    """fit_curve() with a fallback ladder of looser tolerances if the result
    fails the sanity check -- looser tolerances mean fewer/simpler Bezier
    segments, which is much more numerically stable than a tight fit on a
    dense point cloud. Guarantees a sane (if slightly less precise) result
    instead of an occasional wildly-out-of-bounds shape. If even the
    loosest tolerance still fails (can happen on a CLOSED loop where the
    very first/last sample points coincide, an edge case Schneider's
    algorithm was never designed for), falls back to a guaranteed-correct
    straight-polyline-as-bezier chain rather than ever returning something
    wildly out of bounds."""
    for candidate_err in (err, max(err * 4, 6.0), 20.0, 60.0):
        segments = fit_curve(pts, max_error=candidate_err)
        if segments and _segments_sane(segments, pts):
            return segments
    return _polyline_as_bezier(pts)


def _bbox_diag(shape: BezierStroke) -> float:
    x0, y0, x1, y1 = shape.bbox()
    return math.hypot(x1 - x0, y1 - y0)


def _drop_noise_fragments(shapes: List[BezierStroke]) -> List[BezierStroke]:
    """Final safety net: after extraction/smoothing/closing, a handful of
    tiny leftover fragments can still slip through (a sliver where a hatch
    closing didn't fully bridge a gap, antialiasing dust, etc.) and show up
    as a stray little scribble that doesn't belong in the design at all.
    Anything whose bounding-box diagonal is below 4% of the largest shape's
    diagonal is dropped -- comfortably smaller than any real, deliberate
    mark (a label tick, a small hatch stroke) in a normal diagram.
    OPEN strokes (closed=False) are exempt from this floor: those are only
    ever produced by the skeleton/decluttering path for a deliberately
    small mark (one hatch line, one dash of a dashed curve) that is
    SUPPOSED to be short -- applying the same floor to them would delete
    most of the hatching it was built to preserve."""
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
