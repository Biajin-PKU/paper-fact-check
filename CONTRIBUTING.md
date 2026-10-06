# Contributing

Everything lives in `skills/paperfactcheck/`, so the skill folder alone is a complete install.

| Path | What it is |
|---|---|
| `paperfactcheck/checks/` | One module per family of checks. Each has `run(text) -> list[dict]` and a `demo()` self-check. Standard library only. |
| `paperfactcheck/readers.py` | PDF, Word, LaTeX, Markdown and text into one LaTeX-flavoured text. |
| `paperfactcheck/references.py` | Reference lookups (Crossref, OpenAlex, arXiv, doi.org). |
| `paperfactcheck/catalog.py` | Title, group and order of every finding category, in English and Chinese. |
| `paperfactcheck/cli.py`, `report.py`, `mcp.py` | Command line, report, MCP server. |
| `SKILL.md`, `references/` | What the agent does after the script. |

## Adding a check

1. Write the module in `checks/` with `run(text)` and a `demo()` that holds one failing and one passing case.
2. Add it to `TEXT_CHECKS` in `cli.py` and its categories to `catalog.py`.
3. Add a case to `tests/test_paperfactcheck.py`, run `python3 tests/test_paperfactcheck.py`.
4. Run the unseen-paper scan in `benchmark/` and check every major finding by hand. A check that raises
   false majors on real papers is not ready.

A finding must quote the paper and carry the evidence that contradicts it. Report inconsistencies,
never intent.
