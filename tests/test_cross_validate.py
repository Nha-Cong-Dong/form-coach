from datetime import datetime
from pathlib import Path

import pytest

from evaluation.baseline import main as baseline_main
from evaluation.cross_validate import cross_validate
from formcoach.dataset import RepRow
from formcoach.models.base import FormClassifier
from formcoach.types import Rep, RepResult
from tests.test_dataset import add_session


def row(group_day: int, errors: tuple[str, ...], elbow: float) -> RepRow:
    return RepRow(
        session_id=f"s{group_day}",
        recorded_at=datetime(2026, 10, 20 + group_day, 8, 0),
        rep_index=0,
        start_s=0.0,
        end_s=1.0,
        features={"min_elbow_angle": elbow},
        errors=frozenset(errors),
    )


ROWS = [row(1, ("shallow",), 80), row(1, (), 50), row(2, ("shallow",), 75), row(2, (), 45),
        row(3, (), 52), row(3, ("shallow",), 90)]  # fmt: skip
GROUPS = ["d1", "d1", "d2", "d2", "d3", "d3"]


class Spy(FormClassifier):
    """Ghi lại dòng nào được dùng để fit; dự đoán shallow khi min_elbow_angle > 67."""

    instances: list["Spy"] = []

    def __init__(self) -> None:
        self.fitted: list[int] = []
        Spy.instances.append(self)

    def fit(self, reps: list[Rep], errors: list[frozenset[str]]) -> None:
        self.fitted = [r.index for r in reps]

    def predict(self, reps: list[Rep]) -> list[RepResult]:
        return [
            RepResult(r, frozenset({"shallow"} if r.features["min_elbow_angle"] > 67 else ()), None)
            for r in reps
        ]


def test_no_test_row_is_ever_used_for_fit() -> None:
    Spy.instances = []
    results = cross_validate(Spy, ROWS, GROUPS)
    assert len(Spy.instances) == 3  # một model mới cho mỗi lần chia
    for model, res in zip(Spy.instances, results, strict=True):
        assert not set(model.fitted) & set(res.rows)  # không rò rỉ
        assert {GROUPS[i] for i in model.fitted} == set(GROUPS) - {res.test_group}


def test_every_row_predicted_exactly_once() -> None:
    results = cross_validate(Spy, ROWS, GROUPS)
    assert sorted(i for r in results for i in r.rows) == list(range(len(ROWS)))
    for r in results:
        assert list(r.y_true) == [ROWS[i].errors for i in r.rows]


def test_confusion_per_fold() -> None:
    results = cross_validate(Spy, ROWS, GROUPS)
    assert all(r.confusion("shallow").tp == 1 and r.confusion("shallow").fp == 0 for r in results)


def test_baseline_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # 2 ngày dataset (3 rep/hiệp, khuỷu xuống 70° > 67° → luật luôn báo shallow) + 1 hiệp quay thử.
    add_session(tmp_path, "2026-10-20T10-14-01_pushup", "2026-10-20T10:14:01+07:00")
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00", ("shallow",))
    add_session(tmp_path, "b_pushup", "2026-10-21T08:05:00+07:00")
    add_session(tmp_path, "c_pushup", "2026-10-22T08:00:00+07:00", ("shallow",))
    add_session(tmp_path, "d_pushup", "2026-10-22T08:10:00+07:00", label=False)
    baseline_main(["--data", str(tmp_path)])
    out = capsys.readouterr().out
    assert "bỏ qua d_pushup: chưa gán nhãn" in out  # không lặng lẽ chấm trên tập thiếu
    assert "9 rep, 2 lần chia" in out  # 3 hiệp × 3 rep; hiệp quay thử bị loại
    # shallow gộp: TP 6 (a, c), FP 3 (b) → precision 0,67, recall 1.
    line = next(x for x in out.splitlines() if x.strip().startswith("shallow"))
    assert line.split()[-4:] == ["6", "3", "0", "0"]
    assert "hip_sag" in out and "chưa có luật" in out
    assert "neck_drop" in out and "thử nghiệm" in out
    assert "test 2026-10-21: 6 rep" in out
    # Không có rep incomplete_lockout/hip_high và luật cũng không báo: macro-F1 lần chia đó chỉ
    # tính trên shallow, phải nói rõ.
    assert "(không tính incomplete_lockout, hip_high: không có rep lỗi, không báo)" in out


def test_baseline_not_enough_groups(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00")
    baseline_main(["--data", str(tmp_path)])
    assert "Chưa đủ dữ liệu" in capsys.readouterr().out
