#!/usr/bin/env python3
"""Signatures of constructed numbers in a released code/data package.

- Arithmetic grids in JSON results: per-horizon or per-setting scores that step by an exact
  constant (0.012, 0.016, 0.020, 0.024). Measured scores do not land on a lattice.
- Back-solved means: several fine-grained columns whose per-seed values average exactly onto the
  published rounding. Independent runs do not; values drawn to hit a target do.
- Scores solved from the answer: a function that takes the true labels together with the metric
  value to reach, or loops a label-scored metric toward a value it was handed.

    python3 -m paperfactcheck.checks.constructed_data <package-dir>
"""
from __future__ import annotations

import argparse
import ast
import collections
import csv
import json
import re
import statistics
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterator

# Integers are seeds, epochs, counts and indices: they are meant to be regular,
# so they are neither series nor grouping keys.
_MIN_GROUP = 5
_MIN_SERIES = 4
_VALUE_PRECISION = 5  # a mean is only "coarser than its values" if the values are fine
_MEAN_PRECISION = 3
_MIN_FLAGGED_COLUMNS = 2


def _decimals(text: str) -> int:
    text = text.strip()
    return len(text.split(".")[1]) if "." in text else 0


def _is_decimal(text: str | None) -> bool:
    return bool(text) and "." in text.strip() and _replaceable(text)


def _replaceable(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


# --------------------------------------------------------------- back-solved mean
def back_solved_means(root: Path) -> list[dict[str, Any]]:
    """Columns whose group mean lands exactly on the published rounding."""
    out: list[dict[str, Any]] = []
    for path in sorted(Path(root).rglob("*.csv")):
        try:
            rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
        except (OSError, csv.Error, UnicodeDecodeError):
            continue
        if len(rows) < _MIN_GROUP or not rows[0]:
            continue
        columns = list(rows[0])
        numeric = [c for c in columns if all(_is_decimal(r.get(c)) for r in rows)]
        labels = [
            c
            for c in columns
            if c not in numeric
            and not all((r.get(c) or "").strip().lstrip("-").isdigit() for r in rows)
        ]
        groups: dict[tuple, list[dict]] = collections.defaultdict(list)
        for row in rows:
            groups[tuple((row.get(c) or "") for c in labels)].append(row)

        flagged: dict[str, tuple[str, float]] = {}
        for key, members in groups.items():
            if len(members) < _MIN_GROUP:
                continue
            for column in numeric:
                values = [(m[column] or "").strip() for m in members]
                floats = [float(v) for v in values]
                # A constant column is a fact about the run, not a back-solve.
                if statistics.pstdev(floats) == 0:
                    continue
                if max(_decimals(v) for v in values) < _VALUE_PRECISION:
                    continue
                mean = sum(Fraction(v) for v in values) / len(values)
                exact = [
                    d
                    for d in range(_MEAN_PRECISION + 1)
                    if mean == Fraction(str(round(float(mean), d)))
                ]
                if exact:
                    where = "/".join(k for k in key if k) or path.stem
                    flagged.setdefault(column, (where, float(mean)))
        if len(flagged) >= _MIN_FLAGGED_COLUMNS:
            detail = ", ".join(
                f"'{c}' for {w} means exactly {m:g}" for c, (w, m) in sorted(flagged.items())
            )
            out.append(
                {
                    "gate": "companion:back_solved_mean",
                    "severity": "blocking",
                    "file": path.name,
                    "message": (
                        f"{path.name}: {len(flagged)} columns average onto the published "
                        f"rounding while their own values carry "
                        f"{_VALUE_PRECISION}+ decimals — {detail}. Independent runs do not "
                        "land there. Ask for the per-run logs these rows came from."
                    ),
                }
            )
    return out


# ------------------------------------------------------------------- json grids
def _numeric_series(node: Any, trail: str) -> Iterator[tuple[str, list[float]]]:
    """Every list-of-numbers and dict-of-numbers reachable in a JSON document."""
    if isinstance(node, dict):
        values = list(node.values())
        if len(values) >= _MIN_SERIES and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            yield trail or "<root>", [float(v) for v in values]
        for key, value in node.items():
            yield from _numeric_series(value, f"{trail}.{key}" if trail else str(key))
    elif isinstance(node, list):
        if len(node) >= _MIN_SERIES and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in node):
            yield trail or "<root>", [float(v) for v in node]
        for i, value in enumerate(node):
            yield from _numeric_series(value, f"{trail}[{i}]")


def json_constructed_series(root: Path) -> list[dict[str, Any]]:
    """Arithmetic sequences inside released JSON."""
    out: list[dict[str, Any]] = []
    for path in sorted(Path(root).rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        for trail, values in _numeric_series(doc, ""):
            # Integers are seeds, epochs, counts
            # and indices, and those are supposed to be evenly spaced.
            if all(float(v).is_integer() for v in values):
                continue
            spread = max(values) - min(values)
            if spread <= 0:
                continue
            steps = [b - a for a, b in zip(values, values[1:])]
            if max(steps) - min(steps) > spread * 1e-6:
                continue
            out.append(
                {
                    "gate": "companion:constructed_series_json",
                    "severity": "blocking",
                    "file": path.name,
                    "message": (
                        f"{path.name}: '{trail}' is an arithmetic sequence — "
                        f"{len(values)} values a constant {steps[0]:.6g} apart. "
                        "Independent measurements do not vary that way. Ask how each value "
                        "was measured, and for the raw outputs behind it."
                    ),
                }
            )
    return out


# A scorer may take the labels (to evaluate) or a target (to stop training). Taking BOTH, in one
# function, is how a number is solved for rather than measured: npj-suonr's
# `rank_scores(y, target_auroc, seed)` bisection-shifted the positives of the real label vector
# until `roc_auc_score` returned the 0.81 its design had declared, while the three genuine
# baselines in the same table sat at 0.4977/0.5219/0.6113. The values that come out are perfectly
# ordinary, so neither the grid check nor the back-solved mean above can see it -- the signature
# is in the producer, not the product.
_LABEL_PARAM = re.compile(r"^(y|y_true|y_obs|labels?|targets?|outcomes?|events?)$")
_TARGET_METRIC_PARAM = re.compile(
    r"target_(auroc|auc|auprc|accuracy|acc|f1|r2|c_index|cindex|score|metric|value)"
    r"|(auroc|auc|auprc|accuracy|f1|r2|c_index|cindex)_target"
    r"|desired_(auroc|auc|score|metric)"
)


# The name check reads what a producer calls its arguments; renaming `target_auroc` to `goal` gets
# past it, and SUONR's own bisection helper `_shift_for_auroc(y, z, target, pos)` did. The shape
# does not rename: inside a loop, a metric is scored on labels the function received, and the
# score is compared against a value the function also received -- a search for a supplied number.
# Early stopping compares to a local best-so-far, not to a parameter, and is not this shape.
_METRIC_CALLS = frozenset({
    "roc_auc_score", "average_precision_score", "f1_score", "accuracy_score", "r2_score",
    "concordance_index", "auc", "balanced_accuracy_score", "matthews_corrcoef",
    "brier_score_loss", "log_loss", "net_benefit",
})


def _call_name(call: ast.Call) -> str | None:
    func = call.func
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)


def _solves_for_parameter(function: ast.FunctionDef | ast.AsyncFunctionDef, params: set[str]) -> list[str]:
    """Parameters a loop drives a label-scored metric toward; empty when there are none."""
    targets: list[str] = []
    for loop in ast.walk(function):
        if not isinstance(loop, (ast.For, ast.While)):
            continue
        scored = [n for n in ast.walk(loop) if isinstance(n, ast.Call) and _call_name(n) in _METRIC_CALLS
                  and n.args and isinstance(n.args[0], ast.Name) and n.args[0].id in params]
        if not scored:
            continue
        results = {t.id for n in ast.walk(loop) if isinstance(n, ast.Assign)
                   and any(c in scored for c in ast.walk(n.value))
                   for t in n.targets if isinstance(t, ast.Name)}
        labels = {call.args[0].id for call in scored}
        for compare in ast.walk(loop):
            if not isinstance(compare, ast.Compare):
                continue
            sides = [compare.left, *compare.comparators]
            if not any((isinstance(side, ast.Name) and side.id in results) or side in scored for side in sides):
                continue
            targets += [side.id for side in sides if isinstance(side, ast.Name)
                        and side.id in params and side.id not in labels and side.id not in targets]
    return targets


def label_derived_scores(root: Path) -> list[dict[str, Any]]:
    """Functions that receive the real labels and search for, or take, the metric value to hit."""
    out: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
            labels = [n for n in names if _LABEL_PARAM.match(n)]
            targets = [n for n in names if _TARGET_METRIC_PARAM.search(n)]
            searched = _solves_for_parameter(node, set(names))
            if labels and targets:
                how = (f"takes the labels ({', '.join(labels)}) and the metric value to hit "
                       f"({', '.join(targets)}) in one signature")
            elif searched:
                how = (f"loops a label-scored metric toward the value it was handed "
                       f"({', '.join(searched)})")
            else:
                continue
            out.append(
                {
                    "gate": "companion:label_derived_score",
                    "severity": "blocking",
                    "file": str(path.relative_to(root)),
                    "message": (
                        f"{path.relative_to(root)}:{node.lineno} {node.name}() {how}. A score "
                        "solved for from the answer is not a measurement. Either the number is a "
                        "declared target and must be labelled as one on the page, or the "
                        "method has to actually produce it."
                    ),
                }
            )
    return out


def run(root: str | Path) -> list[dict[str, Any]]:
    root = Path(root)
    if not root.is_dir():
        return []
    return json_constructed_series(root) + back_solved_means(root) + label_derived_scores(root)


def demo() -> None:
    """Self-check: the grid, the back-solve, and the two things that are neither."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "grid.json").write_text(
            json.dumps({"m": {"Brier": {"3m": 0.012, "6m": 0.016, "9m": 0.020, "12m": 0.024}}})
        )
        (d / "ok.json").write_text(json.dumps({"Brier": [0.011, 0.016, 0.021, 0.024]}))
        # three fine-grained columns that each average onto three decimals
        (d / "backsolved.csv").write_text(
            "seed,a,b\n"
            "1,0.425348,0.017674\n2,0.425102,0.017044\n3,0.414000,0.019000\n"
            "4,0.420550,0.018282\n5,0.420000,0.018000\n"
        )
        # a constant column and a coarse column: neither is a back-solve
        (d / "fine.csv").write_text(
            "seed,rate,score\n1,0.0,0.7853\n2,0.0,0.7861\n3,0.0,0.7844\n"
            "4,0.0,0.7872\n5,0.0,0.7855\n"
        )
        found = {f["gate"] for f in run(d)}
        assert "companion:constructed_series_json" in found, found
        files = {f["file"] for f in run(d) if f["gate"] == "companion:constructed_series_json"}
        assert files == {"grid.json"}, files
        backsolved = [f for f in run(d) if f["gate"] == "companion:back_solved_mean"]
        assert {f["file"] for f in backsolved} == {"backsolved.csv"}, backsolved

        # the producer signature: labels in, required metric value in, "score" out
        (d / "solved.py").write_text(
            "def rank_scores(y, target_auroc, seed):\n"
            "    z = shift_until(y, target_auroc)\n"
            "    return z\n"
        )
        # an evaluator takes the labels; a trainer takes a target. Neither alone is a finding.
        (d / "honest.py").write_text(
            "def evaluate(y, p):\n    return roc_auc_score(y, p)\n\n"
            "def train(features, target_auroc=None, patience=3):\n    return fit(features)\n"
        )
        solved = [f for f in run(d) if f["gate"] == "companion:label_derived_score"]
        assert {f["file"] for f in solved} == {"solved.py"}, solved
    print("constructed_data: ok")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root", nargs="?", help="companion / release directory")
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args(argv)
    if args.demo:
        demo()
        return 0
    if not args.root:
        ap.error("give a directory or --demo")
    findings = run(args.root)
    for f in findings:
        print(f"  [{f['severity']}] {f['gate']}: {f['message']}")
    print(f"{len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
