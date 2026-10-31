"""Native PyQt6 views. Database and inference work is always queued to a worker."""

from pathlib import Path

import pandas as pd
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon
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
from .inference import load_models
from .charts import DashboardCharts
from .analytics import evaluation
from .qt_workers import Task
from .service import CreditService, export_filename, export_frame, read_file
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
    view.setShowGrid(False)
    view.verticalHeader().setDefaultSectionSize(44)
    view.horizontalHeader().setMinimumHeight(44)
    view.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    view.setTextElideMode(Qt.TextElideMode.ElideRight)
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
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPalette, QColor

        palette = QPalette()
        for role, color in {
            QPalette.ColorRole.Window: "#f7f8fc",
            QPalette.ColorRole.WindowText: "#182338",
            QPalette.ColorRole.Base: "#ffffff",
            QPalette.ColorRole.AlternateBase: "#f4f7fc",
            QPalette.ColorRole.Text: "#182338",
            QPalette.ColorRole.Button: "#f7f8fc",
            QPalette.ColorRole.ButtonText: "#182338",
            QPalette.ColorRole.Highlight: "#2460e8",
            QPalette.ColorRole.HighlightedText: "#ffffff",
            QPalette.ColorRole.ToolTipBase: "#ffffff",
            QPalette.ColorRole.ToolTipText: "#182338",
            QPalette.ColorRole.PlaceholderText: "#64748b",
        }.items():
            palette.setColor(role, QColor(color))
        QApplication.instance().setPalette(palette)
        self.setPalette(palette)
        self.service, self.model = service, model
        self.models = {model.name: model} if model else {}
        self.active_batch_version = None
        self.showing_history = False
        self.task = None
        self.preview = None
        self.source = pd.DataFrame()
        self.displayed = pd.DataFrame()
        self.selected_version = None
        self.setWindowTitle("CreditRisk AI · Nhóm 4 · Dashboard")
        self.resize(1440, 940)
        self.setMinimumSize(1050, 720)
        self.setStyleSheet(
            (ROOT / "creditrisk/style.qss").read_text(encoding="utf-8").replace(
                "__ASSETS__", (ROOT / "creditrisk/assets").as_posix()
            )
        )
        shell = QWidget()
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(224)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(14, 26, 14, 20)
        nav.setSpacing(8)
        brand = QHBoxLayout()
        mark = QLabel()
        mark.setObjectName("brandMark")
        mark.setPixmap(QIcon(str(ROOT / "creditrisk/assets/shield.svg")).pixmap(28, 28))
        mark.setFixedSize(42, 42)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(mark)
        brand.addWidget(label("CreditRisk AI", "brand"))
        nav.addLayout(brand)
        nav.addWidget(label("Quản lý rủi ro tín dụng", "navCaption"))
        nav.addSpacing(24)
        self.nav_buttons = []
        self.stack = QStackedWidget()
        for i, title in enumerate(
            ["Tổng quan", "Quản lý dữ liệu", "Dự báo rủi ro", "Kết quả && Lịch sử", "Hiệu năng mô hình"]
        ):
            item = button(title, lambda checked=False, index=i: self.navigate(index))
            icon = ["overview", "database", "predict", "history", "performance"][i]
            item.setIcon(QIcon(str(ROOT / f"creditrisk/assets/{icon}.svg")))
            item.setIconSize(QSize(20, 20))
            item.setCheckable(True)
            item.setMinimumHeight(46)
            nav.addWidget(item)
            self.nav_buttons.append(item)
        nav.addStretch()
        footer = QFrame()
        footer.setObjectName("sidebarNote")
        footer_layout = QVBoxLayout(footer)
        footer_layout.addWidget(label("Mô hình UCI · 23 trường", "navCaption"))
        footer_layout.addWidget(label("Kết quả hỗ trợ theo dõi rủi ro.\nQuyết định thuộc chuyên viên."))
        nav.addWidget(footer)
        root.addWidget(sidebar)
        content = QWidget()
        content.setObjectName("content")
        main = QVBoxLayout(content)
        main.setContentsMargins(24, 16, 24, 16)
        main.setSpacing(12)
        topbar = QFrame()
        topbar.setObjectName("topbar")
        top = QHBoxLayout(topbar)
        top.setContentsMargins(16, 12, 16, 12)
        top.setSpacing(16)
        self.connection = label("Chưa kết nối MySQL", "subtitle")
        if service:
            self.connection.setText("Cơ sở dữ liệu đã kết nối · thời gian lưu UTC")
        self.connection.setObjectName("connectionBadge")
        top.addWidget(self.connection, 1)
        self.model_choice = QComboBox()
        self.model_choice.setMinimumWidth(180)
        self.model_choice.currentIndexChanged.connect(self.switch_model)
        top.addWidget(self.model_choice)
        self.connect_button = button("Kết nối / tải lại", self.connect_backend, True)
        top.addWidget(self.connect_button)
        main.addWidget(topbar)
        self.model_info = label("Chưa nạp mô hình", "subtitle")
        main.addWidget(self.model_info)
        self.build_dashboard()
        self.build_data_page()
        self.build_prediction_page()
        self.build_history_page()
        self.build_model_page()
        main.addWidget(self.stack, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        main.addWidget(self.progress)
        root.addWidget(content, 1)
        self.setCentralWidget(shell)
        self.navigate(0)
        if model:
            self.model_choice.addItem(model.name)
            self.show_model()
        if auto_connect:
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, self.connect_backend)

    def page(self, title, description):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(14)
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
        self.model_choice.setEnabled(False)
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
        self.model_choice.setEnabled(True)
        self.progress.hide()
        self.statusBar().showMessage("Sẵn sàng", 4000)
        task.deleteLater()
        followup = getattr(self, "after_task", None)
        self.after_task = None
        if followup:
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, followup)

    def show_error(self, message):
        QMessageBox.warning(self, "Không thể hoàn tất", str(message))

    def connect_backend(self):
        def connect():
            config = load_config()
            engine = database_engine(config)
            try:
                initialize(engine)
                service = CreditService(engine)
            except Exception:
                engine.dispose()
                raise
            models, model_error = {}, None
            try:
                models, errors = load_models(ROOT / config["model_path"])
                model_error = "\n".join(errors) or None
            except Exception as exc:
                model_error = str(exc)
            default = next(iter(models.values()), None)
            snapshot = (
                service.list_datasets(),
                service.history(),
                service.portfolio(getattr(default, "digest", None)),
            )
            return service, models, model_error, snapshot

        def connected(result):
            old = self.service
            self.service, self.models, model_error, snapshot = result
            self.model = next(iter(self.models.values()), None)
            self.model_choice.blockSignals(True)
            self.model_choice.clear()
            self.model_choice.addItems(list(self.models))
            self.model_choice.blockSignals(False)
            if old:
                old.engine.dispose()
            self.connection.setText("MySQL đã kết nối · Thời gian lưu UTC")
            self.show_model()
            self.apply_snapshot(snapshot)
            self.invalidate_preview()
            self.update_model_metrics()
            if model_error:
                self.show_error(model_error)
            if self.model and self.dashboard_choice.count():
                self.after_task = self.load_dashboard

        self.execute(connect, connected, "Đang kết nối MySQL và nạp mô hình…")

    def show_model(self):
        if self.model:
            self.model_info.setText(
                f"{self.model.name} · {self.model.version} · τ điểm thô trong notebook = {self.model.threshold:.2f} · PD đã hiệu chỉnh"
            )
            metrics = getattr(self.model, "metadata", {})
            if "cv_auc" in metrics and "test_auc" in metrics:
                self.model_info.setText(
                    self.model_info.text()
                    + f" · CV AUC {metrics['cv_auc']:.4f} · Test AUC {metrics['test_auc']:.4f}"
                )
            if self.decision_basis.currentData() == "raw":
                self.decision.setValue(self.model.threshold * 100)
        else:
            self.model_info.setText("Chưa có mô hình · Có thể quản lý dữ liệu; chưa thể dự báo")

    def snapshot(self, service):
        return (
            service.list_datasets(),
            service.history(),
            service.portfolio(getattr(self.model, "digest", None)),
        )

    def refresh(self):
        if self.service:
            self.execute(lambda: self.snapshot(self.service), self.apply_snapshot)

    def apply_snapshot(self, snapshot):
        data, history, portfolio = snapshot
        self.datasets_view.model().set_frame(data)
        self.history_view.model().set_frame(history)
        self.portfolio_view.model().set_frame(portfolio)
        previous = self.dataset_choice.currentData()
        previous_dashboard = self.dashboard_choice.currentData()
        self.dataset_choice.blockSignals(True)
        self.dataset_choice.clear()
        self.dashboard_choice.clear()
        self.save_destination.clear()
        self.save_destination.addItem("Tạo tệp đơn lẻ mới", None)
        for row in data.to_dict("records"):
            self.dataset_choice.addItem(f"{row['name']} · v{row['revision']}", int(row["version_id"]))
            self.dashboard_choice.addItem(f"{row['name']} · v{row['revision']}", int(row["version_id"]))
            self.save_destination.addItem(
                f"{row['name']} · v{row['revision']}", (int(row["id"]), int(row["version_id"]))
            )
        if previous is not None and self.dataset_choice.findData(previous) >= 0:
            self.dataset_choice.setCurrentIndex(self.dataset_choice.findData(previous))
        if previous_dashboard is not None and self.dashboard_choice.findData(previous_dashboard) >= 0:
            self.dashboard_choice.setCurrentIndex(self.dashboard_choice.findData(previous_dashboard))
        self.dataset_choice.blockSignals(False)
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
            "Tổng quan rủi ro tín dụng",
            "Chọn tệp và mô hình để xem biểu đồ từ kết quả thực; nhãn thực tế được thống kê riêng.",
        )
        toolbar = QHBoxLayout()
        toolbar.addWidget(button("Tải CSV / Excel và dự báo", self.import_file))
        self.dashboard_choice = QComboBox()
        toolbar.addWidget(self.dashboard_choice, 1)
        toolbar.addWidget(button("Phân tích tệp đã chọn", self.load_dashboard, True))
        layout.addLayout(toolbar)
        metrics = QHBoxLayout()
        self.metrics = []
        metrics.setSpacing(14)
        for title, tone in [
            ("Hồ sơ danh mục", "primary"), ("Rủi ro cao", "danger"),
            ("Cần dự báo lại", "warning"), ("Tệp đã lưu", "teal"),
        ]:
            group = QFrame()
            group.setObjectName("metricCard")
            group.setProperty("tone", tone)
            box = QVBoxLayout(group)
            box.setContentsMargins(18, 16, 18, 16)
            box.addWidget(label(title, "metricCaption"))
            value = label("0", "metric")
            self.metrics.append(value)
            box.addWidget(value)
            metrics.addWidget(group)
        layout.addLayout(metrics)
        self.distribution = label("Chưa có kết quả.", "subtitle")
        layout.addWidget(self.distribution)
        tabs = QTabWidget()
        self.charts = DashboardCharts()
        self.charts.setMinimumHeight(500)
        charts_area = QScrollArea()
        charts_area.setWidgetResizable(True)
        charts_area.setWidget(self.charts)
        tabs.addTab(charts_area, "Dashboard của tệp đã chọn")
        status_page = QWidget()
        status_layout = QVBoxLayout(status_page)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Tất cả trạng thái", "Đã dự báo", "Chưa dự báo", "Cần dự báo lại"])
        self.status_filter.currentIndexChanged.connect(self.filter_portfolio)
        status_layout.addWidget(self.status_filter)
        self.portfolio_view = table()
        status_layout.addWidget(self.portfolio_view, 1)
        status_layout.addWidget(button("Tải lại danh mục", self.refresh, True))
        tabs.addTab(status_page, "Trạng thái toàn danh mục")
        layout.addWidget(tabs, 1)

    def load_dashboard(self):
        vid = self.dashboard_choice.currentData()
        if vid is None:
            self.show_error("Tải tệp dữ liệu trước khi phân tích.")
            return
        self.dataset_choice.setCurrentIndex(self.dataset_choice.findData(vid))
        self.predict_batch()

    def filter_portfolio(self, *_):
        frame = getattr(self, "portfolio", pd.DataFrame())
        if not frame.empty and self.status_filter.currentIndex():
            frame = frame[frame["status"] == self.status_filter.currentText()]
        self.portfolio_view.model().set_frame(frame)

    def build_data_page(self):
        layout = self.page(
            "Quản lý dữ liệu", "Nhập CSV/Excel; mỗi lần cập nhật tạo phiên bản mới và giữ nguyên lịch sử."
        )
        actions = QGridLayout()
        actions.setSpacing(10)
        for i, (text, callback, secondary) in enumerate([
            ("Nhập CSV / Excel", self.import_file, False),
            ("Xem tệp đã chọn", self.open_dataset, True),
            ("Bổ sung / cập nhật hồ sơ", self.edit_dataset, True),
            ("Lưu thành bản mới", self.clone_dataset, True),
            ("Xuất dữ liệu đang xem", self.export_data, True),
            ("Xóa dòng đã chọn", self.delete_record, True),
        ]):
            action = button(text, callback, secondary)
            if callback == self.delete_record:
                action.setProperty("danger", True)
                action.setToolTip("Xóa khỏi phiên bản mới; giữ nguyên lịch sử.")
            actions.addWidget(action, i // 3, i % 3)
        layout.addLayout(actions)
        self.datasets_view = table()
        self.datasets_view.setMinimumHeight(120)
        self.datasets_view.doubleClicked.connect(self.open_dataset)
        layout.addWidget(self.datasets_view, 1)
        self.data_note = label("Chọn tệp để xem dữ liệu.", "subtitle")
        layout.addWidget(self.data_note)
        self.version_choice = QComboBox()
        self.version_choice.setPlaceholderText("Chọn phiên bản để xem hoặc lưu thành bản mới")
        self.version_choice.activated.connect(self.open_version)
        layout.addWidget(self.version_choice)
        self.data_view = table()
        self.data_view.setMinimumHeight(140)
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
        if not self.model:
            self.show_error("Nạp mô hình trước khi tải tệp và dự báo.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn tệp khách hàng", "", "Dữ liệu (*.csv *.xlsx *.json)"
        )
        if not path:
            return

        try:
            thresholds = self.thresholds()
        except ValueError as exc:
            self.show_error(str(exc))
            return

        def work():
            frame = read_file(path)
            vid = self.service.import_dataset(Path(path).name, frame)
            run = self.service.get_or_predict(vid, self.model, thresholds)
            return vid, frame, run, self.snapshot(self.service)

        def done(result):
            vid, frame, run, snapshot = result
            self.source = frame
            self.selected_version = vid
            self.data_view.model().set_frame(frame)
            self.apply_snapshot(snapshot)
            self.dataset_choice.setCurrentIndex(self.dataset_choice.findData(vid))
            self.dashboard_choice.setCurrentIndex(self.dashboard_choice.findData(vid))
            self.active_batch_version = vid
            self.showing_history = False
            changes = frame.attrs.get("normalization", {})
            info = ", ".join(f"{k}: {v} giá trị" for k, v in changes.items() if v)
            self.data_note.setText(
                f"Đã kiểm tra, dự báo và lưu {len(frame):,} hồ sơ. Chuẩn hóa theo notebook: {info or 'không cần'}."
            )
            self.set_results(
                run[1],
                f"{Path(path).name} · {self.model.name} · lần chạy #{run[0]} · {self.data_note.text()}",
            )
            self.navigate(2)
            self.tabs.setCurrentIndex(1)

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
        edit_mode = QComboBox()
        edit_mode.addItems(
            ["Cập nhật dataset hiện tại · giữ bản cũ trong lịch sử", "Tạo bản sao rồi chỉnh sửa"]
        )
        copy_name = QLineEdit()
        copy_name.setPlaceholderText("Tên bản sao (chỉ dùng khi chọn tạo bản sao)")
        layout.addWidget(edit_mode)
        layout.addWidget(copy_name)
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
                if edit_mode.currentIndex() and not copy_name.text().strip():
                    raise ValueError("Nhập tên dataset bản sao.")
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
                        self.service.transfer_input(
                            int(row["id"]),
                            cid,
                            values,
                            replace=duplicate,
                            expected_version=int(row["version_id"]),
                            copy_name=copy_name.text().strip() if edit_mode.currentIndex() else None,
                        ),
                        self.snapshot(self.service),
                    ),
                    self.dataset_mutated,
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
            self, "Xuất dữ liệu", export_filename(self.model.name if self.model else None),
            "Excel (*.xlsx);;CSV (*.csv)"
        )
        if path:
            snapshot = frame.copy()
            model, thresholds = self.model, self.thresholds()
            self.execute(
                lambda: export_frame(snapshot, path, model=model, thresholds=thresholds),
                lambda _: QMessageBox.information(self, "Đã xuất", "Đã lưu tệp thành công."),
            )

    def build_prediction_page(self):
        layout = self.page(
            "Dự báo nguy cơ vỡ nợ", "Xác suất PD đã hiệu chỉnh và nhãn cảnh báo hỗ trợ chuyên viên theo dõi."
        )
        self.decision_basis = QComboBox()
        self.decision_basis.addItem("Ngưỡng nhãn trên PD hiệu chỉnh (BRD)", "probability")
        self.decision_basis.addItem("Ngưỡng điểm thô (notebook mô hình)", "raw")
        self.decision_basis.currentIndexChanged.connect(self.change_basis)
        layout.addWidget(self.decision_basis)
        settings = QHBoxLayout()
        self.decision, self.low, self.high = [QDoubleSpinBox() for _ in range(3)]
        for title, field, value in [
            ("Ngưỡng quyết định nhãn", self.decision, 50),
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
        result_group.setObjectName("resultPanel")
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
        transfer = button("Chuyển đầu vào sang dataset", self.transfer_single, True)
        transfer.setToolTip("Chuyển riêng dữ liệu đầu vào sang dataset hàng loạt đã chọn.")
        result.addWidget(transfer)
        result.addWidget(button("Giải thích kết quả", self.explain_single, True))
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
        result_group.setMinimumHeight(690)
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
        self.dataset_choice.currentIndexChanged.connect(self.invalidate_batch)
        controls.addWidget(self.dataset_choice, 1)
        controls.addWidget(button("Chạy dự báo & lưu", self.predict_batch))
        controls.addWidget(button("Tải file & dự báo", self.import_file, True))
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
        advanced = QGridLayout()
        self.max_probability = QDoubleSpinBox()
        self.max_probability.setRange(0, 100)
        self.max_probability.setValue(100)
        self.max_probability.setSuffix(" %")
        self.min_age, self.max_age = QDoubleSpinBox(), QDoubleSpinBox()
        for item in (self.min_age, self.max_age):
            item.setRange(18, 100)
            item.setDecimals(0)
        self.max_age.setValue(100)
        self.min_limit, self.max_limit = QDoubleSpinBox(), QDoubleSpinBox()
        for item in (self.min_limit, self.max_limit):
            item.setRange(0, 10000000)
            item.setDecimals(0)
        self.max_limit.setValue(10000000)
        self.warning_filter = QComboBox()
        self.warning_filter.addItems(["Tất cả nhãn", "Nhãn 0", "Nhãn 1"])
        self.delay_filter = QDoubleSpinBox()
        self.delay_filter.setRange(-2, 8)
        self.delay_filter.setValue(-2)
        self.delay_filter.setDecimals(0)
        for i, (title, item) in enumerate(
            [
                ("PD tối đa", self.max_probability),
                ("Tuổi từ", self.min_age),
                ("Tuổi đến", self.max_age),
                ("Hạn mức từ (TWD)", self.min_limit),
                ("Hạn mức đến", self.max_limit),
                ("PAY_0 tối thiểu", self.delay_filter),
            ]
        ):
            advanced.addWidget(label(title), i // 3 * 2, i % 3)
            advanced.addWidget(item, i // 3 * 2 + 1, i % 3)
            item.valueChanged.connect(self.filter_results)
        advanced.addWidget(self.warning_filter, 4, 0, 1, 3)
        self.warning_filter.currentIndexChanged.connect(self.filter_results)
        batch_layout.addLayout(advanced)
        self.results_note = label("Chưa có kết quả hàng loạt.", "subtitle")
        batch_layout.addWidget(self.results_note)
        self.results_view = table()
        batch_layout.addWidget(self.results_view, 1)
        batch.setMinimumHeight(600)
        batch_area = QScrollArea()
        batch_area.setWidgetResizable(True)
        batch_area.setWidget(batch)
        self.tabs.addTab(batch_area, "Hàng loạt CSV / Excel")
        self.batch_result = pd.DataFrame()

    def thresholds(self):
        return Thresholds(
            self.decision.value() / 100,
            self.low.value() / 100,
            self.high.value() / 100,
            self.decision_basis.currentData(),
        )

    def change_basis(self):
        if not hasattr(self, "decision"):
            return
        self.decision.setValue(
            self.model.threshold * 100 if self.decision_basis.currentData() == "raw" and self.model else 50
        )
        self.invalidate_preview()
        self.invalidate_batch()

    def invalidate_batch(self, *_):
        self.active_batch_version = None
        if hasattr(self, "results_view"):
            self.batch_result = pd.DataFrame()
            self.displayed = pd.DataFrame()
            self.results_view.model().set_frame(self.displayed)
            self.results_note.setText(
                "Dữ liệu, mô hình hoặc ngưỡng đã đổi. Cần chạy dự báo với cấu hình hiện tại."
            )
            self.charts.set_data(pd.DataFrame(), "Chưa có kết quả phù hợp cấu hình hiện tại")

    def invalidate_preview(self, *_):
        self.preview = None
        if hasattr(self, "save_button"):
            self.save_button.setEnabled(False)
            self.result_label.setText("Chưa dự báo")
            self.result_detail.setText("Nhập hoặc thay đổi dữ liệu cần chạy dự báo trước khi lưu.")
        # Editing the single form does not change batch inputs; only shared settings do.
        if self.sender() in [
            getattr(self, "decision", None),
            getattr(self, "low", None),
            getattr(self, "high", None),
            getattr(self, "decision_basis", None),
        ]:
            self.invalidate_batch()

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
                for key, value in {
                    "model_name": self.model.name,
                    "model_version": self.model.version,
                    "model_sha256": self.model.digest,
                    "decision_threshold": thresholds.decision,
                    "decision_basis": thresholds.basis,
                    "risk_low_threshold": thresholds.low,
                    "risk_high_threshold": thresholds.high,
                }.items():
                    output[key] = value
                self.preview = (values.assign(ID=cid), output, thresholds)
                row = result.iloc[0]
                self.result_label.setText(f"{row['probability']:.2%}")
                self.result_label.setStyleSheet(
                    "color: " + {"Low": "#087f83", "Medium": "#986000", "High": "#b91c1c"}[row["risk_level"]]
                )
                self.result_detail.setText(
                    f"{self.model.name} · PD đã hiệu chỉnh · {row['risk_level']}\n\nĐiểm thô: {row['raw_score']:.4f}\nNgưỡng nhãn: {thresholds.decision:.4f} ({thresholds.basis})\nNhãn cảnh báo: {row['default_label']}\n\nChưa lưu vào MySQL."
                )
                self.save_button.setEnabled(self.service is not None)

            self.execute(lambda: self.model.predict(values, thresholds), done, "Đang dự báo hồ sơ…")
        except ValueError as exc:
            self.show_error(str(exc))

    def save_single(self):
        if not self.preview or not self.service:
            return
        values, output, thresholds = self.preview
        # The transfer action handles the chosen batch destination separately (BR-14).
        target = None
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

    def predict_batch(self, version_id=None):
        if not self.service or not self.model:
            self.show_error("Cần kết nối MySQL và nạp mô hình trước khi dự báo.")
            return
        vid = (
            self.dataset_choice.currentData()
            if version_id is None or isinstance(version_id, bool)
            else version_id
        )
        if vid is None:
            self.show_error("Nhập tệp tại Quản lý dữ liệu trước.")
            return
        try:
            thresholds = self.thresholds()
        except ValueError as exc:
            self.show_error(str(exc))
            return

        def work():
            result = self.service.get_or_predict(vid, self.model, thresholds)
            return result, self.snapshot(self.service)

        def done(result):
            (rid, frame), snapshot = result
            self.set_results(
                frame,
                f"{self.model.name} · dữ liệu v#{vid} · lần chạy #{rid} · Đã lưu MySQL · {len(frame):,} hồ sơ · ngưỡng {thresholds.decision:.2f} ({thresholds.basis})",
            )
            self.apply_snapshot(snapshot)
            self.active_batch_version = vid
            self.showing_history = False
            self.dashboard_choice.setCurrentIndex(self.dashboard_choice.findData(vid))

        self.execute(work, done, "Đang dự báo và lưu kết quả hàng loạt…")

    def set_results(self, frame, text):
        self.batch_result = frame.drop(columns=["record_id"], errors="ignore")
        self.results_note.setText(text)
        self.charts.set_data(frame, text)
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
            result = result[result.probability <= self.max_probability.value() / 100]
            result = result[result.AGE.between(self.min_age.value(), self.max_age.value())]
            result = result[result.LIMIT_BAL.between(self.min_limit.value(), self.max_limit.value())]
            result = result[result.PAY_0 >= self.delay_filter.value()]
            if self.warning_filter.currentIndex():
                result = result[result.default_label == self.warning_filter.currentIndex() - 1]
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
            self.showing_history = True
            self.active_batch_version = int(row["version_id"])
            self.search.clear()
            self.risk_filter.setCurrentIndex(0)
            self.min_probability.setValue(0)
            self.set_results(
                frame, f"Lịch sử #{row['run_id']} · {row['model_version']} · Ngưỡng {row['thresholds']}"
            )
            self.navigate(2)
            self.tabs.setCurrentIndex(1)

        self.execute(lambda: self.service.results(int(row["run_id"])), done)

    def switch_model(self, *_):
        name = self.model_choice.currentText()
        if name not in self.models or self.models[name] is self.model:
            return
        had_preview = self.preview is not None
        active = self.active_batch_version
        self.model = self.models[name]
        self.invalidate_preview()
        self.invalidate_batch()
        self.show_model()
        self.update_model_metrics()
        from PyQt6.QtCore import QTimer

        if had_preview and self.tabs.currentIndex() == 0:
            QTimer.singleShot(0, self.predict_single)
        elif active is not None:
            self.dataset_choice.blockSignals(True)
            self.dataset_choice.setCurrentIndex(self.dataset_choice.findData(active))
            self.dataset_choice.blockSignals(False)
            QTimer.singleShot(0, lambda: self.predict_batch(active))

    def build_model_page(self):
        layout = self.page(
            "Hiệu năng mô hình",
            "Random Forest mặc định được chọn theo CV AUC của bộ bàn giao; không chọn lại bằng nhãn file vừa tải.",
        )
        layout.addWidget(
            label(
                "Bảng đầu là chỉ số CV/test gốc lưu trong bundle. Đánh giá file tải lên được trình bày riêng; nếu file gồm dữ liệu huấn luyện, chỉ số đó không đại diện cho kiểm thử độc lập.",
                "subtitle",
            )
        )
        self.model_metrics = table()
        self.model_metrics.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.model_metrics)
        layout.addWidget(button("So sánh 3 mô hình trên tệp hàng loạt đang chọn", self.compare_models))
        self.comparison_view = table()
        layout.addWidget(self.comparison_view, 1)

    def update_model_metrics(self):
        rows = []
        for name, model in self.models.items():
            meta = getattr(model, "metadata", {})
            rows.append(
                {
                    "Mô hình": name,
                    "CV AUC gốc": meta.get("cv_auc"),
                    "Test AUC gốc": meta.get("test_auc"),
                    "Ngưỡng điểm thô notebook": model.threshold,
                    "Phiên bản": model.version,
                }
            )
        self.model_metrics.model().set_frame(pd.DataFrame(rows))

    def compare_models(self):
        vid = self.dataset_choice.currentData()
        if vid is None or not self.service:
            self.show_error("Chọn dataset hàng loạt trước khi so sánh.")
            return
        try:
            thresholds = self.thresholds()
        except ValueError as exc:
            self.show_error(str(exc))
            return

        def work():
            rows = []
            for name, model in self.models.items():
                rid, frame = self.service.get_or_predict(vid, model, thresholds)
                rows.append(
                    {
                        "model": name,
                        "run_id": rid,
                        "decision_basis": thresholds.basis,
                        "decision_threshold": thresholds.decision,
                        **evaluation(frame),
                    }
                )
            return pd.DataFrame(rows), self.snapshot(self.service)

        def done(result):
            self.comparison_view.model().set_frame(result[0])
            self.apply_snapshot(result[1])

        self.execute(work, done, "Đang chạy đúng từng mô hình trên cùng dữ liệu…")

    def explain_single(self):
        if not self.preview or not self.model:
            self.show_error("Chạy dự báo đơn lẻ trước khi xem giải thích.")
            return
        values = self.preview[0].copy()

        def done(frame):
            frame = (
                frame.assign(magnitude=frame.contribution.abs())
                .sort_values("magnitude", ascending=False)
                .head(12)
                .drop(columns="magnitude")
            )
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Giải thích · {self.model.name}")
            dialog.resize(820, 580)
            layout = QVBoxLayout(dialog)
            layout.addWidget(
                label(
                    "Đóng góp vào điểm thô/log-odds của mô hình, không phải phần trăm PD sau hiệu chỉnh. Dấu dương tăng điểm; dấu âm giảm điểm."
                )
            )
            view = table()
            view.model().set_frame(frame)
            layout.addWidget(view)
            dialog.exec()

        self.execute(lambda: self.model.explain(values), done, "Đang tính đóng góp đặc trưng thực…")

    def dataset_mutated(self, result):
        self.apply_snapshot(result[1])
        self.source = pd.DataFrame()
        self.selected_version = None
        self.data_view.model().set_frame(pd.DataFrame())
        self.data_note.setText(
            "Đã tạo phiên bản thay đổi. Chọn tệp và bấm Xem để tải dữ liệu mới; kết quả cũ vẫn giữ trong lịch sử."
        )
        self.invalidate_batch()

    def delete_record(self):
        row = self.selected(self.datasets_view)
        if row is None:
            return
        record = self.selected(self.data_view)
        if record is None:
            return
        if self.selected_version != int(row["version_id"]):
            self.show_error("Mở phiên bản hiện tại trước khi xóa dòng.")
            return
        from PyQt6.QtWidgets import QInputDialog

        mode, ok = QInputDialog.getItem(
            self,
            "Chọn phạm vi xóa",
            "Cách xử lý:",
            ["Xóa khỏi dataset hiện tại (giữ lịch sử)", "Tạo bản sao rồi xóa"],
            0,
            False,
        )
        if not ok:
            return
        copy_name = None
        if mode.startswith("Tạo"):
            copy_name, ok = QInputDialog.getText(self, "Tên bản sao", "Tên dataset mới:")
            if not ok or not copy_name.strip():
                return
        if (
            QMessageBox.question(
                self,
                "Xóa dòng khỏi dataset",
                f"Xóa ID {record['ID']} khỏi bản làm việc?\nBản trước và lịch sử dự báo được giữ nguyên.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.execute(
            lambda: (
                self.service.remove_record(
                    int(row["id"]), str(record["ID"]), self.selected_version, copy_name
                ),
                self.snapshot(self.service),
            ),
            self.dataset_mutated,
        )

    def transfer_single(self):
        target = self.save_destination.currentData()
        if target is None or not self.service:
            self.show_error("Chọn tệp nhận đầu vào ở danh sách Lưu kết quả vào.")
            return
        try:
            values = self.form.values().iloc[0].to_dict()
            cid = self.form.customer_id.text().strip()
            if not cid:
                raise ValueError("Nhập ID khách hàng.")
        except ValueError as exc:
            self.show_error(str(exc))
            return
        from PyQt6.QtWidgets import QInputDialog

        mode, ok = QInputDialog.getItem(
            self,
            "Chuyển đầu vào hàng loạt",
            "Cách lưu:",
            ["Thêm/cập nhật dataset hiện tại", "Tạo bản sao rồi thêm"],
            0,
            False,
        )
        if not ok:
            return
        copy_name = None
        if mode.startswith("Tạo"):
            copy_name, ok = QInputDialog.getText(self, "Tên bản sao", "Tên dataset mới:")
            if not ok or not copy_name.strip():
                return
        if (
            QMessageBox.question(
                self,
                "Xác nhận chuyển đầu vào",
                f"Chuyển ID {cid}; nếu trùng ID sẽ cập nhật sau xác nhận này.\nChỉ chuyển đầu vào, không gán kết quả đơn lẻ cho hàng loạt. Bản cũ vẫn được giữ.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.execute(
            lambda: (
                self.service.transfer_input(
                    target[0], cid, values, expected_version=target[1], replace=True, copy_name=copy_name
                ),
                self.snapshot(self.service),
            ),
            self.dataset_mutated,
        )

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
