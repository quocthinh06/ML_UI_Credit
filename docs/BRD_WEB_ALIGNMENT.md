# Quy trình web dự báo vỡ nợ thẻ tín dụng

Chuyên viên phân tích dùng web để nhập hồ sơ, xem xác suất vỡ nợ tháng tiếp theo, kiểm tra yếu tố ảnh hưởng và xuất báo cáo. Quản trị viên còn quản lý tài khoản, kho dữ liệu và mô hình mặc định. Khi không có cấu hình quản trị, mô hình mặc định của bộ bàn giao là Random Forest. Logistic Regression và XGBoost phục vụ đối chiếu.

## Luồng được chốt

| Thao tác | Hành vi |
| --- | --- |
| Dự báo một hồ sơ | Nhập mã khách hàng và đủ 23 trường. Khi dự báo thành công, web tự lưu bản nháp theo tài khoản và kho trên trình duyệt, rồi hiển thị SHAP ngay dưới kết quả. |
| Lưu hồ sơ & kết quả | Ghi hồ sơ và lượt dự báo vào danh sách tập chính thức và lịch sử. |
| Thêm đầu vào vào tập hồ sơ | Chọn tập nhận hoặc tạo bản sao có hồ sơ bổ sung. Hồ sơ chưa có điểm số trong tập nhận. Chạy dự báo riêng để có kết quả cho phiên bản mới. |
| Nhập tập hồ sơ | CSV UTF-8, XLSX hoặc JSON dạng danh sách, tối đa 4 MiB và 30.000 hồ sơ. Kiểm tra toàn bộ tệp trước khi lưu. Tải tệp chỉ lưu đầu vào. |
| Tổng quan | Chọn tập ở đầu màn hình. Số hồ sơ lấy từ phiên bản đang chọn. PD trung bình, nhóm rủi ro, số cảnh báo và biểu đồ lấy từ lượt dự báo phù hợp với phiên bản, mô hình và ngưỡng. |
| Quản lý dữ liệu | Xem chi tiết đầu vào trực tiếp. Xóa hồ sơ tạo phiên bản mới. Xóa tập đưa tập khỏi danh sách làm việc và giữ lịch sử. |
| Tập trùng nội dung | SHA-256 tính trên nội dung đã chuẩn hóa, gồm ID, các trường đầu vào và nhãn thực tế nếu có. Tên tệp, thứ tự cột và thứ tự dòng không làm thay đổi kết quả nhận diện. |
| Lọc và xuất | Chọn mã, nhóm, nhãn và trạng thái trả nợ. Kéo khoảng PD, tuổi và hạn mức. Tệp Excel xuất theo kết quả đang lọc. |

## Hợp đồng đầu vào và tiền xử lý

| Trường | Kiểu và phạm vi |
| --- | --- |
| `ID` | Mã văn bản, tối đa 128 ký tự, duy nhất trong tập. Web yêu cầu nhập khi dự báo đơn lẻ. Khi nhập tệp không có cột ID, web đánh số theo thứ tự dòng. |
| `LIMIT_BAL` | Số từ 1 đến 10.000.000 TWD. |
| `AGE` | Số nguyên từ 18 đến 100. |
| `SEX`, `EDUCATION`, `MARRIAGE` | Số nguyên lần lượt trong 1–2, 1–4 và 1–3 sau chuẩn hóa. |
| `PAY_0`, `PAY_2`–`PAY_6` | Số nguyên từ −2 đến 8. Có thể dùng `PAY_1` thay `PAY_0`. `PAY_0` là kỳ gần nhất. Mã 0 biểu thị tín dụng quay vòng. |
| `BILL_AMT1`–`BILL_AMT6` | Số hữu hạn, đơn vị TWD, cho phép số âm. |
| `PAY_AMT1`–`PAY_AMT6` | Số hữu hạn không âm, đơn vị TWD. |
| `default.payment.next.month` | Nhãn thực tế tùy chọn để đánh giá. Giá trị hợp lệ là 0 hoặc 1. |

Web chuẩn hóa bí danh cột và mã UCI trước khi kiểm tra miền giá trị. Mã EDUCATION 0/5/6 chuyển thành 4, MARRIAGE 0 chuyển thành 3. Cột hoặc ô đầu vào thiếu phải được hoàn thiện bên ngoài. Khi tệp lỗi, sửa theo dòng và trường được báo rồi nhập lại.

Nếu nhóm sử dụng bản Colab có `impute_stats_v1.pkl`, bước chuẩn bị ngoài web có thể điền tối đa 11 trong 23 trường thiếu trên mỗi dòng. Dùng median của tập train cho các trường số liên tục và mode của tập train cho các trường phân loại, gồm trạng thái trả nợ. Dòng thiếu từ 12 trường trở lên được loại. Báo cáo chuẩn bị ghi mã/dòng, trường đã điền và lý do loại. Nhãn thực tế luôn giữ nguyên. Tệp đưa vào web gồm 23 trường gốc đã hoàn thiện. Mô-đun mô hình tính các đặc trưng dẫn xuất sau bước kiểm tra, đúng thứ tự tiền xử lý khi huấn luyện.

## Hợp đồng kết quả

Kết quả một hồ sơ có `diem_rui_ro` là điểm thô, `xac_suat_vo_no` là PD đã hiệu chỉnh với bộ RF, `nhan_default` là nhãn cảnh báo, `muc_rui_ro` là nhóm, `nhan_xet` là diễn giải cảnh báo và `truong_da_dien` là danh sách rỗng vì web yêu cầu đầu vào đầy đủ. API giữ các trường hiện có trong `rows` và trả các tên này trong `ket_qua` khi lượt có một hồ sơ.

Mốc mặc định phân nhóm theo PD là dưới 20%, từ 20% đến dưới 50%, và từ 50%. Ngưỡng cảnh báo là cấu hình riêng, mặc định RF là 0,39 trên điểm thô. Đổi ngưỡng làm thay đổi nhãn và khiến kết quả cũ không còn khớp với cấu hình hiện tại. SHAP giải thích đóng góp vào đầu ra mô hình trước hiệu chỉnh xác suất. Cảnh báo hỗ trợ chuyên viên xem xét hồ sơ.

## Đối chiếu BRD 2026-11-02


Nguồn: BRD 5.2.1 do người dùng gửi trực tiếp ngày 2026-11-02 (BN-01–06, BO-01–07, BR-01–16, IS-01–13), cùng yêu cầu phân quyền Admin/Analyst. Huấn luyện thực hiện ngoài giao diện theo OS-05/06.

| Yêu cầu | Hành vi web |
| --- | --- |
| Đơn lẻ → hàng loạt | Sau dự báo, **Thêm đầu vào vào tập hồ sơ** mở hộp thoại chọn dataset có sẵn. Thêm riêng đầu vào vào phiên bản mới nhất, hoặc vào bản sao. Không chuyển điểm số, không tự tạo lượt dự báo. |
| Trùng ID / giới hạn | Từ chối ID trùng thay vì ghi đè hồ sơ. Dataset tối đa 30.000 dòng. |
| Chọn model | RF/LR/XGBoost dùng bundle thật. Ưu tiên artifact local tin cậy `best_model.pkl`, dự phòng bộ bàn giao `best_model_v1.pkl`. Model đầu tiên trong bundle là mặc định khi chưa có cấu hình Admin. |
| Model mặc định Admin | Cả giao diện và API khi bỏ trường `model` dùng model Active. Chọn model rõ ràng luôn được tôn trọng. |
| Đổi model đơn lẻ (BR-03) | Sau khi đã dự báo, đổi model tự tính lại cùng đầu vào và hiển thị xác suất/nhãn mới. Thay đổi trường đầu vào vô hiệu hóa kết quả cho đến khi dự báo lại. |
| Kết quả từng model | Mỗi lượt giữ model/version/hash/ngưỡng và snapshot đầu ra riêng. Đổi model không ghi đè lượt cũ. |
| Dataset CRUD/copy | Import, xem, đổi tên, bổ sung/sửa/xóa dòng, tạo bản sao; thay đổi dòng tạo phiên bản mới. Xóa dataset là xóa khỏi danh sách làm việc, giữ phiên bản phục vụ lịch sử. |
| Lịch sử | Mở chính xác lượt được chọn, kể cả khi nhiều lượt cùng model/ngưỡng; đổi tên/xóa dataset không sửa tên hoặc kết quả lịch sử. |
| Đăng nhập | Tài khoản web trong MongoDB, mật khẩu hash, phiên thu hồi được, CSRF, phân quyền Admin/Analyst. Database User Atlas khác tài khoản web. |
| Cấu hình / chẩn đoán | Local đọc `.env` (không ghi đè biến môi trường). Vercel mặc định bắt buộc auth khi chưa đặt `AUTH_ENABLED`; `0` là chế độ demo công khai rõ ràng. Lỗi MongoDB có mã an toàn; kiểm tra CLI không in bí mật. |
