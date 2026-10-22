"""Start/stop a project-owned MySQL instance without changing existing installations."""

import argparse
import json
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time

import pymysql

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
DATA = RUNTIME / "mysql-data"
CREDENTIALS = RUNTIME / "mysql-admin.json"
PORT = 3307


def connect(password: str):
    return pymysql.connect(host="127.0.0.1", port=PORT, user="root", password=password,
                           connect_timeout=2, autocommit=True)


def owned_connection(settings):
    for password in [settings["root_password"], ""]:
        try:
            connection = connect(password)
        except pymysql.MySQLError:
            continue
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@datadir")
            actual = Path(cursor.fetchone()[0]).resolve()
        if actual != DATA.resolve():
            connection.close()
            raise RuntimeError("Port 3307 belongs to another database; refusing to modify it")
        return connection
    raise RuntimeError("Project database credentials are not accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop"], default="start", nargs="?")
    args = parser.parse_args()
    RUNTIME.mkdir(exist_ok=True)
    (RUNTIME / "tmp").mkdir(exist_ok=True)
    if args.action == "stop":
        if not CREDENTIALS.exists():
            raise RuntimeError("No project database is configured")
        settings = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
        connection = owned_connection(settings)
        with connection.cursor() as cursor:
            cursor.execute("SHUTDOWN")
        connection.close()
        print("Stopped the project-owned MySQL instance.")
        return
    if CREDENTIALS.exists():
        settings = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    else:
        if DATA.exists() and any(DATA.iterdir()):
            raise RuntimeError("Existing data without project credentials; refusing to reinitialize")
        settings = {"root_password": secrets.token_hex(24), "app_password": secrets.token_hex(24)}
        CREDENTIALS.write_text(json.dumps(settings), encoding="utf-8")
    executable = shutil.which("mysqld")
    if not executable:
        raise RuntimeError("mysqld is not on PATH; install MySQL 8 or use a configured MySQL URL")
    basedir = Path(executable).resolve().parents[1]
    DATA.mkdir(exist_ok=True)
    if not (DATA / "mysql").is_dir():
        if any(DATA.iterdir()):
            raise RuntimeError("Partial data initialization found; inspect runtime/mysql-init.log before retrying")
        print("Initializing a new MySQL data directory inside the workspace...", flush=True)
        with (RUNTIME / "mysql-init.log").open("w", encoding="utf-8") as log:
            subprocess.run([executable, "--no-defaults", "--initialize-insecure", "--console",
                            f"--basedir={basedir}", f"--datadir={DATA}", f"--tmpdir={RUNTIME / 'tmp'}"],
                           stdout=log, stderr=subprocess.STDOUT, check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    with socket.socket() as probe:
        is_running = probe.connect_ex(("127.0.0.1", PORT)) == 0
    if not is_running:
        with (RUNTIME / "mysql-server.log").open("a", encoding="utf-8") as log:
            subprocess.Popen([executable, "--no-defaults", "--console", f"--basedir={basedir}",
                              f"--datadir={DATA}", "--bind-address=127.0.0.1", f"--port={PORT}",
                              f"--tmpdir={RUNTIME / 'tmp'}",
                              "--mysqlx=0", "--innodb-buffer-pool-size=128M",
                              f"--pid-file={RUNTIME / 'mysql.pid'}"],
                             stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 45
    connection = None
    while time.monotonic() < deadline:
        try:
            connection = owned_connection(settings)
            break
        except RuntimeError as error:
            if "another database" in str(error):
                raise
            time.sleep(0.5)
    if connection is None:
        raise RuntimeError("MySQL did not become ready; inspect runtime/mysql-server.log")
    with connection.cursor() as cursor:
        cursor.execute("CREATE DATABASE IF NOT EXISTS finsentry CHARACTER SET utf8mb4")
        cursor.execute("CREATE USER IF NOT EXISTS 'finsentry_app'@'127.0.0.1' IDENTIFIED BY %s",
                       (settings["app_password"],))
        cursor.execute("ALTER USER 'finsentry_app'@'127.0.0.1' IDENTIFIED BY %s", (settings["app_password"],))
        cursor.execute("GRANT ALL PRIVILEGES ON finsentry.* TO 'finsentry_app'@'127.0.0.1'")
        cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (settings["root_password"],))
    connection.close()
    env_path = ROOT / ".env"
    if not env_path.exists():
        env_path.write_text("DATABASE_URL=mysql+pymysql://finsentry_app:" + settings["app_password"]
                            + "@127.0.0.1:3307/finsentry\n"
                            + "FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173\n", encoding="utf-8")
    print("Project MySQL ready on 127.0.0.1:3307. Credentials are local and are not printed.")


if __name__ == "__main__":
    main()
