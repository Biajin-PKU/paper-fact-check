"""Citations against the reference list.

- LaTeX: cite keys with no entry (the PDF prints [?]), hand-written entries never cited, and one
  title under two keys.
- Numbered lists in plain text: citations beyond the end of the list, and entries never cited.
"""
from __future__ import annotations

import re
from typing import Any

from ._common import objection, strip_comments

CITE_CMD = (r"\\(?:[cC]ite(?:p|t|alp|alt|author|year|yearpar|ps|ts|num)?|[pP]arencite|[tT]extcite|[aA]utocite|"
            r"[fF]ootcite|[sS]martcite|supercite|fullcite|nocite)\*?")
_CITE = re.compile(CITE_CMD + r"(?:\s*\[[^\]]*\]){0,2}\s*\{([^}]*)\}")
_BIBITEM = re.compile(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
_BIBENTRY = re.compile(r"@\s*(\w+)\s*\{\s*([^,\s]+)\s*,", re.I)
_TITLE = re.compile(r"\btitle\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n", re.I | re.S)


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\\[a-zA-Z]+|[{}]", "", t.lower())).strip()


def check_latex(tex: str, bib: str = "") -> list[dict[str, Any]]:
    tex = strip_comments(tex)
    cited: list[str] = []
    for group in _CITE.findall(tex):
        cited += [k.strip() for k in group.split(",") if k.strip() and not k.strip().startswith("#")]
    if "*" in cited:
        return []
    items = _BIBITEM.findall(tex) + _BIBITEM.findall(bib)
    entries = [(kind.lower(), key) for kind, key in _BIBENTRY.findall(bib)
               if kind.lower() not in ("string", "comment", "preamble")]
    # BibTeX matches keys without regard to case
    defined = {k.lower() for k in items} | {key.lower() for _, key in entries}
    if not defined:
        return []  # no list to check against
    out = []
    missing = [k for k in dict.fromkeys(cited) if k.lower() not in defined]
    if len(missing) > max(3, 0.3 * len(set(cited))):
        return []  # most keys unresolved: the list that was read is not the paper's whole bibliography
    for key in missing:
        out.append(objection(
            "citation_undefined", "major", key,
            f"\\cite{{{key}}} has no entry in the reference list; the compiled paper prints [?] here.",
            f"Add the entry for {key}, or fix the key's spelling.", confidence=0.9))
    for key in _BIBITEM.findall(tex):  # a .bbl lists only what was cited; hand-written lists can drift
        if key.lower() not in {c.lower() for c in cited}:
            out.append(objection(
                "reference_never_cited", "minor", key,
                f"The reference list holds \\bibitem{{{key}}}, which the text never cites.",
                "Cite it where it is relevant, or remove it from the list.", confidence=0.85))
    titles: dict[str, str] = {}
    for chunk in re.split(r"(?=@\s*\w+\s*\{)", bib):
        head, title = _BIBENTRY.search(chunk), _TITLE.search(chunk)
        if not head or not title:
            continue
        t = _norm_title(title.group(1))
        cited_lower = {c.lower() for c in cited}
        if (len(t) > 20 and t in titles and titles[t] != head.group(2)
                and titles[t].lower() in cited_lower and head.group(2).lower() in cited_lower):
            out.append(objection(
                "reference_duplicate", "minor", f"{titles[t]} / {head.group(2)}",
                f"Two bibliography entries, {titles[t]} and {head.group(2)}, have the same title "
                f"(\"{title.group(1)[:80]}\"); if both are cited the paper lists one work twice.",
                "Keep one entry and point both citations at it.", confidence=0.8))
        titles.setdefault(t, head.group(2))
    return out


_REF_HEAD = re.compile(r"^\s*(?:\\section\*?\{)?\s*(?:\d+\.?\s*)?(?:references|bibliography|literature cited|works cited|"
                       r"参考文献)\s*\}?\s*:?\s*$",
                       re.I | re.M)
_ENTRY = re.compile(r"^\s*\[(\d{1,3})\]|^\s*(\d{1,3})\.\s+[A-Z\u4e00-\u9fff]", re.M)
_BRACKET = re.compile(r"\[(\d{1,3}(?:\s*[,–\-]\s*\d{1,3})*)\]")


def _expand(group: str) -> set[int]:
    out: set[int] = set()
    for part in group.split(","):
        bounds = [int(x) for x in re.split(r"\s*[–\-]\s*", part.strip()) if x]
        if len(bounds) == 2 and 0 < bounds[1] - bounds[0] < 50:
            out |= set(range(bounds[0], bounds[1] + 1))
        elif bounds:
            out.add(bounds[0])
    return out


def check_numbered(text: str) -> list[dict[str, Any]]:
    heads = list(_REF_HEAD.finditer(text))
    if not heads:
        return []
    body, refs = text[: heads[-1].start()], text[heads[-1].end():]
    numbers = [int(a or b) for a, b in _ENTRY.findall(refs)]
    if len(numbers) < 5 or numbers[0] != 1:
        return []
    count = max(n for i, n in enumerate(numbers) if n <= i + 2)  # stop at the first big jump (page numbers)
    cited: set[int] = set()
    for g in _BRACKET.findall(body):
        cited |= _expand(g)
    if len(cited & set(range(1, count + 1))) < count / 2:
        return []  # not a numbered citation style
    out = []
    beyond = sorted(n for n in cited if n > count)
    if beyond:
        out.append(objection(
            "citation_beyond_list", "major", ", ".join(f"[{n}]" for n in beyond[:10]),
            f"The text cites {', '.join(f'[{n}]' for n in beyond[:10])}, but the reference list ends at [{count}].",
            "Add the missing entries or renumber the citations.", numbers=[str(n) for n in beyond[:10]],
            confidence=0.8))
    never = sorted(set(range(1, count + 1)) - cited)
    if never:
        out.append(objection(
            "reference_never_cited", "minor", ", ".join(f"[{n}]" for n in never[:15]),
            f"Reference list entries {', '.join(f'[{n}]' for n in never[:15])}"
            + (" and more" if len(never) > 15 else "") + " are never cited in the text.",
            "Cite each where it is relevant, or remove it from the list.", confidence=0.6))
    return out


def run(text: str, bib: str = "") -> list[dict[str, Any]]:
    if "\\begin{document}" in text or "\\cite" in text or "\\bibitem" in text:
        return check_latex(text, bib)
    return check_numbered(text)


def demo() -> None:
    assert check_latex(r"\\begin{document}\\cite{a}\\bibitem{a} \\citenamefont {Ernzerhof} x\\end{document}") == []
    assert check_latex(r"\\newcommand{\\mycite}[1]{\\cite{#1}}\\cite{tgd}", "@misc{TGD,\n title={x}}") == []
    tex = r"""\begin{document}As shown before \citep{smith2020, lee2021} and \cite{wang2019}.
\begin{thebibliography}{9}\bibitem{smith2020} A.\bibitem{wang2019} B.\bibitem{old1999} C.\end{thebibliography}
\end{document}"""
    assert sorted(f["category"] for f in run(tex)) == ["citation_undefined", "reference_never_cited"]
    bib = "@article{a1,\n title={Deep Residual Learning for Image Recognition},\n}\n" \
          "@inproceedings{a2,\n title = {Deep residual learning for image recognition},\n}\n"
    hits = run(r"\begin{document}\cite{a1,a2}\end{document}", bib)
    assert [f["category"] for f in hits] == ["reference_duplicate"], hits
    plain = "Intro [1], [2,3] and [4-6]. Later [9].\nReferences\n" + "".join(
        f"[{i}] Author {i}. Title. 2020.\n" for i in range(1, 8))
    cats = sorted(f["category"] for f in run(plain))
    assert cats == ["citation_beyond_list", "reference_never_cited"], cats
    ok = "Intro [1], [2,3] and [4-7].\nReferences\n" + "".join(f"[{i}] Author {i}. Title.\n" for i in range(1, 8))
    assert run(ok) == [], run(ok)


if __name__ == "__main__":
    demo()
    print("ok")
