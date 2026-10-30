# Changelog

## [0.2.0.0] - 2026-10-30

### Added

- Tải CSV/XLSX/JSON và tự dự báo, giữ nhãn thực tế, chuẩn hóa mã UCI theo notebook.
- Dashboard dự báo, khám phá dữ liệu, ROC và ma trận nhầm lẫn trên nhãn hợp lệ.
- Chọn ba mô hình, so sánh chỉ số và giải thích đặc trưng thực.
- Xóa dòng giữ lịch sử, sửa bản sao, chuyển riêng đầu vào đơn lẻ sang hàng loạt.
- Lọc PD/tuổi/hạn mức/trả nợ/nhãn cảnh báo, xuất metadata truy vết.

### Fixed

- Xử lý đúng mã UCI gốc theo bước chuẩn hóa đã huấn luyện.
- Xóa kết quả hiện tại khi mô hình/cấu hình/dữ liệu thay đổi, giữ nguyên lịch sử.
- Tách ngưỡng PD theo BRD và điểm thô theo notebook.
- Đọc tương thích đúng snapshot XGBoost trên Windows, AUC khớp test gốc.

## [0.1.0.0] - 2026-10-30

### Added

- Ứng dụng PyQt6 dự báo đơn lẻ/hàng loạt với Random Forest và xác suất isotonic của nhóm.
- Kiểm tra 23 trường UCI, nhập/xuất CSV và Excel, bộ lọc và tổng quan danh mục.
- Lưu MySQL theo phiên bản dữ liệu và lịch sử dự báo; xác nhận trước cập nhật ID.
- Script cài đặt/khởi chạy Windows, tải mô hình có kiểm tra SHA256, hướng dẫn Workbench và kiểm thử tự động.
