"""Stateless HTTP inference; user datasets and audit history stay in IndexedDB."""
from dataclasses import asdict
from functools import lru_cache
from io import BytesIO
import gzip
import json
import logging
from pathlib import Path
import tempfile
from threading import Lock
from zipfile import BadZipFile, ZipFile

import numpy as np
import pandas as pd
from flask import Flask, g, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException

from .analytics import evaluation, summary
from . import cloud_storage
from . import auth
from .config import ROOT
from .inference import load_models
from .service import export_filename, export_frame, read_file
from .validation import FEATURES, Thresholds, ValidationError, prepare_input

MODEL_LOCK = Lock()
MAX_ROWS = 30000


@lru_cache(maxsize=1)
def model_registry():
    with MODEL_LOCK:
        models, errors = load_models(ROOT / "models/best_model_v1.pkl")
        if errors:
            logging.warning("Optional models failed to load: %s", errors)
        return models


def records_json(frame):
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def payload():
    if request.headers.get("Content-Encoding") == "gzip":
        with gzip.GzipFile(fileobj=BytesIO(request.get_data())) as stream:
            raw = stream.read(64 * 1024 * 1024 + 1)
        if len(raw) > 64 * 1024 * 1024:
            raise ValidationError("Dữ liệu giải nén vượt quá 64 MB.")
        data = json.loads(raw)
    else:
        data = request.get_json()
    if not isinstance(data, dict):
        raise ValidationError("Nội dung yêu cầu phải là một đối tượng JSON.")
    return data


def input_frame(data, limit=MAX_ROWS):
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > limit:
        raise ValidationError(f"Cần từ 1 đến {limit:,} hồ sơ.")
    if not all(isinstance(row, dict) for row in rows):
        raise ValidationError("Mỗi hồ sơ phải là một đối tượng.")
    return prepare_input(pd.DataFrame(rows))


def selected_model(data):
    name = data.get("model", "Random Forest")
    if name not in model_registry():
        raise ValidationError("Mô hình không tồn tại hoặc chưa tải được.")
    return model_registry()[name]


def thresholds(data, model):
    config = data.get("thresholds", {})
    if not isinstance(config, dict):
        raise ValidationError("Cấu hình ngưỡng không hợp lệ.")
    return Thresholds(
        decision=float(config.get("decision", model.threshold)),
        low=float(config.get("low", 0.2)), high=float(config.get("high", 0.5)),
        basis=config.get("basis", "raw"),
    )


def predict(data, limit=500):
    frame = input_frame(data, limit)
    model = selected_model(data)
    config = thresholds(data, model)
    result = pd.concat([frame, model.predict(frame, config)], axis=1)
    for key, value in {
        "model_name": model.name, "model_version": model.version, "model_sha256": model.digest,
        "decision_threshold": config.decision, "decision_basis": config.basis,
        "risk_low_threshold": config.low, "risk_high_threshold": config.high,
    }.items():
        result[key] = value
    return result, model, config


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(MAX_CONTENT_LENGTH=4 * 1024 * 1024)
    auth.install(app)
    if test_config:
        app.config.update(test_config)

    @app.after_request
    def response_headers(response):
        if (response.mimetype == "application/json" and "gzip" in request.headers.get("Accept-Encoding", "")
                and len(response.get_data()) > 1024):
            response.set_data(gzip.compress(response.get_data()))
            response.headers["Content-Encoding"] = "gzip"
            response.vary.add("Accept-Encoding")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(Exception)
    def handle_error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error="Tệp hoặc yêu cầu quá lớn." if exc.code == 413 else exc.description), exc.code
        if isinstance(exc, (ValueError, TypeError, KeyError, OSError, BadZipFile)):
            return jsonify(error=str(exc) if not isinstance(exc, OSError) else "Không thể đọc tệp dữ liệu."), 400
        app.logger.exception("Request failed")
        return jsonify(error="Không thể xử lý yêu cầu. Vui lòng thử lại."), 500

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", storage="mongodb" if cloud_storage.enabled() else "browser",
                       version=(ROOT / "VERSION").read_text().strip())

    @app.route("/api/workspace", methods=["GET", "PUT"])
    def workspace():
        user = getattr(g, "user", None)
        if user:
            from hashlib import sha256
            from werkzeug.exceptions import Forbidden
            account_id = request.args.get("account_id", user["_id"])
            if account_id != user["_id"] and user["role"] != "admin":
                raise Forbidden("Bạn chỉ được truy cập dữ liệu của chính tài khoản mình.")
            owner = sha256(f"account:{account_id}".encode()).hexdigest()
        else:
            owner = cloud_storage.workspace_id(request.headers.get("Authorization", ""))
        try:
            if request.method == "GET":
                return jsonify(cloud_storage.read_snapshot(owner))
            data = payload()
            incoming = data.get("state")
            if user:
                if (not isinstance(incoming, dict) or not isinstance(incoming.get("datasets"), list)
                        or not isinstance(incoming.get("runs"), list)):
                    raise ValidationError("Cấu trúc kho dữ liệu không hợp lệ.")
                for item in incoming["datasets"]:
                    if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                            or not isinstance(item.get("versions"), list) or not item["versions"]
                            or any(not isinstance(v, dict) or not isinstance(v.get("id"), str)
                                   or not isinstance(v.get("rows"), list) for v in item["versions"])):
                        raise ValidationError("Cấu trúc phiên bản dữ liệu không hợp lệ.")
                if any(not isinstance(r, dict) or not isinstance(r.get("id"), str) for r in incoming["runs"]):
                    raise ValidationError("Cấu trúc lịch sử không hợp lệ.")
                previous = cloud_storage.read_snapshot(owner)["state"]
                if previous and isinstance(incoming, dict):
                    old_runs = {r["id"]: r for r in previous.get("runs", [])}
                    new_runs = {r["id"]: r for r in incoming.get("runs", [])}
                    if any(new_runs.get(key) != row for key, row in old_runs.items()):
                        raise ValidationError("Không được xóa hoặc sửa kết quả lịch sử đã lưu.")
                    old_versions = {v["id"]: v for d in previous.get("datasets", []) for v in d["versions"]}
                    for d in incoming.get("datasets", []):
                        for v in d.get("versions", []):
                            if v.get("id") in old_versions and v != old_versions[v["id"]]:
                                raise ValidationError("Dữ liệu đã lưu cần được chỉnh sửa bằng phiên bản mới.")
            result = cloud_storage.write_snapshot(owner, incoming, data.get("revision"))
            if user:
                cloud_storage.database().workspaces.update_one({"_id": owner}, {"$set": {
                    "account_id": account_id, "dataset_count": len(incoming["datasets"]),
                    "version_count": sum(len(d["versions"]) for d in incoming["datasets"]),
                    "run_count": len(incoming["runs"]), "updated_at": auth.now(),
                }})
                auth.audit("data_version_save", account_id, detail=f"datasets={len(incoming['datasets'])}, runs={len(incoming['runs'])}")
            return jsonify(result)
        except (HTTPException, ValidationError):
            raise
        except Exception:
            app.logger.exception("MongoDB workspace unavailable")
            return jsonify(error="Không kết nối được MongoDB Atlas. Dữ liệu cục bộ vẫn được giữ."), 503

    @app.get("/api/models")
    def models():
        default_model = "Random Forest"
        if getattr(g, "user", None):
            setting = cloud_storage.database().system_settings.find_one({"_id": "active_model"})
            if setting:
                default_model = setting["name"]
        return jsonify(default_model=default_model, models=[{
            "name": m.name, "version": m.version, "digest": m.digest, "threshold": m.threshold,
            "cv_auc": m.metadata.get("cv_auc"), "test_auc": m.metadata.get("test_auc"),
        } for m in model_registry().values()], features=FEATURES)

    @app.get("/api/sample")
    def sample():
        return jsonify(rows=records_json(read_file(ROOT / "examples/sample_customers.csv")))

    @app.post("/api/import")
    def import_file():
        upload = request.files.get("file")
        if upload is None:
            raise ValidationError("Chọn tệp CSV, XLSX hoặc JSON.")
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in (".csv", ".xlsx", ".json"):
            raise ValidationError("Chỉ hỗ trợ CSV, XLSX hoặc JSON.")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ("input" + suffix)
            upload.save(path)
            if suffix == ".xlsx":
                with ZipFile(path) as archive:
                    if sum(entry.file_size for entry in archive.infolist()) > 64 * 1024 * 1024:
                        raise ValidationError("Nội dung Excel giải nén vượt quá 64 MB.")
            frame = read_file(path)
        if len(frame) > MAX_ROWS:
            raise ValidationError("Mỗi tệp tối đa 30.000 hồ sơ.")
        return jsonify(rows=records_json(frame), columns=list(frame.columns),
                       normalization=frame.attrs.get("normalization", {}))

    @app.post("/api/predict")
    def inference():
        result, model, config = predict(payload())
        if getattr(g, "user", None):
            auth.audit("prediction", model.name, detail=f"rows={len(result)}")
        return jsonify(rows=records_json(result), summary=summary(result),
                       evaluation=evaluation(result), model=model.name, thresholds=asdict(config))

    @app.post("/api/export")
    def export():
        data = payload()
        model = selected_model(data)
        config = thresholds(data, model)
        incoming = data.get("rows", [])
        frame = input_frame(data)
        # Recompute on the server instead of trusting client-supplied probabilities or metrics.
        if any(row.get("model_sha256", model.digest) != model.digest for row in incoming):
            raise ValidationError("Kết quả không thuộc model đang chọn. Hãy dự báo lại.")
        for column in ("run_id", "prediction_time_utc", "dataset_version_id"):
            if any(column in row for row in incoming):
                frame[column] = [row.get(column) for row in incoming]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / export_filename(model.name)
            export_frame(frame, path, model=model, thresholds=config)
            content = path.read_bytes()
        if len(content) > 4 * 1024 * 1024:
            raise ValidationError("File vượt giới hạn tải của Vercel. Hãy lọc thành nhóm nhỏ hơn để xuất.")
        return send_file(BytesIO(content), download_name=export_filename(model.name), as_attachment=True,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.post("/api/explain")
    def explain():
        data = payload()
        frame = input_frame(data, 1)
        model = selected_model(data)
        from .features import add_features
        values = add_features(frame[FEATURES].rename(columns={"PAY_0": "PAY_1"}))[model.features]
        preprocessing = model.pipeline[:-1]
        transformed = preprocessing.transform(values) if len(preprocessing.steps) else values.to_numpy()
        if hasattr(transformed, "toarray"):
            transformed = transformed.toarray()
        estimator = model.pipeline.steps[-1][1]
        names = list(preprocessing.get_feature_names_out()) if len(preprocessing.steps) else model.features
        if hasattr(estimator, "coef_"):
            contributions = np.asarray(transformed)[0] * estimator.coef_[0]
            scale = "Log-odds: hệ số × giá trị chuẩn hóa"
        elif hasattr(estimator, "get_booster"):
            import xgboost
            contributions = estimator.get_booster().predict(
                xgboost.DMatrix(np.asarray(transformed)), pred_contribs=True, validate_features=False
            )[0][:-1]
            scale = "Tree SHAP · log-odds thô"
        else:
            contributions = np.zeros(len(names))
            for tree in estimator.estimators_:
                node = 0
                while tree.tree_.feature[node] >= 0:
                    feature = tree.tree_.feature[node]
                    child = (tree.tree_.children_left[node] if transformed[0, feature] <= tree.tree_.threshold[node]
                             else tree.tree_.children_right[node])
                    parent_values = tree.tree_.value[node][0]
                    child_values = tree.tree_.value[child][0]
                    contributions[feature] += (child_values[1] / child_values.sum()
                                               - parent_values[1] / parent_values.sum())
                    node = child
            contributions /= len(estimator.estimators_)
            scale = "Đóng góp theo đường đi cây · điểm thô (không phải SHAP)"
        result = pd.DataFrame({"feature": names, "contribution": contributions})
        result = result.iloc[np.argsort(-np.abs(contributions))].head(12)
        return jsonify(rows=records_json(result), scale=scale)

    return app
