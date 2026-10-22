# FinSentry — analyst walkthrough

Start: `& .\scripts\start_project.ps1` from E:\FinSentry. Open http://127.0.0.1:8000. Development commands and fresh setup are in README.md.

## Overview and monitoring

Overview shows recent cases, outstanding attention, escalations and cases cleared by an analyst. Click a count to open the matching queue. The list contains up to the latest 100 submitted cases and refreshes every 20 seconds while visible. It is not a live bank feed.

Review queue supports searching case/customer/merchant and filtering all cases, needs attention, escalations or recorded reviews. Escalations and unreviewed cases appear first. A follow-up or escalation remains outstanding after recording that action; it becomes analyst-cleared only after an explicit clearance.

## Investigate a payment

Choose **Investigate payment**. Load a demo payment or edit customer, amount, UTC timestamp, merchant and category. Location is summarized as distance from the recorded home; use **Edit location** to change coordinates. Device reference is optional under **Device information**. New customers require home coordinates and receive missing-history findings.

Choose **Unusual time and location · normal amount** to reproduce the controlled example: USD 47.72, 15 July 2020 03:15 UTC, a known customer, distant Sydney merchant coordinates. The amount is normal, while the rare hour and distant location produce an investigation recommendation. Detailed inputs and saved result: TIME_LOCATION_WALKTHROUGH.md.

Demo history covers 21 June 2020 12:14:25 UTC to 31 December 2020 23:59:34 UTC. An outside date causes uncertainty, which is separate from an unusual customer spending hour. All supported payments are USD cards in a simulated environment.

## Read a case and review it

The case opens after submission. Start with the recommended action and why attention is needed. Risk indicator is a model estimate; information availability describes supporting history. Neither is a guarantee of fraud or safety. Check the spending comparison and eligible earlier cases. An absent prior case does not prove safety; a merchant association alone does not prove wrongdoing.

Record your name, explicitly choose a review decision, and add notes. This saves a separate review record. It does not change the original assessment, execute a payment action, automatically confirm fraud or retrain the model.

Developer architecture, model evaluation and runtime settings are documented outside the website. Keys stay in private root .env. The site deliberately omits API links, raw feature JSON, package/provider labels, model benchmark cards and internal graph node names.

Browser visual QA remains unavailable; backend integration, server-rendered interface logic and production build checks are recorded in analyst_workspace_verification.json.
