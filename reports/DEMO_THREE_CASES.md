# FinSentry: three verified demo cases and risk explanation

Verified 22 October 2026 using the saved model, current customer history and complete agent workflow. Verification was read-only: no new payment was saved, no model/policy was altered, and no Groq request was required to compute the actions. Machine-readable evidence: `reports/demo_three_cases_verified.json`.

## The quickest demonstration

Open **Investigate payment**. Use **Try a demo payment** to load each preset below. Keep **Customer with no earlier history** unchecked. Submit each payment and explain the findings. These presets already contain the exact merchant coordinates and simulated device references.

| Field | Low risk | Suspicious / maybe | High-risk suspected fraud |
|---|---|---|---|
| Preset | Sample 1 · $47.36 | Unusual time and location · normal amount | Sample 12 · $677.77 |
| Customer shown in dropdown | Customer 37C586D0 | Customer 00686B4D | Customer 4EDFC01F |
| Full customer ID | CUST_37c586d030d10f7e | CUST_00686b4dd6551bfe | CUST_4edfc01f18a27d90 |
| Amount (USD) | 47.36 | 47.72 | 677.77 |
| Payment date/time, UTC | 2020-06-21 17:27:10 | 2020-07-15 03:15:00 | 2020-09-04 23:26:00 |
| Merchant shown in form | Quitzon-Goyette | Lockman, West and Runte | Welch Inc |
| Raw merchant identifier, API only | fraud_Quitzon-Goyette | fraud_Lockman, West and Runte | fraud_Welch Inc |
| Category shown in form | Home | Groceries · in person | Other · online |
| Raw category | home | grocery_pos | misc_net |
| Merchant latitude | 34.286087 | -33.8688 | 37.650845 |
| Merchant longitude | -89.047646 | 151.2093 | -84.899474 |
| Device reference | SIM_DEVICE_37c586d030d10f7e | SIM_DEVICE_00686b4dd6551bfe | SIM_DEVICE_4edfc01f18a27d90 |
| Model risk, verified | 0.000301% (screen rounds to 0.00%) | 0.016392% (screen rounds to 0.02%) | 99.993251% (screen rounds to 99.99%) |
| Recommended next action | No review trigger | Investigate further | Escalate for human review |
| Internal assessment | LOW / CLEAR | MEDIUM / FLAG | HIGH / ESCALATE |
| Information available | Well supported | Well supported | Partly supported |

Payment method is Card and currency is USD for all three. Existing customers' home coordinates are resolved from history by the backend; do not use the new-customer option. If entering manually, choose the customer and merchant first, then set category and **Edit location** coordinates last because selecting a merchant can replace its coordinates with catalog averages.

Use the dates above, not today's date. The evaluated interval is 21 June 2020 12:14:25 UTC through 31 December 2020 23:59:34 UTC. A date outside that period causes uncertainty rather than the intended three-way demonstration. The form explicitly uses UTC; do not convert these values to India time before entering them.

## What to say for each result

### 1. Low-risk payment

“This customer is paying $47.36 to a familiar merchant. The previous 30-day average is about $54.07, and there are no behavior findings or linked prior fraud cases. The model score is below the review cutoff, so the system finds no review trigger.”

The verification found 1,032 strictly earlier payments. The displayed 0.00% is rounding, not mathematical zero or a guarantee of safety. The original source example has `is_fraud=0`.

### 2. Suspicious payment with a normal amount

“The amount is not unusually large, and the model score is low. However, only 1 of 99 payments in the previous 90 days occurred around this hour, and the merchant is about 14,389 km from the recorded home. The behavior agent therefore requests further investigation. This demonstrates why FinSentry combines evidence rather than relying on one classifier.”

At 03:15 UTC, the time check compares the 02:00, 03:00 and 04:00 hour bands. Their combined historical share is about 1%, below the 5% rarity threshold. The distance is above both 300 km and the historical 95th percentile of about 123 km. The verification found 520 strictly earlier payments and no linked prior fraud cases. No unusual-amount finding was generated. This is a counterfactual demo input, not a transaction with a confirmed fraud label.

### 3. High-risk suspected fraud

“The trained model assigns approximately 99.99% risk to this transaction's combined characteristics. That exceeds both the 32.72% review cutoff and the policy's 80% high-risk escalation threshold. The system escalates it for a human decision. Its information coverage is only partly supported because there are six earlier customer payments.”

The verification found a new-merchant finding and a follow-up check. The amount is close to this customer's recent mean, so do not claim that a large amount alone caused the score. The original source example has `is_fraud=1`, checked after scoring; its label is never sent to the investigation API or used as an input feature. This is fraud in a synthetic simulation, not evidence of an actual person's wrongdoing.

## How the risk calculator actually works

There are two related outputs: the **model risk estimate** and the **final evidence-based action**. The final action is not just a conversion of the displayed percentage into a color.

1. The supervisor receives a label-free payment and starts the analysis.
2. The backend loads the selected customer's strictly earlier source and submitted payments. Future and same-timestamp payments are excluded.
3. The Transaction Risk Agent derives 17 features, transforms them with training-fitted preprocessing, and runs the saved LightGBM classifier. Its selected model uses 480 boosting iterations.
4. A separately fitted sigmoid calibration layer adjusts the classifier probability. The resulting score multiplied by 100 is the displayed **Automated risk indicator**.
5. The Customer Behavior Agent independently checks spending, frequency, time, device, merchant and location against that customer's history.
6. The Fraud Intelligence Agent checks exact customer/merchant links to earlier known simulated fraud cases, respecting outcome availability. A merchant link alone does not prove fraud.
7. The supervisor can request one follow-up when findings conflict. The decision policy combines the evidence. Groq writes the explanation from those findings; it does not choose the classifier score or override the saved recommendation.

The 17 model features are amount, log(amount + 1), UTC hour, weekday, merchant-to-home distance, earlier history count, preceding-hour count, preceding-24-hour count, 30-day mean, amount-to-mean ratio, 30-day standard deviation, amount z-score, seconds since previous payment, whether the merchant is new, whether the category is new, category, and merchant. Device novelty is an independent behavior check, not one of these 17 classifier features.

For the saved model, the numeric calculation is:

```text
x = training-fitted preprocessing(derived transaction/history features)
p_raw = saved_lightgbm.predict_proba(x)[fraud_class]
p = clip(p_raw, 0.0000001, 0.9999999)
logit = ln(p / (1 - p))
calibrated_risk = sigmoid(0.8461000394934468 * logit + 0.9240983807021317)
displayed_percentage = calibrated_risk * 100
```

Here `sigmoid(z) = 1 / (1 + exp(-z))`. This is a learned tree ensemble and calibration, not a manually chosen amount/location points formula. The model cutoff is `0.32717085825081416`, or about **32.72%**, selected to maximize F1 on the separate development threshold-selection partition, not on the held-out test set.

## The behavior rules and final action

- **Unusual amount:** amount exceeds three times the previous 30-day mean AND exceeds three standard deviations above that mean. Denominators have a floor of 1 for numerical stability.
- **High frequency:** at least five strictly earlier payments in the preceding hour.
- **Unusual time:** at least 60 prior payments in 90 days, with at most 5% in the circular three-hour band around the current UTC hour.
- **Unusual location:** merchant-to-home distance is above both 300 km and the customer's earlier 95th-percentile distance.
- **New merchant/device:** compared with strictly earlier history; device history is simulated.

With sufficient evidence:

| Evidence | Action |
|---|---|
| Model below cutoff, no behavior finding, no customer fraud-case link, no unresolved follow-up | CLEAR: No review trigger |
| Model above cutoff OR a behavior finding OR a prior customer fraud-case link, without a high-risk combination | FLAG: Investigate further |
| Model at least 80%, OR above cutoff with a serious behavior finding/customer fraud link, OR customer fraud link with a serious behavior finding | ESCALATE: High-risk human review |

Poor evidence coverage or unavailable intelligence can also cause ESCALATE with an **UNCERTAIN** assessment. An unresolved follow-up prevents clearance. Serious behavior findings here mean unusual amount, high frequency, unusual time or unusual location. Merchant association alone is not an automatic fraud finding.

**Well supported** describes evidence coverage, not probability that fraud is present. **Partly supported** means there are evidence limitations. Neither should be described as classifier accuracy.

## Explaining the screenshot with $309.93 and 0.26%

The classifier estimated 0.26%, below the 32.72% model cutoff. Separately, the behavior agent compared $309.93 with a previous 30-day mean of $77.82:

```text
309.93 / 77.82 = approximately 3.98, displayed as 4.0 times usual
```

The shown unusual-amount finding also means the code's standard-deviation condition was met. This independent finding requests investigation despite the low classifier probability. It does not change the classifier's numeric score.

## Rehearsal notes

- Run the low-risk, suspicious and high-risk presets in that order, keeping their inputs unchanged.
- Avoid editing customer history before the demonstration. These scores were verified against current history; adding/deleting earlier payments can change features and outputs. Repeating the exact same timestamp does not add those repetitions to its strictly earlier history.
- Do not use Sample 11 as a guaranteed middle case: its original customer produced CLEAR in this verification. The behavior preset above is the verified middle case.
- A reviewer choosing CLEAR, FLAG or ESCALATE records a separate human decision; it does not rewrite the original classifier score or retrain the model.
- Groq wording may vary or fall back to a factual template. The numeric model score and policy recommendation are computed independently of that wording.
- Demonstrating three selected examples illustrates the workflow, not accuracy over all payments. The classifier's held-out F1 is about 0.799; it does not establish real-bank performance or overall five-agent policy accuracy.

Relevant source: `backend/ml/sparkov_features.py`, `backend/ml/sparkov_predict.py`, `backend/ml/sparkov_train.py`, `backend/agents/sparkov_behavior.py`, `backend/agents/sparkov_decision.py`, and `backend/graph/sparkov_workflow.py`.
