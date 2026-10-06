# Prediction models, including AI and machine learning (TRIPOD+AI 2024)

Official: TRIPOD+AI statement (BMJ 2024), www.tripod-statement.org.

**Title and abstract**
- Identifies the study as developing or evaluating a prediction model, the target population and the outcome.

**Introduction**
- The healthcare context and the rationale, including existing models; objectives, stating whether the study develops, evaluates, or both.

**Methods**
- Data sources (cohort, registry, records), with dates; setting and centres.
- Eligibility criteria; details of any treatment received, if relevant.
- Data preparation: preprocessing, quality checks, and whether this was done the same way across datasets.
- Outcome: definition, how and when assessed, time horizon, whether assessment was blinded to predictors.
- Predictors: definition, how and when measured, blinding to the outcome; rationale for choosing them.
- Sample size: how it was decided and whether it is adequate for development and evaluation.
- Missing data: how much, and how handled (imputation method).
- Analytical methods: model type and rationale; how predictors were handled; model building, hyperparameter tuning and internal validation (cross-validation, bootstrap); handling of class imbalance; approaches to fairness.
- Model output (probabilities, risk groups) and any thresholds, with how they were chosen.
- Performance measures: discrimination (AUC or C-index), calibration (plot, slope, intercept), and clinical utility (decision curve) where relevant, with uncertainty.
- Differences between development and evaluation data; model updating.
- Ethical approval; open science: funding, conflicts, protocol, registration, data and code availability; patient and public involvement.

**Results**
- Participant flow with numbers and outcome events in each dataset; characteristics per dataset.
- The model itself, or how to access it (full equation, code, or an interface).
- Performance with confidence intervals, including calibration, overall and in key subgroups.

**Discussion**
- Interpretation; limitations including non-representative samples and overfitting; how the model would be used in practice and what is needed before deployment.

**Check especially**: test data were not used for tuning or feature selection; calibration is reported, not only AUC; external validation is not claimed for a random split of one dataset; events per predictor are sufficient.
