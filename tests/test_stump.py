import math

import pytest

from formcoach.exercises import ErrorRule, Exercise, PushUp
from formcoach.models import LearnedThreshold, make_classifier
from formcoach.models.stump import MIN_POSITIVES, learn_threshold
from formcoach.types import Rep


def rep(i: int = 0, **features: float) -> Rep:
    return Rep(index=i, start_frame=0, end_frame=1, features=features)


# --- learn_threshold: đáp án biết trước ---


def test_separable_threshold_is_the_midpoint_of_the_gap() -> None:
    # Rep không lỗi ≤ 90, rep có lỗi ≥ 110: ngưỡng ở giữa khoảng trống = 100.
    values = [70.0, 80.0, 90.0, 110.0, 120.0, 130.0]
    labels = [False, False, False, True, True, True]
    assert learn_threshold(values, labels, ">") == 100.0


def test_direction_less_than_is_learned_in_the_right_place() -> None:
    values = [40.0, 50.0, 60.0, 140.0, 150.0, 160.0]
    labels = [True, True, True, False, False, False]  # lỗi khi giá trị NHỎ
    assert learn_threshold(values, labels, "<") == 100.0


def test_overlapping_case_matches_hand_computed_f1() -> None:
    # Giá trị 1..7; dương ở 3, 5, 6, 7. Ứng viên và F1 tính tay (lỗi khi > t):
    #   1,5: TP4 FP2 → 0,800 | 2,5: TP4 FP1 → 0,889 | 3,5: TP3 FP1 FN1 → 0,750
    #   4,5: TP3 FN1 → 0,857 | 5,5: TP2 FN2 → 0,667 | 6,5: TP1 FN3 → 0,400
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    labels = [False, False, True, False, True, True, True]
    assert learn_threshold(values, labels, ">") == 2.5


def test_tie_prefers_the_stricter_threshold_that_fires_less() -> None:
    # Giá trị 1..6, dương ở 1, 2, 5, 6. Ngưỡng 1,5 (báo 5 rep) và 4,5 (báo 2 rep) cùng F1 = 0,667.
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    labels = [True, True, False, False, True, True]
    assert learn_threshold(values, labels, ">") == 4.5
    # Chiều "<" là ảnh gương: cùng dữ liệu đổi dấu phải cho ngưỡng đối xứng.
    assert learn_threshold([-v for v in values], labels, "<") == -4.5


def test_not_enough_positives_or_no_split_returns_none() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert MIN_POSITIVES == 3
    assert learn_threshold(values, [False, False, True, True, False], ">") is None  # 2 dương
    assert learn_threshold([5.0] * 6, [True, True, True, False, False, False], ">") is None
    assert learn_threshold([], [], ">") is None


def test_nan_values_are_ignored() -> None:
    values = [math.nan, 70.0, 80.0, 90.0, 110.0, 120.0, 130.0, math.nan]
    labels = [True, False, False, False, True, True, True, False]
    assert learn_threshold(values, labels, ">") == 100.0  # NaN không làm lệch ngưỡng


def test_positives_without_a_measurement_do_not_count_toward_the_minimum() -> None:
    # 4 rep dương nhưng 2 trong số đó không có số đo: chỉ 2 rep dương dùng được < 3 → không học.
    values = [math.nan, math.nan, 70.0, 80.0, 110.0, 120.0]
    labels = [True, True, False, False, True, True]
    assert learn_threshold(values, labels, ">") is None


def test_learn_threshold_is_deterministic() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    labels = [True, True, False, False, True, True]
    assert learn_threshold(values, labels, ">") == learn_threshold(values, labels, ">")


# --- LearnedThreshold ---


class OneErrorExercise(Exercise):
    """Bài tập giả: lỗi `deep` khi `x > ngưỡng tay`, lỗi `lazy` chưa có luật."""

    name = "fake"
    error_labels = ["deep", "lazy"]

    def angle_definitions(self) -> dict[str, tuple[str, str, str]]:
        return {"a": ("p", "q", "r")}

    def primary_signal(self) -> str:
        return "a"

    def phase_thresholds(self) -> dict[str, float]:
        return {}

    def error_rules(self) -> dict[str, ErrorRule | None]:
        return {"deep": ErrorRule("x", ">", 5.0), "lazy": None}


def test_fit_learns_threshold_and_predict_uses_it() -> None:
    reps = [rep(i, x=v) for i, v in enumerate([70.0, 80.0, 90.0, 110.0, 120.0, 130.0])]
    errors = [frozenset()] * 3 + [frozenset({"deep"})] * 3
    model = LearnedThreshold(OneErrorExercise())
    model.fit(reps, errors)
    assert model.thresholds_ == {"deep": 100.0}  # học được 100, không dùng 5 của luật tay
    results = model.predict([rep(0, x=99.0), rep(1, x=101.0), rep(2, x=500.0)])
    assert [r.errors for r in results] == [frozenset(), frozenset({"deep"}), frozenset({"deep"})]
    assert all(r.scores is None for r in results)


def test_error_without_rule_is_never_predicted_and_is_reported() -> None:
    model = LearnedThreshold(OneErrorExercise())
    assert model.missing == ["lazy"]
    reps = [rep(i, x=v) for i, v in enumerate([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])]
    model.fit(reps, [frozenset({"lazy"})] * 6)  # nhãn lazy có nhưng không có luật để học
    assert "lazy" not in model.thresholds_
    assert all("lazy" not in r.errors for r in model.predict(reps))


def test_few_positives_means_never_fires() -> None:
    reps = [rep(i, x=float(i)) for i in range(8)]
    model = LearnedThreshold(OneErrorExercise())
    model.fit(reps, [frozenset({"deep"})] * 2 + [frozenset()] * 6)  # chỉ 2 rep dương
    assert model.thresholds_ == {"deep": None}
    assert all(not r.errors for r in model.predict(reps))


def test_missing_or_nan_feature_does_not_fire_and_is_skipped_in_fit() -> None:
    reps = [
        rep(0, x=math.nan),
        rep(1),
        *[rep(i, x=v) for i, v in enumerate([70.0, 80.0, 90.0, 110.0, 120.0, 130.0], 2)],
    ]
    errors = (
        [frozenset({"deep"}), frozenset({"deep"})] + [frozenset()] * 3 + [frozenset({"deep"})] * 3
    )
    model = LearnedThreshold(OneErrorExercise())
    model.fit(reps, errors)
    assert model.thresholds_["deep"] == 100.0
    assert [r.errors for r in model.predict([rep(0), rep(1, x=math.nan)])] == [frozenset()] * 2


def test_predict_before_fit_raises_and_refit_resets() -> None:
    model = LearnedThreshold(OneErrorExercise())
    with pytest.raises(RuntimeError, match="chưa fit"):
        model.predict([rep(0, x=1.0)])
    xs = [70.0, 80.0, 90.0, 110.0, 120.0, 130.0]
    reps = [rep(i, x=v) for i, v in enumerate(xs)]
    model.fit(reps, [frozenset()] * 3 + [frozenset({"deep"})] * 3)
    first = dict(model.thresholds_)
    model.fit(reps, [frozenset({"deep"})] * 3 + [frozenset()] * 3)  # nhãn đảo → ngưỡng học khác
    assert model.thresholds_ != first


def test_predict_keeps_order() -> None:
    model = LearnedThreshold(OneErrorExercise())
    xs = [70.0, 80.0, 90.0, 110.0, 120.0, 130.0]
    model.fit(
        [rep(i, x=v) for i, v in enumerate(xs)], [frozenset()] * 3 + [frozenset({"deep"})] * 3
    )
    reps = [rep(7, x=200.0), rep(3, x=0.0), rep(5, x=150.0)]
    assert [r.rep.index for r in model.predict(reps)] == [7, 3, 5]


def test_registry_and_pushup_thresholds_start_from_the_rule_features() -> None:
    model = make_classifier("stump", PushUp())
    assert isinstance(model, LearnedThreshold) and model.missing == []


def test_skipped_lists_errors_whose_threshold_could_not_be_learned() -> None:
    # Chỉ shallow có đủ rep dương; các lỗi còn lại có luật nhưng không học được → skipped_.
    reps = [rep(i, min_elbow_angle=60.0 + 10 * (i % 4)) for i in range(12)]
    errors = [frozenset({"shallow"}) if i % 4 >= 2 else frozenset() for i in range(12)]
    model = LearnedThreshold(PushUp())
    model.fit(reps, errors)
    assert model.thresholds_["shallow"] is not None
    assert "shallow" not in model.skipped_
    assert {"incomplete_lockout", "hip_high", "hip_sag"} <= set(model.skipped_)
