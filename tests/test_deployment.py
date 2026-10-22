"""Deployment checks for database URL handling and artifact tamper detection."""
import hashlib
import io
import json
import sqlite3
import tarfile

import pytest
from sqlalchemy.engine import make_url

from deployment.restore_artifacts import EXPECTED_FILES, restore
from deployment.start import configure_database
from backend.database.sparkov_store import SparkovStore


def test_railway_variables_handle_reserved_password_characters():
    env = dict(MYSQLHOST="mysql.railway.internal", MYSQLPORT="3306", MYSQLUSER="app",
        MYSQLPASSWORD="test-only-@:/#%", MYSQLDATABASE="railway")
    url = make_url(configure_database(env))
    assert url.password == "test-only-@:/#%"
    assert url.drivername == "mysql+pymysql"
    assert url.host == "mysql.railway.internal"


def test_mysql_url_is_normalized_and_non_mysql_rejected():
    assert configure_database({"DATABASE_URL": "mysql://u:p@mysql:3306/app"}).startswith("mysql+pymysql://")
    with pytest.raises(ValueError):
        configure_database({"DATABASE_URL": "sqlite:///temporary.sqlite"})
    with pytest.raises(ValueError):
        configure_database({})


def test_pinned_archive_rejects_tampering_and_unsafe_members(tmp_path):
    payload = b"deployment test artifact"
    paths = sorted(EXPECTED_FILES)
    archive = tmp_path / "artifacts.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for path in paths:
            entry = tarfile.TarInfo(path)
            entry.size = len(payload)
            tar.addfile(entry, io.BytesIO(payload))
    manifest = {"archive_size": archive.stat().st_size,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files": [{"path": path, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()} for path in paths]}
    restore(archive, tmp_path / "restored", manifest)
    assert (tmp_path / "restored/runtime/sparkov/history.sqlite").read_bytes() == payload
    with pytest.raises(ValueError):
        restore(archive, tmp_path / "bad", dict(manifest, archive_sha256="0" * 64))
    invalid = dict(manifest, files=[dict(item, path="../outside") for item in manifest["files"]])
    with pytest.raises(ValueError):
        restore(archive, tmp_path / "bad", invalid)


def test_catalog_cache_matches_source_build_and_stale_catalog_falls_back(tmp_path):
    source = tmp_path / "history.sqlite"
    metadata = {"trained_at_utc": "verified-build", "source": "fixture"}
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE artifact_metadata(metadata_json TEXT)")
        db.execute("INSERT INTO artifact_metadata VALUES (?)", (json.dumps(metadata),))
        db.execute("CREATE TABLE customers(customer_id TEXT)")
        db.execute("INSERT INTO customers VALUES ('CUST_FIXTURE')")
        db.execute("CREATE TABLE transactions(merchant TEXT, category TEXT, merchant_lat REAL, merchant_lon REAL)")
        db.execute("INSERT INTO transactions VALUES ('Merchant', 'home', 40, -74)")
        db.execute("CREATE TABLE cases(case_id TEXT)")
    store = SparkovStore(source)
    expected = store.options()
    cache = source.with_name("options.json")
    cache.write_text(json.dumps({"schema_version": 1, "source_metadata": metadata, "options": expected}), encoding="utf-8")
    assert store.options() == expected
    stale = {"customers": [], "merchants": [], "case_count": 999}
    cache.write_text(json.dumps({"schema_version": 1, "source_metadata": {"trained_at_utc": "old"}, "options": stale}), encoding="utf-8")
    assert store.options() == expected
