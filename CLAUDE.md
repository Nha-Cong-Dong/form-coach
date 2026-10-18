# CLAUDE.md

Form Coach: web app phân tích kỹ thuật push-up (squat sau) qua camera trình duyệt (pose → góc khớp → rep → lỗi → coach, mục tiêu, streak).
Spec: `README.md`. Kiến trúc và interface: `docs/ARCHITECTURE.md`. Tiêu chí nhãn: `docs/labeling-criteria.md`.

## Mục tiêu của dự án: HỌC, không chỉ chạy được

Mình làm dự án này để học qua vibe code. Vì vậy:

- **Làm từng bước nhỏ.** Mỗi lần chỉ một chức năng, rồi dừng lại để mình chạy thử. Không viết nhiều module một lúc.
- **Giải thích ngắn lý do** của mỗi quyết định không hiển nhiên (vì sao chọn cách này, đánh đổi gì). Ngắn gọn, không giảng bài.
- **Không tự ý thêm tính năng** ngoài README. Có ý hay thì đề xuất, chờ mình đồng ý.
- **Khi mình hỏi "tại sao"**, trả lời khái niệm trước, code sau.
- Nếu không chắc về API của một thư viện (MediaPipe, scikit-learn...), nói rõ là không chắc và đề xuất cách kiểm tra, đừng đoán.
- **Code xong thì tóm tắt thay đổi:** liệt kê file đã thêm và file đã sửa, mỗi file một dòng nói nó làm gì hoặc sửa gì và để làm gì. Ngắn gọn, không dán lại code.

## Phần đánh giá và dữ liệu

- **Chia train/test và metric (`evaluation/`):** Claude được viết, nhưng trước khi viết phải giải thích cách chia (vì sao theo buổi quay) và ý nghĩa từng metric. Viết xong thì tự soát theo checklist của `/check-eval`.
- **Tiêu chí nhãn (`docs/labeling-criteria.md`):** mình quyết định. Claude có thể gợi ý, nhưng không tự điền ngưỡng.
- **Phân tích kết quả và phần "hạn chế" trong README:** mình viết, Claude góp ý.

## Quy tắc kỹ thuật

- Python 3.11+, môi trường **conda** tên `formcoach`. Cài thư viện bằng `pip` trong env đó và ghi vào `requirements.txt` (chỉ dùng `conda install` khi pip không cài được, và ghi vào `environment.yml`).
- Không dùng `uv`, `poetry` hay tạo venv riêng.
- Format và lint: `ruff`. Test: `pytest`. Có type hint cho hàm public.
- Theo đúng interface trong `docs/ARCHITECTURE.md`. Muốn đổi interface thì hỏi trước và cập nhật file đó.
- Logic thuần (tính góc, làm mượt, đếm rep, đặc trưng) **không phụ thuộc** OpenCV/MediaPipe, để test được bằng dữ liệu tổng hợp.
- Mỗi hàm xử lý tín hiệu mới cần một test với tín hiệu tổng hợp có đáp án biết trước (ví dụ sóng sin 5 chu kỳ → 5 rep).
- Không hard-code ngưỡng góc trong code logic, đặt trong config của từng `Exercise`.
- Không thêm thư viện mới mà không nói lý do.
- `formcoach/` là lõi Python thuần, không import FastAPI/database. `backend/` (FastAPI) chỉ gọi `formcoach`.
- `web/` (React + Vite, npm) không chứa logic ML: chỉ chạy MediaPipe JS, gửi keypoint, hiển thị kết quả.
- Dữ liệu train chỉ lấy từ trang quay của app (MediaPipe JS). MediaPipe Python chỉ để thử nghiệm offline.

## Dữ liệu và bí mật

- **Không đọc, liệt kê hay sửa `data/`** (video cá nhân). Khi cần dữ liệu thử, sinh dữ liệu tổng hợp.
- Không đọc `.env`. API key (DeepSeek) chỉ qua biến môi trường ở server, không bao giờ đưa vào `web/`.
- Không commit video, keypoint, model đã train.

## Lệnh thường dùng

```bash
conda activate formcoach
pip install -r requirements.txt
pytest                   # chạy test
ruff check .             # lint
ruff format .            # format
```

(Cập nhật khi đã có entrypoint, ví dụ `python -m formcoach analyze <video>`.)

## Skill có sẵn

- `/explain` — giải thích đoạn code vừa viết và hỏi lại mình vài câu để kiểm tra hiểu
- `/check-eval` — review phần đánh giá, tìm rò rỉ dữ liệu và lỗi metric
- `/journal` — ghi một lần vấp vào `docs/journal.md`
