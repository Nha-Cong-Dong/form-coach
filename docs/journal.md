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
