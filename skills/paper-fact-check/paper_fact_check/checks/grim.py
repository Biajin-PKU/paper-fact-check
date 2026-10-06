"""GRIM: is a reported mean possible for its sample size?

A mean of N integer-valued responses, reported to d decimals, must equal round(k/N, d) for some
integer k. If no k reproduces it, that mean cannot come from N integer responses (Brown & Heathers,
2017). Strong for Likert items, counts, and human ratings.
"""

from __future__ import annotations

import re
from typing import Any

from ._common import body_text, objection


def grim_consistent(mean: float, n: int, decimals: int) -> bool:
    """True if `mean` is achievable as (sum of n integers)/n at the given decimal precision."""
    if n <= 0:
        return True
    scale = 10 ** decimals
    target = round(mean * scale)
    # some integer total k has round(k/n * scale) == target ?
    for k in range(0, n * 1000 + 1):  # cap to keep it bounded; means<... items scale small
        if round((k / n) * scale) == target:
            return True
        if k / n > mean + 1:  # past the plausible region
            break
    return False


_INTEGER_SCALE = re.compile(
    r"\b(likert|scale|rating|rated|rate[sd]?|score[sd]?|scoring|items?|points?|questionnaire|survey|"
    r"responses?|respondents?|participants?|count[sd]?|integer)\b", re.I)


def detect_grim(tex: str) -> list[dict[str, Any]]:
    """Scan for 'mean/average X ... N=<n>' with N small enough that GRIM has teeth (n<=100)."""
    body = body_text(tex)
    out: list[dict[str, Any]] = []
    # Allow natural phrasing between the cue and the value ("mean rating was 4.50", "M = 4.50").
    pat = re.compile(
        r"(?:mean|average|\bM)\b[^.\n]{0,25}?(\d+\.(\d+))\b[^.\n]{0,80}?\b[nN]\s*=\s*(\d+)",
    )
    # The same pair with N first ("the N=18 participants gave a mean rating of 5.19").
    rev = re.compile(
        r"\b[nN]\s*=\s*(\d+)\b[^.\n]{0,80}?(?:mean|average|\bM)\b[^.\n]{0,25}?(\d+\.(\d+))\b",
    )
    pairs = [(m, m.group(1), m.group(2), m.group(3)) for m in pat.finditer(body)]
    pairs += [(m, m.group(2), m.group(3), m.group(1)) for m in rev.finditer(body)]
    for m, value, places, size in pairs:
        # GRIM assumes integer-valued responses; a mean of a continuous measure has no grain to test.
        if not _INTEGER_SCALE.search(body[max(0, m.start() - 200): m.end() + 120]):
            continue
        mean = float(value)
        decimals = len(places)
        n = int(size)
        if 1 < n <= 100 and not grim_consistent(mean, n, decimals):
            out.append(objection(
                "grim_infeasible_mean", "major", m.group(0).strip()[:80],
                f"Mean {mean} to {decimals} dp is not achievable from any integer total over N={n} "
                f"items (GRIM test) — the reported mean is arithmetically impossible for that N.",
                "recompute the mean from the raw item sum, or correct N",
                numbers=[value], confidence=0.85,
            ))
    return out


def run(tex: str) -> list[dict[str, Any]]:
    return detect_grim(tex)
