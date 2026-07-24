/*
 * presets.js
 * Full JS port of the desktop app's presets.py: basic Euclidean shapes,
 * topology sketches (torus, genus-2 surface, Mobius strip, Klein bottle,
 * handle, lens...), and the differential-geometry diagram library (charts/
 * atlas, tangent/normal vector, vector field, fiber bundle, Lie groupoid,
 * commutative square, foliation). Inserted centered on the canvas, then
 * repositioned with the Select tool.
 */

/* ------------------------------------------------------------- helpers */
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

/** Uniform Catmull-Rom -> cubic Bezier for a CLOSED loop through anchors. */
function catmullRomClosedBezier(anchors, tension = 1.0) {
  const n = anchors.length;
  const segments = [];
  for (let i = 0; i < n; i++) {
    const p0 = anchors[(i - 1 + n) % n], p1 = anchors[i % n], p2 = anchors[(i + 1) % n], p3 = anchors[(i + 2) % n];
    const c1 = [p1[0] + ((p2[0] - p0[0]) / 6) * tension, p1[1] + ((p2[1] - p0[1]) / 6) * tension];
    const c2 = [p2[0] - ((p3[0] - p1[0]) / 6) * tension, p2[1] - ((p3[1] - p1[1]) / 6) * tension];
    segments.push([p1, c1, c2, p2]);
  }
  return segments;
}

const DEFAULT_WOBBLE = [1.0, 0.84, 1.08, 0.88, 1.14, 0.8, 1.06, 0.92];

/** Irregular but clean closed outline -- the generic "blob" silhouette used
 * for a manifold or a chart region U in textbook atlas diagrams. */
function blobSegments(cx, cy, rx, ry, radiusFactors = null, rotation = 0) {
  const factors = radiusFactors || DEFAULT_WOBBLE;
  const n = factors.length;
  const anchors = [];
  for (let i = 0; i < n; i++) {
    const f = factors[i];
    anchors.push([cx + rx * f * Math.cos(rotation + (2 * Math.PI * i) / n),
                   cy + ry * f * Math.sin(rotation + (2 * Math.PI * i) / n)]);
  }
  return catmullRomClosedBezier(anchors);
}

/** Tiny loop mark hinting "there's a handle here" inside a manifold blob. */
function smallLoopIcon(cx, cy, s = 1.0) {
  return blobSegments(cx, cy, 13 * s, 8 * s, [1.0, 0.35, 1.0, 0.35, 1.0, 0.35]);
}

/** A little R^n coordinate cross under a chart-image plane. */
function coordAxes(cx, cy, length, color, width) {
  return [
    arrowShape([cx - length * 0.12, cy], [cx + length, cy], color, width * 0.75),
    arrowShape([cx, cy + length * 0.12], [cx, cy - length], color, width * 0.75),
  ];
}

/* -------------------------------------------------------- shape factories */
function ellipseShape(cx, cy, rx, ry, color, width, opts = {}) {
  return { type: 'ellipse', cx, cy, rx, ry, color, width, lineStyle: opts.dashed ? 'dashed' : 'solid', filled: !!opts.filled, fillColor: opts.fillColor || null };
}
function lineShape(p0, p1, color, width) {
  return { type: 'line', p0, p1, color, width, lineStyle: 'solid' };
}
function arrowShape(p0, p1, color, width) {
  return { type: 'arrow', p0, p1, color, width, lineStyle: 'solid', headStyle: 'stealth' };
}
function polygonShape(points, color, width, closed, opts = {}) {
  return { type: 'polygon', points, closed, color, width, lineStyle: opts.dashed ? 'dashed' : 'solid', filled: !!opts.filled, fillColor: opts.fillColor || null };
}
function strokeShape(segments, color, width, closed, opts = {}) {
  return { type: 'stroke', segments, closed: !!closed, color, width, lineStyle: opts.dashed ? 'dashed' : (opts.lineStyle || 'solid'), filled: !!opts.filled, fillColor: opts.fillColor || null };
}
function textShape(x, y, text, color, opts = {}) {
  return { type: 'text', x, y, text, latex: !!opts.latex, color, fontsize: opts.fontsize || 16 };
}

/* ------------------------------------------------------------------ list */
const PRESET_LABELS = {
  circle: 'Perfect circle',
  ellipse: 'Perfect ellipse',
  square: 'Square',
  rectangle: 'Perfect rectangle',
  triangle: 'Equilateral triangle',
  pentagon: 'Regular pentagon',
  hexagon: 'Regular hexagon',
  star: '5-point star',
  rhombus: 'Rhombus / diamond',
  trapezoid: 'Trapezoid',
  parallelogram: 'Parallelogram',
  sector: 'Circular sector (pie slice)',
  annulus: 'Annulus (ring)',
  cross: 'Cross / plus mark',
  double_arrow: 'Double-headed arrow',
  right_angle_mark: 'Right-angle mark',
  lens: 'Lens / eye mark',
  handle: 'Handle (with hatch marks)',
  torus: 'Torus (meridian + longitude)',
  genus2_surface: 'Genus-2 surface (sketch)',
  genus2_curves_tau_sigma: 'Genus-2 surface with tau/sigma/tau1/tau2 curves',
  cusp_mark: 'Cusp / fold singularity mark',
  mobius_strip: 'Mobius strip (sketch)',
  klein_bottle: 'Klein bottle (sketch)',
  chart_single: 'Chart map (manifold, U, phi, tilde U)',
  chart_atlas_two: 'Atlas: two charts + transition map',
  tangent_vector: 'Tangent vector T_pM at a point',
  normal_vector: 'Normal vector at a point',
  vector_field: 'Vector field along a curve',
  fiber_bundle: 'Fiber bundle (E, pi, B, fiber F)',
  lie_groupoid: 'Lie groupoid (G rightrightarrows M)',
  commutative_square: 'Commutative diagram (square)',
  foliation: 'Foliation / symplectic leaves',
};

/* --------------------------------------------------------------- builder */
function buildPreset(name, cx, cy, color, width, scale = 1.0) {
  const s = scale;

  if (name === 'circle') {
    const r = 60 * s;
    return [ellipseShape(cx, cy, r, r, color, width)];
  }

  if (name === 'ellipse') {
    return [ellipseShape(cx, cy, 90 * s, 55 * s, color, width)];
  }

  if (name === 'rectangle') {
    const w = 120 * s, h = 80 * s;
    const pts = [[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2], [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]];
    return [polygonShape(pts, color, width, true)];
  }

  if (name === 'triangle') {
    return [polygonShape(regularPolygon(cx, cy, 70 * s, 3, -Math.PI / 2), color, width, true)];
  }

  if (name === 'square') {
    const half = 55 * s;
    const pts = [[cx - half, cy - half], [cx + half, cy - half], [cx + half, cy + half], [cx - half, cy + half]];
    return [polygonShape(pts, color, width, true)];
  }

  if (name === 'pentagon') {
    return [polygonShape(regularPolygon(cx, cy, 70 * s, 5, -Math.PI / 2), color, width, true)];
  }

  if (name === 'hexagon') {
    return [polygonShape(regularPolygon(cx, cy, 70 * s, 6), color, width, true)];
  }

  if (name === 'star') {
    return [polygonShape(starPoints(cx, cy, 75 * s, 30 * s), color, width, true)];
  }

  if (name === 'rhombus') {
    const pts = [[cx, cy - 70 * s], [cx + 45 * s, cy], [cx, cy + 70 * s], [cx - 45 * s, cy]];
    return [polygonShape(pts, color, width, true)];
  }

  if (name === 'trapezoid') {
    const pts = [[cx - 70 * s, cy + 40 * s], [cx + 70 * s, cy + 40 * s], [cx + 40 * s, cy - 40 * s], [cx - 40 * s, cy - 40 * s]];
    return [polygonShape(pts, color, width, true)];
  }

  if (name === 'parallelogram') {
    const pts = [[cx - 70 * s, cy + 35 * s], [cx + 40 * s, cy + 35 * s], [cx + 70 * s, cy - 35 * s], [cx - 40 * s, cy - 35 * s]];
    return [polygonShape(pts, color, width, true)];
  }

  if (name === 'sector') {
    const r = 75 * s;
    const a0 = (-35 * Math.PI) / 180, a1 = (35 * Math.PI) / 180;
    const n = 24;
    const pts = [[cx, cy]];
    for (let i = 0; i <= n; i++) {
      const a = a0 + (a1 - a0) * (i / n);
      pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
    }
    return [polygonShape(pts, color, width, true)];
  }

  if (name === 'annulus') {
    return [ellipseShape(cx, cy, 70 * s, 70 * s, color, width), ellipseShape(cx, cy, 35 * s, 35 * s, color, width)];
  }

  if (name === 'cross') {
    return [
      lineShape([cx - 45 * s, cy], [cx + 45 * s, cy], color, width),
      lineShape([cx, cy - 45 * s], [cx, cy + 45 * s], color, width),
    ];
  }

  if (name === 'double_arrow') {
    const p0 = [cx - 75 * s, cy], p1 = [cx + 75 * s, cy];
    return [arrowShape(p0, p1, color, width), arrowShape(p1, p0, color, width)];
  }

  if (name === 'right_angle_mark') {
    const size = 14 * s;
    const pts = [[cx, cy - size], [cx + size, cy - size], [cx + size, cy]];
    return [polygonShape(pts, color, width * 0.7, false)];
  }

  if (name === 'lens') {
    const a = 26 * s, b = 9 * s, k = 0.9;
    const top = strokeShape([[[cx - a, cy], [cx - a * k, cy - b], [cx + a * k, cy - b], [cx + a, cy]]], color, width, false);
    const bottom = strokeShape([[[cx - a, cy], [cx - a * k, cy + b], [cx + a * k, cy + b], [cx + a, cy]]], color, width, false);
    return [top, bottom];
  }

  if (name === 'handle') {
    const rx = 45 * s, ry = 20 * s;
    const top = strokeShape([[[cx - rx, cy], [cx - rx * 0.4, cy - ry], [cx + rx * 0.4, cy - ry], [cx + rx, cy]]], color, width, false);
    const base = lineShape([cx - rx * 1.6, cy], [cx + rx * 1.6, cy], color, width);
    const h1 = lineShape([cx - rx * 0.5, cy - 6 * s], [cx - rx * 0.5, cy + 6 * s], color, width * 0.7);
    const h2 = lineShape([cx, cy - 6 * s], [cx, cy + 6 * s], color, width * 0.7);
    const h3 = lineShape([cx + rx * 0.5, cy - 6 * s], [cx + rx * 0.5, cy + 6 * s], color, width * 0.7);
    return [base, top, h1, h2, h3];
  }

  if (name === 'torus') {
    const outer = ellipseShape(cx, cy, 100 * s, 55 * s, color, width);
    const inner = ellipseShape(cx, cy, 45 * s, 22 * s, color, width);
    const meridian = ellipseShape(cx, cy, 25 * s, 55 * s, color, width * 0.8);
    return [outer, inner, meridian];
  }

  if (name === 'genus2_surface' || name === 'genus2_curves_tau_sigma') {
    // "peanut" silhouette (two humps) + two handles
    const body = strokeShape([
      [[cx - 160 * s, cy], [cx - 160 * s, cy - 70 * s], [cx - 90 * s, cy - 80 * s], [cx - 40 * s, cy - 55 * s]],
      [[cx - 40 * s, cy - 55 * s], [cx - 10 * s, cy - 40 * s], [cx + 10 * s, cy - 40 * s], [cx + 40 * s, cy - 55 * s]],
      [[cx + 40 * s, cy - 55 * s], [cx + 90 * s, cy - 80 * s], [cx + 160 * s, cy - 70 * s], [cx + 160 * s, cy]],
      [[cx + 160 * s, cy], [cx + 160 * s, cy + 70 * s], [cx + 90 * s, cy + 80 * s], [cx + 40 * s, cy + 55 * s]],
      [[cx + 40 * s, cy + 55 * s], [cx + 10 * s, cy + 40 * s], [cx - 10 * s, cy + 40 * s], [cx - 40 * s, cy + 55 * s]],
      [[cx - 40 * s, cy + 55 * s], [cx - 90 * s, cy + 80 * s], [cx - 160 * s, cy + 70 * s], [cx - 160 * s, cy]],
    ], color, width, true);

    function handle(hx, hy) {
      const rx = 30 * s, ry = 14 * s;
      const top = strokeShape([[[hx - rx, hy], [hx - rx * 0.4, hy - ry], [hx + rx * 0.4, hy - ry], [hx + rx, hy]]], color, width, false);
      const h1 = lineShape([hx - rx * 0.4, hy - 5 * s], [hx - rx * 0.4, hy + 5 * s], color, width * 0.7);
      const h2 = lineShape([hx + rx * 0.4, hy - 5 * s], [hx + rx * 0.4, hy + 5 * s], color, width * 0.7);
      return [top, h1, h2];
    }

    const leftHx = cx - 90 * s, leftHy = cy - 20 * s;
    const rightHx = cx + 90 * s, rightHy = cy - 20 * s;
    const shapes = [body, ...handle(leftHx, leftHy), ...handle(rightHx, rightHy)];

    if (name === 'genus2_surface') return shapes;

    // genus2_curves_tau_sigma: add tau_1, tau_2, sigma, tau curves + labels
    const tau1 = ellipseShape(leftHx, leftHy - 2 * s, 20 * s, 34 * s, color, width * 0.85);
    const tau2 = ellipseShape(rightHx, rightHy - 2 * s, 20 * s, 34 * s, color, width * 0.85);
    const sigma = ellipseShape(cx, cy, 14 * s, 70 * s, color, width * 0.85);
    const tau = strokeShape([
      [[cx - 90 * s, cy + 34 * s], [cx - 70 * s, cy + 60 * s], [cx - 20 * s, cy + 60 * s], [cx, cy + 34 * s]],
      [[cx, cy + 34 * s], [cx + 20 * s, cy + 8 * s], [cx + 70 * s, cy + 8 * s], [cx + 90 * s, cy + 34 * s]],
    ], color, width * 0.85, false, { dashed: true });
    const labelTau1 = textShape(leftHx, leftHy - 45 * s, '$\\tau_1$', color, { latex: true });
    const labelTau2 = textShape(rightHx, rightHy - 45 * s, '$\\tau_2$', color, { latex: true });
    const labelSigma = textShape(cx, cy - 90 * s, '$\\sigma$', color, { latex: true });
    const labelTau = textShape(cx, cy + 68 * s, '$\\tau$', color, { latex: true });
    shapes.push(tau1, tau2, sigma, tau, labelTau1, labelTau2, labelSigma, labelTau);
    return shapes;
  }

  if (name === 'cusp_mark') {
    const left = strokeShape([[[cx - 22 * s, cy - 22 * s], [cx - 14 * s, cy], [cx - 6 * s, cy + 14 * s], [cx, cy + 24 * s]]], color, width, false);
    const right = strokeShape([[[cx, cy + 24 * s], [cx + 6 * s, cy + 14 * s], [cx + 14 * s, cy], [cx + 22 * s, cy - 22 * s]]], color, width, false);
    return [left, right];
  }

  if (name === 'mobius_strip') {
    const outer = strokeShape(blobSegments(cx, cy, 110 * s, 55 * s, [1.0, 0.95, 1.05, 0.9, 1.08, 0.92]), color, width, true);
    const twist = strokeShape([[[cx - 90 * s, cy - 12 * s], [cx - 30 * s, cy + 30 * s], [cx + 30 * s, cy - 30 * s], [cx + 90 * s, cy + 12 * s]]], color, width * 0.9, false);
    const arrow1 = arrowShape([cx - 55 * s, cy - 2 * s], [cx - 40 * s, cy + 12 * s], color, width * 0.8);
    const arrow2 = arrowShape([cx + 55 * s, cy + 2 * s], [cx + 40 * s, cy - 12 * s], color, width * 0.8);
    return [outer, twist, arrow1, arrow2];
  }

  if (name === 'klein_bottle') {
    const body = strokeShape(blobSegments(cx, cy + 25 * s, 55 * s, 80 * s, [1.0, 0.92, 1.06, 0.9, 1.1, 0.9, 1.06, 0.92]), color, width, true);
    const neckOuter = strokeShape([
      [[cx - 8 * s, cy - 55 * s], [cx + 45 * s, cy - 70 * s], [cx + 70 * s, cy - 30 * s], [cx + 45 * s, cy]],
      [[cx + 45 * s, cy], [cx + 20 * s, cy + 22 * s], [cx + 5 * s, cy + 10 * s], [cx + 12 * s, cy - 10 * s]],
    ], color, width, false);
    const neckInner = strokeShape([[[cx + 6 * s, cy - 50 * s], [cx + 38 * s, cy - 60 * s], [cx + 55 * s, cy - 30 * s], [cx + 35 * s, cy - 5 * s]]], color, width * 0.85, false);
    return [body, neckOuter, neckInner];
  }

  if (name === 'chart_single') {
    const manifoldCx = cx - 140 * s, manifoldCy = cy;
    const shapes = [];
    shapes.push(strokeShape(blobSegments(manifoldCx, manifoldCy, 95 * s, 68 * s), color, width, true));
    shapes.push(strokeShape(smallLoopIcon(manifoldCx - 48 * s, manifoldCy - 26 * s, s), color, width * 0.8, true));

    const uCx = manifoldCx + 32 * s, uCy = manifoldCy + 6 * s;
    shapes.push(strokeShape(blobSegments(uCx, uCy, 36 * s, 28 * s, [1.0, 0.9, 1.05, 0.85, 1.1, 0.95]), color, width * 0.85, true, { dashed: true }));
    shapes.push(textShape(uCx + 6 * s, uCy - 40 * s, 'U', color, { fontsize: Math.max(10, Math.round(15 * s)) }));

    const p0 = [uCx + 40 * s, uCy], p1 = [cx + 40 * s, cy];
    shapes.push(arrowShape(p0, p1, color, width));
    shapes.push(textShape((p0[0] + p1[0]) / 2 - 6 * s, (p0[1] + p1[1]) / 2 - 20 * s, '\\varphi', color, { fontsize: Math.max(10, Math.round(15 * s)) }));

    const vCx = cx + 150 * s, vCy = cy;
    shapes.push(strokeShape(blobSegments(vCx, vCy, 55 * s, 42 * s, [1.0, 0.92, 1.05, 0.9, 1.08, 0.95]), color, width, true, { dashed: true }));
    shapes.push(textShape(vCx + 8 * s, vCy - 48 * s, '\\widetilde{U}', color, { fontsize: Math.max(10, Math.round(15 * s)) }));
    shapes.push(...coordAxes(vCx - 10 * s, vCy + 8 * s, 32 * s, color, width));
    return shapes;
  }

  if (name === 'chart_atlas_two') {
    const topCy = cy - 95 * s, bottomCy = cy + 95 * s;
    const shapes = [];
    shapes.push(strokeShape(blobSegments(cx, topCy, 175 * s, 62 * s, [1.0, 0.9, 1.05, 0.85, 1.1, 0.9, 1.05, 0.88]), color, width, true));
    shapes.push(strokeShape(smallLoopIcon(cx - 150 * s, topCy - 18 * s, s), color, width * 0.8, true));
    shapes.push(strokeShape(smallLoopIcon(cx + 155 * s, topCy - 10 * s, s * 0.9), color, width * 0.8, true));
    shapes.push(textShape(cx - 178 * s, topCy - 70 * s, 'X', color, { fontsize: Math.max(10, Math.round(16 * s)) }));

    const u1Cx = cx - 55 * s, u1Cy = topCy, u2Cx = cx + 30 * s, u2Cy = topCy;
    shapes.push(strokeShape(blobSegments(u1Cx, u1Cy, 52 * s, 36 * s, [1.0, 0.9, 1.06, 0.88, 1.1, 0.94]), color, width * 0.85, true, { dashed: true }));
    shapes.push(textShape(u1Cx - 20 * s, u1Cy - 44 * s, 'U_1', color, { fontsize: Math.max(10, Math.round(14 * s)) }));
    shapes.push(strokeShape(blobSegments(u2Cx, u2Cy, 52 * s, 36 * s, [1.0, 0.92, 1.05, 0.9, 1.08, 0.95]), color, width * 0.85, true, { dashed: true }));
    shapes.push(textShape(u2Cx + 30 * s, u2Cy - 44 * s, 'U_2', color, { fontsize: Math.max(10, Math.round(14 * s)) }));

    const box1Cx = cx - 115 * s, box2Cx = cx + 115 * s;
    shapes.push(arrowShape([u1Cx - 5 * s, u1Cy + 32 * s], [box1Cx + 10 * s, bottomCy - 42 * s], color, width));
    shapes.push(textShape((u1Cx + box1Cx) / 2 - 30 * s, (u1Cy + bottomCy) / 2 - 6 * s, '\\varphi_1', color, { fontsize: Math.max(10, Math.round(14 * s)) }));
    shapes.push(arrowShape([u2Cx + 5 * s, u2Cy + 32 * s], [box2Cx - 10 * s, bottomCy - 42 * s], color, width));
    shapes.push(textShape((u2Cx + box2Cx) / 2 + 30 * s, (u2Cy + bottomCy) / 2 - 6 * s, '\\varphi_2', color, { fontsize: Math.max(10, Math.round(14 * s)) }));

    shapes.push(...coordAxes(box1Cx - 12 * s, bottomCy + 10 * s, 60 * s, color, width));
    shapes.push(textShape(box1Cx - 22 * s, bottomCy - 58 * s, '\\varphi_1(U_1)', color, { fontsize: Math.max(10, Math.round(13 * s)) }));
    shapes.push(...coordAxes(box2Cx - 12 * s, bottomCy + 10 * s, 60 * s, color, width));
    shapes.push(textShape(box2Cx - 22 * s, bottomCy - 58 * s, '\\varphi_2(U_2)', color, { fontsize: Math.max(10, Math.round(13 * s)) }));

    shapes.push(arrowShape([box1Cx + 48 * s, bottomCy], [box2Cx - 48 * s, bottomCy], color, width));
    shapes.push(textShape((box1Cx + box2Cx) / 2 - 20 * s, bottomCy - 18 * s, '\\varphi_{12}', color, { fontsize: Math.max(10, Math.round(14 * s)) }));
    return shapes;
  }

  if (name === 'tangent_vector' || name === 'normal_vector') {
    const curve = strokeShape([[[cx - 100 * s, cy + 35 * s], [cx - 40 * s, cy - 35 * s], [cx + 40 * s, cy - 15 * s], [cx + 100 * s, cy + 30 * s]]], color, width, false);
    const p = [cx - 2 * s, cy - 22 * s];
    const dot = ellipseShape(p[0], p[1], 3.5 * s, 3.5 * s, color, width, { filled: true, fillColor: color });
    const labelP = textShape(p[0] - 14 * s, p[1] + 14 * s, 'p', color, { fontsize: Math.max(10, Math.round(14 * s)) });
    if (name === 'tangent_vector') {
      const arrow = arrowShape(p, [p[0] + 60 * s, p[1] + 8 * s], color, width);
      const labelV = textShape(p[0] + 66 * s, p[1] + 4 * s, 'T_pM', color, { fontsize: Math.max(10, Math.round(14 * s)) });
      return [curve, dot, arrow, labelP, labelV];
    }
    const arrow = arrowShape(p, [p[0] - 10 * s, p[1] - 55 * s], color, width);
    const labelN = textShape(p[0] - 26 * s, p[1] - 62 * s, 'n', color, { fontsize: Math.max(10, Math.round(14 * s)) });
    return [curve, dot, arrow, labelP, labelN];
  }

  if (name === 'vector_field') {
    const curve = strokeShape([[[cx - 140 * s, cy], [cx - 60 * s, cy - 25 * s], [cx + 60 * s, cy + 25 * s], [cx + 140 * s, cy]]], color, width, false);
    const shapes = [curve];
    const offsets = [-120, -65, -5, 55, 115];
    const directions = [[-25, -40], [10, -45], [30, -35], [10, -45], [-15, -40]];
    for (let i = 0; i < offsets.length; i++) {
      const px = cx + offsets[i] * s, py = cy;
      const [dx, dy] = directions[i];
      shapes.push(arrowShape([px, py], [px + dx * s * 0.5, py + dy * s * 0.5], color, width * 0.85));
    }
    return shapes;
  }

  if (name === 'fiber_bundle') {
    const eCx = cx, eCy = cy - 60 * s;
    const bY = cy + 90 * s;
    const eBlob = strokeShape(blobSegments(eCx, eCy, 115 * s, 45 * s, [1.0, 0.92, 1.06, 0.9, 1.08, 0.94]), color, width, true);
    const eLabel = textShape(eCx - 130 * s, eCy - 55 * s, 'E', color, { fontsize: Math.max(10, Math.round(16 * s)) });
    const baseLine = lineShape([cx - 100 * s, bY], [cx + 100 * s, bY], color, width);
    const bLabel = textShape(cx + 108 * s, bY, 'B', color, { fontsize: Math.max(10, Math.round(16 * s)) });
    const shapes = [eBlob, eLabel, baseLine, bLabel];
    for (const fx of [-70, -20, 60]) {
      shapes.push(lineShape([cx + fx * s, eCy + 25 * s], [cx + fx * s, bY - 3 * s], color, width * 0.7));
    }
    shapes.push(lineShape([cx + 20 * s, eCy - 40 * s], [cx + 20 * s, bY - 3 * s], color, width * 1.2));
    shapes.push(textShape(cx + 28 * s, eCy - 48 * s, 'F', color, { fontsize: Math.max(10, Math.round(14 * s)) }));
    const piArrow = arrowShape([cx - 20 * s, eCy + 30 * s], [cx - 20 * s, bY - 10 * s], color, width);
    shapes.push(piArrow);
    shapes.push(textShape(cx - 40 * s, (eCy + bY) / 2, '\\pi', color, { fontsize: Math.max(10, Math.round(14 * s)) }));
    return shapes;
  }

  if (name === 'lie_groupoid') {
    const gCx = cx, gCy = cy - 75 * s, mCx = cx, mCy = cy + 75 * s;
    const gShape = ellipseShape(gCx, gCy, 90 * s, 35 * s, color, width);
    const mShape = ellipseShape(mCx, mCy, 90 * s, 30 * s, color, width);
    const gLabel = textShape(gCx - 108 * s, gCy, 'G', color, { fontsize: Math.max(10, Math.round(16 * s)) });
    const mLabel = textShape(mCx - 108 * s, mCy, 'M', color, { fontsize: Math.max(10, Math.round(16 * s)) });
    const sArrow = arrowShape([gCx - 25 * s, gCy + 30 * s], [mCx - 25 * s, mCy - 26 * s], color, width);
    const tArrow = arrowShape([gCx + 25 * s, gCy + 30 * s], [mCx + 25 * s, mCy - 26 * s], color, width);
    const sLabel = textShape(gCx - 50 * s, (gCy + mCy) / 2, 's', color, { fontsize: Math.max(10, Math.round(14 * s)) });
    const tLabel = textShape(gCx + 42 * s, (gCy + mCy) / 2, 't', color, { fontsize: Math.max(10, Math.round(14 * s)) });
    return [gShape, mShape, gLabel, mLabel, sArrow, tArrow, sLabel, tLabel];
  }

  if (name === 'commutative_square') {
    const A = [cx - 75 * s, cy - 75 * s], B = [cx + 75 * s, cy - 75 * s], C = [cx - 75 * s, cy + 75 * s], D = [cx + 75 * s, cy + 75 * s];
    const fs = Math.max(10, Math.round(15 * s));
    return [
      textShape(A[0] - 14 * s, A[1] - 10 * s, 'A', color, { fontsize: fs }),
      textShape(B[0] + 6 * s, B[1] - 10 * s, 'B', color, { fontsize: fs }),
      textShape(C[0] - 14 * s, C[1] + 6 * s, 'C', color, { fontsize: fs }),
      textShape(D[0] + 6 * s, D[1] + 6 * s, 'D', color, { fontsize: fs }),
      arrowShape([A[0] + 14 * s, A[1]], [B[0] - 14 * s, B[1]], color, width),
      arrowShape([A[0], A[1] + 14 * s], [C[0], C[1] - 14 * s], color, width),
      arrowShape([B[0], B[1] + 14 * s], [D[0], D[1] - 14 * s], color, width),
      arrowShape([C[0] + 14 * s, C[1]], [D[0] - 14 * s, D[1]], color, width),
      textShape((A[0] + B[0]) / 2 - 6 * s, A[1] - 16 * s, 'f', color, { fontsize: fs }),
      textShape(A[0] - 20 * s, (A[1] + C[1]) / 2, 'g', color, { fontsize: fs }),
      textShape(D[0] + 10 * s, (B[1] + D[1]) / 2, 'h', color, { fontsize: fs }),
      textShape((C[0] + D[0]) / 2 - 6 * s, D[1] + 14 * s, 'k', color, { fontsize: fs }),
    ];
  }

  if (name === 'foliation') {
    const shapes = [];
    const dys = [-70, -35, 0, 35, 70];
    for (let i = 0; i < dys.length; i++) {
      const dy = dys[i];
      const wob = 18 * s * (i % 2 === 0 ? 1 : -1) * 0.6;
      const leaf = strokeShape([[[cx - 130 * s, cy + dy * s], [cx - 45 * s, cy + dy * s - wob], [cx + 45 * s, cy + dy * s + wob], [cx + 130 * s, cy + dy * s]]],
        color, width * (i === 2 ? 1.3 : 0.85), false);
      shapes.push(leaf);
    }
    return shapes;
  }

  return [];
}
