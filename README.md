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

- Tổng quan: danh mục theo model, phân bố rủi ro/PD, thống kê theo tuổi, khám phá dữ liệu, ma trận nhầm lẫn và ROC khi đủ nhãn.
- Dữ liệu: tải CSV/XLSX/JSON, giữ ID dạng chuỗi, chuẩn hóa UCI, xem/sửa/bổ sung/xóa hồ sơ theo phiên bản, lưu bản sao.
- Dự báo: 23 trường UCI đơn lẻ hoặc hàng loạt, chọn RF/LR/XGBoost, tùy chỉnh ngưỡng raw/PD. Batch chia nhóm 500 dòng để phù hợp request Vercel.
- Lịch sử: bản chụp riêng cho từng lần chạy, model, SHA256, dữ liệu và ngưỡng; mở lại kết quả lịch sử.
- Hiệu năng: CV/test AUC từ bundle và so sánh 3 model trên nhãn hợp lệ của dataset.
- Giải thích: LR dùng hệ số × dữ liệu chuẩn hóa; XGBoost dùng Tree SHAP tích hợp; RF dùng phân rã đóng góp theo đường đi cây và ghi rõ không phải SHAP.
- Excel: dữ liệu sau lọc, insight, số dòng/cột, metadata, dashboard có nhãn/số liệu. Tên `ket_qua_RF.xlsx`, `ket_qua_LR.xlsx`, `ket_qua_XGb.xlsx`. Server tính lại dự báo khi xuất để không tin điểm số sửa từ client.

### Giới hạn triển khai

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
