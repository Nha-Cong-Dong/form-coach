import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from tests.synthetic import make_session


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Mọi file ghi vào thư mục tạm của test, không đụng data/ thật.
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    return TestClient(app)


def test_exercise_info(client: TestClient) -> None:
    r = client.get("/api/exercises/pushup")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "pushup"
    assert "shallow" in body["error_labels"] and "good" not in body["error_labels"]


def test_unknown_exercise_is_404(client: TestClient) -> None:
    assert client.get("/api/exercises/deadlift").status_code == 404


def test_upload_saves_file_and_returns_summary(client: TestClient, tmp_path: Path) -> None:
    payload = make_session()
    payload["frames"][3]["kp"] = None  # một khung không thấy người
    r = client.post("/api/sessions", json=payload)

    assert r.status_code == 201
    body = r.json()
    assert body["session_id"] == payload["session_id"]
    assert body["n_frames"] == 60
    assert body["frames_with_person"] == 59
    assert body["fps"] == pytest.approx(30, abs=2)
    assert body["duration_s"] == pytest.approx(59 / 30, abs=0.2)

    saved = tmp_path / "sessions" / "pushup" / f"{payload['session_id']}.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == payload  # lưu nguyên văn


def test_bad_format_is_422_with_message(client: TestClient, tmp_path: Path) -> None:
    payload = make_session()
    payload["set_errors"] = ["good"]
    r = client.post("/api/sessions", json=payload)
    assert r.status_code == 422
    assert "không hợp lệ" in r.json()["detail"]
    assert not (tmp_path / "sessions").exists()  # sai thì không ghi gì


def test_non_object_body_is_rejected(client: TestClient) -> None:
    assert client.post("/api/sessions", json=[1, 2, 3]).status_code == 422


@pytest.mark.parametrize("bad_id", ["../../evil", "a/b", "..", "x" * 101])
def test_path_traversal_blocked(client: TestClient, tmp_path: Path, bad_id: str) -> None:
    payload = make_session()
    payload["session_id"] = bad_id
    r = client.post("/api/sessions", json=payload)
    assert r.status_code == 422
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert written == []  # không file nào được ghi, kể cả ngoài thư mục


def test_duplicate_session_is_409_and_not_overwritten(client: TestClient, tmp_path: Path) -> None:
    first = make_session()
    assert client.post("/api/sessions", json=first).status_code == 201
    second = make_session(seed=1)  # cùng session_id, nội dung khác
    r = client.post("/api/sessions", json=second)
    assert r.status_code == 409
    saved = tmp_path / "sessions" / "pushup" / f"{first['session_id']}.json"
    assert json.loads(saved.read_text(encoding="utf-8")) == first
