"""D1 (nhận xét mentor): hiệp của người dùng thường không lẫn vào dữ liệu train (`data/sessions/`)
mà build_dataset và màn Gán nhãn đọc. P2 (Postgres): keypoint mọi hiệp ở DB (nén), để xem lại rep
không cần file; chỉ hiệp của admin ghi thêm file train."""

import gzip
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.db import connect
from formcoach.dataset import build_dataset
from tests.synthetic import train_session

PW = "mat-khau-dai"
ADMIN = "admin@example.com"


@pytest.fixture
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pg_database: str) -> Path:
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


def test_user_session_only_in_db_not_training_data(data: Path) -> None:
    user, _ = _client("an@example.com")
    assert (
        user.post("/api/sessions", json=_session("2026-10-31T10-00-00_pushup")).status_code == 201
    )
    assert not [p for p in data.rglob("*") if p.is_file()]  # không ghi file nào
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
    assert _payload_count() == 1  # vẫn có keypoint ở DB để xem lại rep như mọi người
    ids = [s["session_id"] for s in admin.get("/api/sessions/pushup").json()]
    assert ids == ["2026-10-31T11-00-00_pushup"]


def test_owner_replays_others_cannot(data: Path) -> None:
    sid = "2026-10-31T12-00-00_pushup"
    an, _ = _client("an@example.com")
    assert an.post("/api/sessions", json=_session(sid)).status_code == 201
    url = f"/api/sessions/pushup/{sid}/result/reps/0/replay"
    assert an.get(url).status_code == 200
    binh, _ = _client("binh@example.com")
    assert binh.get(url).status_code == 404  # hiệp của người khác: như không tồn tại


def _payload_count() -> int:
    with connect() as c:
        return c.execute("SELECT COUNT(*) AS n FROM session_payloads").fetchone()["n"]


def test_payload_stored_compressed_and_identical(data: Path) -> None:
    an, _ = _client("an@example.com")
    payload = _session("2026-10-31T13-00-00_pushup")
    assert an.post("/api/sessions", json=payload).status_code == 201
    with connect() as c:
        blob = c.execute("SELECT payload_gz FROM session_payloads").fetchone()["payload_gz"]
    assert json.loads(gzip.decompress(blob)) == payload  # giải nén ra đúng y JSON đã gửi
    assert len(blob) < len(json.dumps(payload)) / 2  # nén thật (dữ liệu tổng hợp nén rất tốt)


def test_replay_survives_losing_every_file(data: Path) -> None:
    # Render Free xoá mọi file khi restart: xem lại rep phải chỉ cần DB, cả hiệp của admin.
    sid = "2026-10-31T14-00-00_pushup"
    admin, _ = _client(ADMIN)
    assert admin.post("/api/sessions", json=_session(sid)).status_code == 201
    shutil.rmtree(data / "sessions")
    assert admin.get(f"/api/sessions/pushup/{sid}/result/reps/0/replay").status_code == 200


def test_duplicate_session_is_409_without_files(data: Path) -> None:
    an, _ = _client("an@example.com")
    payload = _session("2026-10-31T15-00-00_pushup")
    assert an.post("/api/sessions", json=payload).status_code == 201
    assert an.post("/api/sessions", json=payload).status_code == 409
    assert _payload_count() == 1


def test_replay_falls_back_to_old_file(data: Path) -> None:
    # Hiệp gửi trước P2: kết quả ở DB nhưng keypoint chỉ có ở file thư mục riêng cũ.
    sid = "2026-10-31T16-00-00_pushup"
    an, uid = _client("an@example.com")
    payload = _session(sid)
    assert an.post("/api/sessions", json=payload).status_code == 201
    with connect() as c:
        c.execute("DELETE FROM session_payloads")
    old = data / "users" / str(uid) / "sessions" / "pushup" / f"{sid}.json"
    old.parent.mkdir(parents=True)
    old.write_text(json.dumps(payload), encoding="utf-8")
    assert an.get(f"/api/sessions/pushup/{sid}/result/reps/0/replay").status_code == 200
