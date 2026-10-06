# GitHub Action

Check the paper on every push, for example in a repository synced with Overleaf.

```yaml
# .github/workflows/paperfactcheck.yml
name: paperfactcheck
on: [push]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Biajin-PKU/paperfactcheck@v1
        with:
          paper: main.tex          # PDF, .docx, .tex, a folder or a .zip
          # code: code/            # optional released code or data
          # fail-on: first-order   # never (default) | first-order | any
```

The report is uploaded as the `paperfactcheck-report` artifact, and the Markdown version is shown on
the run's summary page.

The Action runs the script checks and reference lookups. The reading pass (claims, guidelines,
reference support) needs a model; run the skill in your agent for that.
