import json
import os
from pathlib import Path

from sqlalchemy import URL, create_engine

ROOT = Path(__file__).resolve().parents[1]


def load_config(path=None):
    path = Path(path or ROOT / "config.local.json")
    if not path.exists():
        raise ValueError("Chưa có config.local.json. Sao chép config.example.json và điền tài khoản MySQL.")
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if os.environ.get("CREDITRISK_DB_PASSWORD"):
        config["mysql"]["password"] = os.environ["CREDITRISK_DB_PASSWORD"]
    return config


def database_engine(config):
    db = config["mysql"]
    url = URL.create(
        "mysql+pymysql",
        username=db["user"],
        password=db.get("password", ""),
        host=db.get("host", "127.0.0.1"),
        port=int(db.get("port", 3306)),
        database=db["database"],
        query={"charset": "utf8mb4"},
    )
    args = {"connect_timeout": 5}
    if db.get("ssl_ca"):
        args["ssl"] = {"ca": db["ssl_ca"], "check_hostname": True}
    return create_engine(url, pool_pre_ping=True, connect_args=args)
