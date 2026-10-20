import math

import pytest

from formcoach.exercises import ErrorRule, Exercise, PushUp
from formcoach.models import RuleBased
from formcoach.models.rule_based import rule_fires
from formcoach.types import Rep


class FakeExercise(Exercise):
    """Bài tập giả với luật giả: test không phụ thuộc ngưỡng thật của push-up."""

    name = "fake"
    error_labels = ["deep", "slow", "unmeasured"]

    def angle_definitions(self) -> dict[str, tuple[str, str, str]]:
        return {"knee_angle": ("hip", "knee", "ankle")}

    def primary_signal(self) -> str:
        return "knee_angle"

    def phase_thresholds(self) -> dict[str, float]:
        return {}

    def error_rules(self) -> dict[str, ErrorRule | None]:
        return {
            "deep": ErrorRule("min_knee_angle", "<", 60.0),
            "slow": ErrorRule("duration_s", ">", 3.0),
            "unmeasured": None,  # chưa có ngưỡng
        }


def rep(**features: float) -> Rep:
    return Rep(index=0, start_frame=0, end_frame=10, features=features)


def predict(*reps: Rep) -> list[frozenset[str]]:
    return [r.errors for r in RuleBased(FakeExercise()).predict(list(reps))]


def test_good_rep_has_no_errors() -> None:
    assert predict(rep(min_knee_angle=80.0, duration_s=2.0)) == [frozenset()]


@pytest.mark.parametrize(
    ("features", "expected"),
    [
        ({"min_knee_angle": 50.0, "duration_s": 2.0}, {"deep"}),
        ({"min_knee_angle": 80.0, "duration_s": 4.0}, {"slow"}),
        ({"min_knee_angle": 50.0, "duration_s": 4.0}, {"deep", "slow"}),  # nhiều lỗi cùng lúc
    ],
)
def test_each_rule_independent(features: dict[str, float], expected: set[str]) -> None:
    assert predict(rep(**features)) == [frozenset(expected)]


def test_threshold_is_strict() -> None:
    # Đúng bằng ngưỡng thì chưa phải lỗi ("<" và ">" là so sánh ngặt).
    assert predict(rep(min_knee_angle=60.0, duration_s=3.0)) == [frozenset()]


@pytest.mark.parametrize("value", [None, math.nan])
def test_missing_or_nan_feature_never_fires(value: float | None) -> None:
    features = (
        {"duration_s": 2.0} if value is None else {"min_knee_angle": value, "duration_s": 2.0}
    )
    assert predict(rep(**features)) == [frozenset()]


def test_error_without_rule_is_reported_not_predicted() -> None:
    model = RuleBased(FakeExercise())
    assert model.missing == ["unmeasured"]
    assert all("unmeasured" not in r.errors for r in model.predict([rep(min_knee_angle=10.0)]))


def test_keeps_order_and_scores_none() -> None:
    reps = [Rep(index=i, start_frame=i, end_frame=i + 1, features={"min_knee_angle": a})
            for i, a in enumerate([50.0, 80.0, 40.0])]  # fmt: skip
    results = RuleBased(FakeExercise()).predict(reps)
    assert [r.rep.index for r in results] == [0, 1, 2]
    assert [bool(r.errors) for r in results] == [True, False, True]
    assert all(r.scores is None for r in results)


def test_fit_does_nothing() -> None:
    model = RuleBased(FakeExercise())
    model.fit([rep(min_knee_angle=10.0)], [frozenset()])  # nhãn ngược với luật
    assert predict(rep(min_knee_angle=10.0)) == [frozenset({"deep"})]


def test_rule_for_unknown_error_is_rejected() -> None:
    class Broken(FakeExercise):
        def error_rules(self) -> dict[str, ErrorRule | None]:
            return {"good": ErrorRule("min_knee_angle", ">", 1.0)}

    with pytest.raises(ValueError, match="good"):
        RuleBased(Broken())


def test_rule_fires_compares_both_directions() -> None:
    assert rule_fires(ErrorRule("x", "<", 5.0), {"x": 4.0})
    assert not rule_fires(ErrorRule("x", "<", 5.0), {"x": 6.0})
    assert rule_fires(ErrorRule("x", ">", 5.0), {"x": 6.0})


def test_pushup_rules_use_features_the_segmenter_produces() -> None:
    # Tên đặc trưng sai chính tả → luật không bao giờ bắt lỗi mà không báo gì. Kiểm tra tên
    # có dạng mà RepSegmenter tạo ra: min_/max_/median_<tín hiệu> hoặc top_<tín hiệu chính>.
    ex = PushUp()
    signals = (
        set(ex.angle_definitions()) | set(ex.tilt_definitions()) | set(ex.offset_definitions())
    )
    produced = {f"{p}_{s}" for p in ("min", "max", "median") for s in signals}
    produced |= {f"top_{ex.primary_signal()}", "duration_s", "descent_time_s"}
    for name, rule in ex.error_rules().items():
        if rule is not None:
            assert rule.feature in produced, (name, rule.feature)
