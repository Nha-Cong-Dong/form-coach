import pytest

from evaluation.metrics import Confusion, confusion, exact_match, macro_f1, spread

S, H = "shallow", "hip_high"


def sets(*items: str) -> list[frozenset[str]]:
    """Chuỗi "S", "SH", "" → [{shallow}, {shallow, hip_high}, {}]."""
    return [frozenset({"S": S, "H": H}[c] for c in item) for item in items]


def test_confusion_counts() -> None:
    #           rep:   1    2    3   4    5
    y_true = sets("S", "S", "", "", "SH")
    y_pred = sets("S", "", "S", "", "H")
    assert confusion(y_true, y_pred, S) == Confusion(tp=1, fp=1, fn=2, tn=1)
    assert confusion(y_true, y_pred, H) == Confusion(tp=1, fp=0, fn=0, tn=4)


def test_precision_recall_f1_known_values() -> None:
    c = Confusion(tp=3, fp=1, fn=2, tn=10)
    assert c.precision == pytest.approx(3 / 4)
    assert c.recall == pytest.approx(3 / 5)
    p, r = 3 / 4, 3 / 5
    assert c.f1 == pytest.approx(2 * p * r / (p + r))  # đúng là trung bình điều hoà


def test_undefined_is_none_not_zero_or_one() -> None:
    nothing = Confusion(tn=5)  # không có lỗi thật, không báo lần nào
    assert nothing.precision is None and nothing.recall is None and nothing.f1 is None


def test_false_alarms_without_positives_score_zero() -> None:
    # Buổi không có rep lỗi nhưng luật la oan 2 lần: phải bị phạt, không được bỏ qua.
    c = Confusion(fp=2, tn=3)
    assert c.recall is None and c.precision == 0.0 and c.f1 == 0.0


def test_missed_errors_without_predictions_score_zero() -> None:
    c = Confusion(fn=2, tn=3)
    assert c.precision is None and c.recall == 0.0 and c.f1 == 0.0


def test_confusions_add_up() -> None:
    assert Confusion(1, 2, 3, 4) + Confusion(10, 20, 30, 40) == Confusion(11, 22, 33, 44)


def test_lengths_must_match() -> None:
    with pytest.raises(ValueError):
        confusion(sets("S"), sets("S", ""), S)


def test_exact_match_only_counts_considered_errors() -> None:
    y_true = sets("S", "SH", "")
    y_pred = sets("S", "S", "H")
    assert exact_match(y_true, y_pred, [S, H]) == pytest.approx(1 / 3)
    assert exact_match(y_true, y_pred, [S]) == 1.0  # bỏ qua hip_high
    assert exact_match([], [], [S]) is None


def test_macro_f1_is_unweighted_mean_and_skips_undefined() -> None:
    confusions = {
        S: Confusion(tp=9, fn=1, tn=90),  # lỗi phổ biến, F1 cao
        H: Confusion(tp=0, fn=1, tn=99),  # lỗi hiếm, bỏ sót hết → F1 = 0
        "neck_drop": Confusion(tn=100),  # không xác định → bỏ
    }
    f1_s = confusions[S].f1
    assert macro_f1(confusions, [S, H, "neck_drop"]) == pytest.approx((f1_s + 0.0) / 2)
    assert macro_f1(confusions, ["neck_drop"]) is None


def test_spread_skips_none_and_counts_it() -> None:
    s = spread([0.5, None, 1.0])
    assert s.mean == pytest.approx(0.75)
    assert s.std == pytest.approx(0.3536, abs=1e-3)  # độ lệch chuẩn mẫu
    assert (s.n, s.skipped) == (2, 1)
    assert str(s) == "0.75 ± 0.35 [2/3]"
    assert spread([0.4]).std is None
    assert str(spread([None, None])) == "—"
