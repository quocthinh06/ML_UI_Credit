from PyQt6.QtWidgets import QMessageBox

from creditrisk.ui import MainWindow


def test_prediction_edit_invalidates_and_save(qtbot, service, model, frame, monkeypatch):
    window = MainWindow(service, model, auto_connect=False)
    qtbot.addWidget(window)
    window.show()
    window.navigate(2)
    window.form.set_values(frame.iloc[0].to_dict())
    window.predict_single()
    qtbot.waitUntil(lambda: window.task is None, timeout=10000)
    assert "25.00%" in window.result_label.text()
    assert window.save_button.isEnabled()
    window.form.fields["AGE"].setText("40")
    assert window.preview is None
    assert not window.save_button.isEnabled()
    window.predict_single()
    qtbot.waitUntil(lambda: window.task is None, timeout=10000)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    window.save_single()
    qtbot.waitUntil(lambda: window.task is None, timeout=10000)
    assert len(service.history()) == 1
    assert not window.save_button.isEnabled()


def test_batch_filter_and_history(qtbot, service, model, frame):
    service.import_dataset("Test", frame)
    window = MainWindow(service, model, auto_connect=False)
    qtbot.addWidget(window)
    window.apply_snapshot(window.snapshot(service))
    window.predict_batch()
    qtbot.waitUntil(lambda: window.task is None, timeout=10000)
    assert len(window.displayed) == 1
    window.risk_filter.setCurrentText("High")
    assert window.displayed.empty
    window.risk_filter.setCurrentIndex(0)
    window.search.setText("kh001")
    assert len(window.displayed) == 1
    window.min_probability.setValue(30)
    assert window.displayed.empty


def test_worker_error_recovers_controls(qtbot, service, model, monkeypatch):
    window = MainWindow(service, model, auto_connect=False)
    qtbot.addWidget(window)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))

    def broken():
        raise ValueError("invalid input")

    window.execute(broken, lambda _: None)
    qtbot.waitUntil(lambda: window.task is None, timeout=10000)
    assert messages and "invalid input" in messages[0]
    assert window.stack.isEnabled()


def test_upload_shows_output_and_dashboard(qtbot, service, model, frame, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog
    from creditrisk.validation import TARGET

    source = tmp_path / "upload.csv"
    frame[TARGET] = 1
    frame.to_csv(source, index=False)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(source), ""))
    window = MainWindow(service, model, auto_connect=False)
    qtbot.addWidget(window)
    window.import_file()
    qtbot.waitUntil(lambda: window.task is None, timeout=10000)
    assert len(window.batch_result) == 1
    assert window.batch_result.iloc[0][TARGET] == 1
    assert len(window.charts.frame) == 1
    assert window.tabs.currentIndex() == 1 and window.stack.currentIndex() == 2
    assert window.active_batch_version is not None


def test_model_switch_recomputes_instead_of_relabelling(qtbot, service, model, frame):
    import pandas as pd

    class OtherModel:
        name, version, digest, threshold = "Other", "v2", "b" * 64, 0.4

        def predict(self, frame, thresholds):
            return pd.DataFrame(
                [dict(raw_score=0.9, probability=0.8, default_label=1, risk_level="High")] * len(frame)
            )

    service.import_dataset("Customers", frame)
    window = MainWindow(service, model, auto_connect=False)
    qtbot.addWidget(window)
    window.apply_snapshot(window.snapshot(service))
    window.predict_batch()
    qtbot.waitUntil(lambda: window.task is None, timeout=10000)
    original = window.batch_result.probability.iloc[0]
    other = OtherModel()
    window.models[other.name] = other
    window.model_choice.addItem(other.name)
    window.model_choice.setCurrentText(other.name)
    qtbot.waitUntil(
        lambda: not window.batch_result.empty and window.batch_result.probability.iloc[0] == 0.8,
        timeout=10000,
    )
    qtbot.waitUntil(lambda: window.task is None, timeout=10000)
    assert original == 0.25
    assert len(service.history()) == 2
    assert window.batch_result.model_name.iloc[0] == "Other"
    window.high.setValue(90)
    assert window.batch_result.empty
