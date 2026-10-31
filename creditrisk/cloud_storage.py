"""Optional MongoDB Atlas snapshots, isolated by a hashed 256-bit workspace key."""
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
import json
import os
import re

from werkzeug.exceptions import BadRequest, Conflict, ServiceUnavailable, Unauthorized


def enabled():
    return bool(os.environ.get("MONGODB_URI"))


def workspace_id(authorization):
    token = authorization.removeprefix("Bearer ")
    if not authorization.startswith("Bearer ") or not re.fullmatch(r"[0-9a-f]{64}", token):
        raise Unauthorized("Cần mã kho dữ liệu riêng gồm 64 ký tự hex.")
    return sha256(token.encode()).hexdigest()


@lru_cache(maxsize=1)
def database():
    from pymongo import MongoClient
    if not enabled():
        raise ServiceUnavailable("Chưa cấu hình MONGODB_URI trên Vercel.")
    client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=8000,
                         connectTimeoutMS=8000, maxPoolSize=5)
    return client[os.environ.get("MONGODB_DATABASE", "creditrisk_ai")]


def read_snapshot(owner):
    from gridfs import GridFSBucket
    db = database()
    doc = db.workspaces.find_one({"_id": owner})
    if not doc:
        return {"revision": 0, "state": None}
    output = BytesIO()
    GridFSBucket(db).download_to_stream(doc["snapshot"], output)
    return {"revision": doc["revision"], "state": json.loads(output.getvalue())}


def write_snapshot(owner, state, revision):
    from gridfs import GridFSBucket
    from pymongo.errors import DuplicateKeyError
    if (not isinstance(state, dict) or not isinstance(state.get("datasets"), list)
            or not isinstance(state.get("runs"), list) or not isinstance(revision, int) or revision < 0):
        raise BadRequest("Dữ liệu đồng bộ không hợp lệ.")
    db = database()
    bucket = GridFSBucket(db)
    previous = db.workspaces.find_one({"_id": owner})
    if (previous or {}).get("revision", 0) != revision:
        raise Conflict("Kho dữ liệu đã thay đổi ở thiết bị khác. Hãy sao lưu JSON rồi tải lại trang.")
    snapshot = bucket.upload_from_stream("workspace.json", BytesIO(json.dumps(state, ensure_ascii=False).encode()))
    try:
        if previous:
            result = db.workspaces.update_one({"_id": owner, "revision": revision},
                                             {"$set": {"snapshot": snapshot, "revision": revision + 1}})
            if result.modified_count != 1:
                raise Conflict("Kho dữ liệu đã thay đổi. Hãy sao lưu JSON rồi tải lại trang.")
        else:
            db.workspaces.insert_one({"_id": owner, "snapshot": snapshot, "revision": 1})
    except (Conflict, DuplicateKeyError):
        bucket.delete(snapshot)
        raise Conflict("Kho dữ liệu đã thay đổi. Hãy sao lưu JSON rồi tải lại trang.") from None
    if previous:
        bucket.delete(previous["snapshot"])
    return {"revision": revision + 1}
