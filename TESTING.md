# Kết quả kiểm thử · 2026-10-30

## Môi trường

Windows, Python 3.12, PyQt6 6.12, scikit-learn 1.6.1, imbalanced-learn 0.14.2, pandas 2.2.3; MySQL 8.0 cục bộ `localhost:3306`. Môi trường Python đặt ngoài đường dẫn có dấu vì threadpoolctl/OpenBLAS lỗi khi tìm DLL trong venv nằm dưới đường dẫn tiếng Việt trên máy này.

## Đã kiểm chứng

- **33 kiểm thử pytest qua**, gồm kiểm tra miền dữ liệu/thiếu cột, alias PAY_0/PAY_1, đặc trưng dẫn xuất, CSV/Excel, chống công thức bảng tính trong chuỗi xuất, giao dịch, trùng ID, phiên bản, dự báo thất bại không lưu một phần, lịch sử và thao tác PyQt6 qua QThread. Có kiểm thử thật với 3 hồ sơ tổng hợp từ notebook; các test nghiệp vụ còn lại dùng model giả định danh `test only` và SQLite tạm.
- **Ruff qua**, kiểm tra định dạng và lỗi Python cơ bản.
- **Bộ mô hình gốc:** đối chiếu 6.000 dòng X_test/y_test trên Drive. 38 đặc trưng tái tạo khớp dữ liệu gốc; AUC **0,7768596747239308**; ma trận nhầm lẫn **[[3234,1439],[393,934]]**; Brier sau hiệu chỉnh **0,13554608232876744**. Khớp metadata và số liệu báo cáo.
- **3 hồ sơ mẫu:** điểm thô 0,108104 / 0,504844 / 0,793079; PD 0,040737 / 0,254076 / 0,599673; nhãn 0 / 1 / 1.
- **MySQL thật:** nhập 10.000 hồ sơ ID tổng hợp, dự báo, lưu và đọc lại đúng 10.000 kết quả; thay tuổi một hồ sơ tạo bản mới trong khi bản cũ và kết quả cũ giữ nguyên; trạng thái cần dự báo lại đúng; xuất và đọc lại Excel đủ 10.000 dòng. Script đã xóa đúng tập dữ liệu kiểm thử của nó sau khi hoàn tất.
- Đo một lượt trên máy bàn giao: **0,193 giây** cho riêng suy luận 10.000 dòng; **1,378 giây** cho nhập dữ liệu chuẩn hóa → suy luận → lưu MySQL. Không gồm thời gian chọn file, đọc Excel, xuất Excel, tải mô hình lần đầu hoặc người dùng thao tác. Đây là số đo cục bộ, không cam kết mọi máy/server đều dưới 5 giây.

## Kiểm tra giao diện

Ảnh native Qt ở `docs/screenshots/`: tổng quan trống có chủ đích, dự báo hồ sơ mẫu ở 1440×940 và 1050×720. Dữ liệu dài nằm trong vùng cuộn. Giao diện dùng dữ liệu thật từ bộ mô hình; ảnh dự báo là kết quả chưa lưu, không phải dữ liệu khách hàng thật.

## Phạm vi chưa kiểm chứng

Không kiểm thử triển khai nhiều người dùng, server MySQL từ xa/TLS, mã hóa lưu trữ, khôi phục backup, hiệu năng ở quy mô lớn hơn 10.000 hồ sơ hoặc Mac/Linux. Chưa tích hợp SHAP và màn so sánh cả ba mô hình; ứng dụng triển khai Random Forest được nhóm lựa chọn. GitHub Actions là kiểm tra riêng sau khi push, không thay bằng kết quả local.

## Chạy lại

Xem lệnh tại README. Nếu thư mục temp mặc định Windows bị hạn chế quyền, tạo một thư mục tạm mới trong dự án và chỉ định `pytest --basetemp=<đường_dẫn_mới>`; không trỏ `--basetemp` vào thư mục chứa dữ liệu vì pytest có thể dọn nội dung thư mục đó.
