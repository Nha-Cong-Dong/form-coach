from datetime import datetime
from pathlib import Path

import pytest

from evaluation.dataset_report import main as report_main
from evaluation.split import (
    PILOT_SESSIONS,
    error_counts,
    evaluation_rows,
    group_keys,
    is_pilot,
    leave_one_group_out,
    missing_errors,
)
from formcoach.dataset import Dataset, RepRow
from tests.test_dataset import add_session

ERRORS = ("shallow", "hip_high")


def row(sid: str, at: str, errors: tuple[str, ...] = (), index: int = 0) -> RepRow:
    return RepRow(
        session_id=sid,
        recorded_at=datetime.fromisoformat(at),
        rep_index=index,
        start_s=0.0,
        end_s=1.0,
        features={},
        errors=frozenset(errors),
    )


# --- loại hiệp quay thử ---


def test_pilot_by_list_and_by_date() -> None:
    assert is_pilot(row("2026-10-20T10-14-01_pushup", "2026-10-20T10:14:01+07:00"))
    # Quên ghi vào danh sách nhưng quay trước ngày bắt đầu dataset → vẫn là quay thử.
    assert is_pilot(row("forgotten_pushup", "2026-10-18T09:00:00+07:00"))
    assert not is_pilot(row("x_pushup", "2026-10-21T08:00:00+07:00"))


def test_pilot_list_covers_known_trial_sessions() -> None:
    assert len(PILOT_SESSIONS) == 7


def test_evaluation_rows_never_contain_pilot() -> None:
    rows = (
        row("2026-10-20T10-16-09_pushup", "2026-10-20T10:16:09+07:00"),
        row("a_pushup", "2026-10-21T08:00:00+07:00"),
    )
    ds = Dataset("pushup", ERRORS, rows, ())
    assert [r.session_id for r in evaluation_rows(ds)] == ["a_pushup"]


# --- nhóm ---


def test_group_by_day() -> None:
    rows = [row("a", "2026-10-21T08:00:00+07:00"), row("b", "2026-10-21T20:00:00+07:00"),
            row("c", "2026-10-22T08:00:00+07:00")]  # fmt: skip
    assert group_keys(rows, "day") == ["2026-10-21", "2026-10-21", "2026-10-22"]


def test_group_by_block_splits_on_one_hour_gap() -> None:
    rows = [
        row("a", "2026-10-21T08:00:00+07:00"),
        row("a", "2026-10-21T08:00:00+07:00", index=1),  # cùng hiệp → cùng nhóm
        row("b", "2026-10-21T08:10:00+07:00"),  # cách 10 phút: cùng buổi
        row("c", "2026-10-21T09:30:00+07:00"),  # cách 80 phút: buổi mới
        row("d", "2026-10-22T08:00:00+07:00"),  # ngày mới: đánh số lại
    ]
    assert group_keys(rows, "block") == [
        "2026-10-21#1", "2026-10-21#1", "2026-10-21#1", "2026-10-21#2", "2026-10-22#1"
    ]  # fmt: skip


def test_group_mode_unknown() -> None:
    with pytest.raises(ValueError):
        group_keys([], "week")  # type: ignore[arg-type]


# --- kiểm định chéo bỏ ra một nhóm ---

GROUPS = ["d2", "d1", "d1", "d3", "d2", "d3", "d1"]


def test_each_group_is_test_exactly_once() -> None:
    folds = leave_one_group_out(GROUPS)
    assert [f.test_group for f in folds] == ["d1", "d2", "d3"]  # thứ tự cố định


def test_no_group_on_both_sides_and_nothing_lost() -> None:
    for f in leave_one_group_out(GROUPS):
        test_groups = {GROUPS[i] for i in f.test}
        train_groups = {GROUPS[i] for i in f.train}
        assert test_groups == {f.test_group}
        assert f.test_group not in train_groups  # không rò rỉ
        assert sorted(f.train + f.test) == list(range(len(GROUPS)))


def test_deterministic() -> None:
    assert leave_one_group_out(GROUPS) == leave_one_group_out(list(GROUPS))


def test_needs_two_groups() -> None:
    with pytest.raises(ValueError, match="ít nhất 2 nhóm"):
        leave_one_group_out(["d1", "d1"])


# --- thống kê ---


def test_error_counts_and_missing_warnings() -> None:
    rows = [row("a", "2026-10-21T08:00:00+07:00", ("shallow",)),
            row("b", "2026-10-21T09:00:00+07:00", ("shallow", "hip_high")),
            row("c", "2026-10-22T08:00:00+07:00")]  # fmt: skip
    counts = error_counts(rows, group_keys(rows, "day"), ERRORS)
    assert counts == {
        "2026-10-21": {"reps": 2, "shallow": 2, "hip_high": 1},
        "2026-10-22": {"reps": 1, "shallow": 0, "hip_high": 0},
    }
    assert missing_errors(counts, ERRORS) == [
        "2026-10-22: không có rep shallow",
        "2026-10-22: không có rep hip_high",
    ]


def test_report_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    add_session(tmp_path, "2026-10-20T10-14-01_pushup", "2026-10-20T10:14:01+07:00")  # quay thử
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00", ("shallow",))
    add_session(tmp_path, "b_pushup", "2026-10-22T08:00:00+07:00")
    report_main(["--data", str(tmp_path), "--out", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert "9 rep hợp lệ đã gán nhãn (3 rep quay thử)" in out
    assert "Dùng để chấm điểm: 6 rep" in out
    assert "test 2026-10-21: 3 rep | train 3 rep" in out
    assert "CẢNH BÁO 2026-10-22: không có rep shallow" in out
    assert (tmp_path / "out" / "dataset_pushup.csv").exists()
