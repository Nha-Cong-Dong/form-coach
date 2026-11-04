"""Soạn prompt cho coach LLM (K2). Hàm thuần: không gọi mạng, không đọc key.

Phần gọi API thật (`ClaudeCoach`) nằm ở `backend/`, vì nó đụng ra ngoài (mạng, key, tiền), giống
cách backend đọc biến môi trường và mở DB. Ở đây chỉ biến số liệu của hiệp thành chữ gửi đi.

Số liệu gửi cho LLM chính là câu của `TemplateCoach`, không soạn lại từ đầu. Vì vậy LLM thấy
đúng những con số người dùng vẫn thấy khi dùng mẫu câu (kể cả quy tắc chỉ in số đo vượt ngưỡng
luật), và chỉ có một chỗ quyết định "con số nào được nói ra". Đánh đổi: LLM không thấy số đo
từng rep, nên không nói chi tiết hơn mẫu câu được.
"""

from __future__ import annotations

from dataclasses import dataclass

from formcoach.coach.base import CoachProgress
from formcoach.coach.template import TemplateCoach
from formcoach.types import Session

# Cố định, không chứa số liệu của hiệp: mọi lần gọi gửi cùng một chỉ dẫn. Quy tắc 4 ghi cứng tên
# hiển thị của lỗi push-up (Exercise.error_display) theo độ tin cậy ở README §8 (F1, kappa gán lại
# mù); đổi tên lỗi thì sửa cả ở đây (test_prompt_names_every_pushup_error bắt chỗ lệch).
SYSTEM_PROMPT = """\
Bạn là trợ lý tập luyện thân thiện trong app Form Coach. Sau mỗi hiệp, viết nhận xét ngắn \
(2 đến 4 câu văn xuôi) bằng tiếng Việt để khích lệ và giúp người tập sửa kỹ thuật.

Quy tắc:
1. Định dạng: văn xuôi liền mạch, không markdown, không gạch đầu dòng, không emoji.
2. Số liệu: chỉ dùng con số có trong dữ liệu, giữ nguyên cách viết. Không thêm số rep, góc, \
ngày hay phần trăm nào khác. Lỗi nào không kèm số đo thì không tự thêm số đo cho lỗi đó.
3. Trọng tâm: nếu có lỗi, nói về lỗi gặp ở nhiều rep nhất, kèm một gợi ý sửa ngắn về kỹ thuật \
chung cho chính lỗi đó (ví dụ siết bụng, hạ ngực thấp hơn). Không liệt kê hết mọi lỗi, và không \
gợi ý sửa cho lỗi không có trong dữ liệu.
4. Giọng theo độ tin cậy:
   - "Hông võng", "Hông nhô cao": app nhận ra khá chắc, nhận xét rõ ràng.
   - "Chưa xuống đủ sâu", "Chưa duỗi hết tay", "Cổ gục hoặc rướn": ranh giới mơ hồ hơn, \
nói mềm ("có vẻ", "nên để ý").
5. Tiến độ: nếu có dòng "Hôm nay … rep, streak … ngày" thì nhắc ngắn gọn; nếu không có thì \
không nói về mục tiêu hay streak.
6. An toàn: không chẩn đoán chấn thương, không khuyên về y tế. Không nói mình là AI, không viết \
câu "Công cụ hỗ trợ, không thay huấn luyện viên" (giao diện đã hiện câu này).
7. Trường hợp đặc biệt:
   - Không đếm được rep nào: chỉ nhắc kiểm tra camera thấy rõ cả người, không nhận xét kỹ thuật.
   - Tất cả rep đều đúng: khen và khích lệ giữ phong độ."""


# Tên bài gửi cho LLM: gửi mã ("pushup") thì nó viết lại nguyên mã vào câu ("Hiệp pushup này",
# thử thật 2026-11-01). Bài chưa có tên ở đây thì gửi mã.
EXERCISE_NAMES = {"pushup": "chống đẩy (push-up)"}


@dataclass(frozen=True)
class CoachPrompt:
    """Hai phần gửi cho LLM: chỉ dẫn cố định (`system`) và số liệu của hiệp (`user`)."""

    system: str
    user: str


def build_coach_prompt(session: Session, progress: CoachProgress | None = None) -> CoachPrompt:
    """Prompt cho một hiệp: số liệu lấy từ `TemplateCoach`; không gửi session_id, hình, keypoint."""
    facts = TemplateCoach().summarize(session, progress)
    name = EXERCISE_NAMES.get(session.exercise, session.exercise)
    user = f"Bài tập: {name}\nSố liệu hiệp vừa tập:\n{facts}"
    return CoachPrompt(system=SYSTEM_PROMPT, user=user)
