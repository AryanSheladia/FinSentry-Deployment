# FinSentry AI — Deployment

FinSentry investigates simulated USD card payments using a trained LightGBM classifier, customer-history comparisons, historical fraud entity links and a five-agent LangGraph workflow. Analysts receive an evidence-based CLEAR, FLAG or ESCALATE recommendation and can record a human review. No money is moved or blocked.

This repository contains the complete deployment source. The team's submission repository remains [FinSentry-AI](https://github.com/AryanSheladia/FinSentry-AI).

## Architecture

The root Dockerfile builds the React website and serves it with FastAPI on a single public origin. The Supervisor delegates to parallel Risk and Behavior branches, joins their outputs, checks Fraud Intelligence, performs at most one follow-up and sends the accumulated evidence to Decision & Explanation. Groq generates the explanation from fixed assessment facts; a factual template is used when the provider is unavailable.

MySQL stores submitted payments, investigations and reviews. The read-only SQLite source history is a separate packaged artifact, not the case database. Use one application replica and one Uvicorn worker because background investigations are managed within the process.

## Deploy on Render with Aiven MySQL

Railway new sign-ups were unavailable during preparation, so Render + Aiven is provided as a compatible fallback. Both the Render blueprint (`render.yaml`) and Railway configuration (`railway.json`) use the same Docker image and trained assets.

1. Create an Aiven **Free MySQL** service and wait until it is running. Use its service host, port, user, password and database name. Save its CA certificate; do not disable TLS verification.
2. Create a Render web service from this repository using the root Dockerfile and Free compute, or import `render.yaml` as a blueprint.
3. Set private environment variables `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLDATABASE`, and `MYSQL_SSL_CA_BASE64` (base64 of the CA certificate). Set `GROQ_API_KEY` using your own key, and `GROQ_MODEL=openai/gpt-oss-20b`. Do not put these values into Git or frontend variables.
4. Leave the Docker command at its default (`python deployment/start.py`). The launcher configures a correctly escaped SQLAlchemy connection, waits for MySQL and starts FastAPI on the host-assigned `PORT`.
5. Use `/health` as the deployment health check. Open the service's public HTTPS URL and check the three demonstration cases in `reports/DEMO_THREE_CASES.md`.

Render's Free web service sleeps after inactivity and can take time to wake up; it has limited memory. Aiven's free MySQL has limited storage. This is a student demo deployment, not a high-availability banking service. Keep the deployment available throughout evaluation and verify the host's current limits. The public workspace contains simulated data only; analyst authentication and access controls are required before using any real customer data.

## Deploy on Railway

When account sign-up is available, create a project with a MySQL service and an application service linked to this GitHub repository. Reference the MySQL service's `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD` and `MYSQLDATABASE` variables from the application. Configure the Groq key privately, retain one application replica, and generate a public domain. Do not expose the database to the public internet when using Railway's private networking. Review pricing before activating any paid plan.

## Trained artifacts

The existing model and matching source history are published as the `artifacts-v1` GitHub release. `deployment/artifacts.lock.json` pins the archive URL, sizes and SHA-256 hashes. The Docker build downloads and verifies that release without retraining. Raw Kaggle CSVs, live MySQL files, previous submitted cases and credentials are excluded. All three restored file paths are explicitly allowlisted.

To restore artifacts into a local checkout:

```powershell
python deployment/restore_artifacts.py
```

To rebuild the exact release archive from the original prepared project:

```powershell
python deployment/build_artifacts.py --source E:\FinSentry --output E:\FinSentry\runtime\deployment-assets
```

The model's simulated-data test F1 is approximately 0.7990. That metric describes the classifier, not real-bank performance or the accuracy of every final policy decision. Unknown history, unsupported dates and missing evidence affect the final assessment independently of the model score.

## Verification

GitHub Actions installs the pinned Python dependencies on Linux, checks and builds the frontend, restores the verified artifacts, runs the tests and builds the Docker image. Artifact hashes and the model/source-store build manifests must match.

The original local setup instructions are retained in `docs/DATA_AND_MODEL_SETUP.md`. Local execution uses `python start_backend.py` after preparing the model/history, frontend and local MySQL service.

## Dataset

Sparkov-based simulated card-payment data: [Kaggle dataset](https://www.kaggle.com/datasets/kartik2112/fraud-detection). Customer identifiers are hashed, source transaction history excludes fraud labels and personal names, and historical fraud evidence comes only from development labels with simulated outcome delay. Seeded device identifiers are simulated context, not observed fraud-device intelligence.
