"""Digit distributions of the numbers in result tables. Corroborating evidence only.

Hand-typed tables tend to have terminal digits that are too even, or leading digits far from
Benford's law. Many honest tables are small or bounded, so this is minor and fires only on a clear
deviation with enough samples.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from ._common import harvest_result_decimals, objection

# Benford expected leading-digit frequencies.
_BENFORD = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def _chi_square(observed: dict[int, int], expected_freq: dict[int, float], n: int) -> float:
    chi = 0.0
    for d, ef in expected_freq.items():
        e = ef * n
        o = observed.get(d, 0)
        if e > 0:
            chi += (o - e) ** 2 / e
    return chi


def terminal_digit_uniformity(numbers: list[str]) -> tuple[float, int]:
    """Chi-square of last-digit counts vs uniform(0-9). Returns (chi2, n)."""
    digits = [int(s[-1]) for s in numbers if s[-1].isdigit()]
    n = len(digits)
    if n == 0:
        return 0.0, 0
    obs = Counter(digits)
    return _chi_square(obs, {d: 0.1 for d in range(10)}, n), n


def leading_digit_benford(numbers: list[str]) -> tuple[float, int]:
    lead = []
    for s in numbers:
        for ch in s:
            if ch in "123456789":
                lead.append(int(ch))
                break
    n = len(lead)
    if n == 0:
        return 0.0, 0
    return _chi_square(Counter(lead), _BENFORD, n), n


def detect_digit_anomaly(tex: str, min_n: int = 20) -> list[dict[str, Any]]:
    nums = harvest_result_decimals(tex)
    out: list[dict[str, Any]] = []
    chi_term, n_term = terminal_digit_uniformity(nums)
    # df=9 uniform, 0.001 critical ~ 27.9
    if n_term >= min_n and chi_term > 27.9:
        out.append(objection(
            "terminal_digit_nonuniform", "minor", "result-table terminal digits",
            f"Terminal-digit distribution over {n_term} result numbers deviates strongly from "
            f"uniform (chi2={chi_term:.1f}, df=9).",
            "verify numbers come from measurement, not authoring",
            confidence=0.35,
        ))
    return out


def run(tex: str) -> list[dict[str, Any]]:
    return detect_digit_anomaly(tex)
