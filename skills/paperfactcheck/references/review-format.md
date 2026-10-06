# review.json

Written by the reviewer into the report folder, then merged by `run.py render`. Every field is optional.

```json
{
  "summary": "Two sentences: the overall state of the paper and the one thing to fix first.",
  "study_type": "Retrospective cohort study (prediction model)",
  "guideline": "TRIPOD+AI",
  "dismissed": [
    {"id": "S4", "reason": "0.847 is the validation-set value reported in the previous sentence, not Table 2."}
  ],
  "edits": {
    "S1": {
      "calculation": "1 - 800 / 2800 = 0.714 → 71.4%",
      "fix": "Replace “41.4% bandwidth reduction” with “71.4% bandwidth reduction” in the abstract, Section I and the Figure 2 caption.",
      "order": "first"
    }
  },
  "findings": [
    {
      "title": "Abstract claims a causal effect from an observational design",
      "group": "claims",
      "severity": "major",
      "order": "first",
      "where": "Abstract, conclusion sentence",
      "quote": "Early mobilisation reduces 30-day mortality.",
      "evidence": "Methods: retrospective cohort, adjusted logistic regression; no randomisation or causal design.",
      "calculation": "",
      "fix": "“Early mobilisation was associated with lower 30-day mortality.”"
    }
  ],
  "guideline_items": [
    {"item": "Sample size: how it was determined", "status": "missing", "where": ""},
    {"item": "Handling of missing data", "status": "reported", "where": "Methods 2.4"}
  ],
  "not_verified": [
    {"item": "Figure 3 values", "reason": "figures were not visible in the extracted text"}
  ]
}
```

- `id`: script findings are `S1, S2, ...` as listed in `findings.json`; your own findings are numbered
  `R1, R2, ...` automatically.
- `group`: one of `numbers`, `statistics`, `references`, `figures`, `code`, `reporting`, `claims`, `writing`.
- `severity`: `critical`, `major` or `minor`. `order`: `first` or `second`.
- `status` in `guideline_items`: `reported`, `missing` or `unclear`.
- Write the text fields in the user's language.
