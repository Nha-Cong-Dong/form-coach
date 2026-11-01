"""D1a: lưu mô hình ra file / đọc lại (formcoach/models/store.py) và lệnh `formcoach train`."""

import pickle
from datetime import datetime
from pathlib import Path

import pytest
import sklearn

from formcoach.__main__ import main
from formcoach.dataset import Dataset, RepRow
from formcoach.exercises import get_exercise
from formcoach.models.store import ModelFileError, ModelInfo, load_model, save_model
from formcoach.models.train import train_classifier
from formcoach.types import Rep

PUSHUP = get_exercise("pushup")
NOW = datetime(2026, 10, 31, 12, 0)


def _dataset(n: int = 10) -> Dataset:
    # Tách được ở ~100°: rep sâu tốt, rep nông lỗi shallow (như tests/test_train.py).
    rows = [
        RepRow(f"s{i % 3}", NOW, i, 0.0, 1.0, {"min_elbow_angle": 80.0 + i}, frozenset())
        for i in range(n)
    ]
    rows += [
        RepRow(
            f"s{i % 3}",
            NOW,
            n + i,
            0.0,
            1.0,
            {"min_elbow_angle": 120.0 + i},
            frozenset({"shallow"}),
        )
        for i in range(n)
    ]
    return Dataset("pushup", tuple(PUSHUP.error_labels), tuple(rows), ())


def _info(**overrides: object) -> ModelInfo:
    base = {
        "model_name": "rf",
        "exercise": "pushup",
        "n_reps": 20,
        "trained_at": "2026-10-31T05:00:00+00:00",
        "sklearn_version": sklearn.__version__,
    }
    return ModelInfo(**{**base, **overrides})


REPS = [Rep(0, 0, 0, {"min_elbow_angle": 85.0}), Rep(1, 0, 0, {"min_elbow_angle": 125.0})]


def test_roundtrip_gives_same_predictions(tmp_path: Path) -> None:
    classifier, _ = train_classifier("rf", PUSHUP, _dataset())
    path = tmp_path / "sub" / "pushup-rf.pkl"  # thư mục chưa có: save_model tự tạo
    save_model(path, classifier, _info())
    loaded, info = load_model(path, "pushup")
    assert info == _info()
    before, after = classifier.predict(REPS), loaded.predict(REPS)
    assert [r.errors for r in after] == [r.errors for r in before]
    assert [r.scores for r in after] == [r.scores for r in before]
    assert "shallow" in after[1].errors and "shallow" not in after[0].errors
    assert not list(path.parent.glob("*.tmp"))  # không để lại file tạm


def test_wrong_exercise_is_rejected(tmp_path: Path) -> None:
    classifier, _ = train_classifier("rf", PUSHUP, _dataset())
    save_model(tmp_path / "m.pkl", classifier, _info())
    with pytest.raises(ModelFileError, match="squat"):
        load_model(tmp_path / "m.pkl", "squat")


def test_other_sklearn_version_is_rejected(tmp_path: Path) -> None:
    # Pickle của bản scikit-learn khác có thể đọc sai: phải báo, không âm thầm dùng.
    classifier, _ = train_classifier("rf", PUSHUP, _dataset())
    save_model(tmp_path / "m.pkl", classifier, _info(sklearn_version="0.0.1"))
    with pytest.raises(ModelFileError, match="0.0.1"):
        load_model(tmp_path / "m.pkl", "pushup")


def test_missing_garbage_and_foreign_files_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ModelFileError, match="không thấy"):
        load_model(tmp_path / "khong-co.pkl", "pushup")
    (tmp_path / "rac.pkl").write_bytes(b"khong phai pickle")
    with pytest.raises(ModelFileError, match="không đọc được"):
        load_model(tmp_path / "rac.pkl", "pushup")
    (tmp_path / "la.pkl").write_bytes(
        pickle.dumps({"x": 1})
    )  # pickle hợp lệ nhưng không phải của mình
    with pytest.raises(ModelFileError, match="không phải file mô hình"):
        load_model(tmp_path / "la.pkl", "pushup")


def test_cli_train_saves_loadable_model(tmp_path: Path, monkeypatch, capsys) -> None:
    # Không đọc data/ thật: thay build_dataset bằng dữ liệu tổng hợp.
    monkeypatch.setattr("formcoach.dataset.build_dataset", lambda data_dir, exercise: _dataset())
    out = tmp_path / "pushup-rf.pkl"
    main(["train", "--data", str(tmp_path), "--out", str(out)])
    classifier, info = load_model(out, "pushup")
    assert (info.model_name, info.n_reps) == ("rf", 20)
    assert "shallow" in classifier.predict(REPS)[1].errors
    assert "Không commit" in capsys.readouterr().out


def test_cli_train_refuses_to_save_rules_fallback(tmp_path: Path, monkeypatch) -> None:
    # Không có rep đã gán nhãn → train_classifier lùi về luật: không được lưu file đó dưới tên rf.
    empty = Dataset("pushup", tuple(PUSHUP.error_labels), (), ())
    monkeypatch.setattr("formcoach.dataset.build_dataset", lambda data_dir, exercise: empty)
    out = tmp_path / "pushup-rf.pkl"
    with pytest.raises(SystemExit):
        main(["train", "--data", str(tmp_path), "--out", str(out)])
    assert not out.exists()
