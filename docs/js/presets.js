/*
 * presets.js
 * A small library of ready-made shapes, inserted centered on the canvas.
 * Mirrors a subset of the desktop app's presets.py (perfect Euclidean
 * shapes + a couple of topology sketches). More can be added over time.
 */

function regularPolygon(cx, cy, r, n, rotation = 0) {
  const pts = [];
  for (let i = 0; i < n; i++) {
    const a = rotation + (2 * Math.PI * i) / n;
    pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return pts;
}

function starPoints(cx, cy, rOut, rIn, nPoints = 5, rotation = -Math.PI / 2) {
  const pts = [];
  for (let i = 0; i < nPoints * 2; i++) {
    const r = i % 2 === 0 ? rOut : rIn;
    const a = rotation + (Math.PI * i) / nPoints;
    pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
  }
  return pts;
}

const PRESETS = {
  circle: (cx, cy, color, width) => [{ type: 'ellipse', cx, cy, rx: 60, ry: 60, color, width, lineStyle: 'solid', filled: false }],
  ellipse: (cx, cy, color, width) => [{ type: 'ellipse', cx, cy, rx: 90, ry: 55, color, width, lineStyle: 'solid', filled: false }],
  square: (cx, cy, color, width) => {
    const h = 55;
    return [{ type: 'polygon', points: [[cx - h, cy - h], [cx + h, cy - h], [cx + h, cy + h], [cx - h, cy + h]], closed: true, color, width, lineStyle: 'solid', filled: false }];
  },
  rectangle: (cx, cy, color, width) => {
    const w = 120, h = 80;
    return [{ type: 'polygon', points: [[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]], closed: true, color, width, lineStyle: 'solid', filled: false }];
  },
  triangle: (cx, cy, color, width) => [{ type: 'polygon', points: regularPolygon(cx, cy, 70, 3, -Math.PI / 2), closed: true, color, width, lineStyle: 'solid', filled: false }],
  pentagon: (cx, cy, color, width) => [{ type: 'polygon', points: regularPolygon(cx, cy, 70, 5, -Math.PI / 2), closed: true, color, width, lineStyle: 'solid', filled: false }],
  hexagon: (cx, cy, color, width) => [{ type: 'polygon', points: regularPolygon(cx, cy, 70, 6), closed: true, color, width, lineStyle: 'solid', filled: false }],
  star: (cx, cy, color, width) => [{ type: 'polygon', points: starPoints(cx, cy, 75, 30), closed: true, color, width, lineStyle: 'solid', filled: false }],
  annulus: (cx, cy, color, width) => [
    { type: 'ellipse', cx, cy, rx: 70, ry: 70, color, width, lineStyle: 'solid', filled: false },
    { type: 'ellipse', cx, cy, rx: 35, ry: 35, color, width, lineStyle: 'solid', filled: false },
  ],
  torus: (cx, cy, color, width) => [
    { type: 'ellipse', cx, cy, rx: 100, ry: 55, color, width, lineStyle: 'solid', filled: false },
    { type: 'ellipse', cx, cy, rx: 45, ry: 22, color, width, lineStyle: 'solid', filled: false },
    { type: 'ellipse', cx, cy, rx: 25, ry: 55, color, width: width * 0.8, lineStyle: 'solid', filled: false },
  ],
  double_arrow: (cx, cy, color, width) => [
    { type: 'arrow', p0: [cx - 80, cy], p1: [cx + 80, cy], color, width, lineStyle: 'solid', headStyle: 'stealth' },
    { type: 'arrow', p0: [cx + 80, cy], p1: [cx - 80, cy], color, width, lineStyle: 'solid', headStyle: 'stealth' },
  ],
};

const PRESET_LABELS = {
  circle: 'Perfect circle',
  ellipse: 'Perfect ellipse',
  square: 'Square',
  rectangle: 'Rectangle',
  triangle: 'Equilateral triangle',
  pentagon: 'Regular pentagon',
  hexagon: 'Regular hexagon',
  star: '5-point star',
  annulus: 'Annulus (ring)',
  torus: 'Torus (meridian + longitude)',
  double_arrow: 'Double-headed arrow',
};

function buildPreset(name, cx, cy, color, width) {
  const fn = PRESETS[name];
  return fn ? fn(cx, cy, color, width) : [];
}
