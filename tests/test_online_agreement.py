import json
from pathlib import Path

import pytest

from evaluation.online_agreement import Agreement, main, report, summarize
from tests.synthetic import make_session
from tests.test_online import reps_signal


def _a(offline: int, online: int, sid: str = "s") -> Agreement:
    return Agreement(sid, offline, online, "left")


def test_summarize_counts_by_hand() -> None:
    # Lệch: 0, 0, +1, −1, +3 → khớp 2/5, ≤1: 4/5, |lệch| TB (0+0+1+1+3)/5 = 1,0; thừa 2, thiếu 1.
    s = summarize([_a(5, 5), _a(4, 4), _a(5, 6), _a(6, 5), _a(3, 6)])
    assert s == {
        "n": 5,
        "exact": pytest.approx(0.4),
        "within_one": pytest.approx(0.8),
        "mean_abs": pytest.approx(1.0),
        "over": 2,
        "under": 1,
    }
    assert summarize([]) == {"n": 0}


def test_report_lists_only_mismatches_unless_all() -> None:
    results = [_a(5, 5, "khop"), _a(6, 0, "lech")]
    text = report(results)
    assert "lech: cả hiệp 6, trực tiếp 0  <-- lệch -6 (bên left)" in text
    assert "khop:" not in text and "CHƯA ĐẠT" in text
    assert "khop: cả hiệp 5, trực tiếp 5" in report(results, show_all=True)
    assert "CHƯA ĐẠT" not in report([_a(5, 5), _a(5, 6)])  # lệch 1 vẫn đạt


def test_cli_on_synthetic_sessions(tmp_path: Path, capsys) -> None:
    folder = tmp_path / "sessions" / "pushup"
    folder.mkdir(parents=True)
    for i, n in enumerate([2, 3, 4]):
        s = make_session(reps_signal(n), 5.0)
        s["session_id"] = f"s{i}_pushup"
        (folder / f"s{i}_pushup.json").write_text(json.dumps(s), encoding="utf-8")
    main(["--data", str(tmp_path), "--all"])
    out = capsys.readouterr().out
    for i, n in enumerate([2, 3, 4]):
        assert f"s{i}_pushup: cả hiệp {n}, trực tiếp {n}" in out
    assert "3 hiệp: khớp 100%, lệch ≤ 1: 100%" in out
