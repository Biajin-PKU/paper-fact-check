#!/usr/bin/env python3
"""Benchmark on author corrections: does Paper Fact Check flag, in a paper's first arXiv version, the
numbers its authors later corrected?

1. Search arXiv for papers whose version comment mentions a correction to a table or numbers.
2. Download the LaTeX source of v1 and of the next version; diff the body word by word and keep the
   decimals that were replaced ("0.847" -> "0.851").
3. Run the text checks on v1. A correction is caught when a finding on v1 names the old number.
   The same checks on the corrected version give the findings that remain.

Downloads are cached in benchmark/.cache and spaced 3 s apart (arXiv's API guidance).

    python3 benchmark/arxiv_corrections.py [--max 80] [--out benchmark/results.json]
    python3 benchmark/arxiv_corrections.py --scan 60   # findings per paper on recent unseen papers
"""
from __future__ import annotations

import argparse
import difflib
import gzip
import io
import json
import re
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "paper-fact-check"))
from paper_fact_check.checks.number_agreement import read_tree  # noqa: E402
from paper_fact_check.cli import run_checks  # noqa: E402
from paper_fact_check.readers import Doc, normalize  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache"
QUERIES = [
    'co:typo AND co:table', 'co:typos AND co:table', 'co:corrected AND co:table',
    'co:corrected AND co:numbers', 'co:corrected AND co:values', 'co:fixed AND co:table',
    'co:error AND co:table', 'co:corrected AND co:results', 'co:typo AND co:results',
]
ATOM = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
DECIMAL = re.compile(r"^-?\d*\.\d+$")
_last = [0.0]


def fetch(url: str) -> bytes:
    key = CACHE / re.sub(r"[^\w.-]", "_", url)[-180:]
    if key.exists():
        return key.read_bytes()
    time.sleep(max(0.0, 3.0 - (time.time() - _last[0])))
    request = urllib.request.Request(url, headers={"User-Agent": "paper-fact-check-benchmark/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    _last[0] = time.time()
    CACHE.mkdir(exist_ok=True)
    key.write_bytes(data)
    return data


def candidates(limit: int) -> list[dict]:
    seen: dict[str, dict] = {}
    for query in QUERIES:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": query, "max_results": 100, "sortBy": "submittedDate"})
        root = ET.fromstring(fetch(url))
        for entry in root.findall("a:entry", ATOM):
            ident = entry.find("a:id", ATOM).text.rsplit("/abs/", 1)[-1]
            base, _, version = ident.rpartition("v")
            comment = entry.find("x:comment", ATOM)
            if base and version.isdigit() and int(version) >= 2 and base not in seen:
                seen[base] = {"id": base, "latest": int(version),
                              "comment": " ".join((comment.text or "").split()) if comment is not None else ""}
    return list(seen.values())[:limit]


def source_text(ident: str, version: int) -> str | None:
    """The main .tex of one version, with \\input files inlined and its .bib/.bbl text appended after
    a marker; None if the source is not LaTeX."""
    data = fetch(f"https://arxiv.org/e-print/{ident}v{version}")
    work = CACHE / f"src_{ident.replace('/', '_')}v{version}"
    if not work.exists():
        work.mkdir(parents=True)
        try:
            with tarfile.open(fileobj=io.BytesIO(data)) as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith((".tex", ".bib", ".bbl")) and ".." not in member.name:
                        target = work / member.name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(tar.extractfile(member).read())
        except tarfile.TarError:
            try:
                (work / "main.tex").write_bytes(gzip.decompress(data))
            except OSError:
                (work / "main.tex").write_bytes(data)
    mains = [p for p in work.rglob("*.tex") if "\\documentclass" in p.read_text(errors="replace")]
    if not mains:
        return None
    main = min(mains, key=lambda p: (p.name != "main.tex", len(p.parts)))
    bib = "\n".join(p.read_text(errors="replace") for p in sorted(work.rglob("*.bib")) or sorted(work.rglob("*.bbl")))
    return read_tree(main) + (BIB_MARK + bib if bib else "")


def corrected_numbers(old: str, new: str) -> list[tuple[str, str]]:
    """Decimals replaced between two versions, as (old, new) pairs."""
    a, b = old.split(), new.split()
    pairs = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "replace" and (i2 - i1) == (j2 - j1) and i2 - i1 <= 6:
            for x, y in zip(a[i1:i2], b[j1:j2]):
                x, y = x.strip("(),;:$%\\{}[]"), y.strip("(),;:$%\\{}[]")
                if DECIMAL.match(x) and DECIMAL.match(y) and x != y:
                    pairs.append((x, y))
    return pairs


BIB_MARK = "\n%%PAPERFACTCHECK-BIB%%\n"


def findings(tex: str) -> list[dict]:
    """Every script check except the reference lookups, on one LaTeX text."""
    tex, _, bib = tex.partition(BIB_MARK)
    doc = Doc(text=normalize(tex), kind="latex", path=Path("paper.tex"), root=Path("."), bib=bib)
    return run_checks(doc, offline=True, lang="en")["findings"]


def names(finding: dict, number: str) -> bool:
    """The finding is about this number: it is in the finding's own evidence or numbers, not merely in
    the quoted passage around it."""
    text = finding.get("evidence", "") + " " + " ".join(finding.get("numbers", []))
    return re.search(r"(?<![\d.])" + re.escape(number) + r"(?![\d])", text) is not None


def scan(n: int, out: Path, exclude: set[str] | None = None, since: str = "",
         cats: tuple[str, ...] = ("cs.LG", "stat.ME", "q-bio.QM", "econ.EM")) -> None:
    """Script findings on the latest version of recent papers across fields, skipping any in `exclude`."""
    per_cat = max(1, n // len(cats))
    rows = []
    exclude = exclude or set()
    for cat in cats:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": f"cat:{cat}" + (f" AND submittedDate:[{since}0000 TO 209912312359]" if since else ""),
             "max_results": per_cat, "sortBy": "submittedDate"})
        for entry in ET.fromstring(fetch(url)).findall("a:entry", ATOM):
            ident = entry.find("a:id", ATOM).text.rsplit("/abs/", 1)[-1]
            base, _, version = ident.rpartition("v")
            if base in exclude:
                continue
            try:
                tex = source_text(base, int(version))
            except Exception:  # noqa: BLE001
                continue
            if tex:
                found = findings(tex)
                rows.append({"id": ident, "field": cat, "findings": [
                    {"check": f["check"], "category": f["category"], "severity": f["severity"], "order": f["order"],
                     "quote": f["quote"][:300], "evidence": f["evidence"][:300]} for f in found]})
                print(f"{ident} {cat}: {len(found)}", file=sys.stderr)
    counts: dict[str, int] = {}
    for row in rows:
        for f in row["findings"]:
            counts[f["check"]] = counts.get(f["check"], 0) + 1
    summary = {"papers": len(rows), "papers_with_findings": sum(bool(r["findings"]) for r in rows),
               "majors": sum(f["severity"] == "major" for r in rows for f in r["findings"]), "by_check": counts}
    out.write_text(json.dumps({"summary": summary, "papers": rows}, indent=1, ensure_ascii=False))
    print(json.dumps(summary))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=80)
    ap.add_argument("--scan", type=int, help="scan this many recent papers instead")
    ap.add_argument("--exclude", type=Path, help="a previous scan.json whose papers are skipped")
    ap.add_argument("--since", default="", help="only papers submitted on or after this date, YYYYMMDD")
    ap.add_argument("--cats", default="cs.LG,stat.ME,q-bio.QM,econ.EM", help="arXiv categories, comma-separated")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "results.json")
    args = ap.parse_args()
    if args.scan:
        seen = {p["id"].rpartition("v")[0] for p in json.loads(args.exclude.read_text())["papers"]} if args.exclude else set()
        return scan(args.scan, args.out, seen, args.since, tuple(args.cats.split(",")))
    rows = []
    for paper in candidates(args.max):
        try:
            v1, v2 = source_text(paper["id"], 1), source_text(paper["id"], 2)
        except Exception as exc:  # noqa: BLE001 - a withdrawn or PDF-only paper is skipped
            print(f"skip {paper['id']}: {type(exc).__name__}", file=sys.stderr)
            continue
        if not v1 or not v2:
            continue
        pairs = corrected_numbers(v1, v2)
        if not pairs:
            continue
        before, after = findings(v1), findings(v2)
        caught = [p for p in pairs if any(names(f, p[0]) for f in before)]
        rows.append({**paper, "corrections": pairs, "caught": caught,
                     "findings_v1": len(before), "findings_v2": len(after),
                     "caught_by": sorted({f["check"] for f in before for p in caught if names(f, p[0])})})
        print(f"{paper['id']}: {len(pairs)} corrected, {len(caught)} caught, findings {len(before)} -> {len(after)}",
              file=sys.stderr)
    summary = {"papers_with_numeric_corrections": len(rows),
               "corrections": sum(len(r["corrections"]) for r in rows),
               "papers_caught": sum(bool(r["caught"]) for r in rows),
               "corrections_caught": sum(len(r["caught"]) for r in rows)}
    args.out.write_text(json.dumps({"summary": summary, "papers": rows}, indent=1, ensure_ascii=False))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
