from io import BytesIO
import json
from urllib.error import HTTPError

import pandas as pd
import pytest

from creditrisk.insights import generate_insights


def test_groq_receives_only_server_evidence_without_identity(monkeypatch, frame):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    frame["ID"] = "private-customer"
    explanation = pd.DataFrame([{"feature": "PAY_1", "contribution": .1}, {"feature": "SEX", "contribution": .2}])
    captured = {}
    def request(req, timeout):
        assert req.get_header("User-agent") == "CreditRiskAI/0.4"
        captured.update(json.loads(req.data))
        return BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps({
            "insights": [{"text": "Trả nợ gần nhất làm tăng điểm.", "features": ["PAY_1"]}],
            "checks": ["repayment"],
        })}}]}).encode())
    monkeypatch.setattr("creditrisk.insights.urlopen", request)
    result = generate_insights(frame, explanation, {"probability": .25}, "RF", False)
    sent = json.loads(captured["messages"][1]["content"])
    assert "private-customer" not in json.dumps(sent)
    assert "SEX" not in json.dumps(sent)
    assert sent["evidence"][0]["value"] == -1
    assert result["status"] == "ok"
    assert result["checks"][0]["code"] == "repayment"


def test_missing_key_does_not_call_provider(monkeypatch, frame):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert generate_insights(frame, pd.DataFrame(), {}, "RF", False)["status"] == "unavailable"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 503])
def test_http_diagnostics_distinguish_causes_without_leaking_body(monkeypatch, frame, status, caplog):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    def request(req, timeout):
        raise HTTPError(req.full_url, status, "private detail", {}, BytesIO(b'{"error":{"code":"model_not_found","message":"test-secret"}}'))
    monkeypatch.setattr("creditrisk.insights.urlopen", request)
    explanation = pd.DataFrame([{"feature": "PAY_1", "contribution": .1}])
    result = generate_insights(frame, explanation, {}, "RF", False)
    assert result["code"] == f"groq_http_{status}"
    assert str(status) in result["message"]
    assert "test-secret" not in str(result) + caplog.text
    assert "private detail" not in str(result) + caplog.text


@pytest.mark.parametrize("failure", ["quota", "unknown_feature", "unknown_action"])
def test_provider_failures_and_invalid_evidence_are_not_displayed(monkeypatch, frame, failure):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    def request(req, timeout):
        if failure == "quota":
            raise HTTPError(req.full_url, 429, "private provider detail", {}, None)
        output = {"insights": [{"text": "Nhận xét", "features": ["AGE" if failure == "unknown_feature" else "PAY_1"]}],
                  "checks": ["approve" if failure == "unknown_action" else "repayment"]}
        return BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps(output)}}]}).encode())
    monkeypatch.setattr("creditrisk.insights.urlopen", request)
    explanation = pd.DataFrame([{"feature": "PAY_1", "contribution": .1}])
    result = generate_insights(frame, explanation, {}, "RF", False)
    assert result["status"] == "unavailable"
    assert "private provider detail" not in str(result)
