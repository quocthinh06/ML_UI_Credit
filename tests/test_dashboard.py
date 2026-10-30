import pandas as pd
import numpy as np
import pytest

from creditrisk.analytics import summary, evaluation
from creditrisk.validation import TARGET, prepare_input, Thresholds
from creditrisk.charts import DashboardCharts
from creditrisk.inference import load_models
from creditrisk.config import ROOT
from creditrisk.service import read_file, export_frame


def test_raw_uci_normalization_keeps_actual_labels(frame):
    source = pd.concat([frame] * 3, ignore_index=True)
    source["ID"] = ["A", "B", "C"]
    source["EDUCATION"] = [0, 5, 6]
    source["MARRIAGE"] = [0, 1, 2]
    source[TARGET] = [0, 1, None]
    values = prepare_input(source)
    assert values.EDUCATION.tolist() == [4, 4, 4]
    assert values.MARRIAGE.tolist() == [3, 1, 2]
    assert values.source_EDUCATION.tolist() == [0, 5, 6]
    assert summary(values)["actual_default_rate"] == 0.5
    assert summary(values)["labelled"] == 2
    assert source.EDUCATION.tolist() == [0, 5, 6]


def test_missing_invalid_targets_are_not_nondefault(frame):
    source = pd.concat([frame] * 4, ignore_index=True)
    source[TARGET] = [1, None, "invalid", 2]
    assert summary(source)["actual_default_rate"] == 1
    assert summary(source)["labelled"] == 1
    assert summary(frame)["actual_default_rate"] is None


def test_target_persists_through_import_and_revision(service, frame, model):
    frame[TARGET] = 1
    vid = service.import_dataset("Labels", frame)
    rid, result = service.predict_version(vid, model, Thresholds())
    assert result.loc[0, TARGET] == 1
    assert result.loc[0, "decision_basis"] == "raw"
    assert result.loc[0, "model_name"] == model.name
    did = int(service.list_datasets().iloc[0].id)
    changed = frame.iloc[0].drop("ID").to_dict()
    changed["AGE"] = 44
    v2 = service.revise_dataset(did, "KH001", changed, replace=True, expected_version=vid)
    assert service.data(v2).loc[0, TARGET] == 1
    assert service.results(rid).loc[0, "AGE"] == 35


def test_cache_separates_models_thresholds_and_basis(service, frame, model):
    vid = service.import_dataset("Cache", frame)
    r1, _ = service.get_or_predict(vid, model, Thresholds())
    r2, _ = service.get_or_predict(vid, model, Thresholds())
    r3, _ = service.get_or_predict(vid, model, Thresholds(basis="probability"))
    assert r1 == r2 and r3 != r1
    model.digest = "b" * 64
    r4, _ = service.get_or_predict(vid, model, Thresholds())
    assert r4 != r1


def test_delete_last_row_preserves_history_and_can_add_back(service, frame, model):
    vid = service.import_dataset("Delete", frame)
    rid, _ = service.predict_version(vid, model, Thresholds())
    did = int(service.list_datasets().iloc[0].id)
    empty = service.remove_record(did, "KH001", vid)
    assert service.data(empty).empty
    assert len(service.results(rid)) == 1
    back = service.revise_dataset(did, "NEW", frame.iloc[0].drop("ID").to_dict(), expected_version=empty)
    assert service.data(back).ID.tolist() == ["NEW"]


def test_transfer_only_inputs_and_copy_isolation(service, frame, model):
    vid = service.import_dataset("Original", frame)
    service.predict_version(vid, model, Thresholds())
    did = int(service.list_datasets().iloc[0].id)
    new = service.transfer_input(
        did, "NEW", frame.iloc[0].drop("ID").to_dict(), expected_version=vid, copy_name="Copy"
    )
    assert len(service.data(new)) == 2 and len(service.data(vid)) == 1
    assert len(service.history()) == 1


def test_dashboard_modes(qtbot, frame, model):
    d = pd.concat([frame] * 2, ignore_index=True)
    d[TARGET] = [0, 1]
    output = pd.concat([d, model.predict(d, Thresholds())], axis=1)
    panel = DashboardCharts()
    qtbot.addWidget(panel)
    panel.set_data(output, "Test run")
    for mode in range(3):
        panel.mode.setCurrentIndex(mode)
        panel.canvas.draw()
        assert len(panel.figure.axes) == 4
    assert evaluation(output)["labelled_rows"] == 2
    panel.set_data(frame)
    panel.mode.setCurrentIndex(2)
    panel.canvas.draw()
    assert "không có nhãn" in panel.caption.text()


@pytest.mark.skipif(not (ROOT / "models/model_xgb_v1.pkl").exists(), reason="Download the three handoffs")
def test_three_real_models_and_pd_threshold():
    models, errors = load_models(ROOT / "models/best_model_v1.pkl")
    assert not errors
    assert set(models) == {"Random Forest", "Logistic Regression", "XGBoost"}
    values = read_file(ROOT / "examples/sample_customers.csv")
    predictions = []
    for model in models.values():
        result = model.predict(values, Thresholds(decision=0.5, basis="probability"))
        assert np.isfinite(result.probability).all()
        assert result.default_label.tolist() == (result.probability >= 0.5).astype(int).tolist()
        predictions.append(result.probability.to_numpy())
    assert not np.allclose(predictions[0], predictions[1])
    assert not np.allclose(predictions[0], predictions[2])


def test_export_contains_traceable_thresholds(service, frame, model, tmp_path):
    frame[TARGET] = 1
    vid = service.import_dataset("Output", frame)
    _, out = service.predict_version(vid, model, Thresholds(decision=0.5, basis="probability"))
    path = tmp_path / "out.csv"
    export_frame(out, path)
    result = pd.read_csv(path)
    assert {
        "ID",
        "probability",
        "default_label",
        "risk_level",
        "decision_threshold",
        "decision_basis",
        "model_version",
        "prediction_time_utc",
        TARGET,
    }.issubset(result.columns)


def test_portfolio_is_scoped_to_selected_model(service, frame, model):
    vid = service.import_dataset("Scoped", frame)
    service.predict_version(vid, model, Thresholds())
    first_hash = model.digest
    model.digest = "b" * 64
    service.predict_version(vid, model, Thresholds(decision=0.9))
    assert len(service.portfolio(first_hash)) == 1
    assert len(service.portfolio("not-run")) == 1
    assert service.portfolio("not-run").iloc[0]["status"] == "Chưa dự báo"
    assert pd.isna(service.portfolio("not-run").iloc[0].probability)


def test_delete_on_copy_keeps_source(service, frame, model):
    vid = service.import_dataset("Original", frame)
    rid, _ = service.predict_version(vid, model, Thresholds())
    did = int(service.list_datasets().iloc[0].id)
    copy = service.remove_record(did, "KH001", vid, copy_name="Empty copy")
    assert len(service.data(vid)) == 1
    assert service.data(copy).empty
    assert len(service.results(rid)) == 1
    assert len(service.list_datasets()) == 2
