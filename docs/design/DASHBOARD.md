# Dashboard Tổng quan — triển khai và kiểm chứng

Ngày ghi nhận: 2026-11-15. Đây là tài liệu cho phần mở rộng dashboard theo mock C đã được duyệt (`.impeccable/mocks/dashboard-c.png`), trong hệ thống “Sổ tay phân tích” hiện hữu. `PRODUCT.md`, `DESIGN.md` và `.impeccable/design.json` tiếp tục là nguồn quy ước chung; lượt tài liệu hóa này không sửa các tệp đó.

## Bố cục và hành vi đã triển khai

- Phiếu chạy thống nhất hai hàng: hàng chọn dataset, phiên bản/số hồ sơ và tải tệp; hàng xác nhận model, ngưỡng, số trường đầu vào và một nút “Chạy dự báo & lưu”. Không còn bộ chọn dataset hoặc nút chạy trùng trong Tổng quan.
- Panel “Đọc kết quả” chứa bốn metric inline: hồ sơ sau lọc, PD trung bình, hồ sơ rủi ro cao và hồ sơ cảnh báo. Chưa có kết quả thì hiển thị dấu gạch và nội dung chờ; không dùng số liệu của mock làm kết quả.
- Chế độ “Rủi ro dự báo” hiển thị phân bố PD đã hiệu chỉnh và cơ cấu Thấp / Trung bình / Cao với số lượng, tỷ lệ và nhãn chữ. Đường ngưỡng trên biểu đồ PD chỉ xuất hiện khi cơ sở quyết định là xác suất; ngưỡng điểm thô có biểu đồ riêng.
- Disclosure “Phân tích bổ sung và thông tin lượt chạy” giữ ngữ cảnh dataset/phiên bản/model/ngưỡng/phạm vi lọc, insight, trạng thái hồ sơ, PD theo tuổi và nhãn cảnh báo. Biểu đồ ngưỡng điểm thô xuất hiện khi cấu hình dùng điểm thô.
- Bộ chọn biểu đồ vẫn có “Khám phá dữ liệu” (tuổi, hạn mức TWD, học vấn, trạng thái trả nợ) và “Đánh giá với nhãn thực tế” (ma trận nhầm lẫn, ROC, chỉ số, phân bố nhãn). Đánh giá báo thiếu nhãn hợp lệ hoặc thiếu hai lớp thay vì tạo kết quả giả.
- Bộ lọc mặc định đóng, summary phản ánh điều kiện hiện hành. Bảng tra cứu, metric, biểu đồ và xuất kết quả dùng cùng phạm vi lọc; nút “Dự báo đơn lẻ” mở dự báo cho hồ sơ đang chọn và cho phép quay lại. Phần “Hoạt động dự báo gần đây” đã bỏ khỏi Tổng quan theo yêu cầu; các lượt chạy truy cập tại màn hình Lịch sử dự báo (`#history`), tách riêng với Quản lý dữ liệu (`#datasets`); mỗi màn hình có một mục sidebar.
- Trên màn hình hẹp, phiếu chạy xếp dọc và biểu đồ một cột; metric còn hai cột. Biểu đồ PD giữ chiều rộng đọc nhãn và cuộn trong vùng riêng, có tên vùng, nhận focus bàn phím và viền focus nhìn thấy.

Nguồn đối chiếu: `frontend/index.html` (Tổng quan), các quy tắc dashboard trong `frontend/static/app.css`, `renderOverview`, `barChart`, `renderFilterSummary`, `exportCurrent` và `openRun` trong `frontend/static/app.js`.

## Đối chiếu PRODUCT và DESIGN

Giữ sidebar navy, thao tác xanh, font Be Vietnam Pro tự phục vụ, nền sáng, panel trắng và các token màu/viền hiện hữu. CSS bố cục dashboard chủ yếu giới hạn dưới `#page-overview`; vùng cuộn biểu đồ dùng helper chung. Nhãn rủi ro đi cùng màu; PD, điểm thô, ngưỡng quyết định và nhãn thực tế vẫn được phân biệt.

Metric inline không còn viền trên, bóng hay hình thức thẻ độc lập; đây là biến thể cục bộ trong panel kết quả, khác mô tả metric mặc định của DESIGN. Chart card trong Tổng quan dùng góc bo 10px và bỏ bóng, thay vì panel mặc định 14px. Đây là khác biệt thành phần tại màn hình đã duyệt, không phải cập nhật token toàn hệ thống. Không ghi nhận thay đổi thế giới thị giác toàn cục từ phần mở rộng này.

Không thêm dependency; không thay model, hợp đồng API, cơ chế lưu trữ hoặc quyền backend.

## Kết quả kiểm chứng của lượt triển khai

- 48 kiểm thử Node cho workflow và đăng nhập đạt.
- Trình duyệt: chạy RF thật trên 3 hồ sơ mẫu; lọc rủi ro cao còn 1/3; xuất XLSX; mở chi tiết/quay lại; đổi chế độ biểu đồ; đổi model ẩn kết quả cũ. Lỗi 503 được chèn để kiểm tra: dữ liệu vẫn còn và thử lại khôi phục được. Không tràn ngang toàn trang ở chiều rộng 1280, 1600 và 390px; summary bộ lọc mở/đóng bằng Enter.
- `node --check` và `git diff --check` trên bốn tệp triển khai/kiểm thử đã sửa đạt; Git chỉ thông báo quy đổi line ending.
- Review thị giác độc lập xác nhận bốn vấn đề trọng yếu đã được xử lý và đưa verdict “ship on visual finish review”. Đây là kết luận review thị giác, không thay thế kết quả so ảnh cơ học.
- Hero gate cơ học vẫn **chưa đạt**: `.impeccable/review/diff/hero/report.json` ghi overall `0.7821` (khoảng 78%), verdict `drift`, còn các vùng bị veto. Không diễn giải điểm này thành kiểm chứng khớp mock đã đạt.

Ảnh desktop/mobile của lượt kiểm tra nằm tại `.impeccable/review/desktop.png` và `.impeccable/review/mobile.png`. Ảnh, mock và cấu hình Impeccable đang bị Git ignore; chúng là bằng chứng local, không mặc nhiên đi kèm checkout.

## Giới hạn kiểm chứng

Các kết quả chạy ứng dụng và review ở trên được tổng hợp từ lượt triển khai; lượt tài liệu hóa chỉ đối chiếu mã nguồn và báo cáo hero local, không chạy lại toàn bộ quy trình. Browser smoke test dùng mẫu 3 hồ sơ, chưa chứng minh tải tối đa 30.000 hồ sơ hoặc toàn bộ tổ hợp model/ngưỡng/trình duyệt.

`test_web` với Python trong `.venv`: 25 đạt, 1 lỗi do NumPy/OpenBLAS DLL trên đường dẫn chứa ký tự ngoài ASCII. Python hệ thống thiếu `sqlalchemy`. Hai môi trường này không được thay đổi trong lượt dashboard; chưa thể kết luận toàn bộ kiểm thử Python đạt.
