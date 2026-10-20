# Tiêu chí gán nhãn

> **Tự viết phần này trước khi quay dữ liệu.** Ngưỡng để trống (`?`), điền sau khi đo từ dữ liệu của chính mình. Ngưỡng tham khảo từ bên ngoài cần ghi nguồn.
> Nhãn là **multi-label**: mỗi rep có một **tập lỗi**, có thể nhiều lỗi cùng lúc. Tập rỗng nghĩa là `good`. Ghi chú thêm vào ô ghi chú (`note`) của rep trong màn hình gán nhãn.

## Quy ước quay
- Quay bằng **trang quay của app** (camera trình duyệt), không quay bằng app camera của điện thoại
- Góc máy: bên hông, toàn thân trong khung, máy cố định
- Mỗi hiệp một kiểu: tập đúng, hoặc **cố ý làm một lỗi**. Chọn tập lỗi của hiệp trước khi bấm Bắt đầu; mọi rep nhận tập đó, rep nào làm khác ý định thì sửa riêng
- Mỗi buổi quay ít nhất một hiệp cho từng lỗi, để lỗi nào cũng có mẫu ở nhiều buổi
- Ghi lại: ngày, giờ, địa điểm, quần áo, ánh sáng (để phân tích domain shift sau)

## Rep không hợp lệ (`valid = false`)
Không phải nhãn lỗi. Đánh dấu khi bộ đếm cắt ra một đoạn **không phải rep thật**: lúc vào tư thế, đứng dậy, nghỉ giữa hiệp, chỉnh máy. Rep không hợp lệ bị loại khỏi train và dùng để đo độ chính xác của bộ đếm.

| Trường hợp | valid |
|---|---|
| Rep thật, kể cả mắc lỗi (nông, chưa lên hết...) | `true` |
| Đoạn chuyển tư thế, nghỉ, chỉnh máy bị đếm nhầm | `false` |
| (ca khác, ghi vào "Ca mập mờ") | |

## Push-up (làm trước)

| Lỗi | Mô tả bằng lời | Đo bằng | Ngưỡng |
|---|---|---|---|
| `shallow` | Chưa xuống đủ sâu ở đáy rep | Góc khuỷu nhỏ nhất (vai–khuỷu–cổ tay) | `> ?°` |
| `incomplete_lockout` | Chưa đẩy lên hết ở đỉnh rep | Góc khuỷu lớn nhất ở đỉnh (vai–khuỷu–cổ tay) | `< ?°` |
| `hip_sag` | Hông võng xuống | Góc vai–hông–cổ chân | `< ?°` (võng xuống) |
| `hip_high` | Hông nhô cao | Góc vai–hông–cổ chân | `< ?°` (nhô lên) |
| `neck_drop` *(thử nghiệm)* | Cổ rướn ra trước hoặc gục xuống, đầu lệch khỏi đường thân | Góc tai–vai–hông (hoặc mũi–vai–hông) | `< ?°` |

Lưu ý:
- `hip_sag` và `hip_high` cùng đo một góc nhưng lệch về hai phía. Cần quy ước dấu (hông nằm trên hay dưới đường vai–cổ chân). Hai lỗi này không thể cùng xảy ra trong một rep.
- `incomplete_lockout`: ngưỡng của bộ đếm để coi là "đã lên lại" phải **thấp hơn** ngưỡng này, nếu không rep chưa lên hết sẽ không được đếm.
- `neck_drop`: MediaPipe đặt khớp mặt kém chính xác khi quay ngang. Vẫn gán nhãn, nhưng chỉ đưa vào model nếu dữ liệu cho thấy góc này tách được rep đúng/sai. Nếu không, ghi vào phần hạn chế.

## Squat (mở rộng, làm sau)

| Lỗi | Mô tả bằng lời | Đo bằng | Ngưỡng |
|---|---|---|---|
| `shallow` | Chưa xuống đủ sâu | Góc gối nhỏ nhất (hông–gối–cổ chân) | `> ?°` |
| `back_round` | Lưng gập/cong quá mức | Góc thân (vai–hông–gối) hoặc góc lưng so với phương thẳng đứng | `< ?°` |
| `heel_lift` | Gót chân nhấc khỏi sàn | Độ cao gót so với mũi chân | `> ?` |

## Ca mập mờ
Ghi lại các rep khó phân loại và cách đã quyết định, để nhất quán giữa các buổi.

| Ngày | Mô tả | Quyết định |
|---|---|---|
| | | |

## Lịch sử thay đổi tiêu chí
Nếu đổi ngưỡng sau khi đã gán nhãn, phải gán lại các rep bị ảnh hưởng.

| Ngày | Thay đổi | Lý do |
|---|---|---|
| 2026-10-17 | Chuyển sang multi-label, bỏ cột ưu tiên; push-up thêm `incomplete_lockout`, `neck_drop` (thử nghiệm); thêm cờ `valid` thay cho nhãn `not_ready` | Lỗi push-up hay xảy ra cùng lúc; "có phải rep không" khác với "rep sai ở đâu" |
