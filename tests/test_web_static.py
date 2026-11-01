"""D1 bước 2: backend phục vụ web đã build (`mount_web` trong backend/app.py)."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import mount_web


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Form Coach</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def _app_with_api() -> FastAPI:
    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_serves_index_assets_and_keeps_api_first(tmp_path: Path) -> None:
    app = _app_with_api()
    assert mount_web(app, _dist(tmp_path)) is True
    client = TestClient(app)
    assert "Form Coach" in client.get("/").text  # trang chính; #history... do web tự xử lý
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/ping").json() == {"ok": True}  # API khớp trước phần web
    assert client.get("/khong-co.js").status_code == 404


def test_not_built_means_not_mounted(tmp_path: Path) -> None:
    # Máy dev chưa chạy npm run build: không gắn gì, API chạy như cũ.
    app = _app_with_api()
    assert mount_web(app, tmp_path / "chua-build") is False
    client = TestClient(app)
    assert client.get("/").status_code == 404
    assert client.get("/api/ping").status_code == 200
