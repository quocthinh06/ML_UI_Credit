# CreditRisk AI

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Chuyên viên phân tích rủi ro và Admin trong bối cảnh đồ án nhóm 4 về dự báo nguy cơ vỡ nợ tín dụng. Chuyên viên làm việc với dữ liệu của tài khoản mình; Admin quản lý tài khoản, vai trò, khóa truy cập và đặt lại mật khẩu. Ngữ cảnh này đã được người dùng xác nhận ngày 2026-11-15.

## Product Purpose

Hỗ trợ đánh giá rủi ro tín dụng từ dữ liệu UCI: nhập một hồ sơ hoặc một tệp, kiểm tra dữ liệu, dự báo, xem giải thích, lưu và tra cứu lịch sử. Kết quả hỗ trợ phân tích; hệ thống không tự quyết định cấp hoặc từ chối tín dụng.

## Operating Context

Ứng dụng web Flask/Python với HTML/CSS/JavaScript, triển khai theo cấu hình Vercel; chạy local bằng `python main.py` tại `http://127.0.0.1:5000`. Bản PyQt6/MySQL ở `desktop_main.py` là lựa chọn Windows được giữ tương thích, không phải nền tảng thiết kế chính.

Luồng chính gồm Tổng quan, Quản lý dữ liệu, Dự báo, Lịch sử và Hiệu năng; có Đăng nhập, Đổi mật khẩu và Admin Console. Người dùng chọn dataset/phiên bản, model và ngưỡng; dự báo đơn lẻ hoặc hàng loạt, mở chi tiết hồ sơ và xuất Excel.

## Capabilities and Constraints

- Tái sử dụng RF, LR và XGBoost gốc; đầu vào gồm 23 trường UCI, đơn vị tiền TWD. Xác suất, chỉ số và giải thích phải phản ánh model/bundle thật.
- IndexedDB lưu dữ liệu trên trình duyệt; MongoDB Atlas là tùy chọn đồng bộ kho. Phải phân biệt đã lưu cục bộ, đã đồng bộ, mất kết nối và xung đột phiên bản; không tự ghi đè dữ liệu xung đột.
- Xác thực hai vai trò được kiểm tra ở backend. Chuyên viên được thêm/sửa/xóa dữ liệu làm việc của mình; không được tự nâng quyền bằng giao diện.
- Tệp CSV/XLSX/JSON tối đa 4 MB, dataset tối đa 30.000 hồ sơ; batch chia nhóm tối đa 500 dòng. Xem README.md để biết đầy đủ giới hạn vận hành hiện tại.
- Huấn luyện phiên bản mới chưa được coi là triển khai khi chưa có worker, artifact và evaluation thật. Không hiển thị tiến trình huấn luyện giả.
- LR giải thích bằng hệ số nhân dữ liệu chuẩn hóa; XGBoost dùng Tree SHAP tích hợp; RF dùng phân rã đóng góp theo đường đi cây và phải ghi rõ không phải SHAP.

## Brand Commitments

Tên sản phẩm CreditRisk AI; giao diện và thuật ngữ chính bằng tiếng Việt. Giữ đúng ý nghĩa hồ sơ, dataset, phiên bản, PD, ngưỡng và nhãn thực tế; không đồng nhất nhãn dự báo với nhãn thực tế.

## Evidence on Hand

- `README.md`, `docs/BRD_WEB_ALIGNMENT.md`, `docs/AUTH_ADMIN.md` và `docs/BA_VI/`: chức năng, quyền và phạm vi; phân biệt hiện trạng với giả định/gaps.
- `frontend/`: giao diện web đã triển khai; `docs/design/stitch/`: bốn màn hình tham chiếu, không phải nguồn số liệu thực.
- `models/` và báo cáo/notebook của đồ án: nguồn hợp đồng dữ liệu/mô hình. Chỉ dùng pickle từ nguồn tin cậy.
- Đặc tả Admin được tài liệu cũ dẫn chiếu là `Dac_ta_phan_he_Admin_MLBA.docx`; chưa xác minh vị trí trong lượt này.

## Product Principles

- Ưu tiên tính đúng của dữ liệu, đơn vị, model và phép giải thích.
- Bảo toàn dữ liệu và lịch sử; hiển thị rõ trạng thái lưu và đồng bộ.
- Phân quyền tại backend; giao diện phản ánh quyền đã được xác nhận.
- Hiển thị trạng thái trống, lỗi và thiếu cấu hình trung thực; không dùng số minh họa như kết quả thật.

## Accessibility & Inclusion

Giữ hỗ trợ tiếng Việt, bàn phím, skip link, nhãn trường nhập, focus nhìn thấy và reduced-motion đang có trong mã. Mức rủi ro phải có chữ, không chỉ biểu thị bằng màu. Chưa xác lập chuẩn nghiệm thu accessibility riêng.
