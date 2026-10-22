"""Download and verify pinned deployment assets, or restore a supplied local archive."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FILES = {"models/sparkov_v2/pipeline.joblib", "models/sparkov_v2/metadata.json", "runtime/sparkov/history.sqlite"}


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def restore(archive, destination, manifest):
    if archive.stat().st_size != manifest["archive_size"] or digest(archive) != manifest["archive_sha256"]:
        raise ValueError("Deployment archive failed size/SHA-256 verification")
    records = {item["path"]: item for item in manifest["files"]}
    if set(records) != EXPECTED_FILES:
        raise ValueError("Unexpected artifact manifest paths")
    destination = destination.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if len(members) != len(records) or {member.name for member in members} != set(records):
            raise ValueError("Archive members do not match the manifest")
        for member in members:
            if not member.isfile() or member.size != records[member.name]["size"]:
                raise ValueError("Unsupported or oversized archive member")
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination):
                raise ValueError("Archive path escapes the deployment directory")
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as incoming, target.open("wb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            if digest(target) != records[member.name]["sha256"]:
                target.unlink()
                raise ValueError("Extracted artifact SHA-256 mismatch")
    print("Verified and restored the pinned model and matching source history.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--destination", type=Path, default=ROOT)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "deployment/artifacts.lock.json").read_text(encoding="utf-8"))
    if args.archive:
        restore(args.archive, args.destination, manifest)
        return
    expected_prefix = "https://github.com/AryanSheladia/FinSentry-Deployment/releases/download/"
    if not manifest["url"].startswith(expected_prefix):
        raise ValueError("Unexpected artifact download origin")
    with tempfile.TemporaryDirectory(prefix="finsentry-artifacts-") as directory:
        archive = Path(directory) / "artifacts.tar.gz"
        request = urllib.request.Request(manifest["url"], headers={"User-Agent": "FinSentry-Deployment"})
        with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as file:
            remaining = manifest["archive_size"]
            while block := response.read(min(1024 * 1024, remaining + 1)):
                remaining -= len(block)
                if remaining < 0:
                    raise ValueError("Download exceeds the pinned archive size")
                file.write(block)
        restore(archive, args.destination, manifest)


if __name__ == "__main__":
    main()
