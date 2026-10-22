"""Package only the matched, label-free source store and saved model for a release."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

FILES = ("models/sparkov_v2/pipeline.joblib", "models/sparkov_v2/metadata.json", "runtime/sparkov/history.sqlite")


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = []
    for relative in FILES:
        path = args.source / relative
        records.append({"path": relative, "size": path.stat().st_size, "sha256": digest(path)})
    archive = args.output / "finsentry-artifacts-v1.tar.gz"
    with tarfile.open(archive, "w:gz", compresslevel=6) as tar:
        for relative in FILES:
            tar.add(args.source / relative, arcname=relative, recursive=False)
    manifest = {
        "schema_version": 1,
        "url": "https://github.com/AryanSheladia/FinSentry-Deployment/releases/download/artifacts-v1/finsentry-artifacts-v1.tar.gz",
        "archive_sha256": digest(archive), "archive_size": archive.stat().st_size,
        "files": records,
        "description": "Existing trained Sparkov model and matching read-only label-free source history; no credentials, submitted payments or analyst reviews.",
    }
    (Path(__file__).parent / "artifacts.lock.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "size": archive.stat().st_size, "sha256": manifest["archive_sha256"]}))


if __name__ == "__main__":
    main()
