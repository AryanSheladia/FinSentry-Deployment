"""Capture actual LangGraph node updates without changing cases or application code."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from langgraph.graph import StateGraph

from backend.agents.sparkov_explanation import SparkovExplainer
from backend.database.sparkov_store import SparkovStore
from backend.graph import sparkov_workflow as workflow
from backend.ml.sparkov_predict import SparkovPredictor
from backend.schemas.sparkov import NewPayment


def utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    load_dotenv(ROOT / ".env", override=False)
    output = ROOT / "output" / "execution_trace"
    output.mkdir(parents=True, exist_ok=True)
    run_id = "TRACE_" + uuid4().hex
    example = json.loads((ROOT / "data/sparkov/examples.json").read_text())["transactions"][-1]
    payload = {key: example[key] for key in (
        "customer_id", "amount", "merchant", "category", "merchant_lat",
        "merchant_lon", "device_id", "payment_method")}
    payload.update(currency="USD", timestamp=datetime.fromtimestamp(example["timestamp"], timezone.utc).isoformat())
    request = NewPayment.model_validate(payload)
    payment = request.model_dump(mode="json")
    payment["timestamp"] = int(request.timestamp.timestamp())
    payment["transaction_id"] = run_id
    predictor = SparkovPredictor()
    store = SparkovStore()
    store.verify(predictor.metadata)
    customer = store.customer(payment["customer_id"], payment["timestamp"])
    payment.update(home_lat=customer["home_lat"], home_lon=customer["home_lon"])
    vocab = predictor.bundle["preprocess"].named_transformers_["categorical"].categories_
    payment["unseen_category"] = payment["category"] not in vocab[0]
    payment["unseen_merchant"] = payment["merchant"] not in vocab[1]
    history = store.history(payment["customer_id"], payment["timestamp"])
    assert all(row["timestamp"] < payment["timestamp"] for row in history)
    explainer = SparkovExplainer()
    events = []
    progress_events = []
    started = utc()
    timer = time.perf_counter()

    # Only this isolated process wraps the graph's compiled invoke method. The
    # original nodes, edges, models, rules and provider client are executed.
    class CapturedGraph(StateGraph):
        def compile(self, *args, **kwargs):
            compiled = super().compile(*args, **kwargs)

            class Capture:
                def invoke(self, initial, config):
                    state = dict(initial)
                    for update in compiled.stream(initial, config, stream_mode="updates"):
                        for node, fields in update.items():
                            if fields is None:
                                continue
                            events.append({
                                "sequence": len(events) + 1,
                                "observed_at_utc": utc(),
                                "elapsed_seconds": round(time.perf_counter() - timer, 6),
                                "node": node,
                                "state_update": deepcopy(fields),
                            })
                            state.update(fields)
                    return state

            return Capture()

    original = workflow.StateGraph
    workflow.StateGraph = CapturedGraph
    try:
        result = workflow.investigate(payment, history, predictor, store, explainer,
            lambda stage: progress_events.append({"stage": stage, "observed_at_utc": utc()}))
    finally:
        workflow.StateGraph = original

    nodes = [event["node"] for event in events]
    assert nodes[0] == "plan" and nodes[-1] == "decision"
    assert nodes.index("intelligence") > max(nodes.index("risk"), nodes.index("behavior"))
    assert nodes.count("follow_up") == 1
    assert result["recommendation"] == "ESCALATE" and result["risk_level"] == "HIGH"
    assert abs(result["risk"]["risk_score"] - 0.999932510377034) < 1e-10
    assert result["behavior"]["history_count"] == 6
    assert result["intelligence"]["status"] == "NO_MATCH"
    assert result["follow_up"]["conflict_resolved"] is False

    report = {
        "run_id": run_id, "started_at_utc": started, "finished_at_utc": utc(),
        "capture_method": "Actual compiled production LangGraph streamed with stream_mode=updates; unchanged nodes and edges.",
        "scope": "Fresh read-only workflow execution; not an HTTP submission and not a saved MySQL investigation. Source SQLite history only, excluding previously submitted MySQL payments.",
        "communication": "Agents exchange typed shared-state updates. These are executed handoffs, not invented agent chat messages. Parallel branch emission order does not imply sequential execution.",
        "input": payload, "normalized_payment": payment,
        "history_count": len(history), "history_cutoff": "Strictly before the transaction timestamp",
        "model_version": predictor.metadata["model_version"],
        "source_files_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (
            "backend/graph/sparkov_workflow.py", "backend/agents/sparkov_behavior.py",
            "backend/agents/sparkov_decision.py", "backend/agents/sparkov_explanation.py",
            "backend/database/sparkov_store.py", "backend/ml/sparkov_predict.py")},
        "progress_events": progress_events, "node_updates": events, "result": result,
        "checks": {"all_history_strictly_prior": True, "risk_behavior_join_observed": True,
            "single_follow_up_observed": True, "expected_high_risk_result": True,
            "cases_or_reviews_written": False},
    }
    raw_path = output / "FinSentry_AI_Execution_Trace.json"
    raw_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with (output / "FinSentry_AI_Node_Updates.jsonl").open("w", encoding="utf-8") as file:
        for event in events:
            file.write(json.dumps(event, allow_nan=False) + "\n")

    lines = [
        "FinSentry AI — Captured Agent Execution Trace",
        f"Run ID: {run_id}", f"Captured: {started}",
        "Method: actual production LangGraph node-state updates, captured during a fresh execution.",
        "Scope: read-only workflow run using the trained model and source history; no HTTP/MySQL case created.",
        "Agent communication: shared state, rather than conversational messages between five LLMs.",
        "Risk and Behavior execute as parallel branches; the displayed order is update arrival order.",
        "", "INPUT", json.dumps(payload, indent=2),
        f"Earlier source payments loaded: {len(history)}; all strictly before the input timestamp.", "",
    ]
    for event in events:
        fields = event["state_update"]
        lines.append(f"[{event['observed_at_utc']}] {event['node']} (+{event['elapsed_seconds']:.3f}s)")
        if event["node"] == "plan":
            lines.extend(["Supervisor Agent → parallel Transaction Risk and Customer Behavior agents.",
                "Shared-state write: " + json.dumps(fields),
                "Both branches receive the transaction and strictly earlier history."])
        elif event["node"] == "risk":
            risk = fields["risk"]
            lines.extend(["Transaction Risk Agent → shared state: risk", json.dumps(risk, indent=2)])
        elif event["node"] == "behavior":
            lines.extend(["Customer Behavior Agent → shared state: behavior", json.dumps(fields["behavior"], indent=2)])
        elif event["node"] == "intelligence":
            lines.extend(["Join reached after both Risk and Behavior outputs; Fraud Intelligence Agent executed.",
                "Shared-state writes: intelligence, quality", json.dumps(fields, indent=2),
                "Conditional route → follow_up: model_flag=true and no UNUSUAL_AMOUNT, HIGH_FREQUENCY, UNUSUAL_LOCATION or UNUSUAL_TIME finding."])
        elif event["node"] == "follow_up":
            lines.extend(["Supervisor's bounded follow-up → merchant activity lookup → Decision & Explanation Agent.",
                "Shared-state write: follow_up", json.dumps(fields["follow_up"], indent=2)])
        else:
            final = fields["result"]
            selected = {key: final[key] for key in (
                "recommendation", "risk_level", "evidence_confidence", "confidence_basis",
                "reasons", "conflict_remaining", "explanation_mode", "explanation_provider",
                "explanation_model", "explanation_fallback_reason", "explanation", "cited_case_ids")}
            lines.extend(["Decision & Explanation Agent received risk, behavior, intelligence, quality, plan and follow_up.",
                json.dumps(selected, indent=2), "Decision → END. Human review recommended; no payment action executed."])
        lines.append("")
    lines.extend(["VALIDATION", json.dumps(report["checks"], indent=2),
        "All findings concern simulated Sparkov payments. No historical fraud match does not establish safety.",
        "Raw evidence: FinSentry_AI_Execution_Trace.json; one captured state update per line: FinSentry_AI_Node_Updates.jsonl."])
    text_path = output / "FinSentry_AI_Execution_Trace.txt"
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "started_at_utc": started, "nodes": nodes,
        "history_count": len(history), "model_score": result["risk"]["risk_score"],
        "recommendation": result["recommendation"], "risk_level": result["risk_level"],
        "evidence_confidence": result["evidence_confidence"],
        "follow_up": result["follow_up"], "explanation_mode": result["explanation_mode"],
        "explanation_fallback_reason": result["explanation_fallback_reason"],
        "text_path": str(text_path), "raw_path": str(raw_path)}, indent=2))


if __name__ == "__main__":
    main()
