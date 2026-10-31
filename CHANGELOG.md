# Changelog

## [0.3.0.0] - 2026-10-31

### Added

- Bản web Flask chạy trên Vercel, 5 màn hình HTML/CSS/JavaScript theo Stitch, hỗ trợ desktop và điện thoại.
- API model thật, upload CSV/XLSX/JSON, dự báo batch 500 dòng, đánh giá/giải thích và xuất Excel tính lại ở server.
- IndexedDB giữ dataset/phiên bản/lịch sử; sao lưu và khôi phục JSON; MongoDB Atlas tùy chọn theo mã kho riêng, GridFS và kiểm tra xung đột khi đồng bộ.
- Kiểm thử API, gzip, mã kho và giải thích cả 3 model; nghiệm thu trình duyệt cho dự báo, lọc/xuất, so sánh và phiên bản dữ liệu.

### Changed

- `main.py` trở thành WSGI entrypoint `app`; bản PyQt6 chuyển sang `desktop_main.py`, bộ cài desktop tách riêng.
- Vercel tải model có SHA256 trong build, loại PyQt/Matplotlib/SHAP khỏi runtime web và dùng XGBoost CPU trên Linux.
- Chuyển cấu hình pytest/ruff sang file riêng để Vercel cài đúng dependency từ requirements.txt.

## [0.2.1.0] - 2026-10-31

### Changed

- Áp dụng phong cách bốn màn hình Stitch bằng QSS native: sidebar SVG, thẻ thống kê, thanh kết nối, bảng và tab bo góc, focus/hover/disabled và thanh cuộn đồng nhất.
- Chia nhóm thao tác dữ liệu thành hai hàng, Việt hóa tiêu đề bảng lịch sử/dataset và làm dịu đường lưới biểu đồ.

### Added

- Lưu ảnh và HTML của 4 màn hình Stitch trong `docs/design/stitch/`.
- Xuất Excel gồm dữ liệu, insight, số dòng/cột, thông tin model/ngưỡng và dashboard với nhãn/số liệu; đánh giá và ROC khi đủ nhãn thực tế.
- Tên file mặc định theo model: `ket_qua_RF.xlsx`, `ket_qua_LR.xlsx`, `ket_qua_XGb.xlsx`; ngăn xuất nhầm kết quả model khác.

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
