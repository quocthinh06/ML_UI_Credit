# Đối chiếu chức năng với tài liệu được cung cấp

DOCX có các bản BRD lặp lại và ghi chú soạn thảo. Bảng này dùng các quy tắc nghiệp vụ có cấu trúc, không thực hiện các câu yêu cầu chỉnh sửa báo cáo trong tài liệu như lệnh tác nghiệp. Công nghệ desktop PyQt6/MySQL giữ theo yêu cầu trực tiếp của người dùng.

| Nhóm yêu cầu | Hành vi đã triển khai | Kiểm chứng |
|---|---|---|
| Tiếp nhận CSV/XLSX/JSON | Kiểm tra 23 trường, ID và miền giá trị; báo dòng/cột lỗi | Test nhập/xuất và CSV UCI thật |
| Tiền xử lý UCI | EDUCATION 0/5/6 về 4, MARRIAGE 0 về 3 như notebook; giữ mã source; không tự điền trường thiếu | 30.000 dòng, 345/54 giá trị quy đổi |
| Dự báo | Điểm thô, PD isotonic, nhãn 0/1, Low/Medium/High | Mẫu notebook, test 6.000, UCI 30.000 |
| BR-01–05 mô hình | RF mặc định theo CV; chọn LR/RF/XGB; cache theo version/hash/toàn bộ ngưỡng | Test đổi model, cache, cả ba bundle |
| Ngưỡng nhãn | BRD: PD 50%; notebook: điểm thô với ngưỡng từng model; chọn cơ sở rõ ràng | Test basis và metadata |
| Nhóm rủi ro | PD <20% Low, 20%–<50% Medium, ≥50% High; điều chỉnh độc lập | Test ngưỡng và model thực |
| BR-06–11 dòng dữ liệu | Thêm/sửa/xóa; cập nhật bản làm việc hoặc tạo bản sao; giữ lịch sử | Test version, copy, xóa dòng cuối |
| BR-12–16 chuyển đầu vào | Chuyển riêng đầu vào đơn lẻ vào dataset/bản sao, không chuyển output | Test cách ly bản sao, không tạo run do chuyển |
| Dashboard | Risk, PD, PD theo tuổi, cảnh báo; EDA; ROC/ma trận nhầm lẫn | Test chart và ảnh native 30.000 dòng |
| Nhãn thực tế | Giữ nhãn, tính tỷ lệ trên 0/1 hợp lệ; nhãn thiếu không coi là 0 | Tỷ lệ 22,12%; test nhãn thiếu/sai |
| Hiệu năng | CV/test gốc và đánh giá file tách riêng; không gọi dữ liệu có train là test độc lập | AUC test khớp dưới 1e-9 |
| Bộ lọc | ID/risk/khoảng PD/tuổi/hạn mức/PAY_0/cảnh báo; trạng thái danh mục | Test bảng, lọc và xuất |
| Giải thích | Tree SHAP RF/XGB; hệ số × giá trị biến đổi LR; ghi rõ điểm thô/log-odds | Đã chạy thật cả ba |
| Lịch sử/MySQL | Snapshot, output, ngưỡng, model/hash, UTC, tài khoản Windows; giữ khi khởi động lại | Test giao dịch và MySQL thực |
| Xuất | CSV/XLSX đầu vào + output + metadata; toàn bộ hoặc sau lọc | Roundtrip, CSV đủ 30.000 dòng |

Đăng nhập/phân quyền tài khoản ứng dụng và mã hóa lưu trữ ở bản nháp BRD trước chưa triển khai. Người thực hiện là tài khoản Windows, không được trình bày như xác thực người dùng ứng dụng. Không có huấn luyện lại từ giao diện, phê duyệt khoản vay, Core Banking hoặc thu hồi nợ.
