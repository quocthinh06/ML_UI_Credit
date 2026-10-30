import pandas as pd
import pytest
from sqlalchemy import select, func

from creditrisk.database import datasets, runs
from creditrisk.validation import Thresholds, ValidationError


def test_revisions_keep_history_and_mark_stale(service, frame, model):
    vid = service.import_dataset("Customers", frame)
    run1, result = service.predict_version(vid, model, Thresholds())
    run2, _ = service.predict_version(vid, model, Thresholds(decision=0.7))
    assert service.portfolio().shape[0] == 1
    assert service.results(run1).loc[0, "default_label"] == 1
    assert service.results(run2).loc[0, "default_label"] == 0
    did = int(service.list_datasets().iloc[0]["id"])
    new = frame.iloc[0].drop("ID").to_dict()
    new["AGE"] = 40
    with pytest.raises(ValidationError, match="ID"):
        service.revise_dataset(did, "KH001", new)
    newvid = service.revise_dataset(did, "KH001", new, replace=True, expected_version=vid)
    assert newvid != vid
    assert service.data(vid).loc[0, "AGE"] == 35
    assert service.data(newvid).loc[0, "AGE"] == 40
    assert service.portfolio().loc[0, "status"] == "Cần dự báo lại"
    assert len(service.history()) == 2
    assert len(service.results(run1)) == 1
    with pytest.raises(ValidationError, match="phiên bản mới"):
        service.revise_dataset(did, "KH001", new, replace=True, expected_version=vid)


def test_import_validation_is_atomic(service, frame):
    frame.loc[0, "AGE"] = 3
    with pytest.raises(ValidationError):
        service.import_dataset("Bad", frame)
    assert service.list_datasets().empty


def test_predict_failure_does_not_create_run(service, frame):
    class Broken:
        def predict(self, *_):
            raise ValueError("failed")

    vid = service.import_dataset("File", frame)
    with pytest.raises(ValueError):
        service.predict_version(vid, Broken(), Thresholds())
    assert service.history().empty
    assert service.portfolio().loc[0, "status"] == "Chưa dự báo"


def test_append_and_clone(service, frame):
    vid = service.import_dataset("Original", frame)
    did = int(service.list_datasets().iloc[0]["id"])
    v2 = service.revise_dataset(did, "KH002", frame.iloc[0].drop("ID").to_dict())
    cloned = service.import_dataset("Copy", service.data(v2))
    assert len(service.data(vid)) == 1
    assert len(service.data(v2)) == len(service.data(cloned)) == 2


def test_single_saved_atomically(service, frame, model):
    thresholds = Thresholds()
    result = model.predict(frame, thresholds)
    output = pd.concat([frame, result], axis=1)
    rid = service.save_single(frame, output, model, thresholds)
    assert service.results(rid).loc[0, "probability"] == 0.25
    assert service.history().loc[0, "model_hash"] == "a" * 64
    with service.engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(datasets)) == 1
        assert conn.scalar(select(func.count()).select_from(runs)) == 1


def test_single_append_existing_dataset(service, frame, model):
    vid = service.import_dataset("Original", frame)
    did = int(service.list_datasets().iloc[0]["id"])
    new = frame.copy()
    new["ID"] = "NEW"
    result = pd.concat([new, model.predict(new, Thresholds())], axis=1)
    rid = service.save_single(new, result, model, Thresholds(), dataset_id=did, expected_version=vid)
    assert service.results(rid).loc[0, "ID"] == "NEW"
    assert len(service.data(vid)) == 1
    latest = int(service.list_datasets().iloc[0]["version_id"])
    assert len(service.data(latest)) == 2
    assert service.portfolio()["status"].tolist() == ["Cần dự báo lại", "Đã dự báo"]
