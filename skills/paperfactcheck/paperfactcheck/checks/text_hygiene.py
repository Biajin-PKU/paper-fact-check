"""Text a careful author would not leave in a submitted paper.

- Chatbot replies, prompt echoes and placeholders ("Certainly! Here is", "[insert citation]",
  "Figure ??").
- Tortured phrases: fixed terms replaced word by word with synonyms ("profound learning").
- Abbreviations used before their definition, or expanded two ways.
"""
from __future__ import annotations

import re
from typing import Any

from ._common import body_text, objection

_RESIDUE = [
    (r"\bas an ai(?: language)? model\b", "a chatbot's description of itself"),
    (r"\bas of my (?:last )?(?:knowledge|training) (?:cutoff|update)\b", "a chatbot's knowledge-cutoff disclaimer"),
    (r"\b(?:certainly|sure|absolutely|of course)[!,.]\s+(?:here(?:'s| is| are)|below is)\b", "the opening of a chatbot reply"),
    (r"\bhere(?:'s| is) (?:a |the )?(?:revised|rewritten|improved|polished|refined|updated) (?:version|paragraph|text|abstract|introduction)\b",
     "the opening of a chatbot reply"),
    (r"\bi hope this helps\b|\blet me know if you (?:need|want|would like)\b|\bfeel free to (?:ask|adjust|modify)\b",
     "the closing of a chatbot reply"),
    (r"\bregenerate response\b|\bcopy code\b(?=\s*$)", "interface text copied from a chat window"),
    (r"\[(?:insert|add|citation|cite|ref(?:erence)?|todo|tbd|xx+)[^\]]{0,40}\]", "a placeholder in brackets"),
    (r"\bcitation needed\b", "a placeholder"),
    (r"\blorem ipsum\b", "placeholder text"),
    (r"\((?:author|authors),?\s*(?:et al\.?,?\s*)?(?:year|20xx|19xx)\)", "a placeholder citation"),
    (r"\b(?:figure|fig\.|table|section|equation|eq\.)\s*\?\?", "an undefined cross-reference (LaTeX prints ??)"),
    (r"\[\?\]|\[\?,", "an undefined citation (LaTeX prints [?])"),
    (r"作为(?:一个)?(?:AI|人工智能)(?:语言模型|助手)?", "a chatbot's description of itself"),
    (r"(?:当然|好的)[！!，,。]\s*(?:以下是|下面是)", "the opening of a chatbot reply"),
    (r"以下是(?:修改|润色|改写|优化)后的", "the opening of a chatbot reply"),
    (r"希望(?:这|以上内容)?对(?:你|您)有(?:所)?帮助|如(?:果)?(?:你|您)还有(?:其他|任何)问题", "the closing of a chatbot reply"),
    (r"【(?:插入|此处|待补|引用)[^】]{0,30}】|（此处(?:插入|添加|补充)[^）]{0,30}）", "a placeholder"),
    (r"（作者，\s*年份）|\(作者,\s*年份\)", "a placeholder citation"),
]
_RESIDUE_RE = [(re.compile(p, re.I | re.M), why) for p, why in _RESIDUE]

# Tortured phrases with their expected term (Cabanac, Labbe and Magazinov, 2021, and later screens).
TORTURED = {
    "counterfeit consciousness": "artificial intelligence",
    "man-made consciousness": "artificial intelligence",
    "profound learning": "deep learning",
    "profound neural organization": "deep neural network",
    "counterfeit neural organization": "artificial neural network",
    "convolutional neural organization": "convolutional neural network",
    "intermittent neural organization": "recurrent neural network",
    "long transient memory": "long short-term memory",
    "irregular woodland": "random forest",
    "arbitrary woodland": "random forest",
    "choice tree": "decision tree",
    "backing vector machine": "support vector machine",
    "uphold vector machine": "support vector machine",
    "colossal information": "big data",
    "huge information": "big data",
    "enormous information": "big data",
    "flag to commotion": "signal to noise",
    "bosom malignancy": "breast cancer",
    "bosom disease": "breast cancer",
    "bosom peril": "breast cancer",
    "lung malignancy": "lung cancer",
    "prostate malignancy": "prostate cancer",
    "kidney disappointment": "kidney failure",
    "heart disappointment": "heart failure",
    "lactose bigotry": "lactose intolerance",
    "dark opening": "black hole",
    "cloud figuring": "cloud computing",
    "facial acknowledgment": "facial recognition",
    "face acknowledgment": "face recognition",
    "discourse acknowledgment": "speech recognition",
    "picture acknowledgment": "image recognition",
    "picture preparing": "image processing",
    "characteristic language preparing": "natural language processing",
    "regular language handling": "natural language processing",
    "subterranean insect state": "ant colony",
    "subterranean insect settlement": "ant colony",
    "hereditary calculation": "genetic algorithm",
    "mean square blunder": "mean square error",
    "mean squared blunder": "mean squared error",
    "root mean square blunder": "root mean square error",
    "mean outright blunder": "mean absolute error",
    "mean outright mistake": "mean absolute error",
    "blunder rate": "error rate",
    "fluffy rationale": "fuzzy logic",
    "web of things": "internet of things",
    "remote sensor organization": "wireless sensor network",
    "remote organization": "wireless network",
    "versatile organization": "mobile network",
    "consideration component": "attention mechanism",
    "irregular access memory": "random access memory",
    "haphazard access": "random access",
    "p-esteem": "p-value",
    "standard deviation blunder": "standard error",
    "information mining calculation": "data mining algorithm",
    "AI calculation": "machine learning algorithm",
}
_TORTURED_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(TORTURED, key=len, reverse=True)) + r")\b", re.I)


def _lines(text: str) -> str:
    return re.sub(r"\\%", "%", body_text(text))


def detect_residue(text: str) -> list[dict[str, Any]]:
    body = _lines(text)
    out, seen, spans = [], set(), []
    for rx, why in _RESIDUE_RE:
        for m in rx.finditer(body):
            key = m.group(0).lower()
            line = (body.rfind("\n", 0, m.start()), body.find("\n", m.end()))
            if key in seen or (why, line) in spans:
                continue
            seen.add(key)
            spans.append((why, line))
            start = max(0, m.start() - 60)
            out.append(objection(
                "assistant_residue", "major", m.group(0)[:80],
                f"This is {why}, left in the manuscript: \"...{body[start:m.end() + 60].strip()}...\"",
                "Delete it, or replace the placeholder with the real content.", confidence=0.9))
    return out


def detect_tortured(text: str) -> list[dict[str, Any]]:
    body = _lines(text)
    found: dict[str, int] = {}
    for m in _TORTURED_RE.finditer(body):
        found[m.group(1).lower()] = found.get(m.group(1).lower(), 0) + 1
    return [objection(
        "tortured_phrase", "minor", phrase,
        f"\"{phrase}\" ({count}x) is a word-by-word synonym swap of the fixed term \"{TORTURED[phrase]}\"; "
        "readers and editors take it as text run through a paraphrasing tool.",
        f"Use \"{TORTURED[phrase]}\".", confidence=0.85)
        for phrase, count in found.items() if phrase in TORTURED]


_ABBR = r"([A-Z][A-Za-z]{0,2}[A-Z][A-Za-z0-9]{0,5}s?|[A-Z]{2,8}s?)"
_DEF = re.compile(r"\b([A-Za-z][A-Za-z\-]+(?:\s+[A-Za-z][A-Za-z\-]+){1,7})\s*\(\s*" + _ABBR + r"\s*\)")
_SKIP_ABBR = {"I", "II", "III", "IV", "USA", "UK", "EU", "US", "PhD", "DNA", "RNA", "CI", "SD", "SE", "OR", "HR",
              "RR", "AUC", "ROC", "GPU", "CPU", "AI", "ML", "IQR", "ANOVA", "PDF", "URL", "API", "ID", "IDs"}


def _initials_match(words: str, abbr: str) -> bool:
    letters = [w[0].lower() for w in re.split(r"[\s\-]+", words) if w]
    core = abbr.rstrip("s").lower()
    # the abbreviation's letters appear in order among the initials of the trailing words
    j = len(letters) - 1
    for ch in reversed(core):
        while j >= 0 and letters[j] != ch:
            j -= 1
        if j < 0:
            return False
        j -= 1
    return True


def detect_abbreviations(text: str) -> list[dict[str, Any]]:
    body = body_text(text)
    # the abstract defines its own abbreviations; the body is checked from the first section on
    m = re.search(r"\\section\*?\{|^\s*(?:1\.?\s+)?introduction\s*$|^\s*(?:一、|1\s*)?引言\s*$", body, re.I | re.M)
    body = body[m.start():] if m else body
    body = re.sub(r"\\(?:cite\w*|ref|label|eqref|cref|Cref|url|href|includegraphics)\*?(?:\[[^\]]*\])?\{[^}]*\}", " ", body)
    defs: dict[str, list[tuple[int, str]]] = {}
    for d in _DEF.finditer(body):
        words, abbr = d.group(1), d.group(2)
        if abbr in _SKIP_ABBR or not _initials_match(words, abbr):
            continue
        tail = " ".join(words.split()[-len(abbr.rstrip("s")) - 1:])
        defs.setdefault(abbr.rstrip("s"), []).append((d.start(2), tail))
    out = []
    for abbr, places in defs.items():
        first_def = places[0][0]
        use = re.search(r"(?<![A-Za-z0-9\-])" + re.escape(abbr) + r"s?(?![A-Za-z0-9\-])", body)
        if use and use.start() < first_def - 2:
            ctx = body[max(0, use.start() - 50): use.end() + 50].replace("\n", " ").strip()
            out.append(objection(
                "abbreviation_before_definition", "minor", abbr,
                f"\"{abbr}\" is used (\"...{ctx}...\") before it is defined as \"{places[0][1]} ({abbr})\".",
                f"Define {abbr} at its first use in the body.", confidence=0.7))
        tails = {" ".join(re.sub(r"[^a-z ]", " ", t.lower()).split()[-len(abbr):]) for _, t in places}
        if len(tails) > 1:
            out.append(objection(
                "abbreviation_two_expansions", "minor", abbr,
                f"\"{abbr}\" is expanded in two ways: " + " / ".join(f"\"{t}\"" for _, t in places[:3]) + ".",
                f"Use one expansion for {abbr} throughout.", confidence=0.6))
    return out


def run(text: str) -> list[dict[str, Any]]:
    return detect_residue(text) + detect_tortured(text) + detect_abbreviations(text)


def demo() -> None:
    bad = r"""\begin{document}
\section{Introduction}
We train a CNN on scans. A convolutional neural network (CNN) learns features.
Certainly! Here is a revised version of the paragraph.
Results are in Figure ?? and follow prior work [insert citation].
We compare profound learning with an irregular woodland baseline.
作为一个AI语言模型，我无法确认。
\end{document}"""
    cats = sorted(f["category"] for f in run(bad))
    assert cats == ["abbreviation_before_definition"] + ["assistant_residue"] * 4 + ["tortured_phrase"] * 2, cats
    good = r"""\begin{document}
\section{Introduction}
A convolutional neural network (CNN) learns features; the CNN is trained on scans.
We compare deep learning with a random forest baseline (Figure~\ref{fig:a}).
\end{document}"""
    assert run(good) == [], run(good)


if __name__ == "__main__":
    demo()
    print("ok")
