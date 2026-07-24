/*
 * tikz-export.js
 * JS port of the desktop app's tikz_export.py: shapes -> TikZ/LaTeX body,
 * wrapped in a standalone-document template. Canvas px -> cm, y-flip
 * (TikZ is bottom-left origin, y-up; canvas is top-left, y-down).
 */

const PX_PER_CM = 60.0;

function colorName(hex) {
  return 'gsColor' + hex.replace('#', '').toUpperCase();
}

function collectColors(shapes) {
  const map = new Map();
  for (const s of shapes) {
    for (const hex of [s.color, s.fillColor]) {
      if (hex && hex.toLowerCase() !== '#000000' && !map.has(hex)) map.set(hex, colorName(hex));
    }
  }
  return map;
}

function colorRef(hex, map) {
  if (!hex || hex.toLowerCase() === '#000000') return 'black';
  return map.get(hex);
}

function fmt(pt) { return `(${pt[0]},${pt[1]})`; }

function arrowTipToken(headStyle) {
  return { stealth: '-{Stealth}', harpoon: '-{Harpoon}', none: '-' }[headStyle] || '->';
}

function shapesToTikzBody(shapes, pxPerCm = PX_PER_CM) {
  let maxY = 0;
  for (const s of shapes) {
    const bb = shapeBBox(s);
    maxY = Math.max(maxY, bb[3]);
  }
  const conv = ([x, y]) => [round3(x / pxPerCm), round3((maxY - y) / pxPerCm)];
  const colorMap = collectColors(shapes);
  const lines = [];
  for (const [hex, name] of colorMap) {
    lines.push(`\\definecolor{${name}}{HTML}{${hex.replace('#', '').toUpperCase()}}`);
  }
  if (lines.length) lines.push('');

  for (const s of shapes) {
    const strokeRef = colorRef(s.color, colorMap);
    const colorCmd = `draw=${strokeRef}`;
    if (s.type === 'stroke') {
      if (!s.segments.length) continue;
      const p0 = conv(s.segments[0][0]);
      let path = `(${p0[0]},${p0[1]})`;
      for (const [, c1, c2, p3] of s.segments) {
        const cc1 = conv(c1), cc2 = conv(c2), cp3 = conv(p3);
        path += `\n    .. controls ${fmt(cc1)} and ${fmt(cc2)} .. ${fmt(cp3)}`;
      }
      const close = s.closed ? ' -- cycle' : '';
      let style = `${colorCmd}, line width=${(s.width / 2).toFixed(2)}pt`;
      if (s.filled) style += `, fill=${colorRef(s.fillColor || s.color, colorMap)}`;
      if (s.lineStyle === 'dashed') style += ', dashed';
      if (s.lineStyle === 'dotted') style += ', dotted';
      lines.push(`\\draw[${style}] ${path}${close};`);
    } else if (s.type === 'line' || s.type === 'arrow') {
      const isArrow = s.type === 'arrow';
      const tip = isArrow ? arrowTipToken(s.headStyle || 'stealth') : '';
      let style = (isArrow ? `${tip}, ` : '') + colorCmd + `, line width=${(s.width / 2).toFixed(2)}pt`;
      if (s.lineStyle === 'dashed') style += ', dashed';
      if (s.lineStyle === 'dotted') style += ', dotted';
      const P0 = conv(s.p0), P1 = conv(s.p1);
      lines.push(`\\draw[${style}] ${fmt(P0)} -- ${fmt(P1)};`);
    } else if (s.type === 'ellipse') {
      const c = conv([s.cx, s.cy]);
      const rx = round3(Math.abs(s.rx) / pxPerCm), ry = round3(Math.abs(s.ry) / pxPerCm);
      let style = `${colorCmd}, line width=${(s.width / 2).toFixed(2)}pt`;
      if (s.filled) style += `, fill=${colorRef(s.fillColor || s.color, colorMap)}`;
      if (s.lineStyle === 'dashed') style += ', dashed';
      if (s.lineStyle === 'dotted') style += ', dotted';
      lines.push(`\\draw[${style}] ${fmt(c)} ellipse (${rx} and ${ry});`);
    } else if (s.type === 'polygon') {
      const pts = s.points.map(conv);
      const path = pts.map(fmt).join(' -- ');
      const close = s.closed ? ' -- cycle' : '';
      let style = `${colorCmd}, line width=${(s.width / 2).toFixed(2)}pt`;
      if (s.filled) style += `, fill=${colorRef(s.fillColor || s.color, colorMap)}`;
      if (s.lineStyle === 'dashed') style += ', dashed';
      if (s.lineStyle === 'dotted') style += ', dotted';
      lines.push(`\\draw[${style}] ${path}${close};`);
    } else if (s.type === 'text') {
      const p = conv([s.x, s.y]);
      const text = s.latex ? (s.text.startsWith('$') ? s.text : `$${s.text}$`)
        : s.text.replace(/_/g, '\\_').replace(/&/g, '\\&');
      const textColor = strokeRef !== 'black' ? `text=${strokeRef}, ` : '';
      lines.push(`\\node[${textColor}font=\\fontsize{${s.fontsize}}{${s.fontsize + 2}}\\selectfont] at ${fmt(p)} {${text}};`);
    }
  }
  return lines.join('\n');
}

function round3(v) { return Math.round(v * 1000) / 1000; }

/* ------------------------------------------------------------- SVG export */
function shapesToSVG(shapes, width, height) {
  const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const parts = [`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">`];
  parts.push(`<rect x="0" y="0" width="${width}" height="${height}" fill="#ffffff"/>`);
  const dashFor = (s) => s.lineStyle === 'dashed' ? `stroke-dasharray="${Math.max(4, s.width * 3)},${Math.max(3, s.width * 2)}"`
    : s.lineStyle === 'dotted' ? `stroke-dasharray="1,${Math.max(3, s.width * 2)}"` : '';
  for (const s of shapes) {
    if (s.type === 'stroke') {
      if (!s.segments.length) continue;
      let d = `M ${s.segments[0][0][0]} ${s.segments[0][0][1]}`;
      for (const [, c1, c2, p3] of s.segments) d += ` C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${p3[0]} ${p3[1]}`;
      if (s.closed) d += ' Z';
      const fill = s.filled ? (s.fillColor || s.color) : 'none';
      parts.push(`<path d="${d}" stroke="${s.color}" stroke-width="${s.width}" fill="${fill}" stroke-linecap="round" stroke-linejoin="round" ${dashFor(s)}/>`);
    } else if (s.type === 'line' || s.type === 'arrow') {
      parts.push(`<line x1="${s.p0[0]}" y1="${s.p0[1]}" x2="${s.p1[0]}" y2="${s.p1[1]}" stroke="${s.color}" stroke-width="${s.width}" stroke-linecap="round" ${dashFor(s)}/>`);
      if (s.type === 'arrow' && (s.headStyle || 'stealth') !== 'none') {
        const ang = Math.atan2(s.p1[1] - s.p0[1], s.p1[0] - s.p0[0]);
        const size = Math.max(9, s.width * 4);
        const a1 = ang + Math.PI - 0.4, a2 = ang + Math.PI + 0.4;
        const tip = s.p1;
        const p1 = [tip[0] + size * Math.cos(a1), tip[1] + size * Math.sin(a1)];
        const p2 = [tip[0] + size * Math.cos(a2), tip[1] + size * Math.sin(a2)];
        parts.push(`<polygon points="${tip[0]},${tip[1]} ${p1[0]},${p1[1]} ${p2[0]},${p2[1]}" fill="${s.color}"/>`);
      }
    } else if (s.type === 'ellipse') {
      const fill = s.filled ? (s.fillColor || s.color) : 'none';
      parts.push(`<ellipse cx="${s.cx}" cy="${s.cy}" rx="${Math.abs(s.rx)}" ry="${Math.abs(s.ry)}" stroke="${s.color}" stroke-width="${s.width}" fill="${fill}" ${dashFor(s)}/>`);
    } else if (s.type === 'polygon') {
      const pts = s.points.map((p) => `${p[0]},${p[1]}`).join(' ');
      const fill = s.filled ? (s.fillColor || s.color) : 'none';
      const tag = s.closed ? 'polygon' : 'polyline';
      parts.push(`<${tag} points="${pts}" stroke="${s.color}" stroke-width="${s.width}" fill="${fill}" stroke-linecap="round" stroke-linejoin="round" ${dashFor(s)}/>`);
    } else if (s.type === 'text') {
      parts.push(`<text x="${s.x}" y="${s.y}" fill="${s.color}" font-size="${s.fontsize || 16}" dominant-baseline="middle">${esc(s.text)}</text>`);
    }
  }
  parts.push('</svg>');
  return parts.join('\n');
}

function shapesToStandaloneTex(shapes, pxPerCm = PX_PER_CM) {
  const body = shapesToTikzBody(shapes, pxPerCm);
  return `\\documentclass[tikz,border=4pt]{standalone}
\\usepackage{amsmath,amssymb}
\\usepackage{xcolor}
\\usetikzlibrary{arrows.meta}
\\begin{document}
\\begin{tikzpicture}
${body}
\\end{tikzpicture}
\\end{document}
`;
}
