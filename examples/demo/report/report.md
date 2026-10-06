# Paper Fact Check report: main.tex

**6** Change a conclusion · **1** Worth fixing · **1** Minor · **1** Could not verify

## Numbers

### S1. Text and table give different values [major · changes a conclusion]
- **Where:** Results
- **Quoted text:** > Our model reached an accuracy of 0.847 (Table [tab:main]).
- **What contradicts it:** The text gives 0.847 for 'our model', but no cell of its table row matches at that precision; the nearest row value is 0.851.
- **Suggested fix:** Make the prose and the table report the same value, or name the derivation.

## Statistics

### S2. Mean impossible for its sample size (GRIM) [major · changes a conclusion]
- **Where:** Results
- **Quoted text:** > The N=18 participants gave a mean usefulness rating of 5.19 on a 1--7 scale.
- **What contradicts it:** Mean 5.19 to 2 dp is not achievable from any integer total over N=18 items (GRIM test) — the reported mean is arithmetically impossible for that N.
- **Suggested fix:** Recompute the mean from the raw item sum, or correct N

### S3. p-value does not follow from its test statistic [major · changes a conclusion]
- **Where:** Results
- **Quoted text:** > The difference was significant ( t = 1.20 , p = 0.003 ).
- **What contradicts it:** t = 1.20 cannot give p = 0.003: whatever the degrees of freedom, its two-sided p is at least .228. The result is not significant at 0.05.
- **Suggested fix:** Recompute p from t and its degrees of freedom, and report the degrees of freedom.

## Figures and tables

### S4. Text refers to a panel the figure does not have [major · does not change a conclusion]
- **Where:** Results
- **Quoted text:** > Calibration improved across horizons (Figure [fig:cal]d), with Brier scores listed in the released results.
- **What contradicts it:** The text points to panel d of fig:cal, but its caption marks panels a-c only. Either the panel was dropped and this sentence still cites it, or the caption no longer describes the figure.
- **Suggested fix:** Point the sentence at the panel that shows this result, or restore the panel and its caption entry.

## Code and data

### S5. Released results step by an exact constant [major · changes a conclusion]
- **Where:** brier_by_horizon.json
- **What contradicts it:** brier_by_horizon.json: 'ours' is an arithmetic sequence — 4 values a constant 0.004 apart. Independent measurements do not vary that way. Ask how each value was measured, and for the raw outputs behind it.

### S6. Released results step by an exact constant [major · changes a conclusion]
- **Where:** brier_by_horizon.json
- **What contradicts it:** brier_by_horizon.json: 'baseline' is an arithmetic sequence — 4 values a constant 0.004 apart. Independent measurements do not vary that way. Ask how each value was measured, and for the raw outputs behind it.

### S7. Released result file that no test reads [minor · does not change a conclusion]
- **Quoted text:** > results/main_table.csv
- **What contradicts it:** The manuscript prints 4 values held in results/main_table.csv (0.774, 0.802, 0.812, 0.851), and no shipped test names that file: the page and the file can drift apart while every test still passes.
- **Suggested fix:** Add a test that regenerates the file from code/ and data/, or that reads it and checks the values the manuscript prints.

## Claims

### S8. Claim stronger than its own interval [major · changes a conclusion]
- **Where:** Results
- **Quoted text:** > The ensemble outperformed the strongest baseline by 1.4 points (95% CI -0.3 to 3.1).
- **What contradicts it:** The sentence asserts a direction ('outperformed') but its own evidence does not exclude no effect: 95% CI -0.3 to 3.1 includes 0. Either the comparative word predates the current numbers or the claim overreaches the test.
- **Suggested fix:** Reword to what the interval supports (no detectable difference / direction not established), or report the test that does exclude zero

## Declarations

not found: Ethics approval, Informed consent, Competing interests, Funding, Data availability, Code availability, Trial or review registration, Author contributions, Use of AI tools, Reporting guideline named

## Could not verify

- References: lookups turned off (--offline)
