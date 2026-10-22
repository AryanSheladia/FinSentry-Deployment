# FinSentry model accuracy and risk-calculation review

Audit date: 23 October 2026. The current saved classifier was rerun across the complete original test partition, using the original causal source history. The original model and dataset hashes matched their metadata, and the saved confusion matrix and average precision were reproduced. No live database records, model, calibration, threshold or policy were changed.

Reproduce: `.venv\Scripts\python.exe scripts/audit_sparkov_model.py` from the project root. Aggregate evidence: `reports/model_accuracy_audit.json`.

## Verified classifier performance

| Metric | Result | Interpretation |
|---|---:|---|
| Test transactions | 555,719 | Later chronological source partition |
| Fraud transactions | 2,145 (0.386%) | Very imbalanced dataset |
| Accuracy | 99.8508% | Correct predictions across all payments |
| Precision | 83.2323% | Fraction of model alerts that are source-labeled fraud |
| Recall | 76.8298% | Fraction of source-labeled fraud caught |
| F1 | 0.79903 | Balance between precision and recall |
| Average precision | 0.86865 | Ranking quality under precision/recall; not accuracy |
| ROC-AUC | 0.99639 | Ranking metric; not probability of a correct decision |
| Balanced accuracy | 88.3849% | Mean of fraud recall and non-fraud recall |
| Model alert rate | 0.3563% | Does not include extra behavior/policy alerts |

At the current 32.7171% calibrated-score cutoff:

| Source truth | Predicted non-fraud | Model alert |
|---|---:|---:|
| Non-fraud | 553,242 | 332 |
| Fraud | 497 | 1,648 |

An always-non-fraud classifier would achieve 99.6140% accuracy with zero fraud recall. Consequently, “99.85% accurate” alone overstates usefulness. For this imbalanced task, report precision, recall, F1 and alert volume alongside accuracy. [scikit-learn precision/recall guidance](https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html).

These are classifier results on synthetic Sparkov card payments. They do not establish real-bank performance or the performance of the entire five-agent system. The full decision policy can add review flags and uncertainty escalations; it needs its own evaluation.

## Can adjusting the cutoff help?

The following are diagnostics for prespecified cutoffs, not newly selected or deployed settings:

| Model cutoff | Precision on existing test | Recall on existing test | F1 | Frauds caught | Legitimate alerts |
|---|---:|---:|---:|---:|---:|
| 32.7171% (current) | 83.23% | 76.83% | 0.7990 | 1,648 | 332 |
| 20% | 76.58% | 81.54% | 0.7898 | 1,749 | 535 |
| 10% | 64.70% | 85.45% | 0.7364 | 1,833 | 1,000 |
| 5% | 53.47% | 89.04% | 0.6682 | 1,910 | 1,662 |

A 20% cutoff would catch 101 additional frauds at the cost of 203 additional legitimate alerts in this test partition. It improves recall while reducing precision and slightly reducing F1. Changing a cutoff changes which payments get flagged; it does not improve their probability estimates. Choose an operating point using a separate chronological development set and an explicit analyst-workload/missed-fraud objective. Do not choose it by maximizing the reported test results. [scikit-learn threshold guidance](https://scikit-learn.org/stable/modules/classification_threshold.html).

## Is the current risk percentage calibrated?

The existing sigmoid calibration already improved aggregate metrics on the test partition:

| Probability-quality measure | Raw model | Calibrated model |
|---|---:|---:|
| Brier score (lower is better) | 0.0012360 | 0.0011279 |
| Log loss (lower is better) | 0.0057769 | 0.0047178 |

However, aggregate scores alone do not establish reliability in every risk band. For example, among the 304 payments scoring between 20% and the current cutoff, mean predicted risk was 25.81% and observed fraud frequency was 33.22%. This finite sample suggests checking intermediate-score calibration more closely, not assuming a new method will necessarily perform better. At scores of at least 95%, the 1,065 payments averaged 99.06% predicted risk and 99.34% observed fraud.

Compare sigmoid and isotonic calibration on separate chronological development folds, inspecting calibration curves and log loss/Brier results. Retain whichever generalizes best. A lower Brier score alone does not prove better calibration, since discrimination also affects it. [scikit-learn calibration guidance](https://scikit-learn.org/stable/modules/calibration.html).

## Improvements worth testing, in priority order

1. **Put customer-specific anomaly features into the classifier.** It currently sees UTC hour and home distance but does not see the behavior agent's rare-hour share or historical distance percentile. Add prior-only three-hour-band frequency, distance relative to the customer's historical distribution, and recent-versus-long-term activity changes. These may help the numeric score reflect useful behavioral evidence, but gains must be measured. A distant-location fraud pattern absent from training labels cannot be learned reliably just by adding a distance column.

2. **Use more robust spending baselines.** Means and standard deviations can be inflated by a few extreme earlier payments. Test rolling median, interquartile range or median absolute deviation, and short/long rolling windows alongside the existing mean/z-score. Compute them from strictly earlier records. Do not silently treat unreviewed history as confirmed legitimate.

3. **Evaluate the combined agent policy.** Measure fraud recall, precision, false alerts, review rate and uncertainty-escalation volume for final FLAG/ESCALATE actions, separately from classifier alerts. Check whether a new merchant alone creates too much review work. Do not present the heuristic `assessment_index` as a probability or manually increase percentages to match warnings.

4. **Tune the review objective explicitly.** The current cutoff maximizes development F1. A fraud analyst may prefer higher recall within a manageable daily review volume. Evaluate an F-beta/cost or review-capacity objective on development data rather than simply lowering the cutoff by eye.

5. **Broaden model selection and time validation.** Only three LightGBM configurations were tried. Test additional regularization, tree sizes, minimum leaf counts and modest class weights across rolling chronological folds. The existing weight-4 candidate already had lower validation F1 than the unweighted winner, so class weighting is not automatically an improvement. Changing class weights also requires checking probability calibration. [LightGBM parameter guidance](https://lightgbm.readthedocs.io/en/v4.6.0/Parameters.html).

6. **Check later-period performance and score calibration.** Monthly test F1 ranged from 0.7232 in December to 0.8344 in September; recall ranged from 70.36% in August to 81.63% in November. These differences justify temporal validation and monitoring. They do not, by themselves, prove one particular cause of drift. Tune and calibrate with enough later-period development coverage, then assess a genuinely untouched later holdout.

7. **Keep evidence limits explicit.** A missing history record should still create uncertainty rather than a low-risk assumption. Simulated per-customer devices do not supply real observed device-fraud relationships. Merchant-home distance should be interpreted in payment context, particularly for online purchases. If a single combined fraud probability is eventually required, train and calibrate a fusion model with out-of-fold evidence features and labels; do not average correlated scores using arbitrary weights.

Training gain inspection showed that amount, category and hour dominate this fitted classifier, while home distance contributed relatively little. These are descriptive training-gain statistics, not risk-calculator weights, causal explanations or proof that a feature will help on new data.

## Recommended next experiment

Create a separate v3 candidate with prior-only rare-hour, customer-relative distance and robust spending features. Preserve v2 and its demonstration presets. Select features/model/calibrator/cutoff on chronological development folds; compare the classifier and final review policy on an untouched later holdout. The existing original test set has now been inspected repeatedly and should be treated as a diagnostic benchmark, not a fresh selection-free validation of future improvements.

No numerical improvement is promised until that experiment passes. For the current demonstration, describe low model risk plus behavior warnings as independent evidence checks, not as a broken risk calculator.
