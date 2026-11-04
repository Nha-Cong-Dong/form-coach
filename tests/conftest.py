"""Fixture dùng chung cho các test."""

import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest

# Postgres cho test (docs/plans/postgres-neon.md: container Docker formcoach-pg ở máy). Đổi bằng
# FORMCOACH_TEST_DATABASE_URL. KHÔNG dùng FORMCOACH_DATABASE_URL: test tạo/xoá bảng, không được
# đụng DB thật (kể cả khi terminal đã `source .env`).
TEST_DATABASE_URL = os.environ.get(
    "FORMCOACH_TEST_DATABASE_URL", "postgresql://formcoach:formcoach@127.0.0.1:5432/formcoach"
)
_pg_unavailable: str | None = None  # lý do bỏ qua, nhớ lại để không thử kết nối lại mỗi test


@pytest.fixture
def pg_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Một DB sạch cho mỗi test: schema Postgres riêng (test_<ngẫu nhiên>), xoá khi test xong.

    Schema = một "thư mục" bảng trong cùng DB; `search_path` trong địa chỉ kết nối bảo Postgres
    tạo/tìm bảng trong schema đó. Nhanh hơn tạo cả database mới cho mỗi test.
    Chưa bật Postgres → test bỏ qua (skip) kèm lý do, như test web khi thiếu Node.
    """
    global _pg_unavailable
    import psycopg
    from psycopg.conninfo import make_conninfo

    from backend.db import close_pool

    if _pg_unavailable:
        pytest.skip(_pg_unavailable)
    try:
        admin = psycopg.connect(TEST_DATABASE_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as e:
        _pg_unavailable = f"không kết nối được Postgres cho test ({TEST_DATABASE_URL}): {e}"
        pytest.skip(_pg_unavailable)
    schema = f"test_{uuid.uuid4().hex[:12]}"
    admin.execute(f'CREATE SCHEMA "{schema}"')
    url = make_conninfo(TEST_DATABASE_URL, options=f"-c search_path={schema}")
    monkeypatch.setenv("FORMCOACH_DATABASE_URL", url)
    try:
        yield url
    finally:
        close_pool()
        admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        admin.close()


@pytest.fixture
def make_video(tmp_path: Path) -> Callable[..., Path]:
    """Tạo video tổng hợp trong tmp_path: một chấm trắng chạy ngang trên nền xám, 24 fps."""
    import cv2

    def _make(name: str = "v.mp4", n_frames: int = 12, size: tuple[int, int] = (64, 48)) -> Path:
        w, h = size
        path = tmp_path / name
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (w, h))
        for i in range(n_frames):
            frame = np.full((h, w, 3), 80, np.uint8)
            cv2.circle(frame, (4 * i % w, h // 2), 3, (255, 255, 255), -1)
            writer.write(frame)
        writer.release()
        return path

    return _make


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test không bao giờ gọi Claude thật, kể cả khi terminal đang có key của cổng LLM."""
    from backend.coach_llm import llm_coach

    monkeypatch.delenv("FORMCOACH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("FORMCOACH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("FORMCOACH_LLM_MODEL", raising=False)
    llm_coach.cache_clear()
