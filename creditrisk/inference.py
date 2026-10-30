"""Explicit artifact contract. Never invent features or probabilities."""

import hashlib
from pathlib import Path
import warnings

import joblib
import numpy as np
from sklearn.exceptions import InconsistentVersionWarning

from .validation import FEATURES, Thresholds, validate_frame, prepare_input


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
            try:
                bundle = joblib.load(path)
            except Exception:
                from .xgb_compat import SOURCE_SHA256, load_portable_handoff

                if self.digest != SOURCE_SHA256:
                    raise
                bundle = load_portable_handoff(path)
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
        values = validate_frame(prepare_input(frame))
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
                "default_label": (
                    (raw if thresholds.basis == "raw" else probability) >= thresholds.decision
                ).astype(int),
                "risk_level": np.where(
                    probability < thresholds.low,
                    "Low",
                    np.where(probability < thresholds.high, "Medium", "High"),
                ),
            }
        )

    def explain(self, frame):
        """Tree SHAP on the estimator's actual transformed inputs, not on calibrated PD."""
        import pandas as pd
        import shap
        from .features import add_features

        if len(frame) != 1:
            raise ValueError("Giải thích cần đúng một hồ sơ.")
        values = add_features(validate_frame(frame).rename(columns={"PAY_0": "PAY_1"}))[self.features]
        preprocessing = self.pipeline[:-1]
        transformed = preprocessing.transform(values) if len(preprocessing.steps) else values.to_numpy()
        if hasattr(transformed, "toarray"):
            transformed = transformed.toarray()
        estimator = self.pipeline.steps[-1][1]
        names = list(preprocessing.get_feature_names_out()) if len(preprocessing.steps) else self.features
        if hasattr(estimator, "coef_"):
            contributions = np.asarray(transformed)[0] * estimator.coef_[0]
            return pd.DataFrame({"feature": names, "contribution": contributions}).assign(
                scale="log-odds (hệ số × giá trị chuẩn hóa)"
            )
        explainer = shap.TreeExplainer(estimator)
        explanation = explainer(np.asarray(transformed), check_additivity=False)
        contributions = explanation.values
        if contributions.ndim == 3:
            contributions = contributions[:, :, list(estimator.classes_).index(1)]
        scale = "điểm thô" if self.name == "Random Forest" else "log-odds thô"
        return pd.DataFrame({"feature": names, "contribution": contributions[0]}).assign(
            scale=f"Tree SHAP · {scale}"
        )


def load_models(model_path):
    path = Path(model_path)
    default = ModelRunner(path)
    available = {default.name: default}
    errors = []
    for name in ("model_lr_v1.pkl", "model_rf_v1.pkl", "model_xgb_v1.pkl"):
        candidate = path.parent / name
        if candidate.is_file():
            try:
                runner = ModelRunner(candidate)
                if runner.name not in available:
                    available[runner.name] = runner
            except Exception as exc:
                errors.append(f"{name}: {exc}")
    return available, errors
