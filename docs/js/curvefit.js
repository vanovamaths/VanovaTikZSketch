/*
 * curvefit.js
 * Direct JS port of the desktop app's curvefit.py: Schneider's algorithm
 * for fitting a sequence of digitized points with piecewise cubic Bezier
 * curves (Graphics Gems, 1990), including the v4.15 fix for closed loops
 * (pre-splitting into open arcs so the degenerate p0==p3 case never causes
 * a wild, out-of-bounds control point).
 */

function vsub(a, b) { return [a[0] - b[0], a[1] - b[1]]; }
function vadd(a, b) { return [a[0] + b[0], a[1] + b[1]]; }
function vscale(a, s) { return [a[0] * s, a[1] * s]; }
function vdot(a, b) { return a[0] * b[0] + a[1] * b[1]; }
function vlen(a) { return Math.hypot(a[0], a[1]); }
function vunit(a) {
  const n = vlen(a);
  return n > 1e-9 ? [a[0] / n, a[1] / n] : [0, 0];
}

function chordLengthParameterize(points) {
  const u = [0];
  for (let i = 1; i < points.length; i++) {
    u.push(u[u.length - 1] + vlen(vsub(points[i], points[i - 1])));
  }
  const total = u[u.length - 1] > 1e-9 ? u[u.length - 1] : 1.0;
  return u.map((ui) => ui / total);
}

function bezierPoint(t, ctrl) {
  const mt = 1 - t;
  return vadd(
    vadd(vscale(ctrl[0], mt ** 3), vscale(ctrl[1], 3 * mt ** 2 * t)),
    vadd(vscale(ctrl[2], 3 * mt * t ** 2), vscale(ctrl[3], t ** 3))
  );
}

function bezierDeriv(t, ctrl) {
  const mt = 1 - t;
  return vadd(
    vadd(vscale(vsub(ctrl[1], ctrl[0]), 3 * mt ** 2), vscale(vsub(ctrl[2], ctrl[1]), 6 * mt * t)),
    vscale(vsub(ctrl[3], ctrl[2]), 3 * t ** 2)
  );
}

function newtonRaphsonRootFind(ctrl, point, u) {
  const d = vsub(bezierPoint(u, ctrl), point);
  const qp = bezierDeriv(u, ctrl);
  const qpp = vadd(
    vscale(vadd(vsub(ctrl[2], vscale(ctrl[1], 2)), ctrl[0]), 6 * (1 - u)),
    vscale(vadd(vsub(ctrl[3], vscale(ctrl[2], 2)), ctrl[1]), 6 * u)
  );
  const denom = vdot(qp, qp) + vdot(d, qpp);
  if (Math.abs(denom) < 1e-9) return u;
  return u - vdot(d, qp) / denom;
}

function reparameterize(points, u, ctrl) {
  return points.map((p, i) => newtonRaphsonRootFind(ctrl, p, u[i]));
}

function generateBezier(points, u, tHat1, tHat2) {
  const n = points.length;
  const A = [];
  for (let i = 0; i < n; i++) {
    const t = u[i];
    A.push([vscale(tHat1, 3 * (1 - t) ** 2 * t), vscale(tHat2, 3 * (1 - t) * t ** 2)]);
  }
  const C = [[0, 0], [0, 0]];
  const X = [0, 0];
  const p0 = points[0];
  const p3 = points[n - 1];
  for (let i = 0; i < n; i++) {
    const t = u[i];
    C[0][0] += vdot(A[i][0], A[i][0]);
    C[0][1] += vdot(A[i][0], A[i][1]);
    C[1][0] = C[0][1];
    C[1][1] += vdot(A[i][1], A[i][1]);
    const base = vsub(bezierPoint(t, [p0, p0, p3, p3]), points[i]);
    X[0] -= vdot(A[i][0], base);
    X[1] -= vdot(A[i][1], base);
  }
  const detC0C1 = C[0][0] * C[1][1] - C[1][0] * C[0][1];
  let alphaL = 0;
  let alphaR = 0;
  if (Math.abs(detC0C1) > 1e-12) {
    const detC0X = C[0][0] * X[1] - C[1][0] * X[0];
    const detXC1 = X[0] * C[1][1] - X[1] * C[0][1];
    alphaL = detXC1 / detC0C1;
    alphaR = detC0X / detC0C1;
  }

  const segLen = vlen(vsub(p0, p3));
  let arcLen = 0;
  for (let i = 1; i < n; i++) arcLen += vlen(vsub(points[i], points[i - 1]));
  let xs = points.map((p) => p[0]);
  let ys = points.map((p) => p[1]);
  const diag = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
  const refLen = segLen > 1e-6 ? segLen : (arcLen > 1e-6 ? arcLen / 3 : 1.0);
  const fallback = refLen / 3;
  const maxAlpha = Math.max(diag, refLen, 1e-6);
  const eps = refLen > 0 ? 1e-6 * refLen : 1e-6;
  if (alphaL < eps || alphaR < eps || alphaL > maxAlpha || alphaR > maxAlpha) {
    alphaL = fallback;
    alphaR = fallback;
  }
  const c1 = vadd(p0, vscale(tHat1, alphaL));
  const c2 = vadd(p3, vscale(tHat2, alphaR));
  return [p0, c1, c2, p3];
}

function computeMaxError(points, u, ctrl) {
  let maxDist = 0;
  let splitPoint = Math.floor(points.length / 2);
  for (let i = 0; i < points.length; i++) {
    const d = vsub(bezierPoint(u[i], ctrl), points[i]);
    const dist = vdot(d, d);
    if (dist > maxDist) {
      maxDist = dist;
      splitPoint = i;
    }
  }
  return [maxDist, splitPoint];
}

function fitCubic(points, tHat1, tHat2, error, out) {
  if (points.length === 2) {
    const dist = vlen(vsub(points[0], points[1])) / 3.0;
    const p0 = points[0];
    const p3 = points[1];
    out.push([p0, vadd(p0, vscale(tHat1, dist)), vadd(p3, vscale(tHat2, dist)), p3]);
    return;
  }
  let u = chordLengthParameterize(points);
  let ctrl = generateBezier(points, u, tHat1, tHat2);
  let [maxErr, splitPoint] = computeMaxError(points, u, ctrl);
  if (maxErr < error) {
    out.push(ctrl);
    return;
  }
  for (let iter = 0; iter < 4; iter++) {
    u = reparameterize(points, u, ctrl);
    ctrl = generateBezier(points, u, tHat1, tHat2);
    [maxErr, splitPoint] = computeMaxError(points, u, ctrl);
    if (maxErr < error) {
      out.push(ctrl);
      return;
    }
  }
  if (splitPoint < 2) splitPoint = 2;
  if (splitPoint > points.length - 2) splitPoint = points.length - 2;
  let tHatCenter = vsub(points[splitPoint - 1], points[splitPoint + 1]);
  const norm = vlen(tHatCenter);
  tHatCenter = norm > 1e-9 ? vscale(tHatCenter, 1 / norm) : [0, 0];
  fitCubic(points.slice(0, splitPoint + 1), tHat1, tHatCenter, error, out);
  fitCubic(points.slice(splitPoint), vscale(tHatCenter, -1), tHat2, error, out);
}

function fitCurveClosed(core, maxError, nSplit = 4) {
  const m = core.length;
  nSplit = m >= 6 ? Math.max(2, Math.min(nSplit, Math.floor(m / 3))) : 1;
  const idxs = [];
  for (let i = 0; i < nSplit; i++) idxs.push(Math.round((i * m) / nSplit));
  const out = [];
  for (let k = 0; k < nSplit; k++) {
    const i0 = idxs[k];
    let segPts;
    if (k < nSplit - 1) {
      segPts = core.slice(i0, idxs[k + 1] + 1);
    } else {
      segPts = core.slice(i0).concat([core[0]]);
    }
    if (segPts.length < 2) continue;
    const tHat1 = vunit(vsub(segPts[1], segPts[0]));
    const tHat2 = vunit(vsub(segPts[segPts.length - 2], segPts[segPts.length - 1]));
    fitCubic(segPts, tHat1, tHat2, maxError, out);
  }
  return out;
}

/** points: array of [x,y]; returns array of [P0,C1,C2,P3] segments. */
function fitCurve(pointsXY, maxError = 4.0) {
  const dedup = [pointsXY[0]];
  for (let i = 1; i < pointsXY.length; i++) {
    if (vlen(vsub(pointsXY[i], dedup[dedup.length - 1])) > 1e-6) dedup.push(pointsXY[i]);
  }
  const pts = dedup;
  if (pts.length < 2) {
    const p = pts.length ? pts[0] : [0, 0];
    return [[p, p, p, p]];
  }
  if (pts.length >= 6 && vlen(vsub(pts[0], pts[pts.length - 1])) < 1e-3) {
    return fitCurveClosed(pts.slice(0, -1), maxError);
  }
  const tHat1 = vunit(vsub(pts[1], pts[0]));
  const tHat2 = vunit(vsub(pts[pts.length - 2], pts[pts.length - 1]));
  const out = [];
  fitCubic(pts, tHat1, tHat2, maxError, out);
  return out;
}

function adaptiveMaxError(pointsXY, ratio = 0.012, lo = 1.2, hi = 22.0) {
  if (pointsXY.length < 2) return lo;
  const xs = pointsXY.map((p) => p[0]);
  const ys = pointsXY.map((p) => p[1]);
  const diag = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
  const err = ratio * diag;
  return Math.min(Math.max(err, lo), hi);
}

function segmentsSane(segments, pts) {
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  const w = Math.max(x1 - x0, 1.0), h = Math.max(y1 - y0, 1.0);
  const mx = 0.2 * w, my = 0.2 * h;
  const loX = x0 - mx, hiX = x1 + mx, loY = y0 - my, hiY = y1 + my;
  for (const seg of segments) {
    for (const [px, py] of seg) {
      if (!(px >= loX && px <= hiX && py >= loY && py <= hiY)) return false;
    }
  }
  return true;
}

function polylineAsBezier(pts) {
  const segs = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i], p3 = pts[i + 1];
    const c1 = [p0[0] + (p3[0] - p0[0]) / 3, p0[1] + (p3[1] - p0[1]) / 3];
    const c2 = [p0[0] + (p3[0] - p0[0]) * 2 / 3, p0[1] + (p3[1] - p0[1]) * 2 / 3];
    segs.push([p0, c1, c2, p3]);
  }
  return segs;
}

/** fitCurve with a fallback ladder + guaranteed-in-bounds polyline fallback. */
function fitCurveSafe(pts, err) {
  for (const candidateErr of [err, Math.max(err * 4, 6.0), 20.0, 60.0]) {
    const segments = fitCurve(pts, candidateErr);
    if (segments.length && segmentsSane(segments, pts)) return segments;
  }
  return polylineAsBezier(pts);
}
