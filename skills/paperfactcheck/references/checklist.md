# Reading checklist

Work through the groups in order. For each item, either quote the passage and the conflicting evidence,
or move on. The script has already covered what is marked *(script)*; confirm those, do not redo them.

## Numbers

1. *(script)* The same quantity with different values in abstract, text, tables and captions.
2. *(script)* "Increased by X%" against the two numbers it compares; percentages against their counts.
3. Sample sizes and group sizes: abstract, methods, flow diagram, baseline table and results must
   agree, and groups must add up to the total. Track every exclusion.
4. Denominators: a percentage computed on the analysed sample in one place and on the enrolled sample
   in another.
5. Units, scales and time periods: mg vs g, months vs years, study dates that differ between sections.
6. Rounding that changes meaning: 0.049 reported as "p = .05, significant".

## Statistics

7. *(script)* p-values recomputed from t, F, chi-square, r and z; intervals against p-values; GRIM and
   GRIMMER for means and SDs of integer data.
8. A test that does not fit the data: a t test on a skewed outcome described as median (IQR); a
   chi-square test with expected counts that must be tiny; paired data analysed as independent.
9. Many outcomes or subgroups tested with no correction, and only the significant ones discussed.
10. Significance stars or bold values that do not match the p-values or the legend.
11. A model reported with more predictors than events allow (roughly fewer than 10 events per predictor),
    or performance reported only on the data used to fit it.

## Claims

12. Causal words (causes, reduces, improves, leads to, 导致, 降低了) for an observational or
    cross-sectional design.
13. The abstract or conclusion states more than the results support: a secondary or subgroup result
    presented as the main finding; "significant" where the test was not significant; a population
    wider than the sample.
14. Hedges dropped between sections: "may be associated" in results becomes "is" in the abstract.
15. Planned or proposed work written as done ("we validated" for a validation the methods describe as
    future work).
16. Selective reporting: the worked example is the best case; thresholds or subgroups chosen after
    seeing the results; a sensitivity analysis that only appears where it helps.

## References

17. *(script)* References that do not exist, DOIs that point elsewhere, retracted works, citations
    missing from the list.
18. A cited work that does not support the sentence: check the abstracts in `findings.json` against
    the `cited_in` sentences. Report only clear mismatches.
19. A claim of "first" or "no previous study" that the reference list itself contradicts.

## Figures and tables

20. *(script)* Panels referred to that the figure does not have; tables and figures never referred to.
21. Captions that describe something else than the figure shows; axis labels, units or legends that
    differ from the text; error bars not defined.
22. A table whose rows or columns do not add up, or whose percentages are computed on a different
    denominator than its header says.

## Code and data (when supplied)

23. Run the entry point or the script behind one main table; compare its numbers with the paper.
24. The code computes something other than what Methods describe: a different metric, split, filter,
    or order of steps (for example, scaling or feature selection fitted on all data before the split).
25. Leakage: the same subject, patient or near-duplicate in training and test data; features built
    with information from the outcome or the future.
26. Circular evaluation: ground truth produced by the method being evaluated, or by the same generator
    that produced the inputs.
27. *(script)* Result files that no test reads; series of results that step by an exact constant.

## Reporting and declarations

28. Decide the study type and check the matching guideline in `guidelines/`.
29. *(script lists what is present)* Decide which declarations this study needs: ethics approval and
    consent for human or animal data, trial or review registration, funding, competing interests, data
    and code availability, author contributions, and use of AI tools where the venue asks for it.
30. Internal contradictions in declarations: "retrospective, consent waived" in one place and "written
    consent obtained" in another; "data available on request" next to a public-data claim.

## Writing

31. *(script)* Chatbot text, placeholders, tortured phrases, abbreviations used before definition.
32. One concept under several names (a model called three different things), or one name used for two
    different things.
33. Sentences whose statistics reverse the result ("lower risk (HR 1.35)").

## Stop rule

Stop when what remains would not change what a reader concludes. A short list of solid findings is
more useful than a long list a reader must filter.
