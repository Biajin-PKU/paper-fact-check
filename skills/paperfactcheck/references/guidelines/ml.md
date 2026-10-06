# Machine learning and computational method papers

There is no single reporting guideline; this list follows the NeurIPS paper checklist and common reviewer requests.

- **Claims**: the abstract and introduction claim only what the experiments show; limitations are stated.
- **Theory**: assumptions are stated and proofs are complete, in the paper or an appendix.
- **Data**: datasets named with versions, licences and splits; the same splits for every method; no test examples in training or tuning data (watch near-duplicates and leaked labels).
- **Baselines**: strong, current baselines, tuned with the same budget as the proposed method; numbers copied from other papers are labelled as such and use the same setting.
- **Hyperparameters**: the search space and selection procedure; selection on validation data, never on test data.
- **Variance**: results over several seeds or folds with standard deviation or confidence intervals; significance tests where differences are small.
- **Ablations**: each claimed component is ablated; the ablation table and the main table use the same setting.
- **Compute**: hardware, run time and total compute.
- **Reproducibility**: code and data released or a clear reason why not; enough detail to reimplement.
- **Evaluation**: the metric is appropriate and defined; the evaluation is not circular (labels or references produced by the evaluated model or by a sibling model).
- **Ethics and impact**: broader impacts, safeguards for misuse, licences of used assets, consent and approval for human data or crowdsourcing.

**Check especially**: the best numbers in the text match the tables; "state of the art" is true against the cited baselines; gains are larger than the variance across seeds.
