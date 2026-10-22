# Data and model setup after cloning

The repository contains source, label-free demonstration inputs and evaluation metadata. Raw datasets, trained binary models, credentials, installed dependencies and local databases are excluded from handoff packages and Git.

1. Install Git, Python 3.12, Node.js 20+ and MySQL 8. Ensure `mysqld` is available on PATH for the Windows local database helper.
2. Clone https://github.com/AryanSheladia/FinSentry-AI after all four packages have reached `main`.
3. From the repository root, create and populate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
   npm --prefix frontend ci
   ```

4. Obtain the Sparkov source from [the Kaggle dataset](https://www.kaggle.com/datasets/kartik2112/fraud-detection) under its applicable terms. Put the extracted `fraudTrain.csv` and `fraudTest.csv` into `dataset\sparkov\`. No Kaggle account credentials belong in Git.
5. With the backend stopped, build the model and read-only historical source store:

   ```powershell
   .\.venv\Scripts\python.exe -m backend.ml.sparkov_train
   ```

   This creates `models/sparkov_v2/pipeline.joblib` and `runtime/sparkov/history.sqlite`, and updates the matching metadata and generated demo examples. Keep the binary model and history database local. The checked-in model metadata describes the originally verified build; a new training run has its own timestamp and manifest.

6. Run `.\.venv\Scripts\python.exe scripts\local_mysql.py start` to create/reuse this clone's local database configuration. The helper writes private generated credentials into ignored local files. It must verify ownership before using a database already listening on port 3307. Run one project clone at a time when using that port; retain the existing working `E:\FinSentry` setup for the demonstration.
7. Add your Groq key only to the root private `.env` as `GROQ_API_KEY=...`. Use the existing selected model `openai/gpt-oss-20b`. Never put the key into `.env.example` or any `VITE_` variable. Without a key the factual explanation fallback remains available.
8. Build and launch:

   ```powershell
   npm --prefix frontend run build
   python start_backend.py
   ```

   Open http://127.0.0.1:8000. The terminal remains active and shows request status logs; Ctrl+C stops the backend. For frontend development, run `npm --prefix frontend run dev` in another terminal and open http://127.0.0.1:5173.

9. After data/model setup, verify:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests -q
   npm --prefix frontend test
   npm --prefix frontend run build
   ```

   `FINSENTRY_TEST_MYSQL=1` opts into tests that create and clean up their own local MySQL test records. Start only when no investigation is in progress. Do not treat a source-only partial upload as a runnable full application; all four packages are needed.

The history/store generation preserves strict chronological features and keeps test labels out of history/intelligence. Calibration and threshold selection use separate development partitions. The published test F1 of about 0.799 measures the saved synthetic-data classifier, not real-bank accuracy or complete agent-policy accuracy.

For exact demonstration inputs see `reports/DEMO_THREE_CASES.md`. Package review notes are in `docs/reviews/` and must be filled by the people who actually perform those reviews.
