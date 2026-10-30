"""One retained QThread per task; only signals cross into the GUI thread."""

from PyQt6.QtCore import QThread, pyqtSignal


class Task(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            result = self.function()
        except Exception as exc:
            from sqlalchemy.exc import SQLAlchemyError

            # SQLAlchemy errors may contain bound customer records. Never show them.
            if isinstance(exc, SQLAlchemyError):
                self.failed.emit(
                    "Không thể thao tác MySQL. Kiểm tra dịch vụ, cấu hình và quyền tài khoản; dữ liệu chưa được xác nhận lưu."
                )
            else:
                self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.succeeded.emit(result)
