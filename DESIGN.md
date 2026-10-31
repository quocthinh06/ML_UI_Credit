# Thiết kế web · Vercel

Giao diện chính tại `creditrisk/templates/index.html` và `creditrisk/static/`. Web chuyển từ 4 màn hình Stitch theo yêu cầu mới ngày 2026-10-31; dùng bảng màu xanh đen/xanh dương và bề mặt sáng bo góc của mẫu. Sidebar cố định 238px trên desktop, menu thu gọn trên điện thoại; trang điều hướng theo hash. Bảng cuộn ngang riêng và phân trang; form 23 trường chia nhóm; kết quả đơn lẻ bên phải trên desktop, xếp dưới form trên mobile.

Token CSS: nền `#f8f9fe`, chữ `#15233b`, chữ phụ `#617088`, viền `#e5eaf3`, primary `#2563eb`, teal `#087f83`, đỏ `#bb2745`. Font hệ thống Segoe UI/system-ui; không cần tải font/CDN. SVG icon nét đồng nhất. Biểu đồ SVG có tên trục, nhãn nhóm và giá trị, dùng dữ liệu thực từ model; nhãn thực tế tách khỏi dự báo. Hiện rõ chế độ lưu dữ liệu, trạng thái tải, lỗi, chưa dự báo, cấu hình thay đổi và chưa đồng bộ. Có focus bàn phím, skip link, nhãn input, reduced-motion và CSP chỉ cho tài nguyên cùng origin.

## Bản desktop giữ tương thích

Giữ bố cục ảnh tham khảo: sidebar xanh đen, nội dung nền sáng, nhấn xanh dương, bảng dữ liệu và hai khu nhập/kết quả. Dùng widget PyQt6 native và Segoe UI để tiếng Việt rõ trên Windows. Không dựng trang HTML bên trong Qt.

Tham chiếu hiện tại: bốn màn hình Stitch của dự án **ML dự báo** (`8573081007180144965`), ảnh và HTML tại `docs/design/stitch/`. Chuyển sang widget Qt native qua QSS, không nhúng HTML tham chiếu.

Token trong `creditrisk/style.qss`: nền `#faf8ff`, chữ `#101b33`, chữ phụ `#566176`, sidebar `#0b1626`, nút chính `#2563eb`, đường viền `#e0e5f0`. Bề mặt trắng, góc bo 8–14px, khoảng cách nhóm 12–24px. Kết quả Low `#087f83`, Medium `#986000`, High `#b91c1c`, luôn kèm tên mức độ để không chỉ dựa vào màu.

Cỡ chữ nội dung 13px, tiêu đề 25px, số tổng quan 30px, PD 36px. Cửa sổ tối thiểu 1050×720, mặc định 1440×940. Nhập liệu dài cuộn độc lập; bảng cuộn ngang khi nhiều cột. Giao diện có trạng thái trống, thiếu cấu hình/mô hình, đang chạy, lỗi, đã lưu và cần dự báo lại. Khi xử lý dữ liệu, các thao tác thay đổi dữ liệu bị khóa nhưng thread giao diện vẫn chạy.

Sidebar dùng SVG nét đồng nhất, trạng thái chọn xanh, focus bàn phím rõ. Thanh kết nối và thẻ thống kê có bề mặt trắng; bảng 44px mỗi dòng, tiêu đề tiếng Việt, nền xen kẽ nhẹ. Nút xóa dùng đỏ nhạt và vẫn giữ bước xác nhận. Nhóm thao tác quản lý dữ liệu chia hai hàng để vừa cửa sổ nhỏ. Combo/spinbox dùng SVG mũi tên qua đường dẫn tuyệt đối; thanh cuộn theo cùng bảng màu.

Khác biệt có chủ đích với ảnh: dùng 23 trường UCI và đơn vị TWD thay DPD/DTI/VND; bỏ số liệu minh họa, khuyến nghị từ chối khoản vay và SHAP không có cơ sở tính toán.

Dashboard mở rộng dùng Matplotlib nhúng Qt; biểu đồ trên tệp được chọn, số liệu danh mục theo mô hình được chọn. Chart và bảng hàng loạt có vùng cuộn ở cửa sổ nhỏ. Đã có Tree SHAP thật cho RF/XGB; không dùng phần trăm minh họa trong ảnh mẫu.
