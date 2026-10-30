"""The UCI input contract, shared by forms, imports and model inference."""

from dataclasses import dataclass
import math

import pandas as pd

PAY_COLUMNS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
FEATURES = [
    "LIMIT_BAL",
    "SEX",
    "EDUCATION",
    "MARRIAGE",
    "AGE",
    *PAY_COLUMNS,
    *[f"BILL_AMT{i}" for i in range(1, 7)],
    *[f"PAY_AMT{i}" for i in range(1, 7)],
]


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Thresholds:
    decision: float = 0.39
    low: float = 0.20
    high: float = 0.50

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.decision, self.low, self.high)):
            raise ValidationError("Ngưỡng phải là số hữu hạn.")
        if not 0 <= self.decision <= 1 or not 0 <= self.low < self.high <= 1:
            raise ValidationError("Ngưỡng nhãn thuộc [0, 1]; cần 0 ≤ thấp < cao ≤ 1.")


def validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.columns.duplicated().any():
        raise ValidationError("Tên cột bị trùng sau khi bỏ khoảng trắng.")
    if "PAY_1" in frame and "PAY_0" not in frame:
        frame = frame.rename(columns={"PAY_1": "PAY_0"})
    elif "PAY_1" in frame and "PAY_0" in frame:
        raise ValidationError("Chỉ dùng PAY_0 hoặc PAY_1, không dùng đồng thời.")
    missing = [c for c in FEATURES if c not in frame]
    if missing:
        raise ValidationError("Thiếu cột: " + ", ".join(missing))
    if frame.empty:
        raise ValidationError("Tệp không có hồ sơ.")
    values = frame[FEATURES].apply(pd.to_numeric, errors="coerce")
    import numpy as np

    invalid = ~np.isfinite(values.to_numpy(dtype=float))
    errors = []
    if invalid.any():
        rows, cols = np.where(invalid)
        errors.extend(f"Dòng {r + 2}: {FEATURES[c]} phải là số hữu hạn" for r, c in zip(rows[:10], cols[:10]))
    bounds = {
        "LIMIT_BAL": (1, 10_000_000),
        "SEX": (1, 2),
        "EDUCATION": (1, 4),
        "MARRIAGE": (1, 3),
        "AGE": (18, 100),
        **{c: (-2, 8) for c in PAY_COLUMNS},
        **{f"PAY_AMT{i}": (0, float("inf")) for i in range(1, 7)},
    }
    discrete = {"SEX", "EDUCATION", "MARRIAGE", "AGE", *PAY_COLUMNS}
    for col, (lo, hi) in bounds.items():
        bad = ~values[col].between(lo, hi)
        if col in discrete:
            bad |= values[col] % 1 != 0
        for pos in np.flatnonzero(bad.to_numpy())[:5]:
            errors.append(
                f"Dòng {pos + 2}: {col} ngoài miền [{lo}, {hi}]" + (" (số nguyên)" if col in discrete else "")
            )
    if errors:
        raise ValidationError("\n".join(errors[:20]))
    return values.astype(float).reset_index(drop=True)


def customer_ids(frame: pd.DataFrame) -> list[str]:
    if "ID" not in frame:
        return [str(i + 1) for i in range(len(frame))]
    ids = frame["ID"].map(lambda v: "" if pd.isna(v) else str(v).strip())
    if (ids == "").any() or ids.str.len().gt(128).any() or ids.duplicated().any():
        raise ValidationError("ID phải có giá trị, tối đa 128 ký tự và không trùng trong tệp.")
    return ids.tolist()
