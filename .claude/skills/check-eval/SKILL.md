---
name: check-eval
description: Review code đánh giá mô hình (chia train/test, metric, so sánh mô hình) để tìm rò rỉ dữ liệu và lỗi metric. Dùng khi người dùng gõ /check-eval hoặc vừa viết/sửa code trong evaluation/.
---

# Check eval

Review phần đánh giá (dù người dùng hay Claude viết). Chỉ ra vấn đề và giải thích vì sao nó làm sai số liệu. Chỉ sửa code khi người dùng yêu cầu.

Kiểm tra theo danh sách:

1. **Chia dữ liệu theo buổi quay (`session_id`)**, không theo rep. Mọi rep của một buổi phải nằm cùng một phía. Kiểm tra cả cross-validation (cần `GroupKFold` hoặc tương đương).
2. **Không có thông tin từ test lọt vào train:** chuẩn hoá (scaler), chọn đặc trưng, chọn ngưỡng luật, tinh chỉnh siêu tham số đều chỉ được fit trên train.
3. **Baseline luật** được đánh giá trên **cùng tập test** với model.
4. **Metric cho multi-label:** mỗi rep có một tập lỗi (rỗng = good). Phải có precision/recall/F1 **cho từng lỗi**, macro-F1, tỉ lệ rep đoán đúng toàn bộ tập lỗi, ma trận 2×2 cho từng lỗi; không chỉ accuracy. Lỗi hiếm (ít mẫu dương) phải được báo riêng số mẫu, và mỗi lỗi phải có mẫu dương ở cả train lẫn test.
5. **Độ bất định:** tập test nhỏ thì có báo sai số hoặc khoảng tin cậy không, có kết luận vội khi chênh lệch nhỏ không.
6. **Nhãn:** lỗi không hợp lệ (ngoài `Exercise.error_labels`), rep thiếu nhãn, hoặc nhãn bị sửa sau khi đã nhìn kết quả test. Rep `valid = false` phải bị loại khỏi cả train lẫn test.
7. **Seed và tái lập:** có cố định random seed, có lưu cách chia để chạy lại cho cùng kết quả.
8. **Nguồn dữ liệu:** train và test đều phải từ trang quay của app (MediaPipe JS). Không trộn keypoint từ MediaPipe Python (đường offline), vì hai nguồn có thể lệch hệ thống.
9. **Lỗi thử nghiệm (`neck_drop`):** nếu chưa được xác nhận là đo được, báo riêng, không gộp vào macro-F1 chính.

Báo cáo: liệt kê vấn đề theo mức độ (nghiêm trọng → nhỏ), mỗi vấn đề gồm vị trí (`file:dòng`), vì sao nó làm sai số liệu, và gợi ý hướng sửa bằng lời. Nếu không thấy vấn đề, nói rõ đã kiểm tra những gì.
