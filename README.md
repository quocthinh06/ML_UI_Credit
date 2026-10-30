# CreditRisk AI · Nhóm 4

Ứng dụng desktop **PyQt6 + MySQL** dự báo nguy cơ vỡ nợ tín dụng. Giao diện tham khảo ảnh trong `ML_UI_Credit.zip`; nghiệp vụ dựa trên báo cáo và bộ mô hình nhóm cung cấp. Không dùng Flask/FastAPI hoặc giao diện web.

## Chạy trên Windows

Yêu cầu Python 3.11 hoặc 3.12, MySQL Server 8.0 đang chạy. MySQL Workbench dùng để quản lý server và xem dữ liệu; Workbench không thay thế MySQL Server.

1. Chạy `Setup.cmd` để cài thư viện và tải đúng mô hình từ Drive, có đối chiếu SHA256. Môi trường Python nằm ở `%USERPROFILE%\.creditrisk-ai\venv`, tránh lỗi OpenBLAS khi môi trường nằm trong đường dẫn tiếng Việt.
2. Chạy [sql/setup.sql](sql/setup.sql) trong MySQL Workbench để tạo `Default_Credit` nếu chưa có.
3. Điền tài khoản MySQL vào `config.local.json` (được tạo từ `config.example.json`). File này bị Git bỏ qua. Có thể truyền mật khẩu bằng biến môi trường `CREDITRISK_DB_PASSWORD`. Máy đã được cấu hình trong phiên bàn giao không cần nhập lại.
4. Chạy `Run.cmd`.

Trong Workbench: kết nối `localhost:3306`, chọn schema `Default_Credit`, Refresh All, mở Tables. Ứng dụng tự tạo 5 bảng khi kết nối: `datasets`, `dataset_versions`, `customer_records`, `prediction_runs`, `predictions`.

## Các luồng sử dụng

- **Tổng quan:** số hồ sơ hiện tại, số hồ sơ rủi ro cao, số hồ sơ cần dự báo lại, số tệp; lọc trạng thái. Chỉ tính phiên bản mới nhất và lần chạy mới nhất, không cộng trùng lịch sử.
- **Quản lý dữ liệu:** nhập CSV UTF-8 hoặc `.xlsx`, kiểm tra toàn bộ hồ sơ trước khi lưu; xem dữ liệu và các phiên bản; bổ sung hoặc cập nhật theo ID; lưu thành bản mới; xuất CSV/Excel.
- **Một hồ sơ đơn lẻ:** nhập đủ 23 trường và ID, chạy dự báo, xem kết quả rồi xác nhận lưu. Có thể lưu thành tệp riêng hoặc thêm/cập nhật vào tệp đã lưu. Sửa đầu vào hoặc ngưỡng sẽ vô hiệu kết quả đang xem, cần chạy lại trước khi lưu.
- **Hàng loạt:** chọn tệp đã lưu, đặt ngưỡng, chạy và lưu kết quả trong giao dịch. Tìm theo ID, lọc mức rủi ro/PD tối thiểu và xuất đúng các dòng đang lọc.
- **Kết quả & Lịch sử:** mở lại từng lần chạy, gồm dữ liệu đầu vào, kết quả, ngưỡng, phiên bản và SHA256 mô hình. Thời gian lưu/hiển thị là UTC.

Ví dụ thử nhanh: nhập [examples/sample_customers.csv](examples/sample_customers.csv), gồm **3 hồ sơ tổng hợp minh họa trong notebook của nhóm**, sau đó chạy hàng loạt. Đây không phải thông tin của khách hàng thật.

## Dữ liệu và ý nghĩa kết quả

23 trường UCI: `LIMIT_BAL`, `SEX`, `EDUCATION`, `MARRIAGE`, `AGE`; `PAY_0`, `PAY_2`…`PAY_6`; `BILL_AMT1`…`BILL_AMT6`; `PAY_AMT1`…`PAY_AMT6`. `ID` là định danh trong từng tệp; thiếu ID thì sinh số thứ tự. Có thể dùng `PAY_1` thay `PAY_0`, nhưng không được có cả hai. `ID` không đưa vào mô hình. Các cột bổ sung như nhãn thực tế không đưa vào suy luận và không lưu trong bản dữ liệu chuẩn hóa.

Tiền trong bộ UCI tính bằng **TWD**, không đổi thành VND. Không suy ra 23 trường UCI từ DPD/DTI trong mockup. Trường thiếu, NaN, vô hạn, giá trị ngoài miền và ID trùng bị từ chối; không tự điền dữ liệu thiếu.

Mô hình triển khai là `best_model_v1.pkl`, Random Forest của nhóm:

- `raw_score`: điểm thô của pipeline, so với ngưỡng mặc định **0,39** để ra `default_label` 0/1.
- `probability`: PD sau hiệu chỉnh isotonic, dùng để hiển thị và phân nhóm Low / Medium / High, mặc định **20% / 50%**.
- Nhãn 1 nghĩa là **cảnh báo rủi ro**, không khẳng định khách hàng sẽ vỡ nợ. Hồ sơ có PD 25,41% vẫn có thể có nhãn 1 vì điểm thô vượt 0,39.

Ngưỡng có thể chỉnh trước mỗi lần chạy và được lưu cùng kết quả. Không dùng 0,39 làm ngưỡng của PD đã hiệu chỉnh. 15 đặc trưng dẫn xuất được chép đúng công thức notebook; mô hình nhận đủ 38 trường theo thứ tự trong bộ bàn giao. Xem [models/README.md](models/README.md).

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
```

Dữ liệu, mô hình và tệp đều được xử lý trong QThread; giao diện cập nhật qua signal. SQLAlchemy dùng tham số ràng buộc; mỗi lần lưu có giao dịch, phiên bản cũ không bị ghi đè. Cập nhật một tệp tạo bản chụp mới; các hồ sơ chưa được dự báo trên bản mới được đánh dấu cần dự báo lại. Trường hợp chỉ lưu dự báo đơn lẻ vào tệp, chỉ hồ sơ đó có kết quả mới, các hồ sơ còn lại cần chạy hàng loạt lại. Muốn khôi phục: mở phiên bản cũ tại Quản lý dữ liệu, chọn **Lưu thành bản mới**.

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

Xem kết quả đo thực tế và giới hạn tại [TESTING.md](TESTING.md).

## Phạm vi bàn giao

Đây là ứng dụng đồ án chạy cục bộ; chưa có đăng nhập/phân quyền nhiều người dùng, mã hóa dữ liệu lưu trên đĩa, SHAP từng hồ sơ hay quy trình phê duyệt khoản vay. Không hiển thị số hiệu năng hoặc giải thích AI giả từ ảnh mẫu. Kết nối server từ xa cần cấu hình TLS qua `mysql.ssl_ca`; mã hóa ổ đĩa/backup và quyền truy cập do môi trường triển khai quản lý. Không đưa thông tin đăng nhập, tệp khách hàng hoặc mô hình nhị phân vào Git.
