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
