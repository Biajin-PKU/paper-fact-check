"""Which of the usual declarations a manuscript carries, with the sentence that carries each.

Presence only: whether a statement is required depends on the study and the venue.
"""
from __future__ import annotations

import re
from typing import Any

STATEMENTS = {
    "ethics_approval": r"ethic(?:s|al) (?:committee|approval|review board)|institutional review board|\bIRB\b|"
                       r"approved by the|animal care and use committee|\bIACUC\b|伦理(?:委员会|审查|批准)",
    "informed_consent": r"informed consent|consent (?:was|were) (?:obtained|waived)|waiver of consent|知情同意",
    "conflict_of_interest": r"competing interests?|conflicts? of interest|declaration of interests?|disclosures?|"
                            r"利益冲突",
    "funding": r"\bfunding\b|funded by|supported by (?:the |a )?(?:grant|national|natural)|grant (?:no|number)|"
               r"基金(?:项目|资助)?|资助",
    "data_availability": r"data availability|availability of data|data (?:are|is) (?:publicly )?available|"
                         r"data (?:sharing|access) statement|数据(?:可用性|获取|共享)",
    "code_availability": r"code availability|code (?:is|are) (?:publicly )?available|source code|github\.com|"
                         r"gitlab\.com|zenodo|代码(?:可用|获取|已公开)",
    "trial_registration": r"clinicaltrials\.gov|\bNCT\d{8}\b|\bChiCTR[\w\-]+|\bISRCTN\d+|\bPROSPERO\b|\bCRD\d{8,}|"
                          r"trial registration|registered (?:at|with|in)|注册号",
    "author_contributions": r"author contributions?|\bCRediT\b|contributed equally|作者贡献",
    "ai_use_disclosure": r"(?:generative|large language model|LLM|ChatGPT|GPT-\d|AI)[\w\s\-]{0,40}"
                         r"(?:was|were) used|use of (?:generative )?AI|AI[- ]assisted|人工智能(?:工具)?使用声明",
    "reporting_guideline": r"\b(?:CONSORT|STROBE|PRISMA|ARRIVE|STARD|TRIPOD|COREQ|SRQR|CHEERS|SPIRIT|CARE|"
                           r"MOOSE|SQUIRE|AGREE|RECORD|CLAIM)\b",
}
_RX = {k: re.compile(v, 0 if k == "reporting_guideline" else re.I) for k, v in STATEMENTS.items()}


def scan(text: str) -> list[dict[str, Any]]:
    flat = re.sub(r"\s+", " ", re.sub(r"\\%", "%", text))
    out = []
    for name, rx in _RX.items():
        m = rx.search(flat)
        quote = flat[max(0, m.start() - 80): m.end() + 120].strip() if m else ""
        out.append({"statement": name, "found": bool(m), "quote": quote})
    return out


def demo() -> None:
    text = ("The study was approved by the ethics committee of X Hospital (No. 2021-01). Written informed "
            "consent was obtained. Funding: National Natural Science Foundation of China. "
            "Trial registration: NCT01234567. 作者声明无利益冲突。")
    found = {s["statement"] for s in scan(text) if s["found"]}
    assert found == {"ethics_approval", "informed_consent", "funding", "trial_registration",
                     "conflict_of_interest"}, found


if __name__ == "__main__":
    demo()
    print("ok")
