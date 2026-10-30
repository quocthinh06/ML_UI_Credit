# Thiết kế PyQt6

Giữ bố cục ảnh tham khảo: sidebar xanh đen, nội dung nền sáng, nhấn xanh dương, bảng dữ liệu và hai khu nhập/kết quả. Dùng widget PyQt6 native và Segoe UI để tiếng Việt rõ trên Windows. Không dựng trang HTML bên trong Qt.

Token trong `creditrisk/style.qss`: nền `#f7f8fc`, chữ `#182338`, chữ phụ `#56657b`, sidebar `#0c1929`, nút chính `#2460e8`, đường viền `#dce3ee`. Kết quả Low `#087f83`, Medium `#986000`, High `#b91c1c`, luôn kèm tên mức độ để không chỉ dựa vào màu.

Cỡ chữ nội dung 13px, tiêu đề 26px, số tổng quan 28px, PD 34px. Cửa sổ tối thiểu 1050×720, mặc định 1440×940. Nhập liệu dài cuộn độc lập; bảng cuộn ngang khi nhiều cột. Giao diện có trạng thái trống, thiếu cấu hình/mô hình, đang chạy, lỗi, đã lưu và cần dự báo lại. Khi xử lý dữ liệu, các thao tác thay đổi dữ liệu bị khóa nhưng thread giao diện vẫn chạy.

Khác biệt có chủ đích với ảnh: dùng 23 trường UCI và đơn vị TWD thay DPD/DTI/VND; bỏ số liệu minh họa, khuyến nghị từ chối khoản vay và SHAP không có cơ sở tính toán.
