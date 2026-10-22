import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import httpx
import pytest

from backend.agents.sparkov_decision import assess
from backend.agents.sparkov_explanation import SparkovExplainer
from backend.database.sparkov_store import SparkovStore
from backend.graph.sparkov_workflow import investigate
from backend.graph.sparkov_workflow import quality as evidence_quality
from backend.main import create_app
from backend.schemas.sparkov import NewPayment


def policy_inputs():
    return (dict(risk_score=.01,threshold=.3,model_flag=False),
            dict(findings=[],history_count=100),dict(status="NO_MATCH",cases=[],customer_link=False,merchant_link=False),
            dict(confidence="HIGH",limitations=[]))


def test_intelligence_and_behavior_change_action():
    risk,behavior,intel,quality=policy_inputs()
    assert assess(risk,behavior,intel,quality)["recommendation"]=="CLEAR"
    assert assess(risk,behavior,dict(intel,merchant_link=True),quality)["recommendation"]=="CLEAR"
    assert assess(risk,behavior,dict(intel,customer_link=True),quality)["recommendation"]=="FLAG"
    behavior["findings"]=[dict(code="UNUSUAL_AMOUNT",detail="Unusual amount")]
    assert assess(risk,behavior,dict(intel,customer_link=True),quality)["recommendation"]=="ESCALATE"
    assert assess(risk,behavior,intel,dict(confidence="LOW",limitations=["No history"]))["risk_level"]=="UNCERTAIN"
    assert assess(dict(risk,risk_score=.99,model_flag=True),dict(behavior,findings=[]),intel,quality)["recommendation"]=="ESCALATE"


def test_unknown_evidence_cannot_clear():
    risk,behavior,intel,quality=policy_inputs()
    assert assess(risk,behavior,dict(intel,status="UNAVAILABLE"),quality)["recommendation"]=="ESCALATE"


def test_label_and_score_are_rejected_and_timezone_required():
    row=payment()
    NewPayment.model_validate(row)
    for changed in [dict(row,is_fraud=1),dict(row,risk_score=0),dict(row,timestamp="2020-07-01T12:00:00"),dict(row,amount=float("inf")),dict(row,currency="INR")]:
        with pytest.raises(ValueError):
            NewPayment.model_validate(changed)


def test_outside_period_and_missing_history_reduce_evidence_confidence():
    meta={"splits":{"test":{"min_timestamp":100,"max_timestamp":200}}}
    behavior={"history_count":100,"recent_30d_count":40}
    assert evidence_quality({"timestamp":150,"device_id":"D"},behavior,meta)["confidence"]=="HIGH"
    assert evidence_quality({"timestamp":201,"device_id":"D"},behavior,meta)["confidence"]=="LOW"
    assert evidence_quality({"timestamp":150,"device_id":"D"},dict(behavior,recent_30d_count=0),meta)["confidence"]=="LOW"


def payment():
    return dict(customer_id="NEW_TEST",timestamp="2020-07-01T12:00:00Z",amount=20,currency="USD",merchant="Test merchant",
                category="grocery_pos",home_lat=40,home_lon=-74,merchant_lat=40.01,merchant_lon=-74.01,device_id="TEST_DEVICE",payment_method="CARD")


def test_case_lookup_excludes_future_unknown_outcome_and_self(tmp_path):
    path=tmp_path/"source.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE cases (case_id TEXT,transaction_id TEXT,customer_id TEXT,merchant TEXT,category TEXT,amount REAL,timestamp INTEGER,known_at INTEGER)")
        db.executemany("INSERT INTO cases VALUES (?,?,?,?,?,?,?,?)",[
            ("PAST","PAST","C","M","food",10,10,11),
            ("UNKNOWN","UNKNOWN","C","M","food",10,10,101),
            ("FUTURE","FUTURE","C","M","food",10,101,101),
            ("SELF","CURRENT","C","M","food",10,10,11),
        ])
        db.execute("CREATE TABLE transactions (transaction_id TEXT,customer_id TEXT,merchant TEXT,timestamp INTEGER)")
        db.execute("INSERT INTO transactions VALUES ('X','C','M',10)")
    store=SparkovStore(path)
    result=store.intelligence(dict(customer_id="C",merchant="M",timestamp=100,transaction_id="CURRENT"))
    assert [c["case_id"] for c in result["cases"]]==["PAST"]


def test_graph_plan_join_bounded_follow_up_and_missing_history():
    class Predictor:
        metadata={"splits":{"test":{"min_timestamp":0,"max_timestamp":999999}}}
        def predict(self,payment,history):
            return dict(risk_score=.9,threshold=.3,model_flag=True)
    class Store:
        calls=0
        def intelligence(self,p):
            return dict(status="NO_MATCH",cases=[],customer_link=False,merchant_link=False)
        def follow_up(self,p):
            self.calls+=1
            return {"check":"TEST","conflict_resolved":False}
    store=Store()
    stages=[]
    row=dict(customer_id="NEW_A",timestamp=10000,amount=50,home_lat=40,home_lon=-74,merchant_lat=40,merchant_lon=-74,
             category="food",merchant="M",device_id="D",transaction_id="T")
    result=investigate(row,[],Predictor(),store,SparkovExplainer(api_key=""),stages.append)
    assert stages[0]=="supervisor" and stages[-1]=="decision"
    assert stages.index("intelligence")>stages.index("risk") and stages.index("intelligence")>stages.index("behavior")
    assert store.calls==1
    assert result["recommendation"]=="ESCALATE" and result["evidence_confidence"]=="LOW"
    assert result["explanation_mode"]=="template"


def test_groq_changed_decision_is_rejected():
    risk,behavior,intel,quality=policy_inputs()
    result={**assess(risk,behavior,intel,quality),"risk":risk,"behavior":behavior,"intelligence":intel,"quality":quality,"follow_up":None}
    def handler(request):
        return httpx.Response(200,json={"choices":[{"message":{"content":json.dumps(dict(model_score=.01,recommendation="ESCALATE",cited_case_ids=[],summary="Fabricated changed recommendation."))}}]})
    output=SparkovExplainer(api_key="PRIVATE_TEST_KEY",transport=httpx.MockTransport(handler)).explain_assessment(result)
    assert output["explanation_mode"]=="template" and output["explanation_fallback_reason"]=="INVALID_OUTPUT"
    assert "PRIVATE_TEST_KEY" not in str(output)


@pytest.mark.skipif(not Path("models/sparkov_v2/pipeline.joblib").exists(),reason="Train Sparkov artifacts first")
def test_new_payment_review_and_restart(tmp_path):
    url=f"sqlite:///{(tmp_path/'v2.sqlite').as_posix()}"
    app=create_app(url,enable_sparkov=True)
    with TestClient(app) as client:
        app.state.sparkov.explainer=SparkovExplainer(api_key="")
        assert client.get("/v2/health").status_code==200
        assert client.post("/v2/investigate",json=dict(payment(),label=1)).status_code==422
        response=client.post("/v2/investigate",json=payment())
        assert response.status_code==202,response.text
        identifier=response.json()["investigation_id"]
        result=client.get("/v2/investigations/"+identifier).json()
        assert result["status"]=="COMPLETED",result
        assert result["result"]["recommendation"]=="ESCALATE"
        assert result["result"]["behavior"]["history_count"]==0
        assert result["result"]["explanation_mode"]=="template"
        reviewed=client.post(f"/v2/investigations/{identifier}/review",json=dict(reviewer="Aryan",action="FLAG",notes="Needs additional evidence"))
        assert reviewed.status_code==201,reviewed.text
        assert reviewed.json()["result"]==result["result"]
        assert reviewed.json()["reviews"][0]["action"]=="FLAG"
        assert client.get("/v2/customers/NEW_TEST/history?before=1593604800").json()["count"]==0
        assert client.get("/v2/customers/NEW_TEST/history?before=1593604801").json()["count"]==1
        assert client.get("/v2/investigations/unknown").status_code==404
    with TestClient(create_app(url,enable_sparkov=True)) as client:
        saved=client.get("/v2/investigations/"+identifier).json()
        assert saved["reviews"][0]["reviewer"]=="Aryan"
        assert saved["result"]==result["result"]


@pytest.mark.skipif(not Path("runtime/sparkov/history.sqlite").exists(),reason="Build source store first")
def test_versioned_source_store_is_read_only_label_free_and_matches_model():
    metadata=json.loads(Path("models/sparkov_v2/metadata.json").read_text(encoding="utf-8"))
    store=SparkovStore()
    store.verify(metadata)
    with pytest.raises(ValueError):
        store.verify(dict(metadata,trained_at_utc="different-build"))
    db=store.connect()
    try:
        columns={row[1] for row in db.execute("PRAGMA table_info(transactions)")}
        assert not {"label","is_fraud","cc_num","first","last","dob"}.intersection(columns)
        assert db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]==1852394
        with pytest.raises(sqlite3.OperationalError):
            db.execute("CREATE TABLE forbidden_write (a INTEGER)")
    finally:
        db.close()
