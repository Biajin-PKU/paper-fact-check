"""Percent changes that their own numbers do not give, and one change quoted at two values.

- A sentence with one percentage that is itself a change ("71.4% bandwidth reduction", "reduced ...
by 71.4%") next to one pair of numbers ("800 vs 2800", "from A to B"): the percentage must match the
change relative to A or to B, the ratio, or the difference in points, within the rounding printed.
- The same change phrase ("% bandwidth reduction") quoted with different percentages.

    python3 -m paperfactcheck.checks.relative_change <main.tex>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from ._common import body_text, objection

_TABULAR = re.compile(r"\\begin\{(tabular\*?|tabularx|array)\}.*?\\end\{\1\}", re.S)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\\(一-鿿])|(?<=[。！？；])")
_CHANGE = r"(?:reduc\w*|decreas\w*|lower\w*|fewer|less|sav\w*|cut(?:s|ting)?|drop\w*|improv\w*|increas\w*|higher|gain\w*|faster|speed-?up|boost\w*|better|worse(?:n\w*)?)"
_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_PCT = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")
_ZH_CHANGE = r"(?:降低|减少|下降|缩短|节省|节约|减小|提高|提升|增加|增长|上升|改善|加快|增大)"
_PAIR = re.compile(
    _NUM + r"(?:\s*[A-Za-z%/\-]+){0,4}?\s*(?:vs\.?|versus|compared (?:to|with)|against|relative to)\s*(?:the\s+)?"
    + _NUM + r"|from\s+" + _NUM + r"(?:\s*[A-Za-z%/\-]+){0,3}?\s+to\s+" + _NUM
    + r"|(?P<zha>\d[\d,]*(?:\.\d+)?)(?:\s*[A-Za-z%]+)?[^。；;\d]{0,20}?较[^。；;]{0,40}?(?<![A-Za-z0-9\-.])"
    r"(?P<zhb>\d[\d,]*(?:\.\d+)?)(?![\d.\-])"
    + r"|(?:从|由)\s*" + _NUM + r"(?:\s*[A-Za-z%/\-]+){0,3}?\s*" + r"(?:" + _ZH_CHANGE + r"|降|升|增|减)?(?:至|到)\s*" + _NUM, re.I)
_AFTER = re.compile(r"\s*(?:[a-z-]+\s+){0,2}?" + _CHANGE + r"\b", re.I)
_BEFORE = re.compile(_CHANGE + r"(?:\s+[a-z-]+){0,4}?\s+by\s+(?:about\s+|roughly\s+|approximately\s+|nearly\s+|over\s+)?$"
                     r"|" + _ZH_CHANGE + r"(?:了|约|达|近|超过)?\s*(?:约|达|近)?\s*$", re.I)
_PHRASE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%\s+((?:[a-z]+[- ]){1,2}" + _CHANGE + r")\b", re.I)
_SHARE = re.compile(r"\s*of\s+(?:the|its|their|this)\b", re.I)  # "94% of the gain" is a share, not a change
_GENERIC = {"relative", "absolute", "overall", "average", "mean", "total", "further", "additional", "net", "a", "an", "the"}


def _plain(text: str) -> str:
    text = re.sub(r"\\%", "%", text)
    text = re.sub(r"\\(?:[,;!: ]|quad|qquad)|~|\$|\{|\}", " ", text)
    text = re.sub(r"\\(?:text\w*|emph|mathrm|mathbf)\b", " ", text)
    return re.sub(r"\s+", " ", text)


def prose(tex: str) -> str:
    return _plain(_TABULAR.sub(" ", body_text(tex)))


def _readings(a: float, b: float) -> list[float]:
    out = [abs(a - b)]
    for base in (a, b):
        if base:
            out.append(abs(a - b) / base * 100)
    if a and b:
        out += [a / b * 100, b / a * 100]
    return out


def _places(number: str) -> int:
    return len(number.split(".")[1]) if "." in number else 0


def detect_relative_change(tex: str) -> list[dict[str, Any]]:
    out = []
    for sentence in _SENTENCE.split(prose(tex)):
        # Only a percentage that is itself the change: "71.4% bandwidth reduction", "reduced ... by 71.4%".
        pcts = [m for m in _PCT.finditer(sentence)
                if (_AFTER.match(sentence, m.end()) or _BEFORE.search(sentence[max(0, m.start() - 60): m.start()]))
                and not _SHARE.match(sentence, m.end())]
        pairs = list(_PAIR.finditer(sentence))
        if len(pcts) != 1 or len(pairs) != 1:
            continue
        # The percentage and the pair must belong to one clause, not two halves of a long sentence.
        gap = max(pcts[0].start() - pairs[0].end(), pairs[0].start() - pcts[0].end())
        between = sentence[min(pcts[0].end(), pairs[0].end()): max(pcts[0].start(), pairs[0].start())]
        if gap > 60 or re.search(r"\b(?:and|while|yet|but|whereas|although)\b|;|，|和|而|但", between):
            continue  # "cuts cost by 2% and the rate from A to B": the percentage belongs to another clause
        groups = [g for g in pairs[0].groups() if g]
        a_txt, b_txt = groups[0].replace(",", ""), groups[1].replace(",", "")
        a, b = float(a_txt), float(b_txt)
        if a == b or not (a and b):
            continue
        claimed_txt = pcts[0].group(1)
        claimed = float(claimed_txt)
        if claimed in (a, b):  # the percentage is one of the pair, not a change between them
            continue
        # The pair's own rounding moves the percentage; allow for it plus the claim's last place.
        slack = 0.5 * 10 ** -_places(claimed_txt) + claimed * (
            0.5 * 10 ** -_places(a_txt) / a + 0.5 * 10 ** -_places(b_txt) / b) + 1e-9
        # "A 较 B 提高了 x%": the comparator after 较 is the base
        readings = [abs(a - b) / b * 100, abs(a - b)] if pairs[0].group("zha") else _readings(a, b)
        if min(abs(claimed - r) for r in readings) <= slack:
            continue
        if pairs[0].group("zha"):
            why = (f"The sentence gives a {claimed_txt}% change of {a_txt} over {b_txt}, but relative to {b_txt} "
                   f"those numbers give {abs(a - b) / b * 100:.1f}%.")
        else:
            why = None
        out.append(objection(
            "relative_change_mismatch", "major", sentence.strip()[:120],
            why or f"The sentence gives a {claimed_txt}% change for {a_txt} against {b_txt}, but those numbers give "
            f"{abs(a - b) / b * 100:.1f}% relative to {b_txt} or {abs(a - b) / a * 100:.1f}% relative to {a_txt}, "
            f"and no usual reading gives {claimed_txt}%.",
            f"Recompute the percentage from {a_txt} and {b_txt} and correct it wherever it is quoted.",
            numbers=[claimed_txt, a_txt, b_txt], confidence=0.8))
    return out


def detect_phrase_disagreement(tex: str) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, str]] = {}
    for sentence in _SENTENCE.split(prose(tex)):
        for m in _PHRASE.finditer(sentence):
            words = m.group(2).lower().replace("-", " ").split()
            if words[0] in _GENERIC:
                continue
            seen.setdefault(" ".join(words), {}).setdefault(m.group(1), sentence.strip())
    out = []
    for phrase, values in seen.items():
        if len(values) >= 2:
            vals = sorted(values, key=float)
            out.append(objection(
                "same_change_different_values", "major", phrase,
                f"The text gives the same change, '{phrase}', as {' and as '.join(v + '%' for v in vals)}. "
                + " | ".join(f"\"{values[v][:140]}\"" for v in vals),
                "Report one value for this change everywhere, or name what differs between the two.",
                numbers=vals, confidence=0.75))
    return out


def run(tex: str) -> list[dict[str, Any]]:
    return detect_relative_change(tex) + detect_phrase_disagreement(tex)


def demo() -> None:
    bad = r"""\begin{document}
Our method dominates all baselines, achieving 41.4\% bandwidth reduction (800 vs 2800 bits).
The policy needs 800 bits per message compared to 2800 bits, a 71.4\% bandwidth reduction.
Accuracy rose from 0.168 to 0.187, a 10.8\% improvement over the baseline.
\end{document}"""
    hits = run(bad)
    cats = sorted(h["category"] for h in hits)
    assert cats == ["relative_change_mismatch", "relative_change_mismatch", "same_change_different_values"], hits
    good = r"""\begin{document}
It needs 800 bits per message compared to 2800 bits, a 71.4\% bandwidth reduction.
Accuracy rose from 0.168 to 0.187, an 11.3\% improvement.
Recall went from 80\% to 90\%, a 10\% improvement in absolute terms.
Latency fell by 25\% (40 ms vs 30 ms).
\end{document}"""
    assert run(good) == [], run(good)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        from .number_agreement import read_tree
        for hit in run(read_tree(Path(sys.argv[1]))):
            print(hit["category"], "|", hit["reasoning"][:200])
    else:
        demo()
        print("ok")
