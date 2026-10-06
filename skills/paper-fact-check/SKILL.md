---
name: paper-fact-check
description: Fact-check a research paper against its own evidence. Recomputes p-values, percentages and changes from the paper's own numbers, compares text with tables, looks up every reference (does it exist, is it retracted, does it say what is cited), checks figures, released code and data, reporting guidelines (CONSORT, STROBE, PRISMA, ARRIVE, STARD, TRIPOD+AI, COREQ), declarations, overclaiming and traces of AI writing, then writes an HTML report where each finding quotes the paper, shows the arithmetic and gives a fix. Use when asked to check, verify, fact-check, pre-review or proofread a paper, manuscript, thesis or preprint for errors (PDF, Word, LaTeX, Overleaf zip, Markdown), in any field and in English or Chinese. 论文核查、投稿前检查、查论文里的错误、核对数据和参考文献。
---

# Paper Fact Check

Two layers. A script computes everything arithmetic and lookups can settle; you read the paper for
everything that needs judgement. Both report inconsistencies, never intent.

`SKILL_DIR` below is the directory that holds this file.

## 1. Run the script

```bash
python3 SKILL_DIR/run.py check <paper> --out <report-dir> [--code <code-or-data-dir>] [--offline]
```

- `<paper>`: PDF, .docx, .tex, a LaTeX folder, an Overleaf .zip, .md or .txt. Python 3.9+, no installs.
- `--code`: the released code or data, if the user has it. Ask once if the paper mentions released code.
- `--offline`: only if the user asks; otherwise every reference is looked up (Crossref, OpenAlex, arXiv).
- Default `<report-dir>`: `paper-fact-check-<paper-name>` beside where you run it.
- Exit 0: no first-order findings. Exit 1: at least one. Exit 3: the file could not be read. For a PDF
  without `pdftotext`, read the PDF yourself, write its text to `<name>.md` with tables as Markdown
  tables, and run the script on that file.

The script prints a summary and writes `<report-dir>/findings.json`, `manuscript.txt` (the text it
read), and a first `report.html`.

## 2. Confirm every script finding

Open each finding's passage in the paper. Keep it only if the numbers are what the script read.
Dismiss it, with a one-line reason, when the script misread: a value from another condition, a
figure or supplement, a setting rather than a result, a one-sided or corrected test the sentence
does not name. Never dismiss a finding because the paper would look better without it.

## 3. Read the paper for what the script cannot see

Read `manuscript.txt` (or the PDF itself if you can view pages) from start to end, then work through
`SKILL_DIR/references/checklist.md`. In short:

- **Claims**: causal wording on observational data; the abstract or conclusion claiming more than the
  results show; hedged findings written as certain; planned work written as done.
- **Numbers across the paper**: sample sizes, group sizes and denominators that differ between
  abstract, methods, results, tables and flow diagram; units and time periods.
- **References**: for each item in `findings.json` → `references.items` that has an `abstract` and
  `cited_in`, ask whether the cited work supports the sentence that cites it. Report only clear
  mismatches (the cited work studies something else, or says the opposite).
- **Reporting standard**: decide the study type, open the matching file in
  `SKILL_DIR/references/guidelines/`, and check each item against the paper.
- **Declarations**: `findings.json` → `statements` lists which declarations were found. Decide which
  are required for this study type and report the missing ones.
- **Figures**: if you can see the figures, compare axes, legends, panel letters and plotted values with
  the captions and the text.
- **Code and data** (when given): run the entry point or the script behind one main table, within about
  ten minutes, and compare its output with the paper. Check that the code computes what Methods
  describe (metric, split, filtering, order of steps). Never install packages system-wide.
- **AI writing traces**: one concept under several names, statistics phrased in a way that reverses
  the result, summaries that drop a qualifier.

## 4. Write review.json and render

Write `<report-dir>/review.json` in the format in `SKILL_DIR/references/review-format.md`: dismissals,
edits to script findings (add a `calculation`; when the user writes in Chinese, put Chinese text in
`evidence` and `fix`), your own findings, guideline items, a two-sentence `summary`, and anything you
could not verify. Then:

```bash
python3 SKILL_DIR/run.py render <report-dir>
```

## 5. Reply

In the user's language, briefly:

1. One line: how many findings change a conclusion, how many are worth fixing, what could not be checked.
2. The first-order findings, each as: where, what the paper says, what contradicts it, the fix.
3. The path to `report.html`.

Offer to apply the fixes to the source if it is LaTeX, Word or Markdown. Do not edit the paper unless asked.

## Rules for every finding

- **Quote, do not paraphrase.** A finding needs the passage and the evidence that contradicts it. No
  quote, no finding.
- **Show the arithmetic** whenever a number is involved, from the paper's own numbers.
- **Severity**: `critical` = the main claim does not survive; `major` = a claim or number must be
  corrected; `minor` = presentation, or a check the paper should add.
- **Order**: `first` changes what a reader concludes; `second` does not. Lead with first-order.
- **Inconsistency, not accusation.** Never write that data were fabricated or that anyone acted in bad
  faith. "The text says X; Table 2 says Y" is the finding.
- **Precision over volume.** Stop when what remains is second-order. Say "could not verify" instead of
  guessing.
- Do not judge novelty or importance, and do not score AI-generated text.
