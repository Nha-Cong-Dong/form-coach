# Ảnh chạy app trên server (Railway, hoặc bất kỳ nơi nào chạy Docker).
# Hai tầng: tầng 1 dùng Node build web/ ra web/dist; tầng 2 chỉ có Python, chép web/dist sang và
# để uvicorn phục vụ cả trang lẫn API (backend/app.py, mount_web). Node không nằm trong ảnh cuối.
#
# Dữ liệu (SQLite, file hiệp, file mô hình .pkl) KHÔNG nằm trong ảnh: chúng ở volume gắn vào
# /data lúc chạy (FORMCOACH_DATA_DIR). Build lại ảnh không làm mất dữ liệu.

# ---- Tầng 1: build web ----
FROM node:24-slim AS web
WORKDIR /src/web
# Cài thư viện trước khi chép code: package*.json ít đổi nên Docker dùng lại lớp cache này.
COPY web/package.json web/package-lock.json ./
RUN npm ci
# Model pose của MediaPipe không có trong git (assets/ bị bỏ qua); tải về đúng chỗ
# copy-mediapipe-assets.mjs tìm (../assets so với web/).
ADD https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task /src/assets/pose_landmarker_full.task
COPY web/ ./
RUN npm run build

# ---- Tầng 2: chạy server ----
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FORMCOACH_DATA_DIR=/data \
    FORMCOACH_WEB_DIR=/app/web/dist
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY formcoach/ formcoach/
COPY backend/ backend/
COPY --from=web /src/web/dist web/dist
# Railway đặt biến PORT và cần app nghe 0.0.0.0; chạy máy khác thì mặc định 8000.
# Cần shell để thay $PORT; `exec` để uvicorn thay chỗ shell và nhận tín hiệu tắt (SIGTERM) khi
# redeploy, đóng gọn gàng thay vì bị giết sau 10 giây.
CMD ["sh", "-c", "exec uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
