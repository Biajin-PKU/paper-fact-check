# Paper Fact Check

[![ci](https://github.com/Biajin-PKU/paperfactcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/Biajin-PKU/paperfactcheck/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/Biajin-PKU/paperfactcheck)](https://github.com/Biajin-PKU/paperfactcheck/releases)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**[Checks](docs/checks.md)** | **[Benchmarks](benchmark/README.md)** | **[MCP](docs/mcp.md)** | **[GitHub Action](docs/action.md)** | **[中文](README.zh-CN.md)**

A fact-checker for research papers. It recomputes the statistics, percentages and changes a paper
reports, compares the text with its tables, and looks up every reference. Each finding quotes the
paper, shows the arithmetic, and suggests a fix.

It runs as an agent skill in Claude Code, Codex, Cursor and other coding agents, where the model
then reviews every finding and reads the paper for what arithmetic cannot settle. It also runs on
its own from the command line.

```console
$ paperfactcheck main.tex --offline
main.tex
  S1  major    * Text and table give different values             Results
        The text gives 0.847 for 'our model', but no cell of its table row matches at that precision;
        the nearest row value is 0.851.
  S2  major    * Mean impossible for its sample size (GRIM)       Results
        Mean 5.19 to 2 dp is not achievable from any integer total over N=18 items (GRIM test) — the
        reported mean is arithmetically impossible for that N.
  S3  major    * p-value does not follow from its test statistic  Results
        t = 1.20 cannot give p = 0.003: whatever the degrees of freedom, its two-sided p is at least
        .228. The result is not significant at 0.05.
  …

8 findings: 6 change a conclusion (*), 1 worth fixing, 1 minor.
Report: report/report.html
```

- 41 computed and lookup checks across numbers, statistics, references, figures, and released code
  and data, listed in [docs/checks.md](docs/checks.md)
- Reference lookups against Crossref, OpenAlex, arXiv and doi.org: existence, DOI match, retractions
- A review pass for claims, reporting guidelines (CONSORT, STROBE, PRISMA, ARRIVE, STARD,
  TRIPOD+AI, COREQ) and declarations
- PDF, Word, LaTeX folders and Overleaf zips, Markdown; papers in English and Chinese
- HTML, Markdown and JSON reports
- Python 3.9 standard library only; the manuscript is not uploaded anywhere

<p align="center"><img src="docs/images/report-en.png" width="85%" alt="An HTML report with findings grouped by area"></p>

## Installation

As a skill for Claude Code, Codex, Cursor, OpenCode, Gemini CLI and
[other agents](https://github.com/vercel-labs/skills):

```console
$ npx skills add Biajin-PKU/paperfactcheck
```

As a Claude Code plugin:

```console
/plugin marketplace add Biajin-PKU/paperfactcheck
/plugin install paperfactcheck@paperfactcheck
```

From [ClawHub](https://clawhub.ai), for OpenClaw and Hermes:

```console
$ clawhub install paperfactcheck
```

As a command-line tool:

```console
$ uvx --from git+https://github.com/Biajin-PKU/paperfactcheck paperfactcheck paper.pdf
```

Or with no installation at all:

```console
$ git clone https://github.com/Biajin-PKU/paperfactcheck
$ python3 paperfactcheck/skills/paperfactcheck/run.py paper.pdf
```

In Claude.ai, upload `paperfactcheck-skill.zip` from the
[latest release](https://github.com/Biajin-PKU/paperfactcheck/releases/latest) as a custom skill in
Settings. In any other chat assistant, paste [`prompt.md`](prompt.md) and
attach the paper; without the script, the arithmetic is left to the model.

PDF input uses `pdftotext` (poppler) when it is installed, or `pypdf` if available. Without either,
the agent reads the PDF itself.

## Usage

In an agent:

```console
/paperfactcheck paper.pdf
/paperfactcheck overleaf-project.zip --code ./repo
```

The agent runs the checks, confirms each finding against the paper and dismisses misreadings, reads
the paper against the [reading checklist](skills/paperfactcheck/references/checklist.md) and the
matching reporting guideline, and writes the report.

On the command line:

```console
$ paperfactcheck [check] PAPER [--code DIR] [--out DIR] [--offline] [--lang auto|en|zh] [--json]
$ paperfactcheck render DIR
$ paperfactcheck mcp
```

| Option | |
|---|---|
| `PAPER` | `.pdf`, `.docx`, `.tex`, a LaTeX folder, a `.zip`, `.md` or `.txt` |
| `--code DIR` | Released code or data; enables the code and data checks |
| `--out DIR` | Report folder, default `paperfactcheck-<name>` |
| `--offline` | Skip reference lookups |
| `--lang` | Report language; `auto` follows the paper |
| `--json` | Print the findings as JSON |

`render` rebuilds the report after a `review.json` is added to the report folder
([format](skills/paperfactcheck/references/review-format.md)). `mcp` serves the checks over the Model
Context Protocol ([setup](docs/mcp.md)). The [GitHub Action](docs/action.md) checks a paper on every
push.

Exit status is 0 when nothing changes a conclusion, 1 when something does, and 3 when the file could
not be read.

## How it works

1. **Read.** Every format is turned into one text, with Word and Markdown tables rebuilt as tables
   so that text and table values can be compared.
2. **Compute.** The script extracts reported statistics, percentages, changes, means and table cells,
   recomputes them from the paper's own numbers, and allows for the rounding printed.
3. **Look up.** Each reference is matched in Crossref, OpenAlex and arXiv by DOI, identifier or
   citation text; retraction notices come from Crossref.
4. **Review.** In the skill, the model opens every script finding in the paper and dismisses
   misreadings, then reads for claims, reporting items and declarations.
5. **Report.** Findings are grouped by area, with the quote, the evidence, the calculation and a fix.

## False positives

A script finding is a candidate. Most false alarms come from a number the script tied to the wrong
row or condition, a setting read as a result, or a test the sentence does not say was one-sided. The
review step exists to remove these, and dismissed findings stay visible in the report with the
reason.

On 182 recent arXiv papers never used in development, the script raised 25 major findings; checked
by hand, 5 were real (citation keys missing from the bibliography, figure panels the caption does
not describe) and the rest were false alarms. The patterns behind them were fixed after each set; the
last set of 50 papers raised one. Details and the data are in [benchmark/](benchmark/README.md).

## Scope

Paper Fact Check reports where a paper disagrees with itself or with its sources. It does not score
plagiarism or AI-generated text, detect image manipulation, judge novelty, or decide whether
misconduct happened.

Reference lookups send the reference entries, not the manuscript, to Crossref, OpenAlex, arXiv and
doi.org. Everything else runs locally and with the model you already use.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New checks need a self-test and a hand-checked run on unseen
papers.

## License

MIT
