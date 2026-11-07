"""Giới hạn tải hiệp lên và lưu keypoint (backend/limits.py, ARCHITECTURE §4).

Hiệp tổng hợp chỉ ~9 s nên các test thu nhỏ giới hạn (monkeypatch) thay vì quay hiệp 30 phút.
"""

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend import limits
from backend.app import app
from backend.db import connect
from tests.synthetic import to_v2, train_session

PW = "mat-khau-dai"


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pg_database: str) -> TestClient:
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "0")
    monkeypatch.setenv("FORMCOACH_MODEL", "rules")
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"email": "an@x.vn", "password": PW})
    assert r.status_code == 201
    return c


def session(n: int = 0, v2: bool = False) -> dict:
    """Hiệp Tập ~9,2 s, 3 rep (rep 0 kết thúc ~3,4 s, rep 2 ~8,2 s), session_id riêng theo n."""
    data = train_session()
    data["session_id"] = f"2026-11-07T08-00-0{n}_abc123_pushup"
    return to_v2(data) if v2 else data


def stored_rows() -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "SELECT s.session_id, s.replay_frames, s.replay_s, p.session_pk IS NOT NULL AS has_kp"
            " FROM sessions s LEFT JOIN session_payloads p ON p.session_pk = s.id ORDER BY s.id"
        ).fetchall()


def replay_url(data: dict, index: int) -> str:
    return f"/api/sessions/pushup/{data['session_id']}/result/reps/{index}/replay"


# --- hàm thuần ---


def test_payload_budget() -> None:
    assert limits.payload_budget_s(0) == limits.KEEP_PAYLOAD_S  # 10 phút đầu
    assert limits.payload_budget_s(25 * 60) == 5 * 60  # còn 5 phút trong 24 giờ
    assert limits.payload_budget_s(40 * 60) == 0


def test_minutes_text() -> None:
    assert limits._minutes(30 * 60) == "30 phút"
    assert limits._minutes(30 * 60 + 20.7) == "30 phút 20 giây"
    assert limits._minutes(9.2) == "9 giây"


def test_payload_frames() -> None:
    t = np.arange(0, 10_000, 100.0) + 500  # 100 khung, 10 khung/giây, không bắt đầu ở 0
    assert limits.payload_frames(t, 2.0) == 21  # 0,0 … 2,0 s
    assert limits.payload_frames(t, 1000) == 100
    assert limits.payload_frames(t, 0.05) == 0  # 1 khung → không lưu
    assert limits.payload_frames(t, 0) == 0


# --- qua API ---


@pytest.mark.parametrize("v2", [False, True])
def test_short_session_stores_everything(client: TestClient, v2: bool) -> None:
    data = session(v2=v2)
    body = client.post("/api/sessions", json=data).json()
    assert body["replay_s"] == body["duration_s"]
    assert all(rep["replayable"] for rep in body["reps"])
    row = stored_rows()[0]
    assert row["has_kp"] and row["replay_frames"] == body["n_frames"]
    assert client.get(replay_url(data, 2)).status_code == 200


@pytest.mark.parametrize("v2", [False, True])
def test_long_session_keeps_first_part(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, v2: bool
) -> None:
    """Quá KEEP_PAYLOAD_S: vẫn chấm đủ 3 rep, chỉ lưu keypoint phần đầu."""
    monkeypatch.setattr(limits, "KEEP_PAYLOAD_S", 4.0)
    data = session(v2=v2)
    body = client.post("/api/sessions", json=data).json()
    assert body["summary"]["n_reps"] == 3
    assert body["replay_s"] == pytest.approx(4.0, abs=0.1)
    assert [rep["replayable"] for rep in body["reps"]] == [True, False, False]
    # Đọc lại kết quả cũng biết rep nào xem lại được.
    result = client.get(f"/api/sessions/pushup/{data['session_id']}/result").json()
    assert result["replay_s"] == body["replay_s"]
    assert [rep["replayable"] for rep in result["reps"]] == [True, False, False]

    assert client.get(replay_url(data, 0)).status_code == 200
    r = client.get(replay_url(data, 2))
    assert r.status_code == 404 and "không lưu keypoint" in r.json()["detail"]


def test_daily_limit_over_24_hours(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mỗi người tối đa DAILY_PAYLOAD_S giây keypoint trong 24 giờ; quá thì vẫn chấm."""
    monkeypatch.setattr(limits, "DAILY_PAYLOAD_S", 12.0)
    first = client.post("/api/sessions", json=session(0)).json()  # ~9,2 s: lưu đủ
    second = client.post("/api/sessions", json=session(1)).json()  # còn ~2,8 s: lưu phần đầu
    third = client.post("/api/sessions", json=session(2)).json()  # hết: không lưu
    assert first["replay_s"] == first["duration_s"]
    assert 2.5 < second["replay_s"] < 3.0
    assert third["replay_s"] == 0 and third["summary"]["n_reps"] == 3
    assert not any(rep["replayable"] for rep in third["reps"])
    assert [row["has_kp"] for row in stored_rows()] == [True, True, False]
    r = client.get(replay_url(session(2), 0))
    assert r.status_code == 404 and "không lưu keypoint" in r.json()["detail"]

    # Hiệp cũ hơn 24 giờ không còn tính: lùi created_at rồi gửi tiếp → lưu đủ.
    with connect() as conn:
        conn.execute("UPDATE sessions SET created_at = '2026-01-01T00:00:00+00:00'")
        conn.commit()
    fourth = client.post("/api/sessions", json=session(3)).json()
    assert fourth["replay_s"] == fourth["duration_s"]


def test_daily_limit_counts_old_rows_as_full(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hiệp lưu trước khi có giới hạn (replay_s NULL) tính bằng cả duration_s."""
    monkeypatch.setattr(limits, "DAILY_PAYLOAD_S", 12.0)
    client.post("/api/sessions", json=session(0))
    with connect() as conn:
        conn.execute("UPDATE sessions SET replay_frames = NULL, replay_s = NULL")
        conn.commit()
    second = client.post("/api/sessions", json=session(1)).json()
    assert 2.5 < second["replay_s"] < 3.0
    # Hiệp cũ (NULL) vẫn xem lại được mọi rep.
    result = client.get(f"/api/sessions/pushup/{session(0)['session_id']}/result").json()
    assert result["replay_s"] is None and all(rep["replayable"] for rep in result["reps"])
    assert client.get(replay_url(session(0), 2)).status_code == 200


def test_too_long_session_is_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_SESSION_S", 5)
    r = client.post("/api/sessions", json=session())
    assert r.status_code == 413
    assert r.json()["detail"] == "hiệp dài 9 giây, tối đa 5 giây mỗi hiệp"
    assert stored_rows() == []


def test_too_large_body_is_413(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 10_000)
    r = client.post("/api/sessions", json=session())
    assert r.status_code == 413 and "quá lớn" in r.json()["detail"]
    assert stored_rows() == []


def test_too_large_body_without_content_length(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Không có Content-Length (gửi theo khúc): vẫn dừng khi đọc quá giới hạn."""
    monkeypatch.setattr(limits, "MAX_UPLOAD_BYTES", 10_000)

    def chunks():
        yield b'{"pad": "' + b"x" * 20_000 + b'"}'

    r = client.post("/api/sessions", content=chunks())
    assert r.status_code == 413


def test_invalid_json_is_422(client: TestClient) -> None:
    r = client.post("/api/sessions", content=b"{ khong phai json")
    assert r.status_code == 422 and "JSON" in r.json()["detail"]
