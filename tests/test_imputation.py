import pandas as pd
import pytest

from creditrisk.imputation import prepare_missing
from creditrisk.validation import TARGET, ValidationError


def test_training_statistics_fill_only_missing_values(frame):
    frame.loc[0, ["AGE", "SEX", "PAY_AMT6"]] = None
    frame[TARGET] = None
    result, report = prepare_missing(frame)
    assert result.loc[0, "AGE"] == 34
    assert result.loc[0, "SEX"] == 2
    assert result.loc[0, "PAY_AMT6"] == 1500
    assert pd.isna(result.loc[0, TARGET])
    assert set(report["rows"][0]["fields"]) == {"AGE", "SEX", "PAY_AMT6"}
    assert report["filled_rows"] == 1


@pytest.mark.parametrize("field", ["LIMIT_BAL", "PAY_0", "PAY_6", "BILL_AMT6", "PAY_AMT5"])
def test_core_feature_dependencies_cannot_be_imputed(frame, field):
    frame.loc[0, field] = None
    with pytest.raises(ValidationError, match=field):
        prepare_missing(frame)


def test_all_five_supplementary_columns_can_be_absent(frame):
    result, report = prepare_missing(frame.drop(columns=["SEX", "EDUCATION", "MARRIAGE", "AGE", "PAY_AMT6"]))
    assert result.loc[0, "AGE"] == 34
    assert report["filled_cells"] == 5


def test_missing_columns_use_alias_but_invalid_values_are_rejected(frame):
    frame = frame.drop(columns=["AGE", "PAY_0"])
    frame["PAY_1"] = -1
    result, _ = prepare_missing(frame)
    assert result.loc[0, "PAY_0"] == -1
    frame["SEX"] = "unknown"
    with pytest.raises(ValidationError):
        prepare_missing(frame)


def test_alias_conflicts_and_duplicate_ids_are_not_silently_fixed(frame):
    frame["PAY_1"] = -1
    with pytest.raises(ValidationError):
        prepare_missing(frame)
    with pytest.raises(ValidationError):
        prepare_missing(pd.concat([frame.drop(columns="PAY_1")] * 2))


@pytest.mark.parametrize(("name", "value"), [("AGE", 17), ("SEX", 5), ("PAY_AMT6", -1), ("AGE", float("inf"))])
def test_invalid_present_values_are_not_replaced(frame, name, value):
    frame.loc[0, name] = value
    with pytest.raises(ValidationError):
        prepare_missing(frame)


def test_unverified_statistics_are_rejected_before_loading(tmp_path, monkeypatch):
    from creditrisk import imputation

    (tmp_path / "models").mkdir()
    (tmp_path / "models/impute_stats_v1.pkl").write_bytes(b"untrusted")
    monkeypatch.setattr(imputation, "ROOT", tmp_path)
    imputation.training_defaults.cache_clear()
    with pytest.raises(ValidationError, match="thống kê"):
        imputation.training_defaults()
    imputation.training_defaults.cache_clear()
