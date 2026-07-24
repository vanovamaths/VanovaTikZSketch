"""
latex_render.py  (v4.3)
Keyboard-typed labels, Quiver-diagram philosophy: you type real LaTeX
(\\varphi, \\to, \\Sigma_g, x^2...) with the Text/LaTeX tool or "Name (L)" --
no drawing needed for letters. This module converts that LaTeX source into
readable on-screen Unicode (Greek letters, arrows, operators, sub/superscripts)
for the canvas/preview, while the STORED text stays the real LaTeX source, so
TikZ/SVG/.tex export keeps compiling exactly as typed.

This is a best-effort Unicode approximation for on-screen display (Qt has no
LaTeX engine) -- it is not used for export.
"""
from __future__ import annotations
import re

GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "varepsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π",
    "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ", "sigma": "σ",
    "varsigma": "ς", "tau": "τ", "upsilon": "υ", "phi": "φ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ",
    "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

OPS = {
    "to": "→", "rightarrow": "→", "Rightarrow": "⇒", "leftarrow": "←",
    "Leftarrow": "⇐", "leftrightarrow": "↔", "Leftrightarrow": "⇔",
    "mapsto": "↦", "longmapsto": "⟼", "longrightarrow": "⟶",
    "longleftarrow": "⟵", "hookrightarrow": "↪", "hookleftarrow": "↩",
    "twoheadrightarrow": "↠", "rightsquigarrow": "⇝",
    "circ": "∘", "bullet": "•", "times": "×", "cdot": "·", "ast": "∗",
    "star": "⋆", "otimes": "⊗", "oplus": "⊕", "ominus": "⊖", "odot": "⊙",
    "wedge": "∧", "vee": "∨", "cup": "∪", "cap": "∩", "setminus": "∖",
    "partial": "∂", "nabla": "∇", "infty": "∞", "pm": "±", "mp": "∓",
    "leq": "≤", "geq": "≥", "neq": "≠", "approx": "≈", "sim": "∼",
    "simeq": "≃", "cong": "≅", "equiv": "≡", "propto": "∝",
    "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "supseteq": "⊇",
    "in": "∈", "notin": "∉", "ni": "∋", "forall": "∀", "exists": "∃",
    "nexists": "∄", "emptyset": "∅", "varnothing": "∅",
    "ldots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱",
    "ell": "ℓ", "hbar": "ℏ", "Re": "ℜ", "Im": "ℑ", "wp": "℘",
    "perp": "⊥", "parallel": "∥", "angle": "∠", "triangle": "△",
    "square": "□", "diamond": "◇", "top": "⊤", "bot": "⊥",
    "oint": "∮", "int": "∫", "sum": "∑", "prod": "∏", "coprod": "∐",
    "sqrt": "√", "pmod": "mod", "otimes": "⊗", "boxtimes": "⊠",
    "dagger": "†", "ddagger": "‡", "aleph": "ℵ", "prime": "′",
    "cong": "≅", "simeq": "≃", "hat": "^", "tilde": "~", "bar": "¯",
    "colon": ":", "cdotp": "·",
}

MACROS = {**GREEK, **OPS}

_SUP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
    "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "=": "⁼",
    "(": "⁽", ")": "⁾", "n": "ⁿ", "i": "ⁱ",
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ",
    "h": "ʰ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "o": "ᵒ", "p": "ᵖ",
    "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ", "v": "ᵛ", "w": "ʷ", "x": "ˣ",
    "y": "ʸ", "z": "ᶻ",
}
_SUB = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆",
    "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋", "=": "₌",
    "(": "₍", ")": "₎", "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ",
    "k": "ₖ", "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}

_MACRO_RE = re.compile(r"\\([A-Za-z]+)")


def _replace_macros(text: str) -> str:
    def repl(m):
        name = m.group(1)
        return MACROS.get(name, name)  # unknown macro: drop the backslash
    return _MACRO_RE.sub(repl, text)


def _script(text: str, table: dict) -> str:
    return "".join(table.get(ch, ch) for ch in text)


def _replace_scripts(text: str, marker: str, table: dict) -> str:
    # marker{...} form
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == marker and i + 1 < n:
            if text[i + 1] == "{":
                j = text.find("}", i + 2)
                if j != -1:
                    body = text[i + 2:j]
                    out.append(_script(body, table))
                    i = j + 1
                    continue
            else:
                out.append(_script(text[i + 1], table))
                i += 2
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def latex_to_display(text: str) -> str:
    """
    Best-effort LaTeX -> Unicode for on-screen display (Quiver-style: you
    type \\varphi, \\to, \\Sigma_g and it reads like the real symbols).
    The caller keeps the ORIGINAL text for export -- this is display-only.
    """
    if not text:
        return text
    s = text.strip()
    if s.startswith("$") and s.endswith("$") and len(s) >= 2:
        s = s[1:-1]
    s = s.replace("\\,", " ").replace("\\ ", " ").replace("\\!", "")
    s = s.replace("\\left", "").replace("\\right", "")
    s = _replace_macros(s)
    s = _replace_scripts(s, "^", _SUP)
    s = _replace_scripts(s, "_", _SUB)
    s = s.replace("{", "").replace("}", "")
    return s
