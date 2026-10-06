"""Self-checks: python3 tests/test_paperfactcheck.py (also runs under pytest). No network."""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "paperfactcheck"))

from paperfactcheck import checks, mcp, references  # noqa: E402
from paperfactcheck.checks import (citation_xref, claim_interval, companion_binding, constructed_data,  # noqa: E402
                                   figure_panels, grimmer, number_agreement, relative_change, stat_recompute,
                                   statements, text_hygiene)
from paperfactcheck.cli import main, run_checks  # noqa: E402
from paperfactcheck.readers import load  # noqa: E402
from paperfactcheck.report import render  # noqa: E402

assert checks is not None


def _categories(path: Path, **kw) -> set:
    return {f["category"] for f in run_checks(load(path), offline=True, **kw)["findings"]}


def test_module_self_checks():
    for module in (citation_xref, claim_interval, companion_binding, constructed_data, figure_panels, grimmer,
                   number_agreement, relative_change, stat_recompute, statements, text_hygiene):
        module.demo()


def test_english_latex_demo():
    assert _categories(ROOT / "examples" / "demo" / "main.tex") == {
        "grim_infeasible_mean", "pvalue_recompute_mismatch", "prose_table_number_disagreement",
        "directional_claim_against_interval", "panel_reference_beyond_caption", "constructed_series_json",
        "unbound_released_record"}


def test_chinese_markdown_demo():
    assert _categories(ROOT / "examples" / "demo-zh" / "manuscript.md") == {
        "prose_table_number_disagreement", "relative_change_mismatch", "percent_count_mismatch",
        "pvalue_recompute_mismatch", "interval_p_contradiction", "directional_claim_against_interval",
        "reference_never_cited", "assistant_residue"}


def _docx(path: Path) -> None:
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

    def p(text):
        return f"<w:p><w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"

    def row(*cells):
        return "<w:tr>" + "".join(f"<w:tc>{p(c)}</w:tc>" for c in cells) + "</w:tr>"
    body = (p("Our model reached an accuracy of 0.847 on the test set (Table 1).")
            + p("Table 1. Main results.")
            + f"<w:tbl>{row('Method', 'Accuracy')}{row('Our model', '0.851')}{row('Baseline', '0.812')}</w:tbl>"
            + p("Of the patients, 45/192 (25.4%) relapsed."))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document {w}><w:body>{body}</w:body></w:document>")


def test_word_reader_tables_and_percent():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "paper.docx"
        _docx(path)
        doc = load(path)
        assert "\\begin{tabular}" in doc.text and "25.4\\%" in doc.text
        cats = {f["category"] for f in run_checks(doc, offline=True)["findings"]}
        assert {"prose_table_number_disagreement", "percent_count_mismatch"} <= cats, cats


def test_render_merges_review():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "r"
        assert main(["check", str(ROOT / "examples" / "demo" / "main.tex"), "--out", str(out), "--offline"]) == 1
        found = json.loads((out / "findings.json").read_text())["findings"]
        review = {"summary": "Two numbers need correcting.", "dismissed": [{"id": found[0]["id"], "reason": "misread"}],
                  "edits": {found[1]["id"]: {"calculation": "1 + 1 = 2"}},
                  "findings": [{"title": "Causal wording", "group": "claims", "severity": "major", "order": "first",
                                "quote": "X causes Y", "evidence": "observational", "fix": "X is associated with Y"}]}
        (out / "review.json").write_text(json.dumps(review))
        render(out)
        html = (out / "report.html").read_text()
        assert "Two numbers need correcting." in html and "1 + 1 = 2" in html and "Causal wording" in html
        assert "misread" in html and 'id="R1"' in html


def test_reference_verdicts_without_network():
    records = {
        "https://api.crossref.org/works/10.1000/real": {"message": {
            "DOI": "10.1000/real", "title": ["Deep residual learning for image recognition"],
            "issued": {"date-parts": [[2016]]}}},
        "https://api.crossref.org/works/10.1000/retracted": {"message": {
            "DOI": "10.1000/retracted", "title": ["A retracted result"], "issued": {"date-parts": [[2002]]},
            "updated-by": [{"type": "retraction", "DOI": "10.1000/notice", "source": "retraction-watch"}]}},
    }

    def fetch(url):
        if url in records:
            return records[url]
        if "doi.org/api/handles" in url:
            return {"responseCode": 100}
        if "api.crossref.org/works/" in url:
            return {"_status": 404}
        if "crossref.org/works?" in url:
            return {"message": {"items": []}}
        if "openalex" in url:
            return {"results": []}
        return {"_text": ""}

    bib = ("@article{a, title={Deep Residual Learning for Image Recognition}, journal={CVPR}, year={2016}, doi={10.1000/real}}\n"
           "@article{b, title={Something else entirely about birds}, journal={J}, year={2016}, doi={10.1000/real}}\n"
           "@article{c, title={A retracted result}, journal={Nature}, year={2002}, doi={10.1000/retracted}}\n"
           "@article{d, title={Quantum attention for lunar crop yields}, journal={Nature Agriculture}, year={2023}}\n"
           "@article{e, title={Missing DOI}, journal={J}, year={2020}, doi={10.1000/nothing}}\n")
    rep = references.check(r"\begin{document}\cite{a,b,c,d,e}\end{document}", bib,
                           web=references.Web(fetch=fetch, cache=None), workers=1)
    status = {i["label"]: i["status"] for i in rep["items"]}
    assert status == {"a": "verified", "b": "problem", "c": "problem", "d": "not_found", "e": "problem"}, status
    cats = sorted(f["category"] for f in rep["findings"])
    assert cats == ["reference_doi_mismatch", "reference_doi_unresolved", "reference_not_found",
                    "reference_retracted"], cats
    assert references.guess_title("[5] Lundberg SM, Lee SI. A unified approach to interpreting model predictions. "
                                  "Adv Neural Inf Process Syst. 2017;30.") == \
        "A unified approach to interpreting model predictions"


def test_mcp_handshake():
    init = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    assert init["result"]["serverInfo"]["name"] == "paperfactcheck"
    tools = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in tools} == {"check_paper", "render_report"}
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
