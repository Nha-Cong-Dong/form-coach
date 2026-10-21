# Tiêu chí gán nhãn

> **Tự viết phần này trước khi quay dữ liệu.** Ngưỡng để trống (`?`), điền sau khi đo từ dữ liệu của chính mình. Ngưỡng tham khảo từ bên ngoài cần ghi nguồn.
> Nhãn là **multi-label**: mỗi rep có một **tập lỗi**, có thể nhiều lỗi cùng lúc. Tập rỗng nghĩa là `good`. Ghi chú thêm vào ô ghi chú (`note`) của rep trong màn hình gán nhãn.

## Quy ước quay
- Quay bằng **trang quay của app** (camera trình duyệt), không quay bằng app camera của điện thoại
- Góc máy: bên hông, toàn thân trong khung, máy cố định
- Mỗi hiệp một kiểu: tập đúng, hoặc **cố ý làm một lỗi**. Chọn tập lỗi của hiệp trước khi bấm Bắt đầu; mọi rep nhận tập đó, rep nào làm khác ý định thì sửa riêng
- Mỗi buổi quay ít nhất một hiệp cho từng lỗi, để lỗi nào cũng có mẫu ở nhiều buổi
- Ghi lại: ngày, giờ, địa điểm, quần áo, ánh sáng (để phân tích domain shift sau)

## Quy tắc gán nhãn dataset (chống rò rỉ)
Áp dụng cho các buổi dùng để chấm điểm (từ tối 2026-10-20, 18:00), không áp cho hiệp quay thử.

1. **Gán nhãn bằng mắt, không bằng số đo của luật.** Chỉ dùng màn gán nhãn (người que + đồ thị), xem từng rep ở 0,5× nếu cần. **Không chạy `python -m formcoach analyze` trên hiệp dataset trước khi gán nhãn xong**: lệnh đó in lỗi theo luật và các số đo (`min_elbow_angle`, `top_elbow_angle`…). Tick lỗi theo con số ("67,5° > 67 nên là shallow") thì nhãn chính là output của luật, chấm luật trên đó ra ~100% mà không nói lên gì. Ngưỡng trong bảng dưới là để **luật** dùng; nhãn là đánh giá bằng mắt theo phần "Mô tả bằng lời".
2. **Chốt nhãn trước khi xem kết quả.** Gán nhãn xong mọi buổi (21–24/10) (và chốt ngưỡng `hip_sag` từ hiệp quay thử) **trước** lần chạy `python -m evaluation.baseline` đầu tiên. Sau đó không sửa nhãn vì "thấy luật/model đoán khác". Nếu buộc phải sửa (vd phát hiện tick nhầm), ghi vào "Lịch sử thay đổi tiêu chí" kèm lý do không dựa vào kết quả, và báo cả kết quả trước lẫn sau khi sửa.

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
| `shallow` | Chưa xuống đủ sâu ở đáy rep | Góc khuỷu nhỏ nhất (vai–khuỷu–cổ tay) | `> 67°` |
| `incomplete_lockout` | Chưa đẩy lên hết ở đỉnh rep | Góc khuỷu lớn nhất trong 0,5 s ngay sau rep (`top_elbow_angle`) | `< 146°` |
| `hip_sag` | Hông võng xuống | Độ lệch có dấu của hông so với đường vai–cổ chân (`hip_offset`) | `< ?` *(chờ quay lại hiệp võng rõ)* |
| `hip_high` | Hông nhô cao | Độ lệch có dấu của hông so với đường vai–cổ chân (`hip_offset`), nhỏ nhất trong rep | `min_hip_offset > 0,01` (hông ở trên đường suốt rep) |
| `neck_drop` *(thử nghiệm)* | Cổ rướn ra trước hoặc gục xuống, đầu lệch khỏi đường thân, **giữ phần lớn rep** (gục thoáng qua không tính) | Góc tai–vai–hông, **trung vị** trong rep (`median_neck_angle`) | `< 128°` |

Số đo từ buổi quay thử 2026-10-20 (6 hiệp × 4 rep) + hiệp 2026-10-19T23-38-38 (5 rep), rep cắt bằng bộ đếm theo biên độ:

| Hiệp | Góc khuỷu nhỏ nhất | Góc thân nhỏ nhất |
|---|---|---|
| Tập đúng (2 hiệp) | 41–56° | 162–171° |
| `shallow` | 69–82° | 163–175° |
| `incomplete_lockout` | 38–48° | 164–171° |
| `hip_sag` | 47–65° | 158–170° |
| `hip_high` | 55–64° | 125–155° |
| `neck_drop` | 50–61° | 170–172° |

`hip_offset` (tỉ lệ chiều dài vai–cổ chân, 0,01 ≈ 1,3 cm; dương = hông nhô, âm = võng), từng rep:

| Hiệp | Nhỏ nhất trong rep | Lớn nhất trong rep |
|---|---|---|
| Tập đúng | −0,042 … −0,023 | +0,015 … +0,075 |
| `hip_sag` | −0,092 … −0,042 | −0,024 … −0,003 |
| `hip_high` | +0,032 … +0,115 | +0,105 … +0,240 |

`neck_angle` từng rep (cổ "thẳng" khi nhìn ngang vẫn chỉ ~140–170°, vì đầu nằm cao hơn đường vai–hông). Giá trị nhỏ nhất bị nhiễu tai (±10° giữa các khung) nên dùng trung vị:

| Rep | Nhỏ nhất | Trung vị |
|---|---|---|
| Có `neck_drop` (hiệp `neck_drop` + rep 4 hiệp `shallow`) | 107,7 … 113,1° (rep 4 `shallow`: 112,5°) | 122,1 … 126,6° |
| Không `neck_drop`, buổi 2026-10-20 | 111,7 … 140,6° | 129,2 … 171,3° |
| Tập đúng, buổi 2026-10-19 | 135,4 … 159,4° | 151,2 … 169,9° |

`top_elbow_angle` từng rep: rep chưa duỗi hết tay 112,4 / 132,8 / 135,2°; mọi rep khác (2 buổi) 157,5 … 180,8°. Lockout "đúng" của mình chỉ ~158–166°, chưa thẳng hẳn 180°.

**Buổi quay thử chỉ dùng để chọn ngưỡng, không đưa vào chấm điểm** (ngưỡng chọn để tách đúng chính các rep này; chấm trên nó là rò rỉ dữ liệu).

Lưu ý:
- `shallow`: rep nông của mình chỉ hơi nông (69–82°), rep không nông sâu nhất 65° → khoảng cách chỉ ~4°, dễ sai vì nhiễu vài độ của MediaPipe. Các buổi sau quay hiệp `shallow` nông rõ hơn (~85–100°). Không dùng mốc 90° phổ biến: với mốc đó không rep nào của mình bị tính là nông, trái với nhãn đã gán.
- `hip_sag` và `hip_high`: góc vai–hông–cổ chân chỉ cho biết thân cong bao nhiêu, không biết cong lên hay xuống (góc `hip_sag` 158–170° trùng với tập đúng 162–171°). Dùng `hip_offset` có dấu (bước 4): dương = hông cao hơn đường vai–cổ chân, âm = võng. Hai lỗi này không thể cùng xảy ra trong một rep.
- `incomplete_lockout`: bộ đếm đếm theo biên độ (từ 2026-10-20), không còn cần đỉnh vượt một ngưỡng góc cố định, nên rep chưa lên hết vẫn được đếm. Đỉnh đo được trên đồ thị: rep lỗi 110–135°, rep đúng ~158–176°.
- `neck_drop`: khoảng cách chỉ ~2,6° (126,6° ↔ 129,2° của rep 3 hiệp `shallow`, đầu gục dần theo độ mỏi), nên mốc 128° là quy ước. Hai buổi khác ngày lệch nhau 10–20° (tập đúng 19/10: 151–170°, 20/10: 143–149°): đổi góc đặt máy có thể làm lệch cả khối.
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
| 2026-10-20 | Hiệp `hip_sag` quay thử võng quá nhẹ: hông chỉ thấp hơn đường vai–cổ chân ~5–12 cm (rep 3–4 ~5 cm), trong khi rep đúng cũng tự võng tới ~5 cm ở đáy | Chưa đặt ngưỡng `hip_sag`; quay lại một hiệp võng rõ (hông thấp hơn ≥ ~10 cm, giữ suốt rep) rồi đo lại |

| 2026-10-20 | Rep 4 hiệp `hip_sag`: đầu gục thoáng qua (góc cổ nhỏ nhất 115,5°, trung vị 146,4°) | Không tính `neck_drop`: lỗi cổ phải giữ phần lớn rep |

| 2026-10-20 | Rep 4 (rep cuối) hiệp `incomplete_lockout`: đỉnh sau rep 155,1°, chỉ thấp hơn rep đúng thấp nhất 2,4°; xem lại thì lần cuối đẩy lên gần hết trước khi đứng dậy | Không tính `incomplete_lockout` |

## Lịch sử thay đổi tiêu chí
Nếu đổi ngưỡng sau khi đã gán nhãn, phải gán lại các rep bị ảnh hưởng.

| Ngày | Thay đổi | Lý do |
|---|---|---|
| 2026-10-20 | `incomplete_lockout`: `top_elbow_angle < 146°` (thay mức tạm 150°; nằm giữa 135,2° và 157,5°) | Đo đỉnh sau rep trên buổi quay thử |
| 2026-10-20 | `neck_drop`: `median_neck_angle < 128°`; chỉ tính khi giữ phần lớn rep | Giá trị nhỏ nhất bị nhiễu tai, bắt nhầm 3 rep; trung vị tách được |
| 2026-10-20 | `hip_high`: `min_hip_offset > 0,01` (cách tập đúng ~0,055 ≈ 7 cm) | Đo `hip_offset` trên buổi quay thử |
| 2026-10-20 | `shallow > 67°`; `incomplete_lockout < 150°` (tạm); `hip_sag`/`hip_high` đổi sang đo `hip_offset` có dấu; ngưỡng hông và cổ chờ bước 4 | Đo từ buổi quay thử (bảng trên). Buổi quay thử không đưa vào chấm điểm |
| 2026-10-17 | Chuyển sang multi-label, bỏ cột ưu tiên; push-up thêm `incomplete_lockout`, `neck_drop` (thử nghiệm); thêm cờ `valid` thay cho nhãn `not_ready` | Lỗi push-up hay xảy ra cùng lúc; "có phải rep không" khác với "rep sai ở đâu" |
