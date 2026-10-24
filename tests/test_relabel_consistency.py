import random
from datetime import datetime

import pytest

from evaluation.relabel_consistency import (
    Item,
    audit_hash,
    bootstrap_kappa,
    cohen_kappa,
    draw_sample,
    parse_answers,
    score,
)
from formcoach.dataset import RepRow

LABELS = ["shallow", "incomplete_lockout", "hip_sag", "hip_high", "neck_drop"]
MAIN = ("shallow", "incomplete_lockout", "hip_high", "hip_sag")


# --- Cohen's kappa ---


def test_kappa_identical_is_one() -> None:
    a = [True, False, True, False, False]
    assert cohen_kappa(a, a) == pytest.approx(1.0)


def test_kappa_hand_computed() -> None:
    # p_o = 3/4; tỉ lệ "có": 1/2 và 1/4 → p_e = 1/2·1/4 + 1/2·3/4 = 1/2; kappa = (0,75−0,5)/0,5.
    assert cohen_kappa([True, True, False, False], [True, False, False, False]) == pytest.approx(
        0.5
    )


def test_kappa_opposite_is_negative() -> None:
    assert cohen_kappa([True, False, True, False], [False, True, False, True]) == pytest.approx(-1)


def test_kappa_undefined_when_nothing_to_tell_apart() -> None:
    # Cả hai lần đều toàn "không": khớp 100% nhưng không đo được gì.
    assert cohen_kappa([False] * 5, [False] * 5) is None
    assert cohen_kappa([], []) is None


def test_kappa_independent_random_is_near_zero() -> None:
    rng = random.Random(1)
    a = [rng.random() < 0.3 for _ in range(5000)]
    b = [rng.random() < 0.3 for _ in range(5000)]
    assert abs(cohen_kappa(a, b)) < 0.05


def test_bootstrap_identical_is_one_one() -> None:
    a = [True, False] * 10
    assert bootstrap_kappa(a, a) == pytest.approx((1.0, 1.0))


def test_bootstrap_contains_point_estimate() -> None:
    rng = random.Random(2)
    a = [rng.random() < 0.4 for _ in range(30)]
    b = [x if rng.random() < 0.8 else not x for x in a]
    lo, hi = bootstrap_kappa(a, b)
    assert lo <= cohen_kappa(a, b) <= hi


# --- đáp án ---


def test_parse_answers() -> None:
    got = parse_answers("0, 13 ,x,5", 4, LABELS)
    assert got == [frozenset(), frozenset({"shallow", "hip_sag"}), None, frozenset({"neck_drop"})]


@pytest.mark.parametrize(
    ("text", "match"),
    [("0,1", "cần 3"), ("0,1,a", "không hợp lệ"), ("0,1,6", "số 6"), ("0,1,", "không hợp lệ")],
)
def test_parse_answers_rejects_bad_input(text: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        parse_answers(text, 3, LABELS)


# --- chấm ---


def _item(errors: set[str], i: int = 0) -> Item:
    return Item(f"s{i}", i, frozenset(errors))


def test_score_counts_and_skips_not_rep() -> None:
    items = [_item({"shallow"}, 0), _item(set(), 1), _item({"hip_sag"}, 2), _item(set(), 3)]
    answers = [frozenset({"shallow"}), frozenset({"hip_sag"}), frozenset({"hip_sag"}), None]
    r = score(items, answers, LABELS, MAIN)
    assert r["n_items"] == 4 and r["n_not_rep"] == 1
    # 3 rep được so: rep 0 và 2 khớp hoàn toàn, rep 1 lần 2 thêm hip_sag.
    assert r["exact_all"] == pytest.approx(2 / 3)
    assert r["per_error"]["shallow"]["agreement"] == pytest.approx(1.0)
    assert r["per_error"]["hip_sag"]["pos_first"] == 1
    assert r["per_error"]["hip_sag"]["pos_second"] == 2
    assert r["per_error"]["hip_sag"]["agreement"] == pytest.approx(2 / 3)
    assert r["per_error"]["hip_high"]["kappa"] is None  # không rep nào có lỗi ở cả hai lần


def test_exact_main_ignores_experimental_error() -> None:
    items = [_item({"neck_drop"}, 0)]
    r = score(items, [frozenset()], LABELS, MAIN)
    assert r["exact_all"] == 0 and r["exact_main"] == 1


# --- lấy mẫu ---


def _row(i: int) -> RepRow:
    return RepRow(f"s{i // 5}", datetime(2026, 10, 21), i % 5, 0.0, 1.0, {}, frozenset())


def test_sample_deterministic_without_repeats() -> None:
    rows = [_row(i) for i in range(50)]
    a, b = draw_sample(rows, 30, seed=0), draw_sample(rows, 30, seed=0)
    assert a == b and len({(r.session_id, r.rep_index) for r in a}) == 30
    assert draw_sample(rows, 30, seed=1) != a


def test_sample_too_large_raises() -> None:
    with pytest.raises(ValueError):
        draw_sample([_row(0)], 2, seed=0)


def test_cli_sample_then_score(tmp_path, capsys) -> None:
    from evaluation.relabel_consistency import main
    from tests.test_dataset import add_session

    data, out = tmp_path / "data", tmp_path / "out"
    add_session(data, "a_pushup", set_errors=("shallow",))  # 3 rep, nhãn shallow
    add_session(data, "b_pushup", recorded_at="2026-10-22T08:00:00+07:00")  # 3 rep, không lỗi
    main(["sample", "--data", str(data), "--out", str(out), "--n", "4"])
    printed = capsys.readouterr().out
    assert "#audit/" in printed and "shallow" not in printed  # link không lộ nhãn
    # Lấy mẫu lại khi đã có → từ chối (không chọn lại mẫu "dễ").
    with pytest.raises(SystemExit):
        main(["sample", "--data", str(data), "--out", str(out), "--n", "4"])

    # In lại link của mẫu đã có, không lộ nhãn.
    main(["link", "--out", str(out)])
    relinked = capsys.readouterr().out
    assert "#audit/" in relinked and "shallow" not in relinked

    import json

    key = json.loads((out / "relabel_pushup.json").read_text(encoding="utf-8"))
    # Gán lại y hệt lần 1 → khớp toàn bộ.
    same = ",".join("1" if it["errors"] == ["shallow"] else "0" for it in key["items"])
    main(["score", "--out", str(out), "--answers", same])
    assert "Khớp toàn bộ tập lỗi (4 lỗi chính): 1,00" in capsys.readouterr().out


def test_audit_hash_has_no_labels() -> None:
    h = audit_hash([Item("2026-10-21T08-00-00_pushup", 3, frozenset({"shallow"}))])
    assert h == "audit/2026-10-21T08-00-00_pushup~3"
    assert "shallow" not in h
