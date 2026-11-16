# Dashboard Tổng quan — triển khai và kiểm chứng

## Bổ sung biểu đồ tròn — 2026-11-16

- Dùng SVG vành khuyên cho cơ cấu rủi ro, nhãn cảnh báo, trạng thái dự báo, học vấn (4 mã chuẩn hóa), giới tính và hôn nhân; phân bố nhãn thực tế chỉ dùng nhãn 0/1 hợp lệ, ghi rõ số hồ sơ bị loại khỏi mẫu số.
- Chú giải luôn có tên nhóm, số hồ sơ và tỷ trọng, kể cả nhóm bằng 0. Hover trên lát tròn có chi tiết và màu tương ứng; điện thoại đọc trực tiếp chú giải. Nhóm chiếm 100% vẽ đủ vòng; không có hồ sơ thì không vẽ lát.
- Biểu đồ kết quả dùng hồ sơ sau lọc. Trạng thái dự báo dùng toàn bộ phiên bản đang chọn và model hiện tại, ghi rõ không áp dụng bộ lọc. Không thay công thức dự báo hoặc nhãn, API, lưu trữ, bản desktop và báo cáo Excel.
- Giữ biểu đồ cột/đường cho PD, tuổi, hạn mức, PAY_0, PD trung bình theo tuổi, ma trận nhầm lẫn, ROC và các metric; các thang đo/chỉ số này không phải các phần của một tổng phù hợp với biểu đồ tròn.
- Kiểm thử JavaScript: 50/50 đạt, bao gồm tỷ trọng, nhóm 0/100%, trạng thái và phạm vi nhãn hợp lệ. Kiểm thử API bằng `.venv`: 25 đạt, 1 lỗi tại tải model thật (`/api/models`), trùng giới hạn môi trường đã ghi bên dưới. Kiểm tra trình duyệt dùng dữ liệu kiểm thử riêng, không lưu vào kho và không coi là kết quả dự báo thật.
- Trình duyệt: đã kiểm tra cả ba chế độ tại 1440px và 390px, không tràn ngang toàn trang; hover lát tròn trả đúng nhóm, số hồ sơ và tỷ trọng. Đã sửa xung đột chiều cao SVG với quy tắc icon chung. Ảnh local tại `docs/screenshots/dashboard-pie-desktop.png` và `dashboard-pie-mobile.png`.
- Khắc phục môi trường backend cùng ngày: tạo `%USERPROFILE%\.creditrisk-ai\web-venv`, cài `requirements.txt` để DLL NumPy nằm trong đường dẫn không dấu. Chạy lại `tests/test_web.py` và `tests/test_real_model.py` bằng môi trường này: **28/28 đạt**, gồm tải đủ RF/LR/XGBoost, dự báo và giải thích thật. Có một cảnh báo `qt_api` vì môi trường web không cài plugin Qt. Cập nhật lệnh local trong README; không thay mô hình hoặc mã suy luận.

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
