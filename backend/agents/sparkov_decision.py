"""Evidence-dependent, auditable action policy. Overall index is not a fraud probability."""


def assess(risk,behavior,intelligence,quality,follow_up=None):
    reasons=[]
    model_high=risk["model_flag"]
    findings=behavior["findings"]
    customer_link=intelligence.get("customer_link",False)
    merchant_link=intelligence.get("merchant_link",False)
    serious=sum(f["code"] in {"UNUSUAL_AMOUNT","HIGH_FREQUENCY","UNUSUAL_LOCATION","UNUSUAL_TIME"} for f in findings)
    if model_high:
        reasons.append("Model score exceeds its validation-selected review threshold.")
    reasons.extend(f["detail"] for f in findings)
    if customer_link:
        reasons.append("This customer is linked to a prior known simulated fraud case within 30 days.")
    if merchant_link:
        reasons.append("Merchant appears in a prior known simulated fraud case; this alone does not establish wrongdoing.")
    if quality["limitations"]:
        reasons.extend(quality["limitations"])
    if quality["confidence"]=="LOW" or intelligence.get("status")=="UNAVAILABLE":
        action,level="ESCALATE","UNCERTAIN"
    elif risk["risk_score"]>=max(.8,risk["threshold"]) or (model_high and (serious or customer_link)) or (customer_link and serious):
        action,level="ESCALATE","HIGH"
    elif model_high or findings or customer_link or intelligence.get("status")=="UNAVAILABLE":
        action,level="FLAG","MEDIUM"
    else:
        action,level="CLEAR","LOW"
    conflict=bool(follow_up)
    if conflict:
        reasons.append("A follow-up checked prior merchant activity; conflicting evidence remains and requires human review.")
        if action=="CLEAR":
            action,level="FLAG","MEDIUM"
    index=min(100,round(risk["risk_score"]*60 + min(20,serious*10)+min(8,len(findings)*2)+(12 if customer_link else 0)+(3 if merchant_link else 0)))
    return {"risk_level":level,"recommendation":action,"assessment_index":index,
            "assessment_index_type":"Heuristic evidence index, not a calibrated probability",
            "evidence_confidence":"LOW" if intelligence.get("status")=="UNAVAILABLE" else quality["confidence"],"confidence_basis":quality["limitations"] or ["Sufficient recent history and supported simulation context."],
            "reasons":reasons or ["Model is below threshold and available behavior/intelligence checks did not establish a review trigger."],
            "policy_version":"sparkov-evidence-v2.1","conflict_remaining":conflict}
