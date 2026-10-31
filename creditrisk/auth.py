"""MongoDB-backed accounts, revocable sessions and server-enforced roles."""
from datetime import datetime, timedelta, timezone
from functools import wraps
from hashlib import sha256
import os
import re
import secrets

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, session
from werkzeug.exceptions import BadRequest, Forbidden, ServiceUnavailable, Unauthorized
from werkzeug.security import check_password_hash, generate_password_hash

from .cloud_storage import database, enabled

bp = Blueprint("auth", __name__)


def now():
    return datetime.now(timezone.utc)


def enforced():
    return os.environ.get("AUTH_ENABLED", "0") == "1"


def configured():
    return enabled() and len(current_app.secret_key or "") >= 32


def require_storage():
    if not configured():
        raise ServiceUnavailable("Cần cấu hình MongoDB Atlas và SESSION_SECRET trước khi bật đăng nhập.")
    return database()


def username(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_.@+\-]{3,100}", value.strip()):
        raise BadRequest("Tên đăng nhập cần 3–100 ký tự: chữ, số, dấu chấm, @, _, + hoặc -.")
    return value.strip().lower()


def json_data():
    data = request.get_json()
    if not isinstance(data, dict):
        raise BadRequest("Nội dung yêu cầu phải là đối tượng JSON.")
    return data


def password(value):
    if not isinstance(value, str) or not 10 <= len(value) <= 128:
        raise BadRequest("Mật khẩu cần từ 10 đến 128 ký tự.")
    return value


def public_user(user):
    return {"id": user["_id"], "name": user["name"], "username": user["_id"],
            "role": user["role"], "active": user["active"],
            "must_change_password": user.get("must_change_password", False),
            "created_at": user.get("created_at"), "updated_at": user.get("updated_at")}


def audit(action, target, *, success=True, detail="", actor=None, db=None, mongo_session=None):
    db = database() if db is None else db
    db.audit_logs.insert_one({"actor": actor or getattr(g, "user", {}).get("_id", "system"),
                             "action": action, "target": target, "success": success,
                             "detail": detail[:500], "created_at": now()}, session=mongo_session)


def bootstrap():
    db = require_storage()
    db.auth_sessions.create_index("expires_at", expireAfterSeconds=0)
    db.login_attempts.create_index("expires_at", expireAfterSeconds=0)
    db.audit_logs.create_index([("created_at", -1)])
    db.auth_control.update_one({"_id": "accounts"}, {"$setOnInsert": {"revision": 0}}, upsert=True)
    initial_name, initial_password = os.environ.get("INITIAL_ADMIN_USERNAME"), os.environ.get("INITIAL_ADMIN_PASSWORD")
    if initial_name and initial_password:
        uid = username(initial_name)
        if db.accounts.find_one({"_id": uid}) is None:
            db.accounts.update_one({"_id": uid}, {"$setOnInsert": {
                "name": "Quản trị hệ thống", "role": "admin", "active": True, "auth_version": 1,
                "password_hash": generate_password_hash(password(initial_password)),
                "must_change_password": True, "created_at": now(), "updated_at": now(),
            }}, upsert=True)


def current_user():
    sid = session.get("sid")
    if not sid or not configured():
        return None
    db = database()
    record = db.auth_sessions.find_one({"_id": sha256(sid.encode()).hexdigest(), "expires_at": {"$gt": now()}})
    if not record:
        session.clear()
        return None
    user = db.accounts.find_one({"_id": record["user_id"], "active": True,
                                 "auth_version": record["auth_version"]})
    if not user:
        session.clear()
    return user


def require_user(*, admin=False, allow_password_change=False):
    user = getattr(g, "user", None) or current_user()
    if not user:
        raise Unauthorized("Vui lòng đăng nhập để tiếp tục.")
    g.user = user
    if admin and user["role"] != "admin":
        raise Forbidden("Chỉ quản trị viên được sử dụng chức năng này.")
    if user.get("must_change_password") and not allow_password_change:
        raise Forbidden("Bạn cần đổi mật khẩu trước khi tiếp tục.")
    return user


def admin_only(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        require_user(admin=True)
        return fn(*args, **kwargs)
    return wrapped


def install(app):
    app.config.update(
        SECRET_KEY=os.environ.get("SESSION_SECRET"), SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")), SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )
    app.register_blueprint(bp)

    @app.after_request
    def audit_denied(response):
        if response.status_code >= 400 and request.path.startswith("/api/admin/") and getattr(g, "user", None):
            try:
                audit("admin_action_denied", request.path, success=False,
                      detail=f"{request.method} {response.status_code}")
            except Exception:
                current_app.logger.exception("Could not record denied admin action")
        return response

    @app.before_request
    def guard():
        # Same-origin JSON plus a session CSRF token protects all authenticated writes.
        if request.path.startswith(("/api/admin", "/api/auth")) or enforced() or session.get("sid"):
            g.user = current_user()
        if request.method not in ("GET", "HEAD", "OPTIONS") and session.get("sid"):
            supplied = request.headers.get("X-CSRF-Token", "")
            if not secrets.compare_digest(supplied, session.get("csrf", "")) or not supplied:
                raise Forbidden("Phiên bảo mật đã thay đổi. Hãy tải lại trang.")
        if request.path == "/" and enforced():
            if not g.user:
                return redirect("/login")
            if g.user.get("must_change_password"):
                return redirect("/change-password")
        if enforced() and request.path.startswith("/api/") and request.path not in (
            "/api/health", "/api/auth/session", "/api/auth/login", "/api/auth/logout", "/api/auth/password",
        ):
            require_user()


@bp.get("/login")
def login_page():
    return render_template("login.html", password_change=False, configured=configured())


@bp.get("/change-password")
def password_page():
    require_user(allow_password_change=True)
    return render_template("login.html", password_change=True, configured=configured())


@bp.get("/api/auth/session")
def auth_session():
    user = getattr(g, "user", None) or current_user()
    return jsonify(user=public_user(user) if user else None, csrf=session.get("csrf"),
                   enabled=enforced(), configured=configured())


@bp.post("/api/auth/login")
def login():
    bootstrap()
    data = json_data()
    uid = username(data.get("username", ""))
    supplied = data.get("password", "")
    if not isinstance(supplied, str) or len(supplied) > 128:
        raise Unauthorized("Tên đăng nhập hoặc mật khẩu không đúng.")
    db = database()
    attempt_key = sha256(f"{request.remote_addr}:{uid}".encode()).hexdigest()
    from pymongo import ReturnDocument
    attempt = db.login_attempts.find_one_and_update(
        {"_id": attempt_key}, {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": now() + timedelta(minutes=15)}},
        upsert=True, return_document=ReturnDocument.AFTER,
    )
    if attempt.get("expires_at").replace(tzinfo=timezone.utc) <= now():
        db.login_attempts.update_one({"_id": attempt_key}, {"$set": {"count": 1, "expires_at": now() + timedelta(minutes=15)}})
    elif attempt["count"] > 5:
        return jsonify(error="Đăng nhập sai quá nhiều lần. Hãy thử lại sau 15 phút."), 429
    user = db.accounts.find_one({"_id": uid})
    valid = check_password_hash(user["password_hash"], supplied) if user else False
    if not user or not user["active"] or not valid:
        audit("login", uid, success=False, actor=uid)
        raise Unauthorized("Tên đăng nhập hoặc mật khẩu không đúng, hoặc tài khoản đã bị khóa.")
    db.login_attempts.delete_one({"_id": attempt_key})
    session.clear()
    raw = secrets.token_hex(32)
    session.update(sid=raw, csrf=secrets.token_hex(32))
    session.permanent = True
    db.auth_sessions.insert_one({"_id": sha256(raw.encode()).hexdigest(), "user_id": uid,
                                 "auth_version": user["auth_version"], "expires_at": now() + timedelta(hours=8)})
    audit("login", uid, actor=uid)
    return jsonify(user=public_user(user), csrf=session["csrf"],
                   redirect="/change-password" if user.get("must_change_password") else "/admin" if user["role"] == "admin" else "/")


@bp.post("/api/auth/logout")
def logout():
    if session.get("sid") and configured():
        database().auth_sessions.delete_one({"_id": sha256(session["sid"].encode()).hexdigest()})
        if getattr(g, "user", None):
            audit("logout", g.user["_id"])
    if current_app.secret_key:
        session.clear()
    return jsonify(ok=True)


@bp.post("/api/auth/password")
def change_password():
    user = require_user(allow_password_change=True)
    data = json_data()
    if not check_password_hash(user["password_hash"], str(data.get("current_password", ""))):
        raise BadRequest("Mật khẩu hiện tại không đúng.")
    new = password(data.get("new_password"))
    if check_password_hash(user["password_hash"], new):
        raise BadRequest("Mật khẩu mới cần khác mật khẩu hiện tại.")
    db = database()
    db.accounts.update_one({"_id": user["_id"]}, {"$set": {"password_hash": generate_password_hash(new),
        "must_change_password": False, "updated_at": now()}, "$inc": {"auth_version": 1}})
    db.auth_sessions.delete_many({"user_id": user["_id"]})
    audit("password_change", user["_id"])
    session.clear()
    return jsonify(ok=True, redirect="/login")


@bp.get("/admin")
def admin_page():
    user = current_user()
    if not user:
        return redirect("/login")
    g.user = user
    require_user(admin=True)
    return render_template("admin.html")


@bp.get("/api/admin/users")
@admin_only
def users():
    return jsonify(users=[public_user(u) for u in database().accounts.find().sort("created_at", -1)])


@bp.post("/api/admin/users")
@admin_only
def create_user():
    data = json_data()
    uid, new = username(data.get("username", "")), password(data.get("password"))
    role = data.get("role", "analyst")
    name = str(data.get("name", "")).strip()
    if role not in ("admin", "analyst") or not 1 <= len(name) <= 100:
        raise BadRequest("Cần tên hiển thị và vai trò Admin hoặc Analyst hợp lệ.")
    user = {"_id": uid, "name": name, "role": role, "active": True, "auth_version": 1,
            "password_hash": generate_password_hash(new), "must_change_password": True,
            "created_at": now(), "updated_at": now()}
    from pymongo.errors import DuplicateKeyError
    try:
        database().accounts.insert_one(user)
    except DuplicateKeyError:
        raise BadRequest("Tên đăng nhập đã tồn tại.") from None
    audit("account_create", uid, detail=f"role={role}")
    return jsonify(user=public_user(user)), 201


@bp.patch("/api/admin/users/<uid>")
@admin_only
def update_user(uid):
    data = json_data()
    db = database()
    changes = {}
    if "name" in data:
        name = str(data["name"]).strip()
        if not 1 <= len(name) <= 100:
            raise BadRequest("Tên hiển thị cần 1–100 ký tự.")
        changes["name"] = name
    if "role" in data:
        if data["role"] not in ("admin", "analyst"):
            raise BadRequest("Vai trò không hợp lệ.")
        changes["role"] = data["role"]
    if "active" in data:
        if not isinstance(data["active"], bool):
            raise BadRequest("Trạng thái tài khoản không hợp lệ.")
        changes["active"] = data["active"]
    if "password" in data:
        changes.update(password_hash=generate_password_hash(password(data["password"])), must_change_password=True)
    if not changes:
        raise BadRequest("Chưa có thay đổi.")

    def write(mongo_session):
        # The shared control write serializes concurrent last-admin changes in Atlas transactions.
        db.auth_control.update_one({"_id": "accounts"}, {"$inc": {"revision": 1}}, session=mongo_session)
        user = db.accounts.find_one({"_id": uid}, session=mongo_session)
        if not user:
            raise BadRequest("Không tìm thấy tài khoản.")
        updated = {**user, **changes}
        if user["role"] == "admin" and user["active"] and (updated["role"] != "admin" or not updated["active"]):
            if db.accounts.count_documents({"role": "admin", "active": True}, session=mongo_session) <= 1:
                raise BadRequest("Không thể khóa hoặc hạ quyền Admin cuối cùng đang hoạt động.")
        db.accounts.update_one({"_id": uid}, {"$set": {**changes, "updated_at": now()},
                                               "$inc": {"auth_version": 1}}, session=mongo_session)
        audit("account_update", uid, detail=", ".join("password_reset" if k == "password_hash" else k
              for k in changes if k != "must_change_password"), db=db, mongo_session=mongo_session)
    with db.client.start_session() as mongo_session:
        mongo_session.with_transaction(write)
    return jsonify(ok=True)


@bp.get("/api/admin/audit")
@admin_only
def audit_log():
    query = {}
    for field in ("actor", "action", "target"):
        if request.args.get(field):
            query[field] = request.args[field][:100]
    dates = {}
    for argument, operator in (("since", "$gte"), ("until", "$lte")):
        if request.args.get(argument):
            try:
                dates[operator] = datetime.fromisoformat(request.args[argument].replace("Z", "+00:00"))
            except ValueError:
                raise BadRequest("Khoảng thời gian không hợp lệ.") from None
    if dates:
        query["created_at"] = dates
    rows = list(database().audit_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(200))
    return jsonify(rows=rows)


@bp.get("/api/admin/overview")
@admin_only
def overview():
    db = database()
    return jsonify(accounts=db.accounts.count_documents({}), active=db.accounts.count_documents({"active": True}),
                   locked=db.accounts.count_documents({"active": False}),
                   admins=db.accounts.count_documents({"active": True, "role": "admin"}),
                   workspaces=list(db.workspaces.find({"account_id": {"$exists": True}}, {"snapshot": 0})),
                   training_available=False)


@bp.get("/api/admin/models")
@admin_only
def models():
    from .web import model_registry
    active = database().system_settings.find_one({"_id": "active_model"}) or {"name": "Random Forest"}
    return jsonify(models=[{"name": m.name, "version": m.version, "digest": m.digest,
                            "status": "Active" if m.name == active["name"] else "Evaluated",
                            "cv_auc": m.metadata.get("cv_auc"), "test_auc": m.metadata.get("test_auc"),
                            "threshold": m.threshold} for m in model_registry().values()],
                   active=active["name"], previous=(active.get("previous") or {}).get("name"),
                   training_available=False)


@bp.post("/api/admin/models/<action>")
@admin_only
def activate_model(action):
    from .web import model_registry
    from pymongo.errors import DuplicateKeyError
    from werkzeug.exceptions import Conflict
    if action not in ("activate", "rollback"):
        raise BadRequest("Chức năng mô hình không hợp lệ.")
    data = json_data()
    reason = str(data.get("reason", "")).strip()
    if not 5 <= len(reason) <= 500:
        raise BadRequest("Cần lý do kích hoạt/rollback từ 5 đến 500 ký tự.")
    db = database()
    stored = db.system_settings.find_one({"_id": "active_model"})
    current = stored or {"name": "Random Forest", "revision": 0}
    name = (current.get("previous") or {}).get("name") if action == "rollback" else data.get("name")
    candidate = model_registry().get(name)
    if not candidate or candidate.metadata.get("test_auc") is None:
        raise BadRequest("Chỉ chọn mô hình tích hợp đã có kết quả đánh giá.")
    if candidate.name == current["name"]:
        raise BadRequest("Mô hình này đang Active.")
    new = {"_id": "active_model", "name": candidate.name, "digest": candidate.digest,
           "version": candidate.version, "previous": {"name": current["name"]},
           "revision": current["revision"] + 1, "updated_at": now(), "updated_by": g.user["_id"]}
    try:
        if stored:
            changed = db.system_settings.replace_one({"_id": "active_model", "revision": current["revision"]}, new)
            if changed.matched_count != 1:
                raise Conflict("Mô hình Active vừa thay đổi. Hãy tải lại.")
        else:
            db.system_settings.insert_one(new)
    except DuplicateKeyError:
        raise Conflict("Mô hình Active vừa thay đổi. Hãy tải lại.") from None
    audit("model_" + action, candidate.name, detail=reason)
    return jsonify(ok=True)
