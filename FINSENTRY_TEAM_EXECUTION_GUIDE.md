# FinSentry AI — current execution guide

Updated: 23 October 2026. Workspace: E:\FinSentry. Implementation is sequential and Codex-assisted on Aryan's device. Member names identify assigned scopes, not proof of individual authorship or equal contribution.

| Assigned package | Current state | Evidence |
|---|---|---|
| Parth — data and model | Complete | Sparkov causal features, chronological validation/calibration/threshold partitions, saved model, test F1 0.7990 |
| Aryan — input, history and persistence | Complete | Validated new-payment API, source/submitted prior histories, MySQL saved cases/reviews, restart handling |
| Yash — coordination and evidence | Complete | Supervisor, parallel risk/behavior branches, prior known entity links, bounded follow-up, combined recommendations and Groq explanations |
| Pratik — analyst interface and integration | Complete for local use | Overview, prioritized/filterable review queue, readable evidence and explicit human decisions; startup/build and automated checks |

## Analyst workflow

Demo preparation complete: `reports/DEMO_THREE_CASES.md` gives exact presets/inputs for CLEAR, FLAG and HIGH-risk ESCALATE, plus the model/calibration/policy explanation. All three were checked read-only with the current history and complete workflow; no new cases or model changes were made. `reports/demo_three_cases_verified.json` records outputs. The source labels for the selected low/high examples were checked only after scoring, not supplied as features.

1. Run `& .\scripts\start_project.ps1`; open http://127.0.0.1:8000.
2. Overview shows the latest 100 cases, needs-attention count, escalations and analyst-cleared cases.
3. Open a case to read the recommendation and evidence. An automated no-trigger result is not a human clearance.
4. Record your name, decision and notes. Follow-up and escalated cases stay outstanding until cleared by an analyst.
5. Investigate payment accepts a new label-free USD card payment. Demo examples can populate the form, including the normal-amount unusual-time/location case.
6. Review queue has a **Delete** action with a payment-specific confirmation. It permanently removes the submitted transaction, its cases and review notes together; active investigations must finish first. Source training data stays unchanged.

Follow-up complete (22 October 2026): Aryan's persistence scope now includes an atomic deletion API, related-record cleanup and active-case protection. Pratik's interface scope now includes the queue delete button, confirmation, progress/error feedback and refreshed case counts. Implementation remains Codex-assisted on Aryan's device. Verification: 10 deletion API checks passed across SQLite/MySQL; frontend checks and production build passed. Browser checks verified the queue button and confirmation; screenshot capture timed out after the confirmation was cancelled.

Runtime follow-up complete (22 October 2026): the running backend still exposed only GET for saved cases, so earlier delete attempts had not removed records. Restarted the foreground launcher with current code and verified a disposable payment, case and review were deleted through the actual HTTP API, absent from direct/frontend-proxy lists, and absent from MySQL. Existing 20 payments/cases and 3 reviews were preserved. The interface now explains that nothing was deleted if an older backend rejects DELETE. Eight frontend tests and the production build passed. Evidence: `reports/delete_runtime_fix.json`.

## Current implementation facts

- 23 October 2026: read-only classifier audit complete in Parth's assigned model scope, with risk-policy findings relevant to Yash's scope. Full 555,719-row test evaluation reproduced; accuracy 99.8508%, precision 83.2323%, recall 76.8298%, F1 0.79903. No model, threshold, policy or live cases were changed. See `reports/MODEL_ACCURACY_REVIEW.md` and `reports/model_accuracy_audit.json` for calibration, monthly diagnostics and measured cutoff tradeoffs. Work remains Codex-assisted on Aryan's device.
- 1,852,394 Sparkov transactions; 7,506 development fraud cases with simulated outcome availability.
- Classifier test F1 0.7990 / precision 0.8323 / recall 0.7683. Full policy accuracy is not represented by these metrics.
- Risk indication and evidence coverage are separate. Missing history never means normal behavior.
- Time anomalies require at least 60 earlier payments in 90 days and a rare circular three-hour band (at most 5%).
- Location checks compare merchant-home distance with 300 km and the customer's earlier 95th percentile.
- UI omits developer internals, raw feature vectors, implementation names, model benchmarking and database details.
- Case list refreshes every 20 seconds while visible. This is submitted simulation data, not live bank monitoring.

## Cleanup and handoff

Submission execution trace captured (23 October): Yash's assigned coordination scope was exercised through the unchanged production LangGraph, trained model, read-only source history and configured Groq explanation model. Run `TRACE_6e809586a00c4aafbbe432e008bdec02` captured actual node-state updates, the parallel branch join, one merchant-activity follow-up and an ESCALATE/HIGH result with MEDIUM evidence coverage. Full JSON, JSONL node updates, readable log and form-ready text are saved in `output/execution_trace/`; reproduction helper: `scripts/capture_execution_trace.py`. This was a fresh direct workflow run, not an HTTP submission or saved MySQL case. No model, policy, existing cases or reviews were changed. Capture preparation remains Codex-assisted on Aryan's device.

Submission documentation complete (23 October): PDF synopsis and design document are saved in `output/pdf/`. Both include the supplied student names and PRNs on the first page and use embedded Times New Roman. The synopsis has three paragraphs plus a cover (2 pages total); the design includes architecture, all five agents, shared-state orchestration, communication, technology choices, data handling and evaluation limits (8 pages total). All 10 PDF pages were visually checked; both files are under 10 MB. No application, model, database or GitHub repository changes were made for this document task.

GitHub update (23 October): after the folder-only Parth/Pratik swap, Pratik pushed the first data/model package. Aryan's 25-file API/persistence package is now published on `main` in eight focused commits (`c61a1a7` through `95f64fa`), using the existing AryanSheladia Git identity and actual timestamps. Pratik's existing paths were preserved. Available partial-checkout checks: 7 passed, 5 optional MySQL checks skipped; full integration awaits Yash's workflow and Parth's final frontend package. GitHub confirms the published commit is associated with AryanSheladia. Current upload order is **Pratik → Aryan → Yash → Parth**; Yash is next. Legacy handoff receipt filenames remain compatible with the originally prepared packages. The assisted-check record is published at `docs/reviews/Aryan.md`. No working demo model or database was modified.

GitHub handoff preparation (23 October): user selected **packages only**, with each member pushing their assigned source in order (Parth → Aryan → Yash → Pratik) to `AryanSheladia/FinSentry-AI`, branch `main`. `docs/GITHUB_HANDOFF.md` explains safe application, real-account commits and review records. `scripts/create_team_handoffs.py` creates disjoint source ZIPs without committing, pushing, inventing identities or recording unfinished reviews as completed. Raw datasets, model binaries, credentials, runtime databases, backups, dependencies and generated frontend builds stay local; reconstruction steps are in `docs/DATA_AND_MODEL_SETUP.md`. Review templates are intentionally unfilled for the actual reviewers.

The retired workflow is no longer in startup, active source, data or website navigation. Its files were moved to recoverable `runtime/retired-backup-20261022` after automatic approval review rejected broad irreversible deletion without backup. Sparkov data/model and saved reviews were preserved. Details: `reports/retired_store_cleanup.json` and the archive manifest.

Current guides: `README.md`, `reports/SPARKOV_DEMO_GUIDE.md`, `reports/TIME_LOCATION_WALKTHROUGH.md`, `reports/architecture.md`. Tests cover the active system; retired workflow tests are archived alongside the retired implementation. Browser visual QA remains unavailable because the automation kernel cannot initialize. Container deployment and production access controls are not claimed complete.
