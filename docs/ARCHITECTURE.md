# Kiến trúc

> Bản phác thảo trước khi code. Được phép sửa, nhưng mỗi lần sửa interface thì cập nhật file này và ghi lý do vào mục "Quyết định thiết kế".

## 1. Luồng dữ liệu

Có hai đường vào, cùng đổ về `PoseSequence`. Từ đó trở đi chỉ có một pipeline Python.

```
ĐƯỜNG APP (dùng thật + tạo dữ liệu train)          ĐƯỜNG OFFLINE (thử nghiệm trên máy)
Trình duyệt: camera → MediaPipe JS                  video.mp4
   │  JSON keypoint (mục 2b)                           │  PoseEstimator.estimate()  (MediaPipe Python)
   │  load_session_json()                              │
   └──────────────────────┬────────────────────────────┘
                          ▼
PoseSequence        (T khung hình × K khớp × [x, y, visibility], fps, frame_size)
   │  FeatureExtractor.extract(exercise)
   ▼
FeatureSeries       (T × các góc/tín hiệu đã làm mượt, theo tên)
   │  RepSegmenter.segment(exercise)          (realtime: OnlineRepCounter.update() từng khung)
   ▼
list[Rep]           (start_frame, end_frame, đặc trưng tóm tắt của rep)
   │  FormClassifier.predict()
   ▼
list[RepResult]     (rep + tập lỗi dự đoán + độ tin cậy từng lỗi)
   │  Session (gom lại)
   ▼
Coach.summarize()  ──►  nhận xét
backend/ lưu DB    ──►  lịch sử, mục tiêu, streak  ──►  web/ hiển thị
```

Nguyên tắc:
- Mỗi bước nhận và trả **dữ liệu thuần** (dataclass + NumPy array). Mọi thứ trong `formcoach/` ở giữa pipeline test được mà không cần video, trình duyệt hay database.
- Chỉ `formcoach/pose/` (MediaPipe Python) và `formcoach/video/` chạm vào OpenCV/MediaPipe, và chỉ dùng cho đường offline.
- `formcoach/` **không import** FastAPI hay database. `backend/` gọi `formcoach`, không có chiều ngược lại.
- `web/` **không chứa logic ML**: chỉ chạy MediaPipe JS, gửi keypoint, hiển thị kết quả.
- **Dữ liệu train chỉ lấy từ đường app**, để keypoint lúc train và lúc dùng thật cùng một nguồn.

## 2. Kiểu dữ liệu chính

```python
@dataclass(frozen=True)
class PoseSequence:
    keypoints: np.ndarray      # shape (T, K, 3): x, y, visibility (toạ độ chuẩn hoá 0–1)
    joint_names: list[str]
    fps: float
    frame_size: tuple[int, int]  # (width, height) pixel, để đổi x, y về cùng thang đo

@dataclass(frozen=True)
class FeatureSeries:
    signals: dict[str, np.ndarray]   # ví dụ {"elbow_angle": (T,), "elbow_angle_raw": (T,)}
    fps: float

@dataclass(frozen=True)
class Rep:
    index: int
    start_frame: int
    end_frame: int
    features: dict[str, float]       # ví dụ {"min_elbow_angle": 82.0, "descent_time_s": 1.1}

@dataclass(frozen=True)
class RepResult:
    rep: Rep
    errors: frozenset[str]           # tập lỗi dự đoán, ví dụ {"shallow", "hip_sag"}; rỗng = good
    scores: dict[str, float] | None  # độ tin cậy cho từng lỗi (RuleBased: None)

@dataclass
class Session:
    session_id: str
    exercise: str
    results: list[RepResult]
```

Quy ước:
- **Khung không phát hiện người:** cả hàng trong `keypoints` là NaN, không bỏ khung. Index luôn bằng số frame. Mọi bước sau phải chịu được NaN.
- **Toạ độ:** x chuẩn hoá theo chiều rộng, y theo chiều cao, nên phải nhân với `frame_size` trước khi tính góc.
- **Tín hiệu `_raw`:** bản chưa làm mượt của một tín hiệu (ví dụ `elbow_angle_raw`), giữ trong `signals` để vẽ so sánh.
- **Nhãn multi-label:** mỗi rep có một tập lỗi (`frozenset[str]`), tập rỗng là `good`. "good" không phải một lỗi nên không nằm trong danh sách lỗi.
- **Rep không hợp lệ:** rep do bộ đếm cắt nhầm được đánh dấu `valid = false` lúc gán nhãn (nhãn thật, nằm ở `reps.csv`/DB, không nằm trong `Rep`). Loại khỏi train, dùng để đo độ chính xác của bộ đếm.

### 2b. File keypoint từ trang quay (`format_version` 1)

Đây là ranh giới giữa `web/` và Python. Trang quay xuất file này; `formcoach/pose/session_json.py` đọc thành `PoseSequence` + `SessionMeta` (`parse_session(dict)` / `load_session_json(path)`). Backend nhận cùng định dạng qua API.

```json
{
  "format_version": 1,
  "session_id": "2026-10-20T19-05-12_pushup",
  "exercise": "pushup",
  "set_errors": [],
  "recorded_at": "2026-10-20T19:05:12+07:00",
  "source": {"pose": "mediapipe-js", "version": "?", "model": "pose_landmarker_full"},
  "frame_size": [1280, 720],
  "joint_names": ["nose", "...", "right_foot_index"],
  "frames": [
    {"t_ms": 0,  "kp": [[0.51, 0.42, 0.98], "..."]},
    {"t_ms": 33, "kp": null}
  ]
}
```
- `kp: null` = khung không phát hiện người (đọc vào thành hàng NaN).
- `set_errors` = tập lỗi cố ý của cả hiệp, chọn trước khi quay (`[]` = hiệp tập đúng). Mọi rep của hiệp nhận tập này làm nhãn ban đầu, sửa từng rep sau trong màn hình gán nhãn.

Quy tắc kiểm tra (sai thì `SessionFormatError` nói rõ trường / khung / khớp nào sai):
- Đủ mọi trường ở trên; `format_version == 1`.
- `session_id` chỉ gồm `[A-Za-z0-9_-]`, 1–100 ký tự (được dùng làm tên file, chặn `../`).
- `exercise` có trong `formcoach.exercises.EXERCISES`; `set_errors` là danh sách không trùng, mỗi phần tử thuộc `error_labels` của bài đó.
- `recorded_at` dạng ISO 8601; `source` là object có giá trị chuỗi.
- `frame_size` = `[width, height]` số nguyên dương; `joint_names` đúng 33 tên MediaPipe theo thứ tự.
- `frames` ≥ 2 khung; `t_ms` là số không âm, **tăng ngặt**; `kp` là `null` hoặc 33 × `[x, y, visibility]` số hữu hạn (không nhận `true/false`).

**`t_ms` không đều (bản hiện tại):** `fps = 1000 / trung vị(khoảng cách t_ms)`, giữ nguyên các khung như đã ghi; `t_ms` gốc giữ trong `SessionMeta.timestamps_ms`. Chọn trung vị vì trình duyệt thỉnh thoảng khựng (vài trăm ms không có khung): trung bình bị kéo tụt, trung vị thì không. Có cần lấy mẫu lại về fps cố định (khung gần nhất, giữ NaN) hay không → quyết định ở bước 10 khi đo độ dao động thật trên điện thoại.

## 3. Interface

```python
class Exercise(ABC):
    name: str
    error_labels: list[str]                 # các lỗi hợp lệ, không gồm "good"
    def angle_definitions(self) -> dict[str, tuple[str, str, str]]: ...
        # tên góc -> (khớp A, khớp đỉnh B, khớp C), ví dụ "elbow_angle": ("shoulder", "elbow", "wrist")
        # tên khớp không có bên; FeatureExtractor chọn left_/right_ cho cả hiệp
    def tilt_definitions(self) -> dict[str, tuple[str, str]]: ...   # mặc định {}
        # tên tín hiệu -> (khớp A, khớp B): góc đoạn A→B so với phương ngang (0° nằm, 90° đứng)
        # ví dụ "body_tilt": ("shoulder", "ankle") để biết đang plank hay đang đứng
    def primary_signal(self) -> str: ...    # tín hiệu dùng để cắt rep, ví dụ "elbow_angle"
    def phase_thresholds(self) -> dict[str, float]: ...  # ngưỡng cho máy trạng thái
        # góc tính bằng độ; thời gian tính bằng giây, tên có hậu tố _s (ví dụ "min_rep_duration_s")
        # có ngưỡng "chờ sẵn sàng": chỉ bắt đầu đếm khi đã giữ tư thế đầu đủ lâu (ví dụ "ready_hold_s")
        # ngưỡng "đã lên lại" để đếm rep phải lỏng hơn ngưỡng lỗi incomplete_lockout, để rep lỗi vẫn được đếm
    def rule_thresholds(self) -> dict[str, float]: ...   # ngưỡng cho baseline luật

class PushUp(Exercise): ...                 # làm trước
class Squat(Exercise): ...                  # mở rộng

class PoseEstimator(ABC):                   # chỉ đường offline
    def estimate(self, video_path: Path) -> PoseSequence: ...

def load_session_json(path: Path) -> tuple[PoseSequence, SessionMeta]: ...   # đường app (§2b)
EXERCISES: dict[str, type[Exercise]]        # tên bài → lớp; get_exercise(name) tạo instance

class FeatureExtractor:
    def extract(self, pose: PoseSequence, exercise: Exercise) -> FeatureSeries: ...

class RepSegmenter:                         # cả hiệp, kết quả chính thức
    def segment(self, features: FeatureSeries, exercise: Exercise) -> list[Rep]: ...

class OnlineRepCounter:                     # realtime, tuần 3
    def __init__(self, exercise: Exercise, fps: float): ...
    def update(self, keypoints: np.ndarray) -> int: ...  # nhận 1 khung (K, 3), trả số rep hiện tại

class FormClassifier(ABC):                  # multi-label: mỗi lỗi một quyết định có/không
    def fit(self, reps: list[Rep], errors: list[frozenset[str]]) -> None: ...   # RuleBased: không làm gì
    def predict(self, reps: list[Rep]) -> list[RepResult]: ...

class Coach(ABC):                           # TemplateCoach, DeepSeekCoach
    def summarize(self, session: Session) -> str: ...
```

Ghi chú:
- `RepSegmenter` và `OnlineRepCounter` dùng **chung máy trạng thái và ngưỡng** từ `Exercise`. Khác nhau ở bộ lọc: hết hiệp dùng Savitzky–Golay (nhìn cả trước lẫn sau), realtime dùng bộ lọc nhân quả (ví dụ EMA). Số đếm realtime có thể lệch, kết quả hết hiệp là chuẩn.
- `TemporalNet` (mạng chuỗi) đã chuyển sang mở rộng. Khi làm, cân nhắc thêm trường `signals` vào `Rep` hoặc truyền `FeatureSeries` kèm theo.

## 4. Backend và web (bản nháp, chốt API đầu tuần 3)

### Đã có (tuần 1, `backend/app.py`)
| Method | Đường dẫn | Việc |
|---|---|---|
| `GET` | `/api/exercises/{name}` | Tên bài + `error_labels` (trang quay lấy danh sách lỗi từ đây). Tên lạ → 404 |
| `POST` | `/api/sessions` | Kiểm tra bằng `parse_session` (§2b) → lưu nguyên văn vào `$FORMCOACH_DATA_DIR/sessions/{exercise}/{session_id}.json` (mặc định `data/`) → trả `session_id, exercise, n_frames, duration_s, fps, frames_with_person`. Sai định dạng → 422 kèm lý do; trùng `session_id` → 409, không ghi đè. **Chưa** chạy pipeline, chưa DB/đăng nhập |

Chạy: `uvicorn backend.app:app --port 8000` (chỉ nghe 127.0.0.1; điện thoại đi qua proxy Vite).

### Endpoint dự kiến (tuần 3–4)
| Method | Đường dẫn | Việc |
|---|---|---|
| `POST` | `/api/auth/register`, `/api/auth/login` | Đăng nhập |
| `POST` | `/api/sessions` | Nhận JSON keypoint (mục 2b) → chạy pipeline → lưu → trả rep + nhãn |
| `GET` | `/api/sessions/{id}` | Kết quả một buổi, kèm nhận xét coach |
| `PATCH` | `/api/sessions/{id}/reps/{idx}` | Sửa nhãn một rep (màn hình gán nhãn) |
| `WS` | `/api/live` | Nhận keypoint từng khung, trả số rep hiện tại |
| `GET`/`PUT` | `/api/goals` | Đọc / đặt mục tiêu |
| `GET` | `/api/progress?from=&to=` | Tổng rep, tỉ lệ rep đúng, streak, dữ liệu đồ thị |

### Bảng dữ liệu dự kiến
```
users     (id, email, password_hash, created_at)
sessions  (id, user_id, exercise, recorded_at, set_errors, keypoints_json, source)
reps      (id, session_id, idx, start_frame, end_frame, features_json, predicted_errors, true_errors, valid)
goals     (id, user_id, exercise, daily_reps, min_good_ratio, from_date)
```
- `true_errors` là tập lỗi bạn gán (dùng để train), `predicted_errors` là tập lỗi model đoán. Tách hai cột để không lẫn. `valid = false` là rep bộ đếm cắt nhầm.
- Tiến độ, "đã xong" và streak **tính lúc đọc** từ `sessions`/`reps`/`goals`, không lưu sẵn. Logic này là hàm thuần trong `formcoach/progress/`, test bằng dữ liệu giả.
- Không lưu video. API key DeepSeek chỉ ở server (biến môi trường).

## 5. Cấu trúc thư mục dự kiến

```
formcoach/             # lõi Python, không phụ thuộc web/DB
 ├── types.py          # dataclass ở mục 2
 ├── exercises/        # Exercise, PushUp, Squat
 ├── pose/             # joints (33 tên khớp), PoseEstimator, MediaPipeEstimator (offline), load_session_json
 ├── features/         # geometry (tính góc), smoothing, FeatureExtractor, RepSegmenter, OnlineRepCounter
 ├── models/           # FormClassifier, RuleBased, RandomForest
 ├── coach/            # Coach, TemplateCoach, DeepSeekCoach
 ├── progress/         # tính mục tiêu, tỉ lệ rep đúng, streak (hàm thuần)
 ├── video/            # đọc video cho đường offline
 ├── pipeline.py       # ghép các bước
 └── __main__.py       # CLI cho thử nghiệm offline
backend/               # FastAPI: route, WebSocket, database, đăng nhập; gọi formcoach
web/                   # React (Vite): quay, gán nhãn, kết quả, dashboard
evaluation/            # chia theo buổi, metric, so sánh mô hình
tools/                 # script lẻ (probe MediaPipe, vẽ đồ thị tín hiệu)
notebooks/             # khám phá tín hiệu, biểu đồ
tests/                 # test Python với dữ liệu tổng hợp
data/                  # KHÔNG commit
```

## 6. Pattern và lý do

| Pattern | Ở đâu | Lý do |
|---|---|---|
| Strategy | `PoseEstimator`, `FormClassifier`, `Coach` | Đổi mô hình/cách làm và so sánh mà không sửa pipeline |
| Template/Polymorphism | `Exercise` | Thêm bài tập mới = thêm một lớp, không sửa code chung |
| State | `RepSegmenter`, `OnlineRepCounter` | Rep là chuỗi pha (lên → xuống → đáy → lên), tránh đếm đôi |
| Adapter | `load_session_json`, `PoseEstimator` | Hai nguồn keypoint khác nhau, cùng ra `PoseSequence` |
| Cache | keypoint trong `data/keypoints/` | Pose offline chậm, chỉ chạy một lần mỗi video |
| Lớp mỏng | `backend/` | Chỉ nhận/trả HTTP và lưu DB; logic nằm trong `formcoach/` để test được |

## 7. Quyết định thiết kế

Ghi theo dạng: ngày — quyết định — lý do — phương án đã loại.

- **2026-10-17 — Chọn bên trái/phải theo visibility trung bình của cả video.** `Exercise` dùng tên khớp không có bên (`"knee"`), `FeatureExtractor` chọn bên nhìn rõ hơn rồi ghép `left_`/`right_`. — MediaPipe trả khớp theo bên, quay từ hông thì một bên bị che. — Đã loại: chọn bên theo từng khung (góc nhảy qua lại giữa hai chân); khai báo góc riêng cho từng bên trong `Exercise` (lặp code).
- **2026-10-17 — Thêm `frame_size` vào `PoseSequence`.** — x chuẩn hoá theo chiều rộng, y theo chiều cao; tính góc trực tiếp trên toạ độ 0–1 sẽ méo khi khung không vuông. — Đã loại: lưu toạ độ pixel (cache và annotator bị gắn với độ phân giải).
- **2026-10-17 — Tín hiệu chưa làm mượt đặt trong `signals` với hậu tố `_raw`.** — Cần cho đồ thị so sánh trước/sau làm mượt mà không đổi interface. — Đã loại: thêm trường `meta` vào `FeatureSeries`.
- **2026-10-17 — Khung không có người là hàng NaN.** — Giữ index = số frame để annotator và rep khớp với video. — Đã loại: bỏ khung (lệch frame so với video).
- **2026-10-17 — Ngưỡng thời gian tính bằng giây (hậu tố `_s`).** — Video điện thoại có thể 24/30/60 fps; đổi sang frame bằng `fps` lúc chạy. — Đã loại: ngưỡng theo số frame.
- **2026-10-17 — Đổi `formcoach/io/` thành `formcoach/video/`.** — Tránh nhầm với module chuẩn `io` khi đọc code. — Đã loại: giữ `io/` (vẫn chạy đúng nhờ import tuyệt đối, nhưng dễ nhầm).
- **2026-10-17 — Chuyển thành web app có backend (FastAPI + React), deploy, trong 3–4 tuần.** — Muốn dùng hằng ngày trên điện thoại, có mục tiêu/streak, và học thêm phần đưa model thành sản phẩm. — Đã loại: CLI thuần (không dùng hằng ngày được); web chạy local bằng Streamlit (không có backend, không xem được ở mọi nơi); app native (gần như dự án mới).
- **2026-10-17 — Pose chạy trong trình duyệt (MediaPipe JS), server chỉ nhận keypoint.** — Video không rời khỏi máy, server rẻ, khung xương hiện ngay khi tập. — Đã loại: upload video cho server xử lý (chậm, tốn CPU, video riêng tư nằm trên cloud).
- **2026-10-17 — Dữ liệu train chỉ lấy từ trang quay của app.** — Keypoint MediaPipe JS và Python có thể lệch hệ thống; train một nguồn, dùng nguồn khác là domain shift. MediaPipe Python chỉ dùng để thử nghiệm offline. — Đã loại: quay video bằng app camera rồi chạy MediaPipe Python để tạo dataset.
- **2026-10-17 — Đếm rep realtime qua WebSocket, logic ở Python.** — Một bản logic duy nhất, có test. — Đã loại: viết lại bộ đếm bằng JavaScript (hai bản logic, số đếm có thể lệch nhau).
- **2026-10-17 — Push-up làm trước, squat chuyển sang mở rộng.** — Ưu tiên của người dùng. Rủi ro: pose push-up kém hơn (nằm ngang, bị che), nên kiểm tra ngày 1; nếu kém thì đổi lại. — Đã loại: squat trước.
- **2026-10-17 — Giữ random forest và đánh giá theo buổi; bỏ mạng chuỗi khỏi lõi.** — Phần đánh giá là giá trị học chính; DL không vừa 3–4 tuần cùng với web. — Đã loại: cắt cả random forest để kịp web.
- **2026-10-17 — Nhãn multi-label: mỗi rep một tập lỗi, rỗng = good.** `RepResult.label/confidence` → `errors/scores`, `Exercise.labels` → `error_labels`, `FormClassifier.fit` nhận tập lỗi. — Lỗi push-up nằm ở các bộ phận khác nhau và hay xảy ra cùng lúc (nhất là khi mệt); single-label buộc chọn theo ưu tiên, mất thông tin và làm lẫn các lớp. — Đã loại: single-label có thứ tự ưu tiên. Hệ quả: đánh giá theo từng lỗi (precision/recall/F1, ma trận 2×2), cần đủ mẫu dương cho mỗi lỗi.
- **2026-10-17 — Push-up thêm `incomplete_lockout` và `neck_drop` (thử nghiệm).** — `incomplete_lockout` đo dễ (góc khuỷu lớn nhất ở đỉnh rep). `neck_drop` có thể nhiễu vì khớp mặt khi quay ngang kém chính xác: vẫn gán nhãn, chỉ train nếu dữ liệu cho thấy tách được. — Đã loại: chỉ 4 nhãn cũ.
- **2026-10-17 — `not_ready` không phải nhãn lỗi.** Bộ đếm có trạng thái "chờ sẵn sàng"; rep cắt nhầm đánh dấu `valid = false` lúc gán nhãn. — "Đây có phải rep không" và "rep sai ở đâu" là hai câu hỏi khác nhau, gộp vào một classifier làm nó khó học. — Đã loại: thêm lớp `not_ready` cho classifier.
- **2026-10-19 — Thêm `Exercise.tilt_definitions()` (mặc định `{}`).** PushUp: `body_tilt = (shoulder, ankle)`. — Trạng thái "chờ sẵn sàng" phải phân biệt plank thẳng tay với đứng buông tay; cả hai có góc khuỷu ~160–170°, chỉ khác thân nằm hay đứng. Góc 3 khớp không đo được độ nghiêng so với phương ngang. — Đã loại: dùng góc vai–hông–cổ chân (thẳng ~180° cả khi đứng lẫn khi plank); thêm "khớp ảo" nằm ngang vào `angle_definitions` (khó hiểu).
- **2026-10-19 — `load_session_json` trả `(PoseSequence, SessionMeta)`; thêm `EXERCISES` / `get_exercise`.** — File quay mang thông tin không thuộc `PoseSequence` (session_id, bài tập, tập lỗi của hiệp, t_ms gốc) mà backend và màn hình gán nhãn cần; bảng tra tên → `Exercise` để kiểm tra `set_errors` và để backend tạo bài tập từ tên. — Đã loại: nhét metadata vào `PoseSequence` (đổi kiểu dữ liệu lõi cho một nguồn); trả dict tự do (không có type).
- **2026-10-19 — fps của file quay = 1000 / trung vị khoảng cách `t_ms`, chưa lấy mẫu lại.** — Trung vị không bị kéo tụt khi trình duyệt khựng; giữ nguyên khung đơn giản và đủ dùng cho tới khi có số đo thật. — Đã loại (tạm): lấy mẫu lại về fps cố định ngay (quyết định ở bước 10); fps trung bình (bị khựng kéo tụt).
- **2026-10-17 — Coach dùng DeepSeek API, dự phòng bằng `TemplateCoach`.** — Nhận xét tự nhiên, chi phí thấp; chỉ gửi số liệu, không gửi hình ảnh. Cần kiểm tra docs API khi làm (chưa xác minh độ tương thích với thư viện `openai`). — Đã loại: chỉ mẫu câu; model local.
