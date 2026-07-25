/*
 * app.js
 * Canvas interaction, toolbar wiring, undo/redo, live preview, TikZ live
 * export. Vanilla JS, no build step -- works straight from GitHub Pages.
 */

(function () {
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const previewCanvas = document.getElementById('preview-canvas');
  const previewCtx = previewCanvas.getContext('2d');
  const statusText = document.getElementById('status-text');
  const canvasWrap = document.getElementById('canvas-wrap');

  const PALETTE = [
    '#000000', '#495057', '#9e9e9e', '#ffffff',
    '#e53935', '#d32f2f', '#f06292', '#8e24aa',
    '#7e57c2', '#5c6bc0', '#1e88e5', '#1565c0',
    '#00acc1', '#26c6da', '#26a69a', '#43a047',
    '#66bb6a', '#c0ca33', '#fdd835', '#ffca28',
    '#fb8c00', '#ff7043', '#6d4c41', '#78909c',
  ];
  const GRID_STEP = 20;

  const state = {
    shapes: [],
    tool: 'select',
    color: '#000000',
    width: 2.5,
    fill: false,
    fillColor: '#cccccc',
    lineStyle: 'solid',
    headStyle: 'stealth',
    bend: 0, // quiver-style curve amount (px) for the next line/arrow
    fontsize: 16, // text size for the next label (object names, symbols)
    autoFinish: true,
    snapGrid: false,
    showGrid: false,
    zoom: 1.0,
    selected: -1,
    clipboard: null,
    undoStack: [],
    redoStack: [],
  };

  /* -------------------------------------------------------- undo/redo */
  function pushUndo() {
    state.undoStack.push(JSON.stringify(state.shapes));
    if (state.undoStack.length > 100) state.undoStack.shift();
    state.redoStack.length = 0;
  }
  function undo() {
    if (!state.undoStack.length) return;
    state.redoStack.push(JSON.stringify(state.shapes));
    state.shapes = JSON.parse(state.undoStack.pop());
    state.selected = -1;
    render();
  }
  function redo() {
    if (!state.redoStack.length) return;
    state.undoStack.push(JSON.stringify(state.shapes));
    state.shapes = JSON.parse(state.redoStack.pop());
    state.selected = -1;
    render();
  }

  /* ----------------------------------------------------------- render */
  function drawGrid(c, cx) {
    if (!state.showGrid) return;
    cx.save();
    cx.strokeStyle = '#e5e9f2';
    cx.lineWidth = 1;
    for (let x = 0; x <= c.width; x += GRID_STEP) {
      cx.beginPath(); cx.moveTo(x, 0); cx.lineTo(x, c.height); cx.stroke();
    }
    for (let y = 0; y <= c.height; y += GRID_STEP) {
      cx.beginPath(); cx.moveTo(0, y); cx.lineTo(c.width, y); cx.stroke();
    }
    cx.restore();
  }

  // renderCanvas() repaints only the main drawing canvas -- cheap, safe to
  // call on every pointermove. render() additionally recomputes the Live
  // Preview panel and the full TikZ export text, both O(all shapes); doing
  // that on every mouse-move event while dragging/drawing (a full stroke
  // can fire 60+ move events) is wasted, visibly laggy work with many
  // shapes on the canvas. During an active drag we now repaint the canvas
  // only and defer the side-panel refresh to a single rAF-throttled call,
  // then do one full render() on pointerup so everything stays in sync.
  function renderCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#ece7da'; // soft off-white instead of pure #fff -- easier on the eyes
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    drawGrid(canvas, ctx);
    state.shapes.forEach((s, i) => renderShape(ctx, s, i === state.selected));
    if (drag && drag.previewShape) renderShape(ctx, drag.previewShape, false);
  }

  let sidePanelRaf = null;
  function scheduleSidePanelUpdate() {
    if (sidePanelRaf) return;
    sidePanelRaf = requestAnimationFrame(() => {
      sidePanelRaf = null;
      renderPreview();
      updateTikz();
    });
  }

  function render() {
    renderCanvas();
    renderPreview();
    updateTikz();
  }

  // Fast path used while actively dragging: a fast mouse/tablet can fire
  // pointermove far faster than the screen actually refreshes (500Hz+ on
  // some trackpads/tablets). Coalescing the canvas repaint into a single
  // requestAnimationFrame tick -- instead of redrawing once per raw pointer
  // event -- caps the work to the display's real refresh rate, which is
  // what makes drawing feel smooth/fluid instead of janky under load. The
  // in-progress preview shape is already updated synchronously before this
  // is called, so the rAF callback always paints the latest state.
  let canvasRaf = null;
  function scheduleCanvasRepaint() {
    if (canvasRaf) return;
    canvasRaf = requestAnimationFrame(() => {
      canvasRaf = null;
      renderCanvas();
    });
  }
  function renderDuringDrag() {
    scheduleCanvasRepaint();
    scheduleSidePanelUpdate();
  }

  function renderPreview() {
    previewCtx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
    previewCtx.fillStyle = '#ece7da';
    previewCtx.fillRect(0, 0, previewCanvas.width, previewCanvas.height);
    if (!state.shapes.length) return;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const s of state.shapes) {
      const bb = shapeBBox(s);
      x0 = Math.min(x0, bb[0]); y0 = Math.min(y0, bb[1]);
      x1 = Math.max(x1, bb[2]); y1 = Math.max(y1, bb[3]);
    }
    const w = Math.max(x1 - x0, 1), h = Math.max(y1 - y0, 1);
    const pad = 14;
    const scale = Math.min((previewCanvas.width - 2 * pad) / w, (previewCanvas.height - 2 * pad) / h);
    const ox = (previewCanvas.width - w * scale) / 2 - x0 * scale;
    const oy = (previewCanvas.height - h * scale) / 2 - y0 * scale;
    previewCtx.save();
    previewCtx.translate(ox, oy);
    previewCtx.scale(scale, scale);
    for (const s of state.shapes) renderShape(previewCtx, s, false);
    previewCtx.restore();
  }

  function updateTikz() {
    const out = document.getElementById('tikz-output');
    try {
      out.value = shapesToStandaloneTex(state.shapes);
    } catch (e) {
      out.value = '% (export error) ' + e.message;
    }
  }

  /* ------------------------------------------------------------- tools */
  let drag = null; // active pointer interaction state

  function snap(v) { return state.snapGrid ? Math.round(v / GRID_STEP) * GRID_STEP : v; }

  // ------------------------------------------------------ infinite canvas
  // The drawing surface used to be a fixed 1000x700 <canvas>: hit the right
  // or bottom edge and you simply couldn't draw any further. growCanvasToInclude
  // makes the canvas grow on demand in ALL FOUR directions as you draw near
  // an edge, so the drawing area behaves as if it were infinite:
  //  - growing right/down is simple: just enlarge canvas.width/height.
  //  - growing left/up requires shifting every existing shape's coordinates
  //    (and the canvas's own on-screen scroll position) so nothing appears
  //    to jump -- the new space just appears exactly where the cursor is.
  const GROW_MARGIN = 160; // start growing once the cursor is this close to an edge
  const GROW_STEP = 900;   // grow by this much each time (avoids growing every pixel)

  function growCanvasToInclude(x, y) {
    let shiftX = 0, shiftY = 0;
    let newWidth = canvas.width, newHeight = canvas.height;

    if (x > canvas.width - GROW_MARGIN) newWidth = Math.max(newWidth, Math.ceil(x + GROW_STEP));
    if (y > canvas.height - GROW_MARGIN) newHeight = Math.max(newHeight, Math.ceil(y + GROW_STEP));
    if (x < GROW_MARGIN) { shiftX = GROW_STEP; newWidth += GROW_STEP; }
    if (y < GROW_MARGIN) { shiftY = GROW_STEP; newHeight += GROW_STEP; }

    const resized = newWidth !== canvas.width || newHeight !== canvas.height;
    if (!resized && !shiftX && !shiftY) return [x, y];

    if (shiftX || shiftY) {
      state.shapes.forEach((s) => translateShape(s, shiftX, shiftY));
      if (drag) {
        if (drag.points) drag.points = drag.points.map((p) => [p[0] + shiftX, p[1] + shiftY]);
        if (drag.p0) drag.p0 = [drag.p0[0] + shiftX, drag.p0[1] + shiftY];
        if (drag.p1) drag.p1 = [drag.p1[0] + shiftX, drag.p1[1] + shiftY];
        if (drag.last) drag.last = [drag.last[0] + shiftX, drag.last[1] + shiftY];
      }
    }

    canvas.width = newWidth;
    canvas.height = newHeight;

    if (shiftX || shiftY) {
      // Keep the drawing visually anchored: the canvas element just grew
      // in the top-left direction, so scroll the wrapper by the same
      // amount (in on-screen pixels, i.e. scaled by the current zoom) so
      // nothing appears to jump under the user's cursor.
      canvasWrap.scrollLeft += shiftX * state.zoom;
      canvasWrap.scrollTop += shiftY * state.zoom;
    }

    render();
    return [x + shiftX, y + shiftY];
  }

  function pointerPos(evt) {
    const r = canvas.getBoundingClientRect();
    const sx = canvas.width / r.width, sy = canvas.height / r.height;
    let x = snap((evt.clientX - r.left) * sx);
    let y = snap((evt.clientY - r.top) * sy);
    [x, y] = growCanvasToInclude(x, y);
    return [x, y];
  }

  function newShapeBase() {
    return { color: state.color, width: state.width, lineStyle: state.lineStyle };
  }

  function hitTest(x, y) {
    let best = -1, bestD = 10;
    for (let i = state.shapes.length - 1; i >= 0; i--) {
      const d = distanceToShape(x, y, state.shapes[i]);
      if (d < bestD) { bestD = d; best = i; }
    }
    return best;
  }

  function isNearlyClosed(pts) {
    if (pts.length < 8) return false;
    const d = Math.hypot(pts[0][0] - pts[pts.length - 1][0], pts[0][1] - pts[pts.length - 1][1]);
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const diag = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    return d < Math.max(14, diag * 0.09);
  }

  function finishFreehand(rawPts) {
    if (rawPts.length < 3) return;
    let pts = rawPts;
    let closed = state.autoFinish && isNearlyClosed(rawPts);
    if (closed) pts = pts.concat([pts[0]]);
    const nSamples = Math.min(160, Math.max(24, Math.floor(pts.length / 2)));
    const cleaned = cleanStroke(pts, { closed, nSamples, passes: closed ? 3 : 2 });
    const err = adaptiveMaxError(cleaned, 0.006, 1.0, 6.0);
    const segments = fitCurveSafe(cleaned, err);
    if (!segments.length) return;
    const shape = {
      type: 'stroke', segments, ...newShapeBase(),
      closed, filled: false, fillColor: null,
    };
    pushUndo();
    state.shapes.push(shape);
    state.selected = state.shapes.length - 1; // auto-select so Copy/Duplicate work right away
    render();
    setStatus(closed ? 'Closed shape added (auto-finish).' : 'Stroke added.');
  }

  function setStatus(msg) { statusText.textContent = msg; }

  /* ------------------------------------------------------ pointer flow */
  canvas.addEventListener('pointerdown', (evt) => {
    canvas.setPointerCapture(evt.pointerId);
    const [x, y] = pointerPos(evt);

    if (state.tool === 'pen') {
      drag = { kind: 'pen', points: [[x, y]] };
    } else if (state.tool === 'line' || state.tool === 'arrow') {
      drag = { kind: state.tool, p0: [x, y], p1: [x, y] };
    } else if (state.tool === 'ellipse') {
      drag = { kind: 'ellipse', p0: [x, y], p1: [x, y] };
    } else if (state.tool === 'text') {
      const txt = prompt('Text (LaTeX allowed, e.g. $\\alpha$):', '');
      if (txt) {
        pushUndo();
        state.shapes.push({ type: 'text', x, y, text: txt, latex: true, color: state.color, fontsize: state.fontsize });
        state.selected = state.shapes.length - 1; // auto-select so Copy/Duplicate work right away
        render();
      }
    } else if (state.tool === 'eraser') {
      const hit = hitTest(x, y);
      if (hit >= 0) { pushUndo(); state.shapes.splice(hit, 1); render(); }
    } else if (state.tool === 'select') {
      const hit = hitTest(x, y);
      state.selected = hit;
      if (hit >= 0) {
        pushUndo(); // snapshot BEFORE the move, so undo restores the pre-drag position
        drag = { kind: 'move', last: [x, y] };
      }
      render();
      updateContextualUI();
      syncControlsToSelection();
    }
  });

  canvas.addEventListener('pointermove', (evt) => {
    if (!drag) return;
    const [x, y] = pointerPos(evt);
    if (drag.kind === 'pen') {
      const last = drag.points[drag.points.length - 1];
      if (Math.hypot(x - last[0], y - last[1]) > 1.2) drag.points.push([x, y]);
      drag.previewShape = { type: 'polygon', points: drag.points, closed: false, ...newShapeBase() };
      renderDuringDrag();
    } else if (drag.kind === 'line' || drag.kind === 'arrow') {
      drag.p1 = [x, y];
      drag.previewShape = { type: drag.kind, p0: drag.p0, p1: drag.p1, headStyle: state.headStyle, bend: state.bend, ...newShapeBase() };
      renderDuringDrag();
    } else if (drag.kind === 'ellipse') {
      drag.p1 = [x, y];
      const cx = (drag.p0[0] + drag.p1[0]) / 2, cy = (drag.p0[1] + drag.p1[1]) / 2;
      const rx = Math.abs(drag.p1[0] - drag.p0[0]) / 2, ry = Math.abs(drag.p1[1] - drag.p0[1]) / 2;
      drag.previewShape = { type: 'ellipse', cx, cy, rx, ry, filled: state.fill, fillColor: state.fillColor, ...newShapeBase() };
      renderDuringDrag();
    } else if (drag.kind === 'move' && state.selected >= 0) {
      const dx = x - drag.last[0], dy = y - drag.last[1];
      translateShape(state.shapes[state.selected], dx, dy);
      drag.last = [x, y];
      renderDuringDrag();
    }
  }, { passive: true });

  canvas.addEventListener('pointerup', () => {
    if (!drag) return;
    if (drag.kind === 'pen') {
      finishFreehand(drag.points);
    } else if (drag.kind === 'line' || drag.kind === 'arrow') {
      if (Math.hypot(drag.p1[0] - drag.p0[0], drag.p1[1] - drag.p0[1]) > 2) {
        pushUndo();
        const s = { type: drag.kind, p0: drag.p0, p1: drag.p1, bend: state.bend, ...newShapeBase() };
        if (drag.kind === 'arrow') s.headStyle = state.headStyle;
        state.shapes.push(s);
        state.selected = state.shapes.length - 1; // auto-select so Copy/Duplicate work right away
      }
    } else if (drag.kind === 'ellipse') {
      const cx = (drag.p0[0] + drag.p1[0]) / 2, cy = (drag.p0[1] + drag.p1[1]) / 2;
      const rx = Math.abs(drag.p1[0] - drag.p0[0]) / 2, ry = Math.abs(drag.p1[1] - drag.p0[1]) / 2;
      if (rx > 2 || ry > 2) {
        pushUndo();
        state.shapes.push({
          type: 'ellipse', cx, cy, rx: Math.max(rx, 1), ry: Math.max(ry, 1),
          filled: state.fill, fillColor: state.fill ? state.fillColor : null, ...newShapeBase(),
        });
        state.selected = state.shapes.length - 1;
      }
    }
    drag = null;
    render();
  });

  canvas.addEventListener('wheel', (evt) => {
    if (!evt.ctrlKey && !evt.metaKey) return;
    evt.preventDefault();
    zoomBy(evt.deltaY < 0 ? 1.1 : 1 / 1.1);
  }, { passive: false });

  window.addEventListener('keydown', (evt) => {
    const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
    if (typing) return;
    if ((evt.key === 'Delete' || evt.key === 'Backspace') && state.selected >= 0) {
      pushUndo();
      state.shapes.splice(state.selected, 1);
      state.selected = -1;
      render();
    } else if (evt.ctrlKey || evt.metaKey) {
      const k = evt.key.toLowerCase();
      if (k === 'z' && !evt.shiftKey) { evt.preventDefault(); undo(); }
      else if (k === 'z' && evt.shiftKey) { evt.preventDefault(); redo(); }
      else if (k === 'c') { evt.preventDefault(); copySelected(); }
      else if (k === 'v') { evt.preventDefault(); pasteClipboard(); }
      else if (k === 'd') { evt.preventDefault(); duplicateSelected(); }
    }
  });

  /* --------------------------------------------------------- toolbar */
  document.querySelectorAll('#tools .tool').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#tools .tool').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      state.tool = btn.dataset.tool;
      updateContextualUI();
      setStatus(`Tool: ${btn.textContent.trim()}`);
    });
  });

  // Shows/hides the Head-style and Curve controls based on the active tool
  // AND on the currently selected shape, so they're available both while
  // drawing a new line/arrow and while editing an existing one.
  function updateContextualUI() {
    const sel = state.selected >= 0 ? state.shapes[state.selected] : null;
    const showHead = state.tool === 'arrow' || (sel && sel.type === 'arrow');
    const showCurve = state.tool === 'line' || state.tool === 'arrow' || (sel && (sel.type === 'line' || sel.type === 'arrow'));
    const showFontsize = state.tool === 'text' || (sel && sel.type === 'text');
    document.getElementById('head-style-group').style.display = showHead ? 'flex' : 'none';
    document.getElementById('curve-group').style.display = showCurve ? 'flex' : 'none';
    document.getElementById('fontsize-group').style.display = showFontsize ? 'flex' : 'none';
  }

  function syncControlsToSelection() {
    if (state.selected < 0) return;
    const s = state.shapes[state.selected];
    if (s.color) { document.getElementById('color-picker').value = s.color; state.color = s.color; }
    if (s.width) { document.getElementById('width-slider').value = s.width; document.getElementById('width-value').textContent = Number(s.width).toFixed(1); state.width = s.width; }
    document.getElementById('fill-toggle').checked = !!s.filled;
    document.getElementById('line-style').value = s.lineStyle || 'solid';
    if (s.type === 'arrow') document.getElementById('head-style').value = s.headStyle || 'stealth';
    if (s.type === 'line' || s.type === 'arrow') {
      const bend = s.bend || 0;
      document.getElementById('curve-slider').value = bend;
      document.getElementById('curve-value').textContent = bend;
      state.bend = bend;
    }
    if (s.type === 'text') {
      const fs = s.fontsize || 16;
      document.getElementById('fontsize-slider').value = fs;
      document.getElementById('fontsize-value').textContent = fs;
      state.fontsize = fs;
    }
  }

  const palette = document.getElementById('palette');
  PALETTE.forEach((hex) => {
    const sw = document.createElement('div');
    sw.className = 'swatch';
    sw.style.background = hex;
    sw.style.boxShadow = hex === '#ffffff' ? 'inset 0 0 0 1px #333' : 'none';
    sw.addEventListener('click', () => {
      state.color = hex;
      document.getElementById('color-picker').value = hex;
      document.querySelectorAll('#palette .swatch').forEach((s) => s.classList.remove('active'));
      sw.classList.add('active');
      applyColorToSelection();
    });
    palette.appendChild(sw);
  });

  /* --------------------------------------------- harmonious color palette
   * Inspired by dedicated palette tools (Coolors/Paletton/Khroma): pick a
   * base color and a color-theory scheme, get back a small set of hues that
   * are guaranteed to look coherent together (rotations of the same base
   * hue around the color wheel), instead of guessing complementary colors
   * by eye. Pure HSL math, no external library needed. */
  function hexToHsl(hex) {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h, s;
    const l = (max + min) / 2;
    if (max === min) { h = 0; s = 0; } else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
      else if (max === g) h = (b - r) / d + 2;
      else h = (r - g) / d + 4;
      h /= 6;
    }
    return [h * 360, s * 100, l * 100];
  }
  function hslToHex(h, s, l) {
    h = ((h % 360) + 360) % 360; s = Math.min(100, Math.max(0, s)) / 100; l = Math.min(100, Math.max(0, l)) / 100;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h / 60) % 2 - 1));
    const m = l - c / 2;
    let r = 0, g = 0, b = 0;
    if (h < 60) { r = c; g = x; } else if (h < 120) { r = x; g = c; }
    else if (h < 180) { g = c; b = x; } else if (h < 240) { g = x; b = c; }
    else if (h < 300) { r = x; b = c; } else { r = c; b = x; }
    const toHex = (v) => Math.round((v + m) * 255).toString(16).padStart(2, '0');
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
  }
  const HARMONY_HUE_OFFSETS = {
    complementary: [0, 180],
    analogous: [-30, 0, 30],
    triadic: [0, 120, 240],
    tetradic: [0, 90, 180, 270],
  };
  function generateHarmoniousPalette(baseHex, scheme) {
    const [h, s, l] = hexToHsl(baseHex);
    const offsets = HARMONY_HUE_OFFSETS[scheme] || [0];
    const colors = [];
    offsets.forEach((dh) => {
      colors.push(hslToHex(h + dh, s, l));
      // a lighter tint of the same hue -- handy as a companion fill color
      colors.push(hslToHex(h + dh, Math.max(20, s * 0.55), Math.min(88, l + 22)));
    });
    return colors;
  }
  const paletteGenerated = document.getElementById('palette-generated');
  document.getElementById('btn-generate-palette').addEventListener('click', () => {
    const base = document.getElementById('harmony-base').value;
    const scheme = document.getElementById('harmony-scheme').value;
    const colors = generateHarmoniousPalette(base, scheme);
    paletteGenerated.innerHTML = '';
    colors.forEach((hex) => {
      const sw = document.createElement('div');
      sw.className = 'swatch';
      sw.style.background = hex;
      sw.title = `${hex} -- click = stroke, Alt+click = fill`;
      sw.addEventListener('click', (e) => {
        if (e.altKey) {
          state.fillColor = hex;
          document.getElementById('fill-color').value = hex;
          if (state.selected >= 0) { pushUndo(); state.shapes[state.selected].fillColor = hex; render(); }
        } else {
          state.color = hex;
          document.getElementById('color-picker').value = hex;
          document.querySelectorAll('#palette .swatch').forEach((s) => s.classList.remove('active'));
          applyColorToSelection();
        }
      });
      paletteGenerated.appendChild(sw);
    });
    setStatus(`Generated a ${scheme} palette from ${base}.`);
  });

  /* ------------------------------------------------------ sketchy style
   * Togglable hand-drawn rendering (deterministic double-jittered stroke,
   * implemented in shapes.js/renderShape) -- a lightweight, dependency-free
   * take on the rough.js/Excalidraw look, since this project intentionally
   * stays vanilla JS with no build step / no external libraries. */
  document.getElementById('sketchy-mode').addEventListener('change', (e) => {
    window.SKETCHY_MODE = e.target.checked;
    render();
    setStatus(window.SKETCHY_MODE ? 'Sketchy style on.' : 'Sketchy style off.');
  });

  function applyColorToSelection() {
    if (state.selected >= 0) {
      pushUndo();
      state.shapes[state.selected].color = state.color;
      render();
    }
  }

  document.getElementById('color-picker').addEventListener('input', (e) => {
    state.color = e.target.value;
    applyColorToSelection();
  });
  document.getElementById('width-slider').addEventListener('input', (e) => {
    state.width = parseFloat(e.target.value);
    document.getElementById('width-value').textContent = state.width.toFixed(1);
    if (state.selected >= 0) { pushUndo(); state.shapes[state.selected].width = state.width; render(); }
  });
  document.getElementById('fill-toggle').addEventListener('change', (e) => {
    state.fill = e.target.checked;
    if (state.selected >= 0) { pushUndo(); state.shapes[state.selected].filled = state.fill; render(); }
  });
  document.getElementById('fill-color').addEventListener('input', (e) => {
    state.fillColor = e.target.value;
    if (state.selected >= 0) { pushUndo(); state.shapes[state.selected].fillColor = state.fillColor; render(); }
  });
  document.getElementById('line-style').addEventListener('change', (e) => {
    state.lineStyle = e.target.value;
    if (state.selected >= 0) { pushUndo(); state.shapes[state.selected].lineStyle = state.lineStyle; render(); }
  });
  document.getElementById('head-style').addEventListener('change', (e) => {
    state.headStyle = e.target.value;
    if (state.selected >= 0 && state.shapes[state.selected].type === 'arrow') {
      pushUndo(); state.shapes[state.selected].headStyle = state.headStyle; render();
    }
  });
  document.getElementById('curve-slider').addEventListener('input', (e) => {
    state.bend = parseFloat(e.target.value);
    document.getElementById('curve-value').textContent = state.bend;
    const s = state.selected >= 0 ? state.shapes[state.selected] : null;
    if (s && (s.type === 'line' || s.type === 'arrow')) {
      pushUndo(); s.bend = state.bend; render();
    }
  });
  document.getElementById('fontsize-slider').addEventListener('input', (e) => {
    state.fontsize = parseInt(e.target.value, 10);
    document.getElementById('fontsize-value').textContent = state.fontsize;
    const s = state.selected >= 0 ? state.shapes[state.selected] : null;
    if (s && s.type === 'text') { pushUndo(); s.fontsize = state.fontsize; render(); }
  });
  document.getElementById('btn-reverse-arrow').addEventListener('click', () => {
    const s = state.selected >= 0 ? state.shapes[state.selected] : null;
    if (!s || (s.type !== 'line' && s.type !== 'arrow')) { setStatus('Select a line or arrow to reverse.'); return; }
    pushUndo();
    const tmp = s.p0; s.p0 = s.p1; s.p1 = tmp;
    s.bend = -(s.bend || 0); // swapping endpoints negates the chord direction, so
    render();                // negate bend too to keep the same visual curve
    setStatus('Direction reversed.');
  });
  /* --------------------------------------------------------- presets */
  const presetSelect = document.getElementById('preset-select');
  if (presetSelect) {
    PRESET_NAMES.forEach((name) => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = PRESET_LABELS[name];
      presetSelect.appendChild(opt);
    });
    document.getElementById('btn-insert-preset').addEventListener('click', () => {
      const name = presetSelect.value;
      // Insert centered on whatever part of the (now-infinite) canvas the
      // user is currently looking at, rather than always at the top-left.
      const cx = (canvasWrap.scrollLeft + canvasWrap.clientWidth / 2) / state.zoom;
      const cy = (canvasWrap.scrollTop + canvasWrap.clientHeight / 2) / state.zoom;
      pushUndo();
      const newShapes = buildPreset(name, cx, cy, 1.0, state.color, state.width);
      state.shapes.push(...newShapes);
      let nb0 = Infinity, nb1 = Infinity, nb2 = -Infinity, nb3 = -Infinity;
      for (const sh of newShapes) {
        const bb = shapeBBox(sh);
        nb0 = Math.min(nb0, bb[0]); nb1 = Math.min(nb1, bb[1]);
        nb2 = Math.max(nb2, bb[2]); nb3 = Math.max(nb3, bb[3]);
      }
      growCanvasToInclude(nb2, nb3);
      growCanvasToInclude(nb0, nb1);
      state.selected = state.shapes.length - 1;
      render();
      setStatus(`Preset inserted: ${PRESET_LABELS[name] || name}`);
    });
  }

  document.getElementById('auto-finish').addEventListener('change', (e) => { state.autoFinish = e.target.checked; });
  document.getElementById('snap-grid').addEventListener('change', (e) => { state.snapGrid = e.target.checked; });
  document.getElementById('show-grid').addEventListener('change', (e) => { state.showGrid = e.target.checked; render(); });

  document.getElementById('btn-undo').addEventListener('click', undo);
  document.getElementById('btn-redo').addEventListener('click', redo);
  document.getElementById('btn-delete').addEventListener('click', () => {
    if (state.selected >= 0) { pushUndo(); state.shapes.splice(state.selected, 1); state.selected = -1; render(); }
  });
  document.getElementById('btn-clear').addEventListener('click', clearAll);
  function clearAll() {
    if (!state.shapes.length) return;
    if (confirm('Clear the entire drawing?')) { pushUndo(); state.shapes = []; state.selected = -1; render(); }
  }
  document.getElementById('btn-new').addEventListener('click', clearAll);
  document.getElementById('btn-new-window').addEventListener('click', () => {
    window.open(window.location.pathname, '_blank');
  });
  document.getElementById('btn-help').addEventListener('click', () => {
    alert('VanovaTikZSketch — quick help\n\n'
      + 'Pen: freehand drawing; an almost-closed shape automatically becomes a closed shape (Auto-finish).\n'
      + 'Line / Arrow: click and drag.\n'
      + 'Ellipse: click and drag (hold Fill to make it filled).\n'
      + 'Text: click, then type (LaTeX allowed, e.g. $\\alpha$).\n'
      + 'Select: click to select/move; Delete to remove.\n'
      + 'Presets: pick a ready-made shape (circle, star, torus, lens...) and click Insert -- it drops centered on your current view.\n'
      + 'Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z redo, Ctrl/Cmd+C/V/D copy/paste/duplicate.\n'
      + 'Ctrl/Cmd + scroll wheel: zoom.\n'
      + 'The canvas grows automatically in every direction as you draw near an edge -- there is no fixed boundary.');
  });

  document.getElementById('btn-save').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify({ shapes: state.shapes }, null, 1)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'figure.json';
    a.click();
  });
  document.getElementById('btn-open').addEventListener('click', () => document.getElementById('file-input').click());
  document.getElementById('file-input').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        pushUndo();
        state.shapes = data.shapes || [];
        state.selected = -1;
        render();
        setStatus('Project loaded.');
      } catch (err) { alert('Invalid file.'); }
    };
    reader.readAsText(file);
    e.target.value = '';
  });

  document.getElementById('btn-copy').addEventListener('click', () => {
    const out = document.getElementById('tikz-output');
    out.select();
    navigator.clipboard.writeText(out.value).then(() => setStatus('TikZ code copied.'));
  });
  document.getElementById('btn-download-tex').addEventListener('click', () => {
    const blob = new Blob([document.getElementById('tikz-output').value], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'figure.tex';
    a.click();
  });
  document.getElementById('btn-download-svg').addEventListener('click', () => {
    const svg = shapesToSVG(state.shapes, canvas.width, canvas.height);
    const blob = new Blob([svg], { type: 'image/svg+xml' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'figure.svg';
    a.click();
  });
  document.getElementById('btn-download-png').addEventListener('click', () => {
    // Render onto a plain off-screen canvas (true white background, no
    // grid, no selection box) so the downloaded PNG matches the SVG/TikZ
    // export rather than the softened editing-canvas tint or UI overlays.
    // Exported at a high supersampling factor (SCALE) so the PNG is sharp
    // and print/publication quality instead of the raw 1:1 editor
    // resolution, which looked blurry/pixelated once dropped into a paper
    // or a slide and zoomed in.
    if (!state.shapes.length) { setStatus('Nothing to export yet -- draw something first.'); return; }
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const s of state.shapes) {
      const bb = shapeBBox(s);
      x0 = Math.min(x0, bb[0]); y0 = Math.min(y0, bb[1]);
      x1 = Math.max(x1, bb[2]); y1 = Math.max(y1, bb[3]);
    }
    const margin = 40;
    const w = (x1 - x0) + 2 * margin, h = (y1 - y0) + 2 * margin;
    const SCALE = 3; // supersampling factor -> sharp, publication-quality PNG
    const off = document.createElement('canvas');
    off.width = Math.max(1, Math.round(w * SCALE));
    off.height = Math.max(1, Math.round(h * SCALE));
    const offCtx = off.getContext('2d');
    offCtx.fillStyle = '#ffffff';
    offCtx.fillRect(0, 0, off.width, off.height);
    offCtx.scale(SCALE, SCALE);
    offCtx.translate(margin - x0, margin - y0);
    for (const s of state.shapes) renderShape(offCtx, s, false);
    off.toBlob((blob) => {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'figure.png';
      a.click();
      setStatus('High-resolution PNG exported.');
    }, 'image/png');
  });

  /* --------------------------------------------------- view: zoom/fit */
  function applyZoom() {
    canvas.style.transform = `scale(${state.zoom})`;
    canvas.style.transformOrigin = 'top left';
    document.getElementById('zoom-label').textContent = Math.round(state.zoom * 100) + '%';
  }
  function zoomBy(factor) {
    state.zoom = Math.min(4, Math.max(0.2, state.zoom * factor));
    applyZoom();
  }
  document.getElementById('btn-zoom-in').addEventListener('click', () => zoomBy(1.15));
  document.getElementById('btn-zoom-out').addEventListener('click', () => zoomBy(1 / 1.15));
  document.getElementById('btn-zoom-reset').addEventListener('click', () => { state.zoom = 1; applyZoom(); });
  document.getElementById('btn-fit').addEventListener('click', () => {
    if (!state.shapes.length) { state.zoom = 1; applyZoom(); return; }
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const s of state.shapes) {
      const bb = shapeBBox(s);
      x0 = Math.min(x0, bb[0]); y0 = Math.min(y0, bb[1]);
      x1 = Math.max(x1, bb[2]); y1 = Math.max(y1, bb[3]);
    }
    const w = canvasWrap.clientWidth - 60, h = canvasWrap.clientHeight - 60;
    const scale = Math.min(w / Math.max(x1 - x0, 1), h / Math.max(y1 - y0, 1), 3);
    state.zoom = Math.max(0.2, scale);
    applyZoom();
    canvasWrap.scrollTo({ left: Math.max(0, x0 * state.zoom - 30), top: Math.max(0, y0 * state.zoom - 30), behavior: 'smooth' });
  });

  /* --------------------------------------- shape: copy/paste/duplicate */
  function copySelected() {
    if (state.selected < 0) { setStatus('No shape selected to copy (click a shape, or draw one).'); return; }
    state.clipboard = cloneShape(state.shapes[state.selected]);
    setStatus('Shape copied.');
  }
  function pasteClipboard() {
    if (!state.clipboard) { setStatus('Clipboard empty -- copy a shape first.'); return; }
    pushUndo();
    const s = cloneShape(state.clipboard);
    translateShape(s, 16, 16);
    state.shapes.push(s);
    state.selected = state.shapes.length - 1;
    render();
    setStatus('Shape pasted.');
  }
  function duplicateSelected() {
    if (state.selected < 0) { setStatus('No shape selected to duplicate (click a shape, or draw one).'); return; }
    pushUndo();
    const s = cloneShape(state.shapes[state.selected]);
    translateShape(s, 16, 16);
    state.shapes.push(s);
    state.selected = state.shapes.length - 1;
    render();
    setStatus('Shape duplicated.');
  }
  document.getElementById('btn-copy-shape').addEventListener('click', copySelected);
  document.getElementById('btn-paste-shape').addEventListener('click', pasteClipboard);
  document.getElementById('btn-duplicate-shape').addEventListener('click', duplicateSelected);

  /* ------------------------------------------------------------ order */
  function reorder(fn) {
    if (state.selected < 0) return;
    pushUndo();
    const i = state.selected;
    const j = fn(i, state.shapes.length);
    if (j === i || j < 0 || j >= state.shapes.length) { state.undoStack.pop(); return; }
    const [s] = state.shapes.splice(i, 1);
    state.shapes.splice(j, 0, s);
    state.selected = j;
    render();
  }
  document.getElementById('btn-front').addEventListener('click', () => reorder((i, n) => n - 1));
  document.getElementById('btn-forward').addEventListener('click', () => reorder((i) => i + 1));
  document.getElementById('btn-backward').addEventListener('click', () => reorder((i) => i - 1));
  document.getElementById('btn-back').addEventListener('click', () => reorder(() => 0));

  /* -------------------------------------------------------- transform */
  function transformSelected(fn) {
    if (state.selected < 0) return;
    pushUndo();
    fn(state.shapes[state.selected]);
    render();
  }
  function bboxCenter(s) {
    const bb = shapeBBox(s);
    return [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2];
  }
  function mapPoints(s, fn) {
    if (s.type === 'stroke') s.segments = s.segments.map((seg) => seg.map(fn));
    else if (s.type === 'line' || s.type === 'arrow') { s.p0 = fn(s.p0); s.p1 = fn(s.p1); }
    else if (s.type === 'ellipse') { const c = fn([s.cx, s.cy]); s.cx = c[0]; s.cy = c[1]; }
    else if (s.type === 'polygon') s.points = s.points.map(fn);
    else if (s.type === 'text') { const p = fn([s.x, s.y]); s.x = p[0]; s.y = p[1]; }
  }
  document.getElementById('btn-flip-h').addEventListener('click', () => transformSelected((s) => {
    const [cx] = bboxCenter(s);
    mapPoints(s, ([x, y]) => [2 * cx - x, y]);
    // mirroring reverses handedness, so a curved line/arrow's bend must be
    // negated too or the curve would bulge back out on the same side
    if ((s.type === 'line' || s.type === 'arrow') && s.bend) s.bend = -s.bend;
  }));
  document.getElementById('btn-flip-v').addEventListener('click', () => transformSelected((s) => {
    const [, cy] = bboxCenter(s);
    mapPoints(s, ([x, y]) => [x, 2 * cy - y]);
    if ((s.type === 'line' || s.type === 'arrow') && s.bend) s.bend = -s.bend;
  }));
  document.getElementById('btn-rotate').addEventListener('click', () => transformSelected((s) => {
    const [cx, cy] = bboxCenter(s);
    mapPoints(s, ([x, y]) => [cx - (y - cy), cy + (x - cx)]);
  }));

  render();
  applyZoom();
  setStatus('Ready.');
})();
