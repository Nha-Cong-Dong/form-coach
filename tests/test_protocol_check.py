from datetime import datetime
from pathlib import Path

import pytest

from evaluation.cross_validate import FoldResult
from evaluation.protocol_check import (
    follow_counts,
    predictions_by_row,
    protocol_report,
    split_by_protocol,
)
from evaluation.protocol_check import main as protocol_main
from formcoach.dataset import RepRow
from tests.test_dataset import add_session

MAIN = ("shallow", "hip_sag")


def fs(*names: str) -> frozenset[str]:
    return frozenset(names)


def rep(errors: frozenset[str], set_errors: frozenset[str]) -> RepRow:
    return RepRow("s", datetime(2026, 10, 21, 8, 0), 0, 0.0, 1.0, {}, errors, set_errors)


# 0, 1: nhãn = lỗi cố ý (A). 2: hiệp shallow nhưng rep tốt (B). 3: hiệp shallow, rep có thêm
# hip_sag (B). 4: lỗi thử nghiệm neck_drop không tính, nên vẫn là A.
ROWS = [
    rep(fs("shallow"), fs("shallow")),
    rep(fs(), fs()),
    rep(fs(), fs("shallow")),
    rep(fs("shallow", "hip_sag"), fs("shallow")),
    rep(fs("neck_drop"), fs()),
]


def test_split_uses_only_main_errors() -> None:
    assert split_by_protocol(ROWS, MAIN) == ([0, 1, 4], [2, 3])


def test_follow_counts_separates_script_followers_from_readers() -> None:
    truth = [r.errors for r in ROWS]
    script = [r.set_errors for r in ROWS]
    assert follow_counts(truth, ROWS, [2, 3], MAIN) == (2, 0, 0)  # đọc đúng nhãn thật
    assert follow_counts(script, ROWS, [2, 3], MAIN) == (0, 2, 0)  # theo đúng kịch bản
    assert follow_counts([fs("hip_sag")] * 5, ROWS, [2, 3], MAIN) == (0, 0, 2)  # khác cả hai
    # Lỗi ngoài `main` không làm đổi kết quả: đoán thêm neck_drop vẫn là "= nhãn thật".
    assert follow_counts([fs("neck_drop")] * 5, ROWS, [2], MAIN) == (1, 0, 0)


def test_report_counts_and_reference_row() -> None:
    truth = [r.errors for r in ROWS]
    out = protocol_report({"reader": truth, "follower": [r.set_errors for r in ROWS]}, ROWS, MAIN)
    assert "nhóm A (nhãn thật = lỗi cố ý) 3 rep" in out and "nhóm B" in out and "2 rep" in out
    row = {
        x.split()[0]: x.split()[1:] for x in out.splitlines() if x.startswith("  ") and x.split()
    }
    assert row["reader"][-3:] == ["2", "0", "0"]
    assert row["follower"][-3:] == ["0", "2", "0"]
    assert row["set-only"][-3:] == ["0", "2", "0"]  # mốc luôn theo kịch bản


def test_predictions_are_put_back_on_their_own_rows() -> None:
    results = [
        FoldResult("g1", (2, 0), (fs(), fs()), (fs("shallow"), fs("hip_sag"))),
        FoldResult("g2", (1,), (fs(),), (fs("neck_drop"),)),
    ]
    assert predictions_by_row(results, 3) == [fs("hip_sag"), fs("neck_drop"), fs("shallow")]
    with pytest.raises(ValueError):
        predictions_by_row(results, 4)  # dòng 3 chưa được dự đoán


def test_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00", ("shallow",))
    add_session(tmp_path, "b_pushup", "2026-10-21T14:00:00+07:00")
    add_session(tmp_path, "c_pushup", "2026-10-22T08:00:00+07:00", ("shallow",))
    protocol_main(["--data", str(tmp_path), "--models", "rules"])
    out = capsys.readouterr().out
    assert "9 rep, 3 lần chia" in out
    # Nhãn mặc định = lỗi cố ý, nên mọi rep ở nhóm A và nhóm B trống.
    assert "nhóm A (nhãn thật = lỗi cố ý) 9 rep" in out and "nhóm B (nhãn thật khác" in out
    assert "(0 rep)" in out
