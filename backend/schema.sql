-- Lược đồ SQLite của app (ARCHITECTURE §4). Chạy mỗi lần mở kết nối nên mọi lệnh phải
-- idempotent (IF NOT EXISTS). Chỉ dùng SQL chuẩn để sau này đổi sang Postgres/MySQL rẻ.
-- Thời gian lưu dạng chuỗi ISO 8601 UTC; danh sách/dict lưu dạng chuỗi JSON.
-- DB chỉ giữ tài khoản và kết quả app đã phân tích. File quay và file nhãn trong data/ vẫn là
-- dữ liệu huấn luyện, không chép vào đây.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
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

CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);
