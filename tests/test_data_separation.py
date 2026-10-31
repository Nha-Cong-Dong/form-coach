"""D1 (nhận xét mentor): hiệp của người dùng thường lưu riêng theo tài khoản, không lẫn vào dữ liệu
train (`data/sessions/`) mà build_dataset và màn Gán nhãn đọc."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from formcoach.dataset import build_dataset
from tests.synthetic import train_session

PW = "mat-khau-dai"
ADMIN = "admin@example.com"


@pytest.fixture
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "0")
    monkeypatch.setenv("FORMCOACH_MODEL", "rules")
    monkeypatch.setenv("FORMCOACH_ADMIN_EMAILS", ADMIN)
    monkeypatch.delenv("FORMCOACH_MODEL_PATH", raising=False)
    return tmp_path


def _client(email: str) -> tuple[TestClient, int]:
    client = TestClient(app)
    r = client.post("/api/auth/register", json={"email": email, "password": PW})
    assert r.status_code == 201
    return client, r.json()["id"]


def _session(sid: str) -> dict:
    payload = train_session()
    payload["session_id"] = sid
    return payload


def test_user_session_goes_to_own_folder_not_training_data(data: Path) -> None:
    user, uid = _client("an@example.com")
    assert (
        user.post("/api/sessions", json=_session("2026-10-31T10-00-00_pushup")).status_code == 201
    )
    own = data / "users" / str(uid) / "sessions" / "pushup" / "2026-10-31T10-00-00_pushup.json"
    assert own.is_file()
    assert not list((data / "sessions").glob("**/*.json"))  # thư mục train không có gì
    assert build_dataset(data, "pushup").sessions == ()  # build_dataset không thấy hiệp này

    admin, _ = _client(ADMIN)
    assert admin.get("/api/sessions/pushup").json() == []  # màn Gán nhãn không thấy
    review = admin.get("/api/sessions/pushup/2026-10-31T10-00-00_pushup/review")
    assert review.status_code == 404


def test_admin_session_goes_to_training_folder(data: Path) -> None:
    admin, _ = _client(ADMIN)
    assert (
        admin.post("/api/sessions", json=_session("2026-10-31T11-00-00_pushup")).status_code == 201
    )
    assert (data / "sessions" / "pushup" / "2026-10-31T11-00-00_pushup.json").is_file()
    assert not (data / "users").exists()
    ids = [s["session_id"] for s in admin.get("/api/sessions/pushup").json()]
    assert ids == ["2026-10-31T11-00-00_pushup"]


def test_owner_replays_from_own_folder_others_cannot(data: Path) -> None:
    sid = "2026-10-31T12-00-00_pushup"
    an, _ = _client("an@example.com")
    assert an.post("/api/sessions", json=_session(sid)).status_code == 201
    url = f"/api/sessions/pushup/{sid}/result/reps/0/replay"
    assert an.get(url).status_code == 200
    binh, _ = _client("binh@example.com")
    assert binh.get(url).status_code == 404  # hiệp của người khác: như không tồn tại
