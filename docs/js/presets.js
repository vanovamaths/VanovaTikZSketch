/*
 * presets.js
 * Publication-friendly geometry templates. Every preset is built only from
 * the app's existing ellipse/polygon/stroke/line/arrow primitives, so all
 * editing, selection, TikZ/SVG export, undo/redo and transforms work without
 * a separate rendering path.
 */

const PRESET_LABELS = {
  circle: 'Circle',
  ellipse: 'Ellipse',
  semicircle: 'Semicircle',
  annulus: 'Annulus / ring',
  sector: 'Circular sector',
  square: 'Square',
  rectangle: 'Rectangle',
  triangle: 'Equilateral triangle',
  right_triangle: 'Right triangle',
  isosceles_triangle: 'Isosceles triangle',
  pentagon: 'Regular pentagon',
  hexagon: 'Regular hexagon',
  octagon: 'Regular octagon',
  decagon: 'Regular decagon',
  rhombus: 'Rhombus / diamond',
  parallelogram: 'Parallelogram',
  trapezoid: 'Trapezoid',
  kite: 'Kite',
  star: '5-point star',
  cross: 'Cross / plus mark',
  axes: 'Coordinate axes',
  angle: 'Angle',
  right_angle: 'Right angle marker',
  parabola: 'Parabola',
  hyperbola: 'Hyperbola',
  sine: 'Sine curve',
  spiral: 'Archimedean spiral',
  lens: 'Lens / eye mark',
  sphere: 'Sphere / globe',
  cylinder: 'Cylinder',
  cone: 'Cone',
  cube: 'Cube',
  torus: 'Torus (schematic)',
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

function sampleCurve(fn, t0, t1, steps) {
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const t = t0 + (t1 - t0) * (i / steps);
    pts.push(fn(t));
  }
  return pts;
}

function poly(points, base, closed = true, filled = false, fillColor = null) {
  return { type: 'polygon', points, closed, filled, fillColor, ...base };
}

function line(p0, p1, base, extra = {}) {
  return { type: 'line', p0, p1, bend: 0, ...base, ...extra };
}

function arrow(p0, p1, base, extra = {}) {
  return { type: 'arrow', p0, p1, headStyle: 'stealth', bend: 0, ...base, ...extra };
}

function ellipse(cx, cy, rx, ry, base, extra = {}) {
  return { type: 'ellipse', cx, cy, rx, ry, filled: false, fillColor: null, ...base, ...extra };
}

function cubic(p0, c1, c2, p3, base, extra = {}) {
  return { type: 'stroke', segments: [[p0, c1, c2, p3]], closed: false, filled: false, fillColor: null, ...base, ...extra };
}

function buildPreset(name, cx, cy, scale, color, width) {
  const s = scale;
  const base = { color, width, lineStyle: 'solid' };

  if (name === 'circle') return [ellipse(cx, cy, 60 * s, 60 * s, base)];
  if (name === 'ellipse') return [ellipse(cx, cy, 90 * s, 55 * s, base)];
  if (name === 'semicircle') {
    const pts = sampleCurve((t) => [cx + 72 * s * Math.cos(t), cy - 72 * s * Math.sin(t)], 0, Math.PI, 40);
    return [poly(pts, base, false)];
  }
  if (name === 'annulus') return [ellipse(cx, cy, 70 * s, 70 * s, base), ellipse(cx, cy, 36 * s, 36 * s, base)];
  if (name === 'sector') {
    const arc = sampleCurve((t) => [cx + 72 * s * Math.cos(t), cy + 72 * s * Math.sin(t)], -Math.PI * 0.72, Math.PI * 0.18, 30);
    return [poly([[cx, cy], ...arc], base, true)];
  }
  if (name === 'square') {
    const h = 56 * s;
    return [poly([[cx-h,cy-h],[cx+h,cy-h],[cx+h,cy+h],[cx-h,cy+h]], base)];
  }
  if (name === 'rectangle') {
    const w = 78 * s, h = 48 * s;
    return [poly([[cx-w,cy-h],[cx+w,cy-h],[cx+w,cy+h],[cx-w,cy+h]], base)];
  }
  if (name === 'triangle') return [poly(regularPolygonPoints(cx, cy, 72 * s, 3, -Math.PI / 2), base)];
  if (name === 'right_triangle') return [poly([[cx-68*s,cy+54*s],[cx+68*s,cy+54*s],[cx-68*s,cy-54*s]], base)];
  if (name === 'isosceles_triangle') return [poly([[cx,cy-70*s],[cx+66*s,cy+55*s],[cx-66*s,cy+55*s]], base)];
  if (name === 'pentagon') return [poly(regularPolygonPoints(cx, cy, 72 * s, 5, -Math.PI / 2), base)];
  if (name === 'hexagon') return [poly(regularPolygonPoints(cx, cy, 72 * s, 6, 0), base)];
  if (name === 'octagon') return [poly(regularPolygonPoints(cx, cy, 72 * s, 8, Math.PI / 8), base)];
  if (name === 'decagon') return [poly(regularPolygonPoints(cx, cy, 72 * s, 10, -Math.PI / 2), base)];
  if (name === 'rhombus') return [poly([[cx,cy-72*s],[cx+50*s,cy],[cx,cy+72*s],[cx-50*s,cy]], base)];
  if (name === 'parallelogram') return [poly([[cx-72*s,cy+46*s],[cx+48*s,cy+46*s],[cx+72*s,cy-46*s],[cx-48*s,cy-46*s]], base)];
  if (name === 'trapezoid') return [poly([[cx-76*s,cy+46*s],[cx+76*s,cy+46*s],[cx+44*s,cy-46*s],[cx-44*s,cy-46*s]], base)];
  if (name === 'kite') return [poly([[cx,cy-78*s],[cx+52*s,cy-8*s],[cx,cy+72*s],[cx-38*s,cy-8*s]], base)];
  if (name === 'star') return [poly(starPoints(cx, cy, 78*s, 32*s), base)];
  if (name === 'cross') return [line([cx-52*s,cy],[cx+52*s,cy],base), line([cx,cy-52*s],[cx,cy+52*s],base)];

  if (name === 'axes') {
    return [
      arrow([cx-95*s,cy],[cx+105*s,cy],base),
      arrow([cx,cy+85*s],[cx,cy-95*s],base),
      line([cx-6*s,cy-35*s],[cx+6*s,cy-35*s],base,{width:Math.max(1,width*.7)}),
      line([cx+40*s,cy-6*s],[cx+40*s,cy+6*s],base,{width:Math.max(1,width*.7)}),
    ];
  }
  if (name === 'angle') {
    const r = 42 * s;
    const arcPts = sampleCurve((t) => [cx + r*Math.cos(t), cy - r*Math.sin(t)], 0, Math.PI/3, 18);
    return [line([cx,cy],[cx+92*s,cy],base), line([cx,cy],[cx+72*s,cy-62*s],base), poly(arcPts,base,false)];
  }
  if (name === 'right_angle') {
    const q = 22 * s;
    return [poly([[cx-q,cy],[cx-q,cy-q],[cx,cy-q]],base,false)];
  }
  if (name === 'parabola') {
    const pts = sampleCurve((t) => [cx + t*72*s, cy + (t*t*54 - 38)*s], -1.35, 1.35, 64);
    return [poly(pts, base, false)];
  }
  if (name === 'hyperbola') {
    const left = sampleCurve((t) => [cx - 36*s*Math.cosh(t), cy + 36*s*Math.sinh(t)], -1.05, 1.05, 42);
    const right = sampleCurve((t) => [cx + 36*s*Math.cosh(t), cy + 36*s*Math.sinh(t)], -1.05, 1.05, 42);
    return [poly(left, base, false), poly(right, base, false)];
  }
  if (name === 'sine') {
    const pts = sampleCurve((t) => [cx + t*30*s, cy - Math.sin(t)*44*s], -Math.PI*2.2, Math.PI*2.2, 120);
    return [poly(pts, base, false)];
  }
  if (name === 'spiral') {
    const pts = sampleCurve((t) => {
      const r = 4*s + 4.4*s*t;
      return [cx + r*Math.cos(t), cy + r*Math.sin(t)];
    }, 0, Math.PI*5.2, 150);
    return [poly(pts, base, false)];
  }

  if (name === 'lens') {
    const a = 34*s, b = 14*s, k = .9;
    return [
      cubic([cx-a,cy],[cx-a*k,cy-b],[cx+a*k,cy-b],[cx+a,cy],base),
      cubic([cx-a,cy],[cx-a*k,cy+b],[cx+a*k,cy+b],[cx+a,cy],base),
    ];
  }
  if (name === 'sphere') {
    return [
      ellipse(cx,cy,72*s,72*s,base),
      ellipse(cx,cy,72*s,26*s,base),
      ellipse(cx,cy,25*s,72*s,base),
    ];
  }
  if (name === 'cylinder') {
    return [
      ellipse(cx,cy-55*s,68*s,24*s,base),
      ellipse(cx,cy+55*s,68*s,24*s,base),
      line([cx-68*s,cy-55*s],[cx-68*s,cy+55*s],base),
      line([cx+68*s,cy-55*s],[cx+68*s,cy+55*s],base),
    ];
  }
  if (name === 'cone') {
    return [
      ellipse(cx,cy+54*s,72*s,23*s,base),
      line([cx,cy-78*s],[cx-72*s,cy+54*s],base),
      line([cx,cy-78*s],[cx+72*s,cy+54*s],base),
    ];
  }
  if (name === 'cube') {
    const a=52*s, d=26*s;
    const front=[[cx-a,cy-a],[cx+a,cy-a],[cx+a,cy+a],[cx-a,cy+a]];
    const back=front.map(([x,y])=>[x+d,y-d]);
    return [
      poly(front,base), poly(back,base),
      line(front[0],back[0],base), line(front[1],back[1],base),
      line(front[2],back[2],base), line(front[3],back[3],base),
    ];
  }
  if (name === 'torus') {
    return [
      ellipse(cx,cy,104*s,58*s,base),
      ellipse(cx,cy,46*s,23*s,base),
      ellipse(cx,cy,28*s,58*s,base,{width:Math.max(1,width*.8)}),
    ];
  }
  return [];
}
