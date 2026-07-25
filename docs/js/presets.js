/*
 * presets.js
 * Ready-made shape templates (JS port of the desktop app's presets.py),
 * inserted centered on the current view. Reuses the existing 'ellipse',
 * 'polygon', 'stroke' and 'line' shape types, so rendering, selection,
 * TikZ/SVG export and undo/redo all work on them exactly like hand-drawn
 * shapes -- no special-casing needed anywhere else in the app.
 */

const PRESET_LABELS = {
  circle: 'Perfect circle',
  ellipse: 'Perfect ellipse',
  square: 'Square',
  rectangle: 'Rectangle',
  triangle: 'Equilateral triangle',
  pentagon: 'Regular pentagon',
  hexagon: 'Regular hexagon',
  star: '5-point star',
  rhombus: 'Rhombus / diamond',
  trapezoid: 'Trapezoid',
  annulus: 'Annulus (ring)',
  cross: 'Cross / plus mark',
  lens: 'Lens / eye mark (Dj style)',
  torus: 'Torus (meridian + longitude)',
};

const PRESET_NAMES = Object.keys(PRESET_LABELS);

function regularPolygonPoints(cx, cy, r, n, rotation = 0) {
  const pts = [];
  for (let i = 0; i < n; i++) {
    const ang = rotation + (2 * Math.PI * i) / n;
    pts.push([cx + r * Math.cos(ang), cy + r * Math.sin(ang)]);
  }
  return pts;
}

function starPoints(cx, cy, rOut, rIn, nPoints = 5, rotation = -Math.PI / 2) {
  const pts = [];
  for (let i = 0; i < nPoints * 2; i++) {
    const r = i % 2 === 0 ? rOut : rIn;
    const ang = rotation + (Math.PI * i) / nPoints;
    pts.push([cx + r * Math.cos(ang), cy + r * Math.sin(ang)]);
  }
  return pts;
}

function buildPreset(name, cx, cy, scale, color, width) {
  const s = scale;
  const base = { color, width, lineStyle: 'solid' };

  if (name === 'circle') {
    return [{ type: 'ellipse', cx, cy, rx: 60 * s, ry: 60 * s, filled: false, fillColor: null, ...base }];
  }
  if (name === 'ellipse') {
    return [{ type: 'ellipse', cx, cy, rx: 90 * s, ry: 55 * s, filled: false, fillColor: null, ...base }];
  }
  if (name === 'square') {
    const h = 55 * s;
    const pts = [[cx - h, cy - h], [cx + h, cy - h], [cx + h, cy + h], [cx - h, cy + h]];
    return [{ type: 'polygon', points: pts, closed: true, filled: false, fillColor: null, ...base }];
  }
  if (name === 'rectangle') {
    const w = 60 * s, h = 40 * s;
    const pts = [[cx - w, cy - h], [cx + w, cy - h], [cx + w, cy + h], [cx - w, cy + h]];
    return [{ type: 'polygon', points: pts, closed: true, filled: false, fillColor: null, ...base }];
  }
  if (name === 'triangle') {
    return [{ type: 'polygon', points: regularPolygonPoints(cx, cy, 70 * s, 3, -Math.PI / 2), closed: true, filled: false, fillColor: null, ...base }];
  }
  if (name === 'pentagon') {
    return [{ type: 'polygon', points: regularPolygonPoints(cx, cy, 70 * s, 5, -Math.PI / 2), closed: true, filled: false, fillColor: null, ...base }];
  }
  if (name === 'hexagon') {
    return [{ type: 'polygon', points: regularPolygonPoints(cx, cy, 70 * s, 6, 0), closed: true, filled: false, fillColor: null, ...base }];
  }
  if (name === 'star') {
    return [{ type: 'polygon', points: starPoints(cx, cy, 75 * s, 30 * s), closed: true, filled: false, fillColor: null, ...base }];
  }
  if (name === 'rhombus') {
    const pts = [[cx, cy - 70 * s], [cx + 45 * s, cy], [cx, cy + 70 * s], [cx - 45 * s, cy]];
    return [{ type: 'polygon', points: pts, closed: true, filled: false, fillColor: null, ...base }];
  }
  if (name === 'trapezoid') {
    const pts = [[cx - 70 * s, cy + 40 * s], [cx + 70 * s, cy + 40 * s], [cx + 40 * s, cy - 40 * s], [cx - 40 * s, cy - 40 * s]];
    return [{ type: 'polygon', points: pts, closed: true, filled: false, fillColor: null, ...base }];
  }
  if (name === 'annulus') {
    return [
      { type: 'ellipse', cx, cy, rx: 70 * s, ry: 70 * s, filled: false, fillColor: null, ...base },
      { type: 'ellipse', cx, cy, rx: 35 * s, ry: 35 * s, filled: false, fillColor: null, ...base },
    ];
  }
  if (name === 'cross') {
    return [
      { type: 'line', p0: [cx - 45 * s, cy], p1: [cx + 45 * s, cy], bend: 0, ...base },
      { type: 'line', p0: [cx, cy - 45 * s], p1: [cx, cy + 45 * s], bend: 0, ...base },
    ];
  }
  if (name === 'lens') {
    // A perfectly symmetric lens/vesica ("eye") mark: two arcs meeting at
    // two sharp tips -- exactly the shape used for D1/D2/D3-style
    // degeneracy-locus markings, with zero hand-drawn wobble.
    const a = 26 * s, b = 9 * s, k = 0.9;
    return [
      { type: 'stroke', segments: [[[cx - a, cy], [cx - a * k, cy - b], [cx + a * k, cy - b], [cx + a, cy]]], closed: false, filled: false, fillColor: null, ...base },
      { type: 'stroke', segments: [[[cx - a, cy], [cx - a * k, cy + b], [cx + a * k, cy + b], [cx + a, cy]]], closed: false, filled: false, fillColor: null, ...base },
    ];
  }
  if (name === 'torus') {
    return [
      { type: 'ellipse', cx, cy, rx: 100 * s, ry: 55 * s, filled: false, fillColor: null, ...base },
      { type: 'ellipse', cx, cy, rx: 45 * s, ry: 22 * s, filled: false, fillColor: null, ...base },
      { type: 'ellipse', cx, cy, rx: 25 * s, ry: 55 * s, filled: false, fillColor: null, ...base, width: width * 0.8 },
    ];
  }
  return [];
}
