"""Run locally with server environment; emits no URI, credentials or account names."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from creditrisk import auth, cloud_storage  # noqa: E402
from creditrisk.mongo_diagnostics import connection_error  # noqa: E402
from creditrisk.web import create_app  # noqa: E402


def check(*, bootstrap=False):
    app = create_app()
    with app.app_context():
        if not auth.configured():
            return {"ok": False, "code": "AUTH_CONFIGURATION_MISSING",
                    "error": "Cần MONGODB_URI và SESSION_SECRET tối thiểu 32 ký tự."}
        try:
            db = cloud_storage.database()
            db.command("ping")
            # Ping alone does not verify account read permission.
            admin_exists = db.accounts.find_one({"role": "admin", "active": True}, {"_id": 1}) is not None
            if bootstrap:
                auth.bootstrap()
                admin_exists = db.accounts.find_one({"role": "admin", "active": True}, {"_id": 1}) is not None
            return {"ok": admin_exists, "code": "READY" if admin_exists else "ADMIN_NOT_INITIALIZED",
                    "connected": True, "account_readable": True, "admin_exists": admin_exists,
                    "auth_enabled": auth.enforced(),
                    "hint": "Đăng nhập web để kiểm tra phiên, CSRF và lưu dữ liệu." if admin_exists else
                    "Cấu hình INITIAL_ADMIN_USERNAME/PASSWORD rồi chạy lại với --bootstrap để tạo Admin và chỉ mục."}
        except Exception as exc:
            diagnostic = connection_error(exc)
            code, message = diagnostic or ("CHECK_FAILED", "Kiểm tra thất bại; kiểm tra cấu hình máy chủ.")
            return {"ok": False, "code": code, "error": message}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", action="store_true", help="Create configured initial admin and indexes")
    args = parser.parse_args()
    result = check(bootstrap=args.bootstrap)
    print(json.dumps(result))
    sys.exit(0 if result["ok"] else 1)
