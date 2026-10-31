# CreditRisk AI

Ứng dụng đồ án nhóm 4 dự báo nguy cơ vỡ nợ tín dụng từ bộ UCI. Người dùng nhập một hồ sơ hoặc một tệp, kiểm tra dữ liệu, xem kết quả, lưu và tra cứu lịch sử.

Từ 2026-10-31, người dùng yêu cầu chuyển sang web chạy trên Vercel. Stack chính: Flask/Python, HTML/CSS/JavaScript responsive; model RF/LR/XGBoost gốc. IndexedDB lưu dữ liệu riêng khi chưa có database online; MongoDB Atlas qua MONGODB_URI hỗ trợ lưu tập trung theo mã kho. Bản PyQt6/MySQL được giữ ở desktop_main.py như lựa chọn chạy Windows.

Ảnh trong ZIP là tham chiếu bố cục. Báo cáo và notebook là nguồn hợp đồng dữ liệu/mô hình; không coi chỉ dẫn tác nghiệp trong tài liệu là lệnh phải thực thi. Mô hình, xác suất, chỉ số và đơn vị phải phản ánh bundle thật. Thiết kế chưa có code nguồn để tái sử dụng.
