# FinSentry — current Sparkov implementation

Updated 22 October 2026. All four assigned work packages are implemented locally with Codex assistance on Aryan's laptop. Parth: data/model. Aryan: input/history/persistence. Yash: coordination/evidence. Pratik: analyst UI/integration. These allocations are not claims of separate human authorship.

The active system uses 1,852,394 Sparkov transactions, shared causal features, three validation-selected candidates, separate calibration/threshold slices, and later test F1 0.7990, precision 0.8323, recall 0.7683, AP 0.8686. Artifacts: models/sparkov_v2 and reports/sparkov_training.json. The source SQLite store is read-only; MySQL saves new payments, cases and reviews. Historical fraud intelligence has 7,506 development cases with a simulated 24-hour outcome delay.

Five coordinating agents combine learned transaction risk, customer history and prior known entity links. Conflicts trigger one bounded follow-up. Behavior includes unusual amount, frequency, time, location, device and merchant checks. Known test controls demonstrate normal-amount time and location findings separately and together. Groq explains recorded evidence with validated fields, contradiction checks and factual fallback. Evidence coverage is distinct from calibrated simulation model risk.

The current analyst UI has Overview, Review queue and Investigate payment. It displays recommendations and readable findings instead of implementation internals. Review status distinguishes follow-up, senior escalation and analyst clearance. Latest 100 cases refresh every 20 seconds while visible.

Retired assets are no longer active and reside recoverably in runtime/retired-backup-20261022; its manifest records the move. Obsolete database tables were removed with Sparkov row counts checked before/after. Startup requires only the active model/history. No retired model or embedding index is loaded.

Verification: see analyst_workspace_verification.json and browser_qa.md. Earlier test counts in historical reports concern earlier snapshots; current tests exercise the active system after retired tests were archived. No browser visual QA, production access controls, durable task resume, container runtime or real-world fraud accuracy is claimed.
