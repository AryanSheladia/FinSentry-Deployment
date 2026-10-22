import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]


def database_url() -> str:
    load_dotenv(ROOT / ".env", override=False)
    value = os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is missing; run python scripts/local_mysql.py start first")
    return value


def create_database(url: str):
    arguments = {"pool_pre_ping": True, "hide_parameters": True}
    if url.startswith("sqlite"):
        # Test adapter only; actual local runtime is MySQL.
        arguments["connect_args"] = {"check_same_thread": False}
    else:
        arguments["connect_args"] = {"connect_timeout": 5}
    engine = create_engine(url, **arguments)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
