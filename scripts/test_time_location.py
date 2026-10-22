"""Controlled, label-free new payments: normal / time-only / location-only / both."""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time

import httpx
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.database.sparkov_store import SparkovStore


def main():
    customer="CUST_00686b4dd6551bfe"
    early=int(datetime(2020,7,15,3,15,tzinfo=timezone.utc).timestamp())
    usual=int(datetime(2020,7,15,22,15,tzinfo=timezone.utc).timestamp())
    store=SparkovStore()
    profile=store.customer(customer,early)
    history=store.history(customer,early)
    recent=[r for r in history if r["timestamp"]>=early-30*86400]
    amount=round(float(np.median([r["amount"] for r in recent])),2)
    merchant,category=Counter((r["merchant"],r["category"]) for r in history).most_common(1)[0][0]
    base={"customer_id":customer,"amount":amount,"currency":"USD","merchant":merchant,"category":category,
          "home_lat":profile["home_lat"],"home_lon":profile["home_lon"],"merchant_lat":profile["home_lat"],
          "merchant_lon":profile["home_lon"],"device_id":profile["device_id"],"payment_method":"CARD"}
    cases=[("normal",usual,False,set()),("unusual_time",early,False,{"UNUSUAL_TIME"}),
           ("unusual_location",usual,True,{"UNUSUAL_LOCATION"}),
           ("unusual_time_and_location",early,True,{"UNUSUAL_TIME","UNUSUAL_LOCATION"})]
    records=[]
    with httpx.Client(base_url="http://127.0.0.1:8000",timeout=30) as client:
        client.get("/v2/health").raise_for_status()
        for name,timestamp,far,expected in cases:
            payload={**base,"timestamp":datetime.fromtimestamp(timestamp,timezone.utc).isoformat()}
            if far:
                payload.update(merchant_lat=-33.8688,merchant_lon=151.2093)
            response=client.post("/v2/investigate",json=payload)
            response.raise_for_status()
            identifier=response.json()["investigation_id"]
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                saved=client.get("/v2/investigations/"+identifier).json()
                if saved["status"] in {"COMPLETED","FAILED"}:
                    break
                time.sleep(.4)
            assert saved["status"]=="COMPLETED",saved
            result=saved["result"]
            codes={r["code"] for r in result["behavior"]["findings"]}
            assert expected.issubset(codes),(name,codes)
            assert "UNUSUAL_AMOUNT" not in codes,(name,codes)
            assert not result["quality"]["limitations"],result["quality"]
            if name=="normal":
                assert not codes,(name,codes)
            if expected:
                assert result["recommendation"] in {"FLAG","ESCALATE"}
            record={"scenario":name,"investigation_id":identifier,"input":payload,
                    "model_risk":result["risk"]["risk_score"],"threshold":result["risk"]["threshold"],
                    "recommendation":result["recommendation"],"risk_level":result["risk_level"],
                    "evidence_confidence":result["evidence_confidence"],"behavior_codes":sorted(codes),
                    "behavior":result["behavior"],"explanation_mode":result["explanation_mode"],
                    "fallback_reason":result["explanation_fallback_reason"],"explanation":result["explanation"]}
            records.append(record)
            print(json.dumps({k:record[k] for k in ["scenario","investigation_id","recommendation","model_risk","behavior_codes","evidence_confidence","explanation_mode"]}),flush=True)
        combined=records[-1]
        demo={**combined["input"],"timestamp":early}
        (ROOT/"data/sparkov/time_location_demo.json").write_text(json.dumps({"note":"Counterfactual simulation: source customer's prior median amount, rare time, distant merchant coordinates; no fraud label supplied.","transaction":demo},indent=2)+"\n",encoding="utf-8")
        report={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"purpose":"Normal amount; isolate unusual time and location using prior customer history, no supplied labels or forced scores.","checks":records}
        (ROOT/"reports/time_location_test.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
