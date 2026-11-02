# Phạm vi đối chiếu BRD web — 2026-11-02

Nguồn: yêu cầu trực tiếp trong công việc GitHub và `docs/REQUIREMENTS.md`, `PRODUCT.md` hiện có. Bản đầy đủ BRD trong cuộc trò chuyện ChatGPT trước không truy xuất được trong phiên này; tài liệu này không tuyên bố đã đối chiếu toàn bộ bản đó.

| Yêu cầu | Hành vi web |
| --- | --- |
| Đơn lẻ → hàng loạt | Sau dự báo, **Thêm vào dự báo hàng loạt** mở hộp thoại chọn dataset có sẵn. Thêm riêng đầu vào vào phiên bản mới nhất, hoặc vào bản sao. Không chuyển điểm số, không tự tạo lượt dự báo. |
| Trùng ID / giới hạn | Từ chối ID trùng thay vì ghi đè hồ sơ. Dataset tối đa 30.000 dòng. |
| Chọn model | RF/LR/XGBoost dùng bundle thật. Ưu tiên artifact local tin cậy `best_model.pkl`, dự phòng bộ bàn giao `best_model_v1.pkl`. Model đầu tiên trong bundle là mặc định khi chưa có cấu hình Admin. |
| Model mặc định Admin | Cả giao diện và API khi bỏ trường `model` dùng model Active. Chọn model rõ ràng luôn được tôn trọng. |
| Kết quả từng model | Mỗi lượt giữ model/version/hash/ngưỡng và snapshot đầu ra riêng. Đổi model không ghi đè lượt cũ. |
| Dataset CRUD/copy | Import, xem, đổi tên, bổ sung/sửa/xóa dòng, tạo bản sao; thay đổi dòng tạo phiên bản mới. Xóa dataset là xóa khỏi danh sách làm việc, giữ phiên bản phục vụ lịch sử. |
| Lịch sử | Mở chính xác lượt được chọn, kể cả khi nhiều lượt cùng model/ngưỡng; đổi tên/xóa dataset không sửa tên hoặc kết quả lịch sử. |
| Đăng nhập | Tài khoản web trong MongoDB, mật khẩu hash, phiên thu hồi được, CSRF, phân quyền Admin/Analyst. Database User Atlas khác tài khoản web. |
| Cấu hình / chẩn đoán | Local đọc `.env` (không ghi đè biến môi trường). Vercel mặc định bắt buộc auth khi chưa đặt `AUTH_ENABLED`; `0` là chế độ demo công khai rõ ràng. Lỗi MongoDB có mã an toàn; kiểm tra CLI không in bí mật. |

Kiểm chứng: pytest (gồm ba model thật và auth MongoDB mock), Node workflow tests và browser local. Chưa nghiệm thu Atlas production, transaction/GridFS thật hay đăng nhập production khi Database User vẫn bị từ chối xác thực.
