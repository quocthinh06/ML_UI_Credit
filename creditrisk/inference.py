"""Explicit artifact contract. Never invent features or probabilities."""

import hashlib
from pathlib import Path
import warnings

import joblib
import numpy as np
from sklearn.exceptions import InconsistentVersionWarning

from .validation import FEATURES, Thresholds, validate_frame


class ModelUnavailable(ValueError):
    pass


class ModelRunner:
    def __init__(self, model_path):
        path = Path(model_path)
        if not path.is_file():
            raise ModelUnavailable("Chưa có mô hình thật. Xem models/README.md để tải bộ bàn giao.")
        self.digest = hashlib.sha256(path.read_bytes()).hexdigest()
        # Joblib executes Python: load only the trusted, locally configured handoff.
        with warnings.catch_warnings():
            warnings.simplefilter("error", InconsistentVersionWarning)
            bundle = joblib.load(path)
        required = {"pipeline", "threshold", "features", "calibrator", "model_name", "versions"}
        if not isinstance(bundle, dict) or not required.issubset(bundle):
            raise ModelUnavailable("Tệp không đúng cấu trúc bộ mô hình bàn giao.")
        import sklearn

        if bundle["versions"].get("sklearn") != sklearn.__version__:
            raise ModelUnavailable("Phiên bản scikit-learn không khớp bộ bàn giao.")
        self.name = {"rf": "Random Forest", "lr": "Logistic Regression", "xgb": "XGBoost"}.get(
            bundle["model_name"], bundle["model_name"]
        )
        self.version = path.stem
        self.threshold = float(bundle["threshold"])
        Thresholds(decision=self.threshold)
        self.features = bundle["features"]
        self.pipeline = bundle["pipeline"]
        self.calibrator = bundle["calibrator"]
        self.metadata = {k: v for k, v in bundle.items() if k not in ("pipeline", "calibrator")}
        from .features import add_features
        import pandas as pd

        sample = pd.DataFrame([{c: 1.0 for c in FEATURES}]).rename(columns={"PAY_0": "PAY_1"})
        if set(add_features(sample).columns) != set(self.features) or len(self.features) != 38:
            raise ModelUnavailable("Danh sách đặc trưng khác bộ bàn giao 38 trường.")

    def predict(self, frame, thresholds):
        values = validate_frame(frame)
        from .features import add_features

        values = add_features(values.rename(columns={"PAY_0": "PAY_1"}))[self.features]
        classes = list(self.pipeline.classes_)
        if set(classes) != {0, 1}:
            raise ModelUnavailable("Mô hình phải có hai lớp 0 và 1.")
        raw = np.asarray(self.pipeline.predict_proba(values), dtype=float)[:, classes.index(1)]
        probability = raw.copy()
        if self.calibrator is not None:
            # Contract: isotonic-style predict accepts a 1-D vector of raw scores.
            probability = np.asarray(self.calibrator.predict(raw), dtype=float).reshape(-1)
        if len(raw) != len(values) or len(probability) != len(values):
            raise ModelUnavailable("Số kết quả mô hình không khớp số hồ sơ.")
        for output in (raw, probability):
            if not np.isfinite(output).all() or ((output < 0) | (output > 1)).any():
                raise ModelUnavailable("Mô hình trả điểm/xác suất ngoài [0, 1].")
        import pandas as pd

        return pd.DataFrame(
            {
                "raw_score": raw,
                "probability": probability,
                "default_label": (raw >= thresholds.decision).astype(int),
                "risk_level": np.where(
                    probability < thresholds.low,
                    "Low",
                    np.where(probability < thresholds.high, "Medium", "High"),
                ),
            }
        )
