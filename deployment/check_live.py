"""Verify a deployed simulated workspace, retaining three clearly recorded demo cases."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Public HTTPS deployment URL")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.url.startswith("https://"):
        raise ValueError("Use the public HTTPS deployment URL")
    cases = []
    with httpx.Client(base_url=args.url.rstrip("/"), timeout=90) as client:
        health = client.get("/v2/health")
        health.raise_for_status()
        assert health.json()["status"] == "ready"
        home = client.get("/")
        home.raise_for_status()
        assert "<html" in home.text.lower()
        options = client.get("/v2/options")
        options.raise_for_status()
        options = options.json()
        demonstrations = [("safe", options["examples"][0], "CLEAR"),
            ("suspicious", options["behavior_demo"], "FLAG"),
            ("high_risk", options["examples"][-1], "ESCALATE")]
        for name, sample, expected in demonstrations:
            payload = {key: sample[key] for key in ("customer_id", "amount", "merchant", "category",
                "merchant_lat", "merchant_lon", "device_id", "payment_method")}
            payload.update(currency="USD", timestamp=datetime.fromtimestamp(sample["timestamp"], timezone.utc).isoformat())
            response = client.post("/v2/investigate", json=payload)
            response.raise_for_status()
            assert response.status_code == 202
            identifier = response.json()["investigation_id"]
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                current = client.get("/v2/investigations/" + identifier)
                current.raise_for_status()
                saved = current.json()
                if saved["status"] in {"COMPLETED", "FAILED"}:
                    break
                time.sleep(1)
            assert saved["status"] == "COMPLETED", "Live investigation did not complete"
            result = saved["result"]
            assert result["recommendation"] == expected, "Unexpected live demo recommendation"
            if name == "suspicious":
                assert {"UNUSUAL_TIME", "UNUSUAL_LOCATION"}.issubset({item["code"] for item in result["behavior"]["findings"]})
            cases.append({"name": name, "input": payload, "investigation_id": identifier,
                "recommendation": result["recommendation"], "risk_level": result["risk_level"],
                "risk_score": result["risk"]["risk_score"], "evidence_confidence": result["evidence_confidence"],
                "explanation_mode": result["explanation_mode"],
                "explanation_fallback_reason": result["explanation_fallback_reason"],
                "completed_stages": saved["completed_stages"]})
            print(json.dumps({"demo": name, "recommendation": result["recommendation"], "case": identifier}), flush=True)
        # Only this newly created disposable case is reviewed and deleted.
        disposable = {"customer_id": "NEW_DEPLOY_CHECK", "timestamp": "2020-07-20T12:00:00Z",
            "amount": 20, "currency": "USD", "merchant": "Deployment verification merchant", "category": "home",
            "home_lat": 40, "home_lon": -74, "merchant_lat": 40.01, "merchant_lon": -74.01,
            "device_id": "DEPLOY_CHECK_DEVICE", "payment_method": "CARD"}
        response = client.post("/v2/investigate", json=disposable)
        response.raise_for_status()
        identifier = response.json()["investigation_id"]
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            current = client.get("/v2/investigations/" + identifier)
            current.raise_for_status()
            if current.json()["status"] in {"COMPLETED", "FAILED"}:
                break
            time.sleep(1)
        assert current.json()["status"] == "COMPLETED"
        reviewed = client.post(f"/v2/investigations/{identifier}/review", json={"reviewer": "AUTOMATED_DEPLOY_CHECK",
            "action": "FLAG", "notes": "Disposable deployment persistence check; not a human fraud finding."})
        reviewed.raise_for_status()
        reloaded = client.get("/v2/investigations/" + identifier)
        reloaded.raise_for_status()
        assert reloaded.json()["reviews"][-1]["reviewer"] == "AUTOMATED_DEPLOY_CHECK"
        removed = client.delete("/v2/investigations/" + identifier)
        removed.raise_for_status()
        assert client.get("/v2/investigations/" + identifier).status_code == 404
        existing = client.get("/v2/investigations?limit=100")
        existing.raise_for_status()
        assert identifier not in {item["investigation_id"] for item in existing.json()}
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "url": args.url,
        "health": health.json(), "cases": cases, "review_save_reload_delete_verified": True,
        "note": "Three simulated demo cases retained. Only the separately created disposable verification case and its automated review were deleted."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Live checks passed; report saved without credentials.")


if __name__ == "__main__":
    main()
