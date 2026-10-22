"""Transaction deletion is atomic, persistent, and limited to the chosen payment."""
import os
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, select, func
from sqlalchemy.exc import SQLAlchemyError

from backend.database.connection import create_database, database_url
from backend.database.models import SparkovPayment, SparkovInvestigation, SparkovReview
from backend.main import create_app


@pytest.fixture(params=["sqlite", "mysql"])
def client(request, tmp_path):
    if request.param == "mysql":
        if os.getenv("FINSENTRY_TEST_MYSQL") != "1":
            pytest.skip("Enable explicit local MySQL check")
        url = database_url()
        engine, sessions = create_database(url)
        with sessions() as session:
            pending = session.scalar(select(func.count()).select_from(SparkovInvestigation).where(
                SparkovInvestigation.status.in_(["QUEUED", "RUNNING"])))
        engine.dispose()
        if pending:
            pytest.skip("Do not interrupt active investigations")
    else:
        url = f"sqlite:///{(tmp_path/'delete.sqlite').as_posix()}"
    # No model or LLM is needed to manage saved records.
    with TestClient(create_app(url, enable_sparkov=False)) as item:
        item.app.state.sparkov = SimpleNamespace()
        if request.param == "sqlite":
            @event.listens_for(item.app.state.engine, "checkout")
            def enforce_foreign_keys(connection, record, proxy):
                connection.execute("PRAGMA foreign_keys=ON")
        yield item


def seed(client, status="COMPLETED", cases=1):
    suffix = uuid4().hex
    payment_id = "PAY_" + suffix
    identifiers = ["SPINV_" + uuid4().hex for _ in range(cases)]
    with client.app.state.sessions.begin() as session:
        session.add(SparkovPayment(transaction_id=payment_id, customer_id="NEW_DELETE_TEST",
                                  event_timestamp=1594814400, context={"amount":40}))
        session.flush()
        for identifier in identifiers:
            session.add(SparkovInvestigation(investigation_id=identifier, transaction_id=payment_id,
                                             status=status, completed_stages=[]))
        session.flush()
        for identifier in identifiers:
            session.add(SparkovReview(review_id="REV_"+uuid4().hex, investigation_id=identifier,
                                     reviewer="AUTOMATED_DELETE_TEST", action="FLAG", notes="Test only"))
    return payment_id, identifiers


def test_delete_removes_payment_all_cases_and_reviews_and_preserves_other_payment(client):
    payment_id, identifiers = seed(client, cases=2)
    other_payment, other_cases = seed(client)
    try:
        response = client.delete(f"/v2/investigations/{identifiers[0]}")
        assert response.status_code == 200, response.text
        assert response.json()["transaction_id"] == payment_id
        assert set(response.json()["deleted_case_ids"]) == set(identifiers)
        for identifier in identifiers:
            assert client.get(f"/v2/investigations/{identifier}").status_code == 404
        assert not set(identifiers) & {row["investigation_id"] for row in client.get("/v2/investigations?limit=100").json()}
        # New sessions read committed state rather than an ORM cache.
        with client.app.state.sessions() as session:
            assert session.get(SparkovPayment, payment_id) is None
            assert session.scalar(select(func.count()).select_from(SparkovReview).where(
                SparkovReview.investigation_id.in_(identifiers))) == 0
            assert session.get(SparkovPayment, other_payment) is not None
            assert session.get(SparkovInvestigation, other_cases[0]) is not None
        assert client.delete(f"/v2/investigations/{identifiers[0]}").status_code == 404
    finally:
        client.delete(f"/v2/investigations/{other_cases[0]}")


@pytest.mark.parametrize("status", ["QUEUED", "RUNNING"])
def test_delete_refuses_active_case_without_partial_deletion(client, status):
    payment_id, identifiers = seed(client, status=status)
    try:
        assert client.delete(f"/v2/investigations/{identifiers[0]}").status_code == 409
        with client.app.state.sessions() as session:
            assert session.get(SparkovPayment, payment_id) is not None
            assert session.get(SparkovInvestigation, identifiers[0]).status == status
            assert session.scalar(select(func.count()).select_from(SparkovReview).where(
                SparkovReview.investigation_id == identifiers[0])) == 1
    finally:
        with client.app.state.sessions.begin() as session:
            session.get(SparkovInvestigation, identifiers[0]).status = "FAILED"
        assert client.delete(f"/v2/investigations/{identifiers[0]}").status_code == 200


def test_failed_case_can_be_deleted_and_dev_frontend_can_send_delete(client):
    _, identifiers = seed(client, status="FAILED")
    response = client.options(f"/v2/investigations/{identifiers[0]}", headers={
        "Origin":"http://localhost:5173", "Access-Control-Request-Method":"DELETE"})
    assert response.status_code == 200
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert client.delete(f"/v2/investigations/{identifiers[0]}").status_code == 200


def test_database_failure_rolls_back_reviews_cases_and_payment(client):
    payment_id, identifiers = seed(client)

    def fail_payment_delete(mapper, connection, target):
        if target.transaction_id == payment_id:
            raise SQLAlchemyError("Simulated storage failure")

    event.listen(SparkovPayment, "before_delete", fail_payment_delete)
    try:
        assert client.delete(f"/v2/investigations/{identifiers[0]}").status_code == 503
        with client.app.state.sessions() as session:
            assert session.get(SparkovPayment, payment_id) is not None
            assert session.get(SparkovInvestigation, identifiers[0]) is not None
            assert session.scalar(select(func.count()).select_from(SparkovReview).where(
                SparkovReview.investigation_id == identifiers[0])) == 1
    finally:
        event.remove(SparkovPayment, "before_delete", fail_payment_delete)
        assert client.delete(f"/v2/investigations/{identifiers[0]}").status_code == 200
