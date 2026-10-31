import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QColor


class DataFrameModel(QAbstractTableModel):
    def __init__(self, frame=None, parent=None):
        super().__init__(parent)
        self.frame = frame if frame is not None else pd.DataFrame()

    def set_frame(self, frame):
        self.beginResetModel()
        self.frame = frame.copy()
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.frame) if parent is None or not parent.isValid() else 0

    def columnCount(self, parent=None):
        return len(self.frame.columns) if parent is None or not parent.isValid() else 0

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self.frame.iat[index.row(), index.column()]
        column = self.frame.columns[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, float):
                if pd.isna(value):
                    return ""
                if column in ("probability", "raw_score"):
                    return f"{value:.2%}"
                if (
                    column in ("AGE", "SEX", "EDUCATION", "MARRIAGE")
                    or column.startswith("PAY_")
                    and "AMT" not in column
                ):
                    return f"{value:.0f}"
                if "AUC" in column or column in (
                    "Accuracy",
                    "Precision",
                    "Recall",
                    "F1",
                    "Brier_PD",
                    "contribution",
                ):
                    return f"{value:.4f}"
                return f"{value:,.2f}"
            return str(value)
        if role == Qt.ItemDataRole.ForegroundRole and column == "risk_level":
            return QColor(
                {"Low": "#087f83", "Medium": "#986000", "High": "#b91c1c"}.get(str(value), "#182338")
            )
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                name = str(self.frame.columns[section])
                return {
                    "id": "Mã tệp",
                    "name": "Tên tệp dữ liệu",
                    "created_at": "Thời điểm tạo (UTC)",
                    "revision": "Phiên bản dữ liệu",
                    "version_id": "Mã phiên bản",
                    "run_id": "Mã lần dự báo",
                    "model_name": "Mô hình",
                    "model_version": "Phiên bản mô hình",
                    "thresholds": "Cấu hình ngưỡng",
                    "updated_at_utc": "Cập nhật (UTC)",
                    "probability": "PD đã hiệu chỉnh",
                    "raw_score": "Điểm thô",
                    "default_label": "Cảnh báo (0/1)",
                    "risk_level": "Mức rủi ro",
                    "record_count": "Số hồ sơ",
                    "processing_status": "Trạng thái xử lý",
                }.get(name, name)
            return str(section + 1)
        return None
