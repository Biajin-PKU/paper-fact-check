"""Arithmetic consistency of the numbers a paper prints.

Percentages against their counts, parts against their stated totals, and products a sentence spells
out ("48 profiles x 30 segments x 7 runs"). Column widths and lengths are excluded before any
number is read.
"""

from __future__ import annotations

import re
from typing import Any

from ._common import body_text, objection, strip_typography, tabular_blocks


def detect_compute_budget(tex: str, tol: float = 0.15) -> list[dict[str, Any]]:
    """D7: recompute primary GPU-hours from tasks x seeds x per-seed-task cost.

    Recognizes the common phrasing "<H> hours per seed-task (<g> GPU-hours); <T> tasks x <S>
    seeds = <P> GPU-hours of primary training" and flags when T*S*g != P. Also catches the
    classic "<P> GPU-hours" vs "<S> seeds ... needs <P2>" contradiction when both appear.
    """
    body = body_text(tex)
    out: list[dict[str, Any]] = []

    # per-seed-task GPU-hours, e.g. "(12 GPU-hours)" right after "per seed-task"
    g = _first_float(r"per\s+seed-?task\s*\(?\s*([\d.]+)\s*GPU-?hours?", body)
    T = _first_int(r"([\d]+)\s+(?:benchmark\s+)?tasks", body)
    S = _first_int(r"([\d]+)\s+(?:random\s+)?seeds", body)
    P = _first_int(r"([\d,]+)\s*GPU-?hours?\s+of\s+primary\s+training", body)
    if g and T and S and P:
        computed = T * S * g
        if abs(computed - P) / max(P, 1) > tol:
            out.append(objection(
                "compute_budget_inconsistency", "critical",
                f"primary training budget: stated {P} GPU-hours",
                f"Stated primary training = {P} GPU-hours, but {T} tasks x {S} seeds x {g} "
                f"GPU-hours/seed-task = {computed:g} GPU-hours ({abs(computed-P)/max(P,1)*100:.0f}% off).",
                "reconcile the per-run cost, seed/task counts, and the stated total",
                numbers=[str(P), str(int(computed))], confidence=0.9,
            ))
    return out


def detect_product_vs_total(tex: str, tol: float = 0.06) -> list[dict[str, Any]]:
    """D8: a stated total contradicts an explicit product of its factors.

    Catches e.g. "10K trajectories (48 profiles x 30 segments x 7 runs)" where the product
    must be ~= the stated total. Handles K/M suffixes and '~'/'approx' softeners.
    """
    body = body_text(tex)
    out: list[dict[str, Any]] = []
    pat = re.compile(
        r"([~≈]?\s*[\d.,]+\s*[KMkm]?)\s*\w[\w-]*\s*\("
        r"\s*([\d,]+)\s*[\w-]+\s*[x×]\s*([\d,]+)\s*[\w-]+"
        r"(?:\s*[x×]\s*([\d,]+)\s*[\w-]+)?\s*\)",
    )
    for m in pat.finditer(body):
        total = _to_number(m.group(1))
        factors = [int(x.replace(",", "")) for x in m.groups()[1:] if x]
        if total is None or not factors:
            continue
        prod = 1
        for f in factors:
            prod *= f
        approx = "~" in m.group(1) or "≈" in m.group(1) or "K" in m.group(1).upper()
        rel = abs(prod - total) / max(total, 1)
        if rel > (tol if not approx else max(tol, 0.1)):
            out.append(objection(
                "product_total_mismatch", "major",
                m.group(0).strip()[:80],
                f"Stated total ~{total:g} but factors multiply to {prod} ({rel*100:.0f}% off).",
                "make the factor counts and the stated total consistent",
                numbers=[str(int(total)), str(prod)], confidence=0.8,
            ))
    return out


_PART_WORD = re.compile(r"\b(train\w*|val\w*|test\w*|dev)\b", re.I)
_PCT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*\\%")


def detect_percentage_over_100(tex: str) -> list[dict[str, Any]]:
    """D8b: a train/val/test partition whose fractions exceed 100%.

    Tight windows only: scan a short span right after a partition keyword and require escaped
    ``\\%``. Excludes CI / confidence / coverage contexts and caps the group at 4, so it no longer
    harvests unrelated percentages (repeated 95% CIs, per-task tables) across a whole LaTeX block.
    """
    body = body_text(tex)
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for m in re.finditer(r"\b(train|val|validation|test|split)\b", body, re.IGNORECASE):
        win = body[max(0, m.start() - 40): m.start() + 130]
        if re.search(r"\b(CI|confidence|bootstrap|significan|percentile|coverage|accuracy|recall|precision|"
                     r"vs|versus|perform\w*|better|worse|higher|lower|AUC|F1|score\w*)\b",
                     win, re.IGNORECASE):
            continue
        # Each share must sit next to its own partition word: "80\% train", "test (10\%)". A bare
        # percentage near the word "test" is usually a score (accuracy 87.3\% on the test set).
        # Each percentage goes to the nearest partition word within 20 characters; a word keeps the
        # first share it is given.
        words = [(w.start(), w.end(), w.group(1).casefold()[:3]) for w in _PART_WORD.finditer(win)]
        shares: dict[str, float] = {}
        for pct in _PCT.finditer(win):
            gaps = [(max(start - pct.end(), pct.start() - end, 0), word) for start, end, word in words]
            gap, word = min(gaps, default=(99, ""))
            if gap <= 20 and word not in shares:
                shares[word] = float(pct.group(1))
        parts = [p for p in shares.values() if 0 < p < 100]
        key = tuple(parts)
        if 2 <= len(parts) <= 4 and sum(parts) > 101.5 and key not in seen:
            seen.add(key)
            out.append(objection(
                "split_percentages_exceed_100", "major", win.strip()[:80],
                f"Train/val/test partition fractions sum to {sum(parts):g}% (>100%): {parts}.",
                "use a non-overlapping split whose fractions sum to 100%",
                numbers=[str(p) for p in parts], confidence=0.7,
            ))
    return out


def detect_cross_section_disagreement(
    tex: str,
    metrics: tuple[str, ...] = ("MAPE", "NRS", "CFS", "HLS"),
) -> list[dict[str, Any]]:
    """D9: the same headline metric reported with different values in different places.

    Conservative: only fires for named scalar metrics that appear with >=2 distinct values and
    no subgroup qualifier nearby. Low severity (corroborating, not standalone proof).
    """
    body = body_text(tex)
    out: list[dict[str, Any]] = []
    _subgroup = ("per-task", "per task", "typical", "extreme", "worst", "best", "observed",
                 "synthetic", "segment", "subgroup", "ablation", "upper", "lower", "range",
                 "between", "ceiling", "floor", "oracle", "naive", "from ", " to ")
    for metric in metrics:
        vals: set[str] = set()
        # require an explicit report ("=" or ":"), not a definitional mention
        for m in re.finditer(rf"{re.escape(metric)}\s*[=:]\s*([\d]+(?:\.\d+)?)", body):
            v = m.group(1)
            if float(v) in (0.0, 100.0):  # normalization endpoints, not results
                continue
            ctx = body[max(0, m.start() - 60): m.end() + 60].lower()
            if any(q in ctx for q in _subgroup):
                continue
            vals.add(v)
        if len(vals) >= 3:  # >=3 distinct unlabeled values is a real cross-section disagreement
            out.append(objection(
                "cross_section_number_disagreement", "minor", f"metric {metric}",
                f"{metric} is reported with >=3 distinct headline values {sorted(vals)} with no subgroup label.",
                "reconcile the metric to one value or label the subgroups explicitly",
                numbers=list(vals), confidence=0.4,
            ))
    return out


def run(tex: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    out += detect_compute_budget(tex)
    out += detect_product_vs_total(tex)
    out += detect_percentage_over_100(tex)
    out += detect_cross_section_disagreement(tex)
    return out


# --- small parsing helpers ---------------------------------------------------------------

def _first_int(pat: str, text: str) -> int | None:
    m = re.search(pat, text, re.IGNORECASE)
    return int(m.group(1).replace(",", "")) if m else None


def _first_float(pat: str, text: str) -> float | None:
    m = re.search(pat, text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _to_number(token: str) -> float | None:
    token = token.strip().lstrip("~≈").strip()
    mult = 1.0
    if token[-1:].upper() == "K":
        mult, token = 1_000.0, token[:-1]
    elif token[-1:].upper() == "M":
        mult, token = 1_000_000.0, token[:-1]
    try:
        return float(token.replace(",", "")) * mult
    except ValueError:
        return None
