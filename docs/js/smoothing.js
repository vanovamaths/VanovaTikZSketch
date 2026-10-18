/*
 * smoothing.js
 * JS port of the desktop app's smoothing.py core: resample a raw pointer
 * path to an even arc-length spacing, then apply a few passes of simple
 * neighbor-averaging (jitter removal) -- this corrects hand-tremor without
 * reshaping the stroke's actual design (see the v4.9 fix in the desktop
 * app: auto-finish must never forcibly symmetrize/deform a drawing).
 *
 * CLOSED curves are handled as `nSamples` DISTINCT points cycling around
 * the loop (indices mod n) all the way through resampling AND smoothing,
 * and only re-closed (an explicit duplicate of point 0 appended at the
 * end) as the very last step. Doing the duplication earlier and then
 * smoothing with wraparound neighbors makes the two "same" endpoints
 * drift apart (each sees a different neighbor on its free side), which
 * silently breaks the "first point == last point" invariant curvefit.js
 * relies on to detect a closed loop -- producing wildly wrong Bezier
 * fits. See the desktop app's v4.15 changelog for the Python side of
 * this exact bug class.
 */

function resampleEvenOpen(pts, nSamples) {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  }
  const total = cum[cum.length - 1];
  if (total < 1e-9) return pts.slice();
  const out = [];
  for (let i = 0; i < nSamples; i++) {
    const target = (i / (nSamples - 1)) * total;
    out.push(sampleAt(pts, cum, target));
  }
  return out;
}

function resampleEvenClosed(core, nSamples) {
  // core: distinct points around the loop (core[0] is NOT duplicated at the end)
  const loop = core.concat([core[0]]);
  const cum = [0];
  for (let i = 1; i < loop.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(loop[i][0] - loop[i - 1][0], loop[i][1] - loop[i - 1][1]));
  }
  const total = cum[cum.length - 1];
  if (total < 1e-9) return core.slice();
  const out = [];
  for (let i = 0; i < nSamples; i++) {
    const target = (i / nSamples) * total; // i == nSamples would be the wrap-around point 0 again
    out.push(sampleAt(loop, cum, target));
  }
  return out;
}

function sampleAt(pts, cum, target) {
  let lo = 0, hi = cum.length - 1;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (cum[mid] <= target) lo = mid; else hi = mid;
  }
  const seg = cum[hi] - cum[lo];
  const t = seg > 1e-9 ? (target - cum[lo]) / seg : 0;
  return [
    pts[lo][0] + t * (pts[hi][0] - pts[lo][0]),
    pts[lo][1] + t * (pts[hi][1] - pts[lo][1]),
  ];
}

function smoothPassOpen(pts) {
  const n = pts.length;
  const out = new Array(n);
  for (let i = 0; i < n; i++) {
    if (i === 0 || i === n - 1) { out[i] = pts[i]; continue; }
    out[i] = [
      0.25 * pts[i - 1][0] + 0.5 * pts[i][0] + 0.25 * pts[i + 1][0],
      0.25 * pts[i - 1][1] + 0.5 * pts[i][1] + 0.25 * pts[i + 1][1],
    ];
  }
  return out;
}

function smoothPassClosed(pts) {
  const n = pts.length;
  const out = new Array(n);
  for (let i = 0; i < n; i++) {
    const prev = pts[(i - 1 + n) % n];
    const next = pts[(i + 1) % n];
    out[i] = [
      0.25 * prev[0] + 0.5 * pts[i][0] + 0.25 * next[0],
      0.25 * prev[1] + 0.5 * pts[i][1] + 0.25 * next[1],
    ];
  }
  return out;
}

/** Resample to nSamples points, then apply `passes` rounds of light
 * neighbor-averaging -- corrects jitter without changing the drawn shape.
 * For closed=true, `pts` may or may not already end with a duplicate of
 * pts[0]; either way the output is nSamples DISTINCT points plus one
 * final explicit duplicate of the first point (so downstream code -- the
 * curve fitter in particular -- can rely on out[0] === out[last]). */
function cleanStroke(pts, { closed = false, nSamples = 80, passes = 3 } = {}) {
  if (pts.length < 3) return pts.slice();
  if (closed) {
    let core = pts;
    const last = pts[pts.length - 1];
    if (Math.hypot(pts[0][0] - last[0], pts[0][1] - last[1]) < 1e-6) core = pts.slice(0, -1);
    let out = resampleEvenClosed(core, Math.max(6, nSamples));
    for (let i = 0; i < passes; i++) out = smoothPassClosed(out);
    return out.concat([out[0]]);
  }
  let out = resampleEvenOpen(pts, Math.max(6, nSamples));
  for (let i = 0; i < passes; i++) out = smoothPassOpen(out);
  return out;
}
