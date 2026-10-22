import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import inspect,select,func

from backend.agents.sparkov_explanation import SparkovExplainer
from backend.database.connection import create_database,database_url
from backend.database.models import SparkovPayment,SparkovInvestigation
from backend.main import create_app


def payment():
    return dict(customer_id="NEW_ANALYST_TEST",timestamp="2020-07-15T12:00:00Z",amount=40,currency="USD",
                merchant="Test merchant",category="home",home_lat=35,home_lon=-88,merchant_lat=35,merchant_lon=-88,
                device_id="TEST_DEVICE",payment_method="CARD")


def test_workspace_runs_without_retired_model_and_routes_are_gone(tmp_path):
    assert not Path("models/lightgbm_pipeline.joblib").exists()
    assert not Path("dataset/train_transaction.csv").exists()
    with TestClient(create_app(f"sqlite:///{(tmp_path/'app.sqlite').as_posix()}")) as client:
        assert client.get("/health").json()["status"]=="ready"
        assert client.get("/v2/health").json()["model_version"]=="sparkov-v2"
        for path in ["/transactions","/model","/investigations"]:
            assert client.get(path).status_code==404
        assert client.post("/investigate",json={}).status_code==404
        assert set(inspect(client.app.state.engine).get_table_names())=={"sparkov_payments","sparkov_investigations","sparkov_reviews"}


def test_interrupted_cases_recover_without_losing_payment(tmp_path):
    url=f"sqlite:///{(tmp_path/'recover.sqlite').as_posix()}"
    with TestClient(create_app(url)) as client:
        with client.app.state.sessions.begin() as session:
            session.add(SparkovPayment(transaction_id="PAY_RECOVERY",customer_id="NEW_RECOVERY",event_timestamp=1594814400,context=payment()))
            session.flush()
            session.add(SparkovInvestigation(investigation_id="SPINV_RECOVERY",transaction_id="PAY_RECOVERY",status="RUNNING",completed_stages=["supervisor"]))
    with TestClient(create_app(url)) as client:
        row=client.get("/v2/investigations/SPINV_RECOVERY").json()
        assert row["status"]=="FAILED"
        assert row["payment"]["amount"]==40
        assert client.post("/v2/investigations/SPINV_RECOVERY/review",json={"reviewer":"Test","action":"CLEAR","notes":"Not ready"}).status_code==409


def test_investigation_failure_does_not_expose_internal_errors(tmp_path):
    with TestClient(create_app(f"sqlite:///{(tmp_path/'failure.sqlite').as_posix()}")) as client:
        def fail(*args):
            raise RuntimeError("PRIVATE_VALUE_DO_NOT_EXPOSE")
        client.app.state.sparkov.store.history=fail
        response=client.post("/v2/investigate",json=payment())
        row=client.get("/v2/investigations/"+response.json()["investigation_id"]).json()
        assert row["status"]=="FAILED"
        assert "PRIVATE_VALUE" not in str(row)


def test_unavailable_workspace_reports_unavailable(tmp_path):
    with TestClient(create_app(f"sqlite:///{(tmp_path/'unavailable.sqlite').as_posix()}",enable_sparkov=False)) as client:
        assert client.get("/health").status_code==503
        assert client.get("/v2/options").status_code==503


@pytest.mark.skipif(os.getenv("FINSENTRY_TEST_MYSQL")!="1",reason="Enable explicit local MySQL check")
def test_real_mysql_payment_review_and_reload():
    engine,sessions=create_database(database_url())
    with sessions() as session:
        pending=session.scalar(select(func.count()).select_from(SparkovInvestigation).where(SparkovInvestigation.status.in_(["QUEUED","RUNNING"])))
    engine.dispose()
    if pending:
        pytest.skip("Do not interrupt an active local investigation")
    with TestClient(create_app()) as client:
        client.app.state.sparkov.explainer=SparkovExplainer(api_key="")
        response=client.post("/v2/investigate",json=payment())
        assert response.status_code==202,response.text
        identifier=response.json()["investigation_id"]
        row=client.get("/v2/investigations/"+identifier).json()
        assert row["status"]=="COMPLETED"
        response=client.post(f"/v2/investigations/{identifier}/review",json={"reviewer":"AUTOMATED_INTEGRATION_TEST","action":"FLAG","notes":"Automated persistence verification; not a human fraud confirmation."})
        assert response.status_code==201
        assert response.json()["result"]==row["result"]
    with TestClient(create_app()) as client:
        reloaded=client.get("/v2/investigations/"+identifier).json()
        assert reloaded["reviews"][-1]["reviewer"]=="AUTOMATED_INTEGRATION_TEST"
        assert reloaded["result"]==row["result"]
