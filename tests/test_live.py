"""C2: WebSocket /api/live (đếm rep trực tiếp). Luồng tổng hợp có đáp án biết trước."""

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app import app
from backend.auth import COOKIE_NAME
from backend.live import UNAUTHORIZED, LiveSession, parse_keypoints
from tests.synthetic import SIZE, plank_keypoints
from tests.test_online import reps_signal

START = {"type": "start", "exercise": "pushup", "fps": 30, "frame_size": list(SIZE)}


def frames(n_reps: int) -> list[dict]:
    kp = plank_keypoints(reps_signal(n_reps))
    return [{"t_ms": i * 1000 / 30, "kp": kp[i].tolist()} for i in range(len(kp))]


# --- logic giao thức (không mạng) ---


def test_session_counts_and_reports_only_changes() -> None:
    s = LiveSession()
    assert s.handle(START) == [{"type": "count", "n_reps": 0, "phase": "waiting_ready"}]
    out = [m for f in frames(3) for m in s.handle(f)]
    counts = [m["n_reps"] for m in out]
    assert counts == sorted(counts) and counts[-1] == 3  # tăng dần, không lùi
    assert len(out) < len(frames(3)) / 5  # chỉ gửi khi đổi, không gửi mỗi khung
    assert s.handle({"type": "stop"}) == [{"type": "final", "n_reps": 3}]
    assert s.finished and s.handle(frames(1)[0])[0]["type"] == "error"


def test_session_rejects_bad_messages_without_crashing() -> None:
    s = LiveSession()
    assert s.handle({"kp": None})[0]["detail"] == "gửi 'start' trước"
    for bad in [
        {"type": "start", "exercise": "deadlift", "fps": 30, "frame_size": [1280, 720]},
        {"type": "start", "exercise": "pushup", "fps": 0, "frame_size": [1280, 720]},
        {"type": "start", "exercise": "pushup", "fps": 30, "frame_size": [1280]},
    ]:
        assert s.handle(bad)[0]["type"] == "error"
    s.handle(START)
    assert s.handle(START)[0]["detail"] == "đã bắt đầu rồi"
    for bad in [[1, 2], {"type": "nhay"}, {"kp": [[0, 0, 1]] * 5}, {"kp": [[0, "a", 1]] * 33}]:
        assert s.handle(bad)[0]["type"] == "error"
    # Sau các tin hỏng vẫn đếm bình thường.
    for f in frames(2):
        s.handle(f)
    assert s.handle({"type": "stop"})[0]["n_reps"] == 2


def test_parse_keypoints() -> None:
    assert np.isnan(parse_keypoints(None)).all()
    assert parse_keypoints([[0.1, 0.2, 0.9]] * 33).shape == (33, 3)
    with pytest.raises(ValueError):
        parse_keypoints([[0.1, 0.2, float("nan")]] * 33)  # NaN trong JSON không hợp lệ


# --- kết nối thật qua TestClient ---


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "0")
    return TestClient(app)


def _login(client: TestClient) -> dict[str, str]:
    r = client.post(
        "/api/auth/register", json={"email": "an@example.com", "password": "mat-khau-dai"}
    )
    assert r.status_code == 201
    return {"cookie": f"{COOKIE_NAME}={client.cookies[COOKIE_NAME]}"}


def test_websocket_counts_synthetic_stream(client: TestClient) -> None:
    headers = _login(client)
    with client.websocket_connect("/api/live", headers=headers) as ws:
        ws.send_json(START)
        assert ws.receive_json()["n_reps"] == 0
        for f in frames(3):
            ws.send_json(f)
        ws.send_json({"type": "stop"})
        last = None
        while True:  # đọc hết các tin "count" tới tin "final"
            msg = ws.receive_json()
            if msg["type"] == "final":
                last = msg
                break
        assert last == {"type": "final", "n_reps": 3}


def test_websocket_bad_frame_returns_error_and_stays_open(client: TestClient) -> None:
    headers = _login(client)
    with client.websocket_connect("/api/live", headers=headers) as ws:
        ws.send_text("khong-phai-json")
        assert ws.receive_json() == {"type": "error", "detail": "không phải JSON"}
        ws.send_json(START)
        assert ws.receive_json()["type"] == "count"


@pytest.mark.parametrize("cookie", [None, f"{COOKIE_NAME}=token-la"])
def test_websocket_rejects_without_login(client: TestClient, cookie: str | None) -> None:
    headers = {"cookie": cookie} if cookie else {}
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/api/live", headers=headers):
            pass
    assert e.value.code == UNAUTHORIZED
