# 🏋️ Form Coach: AI phân tích kỹ thuật tập luyện qua camera

> **Trạng thái:** đang làm tuần 1 (khung dự án xong).

> **Mục tiêu chính:** học qua vibe code. Hiểu được thứ AI viết ra quan trọng hơn tốc độ.

> **Thời gian:** 3–4 tuần, ra web app deploy được.

> **Tài liệu liên quan:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/labeling-criteria.md`](docs/labeling-criteria.md) · [`docs/journal.md`](docs/journal.md)

---

## 1. Tổng quan

Web app mở bằng trình duyệt (điện thoại hoặc máy tính). Bật camera, tập **push-up** (sau này thêm **squat**). App vẽ khung xương và đếm rep ngay lúc tập, hết hiệp thì phát hiện lỗi kỹ thuật cho từng rep. Coach AI nhận xét cả buổi. App theo dõi mục tiêu rep mỗi ngày, tỉ lệ rep đúng kỹ thuật và chuỗi ngày tập (streak).

| | |
|---|---|
| **Vấn đề** | Tự tập một mình khó biết mình sai kỹ thuật ở rep nào, và khó duy trì đều đặn. |
| **Giải pháp** | Camera → khung xương → góc khớp → từng rep → nhãn lỗi → nhận xét + mục tiêu hằng ngày. |
| **Giá trị học tập** | Quy trình ML thật (tự tạo dữ liệu → baseline → mô hình → đánh giá đúng cách) và đưa nó vào một sản phẩm web có backend. |

### Ý tưởng trong một phút

```
Trình duyệt: camera → MediaPipe JS lấy khung xương ──keypoint──► Server Python: góc khớp → cắt rep → luật / model → kết quả
```

- **MediaPipe** là model có sẵn của Google. Đưa vào một khung hình, nó trả về **toạ độ các khớp** (vai, khuỷu, hông, gối, cổ chân...). Bản JavaScript chạy ngay trong trình duyệt, nên **video không rời khỏi máy**, chỉ gửi toạ độ (vài trăm KB) lên server.
- **Góc khớp** là cách biến toạ độ thành thông tin có nghĩa. Toạ độ phụ thuộc bạn đứng gần hay xa máy, còn góc thì không. Góc tại khuỷu là góc giữa hai đoạn khuỷu→vai và khuỷu→cổ tay (tích vô hướng của hai vector).
- **Đếm rep:** vẽ góc khuỷu theo thời gian sẽ thấy đường lượn sóng, mỗi sóng là một rep.
- **Phát hiện lỗi:** nhìn từng sóng, ví dụ đáy sóng không xuống đủ sâu thì là `shallow`.

```
Góc khuỷu
170° ─╮    ╭─╮    ╭─╮    ╭─
      │    │ │    │ │    │
 80°  ╰────╯ ╰────╯ ╰────╯
        rep1   rep2   rep3
```

```python
import numpy as np

def angle(a, b, c):                      # góc tại b, giữa đoạn b→a và b→c
    ba, bc = np.array(a) - np.array(b), np.array(c) - np.array(b)
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    return np.degrees(np.arccos(cos))
```

### Model học từ nhãn như thế nào

Mỗi rep được rút gọn thành một dòng số (đặc trưng), kèm **tập lỗi** do **bạn** gán (multi-label: một rep có thể mắc nhiều lỗi, tập rỗng là `good`):

| rep | góc khuỷu nhỏ nhất | góc thân nhỏ nhất | thời gian xuống (s) | lỗi |
|---|---|---|---|---|
| 1 | 78° | 172° | 1,2 | (không, `good`) |
| 2 | 112° | 170° | 0,9 | `shallow` |
| 3 | 110° | 155° | 1,1 | `shallow`, `hip_sag` |
| ... | | | | |

Model nhìn vài trăm dòng như vậy và tự tìm ngưỡng/quy luật (kể cả phối hợp nhiều cột). Sau đó đưa cho nó các rep **chưa từng thấy**, giấu nhãn, bắt đoán, rồi so với đáp án để biết nó tốt đến đâu. Khác với luật tay (bạn tự nghĩ "góc < 90° thì đủ sâu"), model tự rút ngưỡng từ dữ liệu.

> Các con số góc trong tài liệu này chỉ là ví dụ minh hoạ, chưa được kiểm chứng. Ngưỡng thật phải đo từ dữ liệu của bạn.

### Mục tiêu học
- **ML:** xử lý chuỗi thời gian, đặc trưng, classifier cổ điển, đánh giá không rò rỉ dữ liệu, domain shift
- **CV:** pose estimation, hình học khung xương
- **OOP:** mô hình hoá domain, Strategy, State, thêm bài tập mới mà ít sửa code cũ
- **Web:** FastAPI, WebSocket, database, đăng nhập, deploy; React (vibe code, không đi sâu)
- **LLM:** diễn giải kết quả định lượng thành phản hồi (DeepSeek API)
- **Làm dự án:** giới hạn phạm vi, tự tạo và gán nhãn dữ liệu

---

## 2. Phạm vi

### ✅ Lõi
- **Trang quay dữ liệu:** camera trình duyệt + MediaPipe JS, vẽ khung xương, lưu keypoint mỗi hiệp
- **Gán nhãn** trong app: chọn nhãn cho cả hiệp, sửa từng rep
- Tính góc khớp theo thời gian, đếm rep bằng máy trạng thái (push-up)
- Baseline phát hiện lỗi bằng **luật ngưỡng góc**
- Classifier tự train (random forest), so với baseline
- Đánh giá chia theo **buổi quay**, báo precision/recall/F1 và ma trận 2×2 cho từng lỗi
- **Backend FastAPI:** nhận keypoint, trả kết quả, lưu lịch sử vào database, đăng nhập
- **Đếm rep realtime** qua WebSocket
- **Mục tiêu:** số rep mỗi ngày, tỉ lệ rep đúng kỹ thuật, streak, đồ thị tiến bộ
- **Coach LLM** (DeepSeek), dự phòng bằng mẫu câu khi API lỗi
- Deploy, dùng được trên điện thoại (PWA)

### ➕ Mở rộng (chọn khi lõi xong)
- **Squat** chạy qua cùng pipeline (ưu tiên đầu tiên)
- Mạng chuỗi thời gian (1D-CNN/LSTM) so với random forest
- Thí nghiệm domain shift: người khác quay, góc máy khác, MediaPipe Python vs JS
- Cá nhân hoá: so với "rep chuẩn của chính bạn"
- Phát hiện mệt mỏi (biên độ/tốc độ giảm theo rep)
- Đếm rep bằng giọng nói, thông báo nhắc tập
- Các hướng train sâu hơn ở mục 4.6

### ❌ Ngoài phạm vi
Tự train pose model từ đầu, nhiều hơn 3 bài tập, tư vấn y tế, app native (App Store/CH Play), nhiều người dùng ở quy mô lớn, lưu video người dùng trên server.

### Bài tập và lỗi hỗ trợ (bản đầu)
| Bài | Thứ tự | Quay | Lỗi nhận diện được |
|---|---|---|---|
| **Push-up** | Làm trước | Từ bên hông, máy đặt thấp sát sàn | `shallow` (chưa xuống đủ sâu), `incomplete_lockout` (chưa lên hết), `hip_sag` (hông võng), `hip_high` (hông nhô cao), `neck_drop` (cổ rướn/gục, thử nghiệm) |
| **Squat** | Mở rộng | Từ bên hông, toàn thân | `shallow` (chưa đủ sâu), `back_round` (lưng cong), `heel_lift` (nhấc gót) |

Nhãn là **multi-label**: mỗi rep có một tập lỗi, tập rỗng nghĩa là `good`. Rep bộ đếm cắt nhầm (lúc vào tư thế, đứng dậy) được đánh dấu "không phải rep" (`valid = false`), không phải một nhãn lỗi. Lỗi cần quay từ phía trước (gối chụm vào, khuỷu mở rộng) để sau. Định nghĩa chi tiết ở [`docs/labeling-criteria.md`](docs/labeling-criteria.md).

---

## 3. Pipeline

```
Trình duyệt ──► [1 Pose]       MediaPipe JS: các khớp mỗi khung hình
            ──► (gửi keypoint lên server: từng khung qua WebSocket, cả hiệp khi bấm "Xong")
Server      ──► [2 Features]   góc khớp, vận tốc, làm mượt tín hiệu
            ──► [3 Segment]    cắt thành từng rep bằng máy trạng thái (realtime: từng khung)
            ──► [4 Classify]   luật / random forest → nhãn từng rep
            ──► [5 Coach]      tổng hợp cả buổi, diễn giải (DeepSeek)
            ──► [6 Lưu]        database: buổi tập, rep, mục tiêu, streak
Trình duyệt ◄── kết quả, nhận xét, dashboard
```

Chi tiết interface và kiểu dữ liệu giữa các bước: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 4. Phần AI

### 4.1 Pose estimation (có sẵn)
Dùng MediaPipe, không tự train. Việc của bạn là biến toạ độ khớp thành thông tin hữu ích.
- **Trong app:** bản JavaScript chạy trong trình duyệt.
- **Thử nghiệm offline:** bản Python chạy trên video, để kiểm tra nhanh pose và phần đếm rep khi chưa có frontend. **Không** dùng để tạo dữ liệu train (xem 4.4).

### 4.2 Đếm rep
Làm mượt chuỗi góc rồi chạy máy trạng thái (push-up: thẳng tay → xuống → đáy → lên). Phần này trông dễ nhưng hay sai vì nhiễu.
- **Hết hiệp (offline):** làm mượt bằng Savitzky–Golay (nhìn cả trước và sau mỗi điểm), cho kết quả chính thức.
- **Realtime:** chỉ có dữ liệu quá khứ, nên dùng bộ lọc nhân quả (ví dụ EMA). Số đếm realtime có thể lệch kết quả hết hiệp, **lấy kết quả hết hiệp làm chuẩn**.

### 4.3 Phát hiện lỗi: hai cấp để so sánh
| Cấp | Mô hình | Vai trò |
|---|---|---|
| 1 | Luật ngưỡng góc | **Baseline**, hiểu bài toán |
| 2 | Random forest / logistic regression trên đặc trưng của rep | Quy trình ML chuẩn |

Mạng chuỗi (1D-CNN/LSTM) chuyển sang mở rộng.

### 4.3b Vì sao phải tự train (nói thẳng)
- **Có ích khi:** lỗi phụ thuộc nhiều yếu tố cùng lúc (hông võng là tổ hợp góc thân, góc hông, tốc độ), ngưỡng khác nhau theo từng người, hoặc luật nhạy với nhiễu pose.
- **Không có ích khi:** lỗi đơn giản chỉ cần một ngưỡng góc (như `shallow`), hoặc dữ liệu quá ít. Lúc đó luật thường tốt ngang hoặc hơn và dễ giải thích hơn.
- Vì vậy baseline luật luôn làm trước, để **đo xem train có thật sự hơn không**. Kết quả "model không thắng luật" vẫn là kết luận hợp lệ.
- Giá trị học tập chính: trải qua một vòng ML thật (tạo và gán nhãn dữ liệu, chia train/test đúng cách, so với baseline, đọc confusion matrix, thấy overfit).
- Thành thật: phần model tự train ở lõi **nhỏ** (ML cổ điển trên vài chục đặc trưng). Muốn sâu hơn xem mục 4.6.

### 4.4 Đánh giá (quan trọng nhất)
- **Chia train/test theo buổi quay**, không chia ngẫu nhiên theo rep. Các rep cùng buổi quá giống nhau nên chia ngẫu nhiên sẽ làm số liệu đẹp giả.
- **Dữ liệu train phải đi qua đúng đường mà app dùng thật** (camera trình duyệt → MediaPipe JS). Keypoint từ MediaPipe Python hoặc từ video quay bằng app camera có thể lệch vài độ một cách hệ thống. Model học trên một nguồn rồi dùng trên nguồn khác sẽ phán sai, trong khi số liệu đánh giá vẫn đẹp (domain shift).
- Multi-label: báo **precision/recall/F1 cho từng lỗi**, macro-F1, tỉ lệ rep đoán đúng toàn bộ tập lỗi, ma trận 2×2 cho từng lỗi.
- Mỗi lỗi cần đủ rep mắc lỗi đó, rải qua nhiều buổi: mỗi buổi quay ít nhất một hiệp cho từng lỗi.
- Tập test nhỏ nên số liệu dao động. Báo kèm sai số, không kết luận khi chênh lệch nhỏ.
- So sánh: luật vs random forest.

### 4.5 Coach (lớp mỏng)
Đầu vào là **dữ liệu định lượng thật** (số rep, góc đáy từng rep, lỗi theo rep, tiến độ so với mục tiêu), không phải ảnh hay video:

```
Buổi push-up, 12 rep. Rep 1-6: tốt. Rep 7: hông võng (góc thân 155°).
Rep 9-12: chưa đủ sâu (góc khuỷu 110°). Hôm nay 36/50 rep, streak 4 ngày.
```

Cần ràng buộc để không bịa chi tiết ngoài dữ liệu, và ghi rõ đây là công cụ hỗ trợ, không thay huấn luyện viên.

| Cách | Ghi chú |
|---|---|
| **DeepSeek API** | Cách chính. API key chỉ nằm ở server, đọc từ biến môi trường, không bao giờ đưa vào frontend |
| **Mẫu câu (template)** | Dự phòng khi API lỗi hoặc hết hạn mức. Không AI, chắc chắn đúng |

Tất cả nằm sau interface `Coach`, nên đổi qua lại không sửa phần khác.

### 4.6 Nâng cấp phần train (tuỳ chọn, nếu muốn học DL sâu hơn)
- **Fine-tune pose model** (ví dụ YOLO-pose) trên vài trăm khung hình push-up tự gán nhãn khớp, khi MediaPipe sai ở tư thế nằm ngang.
- **Mạng chuỗi viết từ đầu** (PyTorch) kèm augmentation (co giãn thời gian, nhiễu, lật trái-phải), tự đo overfit.
- **Học cách cắt rep** bằng model thay vì máy trạng thái, so với baseline luật.
- Mỗi mục tốn thêm khoảng 1 tuần và có thể cần GPU (Colab/Kaggle, cần kiểm tra giới hạn hiện tại).

---

## 5. Phần web

### Màn hình
| Màn hình | Nội dung | Tuần |
|---|---|---|
| Quay | Camera + khung xương, chọn bài và nhãn của hiệp, Bắt đầu/Xong | 1 |
| Gán nhãn | Xem lại hình người que + đồ thị góc, sửa nhãn từng rep | 2 |
| Đăng nhập | Tài khoản, bảo vệ dữ liệu cá nhân | 3 |
| Đếm realtime | Số rep hiện trên màn hình quay khi đang tập | 3 |
| Kết quả buổi tập | Số rep, nhãn từng rep, nhận xét của coach | 3–4 |
| Dashboard | Mục tiêu hôm nay, tỉ lệ rep đúng, streak, đồ thị tiến bộ | 4 |

### Nguyên tắc
- **Frontend không chứa logic ML.** React chỉ chạy MediaPipe JS và hiển thị. Đếm rep, phân loại, tính streak nằm ở Python, nơi có test.
- **Chốt API trước khi viết frontend.** Endpoint và định dạng JSON ghi trong ARCHITECTURE.
- **Mục tiêu và streak tính lúc đọc**, không lưu cờ "đã xong": đổi mục tiêu thì kết quả tự đúng.
- **Camera trên điện thoại cần HTTPS** (trình duyệt chặn camera trên trang `http` không phải `localhost`). Lúc phát triển dùng HTTPS tự ký hoặc tunnel, không cần deploy sớm.

---

## 6. Kế hoạch dữ liệu

Dữ liệu hoàn toàn tự tạo, **quay bằng trang quay của chính app**.

### Cách quay
- Một góc cố định từ bên hông, điện thoại trên giá hoặc dựa vật cố định, đặt thấp sát sàn
- Toàn thân trong khung, ánh sáng đủ, quần áo ôm
- Nền gọn, không có người khác trong khung
- Mỗi hiệp chứa nhiều rep cùng một kiểu (đúng, hoặc **cố ý làm sai một lỗi**); chọn nhãn của hiệp trước khi bấm Bắt đầu

### Khối lượng ước tính
| Mức | Rep | Dùng cho |
|---|---|---|
| Tối thiểu | 100–150 | Baseline luật và đếm rep |
| Mặc định | 200–300, nhiều buổi khác nhau | Random forest, đánh giá theo buổi |

Quay nhiều buổi (khác ngày, khác giờ) tốt hơn quay một buổi dài, vì cần chia train/test theo buổi. Bắt đầu quay từ tuần 2, không dồn được.

### Cấu trúc dữ liệu
```
data/
 ├── videos/             # video thử offline (MediaPipe Python), không dùng để train
 ├── keypoints/          # cache keypoint của video thử
 ├── sessions/
 │    └── {exercise}/{session_id}.json   # keypoint từ trang quay + nhãn của hiệp
 └── labels/
      └── reps.csv       # session_id, rep_idx, start_frame, end_frame, valid, errors (vd "shallow;hip_sag"), note
```
`data/` không đưa lên git. Video có mặt và không gian riêng tư, không chia sẻ công khai, không lưu trên server.

---

## 7. Thiết kế OOP (tóm tắt)

```
Exercise (abstract)               ← PushUp, Squat
PoseEstimator (abstract)          ← MediaPipeEstimator (offline, Python)
load_session_json                 – đọc keypoint từ trang quay
FeatureExtractor                  – góc, vận tốc
RepSegmenter                      – máy trạng thái cắt rep cả hiệp (State)
OnlineRepCounter                  – cùng máy trạng thái, nhận từng khung (realtime)
FormClassifier (abstract)         ← RuleBased, RandomForest
Rep / Session                     – dữ liệu một rep, một buổi tập
Coach (abstract)                  ← TemplateCoach, DeepSeekCoach
Pipeline                          – ghép các bước
backend/                          – FastAPI: API, WebSocket, database, đăng nhập
web/                              – React: các màn hình ở mục 5
```

Thêm bài tập mới chỉ cần thêm một lớp `Exercise`. Đổi mô hình chỉ cần đổi `FormClassifier`. Chi tiết ở [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 8. Lộ trình 3–4 tuần

| Tuần | Python / ML | Web | Kết quả |
|---|---|---|---|
| **1** | Pose offline, tính góc, đồ thị, đếm rep push-up | Trang quay (camera + MediaPipe JS → JSON) | Đếm rep đúng; quay được dữ liệu bằng app |
| **2** | Đọc JSON từ trang quay, baseline luật | Gán nhãn trong app; **quay dataset nhiều buổi** | Baseline + dataset có nhãn |
| **3** | Random forest, đánh giá theo buổi, đếm rep online | FastAPI + DB + đăng nhập, WebSocket realtime, trang kết quả | Bảng so sánh luật vs RF; app chạy local đủ luồng |
| **4** | Coach DeepSeek + mẫu câu | Dashboard mục tiêu/streak/đồ thị, PWA, **deploy** | Sản phẩm demo được |

### Checklist
- [ ] **Ngày 1:** MediaPipe chạy trên một clip push-up, xem pose có ổn không (rủi ro cao nhất)
- [ ] Tuần 1: đồ thị góc khuỷu theo thời gian, thấy được các "sóng" của rep
- [ ] Tuần 1: đếm rep đúng trên 5 clip thử
- [ ] Tuần 1: trang quay chạy trên điện thoại (HTTPS), xuất được JSON keypoint
- [ ] Tuần 2: viết tiêu chí nhãn trước khi quay
- [ ] Tuần 2: quay nhiều buổi khác nhau (không chỉ một buổi dài)
- [ ] Tuần 2: gán nhãn trong app + `reps.csv`
- [ ] Tuần 3: chia train/test theo buổi, không theo rep
- [ ] Tuần 3: bảng precision/recall/F1 và ma trận 2×2 cho từng lỗi, so với baseline luật
- [ ] Tuần 3: app chạy local đủ luồng: đăng nhập → quay → kết quả
- [ ] Tuần 4: coach, mục tiêu, streak, đồ thị, deploy, README, demo

---

## 9. Độ khó và kiến thức cần có

**Độ khó tổng thể: vừa–khó (3,5/5).** Dễ bắt đầu, khó dần ở giai đoạn ML và khi ghép thành sản phẩm.

| Thành phần | Độ khó |
|---|---|
| Chạy pose, vẽ khung xương | ⭐ |
| Tính góc khớp | ⭐⭐ |
| Đếm rep (nhiễu, ngưỡng, đếm đôi) | ⭐⭐⭐ |
| Đếm rep realtime (lọc nhân quả, WebSocket) | ⭐⭐⭐ |
| Classifier cổ điển | ⭐⭐ |
| Đánh giá đúng cách (không rò rỉ) | ⭐⭐⭐ |
| Backend: API, database, đăng nhập | ⭐⭐ |
| Deploy (HTTPS, biến môi trường, database) | ⭐⭐⭐ |

**Kiến thức bắt buộc:** Python/OOP, NumPy, vector và góc, scikit-learn cơ bản, khái niệm F1/confusion matrix/rò rỉ dữ liệu, HTTP/JSON cơ bản.
**Nên học trong lúc làm:** xử lý tín hiệu cơ bản (làm mượt, `scipy.signal`), máy trạng thái, FastAPI, SQL cơ bản, WebSocket, cross-validation.
**Không cần:** tự train pose model, DL thị giác nâng cao, React chuyên sâu.

---

## 10. Vấn đề dự kiến

| Vấn đề | Mức | Cách xử lý |
|---|---|---|
| Push-up khó với pose (nằm ngang sát sàn, một tay bị che) | Cao | Thử ngày 1, đặt máy thấp; nếu kém thì đổi sang squat trước |
| Pose bị nhiễu, khớp bị che | Cao | Cố định góc quay, quần áo ôm, ánh sáng tốt |
| Rò rỉ dữ liệu khi đánh giá | Cao | Chia theo buổi quay ngay từ đầu |
| Keypoint train và keypoint dùng thật khác nguồn | Cao | Chỉ quay dataset bằng trang quay của app |
| Phình phạm vi (ML + web trong 3–4 tuần) | Cao | Nếu trễ, bỏ theo thứ tự: đếm realtime → đồ thị → streak. Không bỏ phần đánh giá |
| Camera bị chặn trên điện thoại | Vừa | HTTPS tự ký hoặc tunnel khi phát triển |
| Lộ API key / dữ liệu cá nhân | Vừa | Key chỉ ở server, đăng nhập bắt buộc khi deploy, không lưu video |
| Nhãn chủ quan | Vừa | Tiêu chí bằng góc, viết trước khi quay |
| Gán nhãn tốn thời gian | Vừa | Gán nhãn theo hiệp, chỉ sửa rep sai |
| Hiểu nhầm thành tư vấn y tế | Thấp | Ghi rõ: công cụ hỗ trợ, không thay HLV |
| Vibe code mà không hiểu code | Vừa | Xem mục 11 |

---

## 11. Cách vibe code để thực sự học

- **Tự phác sơ đồ class trước**, rồi nhờ AI code từng phần. Quyết định kiến trúc là việc của bạn.
- **Mỗi đoạn AI sinh ra, tự giải thích lại bằng lời.** Không giải thích được thì hỏi lại hoặc viết lại (skill `/explain`). Áp dụng chặt cho phần Python; frontend chỉ cần hiểu định dạng dữ liệu gửi/nhận.
- **Viết test cho phần đếm rep và tính góc** (tín hiệu tổng hợp có đáp án biết trước). Đây là chỗ AI hay sai âm thầm.
- **Tự vẽ đồ thị** góc khớp và vị trí đếm rep để kiểm tra bằng mắt, đừng chỉ tin vào số.
- **Ghi lại mỗi lần vấp** vào [`docs/journal.md`](docs/journal.md) (skill `/journal`).
- **Hiểu kỹ phần đánh giá** (chia dữ liệu, tính metric): nhờ giải thích trước khi viết, rồi soát bằng skill `/check-eval`.

---

## 12. Điều kiện hoàn thành (Definition of Done)

- [ ] Push-up qua camera trình duyệt → khung xương, số rep đúng (realtime và hết hiệp)
- [ ] Dataset tự quay bằng app, có nhãn, chia theo buổi
- [ ] Baseline luật, random forest, có số liệu so sánh (F1 từng lỗi, ma trận 2×2) kèm hạn chế
- [ ] Kiến trúc OOP: thêm bài tập mới không phải sửa pipeline
- [ ] Có test cho đếm rep, tính góc, tính mục tiêu/streak
- [ ] Web app deploy: đăng nhập, quay, kết quả, coach DeepSeek, mục tiêu, streak, đồ thị
- [ ] README có hướng dẫn chạy, ảnh/video demo, kết quả, phần hạn chế
- [ ] (Mở rộng) squat
- [ ] (Mở rộng) thí nghiệm domain shift

---

## 13. Dự án này dạy gì và không dạy gì

**Dạy:** quy trình ML từ dữ liệu tự tạo đến đánh giá, xử lý tín hiệu, hình học khung xương, OOP có lý do, đưa model vào sản phẩm web (API, realtime, database, deploy), tư duy nghi ngờ số liệu của chính mình.

**Không dạy sâu:** kiến trúc bên trong pose model, DL thị giác, React/frontend, hạ tầng quy mô lớn. LLM chỉ là lớp mỏng.

---

## 14. Việc cần làm tiếp

- [x] Khung dự án (bước 0)
- [ ] Chọn chỗ đặt điện thoại để quay push-up từ bên hông, sát sàn
- [ ] Quay thử 1 clip push-up, chạy MediaPipe để xem pose có ổn không
- [ ] Điền tiêu chí nhãn cho push-up trong `docs/labeling-criteria.md`
- [x] Lập lại plan tuần 1 cho push-up + trang quay (plan mode)
