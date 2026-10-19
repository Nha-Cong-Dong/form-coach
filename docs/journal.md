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
- **Bài học:** Biết chính xác con số đo cái gì trước khi đặt ngưỡng, và luôn thử trên dữ liệu thật — test tự viết mang cùng hiểu lầm với người viết.
