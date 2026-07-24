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

  const PALETTE = ['#000000', '#ffffff', '#e53935', '#1e88e5', '#43a047',
    '#fdd835', '#fb8c00', '#8e24aa', '#00acc1', '#6d4c41'];
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

  function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    drawGrid(canvas, ctx);
    state.shapes.forEach((s, i) => renderShape(ctx, s, i === state.selected));
    if (drag && drag.previewShape) renderShape(ctx, drag.previewShape, false);
    if (polyPoints && polyPoints.length) {
      renderShape(ctx, { type: 'polygon', points: polyPoints, closed: false, color: state.color, width: state.width, lineStyle: 'dashed' }, false);
      for (const p of polyPoints) {
        ctx.beginPath();
        ctx.arc(p[0], p[1], 3, 0, Math.PI * 2);
        ctx.fillStyle = '#2563eb';
        ctx.fill();
      }
    }
    renderPreview();
    updateTikz();
  }

  function renderPreview() {
    previewCtx.clearRect(0, 0, previewCanvas.width, previewCanvas.height);
    previewCtx.fillStyle = '#ffffff';
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
  let polyPoints = null; // in-progress polygon

  function snap(v) { return state.snapGrid ? Math.round(v / GRID_STEP) * GRID_STEP : v; }

  function pointerPos(evt) {
    const r = canvas.getBoundingClientRect();
    const sx = canvas.width / r.width, sy = canvas.height / r.height;
    return [snap((evt.clientX - r.left) * sx), snap((evt.clientY - r.top) * sy)];
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
    render();
    setStatus(closed ? 'Forme fermée ajoutée (auto-finish).' : 'Trait ajouté.');
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
    } else if (state.tool === 'polygon') {
      if (!polyPoints) polyPoints = [];
      polyPoints.push([x, y]);
      drag = { kind: 'polygon' };
      render();
    } else if (state.tool === 'text') {
      const txt = prompt('Texte (LaTeX autorisé, ex: $\\alpha$):', '');
      if (txt) {
        pushUndo();
        state.shapes.push({ type: 'text', x, y, text: txt, latex: true, color: state.color, fontsize: 16 });
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
      updateHeadStyleUI();
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
      render();
    } else if (drag.kind === 'line' || drag.kind === 'arrow') {
      drag.p1 = [x, y];
      drag.previewShape = { type: drag.kind, p0: drag.p0, p1: drag.p1, headStyle: state.headStyle, ...newShapeBase() };
      render();
    } else if (drag.kind === 'ellipse') {
      drag.p1 = [x, y];
      const cx = (drag.p0[0] + drag.p1[0]) / 2, cy = (drag.p0[1] + drag.p1[1]) / 2;
      const rx = Math.abs(drag.p1[0] - drag.p0[0]) / 2, ry = Math.abs(drag.p1[1] - drag.p0[1]) / 2;
      drag.previewShape = { type: 'ellipse', cx, cy, rx, ry, filled: state.fill, fillColor: state.fillColor, ...newShapeBase() };
      render();
    } else if (drag.kind === 'move' && state.selected >= 0) {
      const dx = x - drag.last[0], dy = y - drag.last[1];
      translateShape(state.shapes[state.selected], dx, dy);
      drag.last = [x, y];
      render();
    }
  });

  canvas.addEventListener('pointerup', () => {
    if (!drag) return;
    if (drag.kind === 'pen') {
      finishFreehand(drag.points);
    } else if (drag.kind === 'line' || drag.kind === 'arrow') {
      if (Math.hypot(drag.p1[0] - drag.p0[0], drag.p1[1] - drag.p0[1]) > 2) {
        pushUndo();
        const s = { type: drag.kind, p0: drag.p0, p1: drag.p1, ...newShapeBase() };
        if (drag.kind === 'arrow') s.headStyle = state.headStyle;
        state.shapes.push(s);
      }
    } else if (drag.kind === 'ellipse') {
      const cx = (drag.p0[0] + drag.p1[0]) / 2, cy = (drag.p0[1] + drag.p1[1]) / 2;
      const rx = Math.abs(drag.p1[0] - drag.p0[0]) / 2, ry = Math.abs(drag.p1[1] - drag.p0[1]) / 2;
      if (rx > 2 && ry > 2) {
        pushUndo();
        state.shapes.push({ type: 'ellipse', cx, cy, rx, ry, filled: state.fill, fillColor: state.fillColor, ...newShapeBase() });
      }
    }
    drag = null;
    render();
  });

  canvas.addEventListener('dblclick', () => {
    if (state.tool === 'polygon' && polyPoints && polyPoints.length >= 3) {
      pushUndo();
      state.shapes.push({ type: 'polygon', points: polyPoints, closed: true, filled: state.fill, fillColor: state.fillColor, ...newShapeBase() });
      polyPoints = null;
      render();
    }
  });

  canvas.addEventListener('wheel', (evt) => {
    if (!evt.ctrlKey && !evt.metaKey) return;
    evt.preventDefault();
    zoomBy(evt.deltaY < 0 ? 1.1 : 1 / 1.1);
  }, { passive: false });

  window.addEventListener('keydown', (evt) => {
    const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName);
    if (typing) return;
    if (evt.key === 'Enter' && state.tool === 'polygon' && polyPoints && polyPoints.length >= 2) {
      pushUndo();
      state.shapes.push({ type: 'polygon', points: polyPoints, closed: false, ...newShapeBase() });
      polyPoints = null;
      render();
    } else if (evt.key === 'Escape') {
      polyPoints = null;
      render();
    } else if ((evt.key === 'Delete' || evt.key === 'Backspace') && state.selected >= 0) {
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
      polyPoints = null;
      updateHeadStyleUI();
      setStatus(`Outil : ${btn.textContent.trim()}`);
    });
  });

  function updateHeadStyleUI() {
    document.getElementById('head-style-group').style.display = state.tool === 'arrow' ? 'flex' : 'none';
  }

  function syncControlsToSelection() {
    if (state.selected < 0) return;
    const s = state.shapes[state.selected];
    if (s.color) { document.getElementById('color-picker').value = s.color; state.color = s.color; }
    if (s.width) { document.getElementById('width-slider').value = s.width; document.getElementById('width-value').textContent = Number(s.width).toFixed(1); state.width = s.width; }
    document.getElementById('fill-toggle').checked = !!s.filled;
    document.getElementById('line-style').value = s.lineStyle || 'solid';
    if (s.type === 'arrow') document.getElementById('head-style').value = s.headStyle || 'stealth';
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
    if (confirm('Effacer tout le dessin ?')) { pushUndo(); state.shapes = []; state.selected = -1; render(); }
  }
  document.getElementById('btn-new').addEventListener('click', clearAll);
  document.getElementById('btn-new-window').addEventListener('click', () => {
    window.open(window.location.pathname, '_blank');
  });
  document.getElementById('btn-help').addEventListener('click', () => {
    alert('VanovaTikZSketch — aide rapide\n\n'
      + 'Pen : dessine à main levée ; une forme presque fermée devient automatiquement une forme fermée (Auto-finish).\n'
      + 'Line / Arrow : cliquer-glisser.\n'
      + 'Ellipse : cliquer-glisser (bounding box).\n'
      + 'Polygon : cliquer chaque sommet, double-clic ou Entrée pour fermer, Échap pour annuler.\n'
      + 'Text : cliquer, puis taper (LaTeX autorisé, ex: $\\alpha$).\n'
      + 'Select : cliquer pour sélectionner/déplacer ; Suppr pour effacer.\n'
      + 'Ctrl/Cmd+Z annule, Ctrl/Cmd+Shift+Z refait, Ctrl/Cmd+C/V/D copie/colle/duplique.\n'
      + 'Ctrl/Cmd + molette : zoom.');
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
        setStatus('Projet chargé.');
      } catch (err) { alert('Fichier invalide.'); }
    };
    reader.readAsText(file);
    e.target.value = '';
  });

  document.getElementById('btn-copy').addEventListener('click', () => {
    const out = document.getElementById('tikz-output');
    out.select();
    navigator.clipboard.writeText(out.value).then(() => setStatus('Code TikZ copié.'));
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
    if (state.selected < 0) return;
    state.clipboard = cloneShape(state.shapes[state.selected]);
    setStatus('Forme copiée.');
  }
  function pasteClipboard() {
    if (!state.clipboard) return;
    pushUndo();
    const s = cloneShape(state.clipboard);
    translateShape(s, 16, 16);
    state.shapes.push(s);
    state.selected = state.shapes.length - 1;
    render();
    setStatus('Forme collée.');
  }
  function duplicateSelected() {
    if (state.selected < 0) return;
    pushUndo();
    const s = cloneShape(state.shapes[state.selected]);
    translateShape(s, 16, 16);
    state.shapes.push(s);
    state.selected = state.shapes.length - 1;
    render();
    setStatus('Forme dupliquée.');
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
  }));
  document.getElementById('btn-flip-v').addEventListener('click', () => transformSelected((s) => {
    const [, cy] = bboxCenter(s);
    mapPoints(s, ([x, y]) => [x, 2 * cy - y]);
  }));
  document.getElementById('btn-rotate').addEventListener('click', () => transformSelected((s) => {
    const [cx, cy] = bboxCenter(s);
    mapPoints(s, ([x, y]) => [cx - (y - cy), cy + (x - cx)]);
  }));

  /* --------------------------------------------------------- presets */
  const presetSelect = document.getElementById('preset-select');
  Object.keys(PRESET_LABELS).forEach((key) => {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = PRESET_LABELS[key];
    presetSelect.appendChild(opt);
  });
  document.getElementById('btn-insert-preset').addEventListener('click', () => {
    const name = presetSelect.value;
    if (!name) return;
    const shapes = buildPreset(name, canvas.width / 2, canvas.height / 2, state.color, state.width);
    if (!shapes.length) return;
    pushUndo();
    state.shapes.push(...shapes);
    render();
    setStatus(`Preset inséré : ${PRESET_LABELS[name]}`);
  });

  render();
  applyZoom();
  setStatus('Prêt.');
})();
