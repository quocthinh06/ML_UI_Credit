# Đăng nhập và phân hệ Admin

Tham chiếu: `Dac_ta_phan_he_Admin_MLBA.docx` phiên bản 1.0 do người dùng cung cấp ngày 2026-10-31. Quyền Analyst được chốt lại trực tiếp: toàn quyền thêm/sửa/xóa dữ liệu của mình, chỉ xem dữ liệu của mình. Các chỉ dẫn trong tài liệu được dùng làm yêu cầu tham chiếu, không tự động mở rộng sang huấn luyện hoặc triển khai mô hình mới.

## Các màn hình và quyền đã xây dựng

- `/login`: giao diện đồng bộ với CreditRisk AI, đăng nhập bằng username/email và mật khẩu; vai trò lấy từ backend, không cho tự chọn quyền Admin.
- `/change-password`: đổi mật khẩu, bắt buộc với tài khoản mới và tài khoản được đặt lại mật khẩu.
- Analyst: dự báo, xem dashboard, lịch sử và toàn quyền thêm/sửa/xóa dữ liệu làm việc của chính tài khoản. Server lấy chủ kho từ phiên đăng nhập; query tài khoản khác bị từ chối. Mỗi tài khoản dùng cache IndexedDB riêng.
- `/admin`: tổng quan tài khoản, quản lý tài khoản, các kho dữ liệu theo người dùng, các model tích hợp và nhật ký. Admin có thể mở kho theo tài khoản để quản lý dữ liệu.
- Quản lý tài khoản: tạo, đổi tên/vai trò, khóa/mở khóa, đặt lại mật khẩu; không cung cấp đăng ký công khai. Khóa tài khoản hoặc đổi quyền/mật khẩu làm hết hiệu lực phiên cũ.
- Không được khóa hoặc hạ quyền Admin cuối cùng. Thay đổi tài khoản thực hiện trong MongoDB transaction có khóa ghi dùng chung, tránh hai Admin đồng thời làm mất Admin cuối cùng.
- Nhật ký: đăng nhập thành công/thất bại, đăng xuất, tạo/cập nhật tài khoản, đổi mật khẩu, dự báo, lưu phiên bản dữ liệu, kích hoạt/rollback và các thao tác admin bị từ chối. Không lưu mật khẩu vào nhật ký.
- Model: cho phép chọn model mặc định giữa các bundle tích hợp có đánh giá và quay lại model trước kèm lý do. Không đổi các kết quả lịch sử.

## Phần chưa triển khai

Huấn luyện phiên bản mới, worker chạy nền, upload artifact và quy trình đánh giá phiên bản mới chưa được triển khai. Nút huấn luyện bị vô hiệu hóa và ghi rõ chưa khả dụng. Kích hoạt/rollback hiện chỉ áp dụng các bundle tích hợp sẵn, chưa phải vòng đời đầy đủ cho model huấn luyện mới.

## Kích hoạt trên Vercel

Tại Settings → Environment Variables của project, cấu hình:

| Biến | Giá trị |
| --- | --- |
| `MONGODB_URI` | Connection string MongoDB Atlas có quyền đọc/ghi, cluster hỗ trợ transaction |
| `MONGODB_DATABASE` | Mặc định `creditrisk_ai` |
| `SESSION_SECRET` | Khóa ngẫu nhiên tối thiểu 32 ký tự, dùng chung giữa các instance |
| `INITIAL_ADMIN_USERNAME` | Tên tài khoản Admin đầu tiên, 3–100 ký tự |
| `INITIAL_ADMIN_PASSWORD` | Mật khẩu tạm tối thiểu 10 ký tự; nhập trực tiếp trong Vercel |
| `AUTH_ENABLED` | `1` để bắt buộc đăng nhập cho khu phân tích và API |

Có thể tạo khóa phiên bằng `python -c "import secrets; print(secrets.token_hex(32))"`. Không đưa khóa, URI hoặc mật khẩu vào GitHub. Redeploy sau khi cấu hình. Đăng nhập tài khoản Admin ban đầu, đổi mật khẩu riêng rồi cấp tài khoản chuyên viên. Có thể bỏ `INITIAL_ADMIN_PASSWORD` sau khi tài khoản đã được tạo.

Khi chưa có MongoDB/khóa phiên, màn hình login hiển thị chưa cấu hình và không nhận đăng nhập. `AUTH_ENABLED=0` giữ bản công khai hiện tại để tránh khóa người dùng trước khi có nơi lưu tài khoản. Trong chế độ này chưa được coi là hệ thống nhiều người dùng đã kích hoạt.

## Kiểm soát bảo mật và kiểm thử

### Chẩn đoán lỗi Atlas từ chối xác thực

`MONGO_AUTH_FAILED` xảy ra ở kết nối **Database User**, trước khi kiểm tra tài khoản web. Đổi `INITIAL_ADMIN_PASSWORD` không sửa mật khẩu Database User. Không dùng mật khẩu đăng nhập website Atlas để kết nối database.

1. Atlas → Database Access → chọn Database User của ứng dụng, ví dụ `creditrisk_app`. Kiểm tra đúng project/cluster và đặt lại mật khẩu tại đây nếu không chắc mật khẩu hiện tại. Ứng dụng chỉ cần `readWrite` trên database đích.
2. Atlas → cluster → Connect → Drivers: lấy URI. Thay cả `<db_username>` và `<db_password>`; không giữ dấu `< >`. Nếu mật khẩu nằm trong URI, percent-encode riêng mật khẩu đúng một lần. Kiểm tra `authSource` phù hợp; SCRAM Database Users Atlas dùng `admin`.
3. Hoặc dùng URI chỉ chứa host/options cùng **hai Secret** `MONGODB_USERNAME`, `MONGODB_PASSWORD`. Driver nhận mật khẩu nguyên bản, không encode; `MONGODB_AUTH_SOURCE` mặc định `admin`. Nếu URI đã có user/password thì hai biến riêng sẽ ghi đè thông tin đó; chọn một cách và bỏ các override cũ không dùng.
4. Cập nhật Secret trực tiếp trong Vercel → project → Settings → Environment Variables → Production. Không đưa URI/mật khẩu vào chat, issue hoặc PR. Redeploy để deployment mới nhận cấu hình.
5. Đăng nhập bằng `INITIAL_ADMIN_USERNAME` và mật khẩu ứng dụng ban đầu, rồi đổi mật khẩu theo yêu cầu. Mật khẩu này khác Database User.

Nguồn: [MongoDB Atlas troubleshooting](https://www.mongodb.com/docs/atlas/troubleshoot-connection/).

Local: sao chép `.env.example` thành `.env`, điền bí mật trên máy riêng. `python main.py` và script bên dưới tự đọc `.env`, không ghi đè biến đã được hệ điều hành cấp. `.env` bị Git bỏ qua. Không đóng gói `.env` vào deploy; dùng biến môi trường Vercel.

```powershell
python tools/verify_mongodb.py
# Chỉ khi cần khởi tạo tài khoản Admin và chỉ mục (có ghi database):
python tools/verify_mongodb.py --bootstrap
```

Lệnh mặc định chỉ ping và đọc kiểm tra Admin, không in URI, mật khẩu hoặc tên tài khoản. `READY` xác nhận kết nối/đọc tài khoản, chưa thay thế kiểm thử đăng nhập và lưu snapshot/transaction thật. Mã khác: `AUTH_CONFIGURATION_MISSING`, `MONGO_CONFIGURATION_INVALID`, `MONGO_AUTH_FAILED`, `MONGO_PERMISSION_DENIED`, `MONGO_UNREACHABLE`, `ADMIN_NOT_INITIALIZED`. HTTP lỗi MongoDB trả `code` tương ứng; log server chỉ ghi mã lỗi, không ghi exception chứa connection string.

Vercel chỉ tự bắt buộc đăng nhập khi không đặt `AUTH_ENABLED`. Giá trị `AUTH_ENABLED=0` vẫn là lựa chọn demo công khai; đặt rõ `1` cho môi trường nhiều người dùng.

Mật khẩu dùng scrypt của Werkzeug. Cookie phiên HttpOnly, SameSite=Lax và Secure trên Vercel; session ngẫu nhiên chỉ lưu hash phía MongoDB, hết hạn sau 8 giờ. Kiểm tra tài khoản đang hoạt động và phiên bản quyền ở mỗi yêu cầu. Các request ghi đã đăng nhập cần CSRF token. Giới hạn đăng nhập sai 5 lần trong 15 phút theo tài khoản/địa chỉ yêu cầu.

Test `tests/test_auth.py` dùng MongoDB mock để kiểm tra đăng nhập, quyền API, phân tách dữ liệu, CRUD qua phiên bản, thu hồi phiên, Admin cuối cùng, CSRF, tài khoản mới, đổi mật khẩu, nhật ký, giới hạn đăng nhập và kích hoạt/rollback model. MongoDB transaction/GridFS với Atlas thật cần kiểm thử tích hợp sau khi có connection string. Không mô tả MongoDB mock là kết quả nghiệm thu production.
