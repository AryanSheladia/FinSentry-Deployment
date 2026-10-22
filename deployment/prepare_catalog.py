"""Compute unchanged dropdown data at build time instead of scanning on a free web CPU."""
import json
from pathlib import Path
import sys
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.database.sparkov_store import SparkovStore


def main():
    store = SparkovStore()
    options = store.options()
    with closing(store.connect()) as db:
        metadata = json.loads(db.execute("SELECT metadata_json FROM artifact_metadata").fetchone()[0])
    output = store.path.with_name("options.json")
    output.write_text(json.dumps({"schema_version": 1, "source_metadata": metadata, "options": options}, allow_nan=False), encoding="utf-8")
    assert store.options() == options
    print(f"Prepared and verified the customer/merchant catalog ({len(options['customers'])} customers, {len(options['merchants'])} merchant/category pairs).")


if __name__ == "__main__":
    main()
