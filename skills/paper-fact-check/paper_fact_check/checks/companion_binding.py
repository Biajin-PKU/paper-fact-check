"""Released results that no shipped test reads.

A file under results/ that no file under tests/ names can drift from the paper, or from the code,
while every test still passes. A results file is bound when a test names it, names its stem, or
carries a glob that matches it. Only unbound files whose values the paper prints beyond chance are
reported: the same match is repeated with every printed value moved one unit in its last place, and
the real count must be at least twice that and at least 2 more. A package with no tests/ directory
is skipped. A test that names a file and asserts nothing about it is not caught here.

    python3 -m paper_fact_check.checks.companion_binding <package-dir> <main.tex>
"""
from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path
from typing import Any

from ._common import body_text, objection
from .number_agreement import _decimals

_GLOB = re.compile(r"""["']([^"'\n]*\*[^"'\n]*)["']""")
_FLOAT = re.compile(r"-?\d+\.\d+(?:[eE][-+]?\d+)?")
_TEXT_SUFFIXES = {".csv", ".tsv", ".json", ".txt"}
_MAX_BYTES = 5_000_000


def printed(tex: str) -> set[str]:
    """Decimals the manuscript prints with 3+ significant digits."""
    return {d.lstrip("+") for d in _decimals(body_text(tex))
            if "." in d and len(d.replace("-", "").replace(".", "").lstrip("0")) >= 3}


def shared_values(path: Path, values: set[str]) -> list[str]:
    """The printed values a results file holds at the manuscript's precision."""
    if path.suffix.casefold() not in _TEXT_SUFFIXES or path.stat().st_size > _MAX_BYTES:
        return []
    floats = [float(x) for x in _FLOAT.findall(path.read_text(encoding="utf-8", errors="replace"))]
    by_places: dict[int, set[str]] = {}
    out = []
    for value in sorted(values):
        places = len(value.split(".")[1])
        if places not in by_places:
            by_places[places] = {f"{f:.{places}f}" for f in floats}
        if value in by_places[places] or f"{-float(value):.{places}f}" in by_places[places] and value.startswith("-"):
            out.append(value)
    return out


def _shift(value: str, step: int) -> str:
    places = len(value.split(".")[1])
    return f"{float(value) + step * 10 ** -places:.{places}f}"


def quoted(path: Path, values: set[str]) -> list[str]:
    """Printed values the file holds, if it holds them beyond chance; else []."""
    shared = shared_values(path, values)
    chance = max(len(shared_values(path, {_shift(v, k) for v in values} - values)) for k in (-1, 1))
    return shared if len(shared) >= max(2 * chance, chance + 2) else []


def unbound(companion: Path) -> list[str]:
    results, tests = companion / "results", companion / "tests"
    if not results.is_dir() or not tests.is_dir():
        return []
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(tests.rglob("*")) if p.is_file() and p.suffix in {".py", ".R", ".r", ".sh", ".jl"})
    globs = [g.rsplit("/", 1)[-1] for g in _GLOB.findall(text)]
    out = []
    for path in sorted(p for p in results.rglob("*") if p.is_file() and not p.name.startswith(".")):
        name = path.name
        if name in text or path.stem in text or any(fnmatch.fnmatch(name, g) for g in globs):
            continue
        out.append(path.relative_to(companion).as_posix())
    return out


def run(companion: Path, tex: str) -> list[dict[str, Any]]:
    companion, values, out = Path(companion), printed(tex), []
    for rel in unbound(companion):
        shared = quoted(companion / rel, values)
        if not shared:
            continue
        out.append(objection(
            "unbound_released_record", "minor", rel,
            f"The manuscript prints {len(shared)} values held in {rel} ({', '.join(shared[:6])}"
            f"{' ...' if len(shared) > 6 else ''}), and no shipped test names that file: the page and "
            f"the file can drift apart while every test still passes.",
            "Add a test that regenerates the file from code/ and data/, or that reads it and checks the "
            "values the manuscript prints.",
            numbers=[], confidence=0.8))  # about a file, not these numbers
    return out


def demo() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        c = Path(tmp)
        (c / "results").mkdir()
        (c / "tests").mkdir()
        for name in ("TAB1_cohort.csv", "TAB2_auc.csv", "FIG4_dca.csv", "fig_records.json", "deciles.csv"):
            (c / "results" / name).write_text("x")
        (c / "results" / "FIG4_dca.csv").write_text("t,nb\n0.2331,0.05330\n0.4504,0.03003\n")
        # every 3-decimal value in 0.000-0.999: holds the page's numbers by chance only
        (c / "results" / "deciles.csv").write_text("\n".join(f"{i / 1000:.3f}" for i in range(1000)))
        tex = r"\begin{document}Net benefit 0.0533 at 0.450 and 0.0300 at 0.233 (two digits: 0.05).\end{document}"
        (c / "tests" / "test_tables.py").write_text(
            'read("results/TAB1_cohort.csv")\nload("TAB2_auc")\nfor p in glob("results/fig_*.json"): pass\n')
        assert unbound(c) == ["results/FIG4_dca.csv", "results/deciles.csv"], unbound(c)
        hits = run(c, tex)
        assert [h["target"] for h in hits] == ["results/FIG4_dca.csv"], hits  # deciles.csv matches only by chance
        assert "prints 4 values" in hits[0]["reasoning"], hits[0]["reasoning"]
        (c / "tests" / "test_tables.py").unlink()
        (c / "tests").rmdir()
        assert run(c, tex) == []


if __name__ == "__main__":
    if len(sys.argv) > 2:
        from .number_agreement import read_tree
        for hit in run(Path(sys.argv[1]), read_tree(Path(sys.argv[2]))):
            print(hit["reasoning"])
    else:
        demo()
        print("ok")
