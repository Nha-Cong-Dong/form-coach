---
name: explain
description: Giải thích đoạn code vừa viết hoặc một file/hàm được chỉ định, rồi hỏi lại người dùng vài câu để kiểm tra họ đã hiểu. Dùng khi người dùng gõ /explain hoặc muốn hiểu code AI vừa sinh ra.
---

# Explain

Mục tiêu: giúp người dùng **hiểu** code, không chỉ đọc lướt.

1. Xác định đoạn cần giải thích: tham số người dùng đưa (file, hàm), hoặc thay đổi gần nhất trong phiên.
2. Giải thích theo thứ tự:
   - **Mục đích:** đoạn này làm gì trong pipeline (một câu).
   - **Ý tưởng chính:** khái niệm đằng sau (ví dụ tích vô hướng, làm mượt, máy trạng thái), bằng lời đơn giản, có ví dụ số nhỏ nếu hợp.
   - **Đi qua code:** chỉ những dòng quan trọng, không đọc từng dòng.
   - **Chỗ dễ sai:** trường hợp biên, giả định ngầm (đơn vị, thứ tự trục, chia cho 0, NaN).
3. Hỏi **2–3 câu kiểm tra**, ví dụ "nếu fps giảm một nửa thì kết quả thay đổi thế nào?" hoặc "vì sao cần clip giá trị cos?". Không đưa đáp án ngay, chờ người dùng trả lời rồi nhận xét.
4. Nếu người dùng trả lời sai, giải thích lại phần đó theo cách khác, không lặp lại y nguyên.

Giữ ngắn. Tiếng Việt, thuật ngữ kỹ thuật giữ nguyên tiếng Anh.
