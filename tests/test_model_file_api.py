"""D1b: server đọc mô hình từ FORMCOACH_MODEL_PATH (backend/results.py), kiểm tra lúc khởi động."""

from datetime import datetime
from pathlib import Path

import pytest
import sklearn
from fastapi.testclient import TestClient

from backend.app import app
from formcoach.dataset import Dataset, RepRow
from formcoach.exercises import get_exercise
from formcoach.models.store import ModelFileError, ModelInfo, save_model
from formcoach.models.train import train_classifier
from tests.synthetic import train_session

PUSHUP = get_exercise("pushup")
NOW = datetime(2026, 10, 31, 12, 0)


def _model_file(path: Path, **info: object) -> Path:
    """File rf train trên dữ liệu tổng hợp (tách ở ~100° góc khuỷu đáy)."""
    rows = [
        RepRow("s", NOW, i, 0.0, 1.0, {"min_elbow_angle": 80.0 + i}, frozenset()) for i in range(10)
    ]
    rows += [
        RepRow("s", NOW, 10 + i, 0.0, 1.0, {"min_elbow_angle": 120.0 + i}, frozenset({"shallow"}))
        for i in range(10)
    ]
    classifier, _ = train_classifier("rf", PUSHUP, Dataset("pushup", (), tuple(rows), ()))
    base = {
        "model_name": "rf",
        "exercise": "pushup",
        "n_reps": 20,
        "trained_at": "2026-10-31T05:00:00+00:00",
        "sklearn_version": sklearn.__version__,
    }
    save_model(path, classifier, ModelInfo(**{**base, **info}))
    return path


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pg_database: str) -> Path:
    monkeypatch.setenv("FORMCOACH_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FORMCOACH_ALLOW_REGISTER", "1")
    monkeypatch.setenv("FORMCOACH_COOKIE_SECURE", "0")

    # Có file mô hình thì server không được đọc data/ để train.
    def no_dataset(*_args: object) -> None:
        raise AssertionError("không được đọc data/ khi đã có FORMCOACH_MODEL_PATH")

    monkeypatch.setattr("backend.results.build_dataset", no_dataset)
    return tmp_path


def test_upload_uses_model_file(env: Path, monkeypatch) -> None:
    monkeypatch.setenv("FORMCOACH_MODEL_PATH", str(_model_file(env / "m.pkl")))
    monkeypatch.setenv("FORMCOACH_MODEL", "rules")  # có file thì bỏ qua biến này
    with TestClient(app) as client:  # `with` chạy lifespan: đọc file lúc khởi động
        client.post(
            "/api/auth/register", json={"email": "an@example.com", "password": "mat-khau-dai"}
        )
        r = client.post("/api/sessions", json=train_session())
    assert r.status_code == 201
    assert r.json()["model_name"] == "rf@2026-10-31"  # kèm ngày train trong file


@pytest.mark.parametrize(
    "make",
    [
        lambda p: p / "khong-co.pkl",  # không có file
        lambda p: _model_file(p / "m.pkl", sklearn_version="0.0.1"),  # khác bản scikit-learn
    ],
)
def test_bad_model_file_stops_startup(env: Path, monkeypatch, make) -> None:
    monkeypatch.setenv("FORMCOACH_MODEL_PATH", str(make(env)))
    with pytest.raises(ModelFileError), TestClient(app):
        pass


def test_startup_logs_model_in_use(env: Path, monkeypatch, caplog) -> None:
    # Nhận xét mentor: app phải báo rõ đang dùng mô hình nào (log lúc khởi động).
    monkeypatch.setenv("FORMCOACH_MODEL_PATH", str(_model_file(env / "m.pkl")))
    with caplog.at_level("INFO", logger="uvicorn.error"), TestClient(app):
        pass
    assert "rf, train 2026-10-31T05:00:00+00:00, 20 rep" in caplog.text
    monkeypatch.delenv("FORMCOACH_MODEL_PATH")
    caplog.clear()
    with caplog.at_level("INFO", logger="uvicorn.error"), TestClient(app):
        pass
    assert "chưa nạp" in caplog.text


def test_without_model_path_startup_does_not_train(env: Path, monkeypatch) -> None:
    # Không đặt biến: khởi động không đọc data/ (vẫn train lúc cần, như trước D1b).
    monkeypatch.delenv("FORMCOACH_MODEL_PATH", raising=False)
    with TestClient(app) as client:
        assert client.get("/api/exercises/pushup").status_code == 200
