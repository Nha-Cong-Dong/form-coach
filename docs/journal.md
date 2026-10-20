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
