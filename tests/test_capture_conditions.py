import json
from pathlib import Path

import numpy as np
import pytest

from evaluation.capture_conditions import Condition, main, parse_condition
from tests.synthetic import make_session


@pytest.mark.parametrize(
    ("notes", "expected"),
    [
        ("ao:khong goc:0 rep:10", Condition(False, 0, 10)),
        ("goc:20 ao:co", Condition(True, 20, None)),  # thứ tự tuỳ ý, rep tuỳ chọn
        ("tối, đèn trần · ao:co goc:40 rep:8", Condition(True, 40, 8)),  # lẫn chữ khác
    ],
)
def test_parse_condition(notes: str, expected: Condition) -> None:
    assert parse_condition(notes) == expected


@pytest.mark.parametrize("notes", ["", "tối, áo đen", "ao:co", "goc:20", "ao:co goc:abc"])
def test_parse_condition_not_experiment(notes: str) -> None:
    assert parse_condition(notes) is None


def _write(data: Path, session_id: str, notes: str, bottom: float, set_errors=()) -> None:
    """Hiệp tổng hợp 3 rep, đáy góc khuỷu = bottom (luật: shallow khi > 67°)."""
    t = np.arange(int(2.4 * 30)) / 30
    mid, amp = (165 + bottom) / 2, (165 - bottom) / 2
    rep = mid + amp * np.cos(2 * np.pi * t / 2.4)
    elbow = np.concatenate([np.full(30, 165.0), rep, rep, rep, np.full(30, 165.0)])
    s = make_session(elbow, 5.0)
    s["session_id"], s["notes"], s["set_errors"] = session_id, notes, list(set_errors)
    folder = data / "sessions" / "pushup"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{session_id}.json").write_text(json.dumps(s), encoding="utf-8")


def test_report_counts_false_alarms_per_condition(tmp_path: Path, capsys) -> None:
    data = tmp_path / "data"
    _write(data, "a_pushup", "ao:khong goc:0 rep:3", bottom=50)  # đủ sâu: luật không báo
    _write(data, "b_pushup", "ao:co goc:20 rep:3", bottom=100)  # "lệch" thành nông: báo nhầm
    _write(data, "c_pushup", "tối, áo đen", bottom=100)  # không phải hiệp thí nghiệm
    _write(data, "d_pushup", "ao:co goc:20", bottom=100, set_errors=("shallow",))  # có lỗi cố ý
    main(["--data", str(data), "--model", "rf"])  # chưa có nhãn → lùi luật
    out = capsys.readouterr().out
    assert "Mô hình: rules" in out
    assert "cởi trần, 0°: 1 hiệp, 3 rep" in out
    assert "mặc áo, 20°: 1 hiệp, 3 rep" in out  # chỉ b, không tính c và d
    assert "[rules] báo ≥1 lỗi: 0/3" in out
    assert "[rules] báo ≥1 lỗi: 3/3" in out and "shallow 3/3" in out
    assert "bộ đếm (đếm được/thật sự tập): 3/3" in out
    assert "min_elbow_angle" in out and "(lệch " in out  # có độ lệch so với chuẩn


def test_report_without_experiments(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "data", "c_pushup", "tối", bottom=100)
    main(["--data", str(tmp_path / "data")])
    assert "Chưa có hiệp thí nghiệm nào" in capsys.readouterr().out
