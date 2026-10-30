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
                return f"{value:.2%}" if column in ("probability", "raw_score") else f"{value:,.2f}"
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
            return (
                str(self.frame.columns[section])
                if orientation == Qt.Orientation.Horizontal
                else str(section + 1)
            )
        return None
