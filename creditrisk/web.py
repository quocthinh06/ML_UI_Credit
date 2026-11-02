"""Stateless HTTP inference; user datasets and audit history stay in IndexedDB."""
from dataclasses import asdict
from functools import lru_cache
from io import BytesIO
import gzip
import json
import logging
import os
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
        path = ROOT / "models/best_model.pkl"
        if not path.is_file():
            path = ROOT / "models/best_model_v1.pkl"
        models, errors = load_models(path)
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


def default_model():
    if getattr(g, "user", None):
        setting = cloud_storage.database().system_settings.find_one({"_id": "active_model"})
        if setting and setting["name"] in model_registry():
            return setting["name"]
    return next(iter(model_registry()))


def selected_model(data):
    name = data.get("model") if "model" in data else default_model()
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
    if not os.environ.get("VERCEL"):
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
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
        from .mongo_diagnostics import connection_error

        diagnostic = connection_error(exc)
        if diagnostic:
            code, message = diagnostic
            app.logger.error("MongoDB failure: %s", code)
            return jsonify(error=message, code=code), 503
        if isinstance(exc, HTTPException):
            body = {"error": "Tệp hoặc yêu cầu quá lớn." if exc.code == 413 else exc.description}
            if getattr(exc, "reason", None):
                body["code"] = exc.reason
            return jsonify(body), exc.code
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

    def workspace_identity():
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
        return owner, user, account_id if user else None

    def save_workspace(owner, user, account_id, data):
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

    @app.route("/api/workspace", methods=["GET", "PUT"])
    def workspace():
        owner, user, account_id = workspace_identity()
        if request.method == "GET":
            return jsonify(cloud_storage.read_snapshot(owner))
        return save_workspace(owner, user, account_id, payload())

    @app.post("/api/workspace/uploads")
    def begin_workspace_upload():
        from datetime import timedelta
        from uuid import uuid4
        from werkzeug.exceptions import BadRequest, Conflict
        owner, _, _ = workspace_identity()
        data = payload()
        size, count, revision = data.get("size"), data.get("parts"), data.get("revision")
        if (type(size) is not int or not 1 <= size <= 128 * 1024 * 1024
                or type(count) is not int or count != (size + 1024 * 1024 - 1) // (1024 * 1024)
                or type(revision) is not int or revision < 0 or data.get("encoding") not in ("json", "gzip")):
            raise BadRequest("Thông tin đồng bộ chia nhỏ không hợp lệ; kho tối đa 128 MB.")
        db = cloud_storage.database()
        current = db.workspaces.find_one({"_id": owner}, {"revision": 1})
        if (current or {}).get("revision", 0) != revision:
            raise Conflict("Kho đã thay đổi. Hãy thử đồng bộ lại để kiểm tra phiên bản.")
        for collection in (db.workspace_uploads, db.workspace_upload_chunks):
            collection.create_index("expires_at", expireAfterSeconds=0)
        upload_id = uuid4().hex
        db.workspace_uploads.insert_one({"_id": upload_id, "owner": owner, "size": size, "parts": count,
            "revision": revision, "encoding": data["encoding"], "expires_at": auth.now() + timedelta(minutes=30)})
        return jsonify(upload_id=upload_id), 201

    def pending_upload(upload_id, owner):
        from werkzeug.exceptions import NotFound
        doc = cloud_storage.database().workspace_uploads.find_one({"_id": upload_id, "owner": owner,
            "expires_at": {"$gt": auth.now()}})
        if not doc:
            raise NotFound("Lần đồng bộ không tồn tại hoặc đã hết hạn. Hãy thử lại.")
        return doc

    @app.put("/api/workspace/uploads/<upload_id>/<int:part>")
    def workspace_upload_part(upload_id, part):
        from werkzeug.exceptions import BadRequest
        owner, _, _ = workspace_identity()
        doc = pending_upload(upload_id, owner)
        content = request.get_data()
        expected = min(1024 * 1024, doc["size"] - part * 1024 * 1024)
        if not 0 <= part < doc["parts"] or len(content) != expected:
            raise BadRequest("Phần dữ liệu đồng bộ không hợp lệ.")
        cloud_storage.database().workspace_upload_chunks.replace_one({"_id": f"{upload_id}:{part}"},
            {"_id": f"{upload_id}:{part}", "upload_id": upload_id, "part": part, "content": content,
             "expires_at": doc["expires_at"]}, upsert=True)
        return jsonify(ok=True)

    @app.post("/api/workspace/uploads/<upload_id>/commit")
    def commit_workspace_upload(upload_id):
        from werkzeug.exceptions import BadRequest, RequestEntityTooLarge
        owner, user, account_id = workspace_identity()
        doc = pending_upload(upload_id, owner)
        db = cloud_storage.database()
        chunks = list(db.workspace_upload_chunks.find({"upload_id": upload_id}).sort("part", 1))
        if [item["part"] for item in chunks] != list(range(doc["parts"])):
            raise BadRequest("Chưa nhận đủ dữ liệu; kho hiện tại chưa bị thay đổi.")
        content = b"".join(item["content"] for item in chunks)
        if len(content) != doc["size"]:
            raise BadRequest("Kích thước dữ liệu đồng bộ không khớp.")
        if doc["encoding"] == "gzip":
            with gzip.GzipFile(fileobj=BytesIO(content)) as stream:
                content = stream.read(128 * 1024 * 1024 + 1)
        if len(content) > 128 * 1024 * 1024:
            raise RequestEntityTooLarge("Kho vượt giới hạn 128 MB; bản cục bộ vẫn được giữ.")
        data = json.loads(content)
        if not isinstance(data, dict) or data.get("revision") != doc["revision"]:
            raise BadRequest("Phiên bản đồng bộ không khớp.")
        # Only a complete, authenticated and validated snapshot becomes visible.
        result = save_workspace(owner, user, account_id, data)
        db.workspace_upload_chunks.delete_many({"upload_id": upload_id})
        db.workspace_uploads.delete_one({"_id": upload_id, "owner": owner})
        return result

    @app.get("/api/models")
    def models():
        return jsonify(default_model=default_model(), models=[{
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
