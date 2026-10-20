import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from tests.synthetic import make_session, three_rep_session


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


# --- gán nhãn: danh sách hiệp, xem lại, lưu nhãn ---


def upload(client: TestClient, session_id: str, set_errors=(), notes: str | None = None) -> dict:
    payload = three_rep_session(set_errors)
    payload["session_id"] = session_id
    if notes is not None:
        payload["notes"] = notes
    assert client.post("/api/sessions", json=payload).status_code == 201
    return payload


def test_list_sessions(client: TestClient) -> None:
    assert client.get("/api/sessions/pushup").json() == []
    upload(client, "a_pushup", ["shallow"], notes="tối, áo đen")
    upload(client, "b_pushup")  # file không có "notes"
    items = client.get("/api/sessions/pushup").json()
    assert [i["session_id"] for i in items] == ["b_pushup", "a_pushup"]  # mới nhất trước
    assert items[1]["set_errors"] == ["shallow"]
    assert [i["notes"] for i in items] == ["", "tối, áo đen"]
    assert client.get("/api/sessions/pushup/a_pushup/review").json()["notes"] == "tối, áo đen"
    assert all(i["n_reps"] == 3 and i["labeled"] is False for i in items)


def test_list_shows_corrupt_file_with_error(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "sessions" / "pushup"
    folder.mkdir(parents=True)
    (folder / "hong.json").write_text("{}", encoding="utf-8")
    items = client.get("/api/sessions/pushup").json()
    assert items[0]["session_id"] == "hong" and "error" in items[0]


def test_list_unknown_exercise_is_404(client: TestClient) -> None:
    assert client.get("/api/sessions/deadlift").status_code == 404


def test_review_and_save_labels(client: TestClient, tmp_path: Path) -> None:
    upload(client, "s1", ["hip_sag"])
    review = client.get("/api/sessions/pushup/s1/review").json()
    assert len(review["reps"]) == 3 and review["labels_saved"] is False

    labels = review["labels"]
    labels["reps"][0]["errors"] = ["hip_sag", "shallow"]
    labels["reps"][2] |= {"valid": False, "errors": []}
    r = client.put("/api/sessions/pushup/s1/labels", json=labels)
    assert r.status_code == 200 and r.json()["n_reps"] == 3
    assert (tmp_path / "labels" / "pushup" / "s1.json").exists()

    again = client.get("/api/sessions/pushup/s1/review").json()
    assert again["labels_saved"] is True
    assert again["labels"]["reps"][0]["errors"] == ["hip_sag", "shallow"]
    assert again["labels"]["reps"][2]["valid"] is False
    assert client.get("/api/sessions/pushup").json()[0]["labeled"] is True


def test_put_invalid_labels_is_422(client: TestClient) -> None:
    upload(client, "s1")
    labels = client.get("/api/sessions/pushup/s1/review").json()["labels"]
    labels["reps"][0]["errors"] = ["good"]
    assert client.put("/api/sessions/pushup/s1/labels", json=labels).status_code == 422


def test_put_labels_for_other_session_is_422(client: TestClient) -> None:
    upload(client, "s1")
    upload(client, "s2")
    labels = client.get("/api/sessions/pushup/s1/review").json()["labels"]
    assert client.put("/api/sessions/pushup/s2/labels", json=labels).status_code == 422


def test_put_misaligned_labels_is_409(client: TestClient) -> None:
    upload(client, "s1")
    labels = client.get("/api/sessions/pushup/s1/review").json()["labels"]
    labels["reps"] = labels["reps"][:2]  # thiếu một rep so với rep hiện tại
    r = client.put("/api/sessions/pushup/s1/labels", json=labels)
    assert r.status_code == 409 and "số rep khác" in r.json()["detail"]


@pytest.mark.parametrize("session_id", ["khong_co", "..", "a.b"])
def test_review_unknown_session_is_404(client: TestClient, session_id: str) -> None:
    assert client.get(f"/api/sessions/pushup/{session_id}/review").status_code == 404
