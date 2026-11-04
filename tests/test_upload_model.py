"""tools/upload_model.py: kiểm tra file trước khi tải, ghi đè, không in mật khẩu DB."""

from datetime import datetime
from pathlib import Path

import pytest
import sklearn

from backend.db import connect
from formcoach.dataset import Dataset, RepRow
from formcoach.exercises import get_exercise
from formcoach.models.store import ModelFileError, ModelInfo, save_model
from formcoach.models.train import train_classifier
from tools.upload_model import main, upload

NOW = datetime(2026, 10, 31, 12, 0)


def _model_file(path: Path, trained_at: str = "2026-10-31T05:00:00+00:00", **info: object) -> Path:
    rows = [
        RepRow("s", NOW, i, 0.0, 1.0, {"min_elbow_angle": 80.0 + 5 * i}, frozenset())
        for i in range(8)
    ]
    classifier, _ = train_classifier(
        "rules", get_exercise("pushup"), Dataset("pushup", (), tuple(rows), ())
    )
    base = {
        "model_name": "rules",
        "exercise": "pushup",
        "n_reps": 8,
        "trained_at": trained_at,
        "sklearn_version": sklearn.__version__,
    }
    save_model(path, classifier, ModelInfo(**{**base, **info}))
    return path


def _rows() -> list[dict]:
    with connect() as c:
        return c.execute("SELECT exercise, model_name, trained_at, data FROM models").fetchall()


def test_upload_stores_file_bytes(tmp_path: Path, pg_database: str) -> None:
    path = _model_file(tmp_path / "m.pkl")
    with connect() as c:
        info = upload(c, path, "pushup")
    [row] = _rows()
    assert info.n_reps == 8
    assert (row["exercise"], row["model_name"]) == ("pushup", "rules")
    assert bytes(row["data"]) == path.read_bytes()  # nguyên văn file


def test_upload_again_overwrites(tmp_path: Path, pg_database: str) -> None:
    with connect() as c:
        upload(c, _model_file(tmp_path / "a.pkl", "2026-10-20T00:00:00+00:00"), "pushup")
        upload(c, _model_file(tmp_path / "b.pkl", "2026-10-31T00:00:00+00:00"), "pushup")
    assert [r["trained_at"] for r in _rows()] == ["2026-10-31T00:00:00+00:00"]


def test_bad_file_is_not_uploaded(tmp_path: Path, pg_database: str) -> None:
    path = _model_file(tmp_path / "m.pkl", sklearn_version="0.0.1")
    with connect() as c, pytest.raises(ModelFileError):
        upload(c, path, "pushup")
    assert _rows() == []


def test_main_prints_host_not_password(
    tmp_path: Path, pg_database: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(_model_file(tmp_path / "m.pkl"))]) == 0
    out = capsys.readouterr().out
    assert "Đã tải mô hình pushup lên 127.0.0.1/formcoach" in out
    assert "password" not in out and ":formcoach@" not in out


def test_main_reports_missing_file(tmp_path: Path, pg_database: str, capsys) -> None:
    assert main([str(tmp_path / "khong-co.pkl")]) == 1
    assert "không thấy file mô hình" in capsys.readouterr().err
