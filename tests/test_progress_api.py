"""P2: đặt mục tiêu và đọc tiến độ qua API (bảng goals + hiệp đã lưu → formcoach/progress)."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.db import connect, db_path
from tests.synthetic import three_rep_session

PW = "mat-khau-dai"
# Mục tiêu chỉ đặt được cho "hôm nay" (±1 ngày so với server), nên dữ liệu thử bám ngày thật.
TODAY = datetime.now(UTC).date()


@pytest.fixture
def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "0")
    monkeypatch.setenv("FORMCOACH_MODEL", "rules")

    def _make(email: str) -> TestClient:
        client = TestClient(app)
        assert client.post("/api/auth/register", json={"email": email, "password": PW}).is_success
        return client

    return _make


def _upload(client: TestClient, day: date, i: int) -> int:
    """Tải một hiệp 3 rep quay lúc 18:0i ngày `day` (giờ VN); trả số rep đúng bộ phân loại chấm."""
    payload = three_rep_session()
    payload["session_id"] = f"{day.isoformat()}T18-00-{i:02d}_pushup"
    payload["recorded_at"] = f"{day.isoformat()}T18:00:{i:02d}+07:00"
    r = client.post("/api/sessions", json=payload)
    assert r.status_code == 201
    return r.json()["summary"]["n_good"]


def _progress(client: TestClient, start: date, end: date) -> dict:
    r = client.get("/api/progress", params={"from": start.isoformat(), "to": end.isoformat()})
    assert r.status_code == 200
    return r.json()


def test_goal_roundtrip_and_same_day_overwrites(make_client) -> None:
    client = make_client("an@example.com")
    assert client.get("/api/goals").json() == {"exercise": "pushup", "goal": None}

    body = {"exercise": "pushup", "daily_reps": 30, "today": TODAY.isoformat()}
    assert client.put("/api/goals", json=body).status_code == 200
    client.put("/api/goals", json={**body, "daily_reps": 40, "min_good_ratio": 0.7})
    goal = client.get("/api/goals").json()["goal"]
    assert goal == {"daily_reps": 40, "min_good_ratio": 0.7, "from_date": TODAY.isoformat()}

    conn = connect(db_path())
    assert conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0] == 1  # ghi đè, không thêm
    conn.close()


@pytest.mark.parametrize(
    "change",
    [
        {"today": (TODAY - timedelta(days=5)).isoformat()},  # lùi về quá khứ
        {"today": "hôm nay"},
        {"daily_reps": 0},
        {"min_good_ratio": 1.5},
    ],
)
def test_bad_goal_is_rejected(make_client, change: dict) -> None:
    client = make_client("an@example.com")
    body = {"exercise": "pushup", "daily_reps": 30, "today": TODAY.isoformat(), **change}
    assert client.put("/api/goals", json=body).status_code == 422
    assert client.get("/api/goals").json()["goal"] is None


def test_unknown_exercise_is_404(make_client) -> None:
    client = make_client("an@example.com")
    body = {"exercise": "squat-nhay", "daily_reps": 30, "today": TODAY.isoformat()}
    assert client.put("/api/goals", json=body).status_code == 404
    assert client.get("/api/goals", params={"exercise": "squat-nhay"}).status_code == 404


def test_progress_days_goal_and_streak(make_client) -> None:
    client = make_client("an@example.com")
    d2, d1 = TODAY - timedelta(days=2), TODAY - timedelta(days=1)
    good = _upload(client, d2, 0) + _upload(client, d1, 0)
    good += _upload(client, TODAY, 0) + _upload(client, TODAY, 1)
    client.put("/api/goals", json={"exercise": "pushup", "daily_reps": 6, "today": str(TODAY)})

    p = _progress(client, TODAY - timedelta(days=3), TODAY)
    assert [d["n_reps"] for d in p["days"]] == [0, 3, 3, 6]
    # Trước khi đặt mục tiêu: có tập là đạt. Hôm nay: 6 ≥ 6.
    assert [d["daily_reps"] for d in p["days"]] == [None, None, None, 6]
    assert [d["met"] for d in p["days"]] == [False, True, True, True]
    assert p["streak"] == 3
    assert p["today"]["day"] == TODAY.isoformat() and p["goal"]["daily_reps"] == 6
    assert p["totals"]["n_reps"] == 12 and p["totals"]["n_good"] == good

    # Nâng mục tiêu lên 7: hôm nay chưa đạt nhưng chuỗi chưa đứt (ngày chưa hết).
    client.put("/api/goals", json={"exercise": "pushup", "daily_reps": 7, "today": str(TODAY)})
    p = _progress(client, TODAY - timedelta(days=3), TODAY)
    assert p["today"]["met"] is False and p["streak"] == 2


def test_progress_is_per_user(make_client) -> None:
    an = make_client("an@example.com")
    binh = make_client("binh@example.com")
    _upload(an, TODAY, 0)
    an.put("/api/goals", json={"exercise": "pushup", "daily_reps": 3, "today": str(TODAY)})

    p = _progress(binh, TODAY, TODAY)
    assert p["goal"] is None and p["streak"] == 0 and p["totals"]["n_reps"] == 0
    assert binh.get("/api/goals").json()["goal"] is None


@pytest.mark.parametrize(
    ("start", "end"),
    [(TODAY, TODAY - timedelta(days=1)), (TODAY - timedelta(days=366), TODAY)],
)
def test_bad_range_is_rejected(make_client, start: date, end: date) -> None:
    client = make_client("an@example.com")
    r = client.get("/api/progress", params={"from": start.isoformat(), "to": end.isoformat()})
    assert r.status_code == 422


def test_progress_needs_login(make_client) -> None:
    make_client("an@example.com")
    r = TestClient(app).get("/api/progress", params={"from": str(TODAY), "to": str(TODAY)})
    assert r.status_code == 401


def test_result_has_coach_with_progress_up_to_that_set(make_client) -> None:
    client = make_client("an@example.com")
    client.put("/api/goals", json={"exercise": "pushup", "daily_reps": 6, "today": str(TODAY)})
    _upload(client, TODAY - timedelta(days=1), 0)  # hôm qua chưa có mục tiêu: có tập là đạt
    _upload(client, TODAY, 0)
    _upload(client, TODAY, 1)

    def coach(i: int) -> dict:
        sid = f"{TODAY.isoformat()}T18-00-{i:02d}_pushup"
        r = client.get(f"/api/sessions/pushup/{sid}/result")
        assert r.status_code == 200
        return r.json()["coach"]

    # Hiệp đầu hôm nay: chỉ tính chính nó (3/6, chưa đạt → streak chỉ có hôm qua), dù xem sau
    # khi đã tập hiệp thứ hai. Sau hiệp thứ hai: 6/6 đạt → streak hôm qua + hôm nay.
    assert coach(0)["source"] == "template"
    assert coach(0)["text"].splitlines()[-1] == "Hôm nay 3/6 rep, streak 1 ngày."
    assert coach(1)["text"].splitlines()[-1] == "Hôm nay 6/6 rep, streak 2 ngày."
    assert coach(1)["text"].startswith("Hiệp này: 3 rep")


def test_upload_response_has_coach(make_client) -> None:
    client = make_client("an@example.com")
    payload = three_rep_session()
    payload["recorded_at"] = f"{TODAY.isoformat()}T18:00:00+07:00"
    r = client.post("/api/sessions", json=payload)
    assert r.status_code == 201
    assert r.json()["coach"]["text"].splitlines()[-1] == "Hôm nay 3 rep, streak 1 ngày."
