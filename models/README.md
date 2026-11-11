# Bộ mô hình triển khai

Nguồn nhóm cung cấp: [thư mục Google Drive](https://drive.google.com/drive/folders/1lDZT2KGsUv6lD0mHi7n-tJOXzBa5MwcG).

Chạy `python tools/download_model.py` để tải cả Random Forest mặc định, Logistic Regression và XGBoost. Script đối chiếu SHA256:

```text
19d97aeff847a990ea1a3f6c27f95975e41df9275d7e8913084c16c98c865f48
```

Ba mô hình và `impute_stats_v1.pkl` được lưu trong Git; `python tools/vercel_build.py` kiểm tra SHA256 khi build Vercel. Pipeline dùng imbalanced-learn 0.14.2, scikit-learn 1.6.1 và pandas 2.2.3 theo metadata bàn giao. XGBoost 3.4.1 được cài để chạy mô hình XGBoost của nhóm.

Thống kê điền thiếu có SHA256 `7dab4cbe963f5366036fa5d4fc2af694180baad4ad929b11b61144da12f4e38c`. Theo yêu cầu cập nhật ngày 11/11/2026, web chỉ điền SEX, EDUCATION, MARRIAGE bằng mode; AGE và PAY_AMT6 bằng median tập train. 18 trường còn lại bắt buộc ở mọi dòng để tính đầy đủ các đặc trưng trong biểu đồ nhóm cung cấp; không nhận đặc trưng dẫn xuất thay cho dữ liệu gốc. Không điền nhãn và không thay dữ liệu sai bằng thống kê. Quy tắc này thay thế đề xuất cũ điền mọi trường nếu thiếu dưới 50%.

API nhập tệp và dự báo trả báo cáo `imputation` gồm dòng/ID, trường, giá trị đã điền và hash bộ thống kê. Báo cáo nhập tệp được lưu theo phiên bản dataset và tải được dưới dạng JSON. Dự báo đơn lẻ lưu báo cáo trong bản nháp và kết quả lịch sử. SHAP tự xuất hiện dưới kết quả, giải thích đầu vào sau khi điền; đóng góp vào điểm trước hiệu chỉnh, không phải phần trăm PD hay quan hệ nhân quả.

Bundle phải có `pipeline`, `threshold`, `features`, `calibrator`, `model_name`, `versions`. Tên 38 đặc trưng phải khớp đầu ra `creditrisk/features.py`. Công thức đặc trưng và 3 hồ sơ kiểm thử lấy từ `notebooks/04_use_model .ipynb` trên Drive, không thực thi các cell notebook khi chạy ứng dụng.

Chỉ nạp pickle/joblib từ nguồn nhóm tin cậy vì định dạng này có thể thực thi mã Python. Đổi sang một bundle khác bằng `model_path` trong `config.local.json`; cần giữ đúng hợp đồng đặc trưng và thư viện của bundle. Để chạy bundle XGBoost của nhóm phải cài đúng phiên bản XGBoost tương ứng trước.

Bộ XGBoost có SHA256 `8a0e0763ffbf7239227b8a1d21031291e4a5bf9f46cca92f3eaa74c73dc3da5a`. Snapshot gốc không nạp trực tiếp được trên Windows. `xgb_compat.py` chỉ áp dụng cho đúng hash này, đọc thành phần Model sang JSON portable, giữ nguyên cây/trọng số. Bộ giải mã UBJSON được sửa lỗi đọc trước ở mảng rỗng trong một namespace riêng, không sửa thư viện cài đặt. AUC trên 6.000 dòng test khớp chính xác metadata 0,7821740792840464. Không áp dụng cơ chế này cho pickle khác.
