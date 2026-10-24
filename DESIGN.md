---
# Token máy đọc được. web/src/theme.css phải khớp từng giá trị ở đây (tests/test_design_tokens.py).
# Quy ước tên: colors.light.X / colors.dark.X → --color-X; font.X → --font-X; text.X → --text-X;
# radius.X → --radius-X; space.X → --space-X; size.X → --size-X; motion.X → --motion-X.
name: Form Coach
source: https://claude.ai/artifact/MSPvQD7RRNjryvhRHPzTBw
colors:
  light:
    bg: "#F5F5F3"
    card: "#FFFFFF"
    ink: "#14161A"
    ink2: "#5B6068"
    accent: "#0E7A4B"
    on-accent: "#FFFFFF"
    tint: "#7FC4A0"
    chip: "#DCEFE5"
    track: "#E4E6E3"
    line: "#D6D9D5"
    danger: "#B42318"
    warn: "#9A5B00"
    chart-elbow: "#2563EB"
    chart-body: "#9333EA"
    hero-bg: "#0B0D0E"
  dark:
    bg: "#0E1012"
    card: "#181B1E"
    ink: "#F2F3F1"
    ink2: "#A0A5AB"
    accent: "#4CD08A"
    on-accent: "#06180F"
    tint: "#2F6B4E"
    chip: "#193328"
    track: "#2A2E32"
    line: "#33383D"
    danger: "#FF8A7A"
    warn: "#F2B45A"
    chart-elbow: "#60A5FA"
    chart-body: "#C084FC"
    hero-bg: "#1B1F22"
  fixed:
    stage: "#0B0D0E"
    skeleton-bone: "#4CD08A"
    skeleton-joint: "#F2F3F1"
    chart-left: "#F97316"
    chart-right: "#3B82F6"
    chart-neutral: "#9CA3AF"
font:
  body: "'Inter', system-ui, sans-serif"
text:
  counter: 96px
  hero: 36px
  display: 40px
  stat: 34px
  title-lg: 32px
  title: 28px
  headline: 24px
  button: 17px
  heading: 16px
  body: 15px
  body-sm: 14px
  label: 13px
  caption: 12px
radius:
  hero: 28px
  card: 22px
  button: 18px
  logo: 16px
  input: 14px
  icon: 12px
  segment: 10px
space:
  page: 20px
  gap: 14px
  card: 18px
size:
  touch: 44px
  input: 48px
  button: 56px
motion:
  fast: 120ms
  base: 200ms
  slow: 320ms
  ease: "cubic-bezier(0.2, 0.8, 0.2, 1)"
---

# Form Coach: design system

Nguồn: canvas thiết kế "Form Coach Dashboard" (link ở `source`). Token ở phần đầu file là nguồn sự thật; `web/src/theme.css` khai báo đúng các giá trị đó thành biến CSS, test chặn hai file lệch nhau. **Đọc file này trước khi viết hay sửa UI.**

## Tinh thần

App dùng khi đang tập: điện thoại đặt dưới sàn, nhìn từ xa, tay bận. Nên: chữ và số to, ít màu, vùng bấm lớn, mỗi màn một việc chính. Công cụ hỗ trợ, không phải huấn luyện viên: giọng văn ngắn, cụ thể, không phán xét.

## Màu

Một màu nhấn duy nhất (`accent`, xanh lá), còn lại là thang xám ấm. Mọi màu dùng qua biến (`var(--color-ink)`), **không viết mã hex trong component**.

| Token | Dùng cho |
|---|---|
| `bg` | Nền trang |
| `card` | Thẻ, thanh điều hướng dưới |
| `ink` | Chữ chính; viền rep "cần sửa"; nút phụ đặc (Gửi lại, Xong) |
| `ink2` | Chữ phụ, nhãn, chú thích, trục đồ thị |
| `accent` | Nút chính, vòng tiến độ, rep đúng, ngày đạt mục tiêu, chữ "Coach" |
| `on-accent` | Chữ/icon trên nền `accent` |
| `tint` | Cột "chưa đạt" trên đồ thị |
| `chip` | Nền thông báo thành công ("Đã lưu hiệp"), hàng đang chọn. Bản tối = `accent` 18% trên `bg` của canvas, đổi sang màu đặc |
| `track` | Nền thanh/vòng tiến độ, nền nút chọn hai lựa chọn (segmented) |
| `line` | Viền ô nhập, nút viền, đường kẻ |
| `danger` | Chỉ cho **lỗi hệ thống** (mất mạng, file hỏng). *Claude đề xuất, không có trong canvas* |
| `warn` | Cảnh báo thao tác (đang quay dọc). *Claude đề xuất, không có trong canvas* |
| `chart-elbow`, `chart-body` | Đường góc khuỷu / góc thân ở màn Gán nhãn. *Giữ từ app cũ, chỉnh cho nền tối* |
| `hero-bg` | Nền tấm giới thiệu (đăng nhập, máy tính): sáng = `stage`; tối sáng hơn `bg` một bậc để không chìm vào nền |
| `stage` | Nền khung camera và người que: **luôn tối**, cả ở chế độ sáng |
| `skeleton-bone`, `skeleton-joint` | Khung xương vẽ đè lên camera (theo canvas: xương xanh, khớp trắng) |
| `chart-left`, `chart-right`, `chart-neutral` | Người que: bên trái cam, bên phải xanh dương, xương ngang xám. *Giữ từ app cũ (khớp `analyze --plot`)* |

Quy tắc:
- **Lỗi kỹ thuật của rep không dùng màu đỏ.** Rep đúng = tròn đặc `accent`; rep cần sửa = tròn viền `ink`, kèm tên lỗi bằng chữ. Không phân biệt lỗi bằng màu (không có "màu của hip_sag"): tên lỗi luôn viết ra.
- `danger` không dùng cho kỹ thuật tập, chỉ cho lỗi của app.
- Không gradient trang trí, không đổ bóng; tách lớp bằng `card` trên `bg`.
- Tương phản chữ ≥ 4,5:1 trên `bg` và `card` ở cả hai chế độ (đã đo: `ink2` 5,8 / 6,3 sáng, 7,7 / 7,0 tối; `accent` 4,9 / 5,4 sáng). **Chưa đạt:** chữ `accent` trên nền `chip` ở chế độ sáng chỉ 4,49:1 (thông báo "Đã lưu hiệp", 14px đậm). Cần làm đậm `accent` hoặc nhạt `chip` một chút; chờ bạn quyết.

## Chế độ sáng / tối

- Mặc định theo cài đặt của máy (`prefers-color-scheme`); nút mặt trăng/mặt trời đổi tay, nhớ trong trình duyệt.
- Cùng một tên token cho cả hai chế độ; component không bao giờ kiểm tra đang sáng hay tối.
- Nhóm `fixed` không đổi theo chế độ (khung camera luôn tối).

## Chữ

Font **Inter** (gói `@fontsource/inter`, nằm trong app, không tải từ Google), độ đậm 400/500/600/700. Mọi con số dùng `font-variant-numeric: tabular-nums` để số rep, đồng hồ không nhảy khi đổi.

| Token | Cỡ / đậm | Dùng cho |
|---|---|---|
| `counter` | 96 / 700 | Số lớn trên màn Tập khi đang ghi (đồng hồ, sau này số rep), nhìn từ xa |
| `hero` | 36 / 700 | Khẩu hiệu trên tấm giới thiệu (đăng nhập, máy tính) |
| `display` | 40 / 700 | Số lớn trong vòng tiến độ |
| `stat` | 34 / 700 | Số trong thẻ thống kê |
| `title-lg` | 32 / 700 | Tên app ở màn đăng nhập |
| `title` | 28 / 700 | Tiêu đề màn hình |
| `headline` | 24 / 600 | Câu tóm tắt ("5 rep cần sửa") |
| `button` | 17 / 600 | Chữ nút chính |
| `heading` | 16 / 600 | Tiêu đề thẻ; chữ trong ô nhập (≥ 16 để iOS không tự phóng to) |
| `body` / `body-sm` | 15 / 14 | Chữ thường |
| `label` | 13 | Nhãn trên số liệu |
| `caption` | 12 | Chú thích, chú giải đồ thị |

Chữ từ 24px trở lên: `letter-spacing` −0,02em (số lớn −0,03em).

## Hình khối và khoảng cách

- Bo góc: tấm giới thiệu nền tối 28, thẻ 22, nút chính 18, logo 16, ô nhập và nút phụ 14, nút icon 12, nút trong segmented 10. Rep là hình tròn.
- Lề trang 20, khoảng giữa các thẻ 14, đệm trong thẻ 18–20.
- Vùng bấm tối thiểu 44×44; ô nhập cao 48; nút chính cao 56.

## Thành phần

- **Nút chính:** nền `accent`, chữ `on-accent`, cao 56, bo 18, rộng hết thẻ. Mỗi màn tối đa một nút chính.
- **Nút phụ đặc:** nền `ink`, chữ `bg` (Gửi lại, Xong khi đang quay).
- **Nút viền:** nền trong suốt, viền 1,5px `line`, chữ `ink`, cao 44, bo 14.
- **Nút chữ:** không nền, chữ `ink2`, cao 44 ("Về Dashboard").
- **Ô nhập:** cao 48, viền 1,5px `line`, bo 14, nền `bg`, chữ 16; luôn có `<label>`.
- **Số đo từng rep** (trang kết quả): thẻ theo số đo (vd "Góc khuỷu ở đáy"), dòng "Mục tiêu ≤ 67°"; mỗi rep một ô: rep đúng nền `track`, rep bị báo lỗi viền 2px `ink` (như vòng rep, không dùng màu); chữ số đo `ink`, đậm.
- **Xem lại một rep** (trang kết quả): vòng rep và ô số đo là nút; bấm mở khung giữa màn hình (thẻ `card`, nền mờ `stage` 60%), tiêu đề "Rep k", kết luận + số đo, người que lặp lại trên nền `stage`, nhãn "Trong rep / Trước / sau rep", nút Tạm dừng và tốc độ 1× / 0,5× (segmented). Esc hoặc bấm ra ngoài để đóng. Chỉ khung xương, không video.
- **Lỗi trong form:** kiểm tra khi bấm gửi (không dùng bong bóng của trình duyệt: `noValidate`), sau đó cập nhật theo từng phím gõ. Lỗi của một ô hiện **ngay dưới ô đó** (chữ 13 màu `danger`, viền ô `danger`, `aria-invalid` + `aria-describedby`); lỗi không thuộc ô nào (sai email hoặc mật khẩu, mất kết nối) hiện trong khung viền `danger` có icon ở đầu form. Câu báo là câu thường ngày, viết hoa đầu câu, có dấu chấm, nói cách sửa nếu được ("Mật khẩu phải có ít nhất 8 ký tự."); không hiện nguyên câu kỹ thuật từ server.
- **Segmented** (Đăng nhập / Tạo tài khoản; Tập / Quay dữ liệu): nền `track`, nút đang chọn nền `card`.
- **Thẻ:** nền `card`, bo 22, đệm 18–20, không viền, không bóng.
- **Thanh điều hướng dưới** (điện thoại): Dashboard · Quay (nút tròn 60px nền `accent` nổi giữa) · Gán nhãn.
- **Icon:** nét (stroke) 2px, đầu tròn, cùng màu chữ; nút chỉ có icon phải có `aria-label`.
- **Tấm giới thiệu** (đăng nhập, máy tính): nền `stage`, bo 28; khẩu hiệu, người que ở đáy push-up với cung đo góc khuỷu 90° (xương `skeleton-bone`, khớp và số đo `skeleton-joint`), một dòng giải thích. Cao theo nội dung, căn giữa theo chiều dọc với form. Không glow, không gradient.
- **Coach:** chữ "Coach" màu `accent`, đoạn nhận xét, dòng "Công cụ hỗ trợ, không thay huấn luyện viên." luôn đi kèm.

## Chuyển động

Chuyển động để báo trạng thái, không để trang trí. Ngắn, đi ra nhanh hơn đi vào, không nảy.

| Token | Giá trị | Dùng cho |
|---|---|---|
| `fast` | 120ms | Phản hồi khi bấm (nút thu nhỏ 0,97), đổi màu khi rê chuột |
| `base` | 200ms | Focus ô nhập, nút segmented đổi chỗ, thông báo lỗi hiện ra |
| `slow` | 320ms | Nội dung một màn hiện dần khi mở (mờ → rõ, trượt lên 8px, mỗi khối trễ 60ms) |
| `ease` | `cubic-bezier(0.2, 0.8, 0.2, 1)` | Đường cong chung: nhanh lúc đầu, chậm dần |

- Chỉ animate `opacity` và `transform` (không animate kích thước, không gây giật bố cục).
- `prefers-reduced-motion: reduce`: tắt hết animation và transition, hiện ngay trạng thái cuối.
- Mọi thứ bấm được có `:focus-visible` rõ (viền 2px `accent`); không bỏ viền focus.

## Bố cục

- Thiết kế cho điện thoại trước (rộng 390), máy tính dùng cùng token với lưới rộng hơn.
- Màn tập và quay: điện thoại xoay ngang, khung camera chiếm phần lớn, cột phải có số lớn và một nút.
- Các màn hiện có (Quay, Gán nhãn, Gán nhanh) chưa theo bố cục mới; chuyển dần khi làm lại từng màn (Đăng nhập ở B3, Kết quả ở B6, Dashboard tuần 4).
