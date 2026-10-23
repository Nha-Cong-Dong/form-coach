import json
from datetime import datetime
from pathlib import Path

import pytest

from evaluation.audit_sample import (
    CATEGORIES,
    SampleItem,
    build_sample,
    format_result,
    score,
)
from evaluation.audit_sample import main as audit_main
from formcoach.dataset import RepRow
from formcoach.exercises import ErrorRule
from tests.test_dataset import add_session

RULE = ErrorRule("min_elbow_angle", ">", 67.0)


def row(i: int, elbow: float, labeled: bool) -> RepRow:
    return RepRow(
        session_id=f"s{i // 4}",
        recorded_at=datetime(2026, 10, 21, 8, 0),
        rep_index=i % 4,
        start_s=0.0,
        end_s=1.0,
        features={"min_elbow_angle": elbow},
        errors=frozenset({"shallow"} if labeled else ()),
    )


# 8 rep mỗi loại: TP (nhãn có, luật báo), FP, FN, TN.
ROWS = (
    [row(i, 80, True) for i in range(0, 8)]  # TP
    + [row(i, 80, False) for i in range(8, 16)]  # FP
    + [row(i, 50, True) for i in range(16, 24)]  # FN
    + [row(i, 50, False) for i in range(24, 32)]  # TN
)


def test_sample_takes_requested_counts_per_category() -> None:
    items = build_sample(ROWS, "shallow", RULE, {"fp": 4, "tn": 2, "tp": 2, "fn": 1})
    counts = {c: sum(i.category == c for i in items) for c in CATEGORIES}
    assert counts == {"fp": 4, "tn": 2, "tp": 2, "fn": 1}
    assert [i.position for i in items] == list(range(1, 10))


def test_sample_is_capped_by_available_reps() -> None:
    items = build_sample(ROWS, "shallow", RULE, {"fp": 50, "tn": 0, "tp": 0, "fn": 0})
    assert len(items) == 8


def test_sample_is_shuffled_and_reproducible() -> None:
    a = build_sample(ROWS, "shallow", RULE, seed=0)
    b = build_sample(ROWS, "shallow", RULE, seed=0)
    c = build_sample(ROWS, "shallow", RULE, seed=1)
    assert a == b and a != c
    # Không xếp theo loại: nếu không, người xem đoán được loại từ vị trí.
    order = [i.category for i in a]
    assert order != sorted(order) and order != sorted(order, reverse=True)


def test_sample_items_point_to_the_right_rows() -> None:
    items = build_sample(ROWS, "shallow", RULE, {"fp": 8, "tn": 0, "tp": 0, "fn": 0})
    assert {(i.session_id, i.rep_index) for i in items} == {
        (f"s{i // 4}", i % 4) for i in range(8, 16)
    }


def test_score_counts_answers_per_category() -> None:
    items = [SampleItem(1, "a", 0, "fp"), SampleItem(2, "a", 1, "fp"), SampleItem(3, "b", 0, "tn"),
             SampleItem(4, "b", 1, "tp")]  # fmt: skip
    result = score(items, "YnU y".replace(" ", ""))  # chữ hoa vẫn nhận
    assert result["fp"] == {"y": 1, "n": 1, "u": 0}
    assert result["tn"] == {"y": 0, "n": 0, "u": 1}
    assert result["tp"] == {"y": 1, "n": 0, "u": 0}


def test_score_rejects_wrong_length_and_symbols() -> None:
    items = [SampleItem(1, "a", 0, "fp"), SampleItem(2, "a", 1, "tn")]
    with pytest.raises(ValueError, match="cần 2"):
        score(items, "y")
    with pytest.raises(ValueError, match="chỉ gồm"):
        score(items, "yx")


def test_result_text_compares_flagged_with_control() -> None:
    items = [SampleItem(i, "a", i, c) for i, c in enumerate(["fp"] * 4 + ["tn"] * 2, start=1)]
    text = format_result("shallow", score(items, "yyyn" + "nn"))
    assert "báo nhầm (luật báo, nhãn ghi không): 4 rep → có lỗi 3, không 1" in text
    assert "3/4 trông có lỗi thật" in text
    assert "đối chứng (không ai báo), 0/2 trông có lỗi" in text


def test_cli_hides_categories_and_scores_later(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Hiệp tổng hợp: khuỷu xuống 70° > 67° → luật luôn báo shallow.
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00", ("shallow",))  # TP
    add_session(tmp_path, "b_pushup", "2026-10-22T08:00:00+07:00")  # FP
    # Hiệp quay thử (ngưỡng được chọn từ nó) không được lọt vào mẫu.
    add_session(tmp_path, "2026-10-20T10-14-01_pushup", "2026-10-20T10:14:01+07:00", ("shallow",))
    out = tmp_path / "out"
    base = ["--error", "shallow", "--data", str(tmp_path), "--out", str(out)]
    audit_main(base)
    printed = capsys.readouterr().out
    assert "Mẫu 6 rep cho lỗi shallow" in printed
    assert "2026-10-20T10-14-01_pushup" not in printed
    # Danh sách không được lộ loại của rep.
    for word in ("báo nhầm", "đối chứng", "bỏ sót", "báo đúng"):
        assert word not in printed
    key = json.loads((out / "audit_shallow.json").read_text(encoding="utf-8"))
    assert {k["category"] for k in key} == {"tp", "fp"}  # tn/fn trống trong dữ liệu này

    audit_main([*base, "--answers", "yyyyyy"])
    result = capsys.readouterr().out
    assert "báo nhầm (luật báo, nhãn ghi không): 3 rep → có lỗi 3" in result
    assert "báo đúng (luật báo, nhãn ghi có): 3 rep → có lỗi 3" in result


def test_cli_refuses_to_overwrite_and_rejects_ruleless_error(tmp_path: Path) -> None:
    add_session(tmp_path, "a_pushup", "2026-10-21T08:00:00+07:00", ("shallow",))
    base = ["--data", str(tmp_path), "--out", str(tmp_path / "out")]
    audit_main(["--error", "shallow", *base])
    with pytest.raises(SystemExit, match="đã có mẫu"):
        audit_main(["--error", "shallow", *base])
    audit_main(["--error", "shallow", "--force", *base])  # --force thì được
    with pytest.raises(SystemExit, match="chưa có mẫu"):
        audit_main(["--error", "hip_high", "--answers", "y", *base])
