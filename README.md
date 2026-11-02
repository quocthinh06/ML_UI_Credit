# CreditRisk AI · Web

Ứng dụng web dự báo nguy cơ vỡ nợ tín dụng, chạy trên **Vercel + Flask**. Giao diện HTML/CSS/JavaScript theo [4 màn hình Stitch](docs/design/stitch/README.md), thích ứng desktop và điện thoại. Model và xử lý dữ liệu tái sử dụng từ bản PyQt6.

## Chạy local

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python tools/download_model.py
.venv\Scripts\python main.py
```

Mở http://127.0.0.1:5000. Trên Windows nên tạo venv trong đường dẫn không dấu nếu thư viện BLAS không tải được DLL.

## Deploy Vercel

Import repo này và chọn branch `main`. `vercel.json` cấu hình Flask, entrypoint `main:app`, Python 3.12 và build command `python tools/download_model.py`. Không cần cấu hình Output Directory. Model được tải và kiểm tra SHA256 trong bước build. Runtime web không cài PyQt6/Matplotlib/SHAP; Linux dùng XGBoost CPU để giảm kích thước bundle.

Website hoạt động ngay khi chưa cấu hình database: dữ liệu, phiên bản và lịch sử lưu vào **IndexedDB của trình duyệt hiện tại**. API dự báo không lưu hồ sơ lên ổ đĩa server. Chọn **Quản lý dữ liệu → Sao lưu JSON** để tạo bản sao toàn bộ dữ liệu/lịch sử; có chức năng khôi phục.

### MongoDB Atlas (tùy chọn)

1. Tạo cluster Atlas, database user và cấu hình Network Access cho môi trường triển khai.
2. Trên Vercel → project `ml_ui_credit` → Settings → Environment Variables, thêm:
   - `MONGODB_URI`: connection string Atlas có username/password; không đưa vào GitHub hoặc mã frontend.
   - `MONGODB_DATABASE`: tùy chọn, mặc định `creditrisk_ai`.
3. Redeploy. Website nhận chế độ MongoDB từ API và đồng bộ các lần lưu.

Nút **Kho dữ liệu** cung cấp mã truy cập riêng 256-bit; cùng mã mở cùng kho trên thiết bị khác. Mã có quyền đọc/ghi toàn bộ kho và cần giữ riêng. Server chỉ lưu hash mã, không công khai danh sách kho. Snapshot dùng GridFS để không vướng giới hạn một document MongoDB; cập nhật có kiểm tra phiên bản để tránh ghi đè đồng thời. Khi mất kết nối cloud, bản cục bộ vẫn được giữ và giao diện báo chưa đồng bộ. Website không dùng localhost MySQL từ máy cá nhân; MySQL Workbench chỉ là công cụ quản lý server.

## Chức năng

Đối chiếu phạm vi BRD web và các giới hạn nghiệm thu: [BRD web](docs/BRD_WEB_ALIGNMENT.md).

Nút **Thêm vào dự báo hàng loạt** mở chọn dataset nhận hoặc bản sao, thêm riêng đầu vào và giữ lịch sử. Trùng ID bị từ chối. Có đổi tên/xóa dataset khỏi danh sách làm việc; các phiên bản và lượt dự báo cũ vẫn mở được từ lịch sử. Artifact mặc định hỗ trợ `models/best_model.pkl`, dự phòng `best_model_v1.pkl` do script tải về; chỉ dùng pickle từ nguồn tin cậy.

Mỗi dòng trong bảng dữ liệu và kết quả hàng loạt có nút **Xem chi tiết**: mở đủ thông tin đầu vào và tự chạy dự báo riêng một hồ sơ. Đổi model trong màn hình này chỉ chấm lại hồ sơ đó. Có thể giải thích/xuất kết quả hoặc lưu thành hồ sơ đơn lẻ; dữ liệu nguồn và lịch sử hàng loạt giữ nguyên. **Quay lại danh sách hồ sơ** khôi phục tập dữ liệu, phiên bản, model và ngưỡng của màn hình trước.

Đăng nhập hai vai trò, quyền dữ liệu riêng theo tài khoản và Admin Console đã có trong mã nguồn. Xem [cấu hình đăng nhập và Admin](docs/AUTH_ADMIN.md). Cần MongoDB Atlas, khóa phiên và tài khoản Admin ban đầu để bật `AUTH_ENABLED=1`; chưa tự bật khi các giá trị này chưa được cấu hình.

- Tổng quan: danh mục theo model, phân bố rủi ro/PD, thống kê theo tuổi, khám phá dữ liệu, ma trận nhầm lẫn và ROC khi đủ nhãn.
- Dữ liệu: tải CSV/XLSX/JSON, giữ ID dạng chuỗi, chuẩn hóa UCI, xem/sửa/bổ sung/xóa hồ sơ theo phiên bản, lưu bản sao.
- Dự báo: 23 trường UCI đơn lẻ hoặc hàng loạt, chọn RF/LR/XGBoost, tùy chỉnh ngưỡng raw/PD. Batch chia nhóm 500 dòng để phù hợp request Vercel.
- Lịch sử: bản chụp riêng cho từng lần chạy, model, SHA256, dữ liệu và ngưỡng; mở lại kết quả lịch sử.
- Hiệu năng: CV/test AUC từ bundle và so sánh 3 model trên nhãn hợp lệ của dataset.
- Giải thích: LR dùng hệ số × dữ liệu chuẩn hóa; XGBoost dùng Tree SHAP tích hợp; RF dùng phân rã đóng góp theo đường đi cây và ghi rõ không phải SHAP.
- Excel: dữ liệu sau lọc, insight, số dòng/cột, metadata, dashboard có nhãn/số liệu. Tên `ket_qua_RF.xlsx`, `ket_qua_LR.xlsx`, `ket_qua_XGb.xlsx`. Server tính lại dự báo khi xuất để không tin điểm số sửa từ client.

### Giới hạn triển khai

Batch xử lý tuần tự từng nhóm tối đa 500 hồ sơ, giữ đúng thứ tự đầu ra và chỉ lưu lượt dự báo khi đã nhận đủ kết quả. Upload lưu dữ liệu/kết quả trên thiết bị trước, rồi đồng bộ cloud ở nền; nếu dự báo lỗi, đầu vào vẫn được lưu để chạy lại. Tiến trình hiển thị số hồ sơ đã xử lý và thời gian đã chờ, không thêm thời gian chờ giả.

Màn hình **Hiệu năng mô hình** cho chọn dataset và chạy đối chiếu cả ba model. Kết quả được lưu vào lịch sử theo phiên bản dữ liệu, hash model và ngưỡng để sử dụng lại. Tệp không có nhãn vẫn hiển thị số hồ sơ, PD trung bình, cảnh báo và phân bố rủi ro; tệp có nhãn `default.payment.next.month` 0/1 có thêm Accuracy/Precision/Recall/F1, ma trận nhầm lẫn và AUC/ROC khi có cả hai lớp. Không tự gán nhãn thực tế cho file mẫu. Thời gian hiển thị là thời gian suy luận/giao tiếp API ở lần chạy đó, không gồm upload và đồng bộ; không phải benchmark huấn luyện hoặc cam kết tốc độ production.

Tối đa 30.000 hồ sơ mỗi dataset, file upload 4 MB, nội dung giải nén 64 MB và file Excel tải về 4 MB. Request JSON lớn được nén gzip; bảng phân trang 25 dòng. Khi file Excel quá lớn, giao diện yêu cầu lọc nhóm nhỏ hơn. Kết quả hỗ trợ theo dõi; hệ thống không tự quyết định cấp hoặc từ chối tín dụng.

## Kiểm thử

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
node --check creditrisk/static/app.js
```

Bộ test có contract dữ liệu, dịch vụ phiên bản, 3 model thật, báo cáo Excel, API web, gzip, xuất file chống sửa điểm và mã kho MongoDB. CI giữ cả kiểm thử desktop và web.

## Bản desktop tùy chọn

Bản PyQt6 vẫn ở `desktop_main.py`; `Setup.cmd` cài `requirements-desktop.txt`, `Run.cmd` mở bản desktop với MySQL như trước. Xem [hướng dẫn desktop](docs/DESKTOP.md).

### Đồng bộ kho lớn và phục hồi

Kết quả được trả về sau khi IndexedDB lưu thành công, không chờ toàn bộ kho MongoDB tải lên. Thanh trạng thái phân biệt lưu trên thiết bị với đã đồng bộ cloud. Giữ trang mở đến khi báo đã đồng bộ nếu cần mở dữ liệu ở thiết bị khác. Trình duyệt không tự hủy request sau 20–25 giây. Request chờ máy chủ phản hồi; lỗi mạng hoặc giới hạn runtime từ nền tảng vẫn giữ bản cục bộ và dừng tự thử lại. Dùng **Thử đồng bộ lại** để đọc phiên bản hiện tại trước khi gửi tiếp.

Snapshot lớn được truyền bằng các phần tối đa 1 MiB rồi kiểm tra và commit hoàn chỉnh, tránh lỗi 413 do một request vượt giới hạn proxy. Snapshot MongoDB mới được gzip, vẫn đọc được dữ liệu JSON cũ. Giới hạn snapshot là 128 MiB sau giải nén; phần upload chưa hoàn tất tự hết hạn sau 30 phút. Giới hạn file nhập 4 MB giữ nguyên.

Không tự ghi đè khi hai bản có thay đổi khác nhau. Bản cục bộ được giữ để tiếp tục làm việc và sao lưu JSON. **Mở bản trên kho** là thao tác chủ động, có xác nhận, lưu bản phục hồi trên thiết bị và tải bản sao JSON trước khi thay bản làm việc. Lỗi `CSRF_STALE` chỉ được làm mới và thử lại một lần cho cùng tài khoản; lỗi quyền thật không được bỏ qua. Những thay đổi này không đổi mô hình hoặc công thức dự báo.
