# Bộ mô hình triển khai

Nguồn nhóm cung cấp: [thư mục Google Drive](https://drive.google.com/drive/folders/1lDZT2KGsUv6lD0mHi7n-tJOXzBa5MwcG).

Chạy `python tools/download_model.py` để tải `best_model_v1.pkl`. Script đối chiếu SHA256:

```text
19d97aeff847a990ea1a3f6c27f95975e41df9275d7e8913084c16c98c865f48
```

File nhị phân được giữ cục bộ, không commit. Pipeline dùng imbalanced-learn 0.14.2, scikit-learn 1.6.1 và pandas 2.2.3 theo metadata bàn giao. XGBoost không cần cài để chạy Random Forest này.

Bundle phải có `pipeline`, `threshold`, `features`, `calibrator`, `model_name`, `versions`. Tên 38 đặc trưng phải khớp đầu ra `creditrisk/features.py`. Công thức đặc trưng và 3 hồ sơ kiểm thử lấy từ `notebooks/04_use_model .ipynb` trên Drive, không thực thi các cell notebook khi chạy ứng dụng.

Chỉ nạp pickle/joblib từ nguồn nhóm tin cậy vì định dạng này có thể thực thi mã Python. Đổi sang một bundle khác bằng `model_path` trong `config.local.json`; cần giữ đúng hợp đồng đặc trưng và thư viện của bundle. Để chạy bundle XGBoost của nhóm phải cài đúng phiên bản XGBoost tương ứng trước.
