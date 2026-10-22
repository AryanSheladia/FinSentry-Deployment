"""Local fraud investigation workspace. Run one worker for in-process investigations."""
from contextlib import asynccontextmanager
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text,update
from sqlalchemy.exc import SQLAlchemyError

from backend.api.sparkov import create_sparkov_router,SparkovService
from backend.database.connection import ROOT,create_database,database_url
from backend.database.models import Base,SparkovInvestigation,utcnow

logger=logging.getLogger("finsentry")


def create_app(url=None,enable_sparkov=True):
    load_dotenv(ROOT/".env",override=False)

    @asynccontextmanager
    async def lifespan(app):
        engine,sessions=create_database(url or database_url())
        app.state.engine,app.state.sessions=engine,sessions
        try:
            Base.metadata.create_all(engine)
            app.state.sparkov=None
            if enable_sparkov:
                from backend.ml.sparkov_train import ARTIFACTS,STORE
                if (ARTIFACTS/"pipeline.joblib").exists() and STORE.exists():
                    app.state.sparkov=SparkovService()
            with sessions.begin() as session:
                session.execute(update(SparkovInvestigation).where(SparkovInvestigation.status.in_(["QUEUED","RUNNING"])).values(
                    status="FAILED",error="This investigation was interrupted. Submit the payment again.",updated_at=utcnow()))
            yield
        finally:
            engine.dispose()

    app=FastAPI(title="FinSentry AI",version="0.4.0",lifespan=lifespan)
    origins=[s.strip() for s in os.getenv("FRONTEND_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(",")]
    app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=["GET","POST","DELETE"],allow_headers=["Content-Type"])

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request,error):
        logger.error("Workspace database request failed (%s)",type(error).__name__)
        return JSONResponse(status_code=503,content={"detail":"The workspace is temporarily unavailable. Restore the local service and try again."})

    app.include_router(create_sparkov_router(app))

    @app.get("/health")
    def health():
        with app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        if app.state.sparkov is None:
            return JSONResponse(status_code=503,content={"status":"unavailable"})
        return {"status":"ready","workflow_mode":"SPARKOV_FIVE_AGENT_V2"}

    frontend=ROOT/"frontend/dist"
    if (frontend/"assets").is_dir():
        app.mount("/assets",StaticFiles(directory=frontend/"assets"),name="frontend-assets")

    @app.get("/",include_in_schema=False)
    def dashboard():
        if not (frontend/"index.html").is_file():
            raise HTTPException(503,"The analyst workspace has not been built yet.")
        return FileResponse(frontend/"index.html")

    @app.get("/favicon.svg",include_in_schema=False)
    def favicon():
        if not (frontend/"favicon.svg").is_file():
            raise HTTPException(404,"Not found")
        return FileResponse(frontend/"favicon.svg")

    return app


app=create_app()
