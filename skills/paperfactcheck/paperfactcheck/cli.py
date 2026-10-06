"""paperfactcheck: check a research paper against its own evidence.

    paperfactcheck paper.pdf                       # same as: paperfactcheck check paper.pdf
    paperfactcheck check paper.tex --code repo/    # also check a released code/data folder
    paperfactcheck check paper.docx --offline      # skip reference lookups
    paperfactcheck render <report-dir>             # rebuild the report after a review.json is added
    paperfactcheck mcp                             # serve the checks over MCP (stdio)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import __version__, references
from .catalog import GROUPS, describe
from .checks._common import strip_comments
from .checks import (benford, citation_xref, claim_interval, companion_binding, consistency, constructed_data,
                     figure_panels, grim, grimmer, number_agreement, pvalue, relative_change, stat_recompute,
                     statements, text_hygiene)
from .readers import Doc, NeedsText, load
from .report import render

TEXT_CHECKS = (number_agreement, relative_change, consistency, grimmer, grim, stat_recompute, claim_interval,
               figure_panels, text_hygiene, benford)
SEVERITY = {"critical": 0, "major": 1, "minor": 2}

_HEADING = re.compile(r"\\(?:sub)*section\*?\{([^}]*)\}|^\s*(?:\d+(?:\.\d+)*\.?\s+[A-Z][^\n]{2,70}|[A-Z][A-Z ]{4,40}|"
                      r"[一二三四五六七八九十]+[、.．]\s*\S[^\n]{0,30}|\d+(?:\.\d+)*\s*[\u4e00-\u9fff][^\n]{1,30})\s*$",
                      re.M)
_LEAD = re.compile(r"^\s*(?:\\begin\{document\}|\\maketitle)\s*")


_COMMENTS: dict[int, str] = {}


def _uncommented(text: str) -> str:
    """The text with LaTeX comments removed, so quotes are never located inside a comment (cached)."""
    key = id(text)
    if key not in _COMMENTS:
        _COMMENTS.clear()
        _COMMENTS[key] = strip_comments(text)
    return _COMMENTS[key]


def _section_of(text: str, pos: int) -> str:
    name = ""
    for m in _HEADING.finditer(text, 0, pos):
        name = (m.group(1) or m.group(0)).strip()
    if not name:
        return ""
    return re.sub(r"\s+", " ", name)[:80]


def _locate(text: str, quote: str) -> int:
    for probe in (quote, quote[:60], quote[:30]):
        probe = probe.strip()
        if len(probe) >= 8:
            i = text.find(probe)
            if i >= 0:
                return i
    return -1


def _context(text: str, pos: int, width: int = 260) -> str:
    if pos < 0:
        return ""
    start = max(text.rfind("\n\n", 0, pos), pos - width)
    end = text.find("\n\n", pos)
    end = min(end if end > 0 else len(text), pos + width)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _clean_quote(s: str) -> str:
    """LaTeX source to readable text for display."""
    s = _LEAD.sub("", s)
    s = re.sub(r"\\begin\{(?:tabular|table|figure)\*?\}(?:\{[^}]*\}|\[[^\]]*\])*|\\end\{\w+\*?\}", " ", s)
    s = re.sub(r"\\(?:sub)*section\*?\{([^}]*)\}", r" \1: ", s)
    s = re.sub(r"\\(?:caption|textbf|textit|emph|mathrm|text|mathbf)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:label|includegraphics)(?:\[[^\]]*\])?\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:auto|c|C|eq)?ref\{([^}]*)\}", r"[\1]", s)
    s = re.sub(r"\\(?:cite[a-z]*)\*?(?:\[[^\]]*\])*\{([^}]*)\}", r"[\1]", s)
    s = re.sub(r"\\\\", "; ", s)
    s = re.sub(r"\\%", "%", s)
    s = re.sub(r"\\(?:,|;|!| |quad|qquad|midrule|toprule|bottomrule|hline|centering|small|footnotesize)\b", " ", s)
    s = re.sub(r"(?<=\d)\s*~\s*(?=-?\d)", "–", s)
    s = re.sub(r"[$~]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_EMBEDDED = re.compile(r"\s*(?:Sentence|Context):\s*\"(.+?)\"\s*$", re.S)


_LEFT_STOP = re.compile(r"[.!?](?=\s)|[。！？]|\n\s*\n|\\(?:sub)*section\*?\{[^}]*\}|\\(?:begin|end)\{\w+\*?\}|\\item\b")
_RIGHT_STOP = re.compile(r"[.!?](?=\s|$)|[。！？]|\n\s*\n|\\(?:begin|end)\{")


def _sentence_at(text: str, pos: int) -> str:
    left = text[max(0, pos - 500):pos]
    stops = list(_LEFT_STOP.finditer(left))
    start = pos - len(left) + (stops[-1].end() if stops else 0)
    right = _RIGHT_STOP.search(text, pos, pos + 500)
    end = right.end() if right else min(len(text), pos + 500)
    return text[start:end]


def _calculation(category: str, nums: list[str]) -> str:
    try:
        v = [float(n) for n in nums]
    except ValueError:
        return ""
    if category == "relative_change_mismatch" and len(v) >= 3:
        c, a, b = v[:3]
        return (f"|{nums[1]} - {nums[2]}| / {nums[2]} = {abs(a - b) / b * 100:.1f}%;  "
                f"|{nums[1]} - {nums[2]}| / {nums[1]} = {abs(a - b) / a * 100:.1f}%;  stated: {nums[0]}%")
    if category == "percent_count_mismatch" and len(v) >= 3:
        return f"{nums[1]} / {nums[2]} = {v[1] / v[2] * 100:.2f}%;  stated: {nums[0]}%"
    return ""


def normalize_finding(raw: dict[str, Any], check: str, text: str, lang: str) -> dict[str, Any]:
    text = _uncommented(text)
    if "gate" in raw:  # package checks report files
        category = raw["gate"].split(":")[-1]
        severity, quote, evidence, fix, where = "major", "", raw.get("message", ""), "", raw.get("file", "")
    else:
        category = raw.get("category", "")
        severity = raw.get("severity", "minor")
        severity = "critical" if severity in ("critical", "blocking") else severity
        quote, evidence, fix = _clean_quote(str(raw.get("target", ""))), raw.get("reasoning", ""), raw.get("suggested_fix", "")
        where = ""
    group, title, first = describe(category, lang)
    pos = _locate(text, str(raw.get("target", ""))) if quote else -1
    embedded = _EMBEDDED.search(evidence or "")
    if embedded:  # the detector quoted the sentence itself; use it as the quote
        evidence = evidence[: embedded.start()]
        pos = _locate(text, embedded.group(1).strip())
        quote = _clean_quote(_sentence_at(text, pos) if pos >= 0 else embedded.group(1))
    elif quote and pos < 0 and raw.get("numbers"):  # target is a key, not text: find the sentence by its number
        for n in raw["numbers"]:
            m = re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d])", text)
            if m:
                pos = m.start()
                quote = _clean_quote(_sentence_at(text, pos))
                break
    elif pos >= 0 and len(quote) < 120 and category not in ("assistant_residue", "tortured_phrase"):
        quote = _clean_quote(_sentence_at(text, pos)) or quote
    if pos >= 0 and not where:
        where = _section_of(text, pos)
    return {"source": "script", "check": check, "category": category, "group": group, "title": title,
            "severity": severity, "order": "first" if first and severity in ("critical", "major") else "second",
            "where": where, "quote": quote, "context": _clean_quote(_context(text, pos)),
            "evidence": _clean_quote(evidence), "calculation": _calculation(category, raw.get("numbers", [])),
            "fix": (lambda x: x[:1].upper() + x[1:])(_clean_quote(fix)),
            "numbers": raw.get("numbers", [])}


def run_checks(doc: Doc, offline: bool = False, lang: str = "") -> dict[str, Any]:
    lang = lang or doc.language
    text = doc.text
    found: list[dict[str, Any]] = []
    for module in TEXT_CHECKS:
        name = module.__name__.rsplit(".", 1)[-1]
        found += [normalize_finding(f, name, text, lang) for f in module.run(text)]
    found += [normalize_finding(f, "pvalue", text, lang) for f in pvalue.detect_pvalue_clustering(text)]
    found += [normalize_finding(f, "citation_xref", text, lang) for f in citation_xref.run(text, doc.bib)]
    not_verified: list[dict[str, str]] = [{"item": n, "reason": ""} for n in doc.notes]
    if doc.package is not None:
        found += [normalize_finding(f, "companion_binding", text, lang) for f in companion_binding.run(doc.package, text)]
        found += [normalize_finding(f, "constructed_data", text, lang) for f in constructed_data.run(doc.package)]
    else:
        not_verified.append({"item": "Code and data" if lang != "zh" else "代码和数据",
                             "reason": "no code/data folder was provided (--code)" if lang != "zh"
                             else "没有提供代码或数据文件夹（--code）"})
    refs: dict[str, Any] = {"total": 0, "items": [], "findings": [], "not_verified": []}
    if offline:
        not_verified.append({"item": "References" if lang != "zh" else "参考文献",
                             "reason": "lookups turned off (--offline)" if lang != "zh" else "已关闭联网核查（--offline）"})
    else:
        refs = references.check(text, doc.bib)
        found += [normalize_finding(f, "references", text, lang) for f in refs.pop("findings")]
        not_verified += refs.pop("not_verified")
    groups = list(GROUPS)
    found.sort(key=lambda f: (groups.index(f["group"]), f["order"] != "first", SEVERITY.get(f["severity"], 3)))
    for i, f in enumerate(found, 1):
        f["id"] = f"S{i}"
    return {"tool": "paperfactcheck", "version": __version__,
            "generated": _dt.datetime.now().isoformat(timespec="seconds"),
            "paper": doc.path.name, "input": doc.kind, "language": lang,
            "findings": found, "references": refs, "statements": statements.scan(text),
            "not_verified": not_verified}


def summary(result: dict[str, Any], out: Path) -> str:
    f = result["findings"]
    first = [x for x in f if x["order"] == "first"]
    lines = [f"# Paper Fact Check: {result['paper']}", "",
             f"{len(f)} script finding(s), {len(first)} first-order. Report: {out / 'report.html'}", ""]
    for x in f:
        lines.append(f"- {x['id']} [{x['severity']}/{x['order']}] {x['title']}"
                     + (f" ({x['where']})" if x["where"] else "") + f": {x['evidence'][:220]}")
    refs = result["references"]
    if refs.get("total"):
        st: dict[str, int] = {}
        for it in refs["items"]:
            st[it["status"]] = st.get(it["status"], 0) + 1
        lines += ["", f"References: {refs['total']} entries, " + ", ".join(f"{v} {k}" for k, v in sorted(st.items()))]
    missing = [s["statement"] for s in result["statements"] if not s["found"]]
    if missing:
        lines += ["", "Statements not found: " + ", ".join(missing)]
    if result["not_verified"]:
        lines += ["", "Not verified: " + "; ".join(f"{n['item']} ({n['reason']})" if n["reason"] else n["item"]
                                                for n in result["not_verified"])]
    lines += ["", f"Full data: {out / 'findings.json'}. Next: review per SKILL.md, write {out / 'review.json'}, "
              f"then run `render {out}`."]
    return "\n".join(lines)


def cmd_check(args: argparse.Namespace) -> int:
    try:
        doc = load(Path(args.paper), Path(args.code).expanduser() if args.code else None)
    except NeedsText as e:
        print(f"paperfactcheck: {e}", file=sys.stderr)
        return 3
    result = run_checks(doc, offline=args.offline, lang="" if args.lang == "auto" else args.lang)
    out = Path(args.out or f"paperfactcheck-{Path(args.paper).stem}").expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "findings.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "manuscript.txt").write_text(doc.text, encoding="utf-8")
    render(out)
    print(json.dumps(result, ensure_ascii=False, indent=1) if args.json else summary(result, out))
    return 1 if any(f["order"] == "first" for f in result["findings"]) else 0


def cmd_render(args: argparse.Namespace) -> int:
    out = Path(args.dir).expanduser().resolve()
    paths = render(out, lang=None if args.lang == "auto" else args.lang)
    print("\n".join(str(p) for p in paths))
    return 0


def cmd_mcp(_args: argparse.Namespace) -> int:
    from .mcp import serve
    return serve()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("check", "render", "mcp", "-h", "--help", "--version"):
        argv.insert(0, "check")
    ap = argparse.ArgumentParser(prog="paperfactcheck", description="Check a research paper against its own evidence.")
    ap.add_argument("--version", action="version", version=f"paperfactcheck {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="run every check and write the report")
    c.add_argument("paper", help="PDF, Word (.docx), LaTeX file/folder/zip, Markdown or text")
    c.add_argument("--code", help="released code/data folder")
    c.add_argument("--out", help="report folder (default: ./paperfactcheck-<name>)")
    c.add_argument("--offline", action="store_true", help="skip reference lookups")
    c.add_argument("--lang", default="auto", choices=("auto", "en", "zh"), help="report language")
    c.add_argument("--json", action="store_true", help="print the findings as JSON")
    c.set_defaults(func=cmd_check)
    r = sub.add_parser("render", help="rebuild report.html and report.md, merging review.json if present")
    r.add_argument("dir")
    r.add_argument("--lang", default="auto", choices=("auto", "en", "zh"))
    r.set_defaults(func=cmd_render)
    m = sub.add_parser("mcp", help="serve over the Model Context Protocol (stdio)")
    m.set_defaults(func=cmd_mcp)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
