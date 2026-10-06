"""Directional claims that their own interval does not support, and floats nobody cites.

- A sentence says one arm is better, higher, or significant, while the confidence interval it
  prints includes zero, or its p-value is above 0.05.
- A table or figure that the text never references.
"""

from __future__ import annotations

import re
from typing import Any

from ._common import body_text, objection

_FLOATS = re.compile(r"\\begin\{(table|figure)\*?\}.*?\\end\{\1\*?\}", re.S)
_TABLES = re.compile(r"\\begin\{(tabular\*?|tabularx|longtable|array)\}.*?\\end\{\1\}", re.S)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\\一-鿿])|(?<=[;:])\s+|(?<=[。！？；])")
_DIRECTION = re.compile(
    r"\b(outperform\w*|significant(?:ly)?|superior|exceed\w*|better|higher|lower|improv\w*|"
    r"reduc\w*|increas\w*|decreas\w*|gain\w*|advantage)\b"
    r"|显著|优于|高于|低于|提高|降低|改善|增加|减少|下降|上升", re.I)
_CONCEDES = re.compile(
    r"\b(no|not|non-?significant\w*|n\.s\.|comparable|similar\w*|indistinguishable|equivalen\w*|"
    r"overlap\w*|inconclusive|cannot|neither|nor|never|fail\w*|whereas|although|but|threshold)\b"
    r"|\b(?:includ|cross|span|contain|overlap)\w*\s+(?:zero|0|one|1|the null)\b"
    r"|无统计学意义|无显著|不显著|未见|无差异|差异无|相当|相似|但|然而|虽然|尽管|未达|不能|无法", re.I)
_NUM = r"(-?\d*\.?\d+)"
_INTERVAL = re.compile(
    r"(?:\bCI\b|confidence interval|credible interval|置信区间)[^0-9\-]{0,25}?" + _NUM + r"\s*(?:,|to|--|–|—|~|～|至)\s*" + _NUM,
    re.I)
_P = re.compile(r"\b[pP]\s*(=|>)\s*" + _NUM)


_ALPHA = re.compile(r"(\d+(?:\.\d+)?)\s*\\?%\s*(?:significance\s+)?level|(?:alpha|α)\s*=\s*(0?\.\d+)", re.I)


def _stated_alpha(sentence: str) -> float:
    """The largest significance level the sentence names for itself ("at the 5% level ... and at the
    10% level"), else 0.05."""
    levels = [float(a) / 100 if a else float(b) for a, b in _ALPHA.findall(sentence)]
    return max(levels, default=0.05)


def _plain(sentence: str) -> str:
    s = re.sub(r"\\(?:textminus|minus)\b|−|\$-\$", "-", sentence)
    s = re.sub(r"(?<=\d)\s*~\s*(?=-?\d)", " to ", s)
    s = re.sub(r"\\[,;!: ]|\{,\}|[${}~]", " ", s)
    s = re.sub(r"(?<![\w.])-\s+(?=\d)", "-", s)
    return re.sub(r"\s+", " ", s)


def detect_directional_claim_against_interval(tex: str) -> list[dict[str, Any]]:
    prose = _TABLES.sub(" ", _FLOATS.sub(" ", body_text(tex)))
    prose = prose.split("\\begin{thebibliography}")[0].split("\\bibliography{")[0]
    out: list[dict[str, Any]] = []
    for raw in _SENTENCE.split(prose):
        s = _plain(raw)
        # "reduces to", "reduces when" next to symbols is algebra, not an effect.
        # "reduces to", "reduces when" is algebra, and "increases the strength to 30.5" states a value:
        # neither is a comparative claim about the estimate the interval belongs to.
        s_claim = re.sub(r"\breduc\w*\s+(?:to|when)\b", " ", s)
        s_claim = re.sub(r"\b(?:increas|decreas|reduc|improv|rais|lower|boost)\w*\s+(?:[\w\-]+\s+){0,5}?to\s+"
                         r"(?:\S+\s*){0,2}?=?\s*-?\d", " ", s_claim)
        if not _DIRECTION.search(s_claim) or _CONCEDES.search(s):
            continue
        spans = [(m.group(1), m.group(2)) for m in _INTERVAL.finditer(s)
                 if float(m.group(1)) < 0 < float(m.group(2))]
        alpha = _stated_alpha(s)
        loose = [m.group(2) for m in _P.finditer(s)
                 if (m.group(1) == "=" and alpha < float(m.group(2)) < 1) or (m.group(1) == ">" and float(m.group(2)) >= alpha)]
        if not spans and not loose:
            continue
        why = "; ".join([f"95% CI {lo} to {hi} includes 0" for lo, hi in spans] + [f"P = {p}" for p in loose])
        out.append(objection(
            "directional_claim_against_interval", "major", s.strip()[:120],
            f"The sentence asserts a direction ('{_DIRECTION.search(s_claim).group(0)}') but its own evidence "
            f"does not exclude no effect: {why}. Either the comparative word predates the current "
            f"numbers or the claim overreaches the test.",
            "reword to what the interval supports (no detectable difference / direction not established), "
            "or report the test that does exclude zero",
            numbers=[n for pair in spans for n in pair] + loose, confidence=0.7))
    return out


_LABEL = re.compile(r"\\label\{((?:tab|fig|sfig|stab|supp)[:\-][^}]+)\}")
# Any \...ref{} macro counts: papers define \figref, \tabref and the like.
_REF = re.compile(r"\\[A-Za-z]*ref\*?(?:\{([^}]+)\}|\[([^\]]+)\])")


def uncited_labels(tex: str) -> list[str]:
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    refs = {key.strip() for pair in _REF.findall(tex) for key in ",".join(pair).split(",")}
    return sorted(set(_LABEL.findall(tex)) - refs)


def detect_uncited_float(tex: str) -> list[dict[str, Any]]:
    return [objection(
        "uncited_float", "minor", label,
        f"\\label{{{label}}} is never referenced in the text; a reader has no route to it and a "
        f"reviewer reads it as padding or as a result the text avoids discussing.",
        "cite it where its result is discussed, or drop it", confidence=0.9)
        for label in uncited_labels(tex)]


def run(tex: str) -> list[dict[str, Any]]:
    return detect_directional_claim_against_interval(tex) + detect_uncited_float(tex)


def demo() -> None:
    doc = r"""\begin{document}
Our method improved accuracy by 1.2 points (95\% CI $-0.4$ to 2.8).
The gain over the baseline was 3.1 points (95\% CI 1.2 to 5.0).
The difference was not significant (95\% CI -0.4 to 2.8).
Agent routing outperformed the rule baseline (P = 0.21).
Agent routing outperformed the rule baseline (P = 0.002).
Ablating memory increased error by 2.1 (95\% CI -1.5 to 2.7), while reducing latency.
See Table~\ref{tab:main} and Figures~\cref{fig:a}, \figref{fig:b}.
\begin{table}\caption{x}\label{tab:main}\end{table}
\begin{figure}\label{fig:a}\end{figure}\begin{figure}\label{fig:b}\end{figure}
\begin{table}\label{stab:extra}\end{table}
\end{document}"""
    hits = detect_directional_claim_against_interval(doc)
    assert len(hits) == 3, hits
    assert "-0.4" in hits[0]["numbers"] and "0.21" in hits[1]["numbers"] and "-1.5" in hits[2]["numbers"]
    assert uncited_labels(doc) == ["stab:extra"], uncited_labels(doc)


if __name__ == "__main__":
    demo()
    print("ok")
