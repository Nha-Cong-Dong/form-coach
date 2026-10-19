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
