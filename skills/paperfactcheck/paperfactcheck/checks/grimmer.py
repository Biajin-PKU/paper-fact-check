"""Means, standard deviations and percentages that their own counts cannot produce.

- GRIMMER (Anaya, 2016): for N integer responses the sum and the sum of squares are integers of
  the same parity; a mean and SD that no such pair gives cannot come from N integer responses.
- "45/192 (23.4%)": the percentage must equal the count over the stated denominator.
- Three or more "k (p%)" pairs in one sentence sharing a denominator, except one.
"""
from __future__ import annotations

import math
import re
from typing import Any

from ._common import body_text, objection

_INTEGER_SCALE = re.compile(
    r"\b(likert|scale|rating|rated|rate[sd]?|score[sd]?|scoring|items?|points?|questionnaire|survey|"
    r"responses?|respondents?|participants?|count[sd]?|integer)\b|量表|评分|得分|条目|问卷|计数", re.I)
_SENTENCE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z(\[\u4e00-\u9fff])|(?<=[。！？；])")


def _clean(text: str) -> str:
    s = re.sub(r"\\pm|±", " ± ", text)
    s = re.sub(r"\\%|％", "%", s)
    s = re.sub(r"\\[,;!: ]|[${}~]", " ", s)
    return re.sub(r"\s+", " ", s)


def _places(token: str) -> int:
    return len(token.split(".")[1]) if "." in token else 0


def grimmer_consistent(mean_txt: str, sd_txt: str, n: int) -> bool:
    """True if some integer sum S and sum of squares Q (same parity) give the mean and SD as printed."""
    if n < 2:
        return True
    m, s = float(mean_txt), float(sd_txt)
    hm, hs = 0.5 * 10 ** -_places(mean_txt), 0.5 * 10 ** -_places(sd_txt)
    for total in range(math.ceil((m - hm) * n - 1e-9), math.floor((m + hm) * n + 1e-9) + 1):
        base = total * total / n
        q_lo = (n - 1) * max(s - hs, 0.0) ** 2 + base
        q_hi = (n - 1) * (s + hs) ** 2 + base
        q = math.ceil(q_lo - 1e-9)
        if q % 2 != total % 2:
            q += 1
        if q <= q_hi + 1e-9:
            return True
    return False


_SEEDS = re.compile(r"\b(?:seeds?|runs?|folds?|trials?|epochs?|repetitions?|bootstrap\w*|rates?|shares?|proportions?|"
                    r"probabilit\w*|fractions?)\b|RMSE|MAE|AUROC|AUPRC|AUC|accuracy", re.I)


def _grim_ok(mean_txt: str, n: int) -> bool:
    m, h = float(mean_txt), 0.5 * 10 ** -_places(mean_txt)
    return math.floor((m + h) * n + 1e-9) >= math.ceil((m - h) * n - 1e-9)


_MEAN_SD = re.compile(
    r"(?:\b(?:mean|average|M)\b|均值|平均(?:值|分)?)\s*(?:=|:|was|of|为)?\s*(\d+\.\d+)\s*"
    r"(?:\(|,|;|，)?\s*(?:\bSD\b|s\.d\.|standard deviation|标准差)\s*(?:=|:|of|为)?\s*(\d+\.\d+)"
    r"|(\d+\.\d+)\s*±\s*(\d+\.\d+)", re.I)
_SIZE = re.compile(r"\b[nN]\s*=\s*(\d+)\b|(\d+)\s*(?:participants|respondents|subjects|students|patients|名|例|人)")


def detect_grimmer(text: str) -> list[dict[str, Any]]:
    out = []
    for sentence in _SENTENCE.split(_clean(body_text(text))):
        sizes = {int(a or b) for a, b in _SIZE.findall(sentence)}
        if len(sizes) != 1 or not _INTEGER_SCALE.search(sentence):
            continue
        n = sizes.pop()
        if not 2 <= n <= 100:
            continue
        for m in _MEAN_SD.finditer(sentence):
            mean_txt, sd_txt = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            if _places(mean_txt) != 2 or float(sd_txt) == 0 or float(mean_txt) < 1:
                continue  # one decimal leaves GRIMMER little to test; three or more is not integer data
            if not _grim_ok(mean_txt, n):
                continue  # the mean itself cannot come from integers: this is not integer data
            if _SEEDS.search(sentence):
                continue
            if not grimmer_consistent(mean_txt, sd_txt, n):
                out.append(objection(
                    "grimmer_infeasible_sd", "major", m.group(0).strip()[:100],
                    f"With N = {n} integer responses, no set of responses gives mean {mean_txt} together with "
                    f"SD {sd_txt}: the sum and the sum of squares would have to be integers of the same parity, "
                    "and none fall inside the printed rounding (GRIMMER test).",
                    "Recompute the mean and SD from the raw responses, or correct N.",
                    numbers=[mean_txt, sd_txt], confidence=0.8))
    return out


_FRACTION = re.compile(r"(?<![\d.])(\d+)\s*(?:/|of|out of|in)\s*(\d+)\s*(?:[a-z]+\s*){0,2}\(\s*(\d+(?:\.\d+)?)\s*%\s*\)", re.I)
_ZH_FRACTION = re.compile(r"(\d+)\s*例中\s*(?:有)?\s*(\d+)\s*例\s*\(\s*(\d+(?:\.\d+)?)\s*%\s*\)")
_PAIR = re.compile(r"(?<![\d./])(\d+)\s*(?:[a-z]+\s*)?\(\s*(\d+(?:\.\d+)?)\s*%\s*\)", re.I)


def _pct_ok(k: int, n: int, p_txt: str) -> bool:
    h = 0.5 * 10 ** -_places(p_txt) + 1e-9
    return abs(k / n * 100 - float(p_txt)) <= h


def detect_percent_counts(text: str) -> list[dict[str, Any]]:
    out = []
    for sentence in _SENTENCE.split(_clean(body_text(text))):
        triples = [(int(a), int(b), p, m.group(0)) for m in _FRACTION.finditer(sentence) for a, b, p in [m.groups()]]
        triples += [(int(b), int(a), p, m.group(0)) for m in _ZH_FRACTION.finditer(sentence) for a, b, p in [m.groups()]]
        for k, n, p_txt, raw in triples:
            if 0 < n and k <= n and not _pct_ok(k, n, p_txt):
                out.append(objection(
                    "percent_count_mismatch", "major", raw.strip()[:100],
                    f"{k} of {n} is {k / n * 100:.{max(_places(p_txt), 1)}f}%, not {p_txt}%.",
                    f"Correct the percentage to {k / n * 100:.{max(_places(p_txt), 1)}f}%, or the count or "
                    "denominator if one of those is the typo.",
                    numbers=[p_txt, str(k), str(n)], confidence=0.85))
        if triples:
            continue
        pairs = [(int(k), p) for k, p in _PAIR.findall(sentence) if 0 < float(p) < 100 and int(k) > 0]
        if len(pairs) < 3:
            continue
        ranges = []
        for k, p_txt in pairs:
            h = 0.5 * 10 ** -_places(p_txt)
            lo = math.ceil(k * 100 / (float(p_txt) + h) - 1e-9)
            hi = math.floor(k * 100 / max(float(p_txt) - h, 1e-9) + 1e-9)
            ranges.append(set(range(lo, hi + 1)) if hi - lo < 5000 else None)
        if any(r is None for r in ranges):
            continue
        common = set.intersection(*ranges)
        if common:
            continue
        for i, (k, p_txt) in enumerate(pairs):
            rest = set.intersection(*(r for j, r in enumerate(ranges) if j != i))
            if rest and not ranges[i] & rest:
                n = min(rest)
                out.append(objection(
                    "percent_denominator_outlier", "minor", f"{k} ({p_txt}%)",
                    f"The other counts in this sentence are percentages of {n}"
                    + (f" (or {max(rest)})" if len(rest) > 1 else "")
                    + f"; {k} of {n} is {k / n * 100:.{max(_places(p_txt), 1)}f}%, not {p_txt}%. "
                    f"Sentence: \"{sentence.strip()[:160]}\"",
                    "Check this count and its percentage against the table it comes from; if its denominator "
                    "differs from the others, say so.",
                    numbers=[p_txt, str(k)], confidence=0.6))
                break
    return out


def run(text: str) -> list[dict[str, Any]]:
    return detect_grimmer(text) + detect_percent_counts(text)


def demo() -> None:
    assert detect_grimmer("Across 3 seeds the RMSE was 0.98 ± 0.01 on the rating data (N = 3).") == []
    assert grimmer_consistent("3.50", "1.24", 20) and not grimmer_consistent("3.50", "1.21", 20)
    # mean 5.00 over N=4 forces S = 20; SD 1.00 then needs Q = 23, odd while S is even.
    assert not grimmer_consistent("5.00", "1.00", 4)
    bad = ("Participants (N = 4) rated the tool on a 7-point Likert scale (M = 5.00, SD = 1.00). "
           "Of the patients, 45/192 (25.4%) relapsed. "
           "Complications were infection in 24 (12.5%), bleeding in 30 (15.6%) and leak in 19 (12.0%) patients. "
           "共纳入 192 例，192例中有45例(25.4%)复发。")
    good = ("Participants (N = 20) rated the tool on a 7-point Likert scale (M = 3.50, SD = 1.24). "
            "Of the patients, 45/192 (23.4%) relapsed. "
            "Complications were infection in 24 (12.5%), bleeding in 30 (15.6%) and leak in 19 (9.9%) patients. "
            "192例中有45例(23.4%)复发。")
    bad, good = bad.replace("%", r"\%"), good.replace("%", r"\%")  # LaTeX-escaped, as the readers deliver it
    cats = sorted(f["category"] for f in run(bad))
    assert cats == ["grimmer_infeasible_sd", "percent_count_mismatch", "percent_count_mismatch",
                    "percent_denominator_outlier"], cats
    assert run(good) == [], run(good)


if __name__ == "__main__":
    demo()
    print("ok")
