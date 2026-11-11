"""Fill only the five supplementary inputs using the trusted train statistics."""

from functools import lru_cache
import hashlib

import joblib
from .config import ROOT
from .validation import FEATURES, ValidationError, prepare_input

STATS_SHA256 = "7dab4cbe963f5366036fa5d4fc2af694180baad4ad929b11b61144da12f4e38c"
OPTIONAL = ("SEX", "EDUCATION", "MARRIAGE", "AGE", "PAY_AMT6")
REQUIRED = [name for name in FEATURES if name not in OPTIONAL]


@lru_cache(maxsize=1)
def training_defaults():
    path = ROOT / "models/impute_stats_v1.pkl"
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != STATS_SHA256:
        raise ValidationError("Thiếu hoặc sai bộ thống kê điền dữ liệu từ tập train.")
    stats = joblib.load(path)
    return {name: stats["mode" if name in ("SEX", "EDUCATION", "MARRIAGE") else "median"][name]
            for name in OPTIONAL}


def prepare_missing(frame):
    frame = frame.copy().reset_index(drop=True)
    frame.columns = [str(name).strip() for name in frame.columns]
    if frame.columns.duplicated().any() or ("PAY_0" in frame and "PAY_1" in frame):
        raise ValidationError("Cột bị trùng; chỉ dùng PAY_0 hoặc PAY_1, không dùng đồng thời.")
    frame = frame.rename(columns={"PAY_1": "PAY_0"})
    missing_columns = [name for name in REQUIRED if name not in frame]
    if missing_columns:
        raise ValidationError("Thiếu cột bắt buộc để tính đặc trưng: " + ", ".join(missing_columns))
    missing = frame.reindex(columns=FEATURES).isna()
    for name in FEATURES:
        if name in frame:
            missing[name] |= frame[name].map(lambda value: isinstance(value, str) and not value.strip())
    errors = [f"Dòng {index + 2}: thiếu {name} (bắt buộc để tính đặc trưng)"
              for name in REQUIRED for index in frame.index[missing[name]][:5]]
    if errors:
        raise ValidationError("\n".join(errors[:20]))
    report = {"total_rows": len(frame), "filled_rows": 0, "filled_cells": 0,
              "stats_sha256": STATS_SHA256, "rows": []}
    if missing[list(OPTIONAL)].any().any():
        defaults = training_defaults()
        for name in OPTIONAL:
            if name not in frame:
                frame[name] = defaults[name]
            else:
                frame.loc[missing[name], name] = defaults[name]
        for index in frame.index[missing[list(OPTIONAL)].any(axis=1)]:
            fields = [name for name in OPTIONAL if missing.loc[index, name]]
            report["rows"].append({"row": int(index) + 2, "fields": fields,
                                   "values": {name: defaults[name] for name in fields}})
            report["filled_cells"] += len(fields)
        report["filled_rows"] = len(report["rows"])
    prepared = prepare_input(frame)
    for entry in report["rows"]:
        entry["ID"] = prepared.loc[entry["row"] - 2, "ID"]
    return prepared, report
