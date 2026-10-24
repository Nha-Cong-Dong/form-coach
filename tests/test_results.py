"""B5: tải hiệp lên → phân loại → lưu kết quả theo người dùng → đọc lại."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.db import connect, db_path
from tests.synthetic import three_rep_session

PW = "mat-khau-dai"


@pytest.fixture
def make_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Tạo client đã đăng nhập bằng một email (mỗi client một cookie riêng)."""
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "0")
    monkeypatch.setenv("FORMCOACH_MODEL", "rules")

    def _make(email: str) -> TestClient:
        client = TestClient(app)
        r = client.post("/api/auth/register", json={"email": email, "password": PW})
        assert r.status_code == 201
        return client

    return _make


def test_upload_returns_reps_and_summary(make_client) -> None:
    client = make_client("an@example.com")
    payload = three_rep_session()
    r = client.post("/api/sessions", json=payload)
    assert r.status_code == 201
    body = r.json()
    # Trường cũ giữ nguyên, trường mới cộng thêm.
    assert body["session_id"] == payload["session_id"] and "frames_with_person" in body
    assert body["model_name"] == "rules"
    assert [rep["index"] for rep in body["reps"]] == [0, 1, 2]
    assert body["summary"]["n_reps"] == 3
    assert body["summary"]["n_good"] == sum(not rep["errors"] for rep in body["reps"])


def test_result_is_stored_and_read_back(make_client) -> None:
    client = make_client("an@example.com")
    payload = three_rep_session()
    uploaded = client.post("/api/sessions", json=payload).json()
    r = client.get(f"/api/sessions/pushup/{payload['session_id']}/result")
    assert r.status_code == 200
    result = r.json()
    assert result["reps"] == uploaded["reps"]
    assert result["summary"] == uploaded["summary"]
    assert result["model_name"] == "rules" and result["duration_s"] == uploaded["duration_s"]

    conn = connect(db_path())
    n_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    n_reps = conn.execute("SELECT COUNT(*) FROM reps").fetchone()[0]
    conn.close()
    assert (n_sessions, n_reps) == (1, 3)


def test_other_user_cannot_read_result(make_client) -> None:
    an = make_client("an@example.com")
    binh = make_client("binh@example.com")
    payload = three_rep_session()
    an.post("/api/sessions", json=payload)
    assert binh.get(f"/api/sessions/pushup/{payload['session_id']}/result").status_code == 404
    assert binh.get("/api/results").json() == []


def test_results_list_only_mine(make_client) -> None:
    an = make_client("an@example.com")
    payload = three_rep_session()
    an.post("/api/sessions", json=payload)
    items = an.get("/api/results").json()
    assert len(items) == 1
    item = items[0]
    assert item["session_id"] == payload["session_id"] and item["exercise"] == "pushup"
    assert item["n_reps"] == 3 and 0 <= item["n_good"] <= 3


def test_duplicate_upload_is_409_and_not_stored_twice(make_client) -> None:
    client = make_client("an@example.com")
    payload = three_rep_session()
    assert client.post("/api/sessions", json=payload).status_code == 201
    assert client.post("/api/sessions", json=payload).status_code == 409
    conn = connect(db_path())
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    conn.close()


def test_unknown_result_is_404(make_client) -> None:
    client = make_client("an@example.com")
    assert client.get("/api/sessions/pushup/khong-co/result").status_code == 404


def test_learned_model_without_labels_falls_back_to_rules(make_client, monkeypatch) -> None:
    # Server không có dữ liệu đã gán nhãn (vd khi deploy): vẫn chạy, ghi đúng mô hình đã dùng.
    monkeypatch.setenv("FORMCOACH_MODEL", "stump")
    client = make_client("an@example.com")
    body = client.post("/api/sessions", json=three_rep_session()).json()
    assert body["model_name"] == "rules"


def test_exercise_info_has_display_names(make_client) -> None:
    client = make_client("an@example.com")
    body = client.get("/api/exercises/pushup").json()
    assert body["error_display"]["hip_sag"] == "Hông võng"
    assert set(body["error_display"]) == set(body["error_labels"])
