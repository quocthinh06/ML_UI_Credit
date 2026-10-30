"""Verify feature parity and original model metrics, without writing to MySQL."""

import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, confusion_matrix, roc_auc_score

from creditrisk.config import ROOT
from creditrisk.features import add_features
from creditrisk.inference import ModelRunner
from creditrisk.validation import FEATURES, Thresholds


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=Path, help="Directory containing original X_test.csv and y_test.csv")
    args = parser.parse_args()
    model = ModelRunner(ROOT / "models/best_model_v1.pkl")
    x = pd.read_csv(args.data_dir / "X_test.csv")
    y = pd.read_csv(args.data_dir / "y_test.csv").iloc[:, 0]
    base = x.rename(columns={"PAY_1": "PAY_0"})[FEATURES]
    rebuilt = add_features(base.rename(columns={"PAY_0": "PAY_1"}))[model.features]
    assert np.allclose(rebuilt, x[model.features]), "Derived features differ from original handoff"
    output = model.predict(base, Thresholds(decision=model.threshold))
    auc = roc_auc_score(y, output.raw_score)
    assert abs(auc - model.metadata["test_auc"]) < 1e-9
    assert confusion_matrix(y, output.default_label).tolist() == [[3234, 1439], [393, 934]]
    print(f"Feature parity: PASS | AUC: {auc:.12f} | Brier: {brier_score_loss(y, output.probability):.12f}")
    large = pd.concat([base] * (10000 // len(base) + 1), ignore_index=True).iloc[:10000]
    start = time.perf_counter()
    model.predict(large, Thresholds(decision=model.threshold))
    print(f"10,000 rows, inference only: {time.perf_counter() - start:.3f} seconds")


if __name__ == "__main__":
    main()
