# Checks

Every finding carries one of the IDs below. **Script** checks are computed and give the same result on every run; **lookup** checks query Crossref, OpenAlex, arXiv and doi.org (off with `--offline`); **review** checks are done by the model following [`SKILL.md`](../skills/paperfactcheck/SKILL.md) and [`checklist.md`](../skills/paperfactcheck/references/checklist.md).

Severity is the default; the reviewer can change it. *First-order* means the finding can change what a reader concludes.

## Numbers

| ID | Flags | Method | First-order when major |
|---|---|---|---|
| `prose_table_number_disagreement` | A number in the text differs in its last digits from the table row the sentence names. | script | yes |
| `cross_section_number_disagreement` | One quantity is given different values in different sections. | script | yes |
| `relative_change_mismatch` | "Improved by X%" does not follow from the two numbers it compares. | script | yes |
| `same_change_different_values` | The same change is quoted with two different percentages. | script | yes |
| `percent_count_mismatch` | "45/192 (25.4%)": the percentage does not equal count over denominator. | script | yes |
| `percent_denominator_outlier` | Several "k (p%)" pairs share a denominator except one. | script | no |
| `product_total_mismatch` | "48 profiles x 30 segments" does not multiply to the stated total. | script | yes |
| `compute_budget_inconsistency` | Stated totals contradict each other. | script | yes |
| `terminal_digit_nonuniform` | Last digits in tables are far from uniform (weak signal). | script | no |

## Statistics

| ID | Flags | Method | First-order when major |
|---|---|---|---|
| `pvalue_recompute_mismatch` | p does not follow from t, F, chi2, r or z and its degrees of freedom; major when significance flips. | script | yes |
| `pvalue_z_mismatch` |  | script | yes |
| `pvalue_t_impossible` |  | script | yes |
| `pvalue_clustering_below_0_05` | Several p-values just below 0.05. | script | no |
| `interval_p_contradiction` | A 95% interval and its p-value disagree on significance. | script | yes |
| `estimate_outside_interval` | A point estimate lies outside its own interval. | script | yes |
| `effect_size_mismatch` | Partial eta squared does not follow from F and its degrees of freedom. | script | no |
| `grim_infeasible_mean` | A mean of N integer responses that no integer total can give (GRIM). | script | yes |
| `grimmer_infeasible_sd` | A mean and SD of N integer responses that no data can give together (GRIMMER). | script | yes |

## References

| ID | Flags | Method | First-order when major |
|---|---|---|---|
| `citation_undefined` | A citation key with no bibliography entry (prints as [?]). | script | no |
| `citation_beyond_list` | A numbered citation beyond the end of the reference list. | script | no |
| `reference_never_cited` | A reference list entry never cited. | script | no |
| `reference_duplicate` | One work cited under two keys. | script | no |
| `reference_not_found` | No matching work in Crossref, OpenAlex or arXiv. | lookup | yes |
| `reference_doi_unresolved` | The DOI resolves nowhere. | lookup | no |
| `reference_doi_mismatch` | The DOI belongs to a different work. | lookup | no |
| `reference_arxiv_unresolved` | The arXiv identifier does not exist. | lookup | no |
| `reference_arxiv_mismatch` | The arXiv identifier belongs to a different work. | lookup | no |
| `reference_retracted` | The cited work is registered as retracted or withdrawn. | lookup | yes |
| `reference_concern` | An expression of concern is registered for the cited work. | lookup | no |
| `reference_year_mismatch` | The year differs from the record for that DOI. | lookup | no |

## Figures and tables

| ID | Flags | Method | First-order when major |
|---|---|---|---|
| `panel_reference_beyond_caption` | The text cites panel (d) that the caption does not describe. | script | no |
| `uncited_float` | A table or figure the text never refers to. | script | no |

## Code and data

| ID | Flags | Method | First-order when major |
|---|---|---|---|
| `constructed_series_json` | Released results step by an exact constant across settings. | script, needs `--code` | yes |
| `back_solved_mean` | Per-run values average exactly onto the printed rounding. | script, needs `--code` | yes |
| `label_derived_score` | Released code computes a score from the labels it should predict. | script, needs `--code` | yes |
| `unbound_released_record` | A released results file that no test reads. | script, needs `--code` | no |

## Claims

| ID | Flags | Method | First-order when major |
|---|---|---|---|
| `directional_claim_against_interval` | "Better", "significant" next to an interval that includes no effect, or p > 0.05. | script | yes |

## Traces of AI writing

| ID | Flags | Method | First-order when major |
|---|---|---|---|
| `assistant_residue` | Chatbot replies, placeholders, "Figure ??" left in the text (English and Chinese). | script | no |
| `tortured_phrase` | A fixed term replaced word by word with synonyms ("profound learning"). | script | no |
| `abbreviation_before_definition` | An abbreviation used before it is defined. | script | no |
| `abbreviation_two_expansions` | One abbreviation expanded two ways. | script | no |

## Review checks

Done by the model after the script; reported under the same groups.

| Area | Checks |
|---|---|
| Claims | Causal wording for observational designs; abstract or conclusion stronger than the results; dropped hedges; planned work written as done; selective reporting |
| Numbers | Sample and group sizes across abstract, methods, flow diagram and tables; denominators; units and periods |
| Statistics | Tests that do not fit the data; uncorrected multiple comparisons; events per predictor |
| References | Whether the cited work supports the citing sentence (abstracts are fetched for each verified reference) |
| Figures | Captions, axes and legends against the figure and the text, when the model can see figures |
| Code and data | Running the released code against the paper's numbers; code that computes something other than Methods; leakage; circular evaluation |
| Reporting | The matching guideline: CONSORT, STROBE, PRISMA, ARRIVE, STARD, TRIPOD+AI, COREQ, a machine-learning checklist, or a general empirical checklist; required declarations |
| Writing | One concept under several names; statistics phrased so the result reads reversed |
