"""Versioned Sparkov training and offline evidence store."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import time

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from backend.ml.sparkov_features import FEATURES, NUMERIC, batch_features, preprocessor
from backend.ml.evaluation import evaluate, select_threshold, sha256, write_json

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "models/sparkov_v2"
STORE = ROOT / "runtime/sparkov/history.sqlite"
COLUMNS = ["trans_date_trans_time", "cc_num", "merchant", "category", "amt", "lat", "long",
           "merch_lat", "merch_long", "is_fraud", "trans_num"]


def load_source():
    frames, provenance = [], {}
    for filename, partition in [("fraudTrain.csv", "development"), ("fraudTest.csv", "test")]:
        path = ROOT / "dataset/sparkov" / filename
        frame = pd.read_csv(path, usecols=COLUMNS, dtype={"cc_num": "string"})
        frame["customer_id"] = frame.cc_num.map(lambda v: "CUST_"+hashlib.sha256(str(v).encode()).hexdigest()[:16])
        frame = frame.drop(columns="cc_num").rename(columns={"amt":"amount", "lat":"home_lat", "long":"home_lon",
            "merch_lat":"merchant_lat", "merch_long":"merchant_lon", "is_fraud":"label", "trans_num":"transaction_id"})
        frame["timestamp"] = pd.to_datetime(frame.pop("trans_date_trans_time"), utc=True).astype("int64")//10**9
        frame["partition"] = partition
        provenance[filename] = {"rows": len(frame), "fraud_rows": int(frame.label.sum()), "sha256": sha256(path),
                                "min_timestamp": int(frame.timestamp.min()), "max_timestamp": int(frame.timestamp.max())}
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True).sort_values(["timestamp", "transaction_id"], kind="stable").reset_index(drop=True)
    if data.transaction_id.duplicated().any() or frames[0].timestamp.max() >= frames[1].timestamp.min():
        raise ValueError("Expected unique transactions and strictly later test data")
    if (data.amount <= 0).any() or data[["customer_id","merchant","category","timestamp","amount","home_lat","home_lon","merchant_lat","merchant_lon"]].isna().any().any():
        raise ValueError("Invalid source")
    return data, provenance


def calibrated(raw, calibrator):
    logits = np.log(np.clip(raw, 1e-7, 1-1e-7)/(1-np.clip(raw, 1e-7, 1-1e-7)))
    return calibrator.predict_proba(logits.reshape(-1, 1))[:, 1]


def main():
    started = time.perf_counter()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    STORE.parent.mkdir(parents=True, exist_ok=True)
    print("Loading Sparkov; hashing source files...", flush=True)
    data, source = load_source()
    print("Building strictly prior customer features...", flush=True)
    features = batch_features(data)
    development = np.flatnonzero(data.partition.eq("development"))
    boundaries = [int(data.iloc[development[int(len(development)*fraction)]].timestamp) for fraction in (.70,.85,.925)]
    times = data.timestamp.to_numpy()
    dev = data.partition.eq("development").to_numpy()
    groups = {"train": dev & (times<boundaries[0]), "validation": dev & (times>=boundaries[0]) & (times<boundaries[1]),
              "calibration": dev & (times>=boundaries[1]) & (times<boundaries[2]),
              "threshold": dev & (times>=boundaries[2]), "test": ~dev}
    prep = preprocessor()
    xtrain = prep.fit_transform(features.loc[groups["train"]])
    xval = prep.transform(features.loc[groups["validation"]])
    labels = data.label.to_numpy()
    candidates = []
    best = None
    for leaves, weight in [(31,1.), (63,1.), (63,4.)]:
        model = lgb.LGBMClassifier(n_estimators=1800, learning_rate=.04, num_leaves=leaves,
            min_child_samples=60, colsample_bytree=.9, reg_lambda=2., scale_pos_weight=weight,
            random_state=42, n_jobs=4, deterministic=True, force_col_wise=True, verbosity=-1, metric="average_precision")
        model.fit(xtrain, labels[groups["train"]], eval_set=[(xval,labels[groups["validation"]])],
            categorical_feature=list(range(len(NUMERIC),len(FEATURES))),
            callbacks=[lgb.early_stopping(80, first_metric_only=True, verbose=False)])
        score = model.predict_proba(xval)[:,1]
        threshold = select_threshold(labels[groups["validation"]], score)
        metrics = evaluate(labels[groups["validation"]], score, threshold)
        record = {"num_leaves":leaves,"scale_pos_weight":weight,"best_iteration":model.best_iteration_,"validation":metrics}
        candidates.append(record)
        print(json.dumps(record), flush=True)
        if best is None or metrics["f1"] > best[0]:
            best = (metrics["f1"],model,record)
    model = best[1]
    calibration_raw = model.predict_proba(prep.transform(features.loc[groups["calibration"]]))[:,1]
    logits = np.log(np.clip(calibration_raw,1e-7,1-1e-7)/(1-np.clip(calibration_raw,1e-7,1-1e-7)))
    calibrator = LogisticRegression(C=1e3, random_state=42).fit(logits.reshape(-1,1),labels[groups["calibration"]])
    threshold_scores = calibrated(model.predict_proba(prep.transform(features.loc[groups["threshold"]]))[:,1],calibrator)
    threshold = select_threshold(labels[groups["threshold"]],threshold_scores)
    # The supplied later test partition is first evaluated only after all selection is fixed.
    test_scores = calibrated(model.predict_proba(prep.transform(features.loc[groups["test"]]))[:,1],calibrator)
    metrics = {"threshold": evaluate(labels[groups["threshold"]],threshold_scores,threshold),
               "test": evaluate(labels[groups["test"]],test_scores,threshold)}
    metrics["test"]["brier_score"] = float(brier_score_loss(labels[groups["test"]],test_scores))
    metrics["test"]["log_loss"] = float(log_loss(labels[groups["test"]],test_scores))
    created = pd.Timestamp.now(tz="UTC").isoformat()
    metadata = {"model_version":"sparkov-v2", "trained_at_utc":created, "features":FEATURES,
        "threshold":threshold,"score_type":"sigmoid_calibrated_simulation_probability", "source":source,
        "selected":best[2],"candidates":candidates,"metrics":metrics,
        "splits":{k:{"rows":int(v.sum()),"fraud_rows":int(labels[v].sum()),"min_timestamp":int(times[v].min()),"max_timestamp":int(times[v].max())} for k,v in groups.items()},
        "history_policy":"Strictly earlier unlabeled transactions; earlier test features may inform later test payments; no test labels in history/intelligence",
        "case_policy":"Development fraud rows only, available 24h after event; delay is a simulation assumption",
        "simulated_context":"Stable per-customer SIM_DEVICE and CARD payment method; not ML input; not observed source fields",
        "limitations":["Synthetic card-payment environment, not validated for real banking, UPI or transfers",
                        "Calibration measured on this simulation; score is not evidence-confidence",
                        "No raw customer IDs, names, dates of birth or addresses used as predictive features"],
        "elapsed_seconds":round(time.perf_counter()-started,2)}
    joblib.dump({"preprocess":prep,"model":model,"calibrator":calibrator,"metadata":metadata},ARTIFACTS/"pipeline.joblib",compress=3)
    metadata["bundle_sha256"] = sha256(ARTIFACTS/"pipeline.joblib")
    write_json(ARTIFACTS/"metadata.json", metadata)
    export_data(data,metadata,test_scores)


def export_data(data,metadata,test_scores):
    print("Writing versioned historical feature/evidence store...",flush=True)
    dev=data.partition.eq("development").to_numpy()
    # Build beside any previous store, so reruns never expose partially written history.
    pending = STORE.with_suffix(".building.sqlite")
    if pending.exists():
        pending.unlink()
    with sqlite3.connect(pending) as connection:
        public = data.drop(columns=["label", "partition"]).copy()
        public["device_id"] = "SIM_DEVICE_"+public.customer_id.str.removeprefix("CUST_")
        public["payment_method"] = "CARD"
        public.to_sql("transactions",connection,index=False,chunksize=10000)
        connection.execute("CREATE UNIQUE INDEX tx_id ON transactions(transaction_id)")
        connection.execute("CREATE INDEX tx_customer_time ON transactions(customer_id,timestamp)")
        connection.execute("CREATE INDEX tx_merchant_time ON transactions(merchant,timestamp)")
        customers = public.drop_duplicates("customer_id")[["customer_id","home_lat","home_lon","device_id","timestamp"]]
        customers.to_sql("customers",connection,index=False)
        connection.execute("CREATE UNIQUE INDEX customer_id ON customers(customer_id)")
        cases = data.loc[dev & data.label.eq(1)].drop(columns=["label","partition"]).copy()
        cases["case_id"] = "SPCASE_"+cases.transaction_id
        cases["known_at"] = cases.timestamp+86400
        cases.to_sql("cases",connection,index=False)
        connection.execute("CREATE INDEX case_customer_time ON cases(customer_id,known_at)")
        connection.execute("CREATE INDEX case_merchant_time ON cases(merchant,known_at)")
        connection.execute("CREATE INDEX case_category_time ON cases(category,known_at)")
        connection.execute("CREATE TABLE artifact_metadata (metadata_json TEXT NOT NULL)")
        connection.execute("INSERT INTO artifact_metadata VALUES (?)",(json.dumps({"trained_at_utc":metadata["trained_at_utc"],"source":metadata["source"]}),))
    connection.close()
    pending.replace(STORE)
    test = data.loc[~dev]
    order = np.argsort(test_scores,kind="stable")
    examples = []
    for index in np.unique(np.linspace(0,len(order)-1,12).astype(int)):
        row = test.iloc[int(order[index])].drop(labels=["label","partition"]).to_dict()
        row["device_id"] = "SIM_DEVICE_"+row["customer_id"].removeprefix("CUST_")
        row["payment_method"] = "CARD"
        examples.append(row)
    write_json(ROOT/"data/sparkov/examples.json",{"source":"Score quantiles, labels not used for selection; not an evaluation set","transactions":examples})
    write_json(ROOT/"reports/sparkov_training.json",metadata)
    print(json.dumps({"metrics":metadata["metrics"],"threshold":metadata["threshold"],"elapsed_seconds":metadata["elapsed_seconds"]}),flush=True)


if __name__ == "__main__":
    main()
