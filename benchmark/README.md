# Benchmarks

Everything here runs from public arXiv LaTeX sources and is reproducible. Downloads are cached in
`benchmark/.cache` and spaced 3 s apart. These measure the **script** layer alone (no model review),
with reference lookups off.

## Author corrections

```bash
python3 benchmark/arxiv_corrections.py
```

Papers whose arXiv comment says a table or numbers were corrected. The LaTeX of v1 and v2 is diffed
word by word; a replaced decimal is a correction, and it is caught when a finding on v1 is about the
old number.

| | |
|---|---|
| Papers with numeric corrections | 14 |
| Corrected numbers | 860 (one paper accounts for 752) |
| Papers caught | 1 |

The catch: an ICRA 2026 paper's v1 stated "41.4% bandwidth reduction (800 vs 2800 bits)";
1 − 800/2800 = 71.4%, which the authors printed in v2. Most corrections are invisible inside v1: a
re-run experiment changes the number in the text and the table together, so v1 contradicts nothing.

## Major findings on unseen papers

```bash
python3 benchmark/arxiv_corrections.py --scan 100 --since 20261001 --cats cs.SE,q-fin.ST,eess.SP,physics.ao-ph,q-bio.TO --out x.json
```

Recent papers (submitted from 1 October 2026), each set from arXiv categories not used before. Every
major finding was checked by hand against the source. The false alarms each set exposed were fixed
before the next set was drawn, so each row measures the script as it stood when that set was run.

| Set | Categories | Papers | Major findings | Real | False |
|---|---|---|---|---|---|
| [1](unseen-set1.json) | cs.CV, stat.ML, q-bio.NC, physics.soc-ph, cs.HC | 79 | 16 | 3 | 12 (1 unclear) |
| [2](unseen-set2.json) | cs.RO, cs.IR, stat.CO, q-bio.GN, physics.med-ph | 53 | 8 | 2 | 6 |
| [3](unseen-set3.json) | cs.SE, q-fin.ST, eess.SP, physics.ao-ph, q-bio.TO | 50 | 1 | 0 | 1 |

The real ones: citations whose key has no bibliography entry (the PDF prints [?]), including a key
with the wrong year, and figure panels the text cites that the caption does not describe.

What this means for use: a script finding is a candidate. In the skill, the reviewing model opens
each one in the paper and dismisses misreadings before the report is written.
