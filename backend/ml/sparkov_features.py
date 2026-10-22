"""Shared causal features: all history timestamps must be strictly before the payment."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OrdinalEncoder

NUMERIC = ["amount", "log_amount", "hour", "weekday", "home_distance_km", "history_count",
           "count_1h", "count_24h", "mean_30d", "amount_ratio_30d", "std_30d", "amount_z_30d",
           "seconds_since_previous", "new_merchant", "new_category"]
CATEGORICAL = ["category", "merchant"]
FEATURES = NUMERIC + CATEGORICAL


def distance(lat1, lon1, lat2, lon2):
    a, b, c, d = [np.radians(np.asarray(x, dtype=float)) for x in (lat1, lon1, lat2, lon2)]
    hav = np.sin((c-a)/2)**2 + np.cos(a)*np.cos(c)*np.sin((d-b)/2)**2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(hav, 0, 1)))


def base_features(frame):
    time = pd.to_datetime(frame["timestamp"], unit="s", utc=True) if pd.api.types.is_numeric_dtype(frame["timestamp"]) else pd.to_datetime(frame["timestamp"], utc=True)
    result = pd.DataFrame(index=frame.index)
    result["amount"] = frame.amount
    result["log_amount"] = np.log1p(frame.amount)
    result["hour"] = time.dt.hour
    result["weekday"] = time.dt.dayofweek
    result["home_distance_km"] = distance(frame.home_lat, frame.home_lon, frame.merchant_lat, frame.merchant_lon)
    result["category"], result["merchant"] = frame.category, frame.merchant
    return result


def batch_features(frame):
    """Vectorized per-customer prefixes exclude current/same-time rows, including test labels."""
    result = base_features(frame)
    for name in NUMERIC[5:]:
        result[name] = np.nan
    for _, indices in frame.groupby("customer_id", sort=False).groups.items():
        part = frame.loc[indices].sort_values("timestamp", kind="stable")
        idx = part.index
        times = part.timestamp.to_numpy(dtype=np.int64)
        amounts = part.amount.to_numpy(dtype=float)
        end = np.searchsorted(times, times, side="left")
        start = np.searchsorted(times, times - 30*86400, side="left")
        count = end-start
        sums = np.r_[0., np.cumsum(amounts)]
        squares = np.r_[0., np.cumsum(amounts**2)]
        mean = np.divide(sums[end]-sums[start], count, out=np.full(len(part), np.nan), where=count>0)
        variance = np.divide(squares[end]-squares[start], count, out=np.full(len(part), np.nan), where=count>0)-mean**2
        std = np.sqrt(np.maximum(variance, 0))
        previous = np.maximum(end-1, 0)
        result.loc[idx, "history_count"] = end
        result.loc[idx, "count_1h"] = end-np.searchsorted(times, times-3600, side="left")
        result.loc[idx, "count_24h"] = end-np.searchsorted(times, times-86400, side="left")
        result.loc[idx, "mean_30d"] = mean
        result.loc[idx, "std_30d"] = std
        result.loc[idx, "amount_ratio_30d"] = amounts/np.maximum(mean, 1)
        result.loc[idx, "amount_z_30d"] = (amounts-mean)/np.maximum(std, 1)
        result.loc[idx, "seconds_since_previous"] = np.where(end>0, times-times[previous], np.nan)
        for column in ("merchant", "category"):
            first = part.groupby(column).timestamp.transform("min").to_numpy()
            result.loc[idx, "new_"+column] = (first >= times).astype(float)
    return normalize(result)


def online_features(payment: dict, history: list[dict]):
    timestamp = int(payment["timestamp"])
    rows = [r for r in history if r["customer_id"] == payment["customer_id"] and int(r["timestamp"]) < timestamp]
    frame = pd.DataFrame([{**payment, "timestamp": pd.Timestamp(timestamp, unit="s", tz="UTC")}])
    result = base_features(frame)
    recent = [r for r in rows if int(r["timestamp"]) >= timestamp-30*86400]
    amounts = np.array([r["amount"] for r in recent], dtype=float)
    mean = float(amounts.mean()) if len(amounts) else np.nan
    std = float(amounts.std()) if len(amounts) else np.nan
    values = {"history_count": len(rows), "count_1h": sum(r["timestamp"] >= timestamp-3600 for r in rows),
              "count_24h": sum(r["timestamp"] >= timestamp-86400 for r in rows),
              "mean_30d": mean, "std_30d": std,
              "amount_ratio_30d": payment["amount"]/max(mean, 1),
              "amount_z_30d": (payment["amount"]-mean)/max(std, 1),
              "seconds_since_previous": timestamp-max(r["timestamp"] for r in rows) if rows else np.nan,
              "new_merchant": int(payment["merchant"] not in {r["merchant"] for r in rows}),
              "new_category": int(payment["category"] not in {r["category"] for r in rows})}
    for key, value in values.items():
        result[key] = value
    return normalize(result)


def normalize(frame):
    result = frame.loc[:, FEATURES].copy()
    result[NUMERIC] = result[NUMERIC].astype("float32")
    if np.isinf(result[NUMERIC].to_numpy()).any():
        raise ValueError("Infinite feature")
    for column in CATEGORICAL:
        result[column] = result[column].fillna("UNKNOWN").astype(str)
    return result


def preprocessor():
    return ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median", keep_empty_features=True), NUMERIC),
        ("categorical", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CATEGORICAL)
    ], verbose_feature_names_out=False).set_output(transform="pandas")
