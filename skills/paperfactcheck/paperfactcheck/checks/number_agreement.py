#!/usr/bin/env python3
"""Numbers in the text that drift from the table row the sentence names.

A sentence names a table row (a method, a cohort, a condition) and quotes a decimal; the row holds
a value a few units away in the last place. Tables get regenerated and the prose written against
the old numbers stays behind.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from ._common import body_text, objection, strip_comments, strip_typography

_TABULAR = re.compile(r"\\begin\{(?:tabular\*?|tabularx|longtable)\}.*?\\end\{(?:tabular\*?|tabularx|longtable)\}", re.S)
_FLOAT = re.compile(r"\\begin\{(table\*?|figure\*?)\}.*?\\end\{\1\}", re.S)
_DECIMAL = re.compile(r"(?<![A-Za-z0-9_.])-?\d+\.\d+(?![A-Za-z0-9_.])")
_CMD_ARG = re.compile(r"\\(?:textbf|textit|emph|mathrm|mathbf|text|underline|textsc|mbox)\{([^{}]*)\}")
_CMD = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\\(一-鿿])|(?<=[。！？；])")
_INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")
_NEAR = 0.10
_CONTRAST = re.compile(r"\b(?:versus|vs\.?|compared (?:to|with)|relative to|whereas|while)\b|"
                       r"\bfrom\b[^.;]{0,40}?\bto\b|\b(?:ris\w*|rose|fell|falls?|drop\w*|climb\w*|grow\w*|grew)\s+to\b", re.I)
_DECIMAL_ANY = re.compile(r"(?<![A-Za-z0-9_.])\d+\.\d+(?![A-Za-z0-9_.])")
_PM = re.compile(r"\\pm\s*\{?\s*-?\d*\.?\d+\}?|±\s*-?\d*\.?\d+")
_LAST_PLACE_UNITS = 9
_FIG_REF = re.compile(r"\\[A-Za-z]*ref\{(?:fig|sfig)[:\-]|\bFig(?:ure|\.)", re.I)
_TAB_REF = re.compile(r"\\[A-Za-z]*ref\{(?:tab|stab)[:\-]|\bTable", re.I)
# Sentences about a subset of the data legitimately carry values that differ slightly from the
# full-sample row. ponytail: keyword list, replace with a parsed scope if it misses real cases.
_SUBSET = re.compile(r"subgroup|stratum|strata|range|seed|fold|split|sensitivity|ablat|without|"
                     r"excluding|only|per-|subset|bootstrap|declin|dropout|delay|noise|perturb|corrupt|\\pm|interval|\bCI\b", re.I)


def _label(cell: str) -> str:
    text = _CMD_ARG.sub(r"\1", cell)
    text = _CMD.sub(" ", text)
    text = re.sub(r"[^a-z0-9+\-一-鿿]+", " ", text.casefold())
    return " ".join(text.split())


def _decimals(text: str) -> list[str]:
    return _DECIMAL.findall(strip_typography(text))


def table_rows(tex: str) -> dict[str, list[float]]:
    """Row label -> numeric cells, over every tabular. Labels shorter than 3 chars are dropped."""
    rows: dict[str, list[float]] = {}
    for block in _TABULAR.findall(strip_comments(tex)):
        for raw in re.split(r"\\\\", block):
            cells = raw.split("&")
            if len(cells) < 2:
                continue
            first = re.sub(r"\\(?:hline|toprule|midrule|bottomrule|cmidrule\S*|begin\{tabular\*?\}\{[^}]*\})", " ", cells[0])
            label = _label(first)
            values = [float(n) for cell in cells[1:] for n in _decimals(_PM.sub(" ", cell))]
            if len(label) >= 3 and values and not re.fullmatch(r"[\d .+\-]+", label):
                rows.setdefault(label, []).extend(values)
    return rows


def _matches(value: float, places: int, cells: list[float]) -> bool:
    for cell in cells:
        for scaled in (cell, cell * 100, cell / 100):
            if round(scaled, places) == round(value, places):
                return True
            # the text may carry more digits than the table: 0.9538 in prose, 0.954 in the cell
            cell_places = len(repr(scaled).split(".")[1]) if "." in repr(scaled) else 0
            if cell_places < places and round(value, cell_places) == round(scaled, cell_places):
                return True
    return False


def captions(block: str) -> list[str]:
    """Brace-balanced \\caption{...} arguments of one float."""
    out = []
    for match in re.finditer(r"\\caption(?:\[[^\]]*\])?\{", block):
        depth, i = 1, match.end()
        while i < len(block) and depth:
            depth += {"{": 1, "}": -1}.get(block[i], 0)
            i += 1
        out.append(block[match.end(): i - 1])
    return out


def _prose(tex: str) -> str:
    """Body prose plus float captions: a caption quoting its own table drifts like prose does."""
    body = body_text(tex)
    end = re.search(r"\\begin\{thebibliography\}|\\bibliography\{|\\printbibliography", body)
    body = _FLOAT.sub(lambda m: " " + ". ".join(captions(m.group(0))) + ". ", body[: end.start()] if end else body)
    return _TABULAR.sub(" ", body)


def run(tex: str) -> list[dict[str, Any]]:
    rows = table_rows(tex)
    if not rows:
        return []
    every_cell = [v for cells in rows.values() for v in cells]
    # Any table row anywhere (appendix, longtable, \input files, environments the parser skips):
    # a number printed verbatim on a line with '&' is a table value, whichever row the sentence names.
    in_any_table = {d for line in strip_comments(tex).splitlines() if "&" in line for d in _DECIMAL_ANY.findall(line)}
    labels = sorted(rows, key=len, reverse=True)
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for sentence in _SENTENCE.split(_prose(tex)):
        plain = f" {_label(sentence)} "
        named: list[str] = []
        for label in labels:
            hit = label in plain if re.search(r"[一-鿿]", label) else f" {label} " in plain
            if hit and not any(label in longer for longer in named):
                named.append(label)
        # A sentence that cites a figure and no table quotes the figure's values, not the row's.
        if not named or _SUBSET.search(sentence) or (_FIG_REF.search(sentence) and not _TAB_REF.search(sentence)):
            continue
        low = sentence.casefold()
        spots = sorted((low.find(lab), lab) for lab in named if low.find(lab) >= 0)
        decimals = _decimals(sentence)
        if len(named) > 1 and len(decimals) > 1:
            continue  # several rows and several numbers: which number belongs to which row is guesswork
        for number in decimals:
            if re.search(r"(?:about|approximately|roughly|around|nearly|near|~|≈|\\approx|\\sim)\s*\$?\s*"
                         + re.escape(number) + r"(?!\d)", sentence, re.I):
                continue  # an approximate value is not a copy of a cell
            # With several rows named, a number belongs to the row named just before it.
            if len(named) == 1:
                label, close = named[0], True
            else:
                at = sentence.find(number)
                before = [(p, lab) for p, lab in spots if p < at]
                if not before:
                    continue
                label, close = before[-1][1], at - before[-1][0] - len(before[-1][1]) <= 30
            cells = rows[label]
            value = float(number)
            places = len(number.split(".")[1])
            if _matches(value, places, every_cell) or number.lstrip("-") in in_any_table:
                continue
            if re.search(r"[A-Za-z\\}]\s*=\s*\$?\s*" + re.escape(number) + r"(?![\d])", sentence):
                continue  # a setting (delta = 0.75, n = 100), not a result
            # A stale or hand-edited copy differs in its last digits; a value tens of units away in
            # the last place belongs to another condition the sentence walks through.
            near = [c for c in cells if c and abs(c - value) / abs(c) <= _NEAR
                    and abs(c - value) <= _LAST_PLACE_UNITS * 10 ** -places + 1e-12]
            if not near or (label, number) in seen:
                continue
            seen.add((label, number))
            # A contrast ("A versus B") often puts a second entity's or a figure's number beside the
            # row's: still worth a look, not a major claim.
            contrast = bool(_CONTRAST.search(sentence)) or not close
            out.append(objection(
                "prose_table_number_disagreement", "minor" if contrast else "major", f"prose:{label}",
                f"The text gives {number} for '{label}', but no cell of its table row matches "
                f"at that precision; the nearest row value is {near[0]}. Sentence: "
                f"\"{' '.join(sentence.split())[:240]}\"",
                "Make the prose and the table report the same value, or name the derivation.",
                numbers=[number, str(near[0])], confidence=0.4 if contrast else 0.7,
            ))
    return out


def read_tree(main: Path, depth: int = 0) -> str:
    text = main.read_text(encoding="utf-8", errors="replace")
    if depth > 10:
        return text

    def expand(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        for base in (main.parent, main.parent.parent):
            path = base / (name if name.endswith(".tex") else f"{name}.tex")
            if path.is_file():
                return read_tree(path, depth + 1)
        return match.group(0)

    return _INPUT.sub(expand, text)


def demo() -> None:
    tex = r"""\begin{document}
Ours reaches an AUC of 0.913 on the test set. The baseline LogReg reaches 0.871.
Ours improves on LogReg by 0.042.
\begin{table}\begin{tabular}{lc}
Method & AUC \\ \midrule
Ours & 0.917 \\
LogReg & 0.871 \\
\end{tabular}\end{table}
\end{document}"""
    hits = run(tex)
    assert [h["numbers"] for h in hits] == [["0.913", "0.917"]], hits
    assert run(tex.replace("0.913", "0.917")) == []
    in_caption = tex.replace("0.913", "0.917").replace(
        r"\begin{tabular}", r"\caption{Ours reaches \textbf{0.915} AUC.}\begin{tabular}")
    assert [h["numbers"] for h in run(in_caption)] == [["0.915", "0.917"]], run(in_caption)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        demo()
        print("demo ok")
    else:
        for hit in run(read_tree(Path(sys.argv[1]))):
            print(hit["reasoning"])
