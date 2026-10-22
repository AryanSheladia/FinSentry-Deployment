r"""Re-evaluate the saved classifier without retraining or changing the live store.

Run: .venv\Scripts\python.exe scripts/audit_sparkov_model.py
Writes aggregate diagnostics only to reports/model_accuracy_audit.json.
"""
from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss

from backend.ml.evaluation import evaluate, sha256, write_json
from backend.ml.sparkov_features import FEATURES, batch_features
from backend.ml.sparkov_train import ARTIFACTS, calibrated, load_source


def calibration_bins(labels, scores):
    boundaries = [0, .001, .01, .05, .1, .2, .32717085825081416, .5, .8, .95, 1.0000001]
    rows = []
    for lower, upper in zip(boundaries[:-1], boundaries[1:]):
        mask = (scores >= lower) & (scores < upper)
        if mask.any():
            rows.append({"min_score": lower, "max_score_exclusive": upper,
                         "count": int(mask.sum()), "mean_prediction": float(scores[mask].mean()),
                         "observed_fraud_rate": float(labels[mask].mean())})
    return rows


def main():
    started = time.monotonic()
    metadata = json.loads((ARTIFACTS / "metadata.json").read_text(encoding="utf-8"))
    before_hash = sha256(ARTIFACTS / "pipeline.joblib")
    if before_hash != metadata["bundle_sha256"]:
        raise ValueError("Saved model does not match its evaluation metadata")
    bundle = joblib.load(ARTIFACTS / "pipeline.joblib")
    print("Loading source and checking hashes; no training or database writes...", flush=True)
    data, provenance = load_source()
    if provenance != metadata["source"]:
        raise ValueError("Dataset differs from the saved evaluation source")
    print("Rebuilding causal features and evaluating the fixed saved model...", flush=True)
    features = batch_features(data)
    model, prep, calibrator = (bundle[name] for name in ("model", "preprocess", "calibrator"))
    test_mask = data.partition.eq("test").to_numpy()
    y = data.loc[test_mask, "label"].to_numpy()
    raw = model.predict_proba(prep.transform(features.loc[test_mask]))[:, 1]
    scores = calibrated(raw, calibrator)
    threshold = metadata["threshold"]
    metrics = evaluate(y, scores, threshold)
    metrics.update(accuracy=float(accuracy_score(y, scores >= threshold)),
                   balanced_accuracy=float(balanced_accuracy_score(y, scores >= threshold)),
                   brier_score=float(brier_score_loss(y, scores)), log_loss=float(log_loss(y, scores)))
    if metrics["confusion_matrix"] != metadata["metrics"]["test"]["confusion_matrix"]:
        raise ValueError("Recomputed confusion matrix differs from the stored evaluation")
    if abs(metrics["average_precision"] - metadata["metrics"]["test"]["average_precision"]) > 1e-10:
        raise ValueError("Recomputed ranking differs from the stored evaluation")

    # Compare prespecified operating points; these are diagnostics, not test-set tuning.
    times = data.timestamp.to_numpy()
    threshold_split = metadata["splits"]["threshold"]
    dev_mask = data.partition.eq("development").to_numpy() & (times >= threshold_split["min_timestamp"]) & (times <= threshold_split["max_timestamp"])
    y_dev = data.loc[dev_mask, "label"].to_numpy()
    dev_scores = calibrated(model.predict_proba(prep.transform(features.loc[dev_mask]))[:, 1], calibrator)
    operating_points = []
    for value in [.05, .1, .2, threshold, .5, .8]:
        operating_points.append({"threshold": value, "development": evaluate(y_dev, dev_scores, value),
                                 "existing_test_diagnostic": evaluate(y, scores, value)})
    monthly = []
    months = pd.to_datetime(data.loc[test_mask, "timestamp"], unit="s", utc=True).dt.strftime("%Y-%m").to_numpy()
    for month in sorted(set(months)):
        mask = months == month
        monthly.append({"month": month, "rows": int(mask.sum()), "fraud_rows": int(y[mask].sum()),
                        "metrics": evaluate(y[mask], scores[mask], threshold)})
    gains = model.booster_.feature_importance(importance_type="gain")
    importance = sorted([{"feature": name, "gain_share": float(gain / gains.sum())}
                         for name, gain in zip(FEATURES, gains)], key=lambda row: row["gain_share"], reverse=True)
    fraud_rate = float(y.mean())
    after_hash = sha256(ARTIFACTS / "pipeline.joblib")
    if after_hash != before_hash:
        raise ValueError("Model changed during audit")
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "model_version": metadata["model_version"],
              "model_sha256_verified": before_hash, "dataset_provenance_verified": True,
              "stored_evaluation_reproduced": True, "test_rows": len(y), "test_fraud_rows": int(y.sum()),
              "test_fraud_prevalence": fraud_rate, "always_nonfraud_accuracy": 1-fraud_rate,
              "always_nonfraud_recall": 0.0, "threshold": threshold, "test_metrics": metrics,
              "raw_probability_metrics": {"brier_score": float(brier_score_loss(y, raw)), "log_loss": float(log_loss(y, raw))},
              "calibration_bins": calibration_bins(y, scores), "operating_point_diagnostics": operating_points,
              "monthly_test_diagnostics": monthly, "training_gain_importance_not_causal_explanation": importance,
              "full_agent_policy_evaluated": False, "model_or_database_modified": False,
              "limitations": ["Synthetic card-payment data; real-world performance is unverified.",
                              "Classifier metrics do not measure full multi-agent review policy.",
                              "Current test set has now been inspected; future tuning needs a fresh time holdout.",
                              "Threshold comparisons are diagnostics. No new operating point was selected or deployed.",
                              "Gain importance is descriptive; it does not measure generalization or causal effects."],
              "elapsed_seconds": round(time.monotonic()-started, 2)}
    write_json(ROOT / "reports/model_accuracy_audit.json", report)
    print(json.dumps({"test_rows": len(y), "metrics": metrics, "always_nonfraud_accuracy": 1-fraud_rate,
                      "elapsed_seconds": report["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
