# Nhật ký vấp

> Mỗi lần gặp bug, kết quả bất ngờ, hay hiểu sai điều gì thì ghi lại ở đây. Đây là nguyên liệu cho README và phỏng vấn.

Mẫu:

```
## YYYY-MM-DD — <tiêu đề ngắn>
- **Chuyện gì xảy ra:**
- **Nguyên nhân:**
- **Cách sửa:**
- **Bài học:**
```

---

## 2026-10-19 — Góc khuỷu ra 2° vì khung lỗi
- **Chuyện gì xảy ra:** Chạy probe lần đầu, góc khuỷu nhỏ nhất chỉ 2–6°, ảnh "đáy rep" chụp sai tư thế.
- **Nguyên nhân:** Lấy min trên mọi khung, kể cả khung bị che. Nghi ngờ: video có người khác và quay chéo nên sinh thêm khung lỗi.
- **Cách sửa:** Chỉ tính khung nhìn rõ, dùng phân vị thay min/max. Quay lại ngang hông, một mình → 0 khung lỗi.
- **Bài học:** Lọc dữ liệu rác trước khi thống kê, và quay sạch ngay từ đầu.

## 2026-10-19 — Bộ đếm bỏ sót rep hông nhô cao
- **Chuyện gì xảy ra:** Clip mixed có 6 rep, bộ đếm ra 4, sót 2 rep hông nhô cao (nông, nhanh). Test tổng hợp vẫn xanh hết.
- **Nguyên nhân:** Đặt min_rep_duration 0,8 s vì nghĩ một rep dài ~2,4 s. Nhưng 2,4 s là chu kỳ đáy–đáy, còn bộ đếm đo thời gian khuỷu nằm dưới top_min; rep nhanh chỉ ~0,7 s nên bị loại như nhiễu.
- **Cách sửa:** Hạ về 0,4 s, thêm test rep nông và nhanh (kiểm tra test đỏ với 0,8 s).
- **Bài học:** Biết chính xác con số đo cái gì trước khi đặt ngưỡng, và luôn thử trên dữ liệu thật - test tự viết mang cùng hiểu lầm với người viết.

## 2026-10-19 — Điện thoại nằm ngang nhưng khung hình dọc
- **Chuyện gì xảy ra:** Quay 2 hiệp trên trang quay (4 và 5 rep), bộ đếm ra 0 và 1 rep. Góc khuỷu vẫn lên xuống đúng, nhưng độ nghiêng thân lúc hít đất ~72–90° (như đang đứng), lúc đứng lại ~0–20°.
- **Nguyên nhân:** Điện thoại khoá xoay màn hình nên trang web vẫn dọc; trình duyệt gửi hình camera theo chiều trang → hình dọc, người nằm thành đứng. Góc khuỷu/thân không đổi khi xoay hình nên trông bình thường; chỉ độ nghiêng (so với phương ngang của hình) bị lật. Đã xác minh: tắt khoá xoay rồi quay lại thì đúng.
- **Cách sửa:** Trang quay khoá nút Bắt đầu khi khung hình dọc (cao > rộng), hiện hướng dẫn xoay ngang.
- **Bài học:** Hình bị xoay thì phép đo nào dựa vào hướng (độ nghiêng) sai ngay, còn phép đo không phụ thuộc hướng (góc khớp) vẫn đúng, nên phải kiểm tra chiều hình ngay từ đầu vào.

## 2026-10-19 — Rep ma lúc đi lại bấm Xong
- **Chuyện gì xảy ra:** Hiệp 5 rep, bộ đếm ra 6. Rep thứ 6 có góc khuỷu thấp nhất 19° (không thể có khi hít đất), xảy ra sau khi đã đứng dậy.
- **Nguyên nhân:** Đi sát điện thoại để bấm Xong, người lọt khung một phần, visibility khuỷu tụt ~0,2; MediaPipe đoán bừa thân "nằm" và khuỷu gập sâu → bộ đếm tưởng vào lại plank và đếm thêm.
- **Cách sửa:** Bỏ khung có khớp visibility < 0,5 (`min_joint_visibility`), thêm test tái hiện; tắt bộ lọc thì test ra 6, bật lên ra 5.
- **Bài học:** Kết quả từ khớp mô hình không nhìn rõ là đoán bừa; lọc theo độ tin cậy trước khi đưa vào logic.

## 2026-10-19 — Giữ plank 1 s mới đếm làm mất rep đầu
- **Chuyện gì xảy ra:** Clip bắt đầu ngay ở plank, giữ khoảng 0,8 s rồi xuống: bộ đếm bỏ rep đầu.
- **Nguyên nhân:** `ready_hold_s` = 1,0 s dài hơn thời gian giữ thật trước rep đầu.
- **Cách sửa:** Hạ còn 0,5 s.
- **Bài học:** Ngưỡng đặt chặt "cho an toàn" cũng gây sai, theo chiều ngược lại.

## 2026-10-20 — Hiệp chưa duỗi hết tay: 4 rep bị gộp thành 1
- **Chuyện gì xảy ra:** Buổi quay thử, hiệp `incomplete_lockout` có 4 rep, bộ đếm ra 1 rep dài 10,6 s. Các hiệp khác đều ra đúng 4.
- **Nguyên nhân:** Bộ đếm cần khuỷu lên lại trên 140° mới tính xong một rep, nhưng đỉnh giữa các rep chỉ 110°, 133°, 135°. Rep nông lại cần ngưỡng theo chiều ngược lại: hai lỗi đòi hai ngưỡng cố định mâu thuẫn nhau.
- **Cách sửa:** Đếm theo biên độ: xuống ≥ 35° so với đỉnh gần nhất, lên lại ≥ 35° so với đáy. 6 hiệp ra 4 rep mỗi hiệp; 3 video ra 7/7/6. Clip clean giờ ra 7, vì rep cuối bị cắt khi đang đẩy lên vẫn được đếm (trước đây ra 6). Cố ý làm hỏng từng cơ chế của bộ đếm (7 lần), lần nào cũng có test đỏ; chính test cũng bắt được lỗi thời gian nghỉ ở đỉnh bị tính vào rep (một cú giật 0,27 s thành rep dài 1,2 s).
- **Bài học:** Bộ đếm thiết kế và thử trên rep đúng sẽ vỡ khi gặp chính các lỗi mình muốn phát hiện. Phải thử trên dữ liệu có lỗi trước khi tin.

## 2026-10-20 — Rep đầu/cuối bị cắt lấn sang lúc vào và ra tư thế
- **Chuyện gì xảy ra:** Sau khi đổi sang đếm theo biên độ, số rep đúng nhưng rep 1 của hiệp `shallow` dài 10,2 s (rep giữa khoảng 3 s). Hiệp `neck_drop` có góc thân nhỏ nhất ở rep 1 và rep 4 khoảng 132°, rep giữa khoảng 170°.
- **Nguyên nhân:** Rep bắt đầu và kết thúc ở điểm cao nhất của khuỷu. Đồ thị `--plot` xác nhận: lúc giữ plank chờ, khuỷu dao động 155–176° và cao nhất ở đầu lúc giữ, nên rep 1 bắt đầu sớm khoảng 6 s; lúc đứng dậy, tay duỗi thêm tới 179° (thân đã bắt đầu gập) nên rep cuối bị kéo sang đó.
- **Cách sửa:** Ranh giới theo độ ổn định gần đỉnh. Rep kết thúc ở khung đầu tiên mà 0,5 s tới khuỷu không tăng thêm quá 10°; bắt đầu ở khung cuối cùng mà 0,5 s trước đó khuỷu chưa cao hơn nó quá 10°. Cách đầu tiên định làm ("trong 10° dưới đỉnh") vẫn hỏng khi đỉnh bị đẩy lên 179°, nên đã bỏ. Kết quả trên hiệp thật: số rep không đổi (6 hiệp × 4, 23-38-38 ra 5, 3 video ra 7/7/6); rep 1 hiệp shallow 10,2 → 2,7 s; mọi rep của 6 hiệp quay thử dài 1,7–3,7 s; góc thân nhỏ nhất rep 1/rep 4 hiệp neck_drop 131,8/133,3° → 172,0/171,1°.
- **Bài học:** Đếm đúng số rep chưa đủ. Ranh giới rep quyết định đặc trưng nào được tính; không sửa thì luật sẽ bắt nhầm lỗi hông do lúc vào/ra tư thế.

## 2026-10-20 — Hông võng nhưng góc thân không thấy, rồi hiệp võng lại quá nhẹ
- **Chuyện gì xảy ra:** Góc thân (vai–hông–cổ chân) của hiệp `hip_sag` là 158–170°, trùng với tập đúng (162–171°). Thêm `hip_offset` có dấu (độ lệch hông khỏi đường vai–cổ chân) thì `hip_high` tách rõ (hông cao hơn 10–30 cm), nhưng `hip_sag` vẫn sát tập đúng.
- **Nguyên nhân:** Góc 3 khớp không biết thân cong lên hay xuống. Còn hiệp `hip_sag` thì võng thật sự rất nhẹ (~5 cm ở rep 3–4), bằng mức tập đúng tự võng ở đáy rep.
- **Cách sửa:** Đo bằng `hip_offset` có dấu; `hip_high` dùng ngưỡng `min_hip_offset > 0,01`. Chưa đặt ngưỡng `hip_sag`, sẽ quay lại hiệp võng rõ (≥ ~10 cm).
- **Bài học:** Chọn đúng cách đo quan trọng hơn chỉnh ngưỡng. Và khi cố ý làm lỗi để lấy dữ liệu, mình làm nhẹ hơn mình nghĩ: phải kiểm tra số đo ngay sau khi quay.

## 2026-10-20 — Góc cổ nhiễu: giá trị nhỏ nhất bắt nhầm, trung vị thì không
- **Chuyện gì xảy ra:** `min_neck_angle` của 3 rep không gục đầu (111–116°) nằm trong vùng của rep `neck_drop` (108–113°).
- **Nguyên nhân:** Vị trí tai nhảy ±10° giữa các khung; min chỉ lấy một khung nên đo cả nhiễu. Đồ thị cho thấy cổ của hiệp `neck_drop` giữ ~120° suốt hiệp: lỗi này là tư thế kéo dài, không phải một khoảnh khắc. NaN của góc cổ chỉ nằm ngoài rep (lúc đi lại), không phải nguyên nhân.
- **Cách sửa:** Thêm `median_<tín hiệu>` cho mọi tín hiệu. Trung vị tách được `neck_drop` (122–127°) khỏi rep khác (≥ 129°); 1 rep nghi ngờ hoá ra không gục, 1 rep (`shallow`, mỏi cuối hiệp) đúng là có gục và được thêm nhãn. Ngưỡng `median_neck_angle < 128°`; gục thoáng qua không tính.
- **Bài học:** Với tín hiệu nhiễu, đặc trưng "một khung" (min/max) đo nhiễu nhiều hơn đo tư thế. Lỗi giữ suốt rep thì dùng trung vị; lỗi thoáng qua thì phải chấp nhận khó đo.

## 2026-10-20 — Đỉnh của rep phải đo SAU rep, không phải trong rep
- **Chuyện gì xảy ra:** Định dùng `max_elbow_angle` (góc khuỷu lớn nhất trong rep) để bắt `incomplete_lockout`. Test tổng hợp đỏ: rep 1 có max 165° dù sau rep đó chỉ lên tới 110°.
- **Nguyên nhân:** Rep bắt đầu ngay sau đỉnh của rep TRƯỚC (hoặc lúc giữ plank), nên max trong rep đo đỉnh trước rep chứ không phải lúc đẩy lên của chính rep. Rep lại kết thúc ở chỗ "đã lên gần hết", đỉnh thật nằm sau đó.
- **Cách sửa:** Thêm `top_elbow_angle` = góc lớn nhất trong 0,5 s ngay sau rep. Trên buổi quay thử: rep chưa duỗi hết tay 112–135°, mọi rep khác 157,5–181° → cách nhau ~22°, lỗi tách rõ nhất trong 5 lỗi. Ngưỡng `< 146°`.
- **Bài học:** Trước khi dùng một đặc trưng, phải hỏi nó đo đúng khoảnh khắc nào của rep. Tên "max trong rep" nghe đúng nhưng đo nhầm thời điểm.

## 2026-10-20 — /check-eval: luật có thể tự chấm chính nó
- **Chuyện gì xảy ra:** Soát phần đánh giá vừa viết, code không rò rỉ (model mới mỗi lần chia, chỉ fit trên train, hiệp quay thử bị loại), nhưng quy trình thì có: lệnh `analyze` in lỗi theo luật và số đo, file tiêu chí ghi tiêu chí bằng chính ngưỡng của luật. Ngoài ra nhóm theo ngày lịch sẽ cắt đôi một buổi tập khuya (23:50 → 00:10) ra train và test.
- **Nguyên nhân:** Nếu tick nhãn theo con số ("67,5° > 67 là shallow") thì nhãn chính là output của luật → chấm ra ~100% mà không nói lên gì. Rò rỉ có thể nằm ở quy trình con người, không chỉ ở code.
- **Cách sửa:** Quy tắc: gán nhãn dataset bằng mắt, không chạy `analyze` trước khi gán xong; chốt nhãn trước lần chấm đầu tiên. Ngày tập đổi lúc 04:00. Baseline in hiệp bị bỏ qua và ghi rõ lỗi nào không tính vào macro-F1 từng lần chia.
- **Bài học:** Kiểm tra rò rỉ phải xét cả cách người gán nhãn làm việc. Đặt quy tắc trước khi có dữ liệu, vì sau khi thấy điểm thì rất khó không bị ảnh hưởng.

## 2026-10-21 — Chia theo ngày hay theo buổi: lý do ban đầu chưa đủ chặt
- **Chuyện gì xảy ra:** Tối 20/10 bị lỡ, còn 4 ngày quay. Claude đề xuất chia kiểm định chéo theo ngày (4 lần chia, dao động mạnh), cho rằng các buổi cùng ngày giống nhau vì ánh sáng và chỗ đặt máy. Mình phản biện: ánh sáng hôm nào cũng như nhau, và mỗi buổi đều đặt lại điện thoại nên chỗ đặt máy cũng khác.
- **Nguyên nhân:** Lý do ban đầu dựa vào giả định chứ chưa có số đo: bằng chứng thật chỉ là góc cổ của hai ngày lệch 10–20°, còn chênh lệch giữa hai buổi cùng ngày thì chưa đo.
- **Cách sửa:** Đổi đơn vị chấm điểm sang buổi (5 lần chia), với điều kiện đặt lại máy và ghi chú. Vẫn in kết quả theo ngày bên cạnh để đo độ chênh. Chốt trước khi có dữ liệu để không bị chọn theo kết quả.
- **Bài học:** Khi chọn cách chia dữ liệu, tách rõ điều đã đo với điều chỉ suy đoán; nếu không đo được ngay thì báo cả hai cách, rồi chốt quy tắc trước khi thấy điểm.

## 2026-10-21 — Quay lại hip_sag võng rõ: lần này tách được
- **Chuyện gì xảy ra:** Hiệp hip_sag quay thử lần 2 (2026-10-21T18-34-56) có hông dưới đường vai–cổ chân suốt cả 5 rep: max_hip_offset −0,024…−0,047, trung vị −0,056…−0,070 (≈ 7–9 cm). Hiệp lần 1 có rep gần chạm đường thẳng (−0,003).
- **Nguyên nhân:** Lần 1 võng quá nhẹ, nằm trong mức hông tự dao động khi tập đúng (±4–5 cm).
- **Cách sửa:** Luật hip_sag: max_hip_offset < −0,01 (hông chưa lần nào lên tới đường thẳng, đối xứng với hip_high). Rep võng rõ cách tập đúng ~5 cm; chỗ mỏng nhất là các rep mập mờ hôm 20/10 (~1,5 cm). Đưa hip_sag vào macro-F1, chốt trước lần chấm đầu tiên.
- **Bài học:** Cách đo đã đúng từ đầu; vấn đề nằm ở dữ liệu quay thử. Khi một lỗi "không tách được", kiểm tra lại cách làm lỗi trước khi đổi cách đo hay bỏ lỗi.

## 2026-10-23 — Baseline luật lần đầu: bắt được lỗi nhưng báo nhầm nhiều
- **Chuyện gì xảy ra:** 171 rep, 5 buổi (commit f02bd7f). Macro-F1 gộp 0,73 (theo buổi 0,74 ± 0,03), exact match 0,55. hip_high F1 0,98; incomplete_lockout 0,78; shallow và hip_sag 0,57; neck_drop (thử nghiệm) 0,83. Recall 0,78–0,96 nhưng precision chỉ 0,41–0,67: tổng 77 lần báo nhầm, 11 lần bỏ sót. Trên buổi quay thử, luật khớp 29/29 rep. Chia theo buổi và theo ngày cùng cho macro-F1 gộp 0,73 (chỉ có 2 ngày nên bằng chứng yếu).
- **Nguyên nhân:** Chưa phân tích. Ngưỡng được chọn trên chính buổi quay thử nên luôn đẹp hơn thực tế; ở dữ liệu mới rep không lỗi cũng hay chạm ngưỡng.
- **Cách sửa:** Chưa sửa: không chỉnh ngưỡng trên chính dữ liệu chấm điểm (rò rỉ). Tuần 3 học ngưỡng/random forest trên tập train của từng lần chia.
- **Bài học:** Điểm trên dữ liệu dùng để chọn ngưỡng không nói lên gì; quy tắc "tách buổi quay thử, chốt nhãn trước khi chạy" làm con số 0,73 đáng tin hơn con số 100% ban đầu.

## 2026-10-23 — Nhãn mỗi rep chỉ một lỗi làm precision bị đánh giá thấp
- **Chuyện gì xảy ra:** Baseline đạt macro-F1 gộp 0,73 với recall cao (0,78–0,96) nhưng precision thấp (0,41–0,67). 61/77 lần báo nhầm của 4 lỗi chính nằm ở hiệp của lỗi khác; trong hiệp tập đúng chỉ 16 lần (13 là hip_sag). Rep shallow báo nhầm có góc khuỷu 69–75° (chỉ vượt ngưỡng 2–8°), gần giống rep shallow có nhãn.
- **Nguyên nhân:** Lúc gán nhãn chỉ tick một lỗi cho mỗi rep (lỗi của hiệp), dù màn gán nhãn cho tick nhiều lỗi và thực tế lỗi hay đi cùng nhau (gục đầu thì khuỷu cũng nông). Luật báo lỗi thật mà nhãn thiếu → bị tính là báo nhầm. Riêng 13 lần hip_sag báo nhầm ở hiệp tập đúng thì chưa giải thích được (mức nền hông lệch theo buổi).
- **Cách sửa:** Giữ kết quả hiện tại làm v1 (nhãn một lỗi), lưu bản sao nhãn; gán nhãn lại v2 cho mọi rep, tick mọi lỗi nhìn thấy, không xem số đo; so v1 với v2.
- **Bài học:** Nhãn phải phản ánh thực tế, không phải ý định của hiệp. Nhãn một lỗi/rep vừa làm giảm precision, vừa dạy model một quy luật sai của cách quay (lỗi này loại trừ lỗi kia). Giữ cả hai bản kết quả để thấy tác động của nhãn.
- **Cập nhật (sau khi gán lại v2, v3):** giả thuyết này chưa được xác nhận (nhãn gán lại gần như không làm đổi macro-F1); xem mục "Gán nhãn lại hai lần (v2, v3)" bên dưới.

## 2026-10-24 — Gán nhãn lại hai lần (v2, v3): macro-F1 vẫn 0,72–0,73, chỉ đổi chỗ giữa precision và recall
- **Chuyện gì xảy ra:** Gán lại nhãn nhiều lỗi mỗi rep hai lần (v2 nhanh bằng hai ảnh tĩnh, v3 kỹ hơn). Macro-F1 gộp 0,73 → 0,72 → 0,72, exact match 0,55 cả ba. incomplete_lockout: nhãn 31 → 37 → 50, precision 0,67 → 0,83, recall 0,94 → 0,70; neck_drop: nhãn 29 → 28 → 36, precision 0,76 → 0,85, recall 0,90 → 0,81. shallow và hip_sag gần như không đổi.
- **Nguyên nhân:** Nhãn mới nằm sát ngoài ngưỡng của luật (top_elbow_angle 147–159° so với ngưỡng 146°; median_neck_angle 130–140° so với 128°): ngưỡng chọn từ buổi quay thử nghiêm hơn mắt người gán. Nghi vấn về công cụ: ảnh "Đỉnh" là end_frame trong khi số đo lấy max 0,5 s sau đó.
- **Cách sửa:** Chưa sửa. Ghi cả ba bản kết quả; v3 làm nhãn dùng tiếp; tuần 3 thử ngưỡng học trên tập train của từng lần chia.
- **Bài học:** Con số tổng (macro-F1) bền theo cách gán nhãn, còn precision/recall từng lỗi phụ thuộc mạnh vào ranh giới mà mắt người đặt; muốn so sánh công bằng thì ngưỡng nên được học từ chính nhãn.
