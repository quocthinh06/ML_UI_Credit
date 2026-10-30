"""Native PyQt6 views. Database and inference work is always queued to a worker."""

from pathlib import Path

import pandas as pd
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .config import ROOT, database_engine, load_config
from .database import initialize
from .inference import ModelRunner
from .qt_workers import Task
from .service import CreditService, export_frame, read_file
from .table_model import DataFrameModel
from .validation import FEATURES, PAY_COLUMNS, Thresholds, validate_frame


def button(text, callback, secondary=False):
    widget = QPushButton(text)
    widget.setProperty("secondary", secondary)
    widget.clicked.connect(callback)
    return widget


def label(text, name=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    if name:
        widget.setObjectName(name)
    return widget


def table():
    view = QTableView()
    view.setModel(DataFrameModel())
    view.setAlternatingRowColors(True)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setSortingEnabled(False)
    view.verticalHeader().setVisible(False)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    view.horizontalHeader().setDefaultSectionSize(150)
    view.setMinimumHeight(180)
    return view


class ProfileForm(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("profileForm")
        self.fields = {}
        layout = QVBoxLayout(self)
        self.customer_id = QLineEdit()
        self.customer_id.setPlaceholderText("Nhập mã khách hàng để lưu hồ sơ")
        layout.addWidget(label("Mã khách hàng (ID)"))
        layout.addWidget(self.customer_id)
        groups = [
            ("Thông tin khách hàng · đơn vị tiền tệ TWD", FEATURES[:5]),
            ("Trạng thái thanh toán 6 tháng · −2 đến 8", PAY_COLUMNS),
            ("Dư nợ sao kê 6 tháng · TWD", [f"BILL_AMT{i}" for i in range(1, 7)]),
            ("Tiền thanh toán 6 tháng · TWD", [f"PAY_AMT{i}" for i in range(1, 7)]),
        ]
        for title, columns in groups:
            group = QGroupBox(title)
            grid = QGridLayout(group)
            for i, col in enumerate(columns):
                field = QLineEdit()
                field.setPlaceholderText(col)
                field.setAccessibleName(col)
                grid.addWidget(label(col), i // 2 * 2, i % 2)
                grid.addWidget(field, i // 2 * 2 + 1, i % 2)
                self.fields[col] = field
            layout.addWidget(group)
        layout.addWidget(
            label(
                "SEX: 1 nam, 2 nữ · EDUCATION: 1 sau ĐH, 2 ĐH, 3 THPT, 4 khác\nMARRIAGE: 1 đã kết hôn, 2 độc thân, 3 khác · PAY_0 là tháng gần nhất (PAY_1 trong mô hình).",
                "subtitle",
            )
        )

    def values(self):
        return validate_frame(pd.DataFrame([{c: f.text().strip() for c, f in self.fields.items()}]))

    def set_values(self, record):
        self.customer_id.setText(str(record.get("ID", "")))
        for key, field in self.fields.items():
            field.setText(str(record.get(key, "")))


class MainWindow(QMainWindow):
    def __init__(self, service=None, model=None, auto_connect=True):
        super().__init__()
        self.service, self.model = service, model
        self.task = None
        self.preview = None
        self.source = pd.DataFrame()
        self.displayed = pd.DataFrame()
        self.selected_version = None
        self.setWindowTitle("CreditRisk AI · Nhóm 4")
        self.resize(1440, 940)
        self.setMinimumSize(1050, 720)
        self.setStyleSheet((ROOT / "creditrisk/style.qss").read_text(encoding="utf-8"))
        shell = QWidget()
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(218)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(18, 28, 18, 24)
        nav.addWidget(label("CreditRisk AI", "brand"))
        nav.addWidget(label("QUẢN LÝ RỦI RO TÍN DỤNG"))
        nav.addSpacing(32)
        self.nav_buttons = []
        self.stack = QStackedWidget()
        for i, title in enumerate(["Tổng quan", "Quản lý dữ liệu", "Dự báo rủi ro", "Kết quả & Lịch sử"]):
            item = button(title, lambda checked=False, index=i: self.navigate(index))
            item.setCheckable(True)
            nav.addWidget(item)
            self.nav_buttons.append(item)
        nav.addStretch()
        nav.addWidget(
            label("Mô hình UCI · 23 trường\nKết quả hỗ trợ theo dõi rủi ro.\nQuyết định thuộc chuyên viên.")
        )
        root.addWidget(sidebar)
        content = QWidget()
        content.setObjectName("content")
        main = QVBoxLayout(content)
        main.setContentsMargins(28, 20, 28, 20)
        top = QHBoxLayout()
        self.connection = label("Chưa kết nối MySQL", "subtitle")
        top.addWidget(self.connection)
        top.addStretch()
        self.connect_button = button("Kết nối / tải lại", self.connect_backend, True)
        top.addWidget(self.connect_button)
        main.addLayout(top)
        self.model_info = label("Chưa nạp mô hình", "subtitle")
        main.addWidget(self.model_info)
        self.build_dashboard()
        self.build_data_page()
        self.build_prediction_page()
        self.build_history_page()
        main.addWidget(self.stack, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        main.addWidget(self.progress)
        root.addWidget(content, 1)
        self.setCentralWidget(shell)
        self.navigate(0)
        if model:
            self.show_model()
        if auto_connect:
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, self.connect_backend)

    def page(self, title, description):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(description, "subtitle"))
        self.stack.addWidget(page)
        return layout

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i, item in enumerate(self.nav_buttons):
            item.setChecked(i == index)

    def execute(self, function, callback, message="Đang xử lý…"):
        if self.task is not None:
            return
        self.stack.setEnabled(False)
        self.connect_button.setEnabled(False)
        self.progress.show()
        self.statusBar().showMessage(message)
        task = Task(function, self)
        self.task = task
        task.succeeded.connect(callback)
        task.failed.connect(self.show_error)
        task.finished.connect(self.task_finished)
        task.start()

    def task_finished(self):
        task = self.task
        self.task = None
        self.stack.setEnabled(True)
        self.connect_button.setEnabled(True)
        self.progress.hide()
        self.statusBar().showMessage("Sẵn sàng", 4000)
        task.deleteLater()

    def show_error(self, message):
        QMessageBox.warning(self, "Không thể hoàn tất", str(message))

    def connect_backend(self):
        def connect():
            config = load_config()
            engine = database_engine(config)
            try:
                initialize(engine)
                service = CreditService(engine)
                snapshot = self.snapshot(service)
            except Exception:
                engine.dispose()
                raise
            model, model_error = None, None
            try:
                model = ModelRunner(ROOT / config["model_path"])
            except Exception as exc:
                model_error = str(exc)
            return service, model, model_error, snapshot

        def connected(result):
            old = self.service
            self.service, self.model, model_error, snapshot = result
            if old:
                old.engine.dispose()
            self.connection.setText("MySQL đã kết nối · Thời gian lưu UTC")
            self.show_model()
            self.apply_snapshot(snapshot)
            self.invalidate_preview()
            if model_error:
                self.show_error(model_error)

        self.execute(connect, connected, "Đang kết nối MySQL và nạp mô hình…")

    def show_model(self):
        if self.model:
            self.model_info.setText(
                f"{self.model.name} · {self.model.version} · điểm thô τ = {self.model.threshold:.2f} · PD đã hiệu chỉnh"
            )
            metrics = getattr(self.model, "metadata", {})
            if "cv_auc" in metrics and "test_auc" in metrics:
                self.model_info.setText(
                    self.model_info.text()
                    + f" · CV AUC {metrics['cv_auc']:.4f} · Test AUC {metrics['test_auc']:.4f}"
                )
            self.decision.setValue(self.model.threshold * 100)
        else:
            self.model_info.setText("Chưa có mô hình · Có thể quản lý dữ liệu; chưa thể dự báo")

    @staticmethod
    def snapshot(service):
        return service.list_datasets(), service.history(), service.portfolio()

    def refresh(self):
        if self.service:
            self.execute(lambda: self.snapshot(self.service), self.apply_snapshot)

    def apply_snapshot(self, snapshot):
        data, history, portfolio = snapshot
        self.datasets_view.model().set_frame(data)
        self.history_view.model().set_frame(history)
        self.portfolio_view.model().set_frame(portfolio)
        self.dataset_choice.clear()
        self.save_destination.clear()
        self.save_destination.addItem("Tạo tệp đơn lẻ mới", None)
        for row in data.to_dict("records"):
            self.dataset_choice.addItem(f"{row['name']} · v{row['revision']}", int(row["version_id"]))
            self.save_destination.addItem(
                f"{row['name']} · v{row['revision']}", (int(row["id"]), int(row["version_id"]))
            )
        values = [
            len(portfolio),
            int((portfolio.get("risk_level", pd.Series(dtype=str)) == "High").sum()),
            int((portfolio.get("status", pd.Series(dtype=str)) == "Cần dự báo lại").sum()),
            len(data),
        ]
        for widget, value in zip(self.metrics, values):
            widget.setText(f"{value:,}")
        self.distribution.setText(
            "  ·  ".join(
                f"{title}: {int((portfolio.get('risk_level', pd.Series(dtype=str)) == key).sum()):,}"
                for key, title in [("Low", "Thấp"), ("Medium", "Trung bình"), ("High", "Cao")]
            )
        )
        self.portfolio = portfolio
        self.filter_portfolio()
        self.refresh_required = False

    def build_dashboard(self):
        layout = self.page(
            "Tổng quan rủi ro tín dụng", "Danh mục hiện tại, không cộng trùng các lần dự báo lịch sử."
        )
        toolbar = QHBoxLayout()
        toolbar.addWidget(button("Tạo dự báo mới", lambda: self.navigate(2)))
        toolbar.addWidget(button("Tải lại số liệu", self.refresh, True))
        toolbar.addStretch()
        layout.addLayout(toolbar)
        metrics = QHBoxLayout()
        self.metrics = []
        for title in ["Tổng hồ sơ hiện tại", "Hồ sơ rủi ro cao", "Cần dự báo lại", "Tệp dữ liệu đã lưu"]:
            group = QGroupBox(title)
            box = QVBoxLayout(group)
            value = label("0", "metric")
            self.metrics.append(value)
            box.addWidget(value)
            metrics.addWidget(group)
        layout.addLayout(metrics)
        group = QGroupBox("Phân bố mức rủi ro theo xác suất đã hiệu chỉnh")
        group_layout = QVBoxLayout(group)
        self.distribution = label("Chưa có kết quả. Nhập tệp hoặc tạo dự báo để bắt đầu.")
        group_layout.addWidget(self.distribution)
        group_layout.addWidget(
            label(
                "Ngưỡng phân nhóm được lưu theo từng lần chạy. Nhãn cảnh báo được tính riêng từ điểm thô.",
                "subtitle",
            )
        )
        layout.addWidget(group)
        filters = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Tất cả trạng thái", "Đã dự báo", "Chưa dự báo", "Cần dự báo lại"])
        self.status_filter.currentIndexChanged.connect(self.filter_portfolio)
        filters.addWidget(label("Trạng thái hồ sơ"))
        filters.addWidget(self.status_filter)
        filters.addStretch()
        layout.addLayout(filters)
        self.portfolio_view = table()
        layout.addWidget(self.portfolio_view, 1)

    def filter_portfolio(self, *_):
        frame = getattr(self, "portfolio", pd.DataFrame())
        if not frame.empty and self.status_filter.currentIndex():
            frame = frame[frame["status"] == self.status_filter.currentText()]
        self.portfolio_view.model().set_frame(frame)

    def build_data_page(self):
        layout = self.page(
            "Quản lý dữ liệu", "Nhập CSV/Excel; mỗi lần cập nhật tạo phiên bản mới và giữ nguyên lịch sử."
        )
        actions = QHBoxLayout()
        actions.addWidget(button("Nhập CSV / Excel", self.import_file))
        actions.addWidget(button("Xem tệp đã chọn", self.open_dataset, True))
        actions.addWidget(button("Bổ sung / cập nhật hồ sơ", self.edit_dataset, True))
        actions.addWidget(button("Lưu thành bản mới", self.clone_dataset, True))
        actions.addWidget(button("Xuất dữ liệu đang xem", self.export_data, True))
        layout.addLayout(actions)
        self.datasets_view = table()
        self.datasets_view.doubleClicked.connect(self.open_dataset)
        layout.addWidget(self.datasets_view, 1)
        self.data_note = label("Chọn tệp để xem dữ liệu.", "subtitle")
        layout.addWidget(self.data_note)
        self.version_choice = QComboBox()
        self.version_choice.setPlaceholderText("Chọn phiên bản để xem hoặc lưu thành bản mới")
        self.version_choice.activated.connect(self.open_version)
        layout.addWidget(self.version_choice)
        self.data_view = table()
        layout.addWidget(self.data_view, 2)

    def selected(self, view):
        rows = view.selectionModel().selectedRows()
        if not rows:
            self.show_error("Hãy chọn một dòng trong bảng trước.")
            return None
        return view.model().frame.iloc[rows[0].row()].to_dict()

    def import_file(self):
        if not self.service:
            self.show_error("Hãy kết nối MySQL trước khi nhập tệp.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Chọn tệp khách hàng", "", "Dữ liệu (*.csv *.xlsx)")
        if not path:
            return

        def work():
            frame = read_file(path)
            vid = self.service.import_dataset(Path(path).name, frame)
            return vid, frame, self.snapshot(self.service)

        def done(result):
            vid, frame, snapshot = result
            self.source = frame
            self.selected_version = vid
            self.data_view.model().set_frame(frame)
            self.apply_snapshot(snapshot)
            self.dataset_choice.setCurrentIndex(self.dataset_choice.findData(vid))
            self.data_note.setText(
                f"Đã kiểm tra và lưu {len(frame):,} hồ sơ. Có thể chuyển sang Dự báo hàng loạt."
            )

        self.execute(work, done, "Đang kiểm tra cấu trúc và lưu tệp…")

    def open_dataset(self, *_):
        row = self.selected(self.datasets_view)
        if row is None:
            return
        vid = int(row["version_id"])

        def done(frame):
            frame, history = frame
            self.source = frame
            self.selected_version = vid
            self.data_view.model().set_frame(frame.drop(columns=["record_id"], errors="ignore"))
            self.data_note.setText(f"{row['name']} · Phiên bản {row['revision']} · {len(frame):,} hồ sơ")
            self.version_choice.clear()
            for version in history.to_dict("records"):
                self.version_choice.addItem(
                    f"Phiên bản {version['revision']} · {version['created_at']} UTC", int(version["id"])
                )

        self.execute(lambda: (self.service.data(vid), self.service.version_history(int(row["id"]))), done)

    def open_version(self, *_):
        vid = self.version_choice.currentData()
        if vid is None:
            return

        def done(frame):
            self.source = frame
            self.selected_version = vid
            self.data_view.model().set_frame(frame.drop(columns=["record_id"], errors="ignore"))
            self.data_note.setText(
                "Đang xem "
                + self.version_choice.currentText()
                + ". Dùng 'Lưu thành bản mới' để khôi phục thành tệp riêng."
            )

        self.execute(lambda: self.service.data(vid), done)

    def edit_dataset(self):
        row = self.selected(self.datasets_view)
        if row is None:
            return
        if self.selected_version != int(row["version_id"]):
            self.show_error("Bấm 'Xem tệp đã chọn' trước khi bổ sung hoặc sửa hồ sơ.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Bổ sung / cập nhật hồ sơ")
        dialog.resize(680, 800)
        layout = QVBoxLayout(dialog)
        form = ProfileForm()
        selected = self.data_view.selectionModel().selectedRows()
        if selected:
            form.set_values(self.data_view.model().frame.iloc[selected[0].row()].to_dict())
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setWidget(form)
        layout.addWidget(area)
        controls = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        controls.rejected.connect(dialog.reject)

        def save():
            try:
                values = form.values().iloc[0].to_dict()
                cid = form.customer_id.text().strip()
                if not cid:
                    raise ValueError("Nhập ID khách hàng.")
                duplicate = cid in self.source["ID"].astype(str).tolist()
                text = "ID đã tồn tại. Cập nhật hồ sơ này?" if duplicate else "Thêm hồ sơ vào phiên bản mới?"
                if (
                    QMessageBox.question(
                        dialog, "Xác nhận lưu", text + "\nKết quả cũ được giữ; phiên bản mới cần dự báo lại."
                    )
                    != QMessageBox.StandardButton.Yes
                ):
                    return
                dialog.accept()
                self.execute(
                    lambda: (
                        self.service.revise_dataset(
                            int(row["id"]),
                            cid,
                            values,
                            replace=duplicate,
                            expected_version=int(row["version_id"]),
                        ),
                        self.snapshot(self.service),
                    ),
                    lambda result: self.apply_snapshot(result[1]),
                )
            except ValueError as exc:
                self.show_error(str(exc))

        controls.accepted.connect(save)
        layout.addWidget(controls)
        dialog.exec()

    def clone_dataset(self):
        if self.source.empty:
            self.show_error("Mở tệp trước khi lưu thành bản mới.")
            return
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Tên bản mới", "Tên tệp dữ liệu:")
        if ok and name.strip():
            source = self.source.copy()
            self.execute(
                lambda: (self.service.import_dataset(name, source), self.snapshot(self.service)),
                lambda result: self.apply_snapshot(result[1]),
            )

    def export_data(self):
        self.export(self.data_view.model().frame)

    def export(self, frame):
        if frame.empty:
            self.show_error("Chưa có dữ liệu để xuất.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất dữ liệu", "ket_qua.csv", "CSV (*.csv);;Excel (*.xlsx)"
        )
        if path:
            snapshot = frame.copy()
            self.execute(
                lambda: export_frame(snapshot, path),
                lambda _: QMessageBox.information(self, "Đã xuất", "Đã lưu tệp thành công."),
            )

    def build_prediction_page(self):
        layout = self.page(
            "Dự báo nguy cơ vỡ nợ", "Xác suất PD đã hiệu chỉnh và nhãn cảnh báo hỗ trợ chuyên viên theo dõi."
        )
        settings = QHBoxLayout()
        self.decision, self.low, self.high = [QDoubleSpinBox() for _ in range(3)]
        for title, field, value in [
            ("Ngưỡng nhãn · điểm thô", self.decision, 39),
            ("Ngưỡng PD thấp", self.low, 20),
            ("Ngưỡng PD cao", self.high, 50),
        ]:
            field.setRange(0, 100)
            field.setDecimals(2)
            field.setSuffix(" %")
            field.setValue(value)
            field.valueChanged.connect(self.invalidate_preview)
            settings.addWidget(label(title))
            settings.addWidget(field)
        layout.addLayout(settings)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        single = QWidget()
        body = QHBoxLayout(single)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.form = ProfileForm()
        for field in [self.form.customer_id, *self.form.fields.values()]:
            field.textChanged.connect(self.invalidate_preview)
        scroll.setWidget(self.form)
        body.addWidget(scroll, 3)
        result_group = QGroupBox("Kết quả dự báo đơn lẻ")
        result = QVBoxLayout(result_group)
        self.result_label = label("Chưa dự báo", "result")
        result.addWidget(self.result_label)
        self.result_detail = label(
            "Nhập đủ 23 trường để chạy dự báo.\nKhông tự thay thế dữ liệu thiếu.", "subtitle"
        )
        self.result_detail.setMinimumHeight(150)
        result.addWidget(self.result_detail)
        result.addStretch()
        result.addWidget(button("Chạy dự báo", self.predict_single))
        result.addWidget(label("Lưu kết quả vào:"))
        self.save_destination = QComboBox()
        self.save_destination.addItem("Tạo tệp đơn lẻ mới", None)
        result.addWidget(self.save_destination)
        self.save_button = button("Lưu kết quả vào MySQL", self.save_single)
        self.save_button.setEnabled(False)
        result.addWidget(self.save_button)
        result.addWidget(
            button(
                "Xuất kết quả đơn lẻ",
                lambda: self.export(self.preview[1] if self.preview else pd.DataFrame()),
                True,
            )
        )
        result.addWidget(
            label("Nhãn 1 là cảnh báo rủi ro. Hệ thống không tự phê duyệt hoặc từ chối tín dụng.", "subtitle")
        )
        result_group.setMinimumHeight(610)
        result_scroll = QScrollArea()
        result_scroll.setWidgetResizable(True)
        result_scroll.setWidget(result_group)
        body.addWidget(result_scroll, 2)
        self.tabs.addTab(single, "Một hồ sơ đơn lẻ")
        batch = QWidget()
        batch_layout = QVBoxLayout(batch)
        batch_layout.addWidget(
            label(
                "1. Nhập tệp tại Quản lý dữ liệu   →   2. Chọn tệp đã kiểm tra   →   3. Chạy và lưu kết quả"
            )
        )
        controls = QHBoxLayout()
        self.dataset_choice = QComboBox()
        controls.addWidget(self.dataset_choice, 1)
        controls.addWidget(button("Chạy dự báo & lưu", self.predict_batch))
        controls.addWidget(button("Xuất kết quả đã lọc", lambda: self.export(self.displayed), True))
        batch_layout.addLayout(controls)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm ID khách hàng…")
        self.risk_filter = QComboBox()
        self.risk_filter.addItems(["Tất cả mức rủi ro", "Low", "Medium", "High"])
        self.min_probability = QDoubleSpinBox()
        self.min_probability.setRange(0, 100)
        self.min_probability.setSuffix(" %")
        filters.addWidget(self.search, 1)
        filters.addWidget(self.risk_filter)
        filters.addWidget(label("PD tối thiểu"))
        filters.addWidget(self.min_probability)
        self.search.textChanged.connect(self.filter_results)
        self.risk_filter.currentIndexChanged.connect(self.filter_results)
        self.min_probability.valueChanged.connect(self.filter_results)
        batch_layout.addLayout(filters)
        self.results_note = label("Chưa có kết quả hàng loạt.", "subtitle")
        batch_layout.addWidget(self.results_note)
        self.results_view = table()
        batch_layout.addWidget(self.results_view, 1)
        self.tabs.addTab(batch, "Hàng loạt CSV / Excel")
        self.batch_result = pd.DataFrame()

    def thresholds(self):
        return Thresholds(self.decision.value() / 100, self.low.value() / 100, self.high.value() / 100)

    def invalidate_preview(self, *_):
        self.preview = None
        if hasattr(self, "save_button"):
            self.save_button.setEnabled(False)
            self.result_label.setText("Chưa dự báo")
            self.result_detail.setText("Nhập hoặc thay đổi dữ liệu cần chạy dự báo trước khi lưu.")

    def predict_single(self):
        try:
            if not self.model:
                raise ValueError("Chưa nạp được mô hình. Kiểm tra file cấu hình và bộ bàn giao.")
            values, thresholds = self.form.values(), self.thresholds()
            cid = self.form.customer_id.text().strip()
            if not cid or len(cid) > 128:
                raise ValueError("ID cần từ 1 đến 128 ký tự.")

            def done(result):
                output = pd.concat([values, result], axis=1)
                output.insert(0, "ID", cid)
                self.preview = (values.assign(ID=cid), output, thresholds)
                row = result.iloc[0]
                self.result_label.setText(f"{row['probability']:.2%}")
                self.result_label.setStyleSheet(
                    "color: " + {"Low": "#087f83", "Medium": "#986000", "High": "#b91c1c"}[row["risk_level"]]
                )
                self.result_detail.setText(
                    f"PD đã hiệu chỉnh · {row['risk_level']}\n\nĐiểm thô: {row['raw_score']:.4f}\nNgưỡng điểm thô: {thresholds.decision:.4f}\nNhãn cảnh báo: {row['default_label']}\n\nChưa lưu vào MySQL."
                )
                self.save_button.setEnabled(self.service is not None)

            self.execute(lambda: self.model.predict(values, thresholds), done, "Đang dự báo hồ sơ…")
        except ValueError as exc:
            self.show_error(str(exc))

    def save_single(self):
        if not self.preview or not self.service:
            return
        values, output, thresholds = self.preview
        target = self.save_destination.currentData()
        text = (
            "Lưu vào tệp đơn lẻ mới?"
            if target is None
            else "Lưu vào phiên bản mới của tệp đã chọn? Nếu trùng ID, hồ sơ đó sẽ được cập nhật.\nCác hồ sơ khác trong phiên bản mới cần dự báo lại; lịch sử được giữ nguyên."
        )
        if QMessageBox.question(self, "Xác nhận lưu / cập nhật ID", text) != QMessageBox.StandardButton.Yes:
            return

        def work():
            options = (
                {} if target is None else dict(dataset_id=target[0], expected_version=target[1], replace=True)
            )
            rid = self.service.save_single(values, output, self.model, thresholds, **options)
            return rid, self.snapshot(self.service)

        def done(result):
            self.apply_snapshot(result[1])
            self.save_button.setEnabled(False)
            self.result_detail.setText(
                self.result_detail.text().replace(
                    "Chưa lưu vào MySQL.", f"Đã lưu vào MySQL · Lần chạy #{result[0]}"
                )
            )

        self.execute(work, done)

    def predict_batch(self):
        if not self.service or not self.model:
            self.show_error("Cần kết nối MySQL và nạp mô hình trước khi dự báo.")
            return
        vid = self.dataset_choice.currentData()
        if vid is None:
            self.show_error("Nhập tệp tại Quản lý dữ liệu trước.")
            return
        try:
            thresholds = self.thresholds()
        except ValueError as exc:
            self.show_error(str(exc))
            return

        def work():
            result = self.service.predict_version(vid, self.model, thresholds)
            return result, self.snapshot(self.service)

        def done(result):
            (rid, frame), snapshot = result
            self.set_results(
                frame,
                f"Lần chạy #{rid} · Đã lưu MySQL · {len(frame):,} hồ sơ · τ = {thresholds.decision:.2f}",
            )
            self.apply_snapshot(snapshot)

        self.execute(work, done, "Đang dự báo và lưu kết quả hàng loạt…")

    def set_results(self, frame, text):
        self.batch_result = frame.drop(columns=["record_id"], errors="ignore")
        self.results_note.setText(text)
        self.filter_results()

    def filter_results(self, *_):
        result = self.batch_result
        if not result.empty:
            result = result[
                result["ID"].astype(str).str.contains(self.search.text(), case=False, regex=False)
            ]
            if self.risk_filter.currentIndex():
                result = result[result["risk_level"] == self.risk_filter.currentText()]
            result = result[result["probability"] >= self.min_probability.value() / 100]
            order = ["ID", "probability", "raw_score", "default_label", "risk_level"]
            result = result[order + [c for c in result.columns if c not in order]]
        self.displayed = result.copy()
        self.results_view.model().set_frame(result)

    def build_history_page(self):
        layout = self.page(
            "Kết quả & Lịch sử",
            "Mỗi lần chạy lưu phiên bản dữ liệu, SHA256 mô hình, thời điểm UTC và toàn bộ ngưỡng.",
        )
        actions = QHBoxLayout()
        actions.addWidget(button("Xem kết quả lần chạy", self.open_history))
        actions.addWidget(button("Tải lại", self.refresh, True))
        actions.addStretch()
        layout.addLayout(actions)
        self.history_view = table()
        self.history_view.doubleClicked.connect(self.open_history)
        layout.addWidget(self.history_view, 1)

    def open_history(self, *_):
        row = self.selected(self.history_view)
        if row is None:
            return

        def done(frame):
            self.search.clear()
            self.risk_filter.setCurrentIndex(0)
            self.min_probability.setValue(0)
            self.set_results(
                frame, f"Lịch sử #{row['run_id']} · {row['model_version']} · Ngưỡng {row['thresholds']}"
            )
            self.navigate(2)
            self.tabs.setCurrentIndex(1)

        self.execute(lambda: self.service.results(int(row["run_id"])), done)

    def closeEvent(self, event):
        if self.task is not None:
            QMessageBox.information(
                self, "Đang xử lý", "Đợi thao tác hoàn tất trước khi đóng để bảo toàn dữ liệu."
            )
            event.ignore()
            return
        if self.service:
            self.service.engine.dispose()
        event.accept()
