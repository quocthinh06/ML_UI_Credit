from io import BytesIO
import gzip
import json

import pandas as pd
import pytest
from openpyxl import load_workbook

from creditrisk.web import create_app
from creditrisk.config import ROOT


@pytest.fixture
def client(monkeypatch, model):
    model.metadata = {"cv_auc": 0.8, "test_auc": 0.75}
    monkeypatch.setattr("creditrisk.web.model_registry", lambda: {model.name: model})
    return create_app({"TESTING": True}).test_client()


def test_web_entrypoint_and_assets(client):
    response = client.get("/")
    assert response.status_code == 200
    for page in ["overview", "datasets", "predict", "models"]:
        assert f'id="page-{page}"'.encode() in response.data
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert client.get("/api/health").json["storage"] == "browser"


def test_prediction_reports_only_allowed_filled_fields(client, frame):
    rows = frame.drop(columns=["AGE", "PAY_AMT6"]).to_dict("records")
    response = client.post("/api/predict", json={"rows": rows})
    assert response.status_code == 200
    assert response.json["rows"][0]["AGE"] == 34
    assert response.json["imputation"]["filled_cells"] == 2
    assert set(response.json["ket_qua"]["truong_da_dien"]) == {"AGE", "PAY_AMT6"}
    rows[0]["PAY_0"] = None
    assert client.post("/api/predict", json={"rows": rows}).status_code == 400


def test_insights_recompute_scores_and_report_imputation(client, frame, model, monkeypatch):
    monkeypatch.setattr(model, "explain", lambda values: pd.DataFrame([{"feature": "PAY_1", "contribution": .1}]), raising=False)
    seen = {}
    def commentary(values, explanation, prediction, name, has_imputed):
        seen.update(prediction=prediction, imputed=has_imputed)
        return {"status": "unavailable", "message": "test only"}
    monkeypatch.setattr("creditrisk.insights.generate_insights", commentary)
    rows = frame.drop(columns="AGE").to_dict("records")
    rows[0].update(probability=.99, raw_score=.99)
    response = client.post("/api/insights", json={"rows": rows})
    assert response.status_code == 200
    assert seen["prediction"]["probability"] == .25
    assert seen["imputed"] is True
    assert client.post("/api/insights", json={"rows": rows * 2}).status_code == 400


def test_import_fills_supplementary_columns_and_preserves_labels(client, frame):
    frame = frame.drop(columns=["AGE", "EDUCATION"])
    frame["default.payment.next.month"] = None
    response = client.post("/api/import", data={"file": (BytesIO(frame.to_csv(index=False).encode()), "missing.csv")})
    assert response.status_code == 200
    assert response.json["rows"][0]["EDUCATION"] == 2
    assert response.json["rows"][0]["default.payment.next.month"] is None
    assert response.json["imputation"]["filled_rows"] == 1


def test_web_models(client, model):
    data = client.get("/api/models").json
    assert data["models"][0]["name"] == model.name
    assert len(data["features"]) == 23


def test_login_configuration_is_explicit_without_database(client):
    response = client.get("/api/auth/session")
    assert response.json["user"] is None and not response.json["configured"]
    assert client.get("/login").status_code == 200
    assert client.post("/api/auth/login", json={"username": "not_configured", "password": "not-a-real-password"}).status_code == 503
    assert client.post("/api/auth/logout", json={}).status_code == 200


@pytest.mark.parametrize(("error", "expected"), [
    ("auth", "từ chối xác thực"), ("permissions", "readWrite"),
    ("timeout", "Network Access"), ("configuration", "connection string"),
])
def test_mongodb_failures_return_actionable_errors_without_secrets(client, monkeypatch, error, expected):
    from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

    secret = "do-not-return-this-test-secret"
    errors = {"auth": OperationFailure(secret, code=8000),
              "permissions": OperationFailure(secret, code=13),
              "timeout": ServerSelectionTimeoutError(secret), "configuration": ConfigurationError(secret)}
    def fail():
        raise errors[error]
    monkeypatch.setattr("creditrisk.auth.bootstrap", fail)
    response = client.post("/api/auth/login", json={"username": "test-user", "password": "invalid"})
    assert response.status_code == 503
    assert expected in response.json["error"]
    assert secret not in response.get_data(as_text=True)


def test_web_prediction_uses_real_input_contract(client, frame, model):
    response = client.post("/api/predict", json={"rows": frame.to_dict("records"), "model": model.name})
    assert response.status_code == 200
    assert response.json["rows"][0]["probability"] == 0.25
    assert response.json["rows"][0]["model_sha256"] == model.digest
    assert response.json["thresholds"]["basis"] == "raw"


@pytest.mark.parametrize("body", [None, [], {}, {"rows": []}, {"rows": [{"AGE": 1}]},
                                     {"rows": ["not an object"]}])
def test_web_rejects_invalid_inputs(client, body):
    response = client.post("/api/predict", data=json.dumps(body), content_type="application/json")
    assert 400 <= response.status_code < 500


def test_web_batch_limit_and_unknown_model(client, frame):
    rows = frame.to_dict("records")
    assert client.post("/api/predict", json={"rows": rows * 501}).status_code == 400
    assert client.post("/api/predict", json={"rows": rows, "model": "missing"}).status_code == 400


def test_web_import_keeps_ids_and_labels(client, frame):
    frame["ID"] = "00042"
    frame["default.payment.next.month"] = 1
    response = client.post("/api/import", data={"file": (BytesIO(frame.to_csv(index=False).encode()), "data.csv")})
    assert response.status_code == 200
    assert response.json["rows"][0]["ID"] == "00042"
    assert response.json["rows"][0]["default.payment.next.month"] == 1
    assert client.post("/api/import", data={"file": (BytesIO(b"bad"), "model.pkl")}).status_code == 400


def test_web_export_recomputes_untrusted_scores(client, frame, model):
    rows = frame.to_dict("records")
    rows[0].update(probability=0.99, model_sha256=model.digest, run_id="run-1")
    body = gzip.compress(json.dumps({"rows": rows, "model": model.name}).encode())
    response = client.post("/api/export", data=body, content_type="application/json",
                           headers={"Content-Encoding": "gzip"})
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    assert book.sheetnames == ["Du lieu", "Insight", "Dashboard", "So lieu bieu do"]
    output = pd.read_excel(BytesIO(response.data))
    assert output.probability.iloc[0] == 0.25
    assert output.run_id.iloc[0] == "run-1"
    assert "attachment" in response.headers["Content-Disposition"]


def test_web_export_rejects_other_model(client, frame, model):
    rows = frame.to_dict("records")
    rows[0]["model_sha256"] = "other-model"
    response = client.post("/api/export", json={"rows": rows, "model": model.name})
    assert response.status_code == 400


def test_web_json_compression(client):
    response = client.get("/api/sample", headers={"Accept-Encoding": "gzip"})
    assert response.headers["Content-Encoding"] == "gzip"
    assert len(json.loads(gzip.decompress(response.data))["rows"]) == 3


def test_web_cloud_workspace_requires_private_key(client, monkeypatch):
    monkeypatch.delenv("MONGODB_URI", raising=False)
    assert client.get("/api/workspace").status_code == 401
    assert client.get("/api/workspace", headers={"Authorization": "Bearer short"}).status_code == 401
    assert client.get("/api/workspace", headers={"Authorization": "Bearer " + "a" * 64}).status_code == 503


def test_web_cloud_workspace_is_scoped_to_hashed_key(client, monkeypatch):
    from hashlib import sha256

    seen = []
    def write(owner, state, revision):
        seen.append((owner, state, revision))
        return {"revision": revision + 1}
    monkeypatch.setattr("creditrisk.cloud_storage.write_snapshot", write)
    response = client.put("/api/workspace", headers={"Authorization": "Bearer " + "b" * 64},
                          json={"state": {"datasets": [], "runs": []}, "revision": 0})
    assert response.status_code == 200 and response.json["revision"] == 1
    assert seen[0][0] == sha256(("b" * 64).encode()).hexdigest()


@pytest.mark.skipif(not (ROOT / "models/model_xgb_v1.pkl").exists(), reason="Download trusted model handoffs")
def test_web_real_models_predict_and_explain():
    from creditrisk.service import read_file

    client = create_app({"TESTING": True}).test_client()
    rows = read_file(ROOT / "examples/sample_customers.csv").to_dict("records")
    names = [m["name"] for m in client.get("/api/models").json["models"]]
    assert set(names) == {"Random Forest", "Logistic Regression", "XGBoost"}
    probabilities = []
    for name in names:
        result = client.post("/api/predict", json={"rows": rows, "model": name})
        assert result.status_code == 200
        probabilities.append(result.json["rows"][0]["probability"])
        explanation = client.post("/api/explain", json={"rows": rows[:1], "model": name})
        assert explanation.status_code == 200
        assert len(explanation.json["rows"]) == 12
        assert "SHAP" in explanation.json["scale"]
    assert len(set(probabilities)) == 3


def test_frontend_pages_are_plain_html(client):
    from pathlib import Path
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    for name in ("index.html", "login.html", "change-password.html", "admin.html"):
        source = (frontend / name).read_text(encoding="utf-8")
        assert "{{" not in source and "{%" not in source
        assert 'lang="vi"' in source
        from html.parser import HTMLParser
        from urllib.parse import urlsplit
        class Assets(HTMLParser):
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                asset = values.get('src') if tag == 'script' else values.get('href') if tag == 'link' else None
                if asset:
                    assert (frontend / urlsplit(asset).path).is_file(), asset
        Assets().feed(source)
    assert client.get("/").data == (frontend / "index.html").read_bytes()
    assert client.get("/login").data == (frontend / "login.html").read_bytes()
    for name in ("app.css", "auth.css", "app.js", "login.js", "admin.js"):
        assert client.get("/static/" + name).status_code == 200
