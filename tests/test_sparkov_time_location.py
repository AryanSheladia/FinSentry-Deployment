from datetime import datetime,timedelta,timezone
import json

import httpx

from backend.agents.sparkov_behavior import analyze
from backend.agents.sparkov_decision import assess
from backend.agents.sparkov_explanation import SparkovExplainer


def setup():
    now=datetime(2020,7,15,3,15,tzinfo=timezone.utc)
    payment=dict(customer_id="C",timestamp=int(now.timestamp()),amount=40,merchant="M",category="food",
                 home_lat=35,home_lon=-88,merchant_lat=35,merchant_lon=-88,device_id="D")
    history=[dict(payment,timestamp=int((now-timedelta(days=i)).replace(hour=13).timestamp()),transaction_id=str(i)) for i in range(1,71)]
    return payment,history


def test_normal_amount_can_flag_both_time_and_location():
    payment,history=setup()
    result=analyze(dict(payment,merchant_lat=51.5074,merchant_lon=-.1278),history)
    assert {f["code"] for f in result["findings"]}=={"UNUSUAL_TIME","UNUSUAL_LOCATION"}
    assert result["time_profile"]["nearby_hour_count"]==0
    assert result["time_profile"]["prior_90d_count"]==70
    assert result["baseline_mean_30d"]==40
    decision=assess(dict(risk_score=.01,threshold=.3,model_flag=False),result,
        dict(status="NO_MATCH",cases=[],customer_link=False,merchant_link=False),dict(confidence="HIGH",limitations=[]))
    assert decision["recommendation"]=="FLAG"


def test_controls_isolate_time_and_location():
    payment,history=setup()
    noon=dict(payment,timestamp=payment["timestamp"]+10*3600)
    assert analyze(noon,history)["findings"]==[]
    assert {f["code"] for f in analyze(payment,history)["findings"]}=={"UNUSUAL_TIME"}
    assert {f["code"] for f in analyze(dict(noon,merchant_lat=51.5,merchant_lon=0),history)["findings"]}=={"UNUSUAL_LOCATION"}


def test_time_profile_excludes_future_same_time_other_customer_and_old_rows():
    payment,history=setup()
    extras=[dict(payment,timestamp=payment["timestamp"]+i) for i in range(100)]
    extras += [dict(history[0],customer_id="OTHER") for _ in range(100)]
    extras += [dict(history[0],timestamp=payment["timestamp"]-91*86400) for _ in range(100)]
    result=analyze(payment,history+extras)
    assert result["time_profile"]["prior_90d_count"]==70
    assert "UNUSUAL_TIME" in {f["code"] for f in result["findings"]}
    assert "UNUSUAL_TIME" not in {f["code"] for f in analyze(payment,history[:59])["findings"]}


def test_hour_window_wraps_at_midnight():
    payment,history=setup()
    zero=datetime.fromtimestamp(payment["timestamp"],timezone.utc).replace(hour=0)
    history=[dict(row,timestamp=int(datetime.fromtimestamp(row["timestamp"],timezone.utc).replace(hour=23).timestamp())) for row in history]
    result=analyze(dict(payment,timestamp=int(zero.timestamp())),history)
    assert result["time_profile"]["nearby_hour_share"]==1
    assert "UNUSUAL_TIME" not in {f["code"] for f in result["findings"]}


def test_correct_numbers_with_contradictory_model_narrative_are_rejected():
    result=dict(recommendation="FLAG",risk_level="MEDIUM",evidence_confidence="HIGH",reasons=["Unusual merchant location."],
                risk=dict(risk_score=.01,threshold=.327,model_flag=False),behavior={},quality={},follow_up=None,intelligence={"cases":[]})
    def handler(request):
        draft=dict(model_score=.01,model_flag=False,risk_level="MEDIUM",evidence_confidence="HIGH",recommendation="FLAG",cited_case_ids=[],
                   summary="The model flagged this transaction as high risk due to its location.")
        return httpx.Response(200,json={"choices":[{"message":{"content":json.dumps(draft)}}]})
    output=SparkovExplainer(api_key="TEST",transport=httpx.MockTransport(handler)).explain_assessment(result)
    assert output["explanation_mode"]=="template"
    assert output["explanation_fallback_reason"]=="INVALID_OUTPUT"
    assert "below the review threshold" in output["explanation"]
