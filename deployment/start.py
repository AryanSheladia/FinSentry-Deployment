"""Start one cloud worker, using Railway MySQL references without printing secrets."""
import os
import base64
from pathlib import Path
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]


def configure_database(environ):
    query = {}
    certificate = environ.get("MYSQL_SSL_CA_BASE64", "").strip()
    if certificate:
        ca = base64.b64decode(certificate, validate=True).decode("ascii")
        if "-----BEGIN CERTIFICATE-----" not in ca:
            raise ValueError("Database CA must be a PEM certificate")
        path = ROOT / "runtime/cloud/mysql-ca.pem"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(ca, encoding="ascii")
        query = {"ssl_ca": str(path), "ssl_check_hostname": "true"}
    existing = environ.get("DATABASE_URL", "").strip()
    if existing:
        if existing.startswith("mysql://"):
            existing = "mysql+pymysql://" + existing[len("mysql://"):]
        if not existing.startswith("mysql+pymysql://"):
            raise ValueError("Cloud deployment requires a MySQL database URL")
        if query:
            from sqlalchemy.engine import make_url
            existing = make_url(existing).update_query_dict(query).render_as_string(hide_password=False)
        environ["DATABASE_URL"] = existing
        return existing
    keys = ["MYSQLHOST", "MYSQLPORT", "MYSQLUSER", "MYSQLPASSWORD", "MYSQLDATABASE"]
    if any(not environ.get(key) for key in keys):
        raise ValueError("Configure MySQL service references before starting FinSentry")
    url = URL.create("mysql+pymysql", username=environ["MYSQLUSER"], password=environ["MYSQLPASSWORD"],
        host=environ["MYSQLHOST"], port=int(environ["MYSQLPORT"]), database=environ["MYSQLDATABASE"], query=query)
    value = url.render_as_string(hide_password=False)
    environ["DATABASE_URL"] = value
    return value


def main():
    os.chdir(ROOT)
    for relative in ["frontend/dist/index.html", "models/sparkov_v2/pipeline.joblib", "runtime/sparkov/history.sqlite"]:
        if not (ROOT / relative).is_file():
            raise RuntimeError("Deployment is incomplete; rebuild the image with its verified artifacts")
    url = configure_database(os.environ)
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True, connect_args={"connect_timeout": 5})
    for attempt in range(1, 31):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            break
        except Exception:
            if attempt == 30:
                raise RuntimeError("Cloud database not ready; check private MySQL service references") from None
            print(f"Waiting for the cloud database ({attempt}/30)...", flush=True)
            time.sleep(2)
    engine.dispose()
    port = int(os.environ.get("PORT", "8000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be a valid TCP port")
    print(f"Starting FinSentry on port {port}; one investigation worker; database ready.", flush=True)
    os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0",
        "--port", str(port), "--workers", "1", "--access-log"])


if __name__ == "__main__":
    main()
