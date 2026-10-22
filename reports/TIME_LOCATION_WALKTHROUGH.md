# Normal amount, unusual time and location — verified 22 October 2026

The screenshot's escalation had two distinct reasons: 21 June 2020 03:27:10 UTC is before the evaluated test start (21 June 2020 12:14:25 UTC), and USD 1,000 was 18.8 times that customer's prior 30-day mean. Its approximately 1% model score was below the 32.72% model threshold. The old Groq wording incorrectly described this as a high model risk. Stored historical explanations are preserved; new explanations separate model risk from the combined assessment and reject common contradictory model claims.

## Open the verified result

http://127.0.0.1:8000/?investigation=SPINV_3eb2259f81e7444d8b79c3364be82f08

Or refresh **New payment**, select **Unusual time + distant location · normal amount** from **Start with an example**, and submit. The left form now loads the actual saved payment when a saved result is opened.

| Input | Value |
|---|---|
| Customer | CUST_00686b4dd6551bfe |
| Amount | USD 47.72 — prior 30-day median, not an unusual amount |
| Timestamp | 2020-07-15 03:15:00 UTC — within the evaluated period |
| Merchant | fraud_Lockman, West and Runte |
| Category | grocery_pos |
| Merchant latitude / longitude | -33.8688 / 151.2093 — Sydney |
| Device | SIM_DEVICE_00686b4dd6551bfe — unchanged simulated device |

The customer, merchant and device were chosen from existing source history; time and location are counterfactual simulation inputs. No fraud label or score was supplied or forced. This tests evidence routing, not whether a real payment is fraudulent.

## What the agents found

- **UNUSUAL_TIME:** Only 1 of 99 strictly earlier payments in the prior 90 days occurred during hours 02, 03 or 04 UTC (1.0%). The new rule requires at least 60 historical payments and a three-hour window share at or below 5%. Hours wrap across midnight. A night payment is not automatically unusual for every customer.
- **UNUSUAL_LOCATION:** Merchant is approximately 14,389 km from the recorded home, above both 300 km and that customer's prior 95th-percentile distance (123 km).
- **No UNUSUAL_AMOUNT** finding.
- Model risk approximately **0.0164%**, below the **32.72%** model threshold.
- Combined recommendation **FLAG**, with **HIGH evidence confidence**. Behavior evidence causes the flag even though the classifier score is low. High confidence means evidence coverage within the simulation, not certainty of fraud.

## Live controls — same normal amount in every case

| Case | UTC hour | Location | Behavior findings | Recommendation |
|---|---|---|---|---|
| Normal control | 22:15 | Recorded home area | None | CLEAR |
| Unusual time | 03:15 | Recorded home area | UNUSUAL_TIME | FLAG |
| Unusual location | 22:15 | Sydney | UNUSUAL_LOCATION | FLAG |
| Both | 03:15 | Sydney | UNUSUAL_TIME, UNUSUAL_LOCATION | FLAG |

All four completed through the actual API/MySQL workflow. Three used actual Groq explanations. The time-only case used a labeled template fallback because provider output failed validation. Neither fallback nor LLM changes the deterministic recommendation. New narratives begin with a server-rendered model score/threshold/combined-action statement. The contradiction guard covers common model-risk claims, not an exhaustive semantic proof of every LLM sentence.

Machine-readable inputs/results/IDs: `reports/time_location_test.json`. Reproducible script: `scripts/test_time_location.py`. Source histories and model weights were not changed. The classifier's existing evaluation metrics remain unchanged; no full-policy F1 is claimed for the added behavior rule.

**Verification:** 67 tests pass, including time/location controls, history cutoffs, midnight wrapping, minimum history and contradictory explanation rejection. TypeScript/Vite build passes. Saved result, preset and built assets verified over HTTP after backend restart. Browser visual QA remains unavailable because the automation kernel cannot initialize.
