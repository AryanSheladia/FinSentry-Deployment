"""Real local API/MySQL/Groq smoke check; never prints credentials or source labels."""
from datetime import datetime,timezone
import json
from pathlib import Path
import time
import sqlite3

import httpx

ROOT=Path(__file__).resolve().parents[1]


def main():
    records=[]
    with httpx.Client(base_url="http://127.0.0.1:8000",timeout=45) as client:
        health=client.get("/v2/health")
        health.raise_for_status()
        options=client.get("/v2/options")
        options.raise_for_status()
        options=options.json()
        examples=[options["examples"][0],options["examples"][-1]]
        # A label-free test transaction whose customer has a development case already known.
        with sqlite3.connect(ROOT/"runtime/sparkov/history.sqlite") as db:
            db.row_factory=sqlite3.Row
            linked=db.execute("""SELECT t.* FROM cases c JOIN transactions t ON t.customer_id=c.customer_id
                WHERE t.timestamp>=1592741665 AND c.known_at<=t.timestamp AND c.known_at>=t.timestamp-2592000
                ORDER BY t.timestamp LIMIT 1""").fetchone()
            if linked:
                examples.append(dict(linked))
        for example in examples:
            payload={k:example[k] for k in ["customer_id","amount","merchant","category","merchant_lat","merchant_lon","device_id","payment_method"]}
            payload["timestamp"]=datetime.fromtimestamp(example["timestamp"],timezone.utc).isoformat()
            response=client.post("/v2/investigate",json=payload)
            response.raise_for_status()
            identifier=response.json()["investigation_id"]
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                saved=client.get("/v2/investigations/"+identifier).json()
                if saved["status"] in ["COMPLETED","FAILED"]:
                    break
                time.sleep(.4)
            assert saved["status"]=="COMPLETED",saved
            result=saved["result"]
            for case in result["intelligence"]["cases"]:
                assert case["known_at"]<=example["timestamp"] and case["timestamp"]<example["timestamp"]
            records.append({"investigation_id":identifier,"model_score":result["risk"]["risk_score"],"recommendation":result["recommendation"],
                            "risk_level":result["risk_level"],"history_count":result["behavior"]["history_count"],
                            "case_count":len(result["intelligence"]["cases"]),"evidence_confidence":result["evidence_confidence"],
                            "explanation_mode":result["explanation_mode"],"fallback_reason":result["explanation_fallback_reason"],
                            "completed_stages":saved["completed_stages"]})
        reviewed=client.post(f"/v2/investigations/{identifier}/review",json={"reviewer":"AUTOMATED_SMOKE_CHECK","action":"FLAG",
            "notes":"Automated persistence check, not a human fraud confirmation."})
        reviewed.raise_for_status()
        assert reviewed.json()["result"]==result
        assert reviewed.json()["reviews"][-1]["reviewer"]=="AUTOMATED_SMOKE_CHECK"
    report={"checked_at_utc":datetime.now(timezone.utc).isoformat(),"health":health.json(),"checks":records,
            "review_persistence_verified":True,
            "note":"New submissions from label-free examples and one prior-case-linked source payment, not a representative model/policy evaluation. Automated review is marked as a test."}
    (ROOT/"reports/sparkov_smoke.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()
