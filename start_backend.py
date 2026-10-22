"""Run this file from VS Code or with `python start_backend.py`.

Starts the project-owned MySQL service and runs the backend in this terminal.
Uses the project's virtual environment regardless of VS Code's selected Python.
Press Ctrl+C to stop the backend. MySQL remains available for the next run.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the FinSentry backend and local database.")
    parser.add_argument("--restart", action="store_true", help="Accepted for compatibility; each run starts a fresh foreground backend.")
    parser.parse_args()

    python = ROOT / ".venv" / "Scripts" / "python.exe"
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not python.is_file():
        print("Project Python environment is missing. Follow the setup instructions in README.md.", file=sys.stderr)
        return 1
    if not shell:
        print("PowerShell is required to run the project's Windows backend launcher.", file=sys.stderr)
        return 1

    command = [shell, "-NoProfile", "-File", str(ROOT / "scripts" / "start_backend.ps1"), "-StopOnly"]
    process = None
    pid_path = ROOT / "runtime" / "backend.pid"

    try:
        subprocess.run([str(python), str(ROOT / "scripts" / "local_mysql.py"), "start"], cwd=ROOT, check=True)
        subprocess.run(command, cwd=ROOT, check=True)
        print("Backend: http://127.0.0.1:8000", flush=True)
        print("Request logs appear below. Press Ctrl+C to stop the backend.", flush=True)
        process = subprocess.Popen(
            [str(python), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
             "--port", "8000", "--workers", "1", "--access-log"],
            cwd=ROOT,
        )
        pid_path.write_text(str(process.pid), encoding="utf-8")
        return process.wait()
    except subprocess.CalledProcessError as error:
        print("Startup failed. Check the message above or runtime/backend-error.log.", file=sys.stderr)
        return error.returncode or 1
    except OSError as error:
        print(f"Could not launch a required service: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopping backend...", flush=True)
        if process is not None:
            try:
                process.wait(timeout=10)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                process.terminate()
                process.wait()
        return 130
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                process.wait()
            if pid_path.exists() and pid_path.read_text(encoding="utf-8").strip() == str(process.pid):
                pid_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
