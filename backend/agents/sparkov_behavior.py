import numpy as np
from datetime import datetime,timezone

from backend.ml.sparkov_features import distance, online_features


def analyze(payment,history):
    eligible=[r for r in history if r["customer_id"]==payment["customer_id"] and r["timestamp"]<payment["timestamp"]]
    features=online_features(payment,eligible).iloc[0]
    findings=[]
    # A rare three-hour band relative to this customer, not a universal "night = fraud" rule.
    timing_rows=[r for r in eligible if r["timestamp"]>=payment["timestamp"]-90*86400]
    hour=datetime.fromtimestamp(payment["timestamp"],timezone.utc).hour
    nearby_hours={(hour-1)%24,hour,(hour+1)%24}
    timing_matches=sum(datetime.fromtimestamp(r["timestamp"],timezone.utc).hour in nearby_hours for r in timing_rows)
    timing_share=timing_matches/len(timing_rows) if timing_rows else None
    timing={"current_hour_utc":hour,"prior_90d_count":len(timing_rows),"nearby_hour_count":timing_matches,
            "nearby_hour_share":timing_share,"window_hours_utc":sorted(nearby_hours),
            "minimum_history":60,"rare_share_threshold":.05}
    if len(eligible)>=5:
        if features.amount_ratio_30d>3 and features.amount_z_30d>3:
            findings.append({"code":"UNUSUAL_AMOUNT","detail":f"Amount is {features.amount_ratio_30d:.1f} times the prior 30-day mean."})
        if features.count_1h>=5:
            findings.append({"code":"HIGH_FREQUENCY","detail":f"{int(features.count_1h)} strictly earlier payments in the last hour."})
        if len(timing_rows)>=60 and timing_share<=.05:
            findings.append({"code":"UNUSUAL_TIME","detail":f"Unusual transaction time: {hour:02d}:00 UTC hour; only {timing_matches} of {len(timing_rows)} prior 90-day payments ({timing_share:.1%}) occurred within one hour of this hour of day."})
        if features.new_merchant:
            findings.append({"code":"NEW_MERCHANT","detail":"No earlier payment to this merchant for this customer."})
        devices={r.get("device_id") for r in eligible if r.get("device_id")}
        if devices and payment.get("device_id") and payment["device_id"] not in devices:
            findings.append({"code":"NEW_DEVICE","detail":"Device differs from earlier records; source-history devices are simulated."})
        prior_distance=distance([r["home_lat"] for r in eligible],[r["home_lon"] for r in eligible],
                                [r["merchant_lat"] for r in eligible],[r["merchant_lon"] for r in eligible])
        if features.home_distance_km>max(300,float(np.quantile(prior_distance,.95))):
            findings.append({"code":"UNUSUAL_LOCATION","detail":f"Unusual merchant location: {features.home_distance_km:,.0f} km from the customer's recorded home, above both 300 km and the prior 95th percentile ({float(np.quantile(prior_distance,.95)):,.0f} km)."})
    return {"history_status":"AVAILABLE" if len(eligible)>=5 else "INSUFFICIENT_HISTORY","history_count":len(eligible),
            "recent_30d_count":sum(r["timestamp"]>=payment["timestamp"]-30*86400 for r in eligible),
            "findings":findings,"baseline_mean_30d":None if np.isnan(features.mean_30d) else float(features.mean_30d),
            "time_profile":timing,
            "rules_version":"sparkov-behavior-v2.1",
            "provenance":"Prior Sparkov simulated payments plus earlier user-submitted payments; devices/payment method are additional simulated context."}
