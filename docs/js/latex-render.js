/*
 * latex-render.js
 * JS port of the desktop app's latex_render.py: best-effort LaTeX -> Unicode
 * for ON-SCREEN display only (browsers/canvas can't render real LaTeX any
 * more than Qt can) -- \Sigma, \alpha, \to, x^2, x_1 read like the real
 * symbols on the canvas. The shape's STORED text is always kept as the
 * original LaTeX source, so TikZ/.tex export compiles exactly as typed;
 * this function is only ever used for what gets painted on screen.
 */

const GREEK = {
  alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε', varepsilon: 'ε',
  zeta: 'ζ', eta: 'η', theta: 'θ', vartheta: 'ϑ', iota: 'ι', kappa: 'κ',
  lambda: 'λ', mu: 'μ', nu: 'ν', xi: 'ξ', pi: 'π', varpi: 'ϖ', rho: 'ρ',
  varrho: 'ϱ', sigma: 'σ', varsigma: 'ς', tau: 'τ', upsilon: 'υ', phi: 'φ',
  varphi: 'φ', chi: 'χ', psi: 'ψ', omega: 'ω',
  Gamma: 'Γ', Delta: 'Δ', Theta: 'Θ', Lambda: 'Λ', Xi: 'Ξ', Pi: 'Π',
  Sigma: 'Σ', Upsilon: 'Υ', Phi: 'Φ', Psi: 'Ψ', Omega: 'Ω',
};

const OPS = {
  to: '→', rightarrow: '→', Rightarrow: '⇒', leftarrow: '←', Leftarrow: '⇐',
  leftrightarrow: '↔', Leftrightarrow: '⇔', mapsto: '↦', longmapsto: '⟼',
  longrightarrow: '⟶', longleftarrow: '⟵', hookrightarrow: '↪', hookleftarrow: '↩',
  twoheadrightarrow: '↠', rightsquigarrow: '⇝',
  circ: '∘', bullet: '•', times: '×', cdot: '·', ast: '∗', star: '⋆',
  otimes: '⊗', oplus: '⊕', ominus: '⊖', odot: '⊙',
  wedge: '∧', vee: '∨', cup: '∪', cap: '∩', setminus: '∖',
  partial: '∂', nabla: '∇', infty: '∞', pm: '±', mp: '∓',
  leq: '≤', geq: '≥', neq: '≠', approx: '≈', sim: '∼', simeq: '≃', cong: '≅',
  equiv: '≡', propto: '∝',
  subset: '⊂', subseteq: '⊆', supset: '⊃', supseteq: '⊇',
  in: '∈', notin: '∉', ni: '∋', forall: '∀', exists: '∃', nexists: '∄',
  emptyset: '∅', varnothing: '∅',
  ldots: '…', cdots: '⋯', vdots: '⋮', ddots: '⋱',
  ell: 'ℓ', hbar: 'ℏ', Re: 'ℜ', Im: 'ℑ', wp: '℘',
  perp: '⊥', parallel: '∥', angle: '∠', triangle: '△',
  square: '□', diamond: '◇', top: '⊤', bot: '⊥',
  oint: '∮', int: '∫', sum: '∑', prod: '∏', coprod: '∐',
  sqrt: '√', pmod: 'mod', boxtimes: '⊠',
  dagger: '†', ddagger: '‡', aleph: 'ℵ', prime: '′',
  hat: '^', tilde: '~', bar: '¯', colon: ':', cdotp: '·',
};

const MACROS = { ...GREEK, ...OPS };

const SUP = {
  0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹',
  '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾', n: 'ⁿ', i: 'ⁱ',
  a: 'ᵃ', b: 'ᵇ', c: 'ᶜ', d: 'ᵈ', e: 'ᵉ', f: 'ᶠ', g: 'ᵍ', h: 'ʰ', j: 'ʲ',
  k: 'ᵏ', l: 'ˡ', m: 'ᵐ', o: 'ᵒ', p: 'ᵖ', r: 'ʳ', s: 'ˢ', t: 'ᵗ', u: 'ᵘ',
  v: 'ᵛ', w: 'ʷ', x: 'ˣ', y: 'ʸ', z: 'ᶻ',
};
const SUB = {
  0: '₀', 1: '₁', 2: '₂', 3: '₃', 4: '₄', 5: '₅', 6: '₆', 7: '₇', 8: '₈', 9: '₉',
  '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
  a: 'ₐ', e: 'ₑ', h: 'ₕ', i: 'ᵢ', j: 'ⱼ', k: 'ₖ', l: 'ₗ', m: 'ₘ', n: 'ₙ',
  o: 'ₒ', p: 'ₚ', r: 'ᵣ', s: 'ₛ', t: 'ₜ', u: 'ᵤ', v: 'ᵥ', x: 'ₓ',
};

function scriptChars(text, table) {
  return text.split('').map((ch) => table[ch] || ch).join('');
}

function replaceScripts(text, marker, table) {
  let out = '';
  let i = 0;
  const n = text.length;
  while (i < n) {
    if (text[i] === marker && i + 1 < n) {
      if (text[i + 1] === '{') {
        const j = text.indexOf('}', i + 2);
        if (j !== -1) {
          out += scriptChars(text.slice(i + 2, j), table);
          i = j + 1;
          continue;
        }
      } else {
        out += scriptChars(text[i + 1], table);
        i += 2;
        continue;
      }
    }
    out += text[i];
    i += 1;
  }
  return out;
}

/** LaTeX source -> best-effort Unicode for on-screen display only. */
function latexToDisplay(text) {
  if (!text) return text;
  let s = text.trim();
  if (s.startsWith('$') && s.endsWith('$') && s.length >= 2) s = s.slice(1, -1);
  s = s.replace(/\\,/g, ' ').replace(/\\ /g, ' ').replace(/\\!/g, '');
  s = s.replace(/\\left/g, '').replace(/\\right/g, '');
  s = s.replace(/\\([A-Za-z]+)/g, (m, name) => (MACROS[name] !== undefined ? MACROS[name] : name));
  s = replaceScripts(s, '^', SUP);
  s = replaceScripts(s, '_', SUB);
  s = s.replace(/\{/g, '').replace(/\}/g, '');
  return s;
}
