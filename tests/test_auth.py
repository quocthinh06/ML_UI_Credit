from copy import deepcopy
from datetime import datetime, timezone

import mongomock
import pytest
from werkzeug.security import generate_password_hash

from creditrisk.web import create_app

TEST_PASSWORD = "Local-test-password-2026"


class Transaction:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def with_transaction(self, callback):
        return callback(None)


@pytest.fixture
def auth_app(monkeypatch):
    db = mongomock.MongoClient().creditrisk_test
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("MONGODB_URI", "mongodb://test.invalid")
    monkeypatch.setenv("SESSION_SECRET", "test-session-key-" * 4)
    monkeypatch.delenv("INITIAL_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr("creditrisk.auth.database", lambda: db)
    monkeypatch.setattr("creditrisk.cloud_storage.database", lambda: db)
    monkeypatch.setattr(db.client, "start_session", lambda: Transaction())
    # Scope/auth tests use an isolated snapshot store; Atlas/GridFS needs live integration credentials.
    snapshots = {}
    def read(owner):
        return deepcopy(snapshots.get(owner, {"revision": 0, "state": None}))
    def write(owner, state, revision):
        from werkzeug.exceptions import Conflict
        if read(owner)["revision"] != revision:
            raise Conflict()
        snapshots[owner] = {"revision": revision + 1, "state": deepcopy(state)}
        db.workspaces.update_one({"_id": owner}, {"$set": {"revision": revision + 1}}, upsert=True)
        return {"revision": revision + 1}
    monkeypatch.setattr("creditrisk.cloud_storage.read_snapshot", read)
    monkeypatch.setattr("creditrisk.cloud_storage.write_snapshot", write)
    for uid, role in [("rootadmin", "admin"), ("analyst_a", "analyst"), ("analyst_b", "analyst")]:
        db.accounts.insert_one({"_id": uid, "name": uid, "role": role, "active": True,
                               "password_hash": generate_password_hash(TEST_PASSWORD), "auth_version": 1,
                               "must_change_password": False, "created_at": datetime.now(timezone.utc)})
    app = create_app({"TESTING": True})
    return app, db


def login(client, name, password=TEST_PASSWORD):
    result = client.post("/api/auth/login", json={"username": name, "password": password})
    assert result.status_code == 200, result.json
    return {"X-CSRF-Token": result.json["csrf"]}


def test_login_ui_and_auth_required(auth_app):
    app, _ = auth_app
    client = app.test_client()
    assert client.get("/").location.endswith("/login")
    page = client.get("/login")
    assert page.status_code == 200 and b'login-form' in page.data
    assert client.get("/api/models").status_code == 401
    assert client.get("/api/admin/users").status_code == 401
    assert client.get("/api/health").status_code == 200


def test_analyst_cannot_use_admin_or_access_another_workspace(auth_app):
    app, _ = auth_app
    client = app.test_client()
    headers = login(client, "analyst_a")
    assert client.get("/api/admin/users").status_code == 403
    assert client.post("/api/admin/users", headers=headers, json={}).status_code == 403
    assert client.patch("/api/admin/users/analyst_a", headers=headers, json={"role": "admin"}).status_code == 403
    assert client.get("/api/workspace?account_id=analyst_b").status_code == 403
    assert client.put("/api/workspace?account_id=analyst_b", headers=headers,
                      json={"state": {"datasets": [], "runs": []}, "revision": 0}).status_code == 403


def test_analyst_owns_data_and_can_add_edit_delete_rows_by_revision(auth_app):
    app, _ = auth_app
    alice, bob = app.test_client(), app.test_client()
    headers = login(alice, "analyst_a")
    login(bob, "analyst_b")
    state = {"datasets": [{"id": "ds-a", "name": "Own data", "versions": [
        {"id": "v1", "revision": 1, "rows": [{"ID": "A", "AGE": 30}]}]}], "runs": []}
    result = alice.put("/api/workspace", headers=headers, json={"state": state, "revision": 0})
    assert result.status_code == 200
    assert bob.get("/api/workspace").json["state"] is None
    assert alice.get("/api/workspace").json["state"] == state
    original = deepcopy(state)
    state["datasets"][0]["versions"].append({"id": "v2", "revision": 2, "rows": [{"ID": "A", "AGE": 44}]})
    assert alice.put("/api/workspace", headers=headers, json={"state": state, "revision": 1}).status_code == 200
    state["datasets"][0]["versions"].append({"id": "v3", "revision": 3, "rows": []})
    assert alice.put("/api/workspace", headers=headers, json={"state": state, "revision": 2}).status_code == 200
    state["datasets"][0]["versions"][0]["rows"] = []
    assert alice.put("/api/workspace", headers=headers, json={"state": state, "revision": 3}).status_code == 400
    assert alice.get("/api/workspace").json["state"]["datasets"][0]["versions"][0] == original["datasets"][0]["versions"][0]


def test_account_lock_and_role_change_revoke_sessions(auth_app):
    app, _ = auth_app
    admin, analyst = app.test_client(), app.test_client()
    csrf = login(admin, "rootadmin")
    login(analyst, "analyst_a")
    assert admin.patch("/api/admin/users/analyst_a", headers=csrf, json={"active": False}).status_code == 200
    assert analyst.get("/api/workspace").status_code == 401
    assert analyst.post("/api/auth/login", json={"username": "analyst_a", "password": TEST_PASSWORD}).status_code == 401
    assert admin.patch("/api/admin/users/analyst_a", headers=csrf, json={"active": True}).status_code == 200
    login(analyst, "analyst_a")
    assert admin.patch("/api/admin/users/analyst_a", headers=csrf, json={"role": "admin"}).status_code == 200
    assert analyst.get("/api/admin/users").status_code == 401


def test_final_admin_protected_and_csrf_required(auth_app):
    app, db = auth_app
    client = app.test_client()
    csrf = login(client, "rootadmin")
    assert client.patch("/api/admin/users/analyst_a", json={"active": False}).status_code == 403
    for changes in ({"active": False}, {"role": "analyst"}):
        assert client.patch("/api/admin/users/rootadmin", headers=csrf, json=changes).status_code == 400
    assert db.accounts.find_one({"_id": "rootadmin"})["active"]


def test_create_user_password_reset_and_audit(auth_app):
    app, db = auth_app
    admin, new = app.test_client(), app.test_client()
    csrf = login(admin, "rootadmin")
    result = admin.post("/api/admin/users", headers=csrf, json={"username": "new_analyst", "name": "New analyst",
                        "role": "analyst", "password": TEST_PASSWORD})
    assert result.status_code == 201
    assert "password_hash" not in result.json["user"]
    record = db.accounts.find_one({"_id": "new_analyst"})
    assert record["password_hash"] != TEST_PASSWORD
    change_csrf = login(new, "new_analyst")
    assert new.get("/api/workspace").status_code == 403
    result = new.post("/api/auth/password", headers=change_csrf,
                      json={"current_password": TEST_PASSWORD, "new_password": "Different-local-password-2026"})
    assert result.status_code == 200
    login(new, "new_analyst", "Different-local-password-2026")
    assert new.get("/api/workspace").status_code == 200
    logs = admin.get("/api/admin/audit?action=account_create").json["rows"]
    assert logs[0]["actor"] == "rootadmin" and logs[0]["target"] == "new_analyst"


def test_brute_force_limit(auth_app):
    app, _ = auth_app
    client = app.test_client()
    for _ in range(5):
        assert client.post("/api/auth/login", json={"username": "analyst_a", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "analyst_a", "password": TEST_PASSWORD}).status_code == 429


def test_model_activation_and_rollback_are_admin_only(auth_app, monkeypatch):
    from types import SimpleNamespace

    models = {name: SimpleNamespace(name=name, version="v1", digest=str(i) * 64, threshold=0.39,
                                    metadata={"cv_auc": 0.8, "test_auc": 0.79})
              for i, name in enumerate(["Random Forest", "Logistic Regression"])}
    monkeypatch.setattr("creditrisk.web.model_registry", lambda: models)
    app, _ = auth_app
    admin, analyst = app.test_client(), app.test_client()
    csrf = login(admin, "rootadmin")
    analyst_csrf = login(analyst, "analyst_a")
    body = {"name": "Logistic Regression", "reason": "Compare evaluated model"}
    assert analyst.post("/api/admin/models/activate", json=body, headers=analyst_csrf).status_code == 403
    assert admin.post("/api/admin/models/activate", json=body, headers=csrf).status_code == 200
    assert admin.get("/api/models").json["default_model"] == "Logistic Regression"
    assert admin.post("/api/admin/models/rollback", json={"reason": "Restore prior version"}, headers=csrf).status_code == 200
    assert admin.get("/api/models").json["default_model"] == "Random Forest"
    assert admin.get("/api/admin/models").json["training_available"] is False
