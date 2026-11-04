"""ClaudeCoach bằng client giả: không gọi mạng, không cần key, không tốn tiền."""

from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from backend import coach_llm
from backend.coach_llm import ClaudeCoach, CoachUnavailable, coach_text
from formcoach.coach import CoachProgress, TemplateCoach
from formcoach.coach.prompt import SYSTEM_PROMPT, build_coach_prompt
from formcoach.types import Rep, RepResult, Session


def _session(n: int = 3, errors: frozenset[str] = frozenset()) -> Session:
    results = [RepResult(Rep(i, i * 10, i * 10 + 9, {}), errors, None) for i in range(n)]
    return Session("s", "pushup", results)


def _response(text: str | None = "Làm tốt lắm.", finish_reason: str = "stop") -> SimpleNamespace:
    """Giống ChatCompletion của SDK openai (chỉ các trường code đọc)."""
    message = SimpleNamespace(content=text)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=SimpleNamespace(prompt_tokens=500, completion_tokens=40),
    )


class FakeClient:
    """Ghi lại mỗi lần gọi; trả `reply` hoặc ném nó nếu là exception."""

    def __init__(self, reply: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self.reply = reply
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def _use(monkeypatch: pytest.MonkeyPatch, client: FakeClient) -> None:
    coach = ClaudeCoach(client)
    monkeypatch.setattr(coach_llm, "llm_coach", lambda: coach)


def test_sends_prompt_and_returns_text() -> None:
    client = FakeClient(_response("  Hiệp tốt, giữ vững nhé.  "))
    session, progress = _session(), CoachProgress(10, 50, 2)
    assert ClaudeCoach(client).summarize(session, progress) == "Hiệp tốt, giữ vững nhé."
    (call,) = client.calls
    assert call["model"] == "claude-haiku-5-5"
    assert call["messages"] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_coach_prompt(session, progress).user},
    ]


def test_same_prompt_is_cached_new_progress_asks_again() -> None:
    client = FakeClient(_response())
    coach = ClaudeCoach(client)
    coach.summarize(_session(), CoachProgress(10, 50, 2))
    coach.summarize(_session(), CoachProgress(10, 50, 2))
    assert len(client.calls) == 1  # mở lại trang kết quả: không gọi thêm
    coach.summarize(_session(), CoachProgress(10, 30, 2))  # đổi mục tiêu → prompt khác
    assert len(client.calls) == 2


def test_cache_is_bounded() -> None:
    client = FakeClient(_response())
    coach = ClaudeCoach(client, cache_size=2)
    for n in (1, 2, 3):
        coach.summarize(_session(n))
    coach.summarize(_session(1))  # rep 1 đã bị bỏ khỏi cache (cũ nhất)
    assert len(client.calls) == 4


@pytest.mark.parametrize(
    "reply",
    [
        openai.APIConnectionError(request=httpx2.Request("POST", "https://gateway.test/v1")),
        openai.APITimeoutError(request=httpx2.Request("POST", "https://gateway.test/v1")),
        _response("Câu bị cắt giữa", finish_reason="length"),
        _response(None, finish_reason="content_filter"),
        _response(""),
        _response(None),
        SimpleNamespace(choices=[], usage=None),
    ],
    ids=["connection", "timeout", "length", "content_filter", "empty", "none", "no_choices"],
)
def test_any_failure_falls_back_to_template(monkeypatch: pytest.MonkeyPatch, reply: Any) -> None:
    session = _session(2, frozenset({"hip_sag"}))
    with pytest.raises(CoachUnavailable):
        ClaudeCoach(FakeClient(reply)).summarize(session)
    _use(monkeypatch, FakeClient(reply))
    assert coach_text(session, None) == (TemplateCoach().summarize(session), "template")


def test_failure_is_not_cached() -> None:
    client = FakeClient(_response(finish_reason="content_filter"))
    coach = ClaudeCoach(client)
    with pytest.raises(CoachUnavailable):
        coach.summarize(_session())
    client.reply = _response("Ổn rồi.")
    assert coach.summarize(_session()) == "Ổn rồi."


def test_source_claude_when_it_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, FakeClient(_response("Tốt.")))
    assert coach_text(_session(), None) == ("Tốt.", "claude")


def test_no_key_means_template_only() -> None:
    # conftest đã xoá hai biến FORMCOACH_LLM_* và xoá cache của llm_coach.
    assert coach_llm.llm_coach() is None
    assert coach_text(_session(), None)[1] == "template"


@pytest.mark.parametrize("missing", ["FORMCOACH_LLM_API_KEY", "FORMCOACH_LLM_BASE_URL"])
def test_needs_both_key_and_base_url(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    # Thiếu địa chỉ cổng thì SDK sẽ gọi thẳng OpenAI: không được tạo client.
    monkeypatch.setenv("FORMCOACH_LLM_API_KEY", "sk-test-khong-that")
    monkeypatch.setenv("FORMCOACH_LLM_BASE_URL", "https://gateway.test/v1")
    monkeypatch.delenv(missing)
    coach_llm.llm_coach.cache_clear()
    assert coach_llm.llm_coach() is None


def test_key_and_base_url_build_claude_coach(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMCOACH_LLM_API_KEY", "sk-test-khong-that")
    monkeypatch.setenv("FORMCOACH_LLM_BASE_URL", "https://gateway.test/v1")
    coach_llm.llm_coach.cache_clear()
    coach = coach_llm.llm_coach()  # chỉ tạo client, chưa gọi mạng
    assert isinstance(coach, ClaudeCoach)
    assert str(coach._client.base_url).rstrip("/") == "https://gateway.test/v1"


def test_model_from_env_or_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FORMCOACH_LLM_API_KEY", "sk-test-khong-that")
    monkeypatch.setenv("FORMCOACH_LLM_BASE_URL", "https://gateway.test/v1")
    coach_llm.llm_coach.cache_clear()
    assert coach_llm.llm_coach().model == "claude-haiku-5-5"  # không đặt → mặc định

    monkeypatch.setenv("FORMCOACH_LLM_MODEL", "model-khac")
    coach_llm.llm_coach.cache_clear()
    coach = coach_llm.llm_coach()
    client = FakeClient(_response())
    coach._client = client
    coach.summarize(_session())
    assert client.calls[0]["model"] == "model-khac"
