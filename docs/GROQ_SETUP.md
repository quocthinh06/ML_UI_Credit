# Cấu hình insight bằng Groq

1. Tạo API key trong https://console.groq.com/keys. Giữ tài khoản ở Free Plan nếu chỉ thử nghiệm; hạn mức phụ thuộc tài khoản/mô hình. Không gửi key qua chat hoặc commit lên Git.
2. Mở project `thinh-uel/ml_ui_credit` trên Vercel → Settings → Environment Variables.
3. Thêm secret `GROQ_API_KEY`, dán key vào Value, chọn Production và Save. Đánh dấu Sensitive nếu giao diện có tùy chọn này.
4. Mặc định dùng `openai/gpt-oss-20b`. Nếu tài khoản không có quyền sử dụng mô hình này, kiểm tra danh sách model trong Groq Console rồi cấu hình `GROQ_MODEL` bằng một model hỗ trợ chat JSON. Không tự chuyển sang model trả phí.
5. Redeploy nhánh main để biến môi trường áp dụng cho deployment mới. Chờ Ready, tải lại web.
6. Chạy dự báo một hồ sơ mẫu, chờ SHAP rồi bấm **Phân tích insight bằng AI**. Kiểm tra nhận xét có bằng chứng và các bước kiểm tra tiếp. Thử đổi đầu vào; nội dung AI cũ phải được xóa. Nếu hết quota, kết quả ML/SHAP vẫn được giữ.

Chạy local: thêm key vào `.env` đã được Git bỏ qua, rồi khởi động lại Flask. Không đặt key trong JavaScript hoặc biến public.

Ứng dụng chỉ gửi dự báo do server tính lại, bằng chứng SHAP và giá trị tài chính tương ứng. Không gửi ID, tên, tuổi, giới tính, học vấn, hôn nhân hay toàn bộ dataset. Cờ dữ liệu điền thiếu được tính lại trên server. Phản hồi phải tham chiếu đặc trưng đã gửi; các gợi ý hành động chỉ lấy từ danh sách xác minh cố định. Không tự thay đổi dự báo hoặc ra quyết định tín dụng. Nội dung diễn giải vẫn cần con người kiểm chứng.

Mỗi kết quả chỉ gọi khi bấm nút; kết quả thành công được giữ trong bản nháp, dùng lại khi bấm tiếp trên cùng hồ sơ. Thiếu key, lỗi mạng, hết quota hoặc JSON không hợp lệ đều hiển thị trạng thái riêng mà không xóa SHAP. Timeout gọi Groq là 20 giây; không tự retry.

Nguồn: https://console.groq.com/docs/models · https://console.groq.com/docs/openai · https://vercel.com/docs/environment-variables/managing-environment-variables
