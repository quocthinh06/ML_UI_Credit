# Bộ mô hình triển khai

Nguồn nhóm cung cấp: [thư mục Google Drive](https://drive.google.com/drive/folders/1lDZT2KGsUv6lD0mHi7n-tJOXzBa5MwcG).

Chạy `python tools/download_model.py` để tải cả Random Forest mặc định, Logistic Regression và XGBoost. Script đối chiếu SHA256:

```text
19d97aeff847a990ea1a3f6c27f95975e41df9275d7e8913084c16c98c865f48
```

File nhị phân được giữ cục bộ, không commit. Pipeline dùng imbalanced-learn 0.14.2, scikit-learn 1.6.1 và pandas 2.2.3 theo metadata bàn giao. XGBoost 3.4.1 được cài để chạy mô hình XGBoost của nhóm.

Bundle phải có `pipeline`, `threshold`, `features`, `calibrator`, `model_name`, `versions`. Tên 38 đặc trưng phải khớp đầu ra `creditrisk/features.py`. Công thức đặc trưng và 3 hồ sơ kiểm thử lấy từ `notebooks/04_use_model .ipynb` trên Drive, không thực thi các cell notebook khi chạy ứng dụng.

Chỉ nạp pickle/joblib từ nguồn nhóm tin cậy vì định dạng này có thể thực thi mã Python. Đổi sang một bundle khác bằng `model_path` trong `config.local.json`; cần giữ đúng hợp đồng đặc trưng và thư viện của bundle. Để chạy bundle XGBoost của nhóm phải cài đúng phiên bản XGBoost tương ứng trước.

Bộ XGBoost có SHA256 `8a0e0763ffbf7239227b8a1d21031291e4a5bf9f46cca92f3eaa74c73dc3da5a`. Snapshot gốc không nạp trực tiếp được trên Windows. `xgb_compat.py` chỉ áp dụng cho đúng hash này, đọc thành phần Model sang JSON portable, giữ nguyên cây/trọng số. Bộ giải mã UBJSON được sửa lỗi đọc trước ở mảng rỗng trong một namespace riêng, không sửa thư viện cài đặt. AUC trên 6.000 dòng test khớp chính xác metadata 0,7821740792840464. Không áp dụng cơ chế này cho pickle khác.
