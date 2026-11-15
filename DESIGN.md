---
name: CreditRisk AI
description: Sổ tay phân tích rủi ro tín dụng, ưu tiên khả năng đọc và dữ liệu thực.
colors:
  primary: "#1d4ed8"
  deep: "#1e3a8a"
  bg: "#f3f6fc"
  paper: "#ffffff"
  ink: "#0f1b2d"
  muted: "#3d4d66"
  line: "#cfd8e6"
  nav: "#0a1424"
  soft: "#dbeafe"
  teal: "#047857"
  red: "#b91c1c"
  amber: "#92400e"
typography:
  headline:
    fontFamily: "Be Vietnam Pro, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.6px"
  body:
    fontFamily: "Be Vietnam Pro, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "16px"
    lineHeight: 1.6
  label:
    fontSize: "14px"
    fontWeight: 600
rounded:
  tag: "7px"
  control: "10px"
  panel: "14px"
spacing:
  control: "10px 20px"
  panel-heading: "18px 22px"
  main: "28px 30px 36px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "{spacing.control}"
  button-secondary:
    backgroundColor: "{colors.soft}"
    textColor: "{colors.deep}"
    rounded: "{rounded.control}"
  button-danger:
    backgroundColor: "{colors.red}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
  panel:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.panel}"
---

# Design System: CreditRisk AI

## Overview

**Creative North Star: "Sổ tay phân tích"**

Gọn gàng, điềm tĩnh, ưu tiên khả năng đọc. Giao diện tổ chức công việc phân tích bằng điều hướng navy, bề mặt sáng và các vùng dữ liệu có ranh giới rõ. Màu xanh dẫn thao tác; màu trạng thái giúp đọc rủi ro cùng nhãn chữ.

Nút rõ thao tác, ô nhập có viền rõ, thẻ phân lớp nhẹ; bóng giúp phân biệt bề mặt và menu. Đây là mô tả hệ thống đang triển khai, không phải yêu cầu thay giao diện. Định hướng và mô tả thành phần được người dùng xác nhận ngày 2026-11-15.

**Key Characteristics:**
- Chữ tiếng Việt dễ đọc, font lưu cùng ứng dụng.
- Điều hướng tối, vùng làm việc sáng, bảng và biểu đồ ưu tiên dữ liệu.
- Trạng thái thao tác và lưu dữ liệu hiển thị rõ.

Nguồn: `frontend/static/app.css`, `auth.css`, `theme-v2.css` và HTML trong `frontend/`. Thứ tự cascade là app → auth → theme-v2; phải kiểm tra selector cụ thể trước khi áp dụng token. `reference.css` và HTML trong `docs/design/stitch/` là tham chiếu, không phải stylesheet đang nạp trên trang chính. Lượt này đối chiếu mã nguồn, chưa xác nhận computed styles bằng trình duyệt.

## Colors

### Primary

Xanh hành động (`primary`) dành cho nút chính và focus; xanh sâu (`deep`) cho chữ trên nền xanh nhạt (`soft`). Sidebar active và một số chi tiết thương hiệu vẫn dùng xanh (#2563eb) trực tiếp trong CSS, không phải mọi chi tiết đều dùng token primary.

### Secondary

Xanh lá rủi ro thấp (`teal`), đỏ cảnh báo (`red`) và hổ phách (`amber`) biểu thị kết quả có ý nghĩa. Tag dùng nền nhạt và chữ đậm tương ứng; không lấy màu cảnh báo làm màu trang trí ngẫu nhiên.

### Neutral

Nền xanh xám nhạt (`bg`), giấy trắng (`paper`), chữ mực (`ink`), chữ phụ (`muted`), viền xanh xám (`line`) và navy điều hướng (`nav`) tạo các lớp đọc ổn định. Token trong frontmatter ghi giá trị mặc định của theme; một số bề mặt auth có màu riêng.

**The Labeled Risk Rule.** Mọi mức rủi ro phải có tên bằng chữ đi cùng màu.

## Typography

Be Vietnam Pro được tự phục vụ bằng WOFF2 Latin và Vietnamese, các trọng lượng 400/500/600/700; fallback Segoe UI và system font. Không cần CDN font. Frontmatter ghi body, headline và label mặc định; selector cục bộ có thể ghi đè.

Tiêu đề h1 giảm xuống (26px) ở màn hình tối đa (700px). h2 mặc định (19px), số metric (34px), PD (48px). Bảng (14.5px), tiêu đề cột (13px), nút chính (15px). Trang auth giữ các cỡ chữ cục bộ, gồm tiêu đề giới thiệu (42px); không áp dụng headline toàn cục thay cho mọi heading.

**The Readable Data Rule.** Giữ nhãn, đơn vị và độ chính xác số liệu; không rút gọn khiến thay đổi ý nghĩa.

## Layout

Sidebar desktop mặc định (256px), giảm còn (236px) ở tối đa (1200px); workspace bù đúng chiều rộng. Main giới hạn (1800px). Theme đặt padding main như frontmatter; CSS có các điều chỉnh mật độ theo khoảng màn hình cần đọc cùng cascade.

Ở tối đa (950px), form/kết quả đơn lẻ và chart grid chuyển một cột, metric còn hai cột. Ở tối đa (700px), sidebar thành menu đóng/mở, workspace bỏ lề trái và main dùng padding (20px 14px 30px); thanh trên thôi sticky, nhóm thao tác xếp lại. Bảng cuộn ngang trong vùng riêng, phân trang 25 dòng theo ứng dụng.

Topbar sticky trên desktop; footer gửi form sticky dưới vùng làm việc, kết quả đặt top (96px) khi layout cho phép. Luồng onboarding ba bước chuyển một cột ở tối đa (1000px). Auth hai panel chuyển một cột ở tối đa (800px), ẩn phần giới thiệu dài. Admin có điều hướng mobile riêng.

## Elevation & Depth

Panel dùng viền (1.5px) và bóng nhẹ (0 1px 3px #0f1b2d0f). Nút chính có bóng đáy (0 2px 0 #1e3a8a); khi nhấn dịch xuống (1px) và bỏ bóng. Menu nổi dùng bóng (0 14px 34px #0f1b2d38). Auth shell có bóng rộng hơn để tách khung đăng nhập khỏi nền.

**The Surface Separation Rule.** Bóng phân biệt bề mặt và trạng thái thao tác; giữ bảng và dữ liệu dễ đọc hơn hiệu ứng.

## Shapes

Góc bo control, panel và tag theo frontmatter. Tab container bo (12px), tab con (9px); auth shell (24px). Viền là một phần chủ đích của hệ thống, nhất là ô nhập và trạng thái focus. Không chuẩn hóa mọi bề mặt về một bán kính duy nhất.

## Components

### Buttons

Nút primary cao tối thiểu (46px), viền (2px), chữ đậm vừa (600). Hover chuyển xanh đậm (#1e40af); active dùng deep. Secondary nền xanh nhạt, chữ xanh sâu, không bóng; danger đỏ với chữ trắng. Compact và nút trong bảng có kích thước riêng. Disabled giảm opacity và có cursor không cho thao tác.

### Inputs / Fields

Ô nhập mặc định cao tối thiểu (46px), padding (9px 13px), viền (1.5px solid #6b7c96). Focus đổi viền xanh và halo (0 0 0 3px #bfdbfe); focus-visible có outline (3px), offset (3px). Nhãn phải gắn với control; form dài chia nhóm fieldset. Selector auth hoặc label có thể ghi đè kích thước.

### Cards / Containers

Panel trắng, viền rõ, bo theo token; panel heading dùng padding trong frontmatter. Metric có dải màu trên (5px), số lớn và nhãn phụ. Trạng thái trống, thiếu model/cấu hình và lỗi phải là nội dung thật, không lấp bằng số liệu minh họa.

### Navigation

Sidebar tối, icon SVG nét; item active xanh và chữ trắng. Item mặc định cao tối thiểu (64px), có nhãn phụ; hover dùng navy sáng hơn. Focus trong sidebar dùng outline vàng (#ffd54a). Mobile dùng menu hiện có; giữ tên và trạng thái trang đang chọn.

### Chips

Tag nhỏ, chữ đậm (700), padding (5px 10px). Low dùng nền xanh lá nhạt/chữ xanh đậm, medium vàng nhạt/nâu, high đỏ nhạt/đỏ đậm. Nhãn và màu phải cùng phản ánh kết quả thực.

### Tables, charts and feedback

Bảng có header nền xanh nhạt, hàng xen kẽ, hover sáng; padding cell (14px 16px). Biểu đồ SVG phải có nhãn trục, nhóm và giá trị; phân biệt nhãn thực tế với dự báo. Hiển thị tải, lỗi, chưa dự báo, cấu hình đổi và chưa đồng bộ. Giữ skip link, focus và quy tắc prefers-reduced-motion đang có; animation trang hiện tại ngắn (0.2s ease-out).

## Do's and Don'ts

### Do:
- **Do** dùng font tiếng Việt tự phục vụ và giữ focus nhìn thấy.
- **Do** ghi rõ mức rủi ro, đơn vị TWD và trạng thái dữ liệu.
- **Do** tái sử dụng component và thứ tự CSS hiện tại khi mở rộng.

### Don't:
- **Don't** dùng màu làm dấu hiệu duy nhất cho mức rủi ro.
- **Don't** lấy số liệu trong ảnh tham chiếu làm dữ liệu thật.
- **Don't** dùng token desktop làm chuẩn cho web.

Ghi chú desktop kế thừa được giữ riêng tại [DESKTOP_DESIGN.md](docs/design/DESKTOP_DESIGN.md). Những ghi chú đó chưa được kiểm chứng lại trong lượt tài liệu hóa web này.
