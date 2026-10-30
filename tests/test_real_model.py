import numpy as np
import pytest

from creditrisk.config import ROOT
from creditrisk.inference import ModelRunner, ModelUnavailable
from creditrisk.service import read_file
from creditrisk.validation import Thresholds


def test_missing_model_is_explicit(tmp_path):
    with pytest.raises(ModelUnavailable, match="mô hình"):
        ModelRunner(tmp_path / "missing.pkl")


@pytest.mark.skipif(not (ROOT / "models/best_model_v1.pkl").exists(), reason="Run tools/download_model.py")
def test_original_notebook_acceptance():
    model = ModelRunner(ROOT / "models/best_model_v1.pkl")
    values = read_file(ROOT / "examples/sample_customers.csv")
    result = model.predict(values, Thresholds(decision=model.threshold))
    assert np.allclose(result.raw_score, [0.108104, 0.504844, 0.793079], atol=0.000005)
    assert np.allclose(result.probability, [0.040737, 0.254076, 0.599673], atol=0.000005)
    assert result.default_label.tolist() == [0, 1, 1]
    assert result.risk_level.tolist() == ["Low", "Medium", "High"]
