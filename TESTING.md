# Kết quả kiểm thử · 2026-10-30

## Môi trường

Windows, Python 3.12, PyQt6 6.12, scikit-learn 1.6.1, imbalanced-learn 0.14.2, pandas 2.2.3; MySQL 8.0 cục bộ `localhost:3306`. Môi trường Python đặt ngoài đường dẫn có dấu vì threadpoolctl/OpenBLAS lỗi khi tìm DLL trong venv nằm dưới đường dẫn tiếng Việt trên máy này.

## Đã kiểm chứng

- **46 kiểm thử pytest qua**, gồm kiểm tra miền dữ liệu/thiếu cột, alias PAY_0/PAY_1, đặc trưng dẫn xuất, CSV/Excel, chống công thức bảng tính trong chuỗi xuất, giao dịch, trùng ID, phiên bản, dự báo thất bại không lưu một phần, lịch sử và thao tác PyQt6 qua QThread. Có kiểm thử thật với 3 hồ sơ tổng hợp từ notebook; các test nghiệp vụ còn lại dùng model giả định danh `test only` và SQLite tạm.
- **Ruff qua**, kiểm tra định dạng và lỗi Python cơ bản.
- **Bộ mô hình gốc:** đối chiếu 6.000 dòng X_test/y_test trên Drive. 38 đặc trưng tái tạo khớp dữ liệu gốc; AUC **0,7768596747239308**; ma trận nhầm lẫn **[[3234,1439],[393,934]]**; Brier sau hiệu chỉnh **0,13554608232876744**. Khớp metadata và số liệu báo cáo.
- **3 hồ sơ mẫu:** điểm thô 0,108104 / 0,504844 / 0,793079; PD 0,040737 / 0,254076 / 0,599673; nhãn 0 / 1 / 1.
- **MySQL thật:** nhập 10.000 hồ sơ ID tổng hợp, dự báo, lưu và đọc lại đúng 10.000 kết quả; thay tuổi một hồ sơ tạo bản mới trong khi bản cũ và kết quả cũ giữ nguyên; trạng thái cần dự báo lại đúng; xuất và đọc lại Excel đủ 10.000 dòng. Script đã xóa đúng tập dữ liệu kiểm thử của nó sau khi hoàn tất.
- Đo một lượt trên máy bàn giao: **0,193 giây** cho riêng suy luận 10.000 dòng; **1,378 giây** cho nhập dữ liệu chuẩn hóa → suy luận → lưu MySQL. Không gồm thời gian chọn file, đọc Excel, xuất Excel, tải mô hình lần đầu hoặc người dùng thao tác. Đây là số đo cục bộ, không cam kết mọi máy/server đều dưới 5 giây.

## Kiểm tra giao diện

Ảnh native Qt ở `docs/screenshots/`: tổng quan trống có chủ đích, dự báo hồ sơ mẫu ở 1440×940 và 1050×720. Dữ liệu dài nằm trong vùng cuộn. Giao diện dùng dữ liệu thật từ bộ mô hình; ảnh dự báo là kết quả chưa lưu, không phải dữ liệu khách hàng thật.

## Phạm vi chưa kiểm chứng

Không kiểm thử triển khai nhiều người dùng, server MySQL từ xa/TLS, mã hóa lưu trữ, khôi phục backup, hiệu năng ở quy mô lớn hơn 30.000 hồ sơ hoặc Mac/Linux. Đã tích hợp ba mô hình và giải thích đơn lẻ; chưa kiểm thử triển khai đa người dùng. GitHub Actions là kiểm tra riêng sau khi push, không thay bằng kết quả local.

## Chạy lại

Xem lệnh tại README. Nếu thư mục temp mặc định Windows bị hạn chế quyền, tạo một thư mục tạm mới trong dự án và chỉ định `pytest --basetemp=<đường_dẫn_mới>`; không trỏ `--basetemp` vào thư mục chứa dữ liệu vì pytest có thể dọn nội dung thư mục đó.

## Đợt dashboard và CSV UCI gốc

Đã chạy đúng thao tác tải CSV qua MainWindow với `UCI_Credit_Card.csv` 30.000 dòng trên MySQL thật. 345 giá trị EDUCATION và 54 giá trị MARRIAGE được quy đổi đúng notebook; toàn bộ 30.000 nhãn được giữ, tỷ lệ vỡ nợ thực tế 22,12%. Luồng đọc CSV → chuẩn hóa → dự báo RF → lưu MySQL → hiện output/dashboard mất 6,761 giây ở một lượt đo; không phải số đo 10.000 dòng của đợt trước.

Ở chế độ PD ≥ 50%, RF cho PD trung bình 22,3348%, 3.741 cảnh báo và 3.741 hồ sơ High (cùng ngưỡng 50%). Nhóm Low 19.143, Medium 7.116, High 3.741. CSV output xuất đủ 30.000 dòng. Dataset và ba lượt dự báo được giữ trong database để người dùng mở và thao tác.

Ba mô hình đối chiếu với tập test độc lập 6.000 dòng gốc: RF AUC 0,7768596747239308; LR 0,748133507905328; XGB 0,7821740792840464. Đều khớp metadata ở sai số dưới 1e-9. Đã chạy hàm giải thích thực cho cả ba mô hình. Các chỉ số trên file UCI toàn bộ 30.000 dòng trong màn So sánh được gắn rõ là đánh giá trên file có cả dữ liệu huấn luyện, không thay thế test gốc.

Kiểm thử mới gồm chuẩn hóa UCI, giữ nhãn/không coi nhãn thiếu là 0, cache tách theo mô hình/cơ sở ngưỡng, xóa dòng cuối mà vẫn giữ lịch sử, chuyển chỉ đầu vào và cách ly bản sao, biểu đồ có/không có nhãn, tự chạy khi upload, đổi mô hình có tính lại kết quả, và metadata trong output.

Đã chạy lại kiểm tra MySQL sau thay đổi: 10.000 dòng nhập → dự báo → lưu/đọc lại trong 1,587 giây, revision và xuất XLSX qua; dữ liệu kiểm thử tạm đã dọn đúng phạm vi.
# Web acceptance · 2026-10-31

73 pytest tests passed on the migration checkout, including 17 web/API tests and the existing model, data, Excel and desktop tests. Ruff and JavaScript syntax checks passed. Browser acceptance passed 12 checks: original RF probabilities, filtered Excel download, distinct LR/XGBoost inference and explanations, three-model comparison, new dataset revisions, preservation of historical snapshots, and revised-input inference. IndexedDB data survived a reload. Desktop and 390px mobile views were inspected, with no document-wide horizontal overflow and no browser console errors.

MongoDB connection requires a real Atlas URI. Tests cover workspace-key authorization, hashed scoping and configuration-disabled behavior; a live Atlas connection has not been verified without credentials. Linux web CI uses the production dependency set and downloads SHA256-verified model handoffs.
