"""New-payment investigation API. Raw dataset labels are never accepted from clients."""
from functools import lru_cache
import json
import logging
from threading import BoundedSemaphore,Lock
from uuid import uuid4

from fastapi import APIRouter,BackgroundTasks,HTTPException,Query
from sqlalchemy import delete,select

from backend.api.serializers import iso_utc
from backend.database.connection import ROOT
from backend.database.models import SparkovPayment,SparkovInvestigation,SparkovReview,utcnow
from backend.database.sparkov_store import SparkovStore
from backend.schemas.sparkov import NewPayment,HumanReview

logger=logging.getLogger("finsentry.sparkov")


class SparkovService:
    def __init__(self,predictor=None,store=None,explainer=None):
        from backend.ml.sparkov_predict import SparkovPredictor
        from backend.agents.sparkov_explanation import SparkovExplainer
        self.predictor=predictor or SparkovPredictor()
        self.store=store or SparkovStore()
        self.store.verify(self.predictor.metadata)
        self.explainer=explainer or SparkovExplainer()

    @lru_cache(maxsize=1)
    def options(self):
        options=self.store.options()
        example_path=ROOT/"data/sparkov/examples.json"
        options["examples"]=json.loads(example_path.read_text())["transactions"] if example_path.exists() else []
        behavior_demo=ROOT/"data/sparkov/time_location_demo.json"
        options["behavior_demo"]=json.loads(behavior_demo.read_text(encoding="utf-8"))["transaction"] if behavior_demo.exists() else None
        options["metadata"]=self.predictor.metadata
        return options

    def history(self,sessions,payment):
        history=self.store.history(payment["customer_id"],payment["timestamp"])
        with sessions() as session:
            extra=session.scalars(select(SparkovPayment).where(SparkovPayment.customer_id==payment["customer_id"],
                SparkovPayment.event_timestamp<payment["timestamp"],SparkovPayment.transaction_id!=payment["transaction_id"])).all()
            history.extend(row.context for row in extra)
        return sorted(history,key=lambda r:(r["timestamp"],r["transaction_id"]))


def view(session,row):
    reviews=session.scalars(select(SparkovReview).where(SparkovReview.investigation_id==row.investigation_id).order_by(SparkovReview.created_at,SparkovReview.review_id)).all()
    payment=session.get(SparkovPayment,row.transaction_id)
    return {"investigation_id":row.investigation_id,"transaction_id":row.transaction_id,"payment":payment.context,
            "status":row.status,"created_at":iso_utc(row.created_at),"completed_stages":row.completed_stages,
            "result":row.result,"error":row.error,
            "reviews":[{"review_id":r.review_id,"reviewer":r.reviewer,"action":r.action,"notes":r.notes,"created_at":iso_utc(r.created_at)} for r in reviews]}


def create_sparkov_router(app):
    router=APIRouter(prefix="/v2",tags=["Sparkov v2"])
    accepted=BoundedSemaphore(8)
    execution=BoundedSemaphore(2)

    def service():
        item=getattr(app.state,"sparkov",None)
        if item is None:
            raise HTTPException(503,"The investigation service is not ready. Please ask the workspace administrator to restore it.")
        return item

    @router.get("/health")
    def health():
        svc=service()
        # Verify database readiness as well as presence of model/history artifacts.
        from sqlalchemy import text
        with app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status":"ready","model_version":svc.predictor.metadata["model_version"],
                "explanation_provider":"groq","explanation_model":svc.explainer.model,
                "groq_key_configured":bool(svc.explainer.api_key.strip()),"workflow_mode":"SPARKOV_FIVE_AGENT_V2"}

    @router.get("/options")
    def options():
        return service().options()

    @router.get("/customers/{customer_id}/history")
    def history(customer_id:str,before:int=Query(...,gt=0)):
        payment={"customer_id":customer_id,"timestamp":before,"transaction_id":"UNSAVED"}
        rows=service().history(app.state.sessions,payment)
        return {"count":len(rows),"transactions":rows[-10:],"as_of":before,"source":"Strictly prior simulated source/submitted payments"}

    def run(identifier):
        lock=Lock()
        sessions=app.state.sessions
        def progress(stage):
            with lock,sessions.begin() as session:
                row=session.get(SparkovInvestigation,identifier)
                if stage not in row.completed_stages:
                    row.completed_stages=[*row.completed_stages,stage]
                row.updated_at=utcnow()
        try:
            with execution:
                svc=service()
                with sessions.begin() as session:
                    row=session.get(SparkovInvestigation,identifier)
                    row.status="RUNNING"
                    payment=session.get(SparkovPayment,row.transaction_id).context
                history=svc.history(sessions,payment)
                from backend.graph.sparkov_workflow import investigate
                result=investigate(payment,history,svc.predictor,svc.store,svc.explainer,progress)
                with sessions.begin() as session:
                    row=session.get(SparkovInvestigation,identifier)
                    row.result=result
                    row.status="COMPLETED"
                    row.updated_at=utcnow()
        except Exception as error:
            logger.error("Sparkov investigation failed (%s)",type(error).__name__)
            try:
                with sessions.begin() as session:
                    row=session.get(SparkovInvestigation,identifier)
                    row.status="FAILED"
                    row.error="Investigation failed; check local model/history/provider configuration."
                    row.updated_at=utcnow()
            except Exception:
                logger.error("Could not persist Sparkov failure")
        finally:
            accepted.release()

    @router.post("/investigate",status_code=202)
    def submit(request:NewPayment,background:BackgroundTasks):
        svc=service()
        payment=request.model_dump(mode="json")
        payment["timestamp"]=int(request.timestamp.timestamp())
        customer=svc.store.customer(request.customer_id,payment["timestamp"])
        if request.customer_id.startswith("CUST_") and customer is None:
            raise HTTPException(422,"This customer has no record before the payment date. Choose a later date or select a customer with no earlier history.")
        if customer:
            payment["home_lat"],payment["home_lon"]=customer["home_lat"],customer["home_lon"]
        elif request.home_lat is None or request.home_lon is None:
            raise HTTPException(422,"Home coordinates are required for a new customer.")
        # Vocabulary comes from fitted training encoders, not the full test dataset.
        vocab=svc.predictor.bundle["preprocess"].named_transformers_["categorical"].categories_
        payment["unseen_category"]=request.category not in vocab[0]
        payment["unseen_merchant"]=request.merchant not in vocab[1]
        payment["data_mode"]="SPARKOV_SIMULATION_WITH_SUBMITTED_TRANSACTION"
        payment["context_notice"]="USD card payments only; source-history devices and payment method are simulated. No bank connection."
        transaction_id="PAY_"+uuid4().hex
        payment["transaction_id"]=transaction_id
        identifier="SPINV_"+uuid4().hex
        if not accepted.acquire(blocking=False):
            raise HTTPException(503,"Investigation queue is full; retry shortly")
        try:
            with app.state.sessions.begin() as session:
                session.add(SparkovPayment(transaction_id=transaction_id,customer_id=request.customer_id,event_timestamp=payment["timestamp"],context=payment))
                session.flush()
                session.add(SparkovInvestigation(investigation_id=identifier,transaction_id=transaction_id,status="QUEUED",completed_stages=[]))
            background.add_task(run,identifier)
        except Exception:
            accepted.release()
            raise
        return {"investigation_id":identifier,"transaction_id":transaction_id,"status":"QUEUED"}

    @router.get("/investigations")
    def investigations(limit:int=Query(20,ge=1,le=100)):
        service()
        with app.state.sessions() as session:
            rows=session.scalars(select(SparkovInvestigation).order_by(SparkovInvestigation.created_at.desc(),SparkovInvestigation.investigation_id.desc()).limit(limit)).all()
            return [view(session,row) for row in rows]

    @router.get("/investigations/{identifier}")
    def investigation(identifier:str):
        service()
        with app.state.sessions() as session:
            row=session.get(SparkovInvestigation,identifier)
            if row is None:
                raise HTTPException(404,"Unknown Sparkov investigation")
            return view(session,row)

    @router.post("/investigations/{identifier}/review",status_code=201)
    def review(identifier:str,request:HumanReview):
        service()
        with app.state.sessions.begin() as session:
            row=session.scalar(select(SparkovInvestigation).where(SparkovInvestigation.investigation_id==identifier).with_for_update())
            if row is None:
                raise HTTPException(404,"Unknown Sparkov investigation")
            if row.status!="COMPLETED":
                raise HTTPException(409,"Complete the investigation before human review")
            session.add(SparkovReview(review_id="REV_"+uuid4().hex,investigation_id=identifier,**request.model_dump()))
            session.flush()
            return view(session,row)

    @router.delete("/investigations/{identifier}")
    def delete_transaction(identifier:str):
        with app.state.sessions.begin() as session:
            transaction_id=session.scalar(select(SparkovInvestigation.transaction_id).where(SparkovInvestigation.investigation_id==identifier))
            if transaction_id is None:
                raise HTTPException(404,"This case no longer exists. Refresh the review queue.")
            # Serialize deletion of the payment and any cases belonging to it.
            payment=session.scalar(select(SparkovPayment).where(SparkovPayment.transaction_id==transaction_id).with_for_update())
            if payment is None:
                raise HTTPException(404,"This transaction no longer exists. Refresh the review queue.")
            cases=session.scalars(select(SparkovInvestigation).where(SparkovInvestigation.transaction_id==transaction_id).with_for_update()).all()
            if any(row.status in ("QUEUED","RUNNING") for row in cases):
                raise HTTPException(409,"Wait for this transaction's investigation to finish before deleting it.")
            identifiers=[row.investigation_id for row in cases]
            session.execute(delete(SparkovReview).where(SparkovReview.investigation_id.in_(identifiers)))
            session.execute(delete(SparkovInvestigation).where(SparkovInvestigation.investigation_id.in_(identifiers)))
            session.delete(payment)
        return {"transaction_id":transaction_id,"deleted_case_ids":identifiers}

    return router
