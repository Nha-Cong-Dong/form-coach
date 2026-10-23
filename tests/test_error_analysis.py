from datetime import datetime
from pathlib import Path

import pytest

from evaluation.error_analysis import (
    analyze_error,
    list_cases,
    outcomes,
    session_kind,
)
from evaluation.error_analysis import main as analysis_main
from formcoach.dataset import RepRow
from formcoach.exercises import ErrorRule
from tests.test_dataset import add_session

RULE = ErrorRule("min_elbow_angle", ">", 67.0)  # shallow: chưa xuống dưới 67°


def row(sid: str, elbow: float | None, errors=(), set_errors=(), index: int = 0) -> RepRow:
    return RepRow(
        session_id=sid,
        recorded_at=datetime(2026, 10, 21, 8, 0),
        rep_index=index,
        start_s=0.0,
        end_s=1.0,
        features={} if elbow is None else {"min_elbow_angle": elbow},
        errors=frozenset(errors),
        set_errors=frozenset(set_errors),
    )


ROWS = [
    row("a", 80, ("shallow",), ("shallow",)),  # TP
    row("a", 60, ("shallow",), ("shallow",), 1),  # FN (làm nông nhưng vẫn xuống 60°)
    row("b", 75, (), (), 0),  # FP: tập đúng mà luật báo
    row("b", 55, (), (), 1),  # TN
    row("c", None, ("shallow",), ("shallow",)),  # thiếu đặc trưng: luật không báo → FN
]


def test_outcomes_classify_each_row() -> None:
    out = outcomes(ROWS, "shallow", RULE)
    assert out == {"tp": [0], "fp": [2], "fn": [1, 4], "tn": [3]}


def test_threshold_is_strict_in_analysis_too() -> None:
    assert outcomes([row("a", 67.0)], "shallow", RULE)["fp"] == []  # đúng bằng ngưỡng: không báo


def test_session_kind_names_the_intended_errors() -> None:
    assert session_kind(row("a", 80)) == "tập đúng"
    assert session_kind(row("a", 80, set_errors=("shallow", "neck_drop"))) == "neck_drop+shallow"


def test_summary_groups_false_alarms_and_misses() -> None:
    groups = ["g1", "g1", "g2", "g2", "g2"]
    text = analyze_error(ROWS, groups, "shallow", RULE)
    assert "TP 1  FP 1  FN 2  TN 1" in text
    assert "Báo nhầm (1) theo loại hiệp: tập đúng 1" in text
    assert "Bỏ sót (2) theo loại hiệp: shallow 2" in text
    assert "theo nhóm: g2 1" in text  # báo nhầm duy nhất nằm ở nhóm g2
    assert "báo nhầm" in text and "+75.000" in text  # giá trị đặc trưng của rep báo nhầm


def test_list_shows_each_case_with_missing_feature() -> None:
    text = list_cases(ROWS, "shallow", RULE)
    assert "báo nhầm b rep 1 (tập đúng): min_elbow_angle = +75.000" in text
    assert "bỏ sót   a rep 2 (shallow): min_elbow_angle = +60.000" in text
    assert "bỏ sót   c rep 1 (shallow): min_elbow_angle = thiếu" in text


def test_main_end_to_end_skips_pilot_and_uses_set_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Hiệp tổng hợp: khuỷu xuống 70° > 67° → luật luôn báo shallow.
    add_session(tmp_path, "2026-10-20T10-14-01_pushup", "2026-10-20T10:14:01+07:00")  # quay thử
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00", ("shallow",))
    add_session(tmp_path, "b_pushup", "2026-10-22T08:00:00+07:00")
    analysis_main(["--data", str(tmp_path), "--list"])
    out = capsys.readouterr().out
    assert "6 rep, nhóm theo buổi" in out  # hiệp quay thử đã bị loại
    assert "Chỉ để hiểu, không chỉnh ngưỡng" in out
    assert "shallow  (min_elbow_angle > 67): TP 3  FP 3  FN 0  TN 0" in out
    assert "Báo nhầm (3) theo loại hiệp: tập đúng 3" in out
    assert "báo nhầm b_pushup rep 1 (tập đúng)" in out
    assert "2026-10-20T10-14-01_pushup" not in out
    # Lỗi chưa quay trong dữ liệu vẫn được liệt kê, không báo lỗi.
    assert "hip_sag  (max_hip_offset < -0.01): TP 0" in out
