import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from sqlalchemy import create_engine

from creditrisk.database import initialize
from creditrisk.service import CreditService
from creditrisk.validation import FEATURES, PAY_COLUMNS


@pytest.fixture
def profile():
    values = {c: 0.0 for c in FEATURES}
    values.update(LIMIT_BAL=200000, SEX=2, EDUCATION=2, MARRIAGE=1, AGE=35)
    values.update({c: -1 for c in PAY_COLUMNS})
    return values


@pytest.fixture
def frame(profile):
    return pd.DataFrame([dict(ID="KH001", **profile)])


@pytest.fixture
def service(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    initialize(engine)
    yield CreditService(engine)
    engine.dispose()


class TestModel:
    name, version, digest, threshold = "test only", "test-v1", "a" * 64, 0.39

    def predict(self, frame, thresholds):
        return pd.DataFrame(
            [
                dict(
                    raw_score=0.6,
                    probability=0.25,
                    default_label=int(0.6 >= thresholds.decision),
                    risk_level="Medium",
                )
            ]
            * len(frame)
        )


@pytest.fixture
def model():
    return TestModel()
