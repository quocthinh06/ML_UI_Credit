# CreditRisk AI · Nhóm 4

Ứng dụng desktop **PyQt6 + MySQL** dự báo nguy cơ vỡ nợ tín dụng. Giao diện tham khảo ảnh trong `ML_UI_Credit.zip`; nghiệp vụ dựa trên báo cáo và bộ mô hình nhóm cung cấp. Không dùng Flask/FastAPI hoặc giao diện web.

## Chạy trên Windows

Yêu cầu Python 3.11 hoặc 3.12, MySQL Server 8.0 đang chạy. MySQL Workbench dùng để quản lý server và xem dữ liệu; Workbench không thay thế MySQL Server.

1. Chạy `Setup.cmd` để cài thư viện và tải đúng mô hình từ Drive, có đối chiếu SHA256. Môi trường Python nằm ở `%USERPROFILE%\.creditrisk-ai\venv`, tránh lỗi OpenBLAS khi môi trường nằm trong đường dẫn tiếng Việt.
2. Chạy [sql/setup.sql](sql/setup.sql) trong MySQL Workbench để tạo `Default_Credit` nếu chưa có.
3. Điền tài khoản MySQL vào `config.local.json` (được tạo từ `config.example.json`). File này bị Git bỏ qua. Có thể truyền mật khẩu bằng biến môi trường `CREDITRISK_DB_PASSWORD`. Máy đã được cấu hình trong phiên bàn giao không cần nhập lại.
4. Chạy `Run.cmd`.

Trong Workbench: kết nối `localhost:3306`, chọn schema `Default_Credit`, Refresh All, mở Tables. Ứng dụng tự tạo 5 bảng khi kết nối: `datasets`, `dataset_versions`, `customer_records`, `prediction_runs`, `predictions`.

## Tải CSV để có kết quả

Bấm **Tải CSV / Excel và dự báo** ở Tổng quan, hoặc **Nhập CSV / Excel** trong Quản lý dữ liệu. Chọn file; ứng dụng tự kiểm tra → chuẩn hóa theo notebook → dự báo bằng mô hình đang chọn → lưu MySQL → mở output và cập nhật dashboard. Có thể tải CSV UTF-8, XLSX hoặc JSON dạng danh sách hồ sơ.

Với `UCI_Credit_Card.csv` gốc gồm 30.000 dòng, ứng dụng chuẩn hóa `EDUCATION` 0/5/6 về 4 và `MARRIAGE` 0 về 3 đúng bước huấn luyện; thông báo số giá trị đã đổi. Các cột `source_EDUCATION`, `source_MARRIAGE` giữ mã gốc khi có chuẩn hóa. Không tự điền trường thiếu. Sai cấu trúc, giá trị không hữu hạn, mã khác ngoài miền cho phép hoặc ID trùng được báo lỗi trước dự báo.

Output gồm 23 đầu vào, ID, `raw_score`, `probability` (PD), `default_label`, `risk_level`, ngưỡng và cơ sở ngưỡng, phiên bản và SHA256 mô hình, mã lần chạy, phiên bản dữ liệu, thời điểm UTC và người thực hiện (tài khoản Windows). `default.payment.next.month` được giữ nếu có để tính thống kê thực tế, **không đưa nhãn vào mô hình**. Nhãn trống/không hợp lệ không được tính là không vỡ nợ.

## Các luồng sử dụng

- **Tổng quan:** chọn tệp và Phân tích; biểu đồ mức rủi ro, PD, PD theo tuổi, nhãn cảnh báo; chuyển sang khám phá tuổi/hạn mức/học vấn/trả nợ, hoặc ma trận nhầm lẫn/ROC/chỉ số trên file có nhãn. Thanh công cụ biểu đồ hỗ trợ phóng to, di chuyển và lưu hình. Các chỉ số danh mục phía trên tính phiên bản hiện tại theo mô hình đang chọn; biểu đồ phía dưới chỉ thuộc tệp có tên trong phần chú thích.
- **Quản lý dữ liệu:** xem số dòng/trạng thái/lần cập nhật; thêm, sửa, xóa dòng; chọn cập nhật dataset hiện tại (lưu bản cũ trong lịch sử) hoặc tạo bản sao rồi sửa. Có thể xem phiên bản cũ và lưu thành tệp mới để khôi phục. Xóa dòng không xóa lịch sử dự báo.
- **Một hồ sơ đơn lẻ:** nhập đủ 23 trường và ID, dự báo và lưu kết quả đơn lẻ thành tệp riêng. Chọn tệp nhận ở danh sách và bấm **Chuyển đầu vào sang dataset hàng loạt** để chỉ chuyển dữ liệu đầu vào, với lựa chọn bản hiện tại/bản sao và xác nhận trùng ID. Lượt dự báo hàng loạt sẽ tính lại bằng mô hình đang chọn, không kế thừa kết quả đơn lẻ.
- **Hàng loạt:** tự chạy khi tải file mới hoặc bấm Chạy dự báo với tệp đã lưu. Lọc ID, mức rủi ro, khoảng PD, khoảng tuổi, khoảng hạn mức, PAY_0 tối thiểu và nhãn cảnh báo. Xuất đúng các dòng sau lọc sang CSV/XLSX; đặt bộ lọc về toàn bộ để xuất tất cả.
- **Chọn mô hình:** danh sách phía trên gồm Random Forest (mặc định theo CV AUC), Logistic Regression và XGBoost. Khi đổi, ứng dụng chạy lại hoặc mở cache phù hợp với **cùng dữ liệu, mô hình và toàn bộ ngưỡng**; không chỉ đổi tên trên kết quả cũ. Các lượt khác nhau luôn được giữ trong lịch sử.
- **Hiệu năng mô hình:** CV AUC và test AUC gốc từ bundle; nút so sánh ba mô hình trên file đang chọn khi có nhãn. Số đo trên file tải lên được tách khỏi chỉ số test gốc: nếu file chứa dữ liệu huấn luyện thì đó không phải đánh giá độc lập.
- **Giải thích đơn lẻ:** Random Forest/XGBoost dùng Tree SHAP thực, Logistic Regression hiển thị hệ số nhân giá trị đã biến đổi. Đây là đóng góp vào điểm thô/log-odds, không phải phần trăm PD sau isotonic.
- **Lịch sử:** mở lại bất kỳ lượt đã lưu sau khi khởi động lại. Sửa dữ liệu hoặc cấu hình vô hiệu kết quả hiện tại, nhưng không đổi kết quả và ngưỡng cũ. Thời gian là UTC.

## Ngưỡng và đơn vị

Tài liệu có hai quy ước. Ứng dụng hiển thị rõ chế độ được chọn:

1. **PD hiệu chỉnh (mặc định BRD):** ngưỡng nhãn 50%; nhãn 1 khi PD ≥ ngưỡng.
2. **Điểm thô (nghiệm thu notebook):** chọn chế độ điểm thô; dùng ngưỡng của mô hình bàn giao, RF 0,39, LR 0,42, XGB 0,43. RF hồ sơ ranh giới PD 25,41% vẫn có nhãn 1 ở chế độ này.

Hai ngưỡng phân nhóm PD độc lập, mặc định 20%/50%: Low < 20%, Medium từ 20% đến dưới 50%, High ≥ 50%. Thay ngưỡng không thay PD; cấu hình được lưu cùng kết quả. Nhãn 1 là cảnh báo rủi ro, không khẳng định khách hàng sẽ vỡ nợ.

23 trường UCI gồm `LIMIT_BAL`, `SEX`, `EDUCATION`, `MARRIAGE`, `AGE`; `PAY_0`, `PAY_2`…`PAY_6`; `BILL_AMT1`…`BILL_AMT6`; `PAY_AMT1`…`PAY_AMT6`. Có thể dùng `PAY_1` thay `PAY_0`, không dùng đồng thời. ID không đưa vào mô hình; nếu thiếu thì sinh số thứ tự. Tiền tính bằng **TWD**, không đổi thành VND. Không tự suy ra 23 trường từ DPD/DTI của ảnh tham khảo.

Ví dụ nhỏ: [examples/sample_customers.csv](examples/sample_customers.csv). Xem nguồn và hợp đồng mô hình ở [models/README.md](models/README.md).

## Cấu trúc code

```text
main.py                    Khởi tạo QApplication
creditrisk/ui.py           View và điều phối thao tác PyQt6
creditrisk/qt_workers.py   QThread + signal, không sửa widget từ thread nền
creditrisk/table_model.py QAbstractTableModel cho bảng dữ liệu
creditrisk/validation.py  Hợp đồng 23 trường và ngưỡng
creditrisk/features.py    15 đặc trưng đúng notebook
creditrisk/inference.py   Nạp bundle thật, suy luận và hiệu chỉnh
creditrisk/database.py    Metadata 5 bảng, khóa ngoại, ràng buộc ID
creditrisk/service.py     Nhập/xuất, giao dịch, phiên bản và lịch sử
creditrisk/config.py      Cấu hình riêng, kết nối SQLAlchemy/PyMySQL
creditrisk/analytics.py   Thống kê dự báo và nhãn hợp lệ
creditrisk/charts.py      Biểu đồ Matplotlib nhúng PyQt6
creditrisk/xgb_compat.py  Đọc tương thích đúng snapshot XGBoost bàn giao
```

Dữ liệu, mô hình và tệp đều được xử lý trong QThread; giao diện cập nhật qua signal. SQLAlchemy dùng tham số ràng buộc; mỗi lần lưu có giao dịch, phiên bản cũ không bị ghi đè. Cập nhật một tệp tạo bản chụp mới; các hồ sơ chưa được dự báo trên bản mới được đánh dấu cần dự báo lại. Chuyển đầu vào đơn lẻ sang dataset tạo phiên bản cần dự báo lại; không gán kết quả đơn lẻ thành kết quả hàng loạt. Muốn khôi phục: mở phiên bản cũ tại Quản lý dữ liệu, chọn **Lưu thành bản mới**.

## Kiểm thử

```powershell
$py = "$env:USERPROFILE\.creditrisk-ai\venv\Scripts\python.exe"
& $py -m pip install -r requirements-dev.txt
& $py -m pytest -q
& $py -m ruff check .
& $py tools/verify_mysql.py
# Cần X_test.csv và y_test.csv gốc trong thư mục được chỉ định:
& $py tools/verify_handoff.py D:\duong_dan\processed
```

`verify_mysql.py` tạo 10.000 hồ sơ có ID tổng hợp, kiểm thử nhập → dự báo → lưu MySQL → đọc lại → phiên bản → xuất Excel, sau đó xóa **chỉ dữ liệu kiểm thử do script vừa tạo**. Không chạy lên database nghiệp vụ nếu không muốn phát sinh tải kiểm thử. Bộ pytest mặc định dùng SQLite tạm, không đụng MySQL. CI Windows chạy kiểm thử và nghiệm thu mô hình mẫu.

Xem kết quả đo thực tế tại [TESTING.md](TESTING.md), và đối chiếu chức năng với tài liệu tại [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).

## Phạm vi bàn giao

Đây là ứng dụng đồ án chạy cục bộ; chưa có đăng nhập/phân quyền nhiều người dùng, mã hóa dữ liệu lưu trên đĩa hay quy trình phê duyệt khoản vay. Không hiển thị số hiệu năng hoặc giải thích AI giả từ ảnh mẫu. Kết nối server từ xa cần cấu hình TLS qua `mysql.ssl_ca`; mã hóa ổ đĩa/backup và quyền truy cập do môi trường triển khai quản lý. Không đưa thông tin đăng nhập, tệp khách hàng hoặc mô hình nhị phân vào Git.
