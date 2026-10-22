"""Read-only indexed source history; new submitted payments remain in project MySQL."""
import json
from pathlib import Path
import sqlite3
from contextlib import closing

from backend.ml.sparkov_train import ARTIFACTS, STORE


class SparkovStore:
    def __init__(self,path=STORE):
        self.path=Path(path)

    def connect(self):
        connection=sqlite3.connect(self.path.resolve().as_uri()+"?mode=ro",uri=True)
        connection.row_factory=sqlite3.Row
        return connection

    def verify(self,metadata):
        with closing(self.connect()) as db:
            manifest=json.loads(db.execute("SELECT metadata_json FROM artifact_metadata").fetchone()[0])
        if manifest["trained_at_utc"]!=metadata["trained_at_utc"] or manifest["source"]!=metadata["source"]:
            raise ValueError("Sparkov model and source store are from different builds; rebuild offline before restart")

    def customer(self,identifier,as_of=None):
        with closing(self.connect()) as db:
            row=db.execute("SELECT * FROM customers WHERE customer_id=?",(identifier,)).fetchone()
        return dict(row) if row and (as_of is None or row["timestamp"]<as_of) else None

    def history(self,identifier,timestamp):
        with closing(self.connect()) as db:
            rows=db.execute("SELECT * FROM transactions WHERE customer_id=? AND timestamp<? ORDER BY timestamp,transaction_id",(identifier,timestamp)).fetchall()
        return [dict(row) for row in rows]

    def options(self):
        with closing(self.connect()) as db:
            customers=[dict(row) for row in db.execute("SELECT * FROM customers ORDER BY customer_id")]
            merchants=[dict(row) for row in db.execute("SELECT merchant,category,AVG(merchant_lat) AS merchant_lat,AVG(merchant_lon) AS merchant_lon FROM transactions GROUP BY merchant,category ORDER BY merchant")]
            case_count=db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        return {"customers":customers,"merchants":merchants,"case_count":case_count}

    def intelligence(self,payment):
        timestamp=payment["timestamp"]
        with closing(self.connect()) as db:
            cases=db.execute("""SELECT * FROM cases WHERE known_at<=? AND timestamp<? AND transaction_id<>?
                AND known_at>=? AND (customer_id=? OR merchant=?)
                ORDER BY (customer_id=?) DESC,known_at DESC LIMIT 8""",
                (timestamp,timestamp,payment["transaction_id"],timestamp-30*86400,payment["customer_id"],payment["merchant"],payment["customer_id"])).fetchall()
            # An explicit entity lookup, not a semantic resemblance presented as an entity match.
            volume=db.execute("SELECT COUNT(*) FROM transactions WHERE merchant=? AND timestamp<? AND timestamp>=?",
                (payment["merchant"],timestamp,timestamp-30*86400)).fetchone()[0]
        evidence=[]
        for row in cases:
            item=dict(row)
            item["entity_matches"]=[key for key in ("customer_id","merchant") if item[key]==payment[key]]
            item["source"]="Sparkov development label; simulated confirmation delay 24 hours"
            item["is_synthetic"]=True
            item["summary"]=f"Simulated confirmed fraud of USD {item['amount']:.2f}, category {item['category']}; linked by {', '.join(item['entity_matches'])}."
            evidence.append(item)
        return {"status":"MATCHES" if evidence else "NO_MATCH", "cases":evidence,
                "customer_link":any("customer_id" in row["entity_matches"] for row in evidence),
                "merchant_link":any("merchant" in row["entity_matches"] for row in evidence),
                "merchant_prior_30d_volume":volume,
                "limitations":["Case outcomes come from development data only; 24h outcome delay is simulated.",
                               "A merchant link is contextual evidence, not proof that the merchant is fraudulent.",
                               "No source recipient accounts or observed device-fraud links are available."]}

    def follow_up(self,payment):
        with closing(self.connect()) as db:
            row=db.execute("""SELECT COUNT(*) AS prior_payments,COUNT(DISTINCT customer_id) AS prior_customers,
                AVG(amount) AS prior_mean_amount FROM transactions WHERE merchant=? AND timestamp<? AND timestamp>=?""",
                (payment["merchant"],payment["timestamp"],payment["timestamp"]-7*86400)).fetchone()
        return {"check":"MERCHANT_PRIOR_7D_ACTIVITY", **dict(row),
                "conclusion":"Activity volume supplies context; unlabeled payments are not confirmed legitimate.",
                "conflict_resolved":False}
