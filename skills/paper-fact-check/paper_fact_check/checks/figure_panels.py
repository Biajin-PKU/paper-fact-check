"""Panel references the figure does not have.

The text points at Figure~\\ref{fig:x}e while the caption of fig:x describes panels a-d: a panel
was dropped and the sentence that cited it stayed. A figure's panels are the letters its caption
marks: (a), \\textbf{a}, \\textbf{(a)}, and ranges written as (c--f). A caption marking fewer than
two panels is skipped.

    python3 -m paper_fact_check.checks.figure_panels <main.tex>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from ._common import objection, strip_comments

_FIGURE = re.compile(r"\\begin\{figure\*?\}.*?\\end\{figure\*?\}", re.S)
_LABEL = re.compile(r"\\label\{([^}]+)\}")
_MARK = re.compile(r"\(([a-h])\d*(?:\s*(?:,|--|–|-)\s*([a-h])\d*)?\)|\\textbf\{\s*\(?([a-h])\d*"
                   r"(?:\s*(?:,|--|–|-|and)\s*([a-h])\d*)?[).,:]?\s*\}")
_REF = re.compile(r"\\[A-Za-z]*ref\{([^}]+)\}\s*(?:\\,|~)?\s*\(?\s*([a-h](?:\s*(?:,|--|–|-|and)\s*[a-h])*)\)?(?![A-Za-z])")


def _caption(block: str) -> str:
    match = re.search(r"\\caption(?:\[[^\]]*\])?\{", block)
    if not match:
        return ""
    depth, i = 1, match.end()
    while i < len(block) and depth:
        depth += {"{": 1, "}": -1}.get(block[i], 0)
        i += 1
    return block[match.end(): i - 1]


def figure_panels(tex: str) -> dict[str, str]:
    """Figure label -> last panel letter its caption marks (only figures marking 2+ panels)."""
    out = {}
    for block in _FIGURE.findall(tex):
        letters = {x for mark in _MARK.findall(_caption(block)) for x in mark if x}
        if len(letters) >= 2:
            for label in _LABEL.findall(block):
                out[label] = max(letters)
    return out


def run(tex: str) -> list[dict[str, Any]]:
    tex = strip_comments(tex)
    panels = figure_panels(tex)
    out, seen = [], set()
    for match in _REF.finditer(tex):
        label = match.group(1).strip()
        last = panels.get(label)
        if last is None:
            continue
        for letter in re.findall(r"[a-h]", re.sub(r"\band\b", " ", match.group(2))):
            if letter > last and (label, letter) not in seen:
                seen.add((label, letter))
                out.append(objection(
                    "panel_reference_beyond_caption", "major", f"{label}:{letter}",
                    f"The text points to panel {letter} of {label}, but its caption marks panels "
                    f"a-{last} only. Either the panel was dropped and this sentence still cites it, "
                    f"or the caption no longer describes the figure. Context: "
                    f"\"{' '.join(tex[match.start(): match.end() + 160].split())}\"",
                    "Point the sentence at the panel that shows this result, or restore the panel "
                    "and its caption entry.", confidence=0.85))
    return out


def demo() -> None:
    tex = r"""\begin{document}
Calibration holds (Fig.~\ref{fig:cal}b), and the drift in Fig.~\ref{fig:cal}(e) is small.
Panels \ref{fig:cal}a--c agree, as does Figure~\ref{fig:one}d.
\begin{figure}\includegraphics{x}\caption{\textbf{a}, Reliability. \textbf{b}, Drift. (c--d) Gap.}\label{fig:cal}\end{figure}
\begin{figure}\includegraphics{y}\caption{Overview (a) only.}\label{fig:one}\end{figure}
\end{document}"""
    hits = run(tex)
    assert [h["target"] for h in hits] == ["fig:cal:e"], hits
    assert run(tex.replace("(e)", "(d)")) == []


if __name__ == "__main__":
    if len(sys.argv) == 1:
        demo()
        print("demo ok")
    else:
        import number_agreement  # noqa: PLC0415

        for hit in run(number_agreement.read_tree(Path(sys.argv[1]))):
            print(hit["reasoning"])
