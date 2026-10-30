import pandas as pd
import pytest

from creditrisk.validation import ValidationError, Thresholds, customer_ids, validate_frame
from creditrisk.service import read_file, export_frame
from creditrisk.features import add_features


@pytest.mark.parametrize(
    "column,value",
    [
        ("AGE", 17),
        ("AGE", 22.5),
        ("SEX", 0),
        ("EDUCATION", 5),
        ("MARRIAGE", 0),
        ("LIMIT_BAL", 0),
        ("PAY_0", 9),
        ("PAY_AMT1", -1),
        ("BILL_AMT1", float("inf")),
        ("AGE", "abc"),
        ("AGE", None),
    ],
)
def test_invalid_values(frame, column, value):
    frame[column] = value
    with pytest.raises(ValidationError):
        validate_frame(frame)


def test_missing_and_duplicate_columns(frame):
    with pytest.raises(ValidationError, match="AGE"):
        validate_frame(frame.drop(columns=["AGE"]))
    with pytest.raises(ValidationError, match="trùng"):
        validate_frame(pd.concat([frame, frame[["AGE"]]], axis=1))


def test_alias_and_negative_bill(frame):
    frame["BILL_AMT1"] = -100
    a = validate_frame(frame)
    b = validate_frame(frame.rename(columns={"PAY_0": "PAY_1"}))
    pd.testing.assert_frame_equal(a, b)
    frame["PAY_1"] = 1
    with pytest.raises(ValidationError):
        validate_frame(frame)


def test_ids(frame):
    with pytest.raises(ValidationError):
        customer_ids(pd.concat([frame, frame]))
    frame["ID"] = " "
    with pytest.raises(ValidationError):
        customer_ids(frame)


@pytest.mark.parametrize("args", [(0.5, 0.6, 0.2), (float("nan"), 0.2, 0.5), (1.1, 0.2, 0.5)])
def test_thresholds(args):
    with pytest.raises(ValidationError):
        Thresholds(*args)


def test_feature_zero_negative_denominators(frame):
    data = validate_frame(frame).rename(columns={"PAY_0": "PAY_1"})
    data["BILL_AMT2"] = -100
    data["PAY_AMT1"] = 200
    out = add_features(data)
    assert len(out.columns) == 38
    assert out.loc[0, "PAY_RATIO_1"] == 1
    assert out.loc[0, "UTILIZATION_2"] == 0
    assert out.loc[0, "DELAY_MONTHS_COUNT"] == 0


@pytest.mark.parametrize("ext", ["csv", "xlsx"])
def test_file_roundtrip(frame, tmp_path, ext):
    frame["ID"] = "00042"
    path = tmp_path / f"source.{ext}"
    export_frame(frame, path)
    result = read_file(path)
    assert result.loc[0, "ID"] == "00042"
    assert len(result.columns) == 24


def test_export_formula_protection(tmp_path):
    path = tmp_path / "result.csv"
    export_frame(pd.DataFrame({"ID": ["=1+1", " @SUM(1)", "safe"]}), path)
    result = pd.read_csv(path)
    assert result["ID"].tolist() == ["'=1+1", "' @SUM(1)", "safe"]


def test_duplicate_raw_header(tmp_path):
    path = tmp_path / "invalid.csv"
    path.write_text("AGE,AGE\n20,21\n")
    with pytest.raises(ValidationError, match="trùng"):
        read_file(path)
