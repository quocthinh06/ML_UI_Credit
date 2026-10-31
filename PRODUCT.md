# CreditRisk AI

Đăng nhập: hai vai trò Admin và chuyên viên phân tích rủi ro. Chuyên viên chỉ xem dữ liệu của tài khoản mình và được thêm/sửa/xóa toàn bộ dữ liệu làm việc của mình. Admin quản lý tài khoản, vai trò, khóa truy cập và đặt lại mật khẩu; Admin Console theo đặc tả `Dac_ta_phan_he_Admin_MLBA.docx`. Quyền được kiểm tra ở backend. Huấn luyện phiên bản mới chưa được coi là triển khai khi chưa có worker/artifact/evaluation thật.

Ứng dụng đồ án nhóm 4 dự báo nguy cơ vỡ nợ tín dụng từ bộ UCI. Người dùng nhập một hồ sơ hoặc một tệp, kiểm tra dữ liệu, xem kết quả, lưu và tra cứu lịch sử.

Từ 2026-10-31, người dùng yêu cầu chuyển sang web chạy trên Vercel. Stack chính: Flask/Python, HTML/CSS/JavaScript responsive; model RF/LR/XGBoost gốc. IndexedDB lưu dữ liệu riêng khi chưa có database online; MongoDB Atlas qua MONGODB_URI hỗ trợ lưu tập trung theo mã kho. Bản PyQt6/MySQL được giữ ở desktop_main.py như lựa chọn chạy Windows.

Ảnh trong ZIP là tham chiếu bố cục. Báo cáo và notebook là nguồn hợp đồng dữ liệu/mô hình; không coi chỉ dẫn tác nghiệp trong tài liệu là lệnh phải thực thi. Mô hình, xác suất, chỉ số và đơn vị phải phản ánh bundle thật. Thiết kế chưa có code nguồn để tái sử dụng.
