"""Coach bằng Claude Haiku 5.5 (K2): viết lại số liệu của hiệp thành vài câu tự nhiên.

Prompt soạn ở `formcoach/coach/prompt.py` (hàm thuần, có test). File này chỉ lo phần đụng ra
ngoài: đọc key, gọi API, giới hạn thời gian, và quay về `TemplateCoach` khi có bất kỳ trục trặc nào.

Key do ban tổ chức cấp qua một cổng trung gian (gateway) theo định dạng OpenAI (`/chat/completions`,
`Authorization: Bearer`), không phải key Anthropic, nên dùng SDK `openai` trỏ vào cổng đó. Cổng
cũng nhận định dạng Anthropic nhưng docs không ghi, nên không dựa vào (bạn chọn, 2026-11-01).

Biến môi trường (cần cả hai, thiếu một thì chỉ dùng mẫu câu):
- `FORMCOACH_LLM_API_KEY`: key của cổng. Chỉ ở server, không gửi xuống web, không ghi vào log.
- `FORMCOACH_LLM_BASE_URL`: địa chỉ cổng, vd `https://proptit.dekthe.dev/v1`. Bắt buộc, vì thiếu
  thì SDK gọi thẳng OpenAI (không có model này).
- `FORMCOACH_LLM_MODEL` (tuỳ chọn): tên model trên cổng, mặc định `claude-haiku-5-5`. Đổi nhà
  cung cấp thì đổi ba biến này rồi chạy lại `python -m tools.try_coach`: prompt được viết và thử
  với Claude Haiku, model khác cần đọc lại câu trả lời.

Nhận xét được tính lúc đọc (mỗi lần mở trang kết quả), nên chữ của Claude được nhớ trong bộ nhớ
theo nội dung prompt: mở lại cùng hiệp thấy cùng câu và không tốn thêm lượt gọi. Đổi mục tiêu
làm prompt đổi nên có câu mới. Khởi động lại server thì quên, lần mở sau gọi lại.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from functools import cache
from typing import Any

import openai

from formcoach.coach import Coach, CoachProgress, TemplateCoach
from formcoach.coach.prompt import build_coach_prompt
from formcoach.types import Session

DEFAULT_MODEL = "claude-haiku-5-5"
TIMEOUT_S = 10.0  # trang kết quả chờ câu này; quá lâu thì dùng mẫu câu
MAX_RETRIES = 1  # SDK tự thử lại lỗi mạng / 429 / 5xx; một lần là đủ, không bắt người dùng chờ lâu
# Câu trả lời chỉ ~150–250 token, nhưng mô hình suy nghĩ trước khi viết và phần đó cũng tính vào
# đây (thử thật 2026-11-01: có hiệp 835 token ra). Định dạng OpenAI không chỉnh được mức suy nghĩ,
# nên để dư; bị cắt (`length`) thì dùng mẫu câu.
MAX_TOKENS = 2048
CACHE_SIZE = 1024

_log = logging.getLogger("uvicorn.error")


class CoachUnavailable(Exception):
    """Không có được câu từ LLM (lỗi mạng, hết hạn mức, bị từ chối, trả về rỗng...)."""


class ClaudeCoach(Coach):
    """Gọi Claude với prompt của `build_coach_prompt`. Lỗi → ném `CoachUnavailable`.

    `client` truyền vào từ ngoài (test dùng client giả, không gọi mạng, không tốn tiền).
    """

    def __init__(
        self, client: Any, model: str = DEFAULT_MODEL, cache_size: int = CACHE_SIZE
    ) -> None:
        self._client = client
        self.model = model
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()  # route FastAPI đồng bộ chạy trên nhiều luồng

    def summarize(self, session: Session, progress: CoachProgress | None = None) -> str:
        prompt = build_coach_prompt(session, progress)
        with self._lock:
            if prompt.user in self._cache:
                self._cache.move_to_end(prompt.user)
                return self._cache[prompt.user]

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
            )
        except openai.APIError as e:  # gốc của mọi lỗi SDK: mạng, quá giờ, 4xx, 5xx
            raise CoachUnavailable(type(e).__name__) from e

        if not response.choices:
            raise CoachUnavailable("không có câu trả lời")
        choice = response.choices[0]
        # Chỉ nhận câu kết thúc bình thường ("stop"): bị cắt ("length") hay bị lọc
        # ("content_filter") thì dùng mẫu câu còn hơn hiện nửa câu.
        if choice.finish_reason != "stop":
            raise CoachUnavailable(f"finish_reason={choice.finish_reason}")
        text = (choice.message.content or "").strip()
        if not text:
            raise CoachUnavailable("câu trả lời rỗng")

        usage = response.usage
        if usage is not None:
            _log.info(
                "Coach Claude: %d token vào, %d token ra",
                usage.prompt_tokens,
                usage.completion_tokens,
            )
        with self._lock:
            self._cache[prompt.user] = text
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)  # bỏ câu lâu nhất chưa ai mở lại
        return text


@cache
def llm_coach() -> ClaudeCoach | None:
    """Coach Claude dùng chung cho cả server; None nếu thiếu key hoặc địa chỉ cổng.

    Truyền key và địa chỉ thẳng vào client: SDK còn tự đọc `OPENAI_API_KEY`/`OPENAI_BASE_URL`, mà
    server chỉ nên dùng đúng biến đã cấu hình cho app này.
    """
    config = _llm_config()
    if config is None:
        return None
    key, base_url = config
    client = openai.OpenAI(
        api_key=key, base_url=base_url, timeout=TIMEOUT_S, max_retries=MAX_RETRIES
    )
    return ClaudeCoach(client, model=_llm_model())


def _llm_config() -> tuple[str, str] | None:
    key = os.environ.get("FORMCOACH_LLM_API_KEY")
    base_url = os.environ.get("FORMCOACH_LLM_BASE_URL")
    return (key, base_url) if key and base_url else None


def _llm_model() -> str:
    return os.environ.get("FORMCOACH_LLM_MODEL") or DEFAULT_MODEL


def coach_text(session: Session, progress: CoachProgress | None) -> tuple[str, str]:
    """(chữ, nguồn): nguồn "claude" nếu Claude trả lời được, không thì "template"."""
    coach = llm_coach()
    if coach is not None:
        try:
            return coach.summarize(session, progress), "claude"
        except CoachUnavailable as e:
            _log.warning("Coach Claude lỗi (%s), dùng mẫu câu", e)
    return TemplateCoach().summarize(session, progress), "template"


def log_coach_in_use() -> None:
    """Gọi lúc khởi động: in coach đang dùng (không in key)."""
    config = _llm_config()
    if config is not None:
        _log.info("Coach: LLM %s qua %s, lỗi thì dùng mẫu câu.", _llm_model(), config[1])
    elif os.environ.get("FORMCOACH_LLM_API_KEY") or os.environ.get("FORMCOACH_LLM_BASE_URL"):
        _log.warning(
            "Coach: mẫu câu (cần cả FORMCOACH_LLM_API_KEY và FORMCOACH_LLM_BASE_URL,"
            " đang thiếu một)."
        )
    else:
        _log.info("Coach: mẫu câu (chưa đặt FORMCOACH_LLM_API_KEY).")
