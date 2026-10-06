"""Look every reference up: does it exist, is it the work the citation says, has it been retracted.

Sources (free, no key): Crossref (metadata, retraction and correction notices), the DOI handle
service (DOIs Crossref does not hold, such as Zenodo or arXiv DOIs), arXiv, and OpenAlex (search
fallback and abstracts). A network failure makes a reference unverifiable, never a finding.
"""
from __future__ import annotations

import difflib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .checks.citation_xref import _REF_HEAD, CITE_CMD

UA = f"paper-fact-check/{__version__} (https://github.com/Biajin-PKU/paper-fact-check)"
CACHE = Path.home() / ".cache" / "paper-fact-check" / "lookups.json"
MAX_REFS = 200

_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>{}\\,;]+[^\s\"'<>{}\\,;.)\]])")
_ARXIV = re.compile(r"(?:arXiv:\s*|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
_CJK = re.compile(r"[\u4e00-\u9fff]")
_ARTICLE_HINT = re.compile(r"\b(?:journal|proceedings|proc\.|conference|conf\.|transactions|trans\.|letters|review|advances in|"
                           r"\d{4};\s*\d+|"
                           r"vol\.|volume|pp\.|pages|\d+\s*\(\d+\)\s*:|arxiv|ieee|acm|nature|science|lancet|plos)\b",
                           re.I)


# --- entries -------------------------------------------------------------------------------------

def _bib_entries(bib: str) -> list[dict[str, Any]]:
    out = []
    for m in re.finditer(r"@\s*(\w+)\s*\{\s*([^,\s]+)\s*,", bib):
        kind = m.group(1).lower()
        if kind in ("string", "comment", "preamble"):
            continue
        depth, i = 1, m.end()
        while i < len(bib) and depth:
            depth += {"{": 1, "}": -1}.get(bib[i], 0)
            i += 1
        body, fields = bib[m.end(): i - 1], {}
        for f in re.finditer(r"(\w+)\s*=\s*", body):
            j, start = f.end(), f.end()
            if j < len(body) and body[j] == "{":
                d = 0
                while j < len(body):
                    d += {"{": 1, "}": -1}.get(body[j], 0)
                    j += 1
                    if d == 0:
                        break
                value = body[start + 1: j - 1]
            elif j < len(body) and body[j] == '"':
                k = body.find('"', j + 1)
                value = body[j + 1: k if k > 0 else len(body)]
            else:
                value = re.match(r"[^,\n]*", body[j:]).group(0)
            fields.setdefault(f.group(1).lower(), re.sub(r"\s+", " ", re.sub(r"[{}]|\\[a-zA-Z]+\s?", "", value)).strip())
        doi = fields.get("doi", "")
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
        arxiv = fields.get("eprint", "") if "arxiv" in (fields.get("archiveprefix", "") + fields.get("journal", "")).lower() \
            else ""
        if not arxiv:
            a = _ARXIV.search(" ".join(fields.values()))
            arxiv = a.group(1) if a else ""
        raw = ". ".join(x for x in (fields.get("author", ""), fields.get("title", ""),
                                     fields.get("journal") or fields.get("booktitle", ""), fields.get("year", "")) if x)
        out.append({"key": m.group(2), "label": m.group(2), "raw": raw, "title": fields.get("title", ""),
                    "year": fields.get("year", "")[:4], "doi": doi, "arxiv": re.sub(r"v\d+$", "", arxiv),
                    "article": kind in ("article", "inproceedings", "conference") or bool(arxiv)})
    return out


def _strip_tex(s: str) -> str:
    s = re.sub(r"\\(?:emph|textit|textbf|newblock|em|it|bf|url)\b\s*", " ", s)
    s = re.sub(r"\\[a-zA-Z]+\s*|[{}~]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def guess_title(raw: str) -> str:
    """The title inside a formatted reference: quoted, after an APA year, or the segment after the authors."""
    body = re.sub(r"^\s*\[?\d{1,3}[\].]\s*", "", raw)
    quoted = re.search(r"[\"“”]([^\"“”]{15,250})[\"“”]", body)
    if quoted:
        return quoted.group(1).strip(" .,")
    vancouver = re.match(r"(?:[A-Z][A-Za-z'\-]+(?: [A-Z][A-Za-z'\-]+)? [A-Z]{1,3}(?:,\s*|\s+and\s+|$|(?=\.)))+"
                         r"(?:,?\s*et al)?\.\s+(.+?)[.?]\s", body)
    if vancouver and len(vancouver.group(1).split()) >= 3:
        return vancouver.group(1).strip()
    apa = re.search(r"\((?:19|20)\d\d[a-z]?\)\.\s+(.+?)(?:\.\s|\?\s|$)", body)
    if apa:
        return apa.group(1).strip()
    parts = [p.strip() for p in re.split(r"(?<=[^A-Z\s])\.\s+|(?<=\b[A-Z])\.\s+(?=[A-Z][a-z]{3,})", body) if p.strip()]
    for i, part in enumerate(parts[:-1]):
        authors = re.search(r"et al|^[A-Z][A-Za-z'\-]+,? [A-Z]{1,3}\b|,\s*[A-Z]\.|\band\b|&", part)
        if authors and len(parts[i + 1].split()) >= 4:
            return parts[i + 1]
    return ""


def _from_text(raw: str, key: str, label: str) -> dict[str, Any]:
    doi = _DOI.search(raw)
    arxiv = _ARXIV.search(raw)
    year = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", raw)
    return {"key": key, "label": label, "raw": raw[:600], "title": guess_title(raw),
            "year": year.group(1) if year else "", "doi": doi.group(1) if doi else "",
            "arxiv": arxiv.group(1) if arxiv else "", "article": bool(_ARTICLE_HINT.search(raw)) or bool(arxiv)}


def extract(text: str, bib: str = "") -> list[dict[str, Any]]:
    if bib.strip():
        return _bib_entries(bib)
    items = re.findall(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\}|$)",
                       text, re.S)
    if items:
        return [_from_text(_strip_tex(body), key, key) for key, body in items]
    heads = list(_REF_HEAD.finditer(text))
    if not heads:
        return []
    refs = text[heads[-1].end():]
    refs = re.split(r"\n\s*(?:appendix|supplementary|附录)\b", refs, flags=re.I)[0]
    parts = re.split(r"\n\s*(?=\[\d{1,3}\]\s)|\n\s*(?=\d{1,3}\.\s+[A-Z\u4e00-\u9fff])", "\n" + refs)
    entries = [re.sub(r"\s+", " ", p).strip() for p in parts if len(p.strip()) > 25]
    if len(entries) < 3:  # author-year list: one entry per paragraph or per hanging line
        entries = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n|\n(?=[A-Z][A-Za-z'\-]+,\s)", refs)
                   if len(p.strip()) > 25]
    out = []
    for i, e in enumerate(entries[:MAX_REFS], 1):
        n = re.match(r"\[?(\d{1,3})[\].]", e)
        label = f"[{n.group(1)}]" if n else f"#{i}"
        out.append(_from_text(e, str(n.group(1)) if n else f"#{i}", label))
    return out


# --- lookups -------------------------------------------------------------------------------------

class Web:
    def __init__(self, fetch: Callable[[str], Any] | None = None, cache: Path | None = CACHE):
        self._fetch = fetch or self._http
        self._lock = threading.Lock()
        self._cache_path = cache
        self._cache: dict[str, Any] = {}
        if cache and cache.is_file():
            try:
                self._cache = json.loads(cache.read_text(encoding="utf-8"))
            except ValueError:
                self._cache = {}

    @staticmethod
    def _http(url: str) -> Any:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    body = r.read().decode("utf-8", "replace")
                return json.loads(body) if body.lstrip().startswith(("{", "[")) else {"_text": body}
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return {"_status": 404}
                if e.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError("unreachable")

    def get(self, url: str) -> Any:
        with self._lock:
            if url in self._cache:
                return self._cache[url]
        value = self._fetch(url)  # exceptions propagate: the caller marks the reference unverifiable
        with self._lock:
            self._cache[url] = value
        return value

    def save(self) -> None:
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(json.dumps(self._cache)[:50_000_000], encoding="utf-8")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def _title_in(candidate: str, text: str) -> bool:
    words = [w for w in _norm(candidate).split() if len(w) > 2]
    if len(words) < 3:
        return False
    hay = set(_norm(text).split())
    return sum(w in hay for w in words) / len(words) >= 0.85


def _same_title(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85 or (len(a) > 20 and (a in b or b in a))


def _crossref_work(web: Web, doi: str) -> dict | None:
    data = web.get("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/()"))
    return None if data.get("_status") == 404 else data.get("message")


def _crossref_search(web: Web, raw: str) -> list[dict]:
    q = urllib.parse.urlencode({"query.bibliographic": raw[:400], "rows": 3,
                                "select": "DOI,title,issued,updated-by,type,container-title"})
    return web.get("https://api.crossref.org/works?" + q).get("message", {}).get("items", [])


def _openalex_search(web: Web, query: str) -> list[dict]:
    q = urllib.parse.urlencode({"search": query[:300], "per-page": 3, "select": "doi,title,publication_year"})
    return web.get("https://api.openalex.org/works?" + q).get("results", [])


def _arxiv(web: Web, arxiv_id: str) -> str | None:
    data = web.get("https://export.arxiv.org/api/query?id_list=" + arxiv_id)
    titles = re.findall(r"<title>([^<]+)</title>", data.get("_text", ""))
    entry = [t for t in titles[1:] if t.strip() != "Error"]
    return re.sub(r"\s+", " ", entry[0]).strip() if entry else None


def _handle_exists(web: Web, doi: str) -> bool:
    data = web.get("https://doi.org/api/handles/" + urllib.parse.quote(doi, safe="/()"))
    return data.get("responseCode") == 1


def _year(item: dict) -> str:
    parts = (item.get("issued") or {}).get("date-parts") or [[None]]
    return str(parts[0][0] or "")


def _notices(item: dict) -> list[tuple[str, str, str]]:
    return [(u.get("type", ""), u.get("DOI", ""), u.get("source", "")) for u in item.get("updated-by", []) or []]


def _finding(category: str, severity: str, entry: dict, why: str, fix: str) -> dict[str, Any]:
    raw = entry["raw"][:160]
    return {"category": category, "severity": severity,
            "target": raw if raw.startswith(entry["label"]) else f"{entry['label']} {raw}",
            "reasoning": why, "suggested_fix": fix, "numbers": [], "confidence": 0.8}


def verify(entry: dict, web: Web) -> dict[str, Any]:
    """{status, findings, matched}; status in verified, problem, not_found, unverifiable."""
    result: dict[str, Any] = {"status": "verified", "findings": [], "matched": None}
    item = None
    if entry["doi"]:
        item = _crossref_work(web, entry["doi"])
        if item is None:
            if _handle_exists(web, entry["doi"]):
                result["matched"] = {"doi": entry["doi"], "title": "", "year": ""}
                return result
            result["status"] = "problem"
            result["findings"].append(_finding(
                "reference_doi_unresolved", "major", entry,
                f"The DOI {entry['doi']} does not resolve: neither Crossref nor doi.org knows it.",
                "Correct the DOI from the publisher's page, or remove it if the work has none."))
            return result
        title = (item.get("title") or [""])[0]
        if entry["title"] and title and not _same_title(entry["title"], title) and not _title_in(title, entry["raw"]):
            result["status"] = "problem"
            result["findings"].append(_finding(
                "reference_doi_mismatch", "major", entry,
                f"The DOI {entry['doi']} belongs to a different work: \"{title}\".",
                "Use the DOI of the cited work, or cite the work this DOI identifies."))
    elif entry["arxiv"]:
        title = _arxiv(web, entry["arxiv"])
        if title is None:
            result["status"] = "problem"
            result["findings"].append(_finding(
                "reference_arxiv_unresolved", "major", entry,
                f"arXiv:{entry['arxiv']} does not exist.", "Correct the arXiv identifier."))
            return result
        if entry["title"] and not _same_title(entry["title"], title):
            result["status"] = "problem"
            result["findings"].append(_finding(
                "reference_arxiv_mismatch", "major", entry,
                f"arXiv:{entry['arxiv']} is \"{title}\", not the cited title.",
                "Use the identifier of the cited preprint."))
        result["matched"] = {"doi": "", "arxiv": entry["arxiv"], "title": title, "year": ""}
        return result
    else:
        probe = entry["title"] or entry["raw"]
        hits = [c for c in _crossref_search(web, entry["raw"] or probe)
                if (c.get("title") or [""])[0] and (_same_title(c["title"][0], entry["title"]) if entry["title"]
                                                    else _title_in(c["title"][0], entry["raw"]))]
        # same-title records (reprints, commentaries) exist; take the one whose year is closest
        hits.sort(key=lambda c: abs(int(_year(c) or 0) - int(entry["year"] or _year(c) or 0)))
        item = hits[0] if hits else None
        if item is None:
            for cand in _openalex_search(web, probe):
                t = cand.get("title") or ""
                if t and (_same_title(t, entry["title"]) if entry["title"] else _title_in(t, entry["raw"])):
                    result["matched"] = {"doi": (cand.get("doi") or "").replace("https://doi.org/", ""),
                                         "title": t, "year": str(cand.get("publication_year") or "")}
                    break
            if result["matched"] is None:
                if _CJK.search(entry["raw"]) or not entry["article"]:
                    result["status"] = "unverifiable"
                    result["reason"] = ("Chinese-language source; Crossref and OpenAlex index few of these"
                                        if _CJK.search(entry["raw"]) else
                                        "book, report or web page; not indexed as an article")
                    return result
                result["status"] = "not_found"
                result["findings"].append(_finding(
                    "reference_not_found", "major", entry,
                    "No work matching this reference is in Crossref, OpenAlex or arXiv. It may be mis-cited, "
                    "or it may not exist (language models invent plausible references).",
                    "Find the work and copy its details from the publisher's page; remove it if it cannot be found."))
                return result
            return result
    if item is not None:
        title = (item.get("title") or [""])[0]
        result["matched"] = {"doi": item.get("DOI", entry["doi"]), "title": title, "year": _year(item)}
        if entry["doi"] and entry["year"] and _year(item) and abs(int(entry["year"]) - int(_year(item))) > 1:
            result["findings"].append(_finding(
                "reference_year_mismatch", "minor", entry,
                f"The reference gives {entry['year']}; the record for this work says {_year(item)}.",
                f"Correct the year to {_year(item)} (or cite the version from {entry['year']} explicitly)."))
        for kind, notice, source in _notices(item):
            if kind in ("retraction", "withdrawal", "removal"):
                result["status"] = "problem"
                result["findings"].append(_finding(
                    "reference_retracted", "major", entry,
                    f"This work is registered as {kind.replace('_', ' ')} (notice https://doi.org/{notice}"
                    + (f", recorded by {source}" if source else "") + ").",
                    "Open the notice to confirm. Do not rely on a retracted work as evidence; if you discuss it, "
                    "say it was retracted."))
                break
            if kind == "expression_of_concern":
                result["findings"].append(_finding(
                    "reference_concern", "minor", entry,
                    f"An expression of concern is registered for this work (https://doi.org/{notice}).",
                    "Read the notice and say so if the cited result is affected."))
    return result


def _abstracts(web: Web, dois: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for i in range(0, len(dois), 40):
        chunk = [d.lower() for d in dois[i: i + 40] if d]
        if not chunk:
            continue
        q = urllib.parse.urlencode({"filter": "doi:" + "|".join(chunk), "per-page": 50,
                                    "select": "doi,abstract_inverted_index"})
        try:
            data = web.get("https://api.openalex.org/works?" + q)
        except Exception:  # noqa: BLE001 - abstracts are optional
            continue
        for w in data.get("results", []):
            inv = w.get("abstract_inverted_index") or {}
            words = sorted((p, word) for word, ps in inv.items() for p in ps)
            if words:
                out[(w.get("doi") or "").replace("https://doi.org/", "").lower()] = " ".join(x for _, x in words)[:1500]
    return out


def citing_sentences(text: str, entry: dict) -> list[str]:
    key = re.escape(entry["key"])
    if entry["label"].startswith("["):
        n = int(entry["key"])
        rx = re.compile(r"\[(\d{1,3}(?:\s*[,–\-]\s*\d{1,3})*)\]")
        hits = []
        for m in rx.finditer(text):
            nums = set()
            for part in m.group(1).split(","):
                b = [int(x) for x in re.split(r"\s*[–\-]\s*", part.strip()) if x]
                nums |= set(range(b[0], b[-1] + 1)) if len(b) == 2 and b[1] - b[0] < 50 else set(b)
            if n in nums:
                hits.append(m.start())
    else:
        hits = [m.start() for m in re.finditer(CITE_CMD + r"(?:\s*\[[^\]]*\]){0,2}\s*\{[^}]*\b" + key + r"\b", text)]
    out = []
    for h in hits[:3]:
        start = max(text.rfind(". ", 0, h), text.rfind("\n\n", 0, h), h - 300) + 1
        end = min([x for x in (text.find(". ", h), h + 300) if x > 0])
        out.append(re.sub(r"\s+", " ", text[start:end + 1]).strip())
    return out


def check(text: str, bib: str = "", web: Web | None = None, workers: int = 6) -> dict[str, Any]:
    entries = extract(text, bib)
    report: dict[str, Any] = {"total": len(entries), "items": [], "findings": [], "not_verified": []}
    if not entries:
        report["not_verified"].append({"item": "References", "reason": "no reference list was found"})
        return report
    web = web or Web()

    def one(entry: dict) -> dict:
        try:
            return verify(entry, web)
        except Exception as e:  # noqa: BLE001 - offline, rate-limited or malformed: unverifiable, never a finding
            return {"status": "unverifiable", "findings": [], "matched": None, "reason": f"lookup failed ({type(e).__name__})"}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, entries[:MAX_REFS]))
    dois = [r["matched"]["doi"] for r in results if r.get("matched") and r["matched"].get("doi")]
    abstracts = _abstracts(web, dois)
    for entry, res in zip(entries, results):
        doi = (res.get("matched") or {}).get("doi", "")
        report["items"].append({
            "label": entry["label"], "reference": entry["raw"][:300], "status": res["status"],
            "matched": res.get("matched"), "reason": res.get("reason", ""),
            "abstract": abstracts.get(doi.lower(), ""), "cited_in": citing_sentences(text, entry)})
        report["findings"] += res["findings"]
        if res["status"] == "unverifiable":
            report["not_verified"].append({"item": f"Reference {entry['label']}", "reason": res.get("reason", "")})
    if len(entries) > MAX_REFS:
        report["not_verified"].append({"item": f"References beyond the first {MAX_REFS}", "reason": "not looked up"})
    web.save()
    return report
