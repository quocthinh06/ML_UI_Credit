"""Exact 15 derived features from the group's 04_use_model notebook."""


def add_features(data):
    data = data.copy()
    for i in range(1, 7):
        data[f"UTILIZATION_{i}"] = (data[f"BILL_AMT{i}"] / data["LIMIT_BAL"]).clip(lower=0)
    for i in range(1, 6):
        denominator = data[f"BILL_AMT{i + 1}"]
        data[f"PAY_RATIO_{i}"] = (
            (data[f"PAY_AMT{i}"] / denominator.where(denominator > 0)).clip(0, 2).fillna(1.0)
        )
    data["DELAY_MONTHS_COUNT"] = (data[[f"PAY_{i}" for i in range(1, 7)]] > 0).sum(axis=1)
    data["MAX_DELAY_MONTHS"] = data[[f"PAY_{i}" for i in range(1, 7)]].max(axis=1)
    data["AVG_BILL_AMT"] = data[[f"BILL_AMT{i}" for i in range(1, 7)]].mean(axis=1)
    data["BILL_TREND"] = data["BILL_AMT1"] - data["AVG_BILL_AMT"]
    return data
