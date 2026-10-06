"""Turn whatever the user hands over into one text the checks can read.

Every format ends up as LaTeX-flavoured text: prose with `%` escaped, and tables rebuilt as
`tabular` blocks with their captions, so the table checks work on Word and Markdown files too.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from .checks.number_agreement import read_tree


class NeedsText(Exception):
    """The file cannot be read here; the message says what to do instead."""


@dataclass
class Doc:
    text: str
    kind: str                      # latex | pdf | docx | markdown | text
    path: Path
    root: Path
    bib: str = ""
    language: str = "en"
    package: Path | None = None    # code/data folder, if any
    notes: list[str] = field(default_factory=list)


_FULLWIDTH = str.maketrans({**{chr(0xFF10 + i): str(i) for i in range(10)},
                            "（": "(", "）": ")", "，": ", ", "：": ": ", "；": "; ", "＝": "=", "＜": "<",
                            "＞": ">", "～": "~", "－": "-", "．": ".", "＋": "+", "／": "/", "％": "\\%",
                            "≦": "≤", "≧": "≥", "\u3000": " "})


def normalize(text: str) -> str:
    """Full-width digits and punctuation to ASCII so numbers read the same in Chinese and English text."""
    return text.translate(_FULLWIDTH)


def _escape_percent(text: str) -> str:
    return re.sub(r"(?<!\\)%", r"\\%", text)


def _language(text: str) -> str:
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    return "zh" if cjk > max(200, 0.05 * len(text)) else "en"


def _table(caption: str, rows: list[list[str]]) -> str:
    def cell(c: str) -> str:
        return _escape_percent(c.replace("&", r"\&").strip())
    width = max((len(r) for r in rows), default=1)
    body = "\n".join(" & ".join(cell(c) for c in r) + r" \\" for r in rows)
    return (f"\n\\begin{{table}}\n\\caption{{{_escape_percent(caption)}}}\n"
            f"\\begin{{tabular}}{{{'l' * width}}}\n{body}\n\\end{{tabular}}\n\\end{{table}}\n")


_CAPTION = re.compile(r"^\s*(?:table|tab\.|表)\s*[\dSIVX]+", re.I)


# --- formats -------------------------------------------------------------------------------------

def _docx(path: Path) -> str:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    w = "{%s}" % ns["w"]
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    out, last_para = [], ""

    def para_text(p) -> str:
        parts = []
        for node in p.iter():
            if node.tag == w + "t" and node.text:
                parts.append(node.text)
            elif node.tag == w + "tab":
                parts.append(" ")
            elif node.tag in (w + "br", w + "cr"):
                parts.append("\n")
        return "".join(parts)

    body = root.find("w:body", ns)
    for child in body if body is not None else []:
        if child.tag == w + "p":
            t = para_text(child)
            style = child.find("w:pPr/w:pStyle", ns)
            if style is not None and re.match(r"(?i)heading|标题", style.get(w + "val", "")):
                t = f"\n\\section{{{t.strip()}}}" if t.strip() else t
            else:
                t = _escape_percent(t)
            out.append(t)
            if t.strip():
                last_para = t.strip()
        elif child.tag == w + "tbl":
            rows = [[" ".join(para_text(p) for p in tc.iter(w + "p")) for tc in tr.iter(w + "tc")]
                    for tr in child.iter(w + "tr")]
            caption = last_para if _CAPTION.match(last_para) else ""
            out.append(_table(caption, rows))
    return "\n".join(out)


_PIPE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_PIPE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}")


def _markdown(text: str) -> str:
    lines, out, i = text.splitlines(), [], 0
    while i < len(lines):
        if _PIPE_ROW.match(lines[i]) and i + 1 < len(lines) and _PIPE_RULE.match(lines[i + 1]):
            caption = next((l for l in reversed(out[-3:]) if l.strip()), "")
            rows = []
            while i < len(lines) and _PIPE_ROW.match(lines[i]):
                if not _PIPE_RULE.match(lines[i]):
                    rows.append([c.strip() for c in _PIPE_ROW.match(lines[i]).group(1).split("|")])
                i += 1
            out.append(_table(caption if _CAPTION.match(caption.lstrip("#* ")) else "", rows))
            continue
        heading = re.match(r"^\s*#{1,6}\s+(.*)", lines[i])
        out.append(f"\\section{{{heading.group(1).strip()}}}" if heading else _escape_percent(lines[i]))
        i += 1
    return "\n".join(out)


def _pdf(path: Path) -> str:
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True,
                              check=True).stdout
    try:
        from pypdf import PdfReader  # optional
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    except ImportError:
        raise NeedsText(
            f"Cannot read {path.name}: install poppler (`pdftotext`) or `pip install pypdf`, or save the paper's "
            "text as a .txt/.md file (keep tables as Markdown tables) and run the check on that.") from None


# --- entry ---------------------------------------------------------------------------------------

def _main_tex(folder: Path) -> Path | None:
    cands = [p for p in folder.rglob("*.tex") if "\\documentclass" in p.read_text(encoding="utf-8", errors="ignore")]
    cands.sort(key=lambda p: (p.name != "main.tex", len(p.parts), -p.stat().st_size))
    return cands[0] if cands else None


def _bib(main: Path, tex: str) -> str:
    names = []
    for group in re.findall(r"\\(?:bibliography|addbibresource)\{([^}]+)\}", tex):
        names += [n.strip() for n in group.split(",")]
    files = [main.parent / (n if n.endswith(".bib") else n + ".bib") for n in names]
    files = [f for f in files if f.is_file()] or sorted(main.parent.glob("*.bib")) or sorted(main.parent.glob("*.bbl"))
    return "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files)


def _package_near(folder: Path) -> Path | None:
    for c in (folder / "companion", folder / "code", folder, folder.parent / "companion", folder.parent):
        if (c / "results").is_dir():
            return c
    return None


def load(path: Path, code: Path | None = None) -> Doc:
    path = path.expanduser().resolve()
    if not path.exists():
        raise NeedsText(f"{path} does not exist.")
    if path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="paper-fact-check-"))
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                target = (tmp / member).resolve()
                if not str(target).startswith(str(tmp)):
                    raise NeedsText(f"{path.name} contains an unsafe path: {member}")
            z.extractall(tmp)
        doc = load(tmp, code)
        doc.path = path
        return doc
    if path.is_dir():
        main = _main_tex(path)
        if main is None:
            for pattern in ("*.pdf", "*.docx", "*.md", "*.txt"):
                found = sorted(path.rglob(pattern))
                if found:
                    return load(found[0], code or _package_near(path))
            raise NeedsText(f"No .tex, .pdf, .docx, .md or .txt manuscript found in {path}.")
        doc = load(main, code or _package_near(path))
        return doc
    suffix = path.suffix.lower()
    if suffix == ".tex":
        text, kind = read_tree(path), "latex"
        bib = _bib(path, text)
    elif suffix == ".pdf":
        text, kind, bib = _escape_percent(_pdf(path)), "pdf", ""
    elif suffix == ".docx":
        text, kind, bib = _docx(path), "docx", ""
    elif suffix in (".md", ".markdown"):
        text, kind, bib = _markdown(path.read_text(encoding="utf-8", errors="replace")), "markdown", ""
    elif suffix in (".txt", ".text", ""):
        text, kind, bib = _markdown(path.read_text(encoding="utf-8", errors="replace")), "text", ""
    elif suffix == ".doc":
        raise NeedsText("Old .doc files cannot be read; save the paper as .docx or PDF.")
    else:
        raise NeedsText(f"Unsupported file type: {path.suffix}. Use PDF, Word (.docx), LaTeX, Markdown or text.")
    text = normalize(text)
    doc = Doc(text=text, kind=kind, path=path, root=path.parent, bib=bib, language=_language(text),
              package=code or _package_near(path.parent))
    if kind == "pdf":
        doc.notes.append("Read from PDF: table cells are not separated, so table-against-text checks are "
                         "limited; the LaTeX source or the Word file gives fuller results.")
    return doc
