-- Lược đồ SQLite của app (ARCHITECTURE §4). Chạy mỗi lần mở kết nối nên mọi lệnh phải
-- idempotent (IF NOT EXISTS). Chỉ dùng SQL chuẩn để sau này đổi sang Postgres/MySQL rẻ.
-- Thời gian lưu dạng chuỗi ISO 8601 UTC; danh sách/dict lưu dạng chuỗi JSON.
-- DB chỉ giữ tài khoản và kết quả app đã phân tích. File quay và file nhãn trong data/ vẫn là
-- dữ liệu huấn luyện, không chép vào đây.

-- email lưu đúng như người dùng gõ; trùng nhau được so KHÔNG phân biệt hoa thường
-- (chỉ mục lower(email) bên dưới, truy vấn dùng `lower(email) = lower(?)`).
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

-- Phiên đăng nhập: chỉ lưu sha256 của token, token thật nằm trong cookie của trình duyệt.
-- Lộ DB thì cũng không dùng lại được token.
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- Một hiệp tập đã phân tích. (exercise, session_id) khớp đường dẫn file
-- data/sessions/{exercise}/{session_id}.json.
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    exercise    TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    recorded_at TEXT,
    set_errors  TEXT NOT NULL,  -- JSON list: lỗi cố ý chọn lúc quay
    source      TEXT,           -- JSON: nguồn pose (vd mediapipe-js)
    model_name  TEXT NOT NULL,  -- bộ phân loại đã chấm hiệp này (rules, stump, rf)
    n_frames    INTEGER NOT NULL,
    duration_s  REAL NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (exercise, session_id)
);

-- Kết quả từng rep do bộ phân loại đoán. Nhãn thật vẫn ở file nhãn (§2c), không lưu ở đây.
CREATE TABLE IF NOT EXISTS reps (
    id               INTEGER PRIMARY KEY,
    session_pk       INTEGER NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    idx              INTEGER NOT NULL,
    start_frame      INTEGER NOT NULL,
    end_frame        INTEGER NOT NULL,
    features_json    TEXT NOT NULL,
    predicted_errors TEXT NOT NULL,  -- JSON list, rỗng = rep tốt
    scores_json      TEXT NOT NULL,  -- JSON dict lỗi → điểm
    UNIQUE (session_pk, idx)
);

-- Mục tiêu rep mỗi ngày (tuần 4). Giữ cả lịch sử: mục tiêu áp dụng từ from_date tới khi có mục
-- tiêu mới hơn, nên đổi mục tiêu không chấm lại ngày cũ. Tiến độ/streak tính lúc đọc
-- (formcoach/progress/goals.py), không lưu cờ "đã đạt". Đặt lại trong cùng ngày thì ghi đè.
CREATE TABLE IF NOT EXISTS goals (
    id             INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    exercise       TEXT NOT NULL,
    daily_reps     INTEGER NOT NULL,
    min_good_ratio REAL,           -- NULL = không xét tỉ lệ rep đúng
    from_date      TEXT NOT NULL,  -- YYYY-MM-DD theo giờ điện thoại
    created_at     TEXT NOT NULL,
    UNIQUE (user_id, exercise, from_date)
);

-- Lần đăng nhập sai, để khoá tạm khi bị đoán mật khẩu (backend/auth.py, D0b). Ghi theo email
-- viết thường, kể cả email chưa đăng ký (không lộ email nào có thật). Không khoá ngoại tới users.
-- Bản ghi cũ hơn cửa sổ đếm + thời gian khoá bị xoá ở mỗi lần đăng nhập.
CREATE TABLE IF NOT EXISTS login_failures (
    id        INTEGER PRIMARY KEY,
    email_key TEXT NOT NULL,  -- lower(email)
    at        TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower ON users (lower(email));
CREATE INDEX IF NOT EXISTS idx_login_failures_email ON login_failures (email_key, at);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);
