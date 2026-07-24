/*
 * shapes.js
 * Plain-object shape model (mirrors the desktop app's shapes.py), plus
 * bbox / translate / clone helpers and the canvas render routine.
 */

const HEAD_STYLES = ['stealth', 'classical', 'harpoon', 'none'];

function shapeBBox(s) {
  if (s.type === 'stroke') {
    let xs = [], ys = [];
    for (const seg of s.segments) for (const p of seg) { xs.push(p[0]); ys.push(p[1]); }
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  }
  if (s.type === 'line' || s.type === 'arrow') {
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
    const w = Math.max(20, 8 * s.text.length);
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
  if (s.type === 'stroke') {
    if (!s.segments.length) return;
    ctx.beginPath();
    ctx.moveTo(s.segments[0][0][0], s.segments[0][0][1]);
    for (const [, c1, c2, p3] of s.segments) ctx.bezierCurveTo(c1[0], c1[1], c2[0], c2[1], p3[0], p3[1]);
    if (s.closed) ctx.closePath();
    if (s.filled) { ctx.fillStyle = s.fillColor || s.color; ctx.fill(); }
    applyLineStyle(ctx, s);
    ctx.strokeStyle = s.color; ctx.lineWidth = s.width; ctx.stroke();
  } else if (s.type === 'line' || s.type === 'arrow') {
    applyLineStyle(ctx, s);
    ctx.strokeStyle = s.color; ctx.lineWidth = s.width;
    const shrink = s.type === 'arrow' && s.headStyle !== 'none' ? s.width * 3.2 : 0;
    const ang = Math.atan2(s.p1[1] - s.p0[1], s.p1[0] - s.p0[0]);
    const endPt = [s.p1[0] - shrink * Math.cos(ang), s.p1[1] - shrink * Math.sin(ang)];
    ctx.beginPath();
    ctx.moveTo(s.p0[0], s.p0[1]);
    ctx.lineTo(endPt[0], endPt[1]);
    ctx.stroke();
    if (s.type === 'arrow') drawArrowHead(ctx, s.p0, s.p1, s.color, Math.max(9, s.width * 4), s.headStyle || 'stealth');
  } else if (s.type === 'ellipse') {
    ctx.beginPath();
    ctx.ellipse(s.cx, s.cy, Math.abs(s.rx), Math.abs(s.ry), 0, 0, Math.PI * 2);
    if (s.filled) { ctx.fillStyle = s.fillColor || s.color; ctx.fill(); }
    applyLineStyle(ctx, s);
    ctx.strokeStyle = s.color; ctx.lineWidth = s.width; ctx.stroke();
  } else if (s.type === 'polygon') {
    if (s.points.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(s.points[0][0], s.points[0][1]);
    for (const p of s.points.slice(1)) ctx.lineTo(p[0], p[1]);
    if (s.closed) ctx.closePath();
    if (s.filled) { ctx.fillStyle = s.fillColor || s.color; ctx.fill(); }
    applyLineStyle(ctx, s);
    ctx.strokeStyle = s.color; ctx.lineWidth = s.width; ctx.stroke();
  } else if (s.type === 'text') {
    ctx.setLineDash([]);
    ctx.fillStyle = s.color;
    ctx.font = `${s.fontsize || 16}px "Latin Modern Math", "Cambria Math", Georgia, serif`;
    ctx.textBaseline = 'middle';
    ctx.fillText(s.text, s.x, s.y);
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
