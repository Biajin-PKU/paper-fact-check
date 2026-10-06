"""Recompute p-values from the test statistics printed beside them.

A z statistic and its p-value must agree; for a t statistic, no t distribution gives a two-sided p
below the normal one, so a p far below that is impossible whatever the degrees of freedom. Normal
approximation via math.erfc; stdlib only.
"""

from __future__ import annotations

import math
import re
from typing import Any

from ._common import body_text, objection


def p_two_sided_from_z(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def detect_z_p_mismatch(tex: str, tol: float = 0.5) -> list[dict[str, Any]]:
    """Find 'z=.. , p=..' pairs and flag when recomputed p disagrees by >tol in log10 units."""
    body = body_text(tex)
    out: list[dict[str, Any]] = []
    pat = re.compile(r"[zZ]\s*=\s*(-?\d+\.?\d*)\s*[,;]?\s*p\s*[=<]\s*(\d*\.\d+)")
    for m in pat.finditer(body):
        z = float(m.group(1))
        p_reported = float(m.group(2))
        p_calc = p_two_sided_from_z(z)
        if p_reported > 0 and p_calc > 0:
            if abs(math.log10(p_reported) - math.log10(p_calc)) > tol:
                out.append(objection(
                    "pvalue_z_mismatch", "major", m.group(0).strip(),
                    f"Reported p={p_reported} but a two-sided normal p for z={z} is "
                    f"{p_calc:.2g} — inconsistent by >{tol} log10 units.",
                    "recompute p from the test statistic",
                    numbers=[m.group(2)], confidence=0.8,
                ))
    return out


def detect_pvalue_clustering(tex: str, lo: float = 0.045, hi: float = 0.05, min_count: int = 3) -> list[dict[str, Any]]:
    """Many reported p-values sitting in [lo, hi) is a classic p-hacking / fabrication signature."""
    body = body_text(tex)
    ps = [float(x) for x in re.findall(r"p\s*[=<]\s*(\d*\.\d+)", body)]
    just_under = [p for p in ps if lo <= p < hi]
    out: list[dict[str, Any]] = []
    if len(just_under) >= min_count:
        out.append(objection(
            "pvalue_clustering_below_0_05", "minor", "reported p-values",
            f"{len(just_under)} reported p-values fall in [{lo},{hi}) (just under 0.05): "
            f"{just_under} — a clustering pattern associated with selective reporting.",
            "report exact p-values and pre-registration where possible",
            numbers=[f"{p:g}" for p in just_under], confidence=0.4,
        ))
    return out


def detect_t_p_mismatch(tex: str, tol: float = 1.0) -> list[dict[str, Any]]:
    """'t = .., p = ..' with p far below what any t distribution allows.

    For every df, the two-sided t p-value is at least the normal one, so a reported p more than
    `tol` log10 units below the normal p is impossible whatever the degrees of freedom."""
    body = body_text(tex)
    out: list[dict[str, Any]] = []
    pat = re.compile(r"\bt(?:\s*\(\s*\d+(?:\.\d+)?\s*\))?\s*=\s*(-?\d+\.?\d*)\s*[,;]?\s*\$?\s*,?\s*\$?p\s*[=<]\s*(\d*\.\d+)")
    for m in pat.finditer(body):
        t, p_reported = float(m.group(1)), float(m.group(2))
        p_floor = p_two_sided_from_z(t)
        if 0 < p_reported and p_floor > 0 and math.log10(p_floor) - math.log10(p_reported) > tol:
            out.append(objection(
                "pvalue_t_impossible", "major", m.group(0).strip(),
                f"Reported p={p_reported} for t={t}, but no t distribution gives a two-sided p below "
                f"{p_floor:.2g} for that statistic (the normal limit).",
                "recompute p from the test statistic and its degrees of freedom",
                numbers=[m.group(2)], confidence=0.85,
            ))
    return out


def run(tex: str) -> list[dict[str, Any]]:
    return detect_z_p_mismatch(tex) + detect_t_p_mismatch(tex) + detect_pvalue_clustering(tex)
