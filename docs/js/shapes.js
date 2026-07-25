/*
 * shapes.js
 * Plain-object shape model (mirrors the desktop app's shapes.py), plus
 * bbox / translate / clone helpers and the canvas render routine.
 */

const HEAD_STYLES = ['stealth', 'classical', 'harpoon', 'none'];

// Global toggle for the "Sketchy style" option: draws every shape's
// outline as a hand-drawn-looking double pass (small, deterministic
// per-point jitter) instead of a perfectly crisp line -- a lightweight,
// dependency-free take on the effect made popular by rough.js/Excalidraw.
// Kept as a simple global (rather than plumbed through every render call)
// since it's a single app-wide display preference, toggled from app.js.
window.SKETCHY_MODE = false;

/** Quiver-style "bend": p0/p1 stay the straight endpoints, `bend` is a px
 * offset of a single quadratic-bezier control point, perpendicular to the
 * p0->p1 chord (positive = one side, negative = the other). Recomputed from
 * p0/p1 at render/export time, so it stays correct under translation and
 * rotation automatically; flip transforms negate it explicitly (see app.js)
 * to keep the curve's visual handedness mirrored along with the shape. */
function bendControlPoint(p0, p1, bend) {
  const mx = (p0[0] + p1[0]) / 2, my = (p0[1] + p1[1]) / 2;
  const dx = p1[0] - p0[0], dy = p1[1] - p0[1];
  const len = Math.hypot(dx, dy) || 1;
  const px = -dy / len, py = dx / len;
  return [mx + px * bend, my + py * bend];
}

function flattenQuadratic(p0, ctrl, p1, steps = 16) {
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps, mt = 1 - t;
    const x = mt * mt * p0[0] + 2 * mt * t * ctrl[0] + t * t * p1[0];
    const y = mt * mt * p0[1] + 2 * mt * t * ctrl[1] + t * t * p1[1];
    pts.push([x, y]);
  }
  return pts;
}

function shapeBBox(s) {
  if (s.type === 'stroke') {
    let xs = [], ys = [];
    for (const seg of s.segments) for (const p of seg) { xs.push(p[0]); ys.push(p[1]); }
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  if (s.type === 'line' || s.type === 'arrow') {
    if (s.bend) {
      const ctrl = bendControlPoint(s.p0, s.p1, s.bend);
      const xs = [s.p0[0], s.p1[0], ctrl[0]], ys = [s.p0[1], s.p1[1], ctrl[1]];
      return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    }
    return [Math.min(s.p0[0], s.p1[0]), Math.min(s.p0[1], s.p1[1]),
            Math.max(s.p0[0], s.p1[0]), Math.max(s.p0[1], s.p1[1])];
  }
  if (s.type === 'ellipse') {
    return [s.cx - s.rx, s.cy - s.ry, s.cx + s.rx, s.cy + s.ry];
  }
  if (s.type === 'polygon') {
    const xs = s.points.map((p) => p[0]);
    const ys = s.points.map((p) => p[1]);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  if (s.type === 'text') {
    const disp = typeof latexToDisplay === 'function' ? latexToDisplay(s.text) : s.text;
    const w = Math.max(20, 8 * disp.length);
    return [s.x, s.y - 10, s.x + w, s.y + 10];
  }
  return [0, 0, 0, 0];
}

function translateShape(s, dx, dy) {
  if (s.type === 'stroke') {
    s.segments = s.segments.map((seg) => seg.map((p) => [p[0] + dx, p[1] + dy]));
  } else if (s.type === 'line' || s.type === 'arrow') {
    s.p0 = [s.p0[0] + dx, s.p0[1] + dy];
    s.p1 = [s.p1[0] + dx, s.p1[1] + dy];
  } else if (s.type === 'ellipse') {
    s.cx += dx; s.cy += dy;
  } else if (s.type === 'polygon') {
    s.points = s.points.map((p) => [p[0] + dx, p[1] + dy]);
  } else if (s.type === 'text') {
    s.x += dx; s.y += dy;
  }
}

function cloneShape(s) { return JSON.parse(JSON.stringify(s)); }

function pointInBBox(x, y, bbox, pad = 6) {
  return x >= bbox[0] - pad && x <= bbox[2] + pad && y >= bbox[1] - pad && y <= bbox[3] + pad;
}

/** Distance from point to shape, for hit-testing (select/eraser). */
function distanceToShape(x, y, s) {
  const distSeg = (px, py, ax, ay, bx, by) => {
    const dx = bx - ax, dy = by - ay;
    const len2 = dx * dx + dy * dy;
    let t = len2 > 1e-9 ? ((px - ax) * dx + (py - ay) * dy) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    const cx = ax + t * dx, cy = ay + t * dy;
    return Math.hypot(px - cx, py - cy);
  };
  if (s.type === 'line' || s.type === 'arrow') {
    if (s.bend) {
      const ctrl = bendControlPoint(s.p0, s.p1, s.bend);
      const pts = flattenQuadratic(s.p0, ctrl, s.p1, 16);
      let best = Infinity;
      for (let i = 0; i < pts.length - 1; i++) best = Math.min(best, distSeg(x, y, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]));
      return best;
    }
    return distSeg(x, y, s.p0[0], s.p0[1], s.p1[0], s.p1[1]);
  }
  if (s.type === 'stroke') {
    let best = Infinity;
    for (const seg of s.segments) {
      const pts = flattenBezier(seg, 12);
      for (let i = 0; i < pts.length - 1; i++) {
        best = Math.min(best, distSeg(x, y, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]));
      }
    }
    return best;
  }
  if (s.type === 'polygon') {
    let best = Infinity;
    const pts = s.points;
    const n = pts.length;
    const lim = s.closed ? n : n - 1;
    for (let i = 0; i < lim; i++) {
      const a = pts[i], b = pts[(i + 1) % n];
      best = Math.min(best, distSeg(x, y, a[0], a[1], b[0], b[1]));
    }
    return best;
  }
  if (s.type === 'ellipse') {
    const dx = (x - s.cx) / Math.max(s.rx, 1e-6);
    const dy = (y - s.cy) / Math.max(s.ry, 1e-6);
    const r = Math.hypot(dx, dy);
    return Math.abs(r - 1) * Math.max(s.rx, s.ry);
  }
  if (s.type === 'text') {
    const bb = shapeBBox(s);
    return pointInBBox(x, y, bb, 0) ? 0 : Infinity;
  }
  return Infinity;
}

function flattenBezier([p0, c1, c2, p3], steps = 16) {
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const mt = 1 - t;
    const x = mt ** 3 * p0[0] + 3 * mt ** 2 * t * c1[0] + 3 * mt * t ** 2 * c2[0] + t ** 3 * p3[0];
    const y = mt ** 3 * p0[1] + 3 * mt ** 2 * t * c1[1] + 3 * mt * t ** 2 * c2[1] + t ** 3 * p3[1];
    pts.push([x, y]);
  }
  return pts;
}

/* -------------------------------------------------------- sketchy style */
// Deterministic per-point "randomness" (a stable hash, NOT Math.random()):
// the same point always gets the same jitter, so the hand-drawn wobble
// stays put across repaints instead of visibly vibrating every frame.
function sketchHash(n) {
  const v = Math.sin(n * 12.9898 + 78.233) * 43758.5453123;
  return v - Math.floor(v); // -> stable value in [0, 1)
}

function jitterPoint(x, y, idx, amp, salt) {
  const ang = sketchHash(idx * 0.6180339887 + salt) * Math.PI * 2;
  const r = sketchHash(idx * 0.37 + salt + 7.13) * amp;
  return [x + r * Math.cos(ang), y + r * Math.sin(ang)];
}

// Two overlapping, independently-jittered passes of the same outline is
// the classic "rough sketch" look (what rough.js/Excalidraw do): each pass
// alone is just a wobbly line, but two slightly different ones together
// read unmistakably as hand-drawn.
const SKETCH_SALTS = [12.9, 231.7];

function strokeSketchy(ctx, pts, closed, color, width) {
  if (pts.length < 2) return;
  const amp = Math.max(0.6, width * 0.6);
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(0.6, width * 0.85);
  for (const salt of SKETCH_SALTS) {
    ctx.beginPath();
    pts.forEach((p, i) => {
      const [jx, jy] = jitterPoint(p[0], p[1], i, amp, salt);
      if (i === 0) ctx.moveTo(jx, jy); else ctx.lineTo(jx, jy);
    });
    if (closed) ctx.closePath();
    ctx.stroke();
  }
}

// Subdivides straight polygon/line edges before jittering -- jittering only
// the original vertices of a long straight edge just tilts the whole edge
// (still perfectly straight), it doesn't look "wobbly"; adding a few points
// along the way is what actually produces a hand-drawn-looking line.
function densify(pts, perEdge = 6, closed = false) {
  const out = [];
  const n = pts.length;
  const lim = closed ? n : n - 1;
  for (let i = 0; i < lim; i++) {
    const a = pts[i], b = pts[(i + 1) % n];
    for (let k = 0; k < perEdge; k++) {
      const t = k / perEdge;
      out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
    }
  }
  if (!closed) out.push(pts[n - 1]);
  return out;
}

function ellipsePoints(cx, cy, rx, ry, n = 48) {
  const pts = [];
  for (let i = 0; i < n; i++) {
    const t = (2 * Math.PI * i) / n;
    pts.push([cx + rx * Math.cos(t), cy + ry * Math.sin(t)]);
  }
  return pts;
}

/* ---------------------------------------------------------------- render */
function drawArrowHead(ctx, from, to, color, size, style) {
  if (style === 'none') return;
  const ang = Math.atan2(to[1] - from[1], to[0] - from[0]);
  ctx.save();
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = Math.max(1, size * 0.18);
  if (style === 'harpoon') {
    const a1 = ang + Math.PI - 0.5;
    ctx.beginPath();
    ctx.moveTo(to[0], to[1]);
    ctx.lineTo(to[0] + size * Math.cos(a1), to[1] + size * Math.sin(a1));
    ctx.stroke();
  } else if (style === 'classical') {
    const a1 = ang + Math.PI - 0.45, a2 = ang + Math.PI + 0.45;
    ctx.beginPath();
    ctx.moveTo(to[0] + size * Math.cos(a1), to[1] + size * Math.sin(a1));
    ctx.lineTo(to[0], to[1]);
    ctx.lineTo(to[0] + size * Math.cos(a2), to[1] + size * Math.sin(a2));
    ctx.stroke();
  } else {
    const a1 = ang + Math.PI - 0.4, a2 = ang + Math.PI + 0.4;
    const back = [to[0] + size * 0.55 * Math.cos(ang + Math.PI), to[1] + size * 0.55 * Math.sin(ang + Math.PI)];
    ctx.beginPath();
    ctx.moveTo(to[0], to[1]);
    ctx.lineTo(to[0] + size * Math.cos(a1), to[1] + size * Math.sin(a1));
    ctx.lineTo(back[0], back[1]);
    ctx.lineTo(to[0] + size * Math.cos(a2), to[1] + size * Math.sin(a2));
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
}

function applyLineStyle(ctx, s) {
  ctx.setLineDash(s.lineStyle === 'dashed' ? [Math.max(4, s.width * 3), Math.max(3, s.width * 2)]
    : s.lineStyle === 'dotted' ? [1, Math.max(3, s.width * 2)] : []);
}

function renderShape(ctx, s, selected) {
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  const sketchy = window.SKETCHY_MODE && !selected;

  if (s.type === 'stroke') {
    if (!s.segments.length) return;
    ctx.beginPath();
    ctx.moveTo(s.segments[0][0][0], s.segments[0][0][1]);
    for (const [, c1, c2, p3] of s.segments) ctx.bezierCurveTo(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1]);
    if (s.closed) ctx.closePath();
    if (s.filled) { ctx.fillStyle = s.fillColor || s.color; ctx.fill(); }
    if (sketchy) {
      let pts = [];
      for (const seg of s.segments) pts = pts.concat(flattenBezier(seg, 14));
      strokeSketchy(ctx, pts, s.closed, s.color, s.width);
    } else {
      applyLineStyle(ctx, s);
      ctx.strokeStyle = s.color; ctx.lineWidth = s.width; ctx.stroke();
    }
  } else if (s.type === 'line' || s.type === 'arrow') {
    if (s.bend) {
      const ctrl = bendControlPoint(s.p0, s.p1, s.bend);
      if (sketchy) {
        strokeSketchy(ctx, flattenQuadratic(s.p0, ctrl, s.p1, 16), false, s.color, s.width);
      } else {
        applyLineStyle(ctx, s);
        ctx.strokeStyle = s.color; ctx.lineWidth = s.width;
        ctx.beginPath();
        ctx.moveTo(s.p0[0], s.p0[1]);
        ctx.quadraticCurveTo(ctrl[0], ctrl[1], s.p1[0], s.p1[1]);
        ctx.stroke();
      }
      if (s.type === 'arrow') {
        // tangent at the curve's end (t=1) points from ctrl to p1
        const tdx = s.p1[0] - ctrl[0], tdy = s.p1[1] - ctrl[1];
        const tlen = Math.hypot(tdx, tdy) || 1;
        const synthFrom = [s.p1[0] - (tdx / tlen) * 40, s.p1[1] - (tdy / tlen) * 40];
        drawArrowHead(ctx, synthFrom, s.p1, s.color, Math.max(9, s.width * 4), s.headStyle || 'stealth');
      }
    } else {
      const shrink = s.type === 'arrow' && s.headStyle !== 'none' ? s.width * 3.2 : 0;
      const ang = Math.atan2(s.p1[1] - s.p0[1], s.p1[0] - s.p0[0]);
      const endPt = [s.p1[0] - shrink * Math.cos(ang), s.p1[1] - shrink * Math.sin(ang)];
      if (sketchy) {
        strokeSketchy(ctx, densify([s.p0, endPt], 8, false), false, s.color, s.width);
      } else {
        applyLineStyle(ctx, s);
        ctx.strokeStyle = s.color; ctx.lineWidth = s.width;
        ctx.beginPath();
        ctx.moveTo(s.p0[0], s.p0[1]);
        ctx.lineTo(endPt[0], endPt[1]);
        ctx.stroke();
      }
      if (s.type === 'arrow') drawArrowHead(ctx, s.p0, s.p1, s.color, Math.max(9, s.width * 4), s.headStyle || 'stealth');
    }
  } else if (s.type === 'ellipse') {
    ctx.beginPath();
    ctx.ellipse(s.cx, s.cy, Math.abs(s.rx), Math.abs(s.ry), 0, 0, Math.PI * 2);
    if (s.filled) { ctx.fillStyle = s.fillColor || s.color; ctx.fill(); }
    if (sketchy) {
      strokeSketchy(ctx, ellipsePoints(s.cx, s.cy, Math.abs(s.rx), Math.abs(s.ry), 56), true, s.color, s.width);
    } else {
      applyLineStyle(ctx, s);
      ctx.strokeStyle = s.color; ctx.lineWidth = s.width; ctx.stroke();
    }
  } else if (s.type === 'polygon') {
    if (s.points.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(s.points[0][0], s.points[0][1]);
    for (const p of s.points.slice(1)) ctx.lineTo(p[0], p[1]);
    if (s.closed) ctx.closePath();
    if (s.filled) { ctx.fillStyle = s.fillColor || s.color; ctx.fill(); }
    if (sketchy) {
      strokeSketchy(ctx, densify(s.points, 6, s.closed), s.closed, s.color, s.width);
    } else {
      applyLineStyle(ctx, s);
      ctx.strokeStyle = s.color; ctx.lineWidth = s.width; ctx.stroke();
    }
  } else if (s.type === 'text') {
    ctx.setLineDash([]);
    ctx.fillStyle = s.color;
    ctx.font = `${s.fontsize || 16}px "Latin Modern Math", "Cambria Math", Georgia, serif`;
    ctx.textBaseline = 'middle';
    const displayText = typeof latexToDisplay === 'function' ? latexToDisplay(s.text) : s.text;
    ctx.fillText(displayText, s.x, s.y);
  }
  if (selected) {
    const bb = shapeBBox(s);
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 1.2;
    ctx.strokeRect(bb[0] - 5, bb[1] - 5, (bb[2] - bb[0]) + 10, (bb[3] - bb[1]) + 10);
    ctx.restore();
  }
}
