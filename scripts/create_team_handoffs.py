r"""Create disjoint, secret-checked source handoffs; never commits or pushes.

Usage: python scripts/create_team_handoffs.py --output E:\flexi_repo
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/AryanSheladia/FinSentry-AI.git"
BASE = "500c37381f40fc1e3109587cc01f489d87f63acb"
MEMBERS = ["Parth", "Aryan", "Yash", "Pratik"]
SCOPES = ["Data, model and reproducibility", "Input, history, persistence and backend startup",
          "Agent coordination, evidence, decisions and explanations", "Analyst interface and final integration"]

# This wrapper is outside project/, and is never automatically committed.
APPLY_HELPER = r'''"""Apply only manifest-listed source files. This helper never commits or pushes."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo, *arguments):
    result = subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--stage", action="store_true", help="Stage only the copied manifest paths; does not commit/push")
    parser.add_argument("--check", action="store_true", help="Verify an already applied package without writing")
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    manifest = json.loads((package/"PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    repo = args.repo.resolve(strict=True)
    if repo == package or repo.is_relative_to(package):
        raise ValueError("Clone the repository outside the extracted handoff folder")
    if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("--repo must name the clone root")
    remote = git(repo, "remote", "get-url", "origin").rstrip("/").removesuffix(".git")
    if remote.lower() not in {"https://github.com/aryansheladia/finsentry-ai", "git@github.com:aryansheladia/finsentry-ai", "ssh://git@github.com/aryansheladia/finsentry-ai"}:
        raise ValueError("This clone is not the intended FinSentry-AI repository")
    if git(repo, "branch", "--show-current") != "main":
        raise ValueError("Check out main and pull the previous package first")
    if not args.check and git(repo, "status", "--porcelain"):
        raise ValueError("The clone has uncommitted changes. Review/commit or preserve them before applying a package")
    for receipt in manifest["required_receipts"]:
        if not (repo/receipt).is_file():
            raise ValueError("Previous handoff is missing: "+receipt+". Wait for its push and pull main")
    source_root = (package/"project").resolve()
    copies = []
    for item in manifest["files"]:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or "\\" in item["path"]:
            raise ValueError("Unsafe path in package manifest")
        source = source_root.joinpath(*relative.parts)
        destination = repo.joinpath(*relative.parts)
        if not source.resolve().is_relative_to(source_root) or source.is_symlink():
            raise ValueError("Package source escapes project/")
        if not destination.resolve().is_relative_to(repo):
            raise ValueError("Destination escapes the clone")
        current = destination
        while current != repo:
            if current.is_symlink() or current.is_junction():
                raise ValueError("Refusing a linked/junction destination")
            current = current.parent
        if digest(source) != item["sha256"]:
            raise ValueError("Package file changed: "+item["path"])
        if destination.exists():
            if not destination.is_file() or digest(destination) != item["sha256"]:
                raise ValueError("Existing file would be overwritten: "+item["path"])
        elif args.check:
            raise ValueError("Missing applied file: "+item["path"])
        else:
            copies.append((source,destination))
    if args.check:
        print("Verified package for "+manifest["member"]+" (all files match)")
        return
    for source,destination in copies:
        destination.parent.mkdir(parents=True,exist_ok=True)
        with source.open("rb") as incoming, destination.open("xb") as outgoing:
            shutil.copyfileobj(incoming,outgoing)
    if args.stage:
        git(repo,"add","--",*[item["path"] for item in manifest["files"]])
    print("Applied "+manifest["member"]+" package: "+str(len(manifest["files"]))+" paths")
    print("Review the changes, fill docs/reviews/"+manifest["member"]+".md, stage your notes/fixes, then commit and push using your own account.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print("Package not applied: "+str(error),file=sys.stderr)
        raise SystemExit(1)
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assignments():
    groups = {name: set() for name in MEMBERS}

    def add(member, *paths):
        for path in paths:
            target = ROOT/path
            if target.is_dir():
                groups[member].update(p.relative_to(ROOT).as_posix() for p in target.rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".tsbuildinfo"})
            else:
                if not target.is_file():
                    raise FileNotFoundError(path)
                groups[member].add(path)

    add("Parth", ".gitignore", "README.md", "pytest.ini", "backend/__init__.py", "backend/ml",
        "backend/requirements.txt", "backend/requirements-lock.txt", "backend/constraints.txt",
        "models/sparkov_v2/metadata.json", "data/sparkov/examples.json", "tests/test_sparkov_features.py",
        "scripts/audit_sparkov_model.py", "scripts/lock_dependencies.py", "reports/sparkov_training.json",
        "reports/model_accuracy_audit.json", "reports/MODEL_ACCURACY_REVIEW.md", "reports/SPARKOV_UPGRADE.md",
        "docs/DATA_AND_MODEL_SETUP.md", "docs/GITHUB_HANDOFF.md", "docs/reviews/Parth.md")
    add("Aryan", "backend/api", "backend/database", "backend/schemas", "backend/main.py", "backend/Dockerfile",
        "tests/test_analyst_backend.py", "tests/test_transaction_delete.py", "scripts/local_mysql.py",
        "scripts/start_backend.ps1", "start_backend.py", ".env.example", ".env.docker.example", ".dockerignore",
        "docker-compose.yml", "reports/transaction_delete_verification.json", "reports/delete_runtime_fix.json",
        "reports/retired_store_cleanup.json", "docs/reviews/Aryan.md")
    add("Yash", "backend/agents", "backend/graph", "backend/services", "tests/test_sparkov_workflow.py",
        "tests/test_sparkov_time_location.py", "data/sparkov/time_location_demo.json", "scripts/test_time_location.py",
        "scripts/smoke_sparkov.py", "reports/TIME_LOCATION_WALKTHROUGH.md", "reports/time_location_test.json",
        "reports/architecture.md", "reports/DEMO_THREE_CASES.md", "reports/demo_three_cases_verified.json",
        "reports/demo_script.md", "reports/sparkov_smoke.json", "docs/reviews/Yash.md")
    # Explicit frontend directories avoid copying dependencies or compiled assets.
    add("Pratik", "frontend/src", "frontend/public", "frontend/tests", "frontend/package.json",
        "frontend/package-lock.json", "frontend/tsconfig.json", "frontend/vite.config.ts", "frontend/index.html",
        "frontend/Dockerfile", "frontend/nginx.conf", "frontend/README.md", "scripts/start_project.ps1",
        "scripts/create_team_handoffs.py", "FINSENTRY_TEAM_EXECUTION_GUIDE.md", "reports/contributions.md",
        "reports/SPARKOV_DEMO_GUIDE.md", "reports/browser_qa.md", "reports/analyst_workspace_verification.json",
        "reports/sparkov_ui_checks.json", "reports/sparkov_integrity.json", "reports/sparkov_status.json",
        "docs/reviews/Pratik.md")
    owners = {}
    for member,paths in groups.items():
        for path in paths:
            if path in owners:
                raise ValueError("Overlapping ownership: "+path)
            owners[path] = member
    # Detect accidentally omitted active source/doc/config files.
    excluded_dirs = {".git", ".venv", "runtime", "dataset", "node_modules", "dist", "__pycache__", ".pytest_cache"}
    extensions = {".py", ".ps1", ".ts", ".tsx", ".css", ".svg", ".html", ".md", ".json", ".txt", ".yml", ".mjs", ".conf", ".ini"}
    for current,dirs,files in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in excluded_dirs]
        for name in files:
            path = Path(current)/name
            relative = path.relative_to(ROOT).as_posix()
            if path.suffix in extensions and relative not in owners:
                raise ValueError("Unassigned active file: "+relative)
    return groups


def private_values():
    values = set()
    env = ROOT/".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            key,value = line.split("=",1)
            value = value.strip().strip("\"'")
            if re.search(r"KEY|PASSWORD|SECRET|TOKEN|DATABASE_URL",key) and len(value)>=12:
                values.add(value)
                if key.strip()=="DATABASE_URL" and urlsplit(value).password:
                    values.add(urlsplit(value).password)
    admin = ROOT/"runtime/mysql-admin.json"
    if admin.is_file():
        values.update(str(value) for value in json.loads(admin.read_text(encoding="utf-8")).values() if len(str(value))>=12)
    return [value.encode() for value in values]


def check_payload(path, data, secrets):
    if any(value in data for value in secrets):
        raise ValueError("Private credential detected in "+path+" (value withheld)")
    if re.search(rb"(?:gsk_|ghp_|github_pat_)[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",data):
        raise ValueError("Credential-like material detected in "+path+" (value withheld)")
    data.decode("utf-8")
    if len(data)>10*1024*1024:
        raise ValueError("Unexpectedly large source file: "+path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if output != Path("E:/flexi_repo").resolve() and not output.is_relative_to((ROOT/"runtime").resolve()):
        raise ValueError("Output must be E:/flexi_repo or a new staging directory under this project's runtime")
    for parent in [output,*output.parents]:
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("Output must not traverse a link or junction")
    for name in [*MEMBERS,"START_HERE.md","HANDOFF_INDEX.json","VERIFICATION.json"]:
        if (output/name).exists():
            raise FileExistsError("Refusing to overwrite existing handoff: "+str(output/name))
    groups=assignments()
    secrets=private_values()
    snapshot={}
    for paths in groups.values():
        for path in paths:
            source=ROOT/path
            if source.is_symlink() or source.is_junction():
                raise ValueError("Refusing linked source: "+path)
            content=source.read_bytes()
            check_payload(path,content,secrets)
            snapshot[path]=content
    index={"repository":REPOSITORY,"branch":"main","inspected_base_commit":BASE,
           "created_at_utc":datetime.now(timezone.utc).isoformat(),"remote_modified":False,
           "provenance":"Codex-assisted source prepared on Aryan's device. Assigned scope does not establish independent authorship or equal effort.",
           "packages":[]}
    output.mkdir(parents=True,exist_ok=True)
    previous=[]
    for number,member in enumerate(MEMBERS,1):
        folder=output/member
        folder.mkdir()
        payload={path:snapshot[path] for path in sorted(groups[member])}
        receipt=f"docs/handoffs/{number:02d}_{member}.json"
        receipt_data={"package":member,"order":number,"scope":SCOPES[number-1],"inspected_base_commit":BASE,
                      "review_status":"Assigned for review; this receipt is not a review sign-off",
                      "file_paths":sorted(payload),"provenance":index["provenance"]}
        payload[receipt]=(json.dumps(receipt_data,indent=2)+"\n").encode()
        manifest={"member":member,"order":number,"scope":SCOPES[number-1],"repository":REPOSITORY,"branch":"main",
                  "required_receipts":list(previous),"files":[]}
        for path,content in sorted(payload.items()):
            target=folder/"project"/path
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(content)
            manifest["files"].append({"path":path,"bytes":len(content),"sha256":digest(content)})
        instructions=f'''# {member}: handoff {number} of 4

Scope: **{SCOPES[number-1]}**. Upload order: Parth → Aryan → Yash → Pratik.

This is a package of assisted source for you to review and integrate. It does not claim you independently wrote it or that it represents 25% of measured effort. Fill `project/docs/reviews/{member}.md` with the review and testing you actually perform.

## Upload instructions (PowerShell)

1. Extract this ZIP into its own folder, for example `C:\\FinSentryHandoffs\\{member}`. Do not initialize Git in the extracted package.
2. Ensure you are an accepted collaborator on the repository. Wait until {MEMBERS[number-2] if number>1 else 'you are ready to start the first handoff'}{' has pushed their package' if number>1 else ''}.
3. Clone into a separate folder:

   ```powershell
   git clone {REPOSITORY}
   cd FinSentry-AI
   git switch main
   git pull --ff-only origin main
   git config user.name "{member}"
   git config user.email "YOUR_OWN_GITHUB_LINKED_EMAIL"
   ```

   Replace the email placeholder with your own linked email or GitHub-provided noreply email. Use your own real display name if different. These commands configure this clone only. Authenticate GitHub as yourself; do not share tokens.
4. Apply/stage your package from this repository directory. Replace the example extracted-package path:

   ```powershell
   python "C:\\FinSentryHandoffs\\{member}\\APPLY_PACKAGE.py" --repo . --stage
   ```

   The helper verifies a clean `main` clone, the repository URL, previous-package receipts, hashes and no-overwrite safety. It does not create commits or push anything. Only `project/` contents are copied into the clone root; wrappers and ZIPs stay outside Git.
5. Inspect your assigned files. Complete `docs/reviews/{member}.md`, run the applicable checks listed there and make any genuine fixes. Stage your completed note/fixes and inspect the staged diff:

   ```powershell
   git add -- docs/reviews/{member}.md
   git diff --cached --stat
   git diff --cached
   ```

   Add any other actual fixes explicitly by file path. Do not stage secrets, local databases, downloaded data, generated binary models or installed dependencies.
6. When your reviewed changes are ready:

   ```powershell
   git commit -m "Integrate {SCOPES[number-1].lower()} package" -m "Assisted source handoff; actual review and checks are recorded in docs/reviews/{member}.md."
   git push origin main
   ```

   Tell {MEMBERS[number] if number<4 else 'the team'} when the push succeeds. There is no need to delete or replace the existing repository. Never force-push. If branch protection requires a PR, push your work on a feature branch and merge it into `main` before the next member continues.

## Notes

- Packages 1–3 are intentionally partial; the complete application arrives after package 4. Read `docs/DATA_AND_MODEL_SETUP.md` for datasets, model generation, private `.env`, dependencies and startup.
- Source ZIPs exclude raw datasets, `.venv`, `node_modules`, `dist`, runtime/MySQL/SQLite files, private environment files, old backups and binary models. The original working `E:\\FinSentry` installation remains in place.
- If someone changed files assigned to this package, the helper refuses an overwrite. Review that difference instead of forcing it. If a push is rejected, fetch/pull and resolve normally; do not rewrite history.
- GitHub file counts and commit counts do not prove equal effort or guarantee marks. A valid contribution email and merge to the default branch affect visible credit; see `docs/GITHUB_HANDOFF.md`.
'''
        for name,content in [("START_HERE.md",instructions.encode()),("APPLY_PACKAGE.py",APPLY_HELPER.encode()),
                             ("PACKAGE_MANIFEST.json",(json.dumps(manifest,indent=2)+"\n").encode())]:
            check_payload(name,content,secrets)
            (folder/name).write_bytes(content)
        archive=folder/f"FinSentry_{member}.zip"
        with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(folder.rglob("*")):
                if path.is_file() and path!=archive:
                    zipped.write(path,path.relative_to(folder).as_posix())
        with zipfile.ZipFile(archive) as zipped:
            if zipped.testzip() is not None:
                raise ValueError("ZIP integrity check failed")
            for path in zipped.namelist():
                check_payload(path,zipped.read(path),secrets)
        previous.append(receipt)
        index["packages"].append({"member":member,"order":number,"scope":SCOPES[number-1],
                                  "file_count":len(payload),"source_bytes":sum(map(len,payload.values())),
                                  "zip":str(archive.relative_to(output)),"zip_bytes":archive.stat().st_size,
                                  "zip_sha256":digest(archive.read_bytes())})
    root_guide='''# FinSentry: send these four packages in order

1. **Parth/FinSentry_Parth.zip** — data/model and source setup.
2. **Aryan/FinSentry_Aryan.zip** — input/history/database/API and backend startup.
3. **Yash/FinSentry_Yash.zip** — agents, evidence, decisions and explanation/demo walkthroughs.
4. **Pratik/FinSentry_Pratik.zip** — analyst frontend and final integration.

Send each person their named ZIP. Each ZIP includes source under `project/`, its own START_HERE.md, a hash manifest and a safe apply/stage helper. The same contents are available unpacked in each named folder. Do not send the source project itself or any private `.env` file.

Target: https://github.com/AryanSheladia/FinSentry-AI, branch main. No files have been pushed by the packaging operation. Existing history is preserved. Aryan must ensure all three teammates are accepted collaborators; each member commits and pushes from their own GitHub account with their own linked commit email.

**Wait for each push before the next member pulls and applies their package.** File paths do not overlap. The helper stops on missing earlier-package receipts or conflicting files. Upload only the contents of `project/` into the repository root; never commit the ZIP, helper wrapper, manifest wrapper or member folder. Follow the individual START_HERE.md commands.

Members should review, test and record their own work in docs/reviews/. Source was prepared with Codex assistance on Aryan's device. These assignments do not establish equal measured effort, independent authorship or a guaranteed 25% GitHub contribution each. No identity or authorship is forged. Integrating reviewed assisted source can be recorded honestly without claiming independent original implementation.

Raw datasets, keys, private environment files, databases, local records/backups, dependencies, compiled frontend assets and binary models are excluded. Recreate these after all packages land using docs/DATA_AND_MODEL_SETUP.md. Keep the original E:\\FinSentry working setup for the demonstration.

GitHub contribution visibility: https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/troubleshooting-missing-contributions
'''
    (output/"START_HERE.md").write_text(root_guide,encoding="utf-8")
    (output/"HANDOFF_INDEX.json").write_text(json.dumps(index,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"output":str(output),"packages":index["packages"],"unique_source_files":len(snapshot),
                      "overlapping_paths":0,"credential_matches":0,"remote_modified":False},indent=2))


if __name__ == "__main__":
    main()
