"""Shared helpers: comment stripping, table extraction, number harvesting.

Stdlib only. A finding is a dict ``{category, severity, target, reasoning, suggested_fix,
numbers, confidence}``.
"""

from __future__ import annotations

import re
from typing import Any

_COMMENT_RE = re.compile(r"(?<!\\)%.*")
_TABULAR_RE = re.compile(r"\\begin\{(tabular\*?|tabularx|array)\}.*?\\end\{\1\}", re.DOTALL)
_DECIMAL_RE = re.compile(r"-?\d+\.\d+")
_INT_RE = re.compile(r"-?\d+")

# Column-width / length specs whose decimals must NOT be read as result numbers.
# `p{2.7cm}` is a column width, not a result "2.7".
_COLSPEC_RE = re.compile(r"[pmb]\{[^{}]*\}")
_LENGTH_RE = re.compile(r"-?\d*\.?\d+\s*(?:cm|mm|pt|em|ex|in|bp|dd|pc|sp|\\[a-zA-Z]+)")
_HSPACE_RE = re.compile(r"\\(?:hspace|vspace|hskip|vskip|setlength|arraystretch|extrarowheight|addlinespace)\*?\{[^{}]*\}")


def strip_comments(tex: str) -> str:
    return _COMMENT_RE.sub("", tex)


def tabular_blocks(tex: str) -> list[str]:
    return [m.group(0) for m in _TABULAR_RE.finditer(strip_comments(tex))]


_DEFINITION_RE = re.compile(r"\\(?:renewcommand|newcommand|setlength|addtolength|setcounter)\*?\s*\{[^{}]*\}(?:\[[^\]]*\])*\s*\{[^{}]*\}")


def strip_typography(fragment: str) -> str:
    """Remove length/column-width/spacing constructs before harvesting result numbers."""
    frag = _DEFINITION_RE.sub(" ", fragment)
    frag = _HSPACE_RE.sub(" ", frag)
    frag = _COLSPEC_RE.sub(" ", frag)
    frag = _LENGTH_RE.sub(" ", frag)
    return frag


def harvest_result_decimals(tex: str) -> list[str]:
    """Decimals inside tabular environments, excluding column widths / lengths."""
    out: list[str] = []
    for block in tabular_blocks(tex):
        out.extend(_DECIMAL_RE.findall(strip_typography(block)))
    return out


def normalize_number(num_str: str) -> str:
    """Canonical form so "0.850" == "0.85" and "60.0" == "60"."""
    try:
        value = float(num_str)
    except ValueError:
        return num_str.strip()
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(value)


def objection(
    category: str,
    severity: str,
    target: str,
    reasoning: str,
    suggested_fix: str = "",
    numbers: list[str] | None = None,
    confidence: float = 0.6,
) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "target": target,
        "reasoning": reasoning,
        "suggested_fix": suggested_fix,
        "numbers": [normalize_number(n) for n in (numbers or [])],
        "confidence": confidence,
        "detector_origin": "paper-fact-check",
    }


def body_text(tex: str) -> str:
    """Document body after \\begin{document}, comments stripped."""
    tex = strip_comments(tex)
    i = tex.find("\\begin{document}")
    return tex[i:] if i >= 0 else tex
