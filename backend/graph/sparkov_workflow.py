from typing import Any,TypedDict

from langgraph.graph import START,END,StateGraph

from backend.agents.sparkov_behavior import analyze
from backend.agents.sparkov_decision import assess


class State(TypedDict,total=False):
    payment:dict[str,Any]
    history:list[dict]
    plan:list[str]
    risk:dict
    behavior:dict
    intelligence:dict
    quality:dict
    follow_up:dict|None
    result:dict


def quality(payment,behavior,metadata):
    limits=[]
    if behavior["history_count"]<5:
        limits.append("Insufficient customer history; normal behavior cannot be established.")
    if behavior["recent_30d_count"]<5:
        limits.append("Fewer than five payments in the preceding 30 days.")
    if not payment.get("device_id"):
        limits.append("Device information is missing.")
    if payment["timestamp"]>metadata["splits"]["test"]["max_timestamp"] or payment["timestamp"]<metadata["splits"]["test"]["min_timestamp"]:
        limits.append("Transaction date is outside the evaluated test period; model reliability is unverified for this date.")
    if payment.get("unseen_merchant") or payment.get("unseen_category"):
        limits.append("Merchant or category is outside the training vocabulary.")
    confidence="LOW" if behavior["recent_30d_count"]<5 or any("outside" in v for v in limits) else "MEDIUM" if limits or behavior["history_count"]<20 else "HIGH"
    return {"confidence":confidence,"limitations":limits,"meaning":"Evidence coverage within the simulation, not probability the decision is correct."}


def investigate(payment,history,predictor,store,explainer,progress):
    def plan(state):
        progress("supervisor")
        return {"plan":["Score the transaction", "Compare strictly earlier customer history", "Check prior known fraud entities", "Resolve conflicts once", "Aggregate evidence and recommend human action"],"follow_up":None}
    def risk(state):
        result=predictor.predict(state["payment"],state["history"])
        progress("risk")
        return {"risk":result}
    def behavior(state):
        result=analyze(state["payment"],state["history"])
        progress("behavior")
        return {"behavior":result}
    def intelligence(state):
        try:
            result=store.intelligence(state["payment"])
        except Exception:
            result={"status":"UNAVAILABLE","cases":[],"customer_link":False,"merchant_link":False,"limitations":["Fraud evidence lookup unavailable."]}
        progress("intelligence")
        coverage=quality(state["payment"],state["behavior"],predictor.metadata)
        if result["status"]=="UNAVAILABLE":
            coverage["confidence"]="LOW"
            coverage["limitations"].append("Fraud intelligence is unavailable; the evidence check is incomplete.")
        return {"intelligence":result,"quality":coverage}
    def conflict(state):
        return "follow_up" if ((state["risk"]["model_flag"] and not any(f["code"] in {"UNUSUAL_AMOUNT","HIGH_FREQUENCY","UNUSUAL_LOCATION","UNUSUAL_TIME"} for f in state["behavior"]["findings"])) or
            (not state["risk"]["model_flag"] and state["intelligence"].get("customer_link"))) else "decision"
    def follow_up(state):
        try:
            result=store.follow_up(state["payment"])
        except Exception:
            result={"check":"MERCHANT_PRIOR_7D_ACTIVITY","status":"UNAVAILABLE","conflict_resolved":False}
        progress("follow_up")
        return {"follow_up":result}
    def decision(state):
        result=assess(state["risk"],state["behavior"],state["intelligence"],state["quality"],state["follow_up"])
        result.update({k:state[k] for k in ["payment","plan","risk","behavior","intelligence","quality","follow_up"]})
        result.update(explainer.explain_assessment(result))
        result["analysis_stage"]="SPARKOV_FIVE_AGENT_V2"
        progress("decision")
        return {"result":result}
    graph=StateGraph(State)
    for name,node in [("plan",plan),("risk",risk),("behavior",behavior),("intelligence",intelligence),("follow_up",follow_up),("decision",decision)]:
        graph.add_node(name,node)
    graph.add_edge(START,"plan")
    graph.add_edge("plan","risk")
    graph.add_edge("plan","behavior")
    graph.add_edge(["risk","behavior"],"intelligence")
    graph.add_conditional_edges("intelligence",conflict,{"follow_up":"follow_up","decision":"decision"})
    graph.add_edge("follow_up","decision")
    graph.add_edge("decision",END)
    return graph.compile().invoke({"payment":payment,"history":history},{"recursion_limit":12})["result"]
