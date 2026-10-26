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
    # mỗi tín hiệu: min_/max_/median_<tên>; thêm top_<tín hiệu chính> = đỉnh trong
    # top_settle_s ngay SAU rep (cho incomplete_lockout); duration_s, descent_time_s, bottom_frame

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
- **Rep không hợp lệ:** rep do bộ đếm cắt nhầm được đánh dấu `valid = false` lúc gán nhãn (nhãn thật, nằm trong file nhãn §2c / DB sau này, không nằm trong `Rep`). Loại khỏi train, dùng để đo độ chính xác của bộ đếm.

### 2b. File keypoint từ trang quay (`format_version` 1)

Đây là ranh giới giữa `web/` và Python. Trang quay xuất file này; `formcoach/pose/session_json.py` đọc thành `PoseSequence` + `SessionMeta` (`parse_session(dict)` / `load_session_json(path)`). Backend nhận cùng định dạng qua API.

Phía web, định dạng nằm ở `web/src/session/format.ts` (kiểu TypeScript + hàm dựng file). Hai phía được kiểm tra chéo bằng `tests/test_web_format.py`: chạy `web/scripts/sample-session.ts` bằng Node để dựng file từ chính code TypeScript, rồi đọc bằng `load_session_json`. Đổi định dạng ở một phía mà quên phía kia thì test này đỏ.

```json
{
  "format_version": 1,
  "session_id": "2026-10-20T19-05-12_pushup",
  "exercise": "pushup",
  "set_errors": [],
  "recorded_at": "2026-10-20T19:05:12+07:00",
  "notes": "tối, đèn trần, áo đen",
  "capture_mode": "dataset",
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
- `notes` (**tuỳ chọn**, thêm 2026-10-20, `format_version` vẫn 1) = ghi chú điều kiện quay (ánh sáng, quần áo, chỗ quay, đau mỏi), nhập ở trang quay. Dùng khi kiểm định chéo để giải thích một buổi lệch hẳn các buổi khác. File cũ không có trường này → `SessionMeta.notes = ""`.
- `capture_mode` (**tuỳ chọn**, thêm 2026-10-24, `format_version` vẫn 1) = `"dataset"` (màn Quay dữ liệu, có lỗi cố ý) hoặc `"train"` (chế độ Tập của app, không có kịch bản lỗi: `set_errors` phải rỗng, và rỗng ở đây KHÔNG có nghĩa "cố ý tập đúng"). File cũ không có trường này → `"dataset"`. Đánh giá (`evaluation_rows`) mặc định bỏ hiệp `"train"`; app vẫn học từ hiệp Tập nếu đã gán nhãn.
- `set_errors` = tập lỗi cố ý của cả hiệp, chọn trước khi quay (`[]` = hiệp tập đúng). Mọi rep của hiệp nhận tập này làm nhãn ban đầu, sửa từng rep sau trong màn hình gán nhãn.

Quy tắc kiểm tra (sai thì `SessionFormatError` nói rõ trường / khung / khớp nào sai):
- Đủ mọi trường ở trên; `format_version == 1`.
- `session_id` chỉ gồm `[A-Za-z0-9_-]`, 1–100 ký tự (được dùng làm tên file, chặn `../`).
- `exercise` có trong `formcoach.exercises.EXERCISES`; `set_errors` là danh sách không trùng, mỗi phần tử thuộc `error_labels` của bài đó.
- `recorded_at` dạng ISO 8601; `source` là object có giá trị chuỗi; `notes` (nếu có) là chuỗi ≤ 1000 ký tự.
- `frame_size` = `[width, height]` số nguyên dương; `joint_names` đúng 33 tên MediaPipe theo thứ tự.
- `frames` ≥ 2 khung; `t_ms` là số không âm, **tăng ngặt**; `kp` là `null` hoặc 33 × `[x, y, visibility]` số hữu hạn (không nhận `true/false`).

**`t_ms` không đều (bản hiện tại):** `fps = 1000 / trung vị(khoảng cách t_ms)`, giữ nguyên các khung như đã ghi; `t_ms` gốc giữ trong `SessionMeta.timestamps_ms`. Chọn trung vị vì trình duyệt thỉnh thoảng khựng (vài trăm ms không có khung): trung bình bị kéo tụt, trung vị thì không. **Không lấy mẫu lại** (chốt 2026-10-20 bằng số đo thật trên điện thoại: trung vị 82,7 ms ≈ 12 fps, lệch chuẩn 17%, lớn nhất 108 ms, 0 lần khựng). `python -m formcoach analyze <file>.json` in dòng "Khoảng cách khung" để theo dõi; nếu lệch chuẩn > 20% trung vị hoặc có khoảng trống > 3× trung vị thì xem lại quyết định này.

### 2c. File nhãn (`format_version` 1, `formcoach/labels.py`)

Mỗi hiệp một file `data/labels/<bài>/<session_id>.json`, ghi bằng màn hình gán nhãn (qua backend):

```json
{
  "format_version": 1,
  "session_id": "2026-10-20T19-05-12_pushup",
  "exercise": "pushup",
  "labeled_at": "2026-10-20T21:30:00+07:00",
  "segmenter_thresholds": {"top_min": 140.0, "min_amplitude_deg": 35.0, "...": 0},
  "reps": [
    {"rep_index": 0, "start_frame": 30, "end_frame": 75, "start_s": 1.0, "end_s": 2.5,
     "valid": true, "errors": ["hip_sag", "shallow"], "note": ""}
  ]
}
```
- Nhãn ban đầu (`default_labels`) = `set_errors` của hiệp cho mọi rep, `valid = true`.
- Rep gắn nhãn qua **ranh giới** (frame + giây), không chỉ số thứ tự; `segmenter_thresholds` ghi ngưỡng bộ đếm lúc cắt. `check_alignment` so nhãn với rep cắt lại (lệch > 0,2 s hoặc khác số rep → báo), để đổi ngưỡng bộ đếm sau này không làm nhãn gắn nhầm rep.
- Kiểm tra: `rep_index` liên tiếp từ 0, rep không chồng nhau, lỗi ⊂ `error_labels`, rep `valid = false` thì không gắn lỗi. Ghi ra file tạm rồi đổi tên (không hỏng file cũ nếu bị ngắt giữa chừng).
- Nhãn vẫn ở các file này khi đã có database (quyết định 2026-10-24, §7): bảng `reps` (§4) chỉ lưu lỗi mô hình đoán.

## 3. Interface

```python
class Exercise(ABC):
    name: str
    error_labels: list[str]                 # các lỗi hợp lệ, không gồm "good"
    error_display: dict[str, str] = {}      # mã lỗi -> tên cho người dùng ("hip_sag" -> "Hông võng")
    measure_display: dict[str, tuple[str, str]] = {}  # đặc trưng -> (tên, đơn vị) hiện ở trang
        # kết quả, vd "min_elbow_angle" -> ("Góc khuỷu ở đáy", "°"); mục tiêu lấy từ error_rules()
    def angle_definitions(self) -> dict[str, tuple[str, str, str]]: ...
        # tên góc -> (khớp A, khớp đỉnh B, khớp C), ví dụ "elbow_angle": ("shoulder", "elbow", "wrist")
        # tên khớp không có bên; FeatureExtractor chọn left_/right_ cho cả hiệp
    def tilt_definitions(self) -> dict[str, tuple[str, str]]: ...   # mặc định {}
        # tên tín hiệu -> (khớp A, khớp B): góc đoạn A→B so với phương ngang (0° nằm, 90° đứng)
        # ví dụ "body_tilt": ("shoulder", "ankle") để biết đang plank hay đang đứng
    def offset_definitions(self) -> dict[str, tuple[str, str, str]]: ...   # mặc định {}
        # tên tín hiệu -> (khớp P, khớp A, khớp B): độ lệch có dấu của P khỏi đường A–B,
        # chia cho độ dài A–B; dương = P phía trên đường (theo ảnh), âm = phía dưới
        # ví dụ "hip_offset": ("hip", "shoulder", "ankle"): dương = hông nhô, âm = hông võng
    def primary_signal(self) -> str: ...    # tín hiệu dùng để cắt rep, ví dụ "elbow_angle"
    def phase_thresholds(self) -> dict[str, float]: ...  # ngưỡng cho máy trạng thái
        # góc tính bằng độ; thời gian tính bằng giây, tên có hậu tố _s (ví dụ "min_rep_duration_s")
        # có ngưỡng "chờ sẵn sàng": chỉ bắt đầu đếm khi đã giữ tư thế đầu đủ lâu (ví dụ "ready_hold_s")
        # đếm theo biên độ ("min_amplitude_deg"), không theo ngưỡng góc cố định, để rep lỗi
        # (nông, chưa duỗi hết tay) vẫn được đếm; ranh giới rep theo độ ổn định gần đỉnh
        # ("top_tolerance_deg", "top_settle_s")
    def error_rules(self) -> dict[str, ErrorRule | None]: ...   # luật cho baseline, mỗi lỗi một luật
        # ErrorRule(feature, op, threshold): lỗi khi Rep.features[feature] <op> threshold,
        # op là "<" hoặc ">"; None = chưa có ngưỡng (RuleBased bỏ qua và báo ra)
        # ví dụ "shallow": ErrorRule("min_elbow_angle", ">", 67.0)

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

class OnlineRepCounter:                     # realtime (features/online.py), chỉ để hiển thị
    def __init__(self, exercise: Exercise, fps: float, frame_size: tuple[int, int],
                 joint_names: list[str] | None = None): ...
    def update(self, keypoints: np.ndarray) -> int: ...  # nhận 1 khung (K, 3), trả số rep hiện tại
    def finish(self) -> int: ...            # hết hiệp: chốt rep chờ, trả số rep cuối
    count: int; completed: int; phase: str; side: str   # của bên đang rõ hơn tính tới giờ

class FormClassifier(ABC):                  # multi-label: mỗi lỗi một quyết định có/không
    def fit(self, reps: list[Rep], errors: list[frozenset[str]]) -> None: ...   # RuleBased: không làm gì
    def predict(self, reps: list[Rep]) -> list[RepResult]: ...

def make_classifier(name: str, exercise: Exercise, seed: int = 0) -> FormClassifier: ...  # registry
def train_classifier(name, exercise, dataset: Dataset | None) -> tuple[FormClassifier, str]: ...
    # models/train.py: bộ phân loại cho app, học trên mọi rep đã gán nhãn; không có dữ liệu
    # hoặc fit lỗi → lùi về "rules"; trả (bộ đã fit, tên mô hình thật sự dùng)
def classify_session(pose, exercise, classifier, session_id) -> Session: ...  # pipeline.py
def summarize(session: Session, error_labels) -> dict: ...  # progress/summary.py
    # {n_reps, n_good, good_ratio (None khi 0 rep), error_counts: đủ mọi lỗi, theo thứ tự}

# progress/goals.py: mục tiêu và streak, tính lúc đọc; không đọc đồng hồ (today truyền vào)
SetRecord(recorded_at: datetime, n_reps, n_good)       # một hiệp đã chấm; ngày = recorded_at.date()
Goal(daily_reps, from_date, min_good_ratio=None)       # hiệu lực từ from_date tới mục tiêu mới hơn
DayProgress(day, n_reps, n_good, good_ratio, goal, met)
def goal_on(day, goals) -> Goal | None: ...
def daily_progress(records, goals, start, end) -> list[DayProgress]: ...  # đủ mọi ngày, kể cả ngày trống
def streak(records, goals, today) -> int: ...  # hôm nay chưa đạt thì chưa đứt, đếm từ hôm qua
    # đạt = n_reps ≥ daily_reps và (nếu có) good_ratio ≥ min_good_ratio; chưa có mục tiêu: có tập là đạt

CoachProgress(day_reps, daily_reps: int | None, streak)  # tiến độ trong ngày TỚI HẾT hiệp này
class Coach(ABC):                           # TemplateCoach, DeepSeekCoach
    def summarize(self, session: Session, progress: CoachProgress | None = None) -> str: ...
    # chỉ dùng số liệu trong session/progress; tên lỗi, số đo, mục tiêu lấy từ get_exercise().
    # Dòng "Công cụ hỗ trợ, không thay huấn luyện viên." do giao diện luôn hiện, không nằm trong chữ
```

Ghi chú:
- `RepSegmenter` và `OnlineRepCounter` dùng **chung máy trạng thái và ngưỡng** từ `Exercise`. Khác nhau ở bộ lọc: hết hiệp dùng Savitzky–Golay (nhìn cả trước lẫn sau), realtime dùng bộ lọc nhân quả (ví dụ EMA). Số đếm realtime có thể lệch, kết quả hết hiệp là chuẩn.
- `TemporalNet` (mạng chuỗi) đã chuyển sang mở rộng. Khi làm, cân nhắc thêm trường `signals` vào `Rep` hoặc truyền `FeatureSeries` kèm theo.

## 4. Backend và web (bản nháp, chốt API đầu tuần 3)

### Đã có (`backend/app.py`)
| Method | Đường dẫn | Việc |
|---|---|---|
| `GET` | `/api/exercises/{name}` | Tên bài + `error_labels` + `error_display` (tên lỗi cho người dùng). Tên lạ → 404 |
| `POST` | `/api/sessions` | Kiểm tra bằng `parse_session` (§2b) → `classify_session` bằng bộ phân loại `FORMCOACH_MODEL` (mặc định `rf`; huấn luyện lần đầu cần từ `data/`, không được thì `rules`) → ghi `sessions`/`reps` gắn `user_id` → lưu file nguyên văn vào `$FORMCOACH_DATA_DIR/sessions/{exercise}/{session_id}.json` → commit. Trả `session_id, exercise, n_frames, duration_s, fps, frames_with_person` và (cộng thêm) `model_name, reps[{index, start_frame, end_frame, errors, scores, measures{đặc trưng: số}}], summary{n_reps, n_good, good_ratio, error_counts}, measures[{error, feature, label, unit, op, threshold}]` (số đo hiện cho người dùng theo `Exercise.measure_display`, mục tiêu từ `error_rules()`). Sai định dạng → 422; trùng `session_id` → 409, không ghi đè |
| `GET` | `/api/sessions/{exercise}/{session_id}/result` | Kết quả đã lưu của chính user: như trên + `recorded_at, set_errors`. Hiệp người khác / quay trước khi có DB → 404 |
| `GET` | `/api/results` | Lịch sử của user, mới nhất trước: `exercise, session_id, recorded_at, duration_s, model_name, n_reps, n_good` |
| `GET` | `/api/sessions/{exercise}/{session_id}/result/reps/{index}/replay` | Người que của một rep để xem lại ở trang kết quả (`build_rep_replay`): 15 khớp `STICK_JOINTS`, khung từ đầu đến cuối rep thêm 0,3 s mỗi bên, `times_s` tính từ khung đầu đoạn, `rep_start_s/rep_end_s`. Rep lấy theo kết quả đã lưu của chính user; hiệp người khác / rep không có → 404. Không có video |
| `GET` | `/api/sessions/{exercise}` | Danh sách hiệp (mới nhất trước): `session_id, recorded_at, set_errors, duration_s, n_reps, labeled`. File hỏng vẫn hiện kèm `error` |
| `GET` | `/api/sessions/{exercise}/{session_id}/review` | `formcoach.review.build_review`: thời gian từng khung, tín hiệu đã lọc, khung xương rút gọn (15 khớp, NaN → `null`), rep + đặc trưng, nhãn đã lưu hoặc nhãn mặc định, `alignment_problems` nếu nhãn đã lưu không khớp rep hiện tại |
| `PUT` | `/api/sessions/{exercise}/{session_id}/labels` | Body = file nhãn §2c → kiểm tra (`from_dict`), đúng hiệp, **khớp rep hiện tại** (`check_alignment`, lệch → 409) → lưu `data/labels/...` |
| `POST` | `/api/auth/register` | `{email, password}` → tạo tài khoản và đăng nhập luôn (đặt cookie). 403 nếu chưa bật `FORMCOACH_ALLOW_REGISTER=1`; 422 email sai hình dạng hoặc mật khẩu < 8 ký tự; 409 email đã có (so không phân biệt hoa thường) |
| `POST` | `/api/auth/login` | `{email, password}` → đặt cookie. Sai email hay sai mật khẩu đều 401 cùng thông báo |
| `POST` | `/api/auth/logout` | Xoá token khỏi DB và xoá cookie; chưa đăng nhập cũng 200 |
| `GET` | `/api/auth/options` | `{allow_register}` theo `FORMCOACH_ALLOW_REGISTER`; mở, không cần đăng nhập. Web ẩn "Tạo tài khoản" khi `false` |
| `GET` | `/api/auth/me` | `{id, email}` của người đang đăng nhập; 401 nếu không |
| `GET` | `/api/goals?exercise=pushup` | Mục tiêu mới nhất của mình: `{exercise, goal: {daily_reps, min_good_ratio, from_date} \| null}`. Bài lạ → 404 |
| `PUT` | `/api/goals` | `{exercise, daily_reps (1–10000), min_good_ratio (0–1, tuỳ chọn), today: "YYYY-MM-DD"}` → mục tiêu áp dụng từ `today` (ngày theo giờ điện thoại), đặt lại cùng ngày thì ghi đè; ngày cũ giữ mục tiêu cũ. `today` lệch quá 1 ngày so với ngày UTC của server → 422 (không đặt lùi về quá khứ) |
| `GET` | `/api/progress?exercise=pushup&from=&to=` | `backend/progress.py` → `formcoach/progress/goals.py`. `to` = hôm nay theo giờ điện thoại. Trả `from, to, goal` (hiệu lực ngày `to`), `today` (ngày `to`), `streak` (tính tới `to`), `totals{n_reps, n_good, good_ratio}`, `days[{day, n_reps, n_good, good_ratio, daily_reps, met}]` đủ mọi ngày kể cả ngày trống. Tính từ mọi hiệp của mình (cả hiệp Quay dữ liệu). `from > to` hoặc > 366 ngày → 422 |
| `WS` | `/api/live` | Đếm rep trực tiếp (`backend/live.py`, `OnlineRepCounter`), không lưu gì. Client gửi `{"type":"start","exercise","fps","frame_size"}`, rồi mỗi khung `{"t_ms","kp":[[x,y,v]×33] \| null}`, cuối cùng `{"type":"stop"}`. Server gửi `{"type":"count","n_reps","phase"}` khi số rep/pha đổi, `{"type":"final","n_reps"}` rồi đóng. Tin sai → `{"type":"error","detail"}`, kết nối vẫn mở. Kiểm tra cookie phiên TRƯỚC khi accept: không hợp lệ → đóng mã 4401 (TestClient thấy 4401; uvicorn thật trả HTTP 403, trình duyệt chỉ thấy kết nối thất bại). Cần gói `websockets` (requirements) |

**Đăng nhập (`backend/auth.py`):** cookie `formcoach_session` (HttpOnly, SameSite=Lax, `Secure` mặc định, tắt bằng `FORMCOACH_COOKIE_SECURE=0` khi chạy qua http thuần như test, 30 ngày) chứa token ngẫu nhiên; DB lưu sha256 của token. Đăng nhập dọn token hết hạn của user đó. Các route ghi token `commit()` trước khi trả về (không có cookie trỏ tới token chưa lưu). Mật khẩu ≤ 1024 ký tự, email ≤ 254 (422 trước khi chạy scrypt). Mọi endpoint trừ `/api/auth/*` và `/api/exercises/*` cần đăng nhập (router `protected` trong `app.py`, dependency `current_user`), thiếu/sai/hết hạn → 401. Email lưu đúng như gõ, so sánh không phân biệt hoa thường. Mật khẩu: `backend/security.py` (scrypt).

Chạy: `uvicorn backend.app:app --port 8000` (chỉ nghe 127.0.0.1; điện thoại đi qua proxy Vite). Lần đầu tạo tài khoản: thêm `FORMCOACH_ALLOW_REGISTER=1`.

### Web (`web/src`)
- `App.tsx`: cổng đăng nhập (`GET /api/auth/options` + `/me` lúc mở; chưa đăng nhập thì chỉ có `LoginView`; API trả 401 giữa chừng → `LoginView` đè lên, màn dưới giữ nguyên), rồi các tab theo hash URL: `#dashboard` (mặc định khi không có hash; `DashboardView`: `/api/progress` 14 ngày tới hôm nay theo giờ máy, đặt mục tiêu bằng `PUT /api/goals`, gắn lại mỗi lần mở tab để tải số mới — `progress/api.ts`, `progress/format.ts`), `#capture` (Quay), `#label` (Gán nhãn), `#quick` (Gán nhanh), `#result/<bài>/<id>` (trang kết quả, `ResultView`). Điều hướng (`header.app-bar`): máy tính là thanh trên (Form Coach · Dashboard / Quay / Gán nhãn · sáng/tối · Đăng xuất); điện thoại (≤ 720px) `<nav>` thành thanh dưới cố định (nút Quay tròn ở giữa), chỉ hiện ở Dashboard và Gán nhãn, màn Quay/Kết quả thay bằng link "‹ Dashboard"; điện thoại xoay ngang ẩn cả thanh để màn Tập vừa màn hình. Gán nhanh mở bằng link trong màn Gán nhãn.
- Tab Quay có hai chế độ: **Tập** (`TrainView`, app): Chuẩn bị (máy dọc, tự chuyển khi xoay ngang) → Sẵn sàng (camera tự bật, "đã thấy toàn thân" từ `train/body.ts`) → đếm ngược 5 s → Đang ghi (số rep trực tiếp qua WebSocket `/api/live`, mở từ lúc đếm ngược; khung chỉ gửi khi đang ghi, tối đa 30 khung/s, `start` mang fps đo được; không kết nối được thì hiện đồng hồ, việc ghi không bị ảnh hưởng — `train/live.ts`) → Xong: gửi, sang trang kết quả. **Quay dữ liệu** (`CaptureView`, công cụ dataset: chọn lỗi cố ý, ghi chú). Gửi hiệp và danh sách "chưa gửi" dùng chung `session/upload.ts`.
- Gọi API: `auth/api.ts` (đăng nhập), `label/api.ts` (hiệp, review, nhãn), `CaptureView.tsx` (tải hiệp lên); lỗi HTTP đọc chung ở `http.ts`. Cookie phiên do trình duyệt tự gửi (cùng nguồn qua proxy `/api`), JavaScript không đọc/lưu token.
- Giao diện theo `DESIGN.md`; token ở `theme.css`, chế độ sáng/tối ở `theme.ts`.

### Endpoint dự kiến (tuần 3–4)
| Method | Đường dẫn | Việc |
|---|---|---|
| — | — | (`/api/goals`, `/api/progress` đã làm ở P2, xem bảng trên) |

### Bảng dữ liệu (SQLite, `backend/schema.sql`, kết nối ở `backend/db.py`)
```
users       (id, email, password_hash, created_at; UNIQUE lower(email))
auth_tokens (token_hash PK, user_id, created_at, expires_at)
sessions    (id, user_id, exercise, session_id, recorded_at, set_errors, source, model_name,
             n_frames, duration_s, created_at; UNIQUE(exercise, session_id))
reps        (id, session_pk, idx, start_frame, end_frame, features_json, predicted_errors,
             scores_json; UNIQUE(session_pk, idx))
goals       (id, user_id, exercise, daily_reps, min_good_ratio, from_date, created_at;
             UNIQUE(user_id, exercise, from_date))   -- giữ lịch sử mục tiêu
```
- File DB: `$FORMCOACH_DATA_DIR/formcoach.db`. Mỗi request một kết nối (`get_db`): commit khi route xong, rollback khi lỗi. Khoá ngoại bật, xoá user thì xoá theo token/hiệp/rep.
- **DB chỉ giữ tài khoản và kết quả app đã phân tích.** File quay (`data/sessions/**`, §2b) và file nhãn (§2c) vẫn là dữ liệu huấn luyện mà `build_dataset` đọc; không chép keypoint hay nhãn thật vào DB. `predicted_errors`/`scores_json` là thứ bộ phân loại `model_name` đoán.
- `auth_tokens` chỉ lưu sha256 của token; token thật ở cookie.
- Thời gian là chuỗi ISO 8601 UTC; danh sách/dict là chuỗi JSON.
- Tiến độ, "đã xong" và streak **tính lúc đọc** từ `sessions`/`reps`/`goals`, không lưu sẵn. Logic này là hàm thuần trong `formcoach/progress/`, test bằng dữ liệu giả.
- Không lưu video. API key DeepSeek chỉ ở server (biến môi trường).

## 5. Cấu trúc thư mục dự kiến

```
formcoach/             # lõi Python, không phụ thuộc web/DB
 ├── types.py          # dataclass ở mục 2
 ├── exercises/        # Exercise, PushUp, Squat
 ├── pose/             # joints (33 tên khớp), PoseEstimator, MediaPipeEstimator (offline), load_session_json
 ├── features/         # geometry (tính góc), smoothing, FeatureExtractor, RepSegmenter, OnlineRepCounter
 ├── models/           # FormClassifier, RuleBased, LearnedThreshold, RandomForest, registry (tạo theo tên)
 ├── coach/            # Coach, TemplateCoach, DeepSeekCoach
 ├── labels.py         # nhãn từng rep: lưu/đọc/kiểm tra file nhãn (§2c)
 ├── review.py         # dữ liệu cho màn hình gán nhãn (hàm thuần, backend chỉ gọi)
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
- **2026-10-20 — Nhãn lưu mỗi hiệp một file JSON (§2c), không dùng chung `reps.csv`.** — Mỗi lần lưu chỉ đụng một file (không sửa chung một CSV); giữ ranh giới rep + ngưỡng bộ đếm để phát hiện nhãn lệch khi rep được cắt lại. Bảng CSV để train sẽ được xuất ra từ các file này. — Đã loại: một `reps.csv` chung (ghi đè lẫn nhau, không giữ được ngưỡng lúc cắt).
- **2026-10-20 — Đánh giá bằng kiểm định chéo bỏ ra một buổi (leave-one-session-out).** — Chỉ có 5–6 buổi: một buổi test (~25 rep, mỗi lỗi ~4–5 rep) cho F1 dao động quá mạnh; kiểm định chéo cho mỗi buổi làm test một lần, báo trung bình ± dao động, vẫn chia theo buổi nên không rò rỉ. Ngưỡng luật chốt từ buổi quay thử rồi giữ cố định khi chấm; mọi thứ fit theo dữ liệu chỉ fit trên phần train của từng lần. — Đã loại: 80/20 một lần (quá ít rep test); khoá thêm một buổi ngoài kiểm định chéo (bớt dữ liệu).
- **2026-10-20 — Thêm `Exercise.offset_definitions()` (mặc định `{}`) và `geometry.signed_offset`.** PushUp: `hip_offset = (hip, shoulder, ankle)`. Tính trong toạ độ pixel, chia cho độ dài vai–cổ chân; dấu theo hướng "lên" của ảnh (không đổi khi đảo chiều đoạn hay lật ảnh trái–phải). — Góc vai–hông–cổ chân bằng nhau khi hông nhô hay võng cùng mức; buổi quay thử: góc thân hiệp `hip_sag` 158–170° trùng với tập đúng 162–171°. — Đã loại: dấu theo tích có hướng (đổi dấu khi người quay đầu sang phía kia); chênh y thô của hông (phụ thuộc khoảng cách tới camera và độ nghiêng thân).
- **2026-10-20 — Sau `/check-eval` bước 6–7:** ngày tập đổi lúc 04:00 sáng (buổi khuya không bị cắt đôi ra train/test); dataset chỉ nhận hiệp có `source.pose = "mediapipe-js"`; `evaluation.baseline` in hiệp bị bỏ qua và ghi rõ lỗi nào không tính vào macro-F1 của từng lần chia. Quy tắc gán nhãn dataset (gán bằng mắt, không chạy `analyze` trước khi gán; chốt nhãn trước lần chấm đầu tiên) ghi ở `docs/labeling-criteria.md`. — Nhãn dựa vào số đo của luật hoặc sửa sau khi xem kết quả làm điểm cao giả.
- **2026-10-24 — `LearnedThreshold` (ngưỡng học) và hook `on_fold` của `cross_validate`.** Mỗi lỗi giữ đặc trưng và chiều so sánh từ `Exercise.error_rules()`, chỉ con số ngưỡng được học: ứng viên là trung điểm giữa hai giá trị khác nhau liền kề, chọn F1 cao nhất trên train; hoà thì chọn ngưỡng báo ÍT hơn (nghiêm hơn), vẫn hoà thì ngưỡng đầu; dưới 3 rep dương (có số đo) hoặc mọi giá trị bằng nhau thì không học và lỗi không bao giờ được báo. `cross_validate(..., on_fold)` gọi sau mỗi lần chia để `compare` in ngưỡng đã học so với ngưỡng chọn tay mà không đổi cách chấm. — Tách "chỉnh ngưỡng" khỏi "học tập đặc trưng" để biết random forest hơn luật nhờ đâu. Hoà → báo ít hơn vì báo nhầm gây khó chịu hơn bỏ sót khi dùng thật (khác dự kiến ban đầu "giữa đoạn phẳng": ngưỡng trên các giá trị liền kề không tạo đoạn phẳng nên không cần). — Đã loại: tự chọn đặc trưng (đó là việc của random forest); ngưỡng riêng theo buổi.
- **2026-10-24 — scikit-learn và `RandomForest` (một rừng nhị phân mỗi lỗi).** Thêm `scikit-learn==1.9.1` (random forest đã kiểm chứng; kiểm tra thật rằng rừng nhận NaN trực tiếp). Cột đặc trưng lấy theo tập train của từng lần chia (hợp các khoá, bỏ cột không có giá trị hữu hạn); khoá lạ lúc dự đoán (vd `bottom_frame` trong app) bị bỏ; thiếu số đo = NaN. Siêu tham số cố định trước (README §8): 300 cây, `max_depth=4`, `min_samples_leaf=5`, `class_weight="balanced_subsample"`, `random_state=seed`, báo lỗi khi xác suất ≥ 0,5; ít hơn 2 rep dương (hoặc toàn dương) trong train thì không fit, lỗi không bao giờ báo, điểm 0. Import scikit-learn trễ trong registry (backend chạy luật không phải trả giá). — Các lỗi có nguyên nhân độc lập và mất cân bằng lớp riêng; khớp cách luật và `exact_match` xử lý từng lỗi. — Đã loại: `MultiOutputClassifier` (không có lợi ích, `class_weight` chung); tinh chỉnh siêu tham số theo điểm test (rò rỉ); logistic regression (tuỳ chọn, để sau nếu còn giờ).
- **2026-10-24 — Registry bộ phân loại (`formcoach/models/registry.py`) và `evaluation.compare`.** `make_classifier(name, exercise, seed)` tạo bộ phân loại MỚI theo tên (`rules`, sau này `stump`, `rf`, `lr`); `python -m evaluation.compare --models rules,stump,rf` chạy nhiều mô hình qua cùng dữ liệu và các lần chia, in báo cáo từng mô hình (dùng chung `baseline.report`) và một bảng so sánh. Siêu tham số mô hình (không phải ngưỡng lỗi, ngưỡng lỗi ở `Exercise.error_rules`) đặt ở registry một chỗ để mô hình được chấm chính là mô hình dùng trong app. `FormClassifier` giữ nguyên. — Tuần 3 so luật với random forest cần một bảng và một cách tạo mô hình thống nhất; registry tránh việc đánh giá và app tạo mô hình mỗi nơi một kiểu. — Đã loại: sửa `baseline.py` để nhận nhiều mô hình (giữ nguyên làm bản tham chiếu tái hiện 0,72).
- **2026-10-24 — SQLite bằng `sqlite3` của thư viện chuẩn; DB chỉ giữ tài khoản và kết quả.** Lược đồ ở `backend/schema.sql`, chạy mỗi lần mở kết nối (idempotent, không có migration); mọi truy vấn nằm trong `backend/`. So với bản nháp: thêm `auth_tokens`; bỏ `keypoints_json` (đã có file quay), bỏ `true_errors`/`valid` (nhãn ở file §2c, tránh hai nguồn sự thật); thêm `model_name`, `scores_json`; `goals` để tuần 4. Các file quay có sẵn không chuyển vào DB (dữ liệu huấn luyện, không có chủ). — Một người dùng, tải ghi rất nhỏ; không thêm thư viện, không cần chạy server DB, test dùng file tạm. — Đã loại: MySQL (đã cài trên máy, nhưng thêm driver, mật khẩu kết nối, server cho test và một dịch vụ khi deploy mà không được lợi gì ở tải này); Postgres (cùng lý do; là đường lui nếu nơi deploy tuần 4 không có ổ đĩa lưu lâu dài hoặc phải chạy nhiều server app); ORM/migration (che SQL, không cần ở quy mô này).
- **2026-10-24 — Trang kết quả hiện số đo từng rep; hiệp thí nghiệm điều kiện quay không bao giờ vào train.** `Exercise.measure_display` chọn số đo người tập hiểu được (góc khuỷu ở đáy và ở đỉnh), mục tiêu lấy từ `error_rules()` (không thêm ngưỡng mới); màu ô theo kết luận của bộ phân loại, mục tiêu chỉ là mốc tham khảo. Hiệp có ghi chú `ao:… goc:…` (`formcoach/conditions.py`) bị `build_dataset` bỏ dù đã gán nhãn. — Sau đo độ nhất quán: nhãn `shallow` kappa 0,53, báo "đúng/sai" cho lỗi một-số-đo kém hữu ích bằng báo số đo; hiệp thí nghiệm có đáp án theo thiết kế ("tập đúng"), gán nhãn rồi đưa vào train sẽ trộn hai loại dữ liệu. — Đã loại: thay hẳn kết luận bằng số đo (bộ phân loại vẫn hơn luật ở lỗi hông); hiện độ lệch hông (không có đơn vị dễ hiểu).
- **2026-10-24 — File hiệp ghi `capture_mode` ("dataset" | "train").** Chế độ Tập lưu hiệp như Quay dữ liệu (keypoint, không video) nhưng không có kịch bản lỗi. Ghi chế độ lúc quay vì sau này không phân biệt được: hiệp dataset "cố ý tập đúng" cũng có `set_errors` rỗng. Đánh giá mặc định bỏ hiệp Tập (bảng tuần 3 đăng ký trước giữ nguyên, `protocol_check` không bị sai nghĩa); `include_train=True` để thử sau. — Đã loại: để nguyên (mất thông tin vĩnh viễn, phân tích lỗi cố ý sai nếu gán nhãn hiệp Tập); không lưu file hiệp Tập (bỏ nguồn dữ liệu nhiều buổi, không kịch bản, đúng thứ phần hạn chế đang thiếu).
- **2026-10-24 — WebSocket `/api/live` (C2) và gói `websockets` 17.2.** Logic giao thức là lớp thuần `LiveSession` (tin vào → tin ra, test không cần mạng), endpoint chỉ đọc/ghi và kiểm tra cookie trước khi accept (`auth.user_for_token`, dùng chung với `current_user`). Chỉ gửi `count` khi số rep hoặc pha đổi. Một khung hỏng trả `error` chứ không đóng kết nối. uvicorn 0.54 chỉ kèm h11 (HTTP), không có thư viện WebSocket thì kết nối bị từ chối: thêm `websockets` (bản 17.2, 17.3 mới 5 ngày), đã thử với uvicorn thật. — Đã loại: `wsproto` (uvicorn ưu tiên `websockets`); accept rồi mới đóng 4401 (mở phiên cho người lạ chỉ để báo lỗi); gửi count mỗi khung (thừa băng thông khi số không đổi).
- **2026-10-24 — `OnlineRepCounter` (C1): cùng `RepStateMachine` và ngưỡng với bản cả hiệp, chỉ khác phần không nhìn được tương lai.** Chạy song song một máy trạng thái cho mỗi bên, hiển thị bên có visibility trung bình cao hơn tính tới khung hiện tại (bản đầu khoá bên sau ~1 s: thử trên 44 hiệp thật, sai bên ở 9 hiệp vì giây đầu còn đứng gần máy, đếm ra 0), giữ giá trị cuối qua lỗ ngắn ≤ `max_gap_s` (cả hiệp nội suy), trung vị nhân quả nửa `smoothing_window_s` (cả hiệp Savitzky–Golay hai phía). Số hiện = rep đã chốt + rep chờ, nên tăng ngay khi vừa đẩy lên. Thêm `frame_size` vào constructor (góc tính trong pixel như bản cả hiệp; khung không vuông). — Số trực tiếp chỉ để hiển thị, lệch ±1 được chấp nhận; kết quả từng rep luôn từ `analyze`. — Đã loại: viết lại bộ đếm bằng JS (hai bản logic); EMA (trễ đều, khó chọn hệ số theo fps); chọn bên theo từng khung (góc nhảy); khoá bên sau 1 s (sai bên khi giây đầu không phải tư thế tập).
- **2026-10-24 — Kết quả trong app: `classify_session` + `summarize`, lưu theo user (B4–B5).** Bộ phân loại theo `FORMCOACH_MODEL` (mặc định `rf`), dựng qua registry nên cùng siêu tham số với lúc chấm; app học trên **mọi** rep hợp lệ đã gán nhãn, kể cả hiệp quay thử (loại quay thử là để chấm điểm không rò rỉ, mô hình dùng thật nên học từ toàn bộ dữ liệu). Huấn luyện lần đầu cần rồi giữ trong bộ nhớ (nhãn mới cần khởi động lại); không có dữ liệu → lùi `rules`, `model_name` ghi mô hình thật đã chấm. Tải lên: phân loại + ghi DB → ghi file → commit. Tên lỗi tiếng Việt ở `Exercise.error_display` (một nguồn, web lấy qua `/api/exercises`). — Đã loại: huấn luyện lúc khởi động (server chậm lên dù chỉ gán nhãn); lưu mô hình ra file (tuần 4, khi deploy không có `data/`); tên lỗi viết trong web (hai nguồn).
- **2026-10-24 — Đăng nhập: mật khẩu scrypt + token mờ trong cookie HttpOnly.** `hashlib.scrypt` (n=2^14, r=8, p=1, salt 16 byte, tham số lưu trong chuỗi `scrypt$n$r$p$salt$hash`); token `secrets.token_urlsafe(32)`, DB lưu sha256; mỗi request tra `auth_tokens` một lần. Email lưu đúng như gõ, trùng và đăng nhập so không phân biệt hoa thường (chỉ mục `lower(email)`), để bàn phím điện thoại tự viết hoa không làm hỏng đăng nhập và để tuần 4 liên kết được tài khoản Google cùng email (chỉ khi Google báo `email_verified`). Đăng ký mặc định tắt. Endpoint mới mặc định cần đăng nhập (router `protected`). — Không thêm thư viện; đăng xuất có hiệu lực ngay; WebSocket tự mang cookie. — Đã loại: bcrypt (thêm thư viện, chỉ dùng 72 byte đầu); JWT (khó thu hồi trước hạn, thêm thư viện); chuyển email về chữ thường khi lưu (sửa dữ liệu người dùng gõ); phân biệt hoa thường hoàn toàn (đúng chuẩn RFC 5321 cho phần trước @ nhưng hỏng khi điện thoại tự viết hoa); chỉ chữ thường tên miền.
- **2026-10-23 — Nhãn v2 và chế độ "Gán nhanh" (tab `#quick`).** Nhãn v1 chỉ có lỗi của hiệp (quen tay một rep một lỗi) nên thiếu lỗi: 61/77 lần luật báo nhầm nằm ở hiệp của lỗi khác. Gán lại bằng màn mới: mỗi lần một rep, hai khung tĩnh (đáy, vừa lên xong), phím 1–5 bật/tắt lỗi, Enter lưu cả file nhãn của hiệp rồi sang rep kế, không hiện số đo; tiến độ nhớ trong trình duyệt. Logic thuần (`web/src/label/quick.ts`) có test bằng Node (`tests/test_web_quick_label.py`). Nhãn v1 sao lưu ra `data/v1` trước khi gán; `--data data/v1` chấm lại bản v1. — Gán tay từng rep qua màn Gán nhãn đầy đủ (phát lại, đồ thị, bảng) quá chậm với 171 rep; nhãn do Claude gán bị loại vì không xem được video, gán từ số đo là luật tự chấm chính nó, và Claude đã thấy kết quả. — Đã loại: để Claude gán nhãn; điền sẵn nhãn theo luật (neo vào luật, rò rỉ); lưu tiến độ trong file nhãn (đổi định dạng).
- **2026-10-23 — Sau lần chấm đầu tiên: `evaluation.error_analysis` và thống kê bộ đếm trong `dataset_report`.** `RepRow.set_errors` (lỗi cố ý chọn lúc quay, không phải nhãn rep) để xem luật báo nhầm / bỏ sót ở loại hiệp nào; `Dataset.sessions` đếm rep bộ đếm cắt và rep thật, chỉ tính hiệp chấm điểm. — Cần để viết phần phân tích có số liệu. Chỉ để hiểu: không chỉnh ngưỡng rồi chấm lại trên chính dữ liệu này (rò rỉ); chỉ đo được rep cắt thừa, chưa đo được rep thật bị bỏ sót (không có nhãn). — Đã loại: chỉnh ngưỡng theo kết quả; thêm cột `set_errors` vào CSV (chưa cần).
- **2026-10-21 — Đơn vị kiểm định chéo = BUỔI quay (kết quả chính); theo ngày chỉ để so. Loại hiệp quay thử bằng danh sách + mốc 2026-10-20 18:00.** `evaluation/split.py`: hiệp cách hiệp trước ≥ 1 giờ thì sang buổi mới (ngày tập đổi lúc 04:00); mỗi buổi mỗi lần chia bỏ ra một buổi. `evaluation.baseline` luôn in thêm bảng so sánh theo buổi và theo ngày. Điều kiện: mỗi buổi người quay đặt lại máy và ghi vào ghi chú buổi quay. Macro-F1 chỉ gồm lỗi có luật và không thử nghiệm (`shallow`, `incomplete_lockout`, `hip_high`, và từ 2026-10-23 `hip_sag`, chốt trước lần chấm đầu tiên); `neck_drop` (thử nghiệm) báo riêng; lỗi chính chưa có luật thì `baseline` cảnh báo. Báo cả trung bình ± độ lệch qua các lần chia và kết quả gộp. — Chỉ có 4 ngày quay (tối 20/10 bị lỡ; 21/10 quay hai buổi), nhóm theo ngày chỉ được 4 lần chia, dao động rất mạnh. Hai buổi cùng ngày khác nhau về chỗ đặt máy (đặt lại mỗi buổi), giờ (ánh sáng) và độ mỏi; góc cổ tập đúng của hai NGÀY quay thử lệch 10–20°, còn mức chênh giữa hai BUỔI cùng ngày chưa đo được, nên báo kèm kết quả theo ngày và ghi vào hạn chế: chênh nhiều thì các buổi cùng ngày rò rỉ sang nhau. Quyết định này chốt trước khi có dữ liệu, không đổi sau khi xem điểm. — Đã loại: theo ngày làm kết quả chính (bảo thủ nhưng chỉ 4 lần chia); loại quay thử chỉ theo ngày (hiệp `hip_sag` quay thử có thể cùng ngày với dataset).
- *(Bản trước, 2026-10-20: nhóm theo ngày làm kết quả chính; thay bằng quyết định ngay trên sau khi người dùng chỉ ra mỗi buổi đều đặt lại máy.)*
- **2026-10-20 — `Exercise.rule_thresholds() -> dict[str, float]` đổi thành `error_rules() -> dict[str, ErrorRule | None]`.** `ErrorRule(feature, op, threshold)`; `RuleBased(exercise)` dùng chung cho mọi bài, rep thiếu đặc trưng (NaN) thì không bắt lỗi đó. — Mỗi luật cần ba thông tin (đặc trưng nào, lớn hơn hay nhỏ hơn, ngưỡng); chỉ lưu con số thì phải viết cứng luật push-up trong `RuleBased`, trái quy tắc "ngưỡng nằm trong config của Exercise". Test kiểm tra luật khớp với `docs/labeling-criteria.md`. — Đã loại: giữ tên `rule_thresholds` chỉ đổi kiểu (tên gây hiểu nhầm); viết cứng luật trong `RuleBased`.
- **2026-10-20 — Buổi quay thử (bước 0) không đưa vào chấm điểm.** Chỉ dùng để chọn ngưỡng luật (`labeling-criteria.md`); kiểm định chéo chạy trên các buổi quay sau. — Ngưỡng được chọn để tách đúng chính các rep của buổi này; nếu nó làm tập test ở một lần chia thì kết quả lần đó đẹp giả (rò rỉ). — Đã loại: vẫn đưa vào và báo hai bộ kết quả có/không có buổi này (phức tạp, dễ quên).
- **2026-10-20 — Chốt: không lấy mẫu lại `t_ms`.** — Đo trên hiệp quay thật (điện thoại, camera trước): khoảng cách khung trung vị 82,7 ms, lệch chuẩn 14 ms (17%), p95 100 ms, lớn nhất 108 ms, không lần khựng nào > 3× trung vị; bộ đếm ra đúng 5/5 rep. Khung chậm nhưng đều, coi cách đều theo trung vị là đủ. — Đã loại: lấy mẫu lại về fps cố định (phức tạp hơn, không cải thiện gì ở mức dao động này).
- **2026-10-19 — fps của file quay = 1000 / trung vị khoảng cách `t_ms`, chưa lấy mẫu lại.** — Trung vị không bị kéo tụt khi trình duyệt khựng; giữ nguyên khung đơn giản và đủ dùng cho tới khi có số đo thật. — Đã loại (tạm): lấy mẫu lại về fps cố định ngay (quyết định ở bước 10); fps trung bình (bị khựng kéo tụt).
- **2026-10-19 — FeatureExtractor bỏ khung có khớp mờ (`min_joint_visibility` = 0,5 trong `phase_thresholds`).** Mỗi góc chỉ được tính ở khung mà mọi khớp tạo nên nó có visibility ≥ ngưỡng, còn lại = NaN (lỗ ngắn được lấp, lỗ dài làm bộ đếm về chờ); `<tên>_raw` vẫn giữ góc thô. — Hiệp quay thật trên điện thoại: lúc đi sát điện thoại bấm Xong, khớp mờ (~0,2), MediaPipe đoán bừa thân "nằm" + khuỷu gập 19° → một rep ma. — Đã loại: chặn bằng thời gian sau khi đứng dậy (không tổng quát); dựa vào độ nghiêng thân (chính nó cũng bị đoán bừa).
- **2026-10-19 — Trang quay không cho ghi khi khung camera DỌC.** — Trình duyệt xoay luồng camera theo hướng trang; khoá xoay màn hình + điện thoại nằm ngang → hình dọc, người nằm thành đứng, độ nghiêng thân lật 90° → 0 rep. — Đã loại: tự xoay keypoint 90° phía Python (không biết chắc hướng xoay).
- **2026-10-20 — Bộ đếm rep đếm theo biên độ, không theo ngưỡng góc cố định.** Xuống ≥ `min_amplitude_deg` (35°) so với đỉnh gần nhất → đang xuống; lên lại ≥ 35° so với đáy → đếm rep. `top_min` chỉ còn dùng cho trạng thái chờ sẵn sàng. Rep bị cắt khi đang đẩy lên (đã lên ≥ 35°) giờ **được đếm**. — Buổi quay thử: hiệp `incomplete_lockout` có đỉnh giữa các rep chỉ 110–135° (< 140°) nên 4 rep bị gộp thành 1 rep dài 10,6 s; rep nông lại đòi ngưỡng xuống thấp hơn, hai lỗi đòi hai ngưỡng cố định ngược nhau. Sau khi đổi: 6 hiệp quay thử ra 4 rep mỗi hiệp, 3 video ra 7/7/6. — Đã loại: hạ `top_min` (rep đúng bắt đầu bị cắt sớm, nhiễu lúc giữ plank dễ tạo rep); ngưỡng riêng theo `set_errors` của hiệp (bộ đếm phải biết trước lỗi, không dùng được khi tập thật).
- **2026-10-20 — Ranh giới rep theo độ ổn định gần đỉnh (`top_tolerance_deg` 10°, `top_settle_s` 0,5 s).** Rep kết thúc ở khung đầu tiên mà 0,5 s tới khuỷu không tăng thêm quá 10°; bắt đầu ở khung cuối cùng mà 0,5 s trước đó khuỷu chưa cao hơn nó quá 10°. Thời gian nghỉ ở đỉnh không thuộc rep nào; rep không còn nối sát nhau. — Lấy đỉnh tuyệt đối thì lúc giữ plank chờ và lúc tay duỗi thêm khi đứng dậy bị tính vào rep 1 và rep cuối (rep 1 dài 10,2 s; góc thân rep cuối tụt ~133°, dễ bị luật bắt nhầm lỗi hông). — Đã loại: "khung đầu/cuối trong 10° dưới đỉnh" (đỉnh bị tay duỗi lúc đứng dậy đẩy lên 179° thì rep vẫn bị kéo thêm ~1,5 s); cắt ở lúc cắt qua ngưỡng cố định (mất đoạn đầu rep, không hợp với đếm theo biên độ).
- **2026-10-17 — Coach dùng DeepSeek API, dự phòng bằng `TemplateCoach`.** — Nhận xét tự nhiên, chi phí thấp; chỉ gửi số liệu, không gửi hình ảnh. Cần kiểm tra docs API khi làm (chưa xác minh độ tương thích với thư viện `openai`). — Đã loại: chỉ mẫu câu; model local.
