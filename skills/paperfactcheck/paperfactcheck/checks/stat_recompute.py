"""Recompute reported test results from their own statistics, stdlib only.

- t(df), F(df1, df2), chi2(df), r(df) and z results whose printed p does not follow from the
  statistic and its degrees of freedom, allowing for the statistic's rounding. A mismatch that moves
  the result across 0.05 is major; any other is minor. One-sided and corrected tests are skipped.
- An estimate with a 95% interval and a p-value that disagree on significance.
- A point estimate outside its own interval.
- A partial eta squared that F(df1, df2) does not give.
"""
from __future__ import annotations

import math
import re
from typing import Any

from ._common import objection

# --- distributions -------------------------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz)."""
    tiny, qab, qap, qam = 1e-300, a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def gammaincc(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x)."""
    if x <= 0.0:
        return 1.0
    gln = math.lgamma(a)
    if x < a + 1.0:  # series for P, then Q = 1 - P
        term = total = 1.0 / a
        ap = a
        for _ in range(1000):
            ap += 1.0
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-14:
                break
        return 1.0 - total * math.exp(-x + a * math.log(x) - gln)
    tiny = 1e-300
    b = x + 1.0 - a
    c, d = 1.0 / tiny, 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = b + an / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def p_from(test: str, stat: float, df1: float | None, df2: float | None) -> float:
    """Two-sided p for t, r and z; upper-tail p for F and chi2."""
    if test == "z":
        return math.erfc(abs(stat) / math.sqrt(2.0))
    if test == "t":
        return betainc(df1 / 2.0, 0.5, df1 / (df1 + stat * stat))
    if test == "r":
        if abs(stat) >= 1:
            return 0.0
        t = stat * math.sqrt(df1 / (1.0 - stat * stat))
        return betainc(df1 / 2.0, 0.5, df1 / (df1 + t * t))
    if test == "F":
        return betainc(df2 / 2.0, df1 / 2.0, df2 / (df2 + df1 * stat)) if stat > 0 else 1.0
    if test == "chi2":
        return gammaincc(df1 / 2.0, stat / 2.0) if stat > 0 else 1.0
    raise ValueError(test)


# --- text ----------------------------------------------------------------------------------------

_SENTENCE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z(\[\u4e00-\u9fff])|(?<=[。！？；])")
_SKIP = re.compile(r"one[- ]?(?:tailed|sided)|single[- ]tailed|directional test|bonferroni|holm|"
                   r"benjamini|false discovery|\bFDR\b|corrected|adjusted p|p_?adj|单侧|校正", re.I)


def plain(text: str) -> str:
    """Strip LaTeX math decoration so 't(28) = 2.10, p = .045' reads the same however it was typeset."""
    s = re.sub(r"\\(?:chi|mathcal\{X\})\s*\^?\s*\{?2\}?|χ\s*\^?\s*\{?2\}?|χ²|\\chi\^2|chi-?squared?", " chi2", text)
    s = re.sub(r"\\eta\s*_\s*\{?p\}?\s*\^\s*\{?2\}?|η\s*_?p\s*\^?\s*2|η[pP]²|ηp2|partial\s+(?:\\eta|η)\s*\^?\s*\{?2\}?|"
               r"partial eta[- ]squared", " etap2 ", s)
    s = re.sub(r"\\eta\s*\^\s*\{?2\}?|η²|η\^2|eta[- ]squared", " eta2 ", s)
    s = re.sub(r"\\(?:textminus|minus)\b|−|–|—|\\text(?:endash|emdash)\b|--", "-", s)
    s = re.sub(r"\\(?:le|leq)\b|≤", "<", s)
    s = re.sub(r"\\(?:ge|geq)\b|≥", ">", s)
    s = re.sub(r"\\(?:mathit|mathrm|textit|emph|text|mathbf|textbf)\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"(?<=\d)\s*~\s*(?=-?\d)", " to ", s)
    s = re.sub(r"\\[,;!: ]|\\%|[${}~]", " ", s)
    s = re.sub(r"(?<=\d)\s*,\s*(?=\d{3}\b)", "", s)  # 1,024 -> 1024
    return re.sub(r"\s+", " ", s)


_N = r"(-?\d*\.?\d+)"
_PV = r"\b[pP]\s*(=|<|>)\s*(0?\.\d+|1(?:\.0+)?|0)\b"
_RESULT = re.compile(
    r"(?<![A-Za-z])(?:(?P<t>t)\s*\(\s*(?P<tdf>\d+(?:\.\d+)?)\s*\)"
    r"|(?P<F>F)\s*\(\s*(?P<fdf1>\d+(?:\.\d+)?)\s*,\s*(?P<fdf2>\d+(?:\.\d+)?)\s*\)"
    r"|(?P<chi2>chi2)\s*\(\s*(?P<cdf>\d+)\s*(?:,\s*[Nn]\s*=\s*\d+\s*)?\)"
    r"|(?P<r>r)\s*\(\s*(?P<rdf>\d+)\s*\)"
    r"|(?P<z>[zZ])|(?P<tn>t))\s*=\s*" + _N + r"\s*[,;]?\s*(?:\S+\s*){0,3}?" + _PV)


def _places(token: str) -> int:
    return len(token.split(".")[1]) if "." in token else 0


def _half_ulp(token: str) -> float:
    return 0.5 * 10 ** -_places(token)


def _p_range(test: str, stat_txt: str, df1: float | None, df2: float | None) -> tuple[float, float]:
    """The p-values the printed statistic can give once its rounding is undone."""
    x, h = abs(float(stat_txt)), _half_ulp(stat_txt)
    lo, hi = max(x - h, 0.0), x + h
    if test == "r":
        hi = min(hi, 0.999999)
    a, b = p_from(test, lo, df1, df2), p_from(test, hi, df1, df2)
    return min(a, b), max(a, b)


def _fmt(p: float) -> str:
    return "< .001" if p < 0.001 else f"{p:.3f}".lstrip("0")


def detect_pvalue_recompute(text: str, alpha: float = 0.05) -> list[dict[str, Any]]:
    out = []
    for sentence in _SENTENCE.split(plain(text)):
        if _SKIP.search(sentence):
            continue
        for m in _RESULT.finditer(sentence):
            stat_txt, op, p_txt = m.group(m.lastindex - 2), m.group(m.lastindex - 1), m.group(m.lastindex)
            if m.group("t"):
                test, df1, df2, label = "t", float(m.group("tdf")), None, f"t({m.group('tdf')})"
            elif m.group("F"):
                test, df1, df2 = "F", float(m.group("fdf1")), float(m.group("fdf2"))
                label = f"F({m.group('fdf1')}, {m.group('fdf2')})"
            elif m.group("chi2"):
                test, df1, df2, label = "chi2", float(m.group("cdf")), None, f"chi2({m.group('cdf')})"
            elif m.group("r"):
                test, df1, df2, label = "r", float(m.group("rdf")), None, f"r({m.group('rdf')})"
            elif m.group("z"):
                test, df1, df2, label = "z", None, None, "z"
            else:
                # t without degrees of freedom: no t distribution gives a p below the normal one
                floor = p_from("z", abs(float(stat_txt)) + _half_ulp(stat_txt), None, None)
                p = float(p_txt)
                if op != ">" and 0 < p and math.log10(floor) - math.log10(p + _half_ulp(p_txt)) > 0.3:
                    out.append(objection(
                        "pvalue_recompute_mismatch", "major" if floor >= alpha > p else "minor",
                        m.group(0).strip()[:120],
                        f"t = {stat_txt} cannot give p {op} {p_txt}: whatever the degrees of freedom, its two-sided "
                        f"p is at least {_fmt(floor)}." + (f" The result is not significant at {alpha:g}."
                                                            if floor >= alpha > p else ""),
                        "Recompute p from t and its degrees of freedom, and report the degrees of freedom.",
                        numbers=[p_txt, stat_txt], confidence=0.85))
                continue
            if (df1 is not None and df1 <= 0) or (df2 is not None and df2 <= 0):
                continue
            p = float(p_txt)
            p_lo, p_hi = _p_range(test, stat_txt, df1, df2)
            if op == "=":
                h = _half_ulp(p_txt)
                ok = p_lo <= p + h and p_hi >= p - h
                reported_sig = p < alpha
            elif op == "<":
                ok = p_lo < p
                reported_sig = p <= alpha
            else:
                ok = p_hi > p
                reported_sig = False
            if ok:
                continue
            computed_sig = p_hi < alpha
            flips = reported_sig != computed_sig and (p_lo >= alpha or p_hi < alpha)
            mid = p_from(test, abs(float(stat_txt)), df1, df2)
            out.append(objection(
                "pvalue_recompute_mismatch", "major" if flips else "minor", m.group(0).strip()[:120],
                f"{label} = {stat_txt} gives p {_fmt(mid)}" + (" (two-sided)" if test in ("t", "r", "z") else "")
                + f", not p {op} {p_txt}." + (" The recomputed value is on the other side of "
                                               f"{alpha:g}, so the significance claim changes." if flips else ""),
                f"Report p {('= ' + _fmt(mid)) if mid >= 0.001 else '< .001'} for {label} = {stat_txt}, or correct "
                "the statistic or its degrees of freedom; state it if the test was one-sided or corrected.",
                numbers=[p_txt, stat_txt], confidence=0.85 if flips else 0.7))
    return out


# --- intervals -----------------------------------------------------------------------------------

_RATIO = r"(?:a?OR|a?HR|a?RR|IRR|SHR|odds ratio|hazard ratio|risk ratio|relative risk|rate ratio)"
_DIFF = r"(?:MD|SMD|mean difference|difference|β|\\beta|beta|\bB\b|\bb\b|coefficient|estimate|effect)"
_EST = re.compile(
    r"(?P<kind>" + _RATIO + "|" + _DIFF + r")\s*(?:\w+\s*){0,3}?(?:=|:|was|of|,)?\s*" + _N +
    r"\s*[,;(\[]?\s*(?:95\s*%?\s*)?(?:CI|confidence interval|credible interval)\s*[:=,]?\s*\[?\(?\s*" + _N +
    r"\s*(?:,|to|-|~)\s*" + _N + r"\s*[)\]]?\s*[,;)]?\s*(?:\S+\s*){0,2}?(?:" + _PV + ")?", re.I)
_RATIO_RE = re.compile(_RATIO, re.I)


def detect_interval_findings(text: str, alpha: float = 0.05) -> list[dict[str, Any]]:
    out = []
    for sentence in _SENTENCE.split(plain(text)):
        if _SKIP.search(sentence):
            continue
        for m in _EST.finditer(sentence):
            est_txt, lo_txt, hi_txt = m.group(2), m.group(3), m.group(4)
            est, lo, hi = float(est_txt), float(lo_txt), float(hi_txt)
            if lo > hi:
                continue
            ratio = bool(_RATIO_RE.fullmatch(m.group("kind").strip()))
            if ratio and (lo <= 0 or est <= 0):
                continue
            slack = max(_half_ulp(lo_txt), _half_ulp(hi_txt), _half_ulp(est_txt))
            where = m.group(0).strip()[:120]
            if est < lo - slack or est > hi + slack:
                out.append(objection(
                    "estimate_outside_interval", "major", where,
                    f"The estimate {est_txt} lies outside its own interval {lo_txt} to {hi_txt}.",
                    "Check which of the three numbers was mistyped; an estimate always lies inside its interval.",
                    numbers=[est_txt, lo_txt, hi_txt], confidence=0.85))
                continue
            if not m.group(5):
                continue
            op, p_txt = m.group(5), m.group(6)
            p = float(p_txt)
            null = 1.0 if ratio else 0.0
            excludes = lo - slack > null or hi + slack < null
            includes = lo + slack < null < hi - slack
            p_sig = (op == "=" and p < alpha) or (op == "<" and p <= alpha)
            p_nonsig = (op == "=" and p > alpha) or op == ">"
            if (excludes and p_nonsig) or (includes and p_sig):
                side = "excludes" if excludes else "includes"
                out.append(objection(
                    "interval_p_contradiction", "major", where,
                    f"The interval {lo_txt} to {hi_txt} {side} the null value {null:g}, but p {op} {p_txt} "
                    f"says the opposite at {alpha:g}. A 95% interval and a two-sided p from the same estimate "
                    "agree on significance.",
                    "Recheck the interval and the p-value against the analysis output and correct the one "
                    "that is wrong; if they come from different models, say so.",
                    numbers=[lo_txt, hi_txt, p_txt], confidence=0.75))
    return out


# --- effect sizes --------------------------------------------------------------------------------

_ETA = re.compile(r"F\s*\(\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)\s*=\s*(\d*\.?\d+).{0,60}?"
                  r"\b(etap2|eta2)\s*=\s*(0?\.\d+)")


def detect_effect_size(text: str) -> list[dict[str, Any]]:
    out = []
    for sentence in _SENTENCE.split(plain(text)):
        for m in _ETA.finditer(sentence):
            df1, df2, f_txt, kind, e_txt = float(m.group(1)), float(m.group(2)), m.group(3), m.group(4), m.group(5)
            f_lo, f_hi = max(float(f_txt) - _half_ulp(f_txt), 0.0), float(f_txt) + _half_ulp(f_txt)
            lo, hi = (f * df1 / (f * df1 + df2) for f in (f_lo, f_hi))
            e, h = float(e_txt), _half_ulp(e_txt)
            # Plain eta squared is at most the partial one; only an exact partial value can be checked both ways.
            bad = (e - h > hi) if kind == "eta2" else (e - h > hi or e + h < lo)
            if bad:
                calc = float(f_txt) * df1 / (float(f_txt) * df1 + df2)
                name = "partial eta squared" if kind == "etap2" else "eta squared"
                out.append(objection(
                    "effect_size_mismatch", "minor", m.group(0).strip()[:120],
                    f"F({m.group(1)}, {m.group(2)}) = {f_txt} gives a partial eta squared of {calc:.3f}; the "
                    f"reported {name} is {e_txt}" + (", larger than the partial value can be." if kind == "eta2" else "."),
                    f"Report {name} = {calc:.2f}, or correct F or its degrees of freedom.",
                    numbers=[e_txt, f_txt], confidence=0.7))
    return out


def run(text: str) -> list[dict[str, Any]]:
    return detect_pvalue_recompute(text) + detect_interval_findings(text) + detect_effect_size(text)


def demo() -> None:
    # distributions against known values
    assert abs(p_from("t", 2.048, 28, None) - 0.05) < 1e-3
    assert abs(p_from("F", 4.20, 1, 28) - 0.0499) < 2e-3
    assert abs(p_from("chi2", 3.841, 1, None) - 0.05) < 1e-3
    assert abs(p_from("chi2", 11.07, 5, None) - 0.05) < 1e-3
    assert abs(p_from("r", 0.361, 28, None) - 0.05) < 2e-3
    assert abs(p_from("z", 1.96, None, None) - 0.05) < 1e-3
    bad = (r"The groups differed, $t(28) = 1.20$, $p = .03$. "
           r"Accuracy improved, F(1, 40) = 2.10, p < .05. "
           r"The effect was small, \chi^2(2) = 7.30, p = .06. "
           r"Reaction times differed, t(28) = 2.20, p = .041. "
           r"Mortality was lower (HR 0.75, 95% CI 0.80-0.94; P = 0.01). "
           r"Risk rose (OR = 1.40, 95% CI 0.90 to 2.10, p = .003). "
           r"Scores rose with training, F(2, 57) = 8.40, p < .001, $\eta_p^2 = .40$.")
    cats = sorted(f["category"] for f in run(bad))
    assert cats == ["effect_size_mismatch", "estimate_outside_interval", "interval_p_contradiction",
                    "pvalue_recompute_mismatch", "pvalue_recompute_mismatch", "pvalue_recompute_mismatch",
                    "pvalue_recompute_mismatch"], cats
    hit = detect_pvalue_recompute("The difference was significant (t = 1.20, p = 0.003).")
    assert hit and hit[0]["severity"] == "major", hit
    assert detect_pvalue_recompute("差异有统计学意义（t = 2.31, P = 0.023）。") == []
    sev = {f["target"][:9]: f["severity"] for f in run(bad) if f["category"] == "pvalue_recompute_mismatch"}
    assert sev["t(28) = 1"] == "major" and sev["t(28) = 2"] == "minor", sev
    good = ("The groups differed, t(28) = 2.20, p = .036. Accuracy improved, F(1, 40) = 5.10, p = .03. "
            "The association held, chi2(1) = 3.84, p = .05. A one-tailed test gave t(20) = 1.80, p = .04. "
            "Mortality was lower (HR 0.75, 95% CI 0.60-0.94; P = 0.01). "
            "Scores rose with training, F(2, 57) = 8.40, p < .001, partial eta squared = .23. "
            "两组差异有统计学意义，t(58) = 2.50，P = 0.015。")
    assert run(good) == [], run(good)


if __name__ == "__main__":
    demo()
    print("ok")
