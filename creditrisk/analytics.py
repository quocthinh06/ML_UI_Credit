"""Statistics from the selected dataset/run; unknown targets never count as negatives."""

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    brier_score_loss,
)
from .validation import TARGET


def labelled(frame):
    if TARGET not in frame:
        return frame.iloc[:0]
    target = pd.to_numeric(frame[TARGET], errors="coerce")
    return frame.loc[target.isin([0, 1])].assign(**{TARGET: target[target.isin([0, 1])].astype(int)})


def summary(frame):
    known = labelled(frame)
    return {
        "rows": len(frame),
        "labelled": len(known),
        "actual_default_rate": float(known[TARGET].mean()) if len(known) else None,
        "mean_pd": float(frame.probability.mean()) if "probability" in frame and len(frame) else None,
        "warnings": int(frame.default_label.sum()) if "default_label" in frame else 0,
        "high_risk": int((frame.risk_level == "High").sum()) if "risk_level" in frame else 0,
    }


def evaluation(frame):
    known = labelled(frame)
    if known.empty or "default_label" not in known:
        return {}
    y, pred = known[TARGET], known.default_label
    return {
        "labelled_rows": len(known),
        "Accuracy": accuracy_score(y, pred),
        "Precision": precision_score(y, pred, zero_division=0),
        "Recall": recall_score(y, pred, zero_division=0),
        "F1": f1_score(y, pred, zero_division=0),
        "AUC": roc_auc_score(y, known.raw_score) if y.nunique() == 2 else None,
        "Brier_PD": brier_score_loss(y, known.probability),
    }
