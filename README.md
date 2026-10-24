# 🏋️ Form Coach: AI phân tích kỹ thuật tập luyện qua camera

> **Trạng thái:** xong tuần 1 (đếm rep push-up + trang quay trên điện thoại) và tuần 2 (dataset 5 buổi có nhãn + baseline luật chấm bằng kiểm định chéo theo buổi, macro-F1 0,72); sắp sang tuần 3 (random forest, luồng app).

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
- **Backend FastAPI:** nhận keypoint, trả kết quả, lưu lịch sử vào database, đăng nhập (email + mật khẩu ở tuần 3, thêm Google ở tuần 4)
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

### 4.4b Kết quả baseline luật và hạn chế (tuần 2)

**Dữ liệu và cách chấm.** 167 rep hợp lệ từ 30 hiệp, 5 buổi (một người, cởi trần, quay ngang hông bằng trang quay của app). Mỗi buổi 6 hiệp: tập đúng và mỗi lỗi một hiệp cố ý. Hiệp quay thử (nơi chọn ngưỡng) bị loại khỏi phần chấm điểm. Chia theo buổi: 5 lần chia, mỗi lần bỏ ra một buổi làm test. Mỗi lỗi một luật, ngưỡng chọn từ buổi quay thử rồi giữ cố định: `shallow` khuỷu nhỏ nhất > 67°; `incomplete_lockout` đỉnh khuỷu sau rep < 146°; `hip_high` độ lệch hông nhỏ nhất trong rep > 0,01 (hông trên đường vai–cổ chân suốt rep); `hip_sag` độ lệch hông lớn nhất < −0,01; `neck_drop` (thử nghiệm) trung vị góc tai–vai–hông < 128°.

**Kết quả** (số gộp qua 5 lần chia, nhãn v3):

| Lỗi | Precision | Recall | F1 | Báo đúng / báo nhầm / bỏ sót |
|---|---|---|---|---|
| `shallow` | 0,41 | 0,79 | 0,54 | 19 / 27 / 5 |
| `incomplete_lockout` | 0,83 | 0,70 | 0,76 | 35 / 7 / 15 |
| `hip_high` | 1,00 | 0,96 | 0,98 | 26 / 0 / 1 |
| `hip_sag` | 0,42 | 0,93 | 0,58 | 26 / 36 / 2 |
| *`neck_drop` (thử nghiệm, không tính macro-F1)* | 0,85 | 0,81 | 0,83 | 29 / 5 / 7 |

Macro-F1 (4 lỗi chính) **0,72**; tỉ lệ rep đoán đúng toàn bộ tập lỗi **0,55**. Nhãn được gán lại hai lần (v1 một lỗi mỗi rep, v2 gán nhanh, v3 sửa kỹ) cho macro-F1 gộp 0,73 / 0,72 / 0,72: con số tổng bền theo cách gán nhãn, còn precision và recall từng lỗi dịch chuyển. Chia theo ngày cho cùng macro-F1 (0,72) nhưng chỉ có 2 ngày nên bằng chứng yếu. Bộ đếm cắt 172 rep ở các hiệp chấm điểm, trong đó 5 rep (2,9%) bị đánh dấu "không phải rep" theo nhãn v3 (1 rep theo nhãn v1); rep thật bị bỏ sót chưa đo được.

**Phân tích.**
- Trên buổi quay thử luật khớp 29/29 rep, nhưng con số đó không có ý nghĩa vì ngưỡng được chọn từ chính nó; điểm trên dữ liệu chấm điểm mới là điểm thật.
- Lỗi rõ thì luật gần như hoàn hảo (`hip_high`: F1 0,98, không báo nhầm). Lỗi nhẹ thì luật bắt được phần lớn lỗi thật ở `shallow` và `hip_sag` (recall 0,79 và 0,93) nhưng báo nhầm nhiều (precision ~0,4).
- Ngưỡng chọn từ buổi quay thử nghiêm hơn ranh giới của mắt người gán nhãn. Ở `incomplete_lockout` và `neck_drop`, nhãn gán lại nằm sát ngoài ngưỡng (đỉnh khuỷu 147–159° so với ngưỡng 146°; góc cổ 130–140° so với 128°), nên nhãn kỹ hơn làm precision tăng (0,67 → 0,83) và recall giảm (0,94 → 0,70) trong khi F1 gần như không đổi. Ngưỡng học từ chính nhãn có thể sửa lệch này.
- `shallow`: rep bị báo nhầm có góc khuỷu nhỏ nhất 68–94°, gần như trùng rep có nhãn `shallow` (trung vị 73° và 75°): góc khuỷu nhỏ nhất không đủ để tách "nông" theo nhãn. 23/27 lần báo nhầm nằm ở hiệp của lỗi khác (`neck_drop`, `hip_high`, `hip_sag`), nhưng gán lại nhãn nhiều lỗi không làm số báo nhầm giảm (26 → 27 từ v1 sang v3), nên nguyên nhân chưa rõ.
- `hip_sag`: 13/36 lần báo nhầm nằm trong hiệp tập đúng, nơi hông của rep đúng có lúc thấp nhẹ (1–4 cm) trong cả rep; báo nhầm dồn ở buổi 21/10 lần 1 (15/36), gợi ý mức nền của độ lệch hông khác nhau giữa các buổi (đặt máy, độ mỏi).
- `neck_drop` (thử nghiệm) đo được khá (F1 0,83) nhưng khoảng cách giữa rep có và không có lỗi chỉ vài độ.

**Hạn chế.**
- **Một người, một điều kiện:** một người tập, cởi trần, quay ngang hông, một chỗ trong nhà. Kết quả không nói gì về người khác, góc máy khác hay quần áo khác.
- **Dữ liệu nhỏ:** 167 rep; mỗi lỗi chỉ có 24–50 rep có nhãn. Khoảng tin cậy 95% của một tỉ lệ như recall 0,79 (19/24) rộng khoảng ±0,16, nên chênh lệch dưới ~0,15 giữa hai lỗi hoặc hai mô hình chưa có ý nghĩa. Chỉ có 5 lần chia.
- **5 buổi nhưng chỉ 2 ngày** (21/10 hai buổi, 23/10 ba buổi). Các buổi cùng ngày có thể không độc lập hoàn toàn dù mỗi buổi đặt lại máy; so sánh theo ngày chỉ có 2 lần chia.
- **Nhãn nhiễu ở lỗi nhẹ:** một người gán bằng mắt; khuỷu 65° so với 75°, hông thấp 2 cm so với 4 cm vượt khả năng phân biệt của mắt. Độ nhất quán của người gán chưa được đo. Nhãn v2 gán bằng hai ảnh tĩnh (đáy, đỉnh) nên không đánh giá được lỗi "suốt rep"; ảnh "đỉnh" là khung cuối rep còn số đo lấy giá trị lớn nhất trong 0,5 s sau đó. Nhãn v2 và v3 được sửa sau khi đã xem kết quả v1 (vì vậy báo cả ba bản). Điểm của mọi mô hình không thể vượt độ nhất quán của chính nhãn.
- **Ngưỡng và rò rỉ nhẹ:** ngưỡng chọn từ buổi quay thử (loại khỏi chấm điểm) rồi giữ cố định. Riêng `hip_sag`, hiệp quay thử được quay cùng ngày với buổi dataset đầu tiên.
- **Rep bị bỏ sót chưa đo được:** chỉ đo được rep bộ đếm cắt thừa.
- **`neck_drop` còn là thử nghiệm:** vị trí tai khi quay ngang kém ổn định; không tính vào macro-F1.
- **Nhịp khung không đều:** các hiệp đã kiểm tra có 12–19 khung/giây, lệch chuẩn khoảng cách khung 9–27%; chưa lấy mẫu lại.
- **Chưa so với random forest:** đây mới là baseline; phần so sánh luật với random forest nằm ở §8 (tuần 3).

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
| Đăng nhập | Tài khoản, bảo vệ dữ liệu cá nhân; email + mật khẩu (3), Google (4) | 3–4 |
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
 │    └── {exercise}/{session_id}.json   # keypoint từ trang quay + tập lỗi cố ý của hiệp
 └── labels/
      └── {exercise}/{session_id}.json   # nhãn từng rep: ranh giới, valid, tập lỗi, ghi chú
```
Bảng dữ liệu để train (mỗi dòng một rep: đặc trưng + nhãn) được xuất ra từ các file trên, không sửa tay.
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
| **4** | Coach DeepSeek + mẫu câu | Dashboard mục tiêu/streak/đồ thị, PWA, đăng nhập Google, **deploy** | Sản phẩm demo được |

### Đăng ký trước: so sánh luật với random forest (tuần 3)

Ghi ngày 2026-10-24, **trước khi chạy random forest lần đầu**, để kết quả không bị chọn theo điểm.
- **Dữ liệu và cách chấm:** nhãn v3 (167 rep, 5 buổi), kiểm định chéo bỏ ra một buổi (`evaluation.compare`). Macro-F1 và exact match tính trên bốn lỗi chính (`shallow`, `incomplete_lockout`, `hip_high`, `hip_sag`); `neck_drop` (thử nghiệm) báo riêng. Không sửa nhãn và không đổi danh sách lỗi chính.
- **Ba mô hình:** luật tay (ngưỡng cố định, tuần 2); ngưỡng học (mỗi lỗi giữ đặc trưng và chiều so sánh của luật, ngưỡng chọn để F1 cao nhất trên tập train của từng lần chia); random forest (một rừng nhị phân mỗi lỗi).
- **Siêu tham số random forest, cố định, không chỉnh theo điểm:** `n_estimators=300`, `max_depth=4`, `min_samples_leaf=5`, `class_weight="balanced_subsample"`, `random_state=0`, báo lỗi khi xác suất ≥ 0,5. Không tinh chỉnh lồng nhau (4 buổi trong ~130 rep quá nhiễu); ghi vào hạn chế.
- **Quy tắc kết luận:** random forest chỉ được coi là tốt hơn luật khi khoảng tin cậy 95% ghép cặp của hiệu macro-F1 (random forest trừ luật) **không chứa 0**; ngược lại kết luận là "chưa có bằng chứng random forest tốt hơn luật" (cũng là một kết luận hợp lệ).

### Kết quả so sánh luật với random forest và hạn chế (tuần 3)

**Cách chấm.** Như phần đăng ký trước: nhãn v3, 167 rep, kiểm định chéo bỏ ra một buổi (5 lần chia), macro-F1 và exact match trên bốn lỗi chính, `neck_drop` báo riêng. Cả ba mô hình chạy trên đúng cùng các rep và các lần chia, mô hình được tạo mới ở mỗi lần chia và chỉ học trên tập train của lần đó. Siêu tham số random forest giữ nguyên như đã đăng ký (không chỉnh sau khi xem điểm).

**Kết quả chính** (số gộp qua 5 lần chia theo buổi):

| Lỗi | F1 luật | F1 ngưỡng học | F1 random forest | RF: precision / recall | RF: báo đúng / báo nhầm / bỏ sót |
|---|---|---|---|---|---|
| `shallow` | 0,54 | 0,53 | **0,75** | 0,94 / 0,62 | 15 / 1 / 9 |
| `incomplete_lockout` | 0,76 | 0,77 | 0,69 | 0,71 / 0,68 | 34 / 14 / 16 |
| `hip_high` | 0,98 | 0,98 | 0,98 | 1,00 / 0,96 | 26 / 0 / 1 |
| `hip_sag` | 0,58 | 0,67 | **0,92** | 0,87 / 0,96 | 27 / 4 / 1 |
| *`neck_drop` (thử nghiệm)* | 0,83 | 0,81 | 0,71 | 0,70 / 0,72 | 26 / 11 / 10 |
| **Macro-F1 gộp** | **0,72** | **0,74** | **0,84** | | |
| Macro-F1 theo lần chia | 0,72 ± 0,07 | 0,73 ± 0,06 | 0,82 ± 0,06 | | |
| **Exact match** | **0,55** | **0,63** | **0,74** | | |

**Theo quy tắc đã đăng ký:** khoảng tin cậy 95% ghép cặp (bootstrap 1000 lần, lấy mẫu lại rep, cùng mẫu cho mọi mô hình) của hiệu macro-F1 random forest − luật là **+0,12 [+0,07, +0,17]**, không chứa 0, nên random forest được coi là tốt hơn luật. Với ngưỡng học − luật là **+0,02 [−0,01, +0,06]**, chứa 0: chưa có bằng chứng ngưỡng học tốt hơn ngưỡng chọn tay. Hiệu macro-F1 theo từng lần chia (random forest − luật) là +0,12, +0,03, +0,07, +0,20, +0,09: cả 5 lần đều dương. Chạy random forest với 5 seed cho macro-F1 gộp 0,83–0,85 (0,84 ± 0,01): kết quả không phụ thuộc may rủi của seed.

**Kiểm tra bảo thủ: nhóm theo ngày** (2 lần chia: 21/10 và 23/10; train chỉ còn 68 hoặc 99 rep). Macro-F1 gộp: luật 0,72, ngưỡng học 0,74, random forest **0,78**; hiệu random forest − luật **+0,07 [+0,02, +0,11]**, cả 2 lần chia random forest cao hơn (0,83 và 0,77 so với 0,72 và 0,72). Theo từng lỗi: `hip_sag` 0,58 / 0,75 / **0,90**; `shallow` 0,54 / 0,49 / **0,55**; `incomplete_lockout` 0,76 / 0,73 / 0,68; `hip_high` 0,98 / 0,98 / 1,00.

**Ngưỡng học.** Ổn định qua các lần chia: `shallow` ≈ 66,9° (một lần 70,6°; tay 67°), `incomplete_lockout` 148–150° (tay 146°), `hip_sag` −0,020 đến −0,031 (tay −0,01), `neck_drop` 123–128° (tay 128°). `hip_high` học ra ngưỡng âm (−0,019 đến −0,004; tay +0,01) vì rep `hip_high` và rep võng tách nhau rất xa trên số đo này; điểm vẫn 0,98.

**Thăm dò sau khi đã thấy kết quả** (không phải kiểm định đăng ký trước; `evaluation.compare` và `evaluation.protocol_check`):
- *Độ quan trọng đặc trưng của random forest (trung bình qua 5 lần chia, chỉ để mô tả).* `incomplete_lockout`: `top_elbow_angle` 0,30; `hip_sag` và `hip_high`: `min_hip_offset` 0,27–0,28 và `median_hip_offset` 0,22; `neck_drop`: `median_neck_angle` 0,24; `shallow`: `min_body_tilt` 0,22 xếp trên `min_elbow_angle` 0,16. Không có đặc trưng về thời lượng hay nhịp nào lọt top 5.
- *Rừng đọc số đo hay theo kịch bản quay?* Mỗi hiệp quay với một lỗi cố ý, nên nhãn rep phần lớn trùng lỗi cố ý của hiệp (122/167 rep). Bộ đoán "luôn báo lỗi cố ý của hiệp" (biết trước kịch bản) đạt exact match 0,73, gần bằng random forest (0,74), nên exact match cao tự nó không chứng minh mô hình giỏi hơn kịch bản. Chỗ phân biệt là 45 rep có nhãn **khác** lỗi cố ý của hiệp (rep tốt lẫn trong hiệp lỗi, hoặc lỗi phụ). Ở đó, số rep đoán đúng nhãn thật / đoán đúng lỗi cố ý / khác cả hai: luật 17 / 4 / 24; ngưỡng học 23 / 6 / 16; random forest **26 / 16 / 3**. Ở 122 rep còn lại (nhãn trùng lỗi cố ý), exact match: luật 0,61; ngưỡng học 0,68; random forest 0,80.

**Phân tích.**
- Random forest tốt hơn luật về macro-F1, và hướng đó nhất quán qua cả 5 lần chia theo buổi lẫn 2 lần chia theo ngày. Mức hơn không do may rủi của seed.
- **Mức hơn không đồng đều giữa các lỗi.** Phần chắc nhất nằm ở `hip_sag` (0,58 → 0,90–0,92 ở cả hai cách chia). Với `shallow`, mức hơn (0,54 → 0,75, báo nhầm 27 → 1) chỉ có khi chia theo buổi; chia theo ngày điểm về bằng luật (0,55). Với `incomplete_lockout` và `neck_drop` random forest không tốt hơn luật (0,69 so với 0,76; 0,71 so với 0,83). Mình chưa tính khoảng tin cậy riêng cho từng lỗi, nên chưa biết các chênh lệch từng lỗi này có vượt nhiễu hay không.
- **Ngưỡng học chỉ thêm khoảng 0,02 macro-F1 (chưa có bằng chứng khác luật)**, nên phần lớn mức hơn của random forest không đến từ việc chọn ngưỡng tốt hơn cho cùng một số đo. Ngoại lệ có thể là `hip_sag`: ngưỡng học (−0,02 đến −0,03) chặt hơn ngưỡng tay (−0,01) và F1 tăng 0,58 → 0,67 (theo buổi) / 0,75 (theo ngày), vì luật tay báo nhầm 36 lần; ngưỡng tay ở `hip_sag` có vẻ quá nhạy. Random forest còn cao hơn nữa, nhiều khả năng vì dùng thêm `median_hip_offset` (ổn định hơn số đo cực trị). Đây là giả thuyết chưa kiểm chứng.
- **Random forest đánh đổi theo hướng "báo ít nhưng chắc".** Ở `shallow`, báo nhầm giảm 27 → 1 nhưng bỏ sót tăng 5 → 9 (recall 0,79 → 0,62).
- **Chưa có bằng chứng random forest chỉ học "kiểu hiệp" thay vì số đo.** Ở ba lỗi (`hip_sag`, `incomplete_lockout`, `neck_drop`) rừng dựa chủ yếu vào đúng số đo mô tả lỗi, và ở nhóm rep có nhãn khác lỗi cố ý nó vẫn đoán đúng nhãn thật nhiều hơn luật (26 so với 17 trên 45 rep). Tuy vậy random forest nghiêng về kịch bản nhiều hơn luật (16 so với 4 rep đoán đúng lỗi cố ý nhưng sai nhãn thật); không phân biệt được là nó nhận ra kiểu hiệp, hay học rằng "rep sát ngưỡng trong hiệp lỗi thường được gán là có lỗi". Riêng `shallow`, độ nghiêng thân (phụ thuộc góc đặt máy) quan trọng ngang góc khuỷu, và mức hơn biến mất khi chia theo ngày: nên đọc kết quả `shallow` của random forest thận trọng.

**Hạn chế (thêm vào các hạn chế của tuần 2).**
- **Khoảng tin cậy lạc quan.** Bootstrap lấy mẫu lại 167 rep như thể độc lập, trong khi rep cùng buổi giống nhau hơn rep khác buổi và chỉ có một người quay, một người gán nhãn. Con số "cao hơn" nên tin hơn độ rộng của khoảng. Bằng chứng theo lần chia chỉ có 5 điểm (hai cặp cùng ngày); kiểm định dấu hai phía với 5/5 lần cùng chiều cũng chỉ cho p ≈ 0,06.
- **Chưa tách được "rò rỉ theo ngày" khỏi "ít dữ liệu".** Khi chia theo ngày, train còn 68–99 rep (so với ~135 khi chia theo buổi), nên điểm theo ngày thấp hơn có thể do rò rỉ giữa các buổi cùng ngày, hoặc chỉ do ít dữ liệu huấn luyện hơn. Chỉ có 2 lần chia theo ngày.
- **Luật được ưu ái, nhãn bị sửa sau khi xem kết quả.** Tiêu chí nhãn dùng chính các ngưỡng của luật; nhãn v3 được sửa sau khi đã xem kết quả của luật (xem tuần 2). Khả năng nhãn thiên về luật làm mức hơn của random forest nhiều khả năng bị ước lượng **thấp** chứ không cao, nhưng chưa kiểm chứng.
- **Không tinh chỉnh siêu tham số.** Siêu tham số random forest cố định theo đăng ký trước (không tinh chỉnh lồng nhau vì 4 buổi trong ~130 rep quá nhiễu). Một cấu hình khác có thể tốt hơn hay kém hơn; chưa thử.
- **Các phân tích thăm dò làm sau khi đã thấy kết quả:** độ quan trọng đặc trưng, so sánh theo ngày và phép thử lỗi cố ý không phải kiểm định đăng ký trước. Nhóm "nhãn khác lỗi cố ý" chỉ có 45 rep. Nhãn ban đầu của mỗi hiệp lấy từ lỗi cố ý rồi mới sửa tay, nên nhãn trùng kịch bản (122 rep) có thể chứa rep chưa được xem lại kỹ.
- **Độ quan trọng đặc trưng chỉ để mô tả:** mức quan trọng theo độ giảm tạp chất (impurity) của rừng, không chứng minh đặc trưng đó gây ra lỗi.
- **Không có bằng chứng cho người dùng khác.** Mọi kết luận vẫn chỉ cho một người, một điều kiện quay; random forest học đặc thù của người và chỗ đặt máy có thể kém hơn luật khi gặp người dùng mới.

### Checklist
- [x] **Ngày 1:** MediaPipe chạy trên một clip push-up, xem pose có ổn không (rủi ro cao nhất)
- [x] Tuần 1: đồ thị góc khuỷu theo thời gian, thấy được các "sóng" của rep
- [x] Tuần 1: đếm rep đúng trên 4 clip thử (3 video + 1 hiệp quay bằng app: 6/7/6/5 rep)
- [x] Tuần 1: trang quay chạy trên điện thoại (HTTPS), xuất được JSON keypoint
- [x] Tuần 2: viết tiêu chí nhãn trước khi quay
- [x] Tuần 2: quay nhiều buổi khác nhau (không chỉ một buổi dài): 5 buổi, trong 2 ngày
- [x] Tuần 2: gán nhãn trong app, file nhãn theo từng hiệp
- [x] Tuần 3: chia train/test theo buổi, không theo rep
- [x] Tuần 3: bảng precision/recall/F1 và ma trận 2×2 cho từng lỗi, so với baseline luật
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
- [x] Chọn chỗ đặt điện thoại để quay push-up từ bên hông, sát sàn
- [x] Quay thử 1 clip push-up, chạy MediaPipe để xem pose có ổn không
- [x] Điền tiêu chí nhãn cho push-up trong `docs/labeling-criteria.md`
- [x] Lập lại plan tuần 1 cho push-up + trang quay (plan mode)
- [x] Tuần 1: pose offline, đếm rep, trang quay, backend nhận file, lệnh `python -m formcoach analyze`
- [x] Lập plan tuần 2 (plan mode): gán nhãn, đặc trưng lỗi, baseline luật, quay dataset
- [x] Tuần 2: gán nhãn, đặc trưng lỗi, baseline luật, dataset 5 buổi, kiểm định chéo theo buổi (macro-F1 0,72)
- [ ] Lập plan tuần 3 (plan mode): ngưỡng học trên tập train + random forest, luồng app
