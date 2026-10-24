import math

import numpy as np
import pytest

from formcoach.exercises import PushUp
from formcoach.exercises.base import ErrorRule, Exercise
from formcoach.models import make_classifier
from formcoach.models import random_forest as rf_module
from formcoach.models.random_forest import RandomForest
from formcoach.types import Rep


class TwoErrorExercise(Exercise):
    """Bài tập giả có hai lỗi độc lập `a` và `b` (RF không dùng luật, chỉ cần tên lỗi)."""

    name = "fake"
    error_labels = ["a", "b"]

    def angle_definitions(self) -> dict[str, tuple[str, str, str]]:
        return {"s": ("p", "q", "r")}

    def primary_signal(self) -> str:
        return "s"

    def phase_thresholds(self) -> dict[str, float]:
        return {}

    def error_rules(self) -> dict[str, ErrorRule | None]:
        return {"a": None, "b": None}


def make_reps(n: int, seed: int) -> tuple[list[Rep], list[frozenset[str]]]:
    """Lỗi `a` khi x cao, lỗi `b` khi y thấp, hai lỗi độc lập; z là nhiễu không liên quan."""
    rng = np.random.default_rng(seed)
    reps, errors = [], []
    for i in range(n):
        has_a, has_b = bool(rng.integers(2)), bool(rng.integers(2))
        x = rng.uniform(60, 100) if has_a else rng.uniform(0, 40)
        y = rng.uniform(0, 10) if has_b else rng.uniform(30, 60)
        reps.append(Rep(i, 0, 1, {"x": x, "y": y, "z": float(rng.normal())}))
        errors.append(frozenset({e for e, on in (("a", has_a), ("b", has_b)) if on}))
    return reps, errors


def fitted(seed: int = 0, n: int = 120) -> RandomForest:
    model = RandomForest(TwoErrorExercise(), seed=seed)
    model.fit(*make_reps(n, seed=100))
    return model


def test_learns_separable_features_and_generalises_to_unseen_reps() -> None:
    model = fitted()
    test_reps, test_errors = make_reps(60, seed=200)
    predicted = [r.errors for r in model.predict(test_reps)]
    assert predicted == test_errors  # đa nhãn: rep có cả a và b được đoán đủ cả hai


def test_same_seed_gives_identical_predictions_and_scores() -> None:
    reps, _ = make_reps(30, seed=300)
    first, second = fitted(seed=3).predict(reps), fitted(seed=3).predict(reps)
    assert [r.errors for r in first] == [r.errors for r in second]
    assert [r.scores for r in first] == [r.scores for r in second]


def test_scores_are_probabilities_for_every_error() -> None:
    reps, _ = make_reps(20, seed=400)
    for result in fitted().predict(reps):
        assert set(result.scores) == {"a", "b"}
        assert all(0.0 <= s <= 1.0 for s in result.scores.values())
        # Báo lỗi khi xác suất ≥ 0,5 (ngưỡng đã đăng ký trước).
        assert result.errors == frozenset(e for e, s in result.scores.items() if s >= 0.5)


def test_unseen_keys_at_predict_are_ignored() -> None:
    # Trong app, rep từ `analyze` còn có khoá như bottom_frame mà bảng train không có: bỏ qua.
    model = fitted()
    reps, _ = make_reps(10, seed=500)
    extra = [
        Rep(r.index, 0, 1, {**r.features, "bottom_frame": 123.0, "khong_co": 9.0}) for r in reps
    ]
    assert [r.scores for r in model.predict(reps)] == [r.scores for r in model.predict(extra)]
    assert "bottom_frame" not in model.columns_


def test_missing_keys_and_nan_do_not_crash() -> None:
    model = fitted()
    odd = [
        Rep(0, 0, 1, {}),  # không có số đo nào
        Rep(1, 0, 1, {"x": math.nan, "y": 5.0}),
        Rep(2, 0, 1, {"z": 0.1}),
    ]
    results = model.predict(odd)
    assert len(results) == 3 and all(isinstance(r.errors, frozenset) for r in results)


def test_training_with_nan_and_missing_keys_works() -> None:
    reps, errors = make_reps(120, seed=100)
    reps = [
        Rep(r.index, 0, 1, {**r.features, "x": math.nan} if r.index % 10 == 0 else dict(r.features))
        for r in reps
    ]
    reps[5] = Rep(5, 0, 1, {"y": reps[5].features["y"]})  # thiếu hẳn khoá x và z
    model = RandomForest(TwoErrorExercise())
    model.fit(reps, errors)
    assert model.predict(reps[:3])  # không lỗi


def test_error_with_too_few_positives_never_fires_but_others_still_learn() -> None:
    reps, errors = make_reps(120, seed=100)
    one_positive_b = [e - {"b"} for e in errors]
    one_positive_b[0] = one_positive_b[0] | {"b"}  # chỉ đúng 1 rep dương cho b
    model = RandomForest(TwoErrorExercise())
    model.fit(reps, one_positive_b)
    results = model.predict(reps)
    assert all("b" not in r.errors and r.scores["b"] == 0.0 for r in results)
    assert any("a" in r.errors for r in results)  # lỗi a vẫn học bình thường
    assert "b" not in model.importances_


def test_no_positive_or_all_positive_means_no_model_for_that_error() -> None:
    reps, errors = make_reps(60, seed=100)
    model = RandomForest(TwoErrorExercise())
    model.fit(reps, [frozenset({"a"})] * len(reps))  # a luôn có: một lớp, không học được
    assert "a" not in model.importances_ and "b" not in model.importances_
    assert all(not r.errors for r in model.predict(reps))


def test_columns_come_from_the_training_reps_only() -> None:
    reps = [Rep(i, 0, 1, {"x": float(i), "y": float(i % 3)}) for i in range(30)]
    reps[0] = Rep(0, 0, 1, {"x": 0.0, "y": 0.0, "chi_mot_rep": 1.0, "toan_nan": math.nan})
    model = RandomForest(TwoErrorExercise())
    model.fit(reps, [frozenset({"a"}) if i % 2 else frozenset() for i in range(30)])
    assert model.columns_ == ["chi_mot_rep", "x", "y"]  # toàn NaN bị bỏ; sắp xếp cố định


def test_predict_before_fit_raises_and_refit_replaces_the_columns() -> None:
    model = RandomForest(TwoErrorExercise())
    with pytest.raises(RuntimeError, match="chưa fit"):
        model.predict([Rep(0, 0, 1, {"x": 1.0})])
    model.fit(*make_reps(60, seed=1))
    assert model.columns_ == ["x", "y", "z"]
    model.fit(
        [Rep(i, 0, 1, {"w": float(i)}) for i in range(20)],
        [frozenset({"a"})] * 10 + [frozenset()] * 10,
    )
    assert model.columns_ == ["w"]


def test_order_is_preserved_and_empty_input_gives_empty_output() -> None:
    model = fitted()
    reps = [Rep(7, 0, 1, {"x": 90.0, "y": 5.0}), Rep(3, 0, 1, {"x": 10.0, "y": 50.0})]
    assert [r.rep.index for r in model.predict(reps)] == [7, 3]
    assert model.predict([]) == []


def test_importance_points_at_the_informative_feature() -> None:
    model = fitted()
    imp_a, imp_b = model.importances_["a"], model.importances_["b"]
    assert max(imp_a, key=imp_a.get) == "x" and max(imp_b, key=imp_b.get) == "y"
    assert sum(imp_a.values()) == pytest.approx(1.0)


def test_pre_registered_hyperparameters_are_unchanged() -> None:
    # Đăng ký trước ở README §8: đổi các số này là đổi giả thuyết, phải ghi lý do.
    assert (rf_module.N_ESTIMATORS, rf_module.MAX_DEPTH, rf_module.MIN_SAMPLES_LEAF) == (300, 4, 5)
    assert rf_module.CLASS_WEIGHT == "balanced_subsample" and rf_module.THRESHOLD == 0.5
    params = fitted(seed=5)._models["a"].get_params()
    assert params["n_estimators"] == 300 and params["max_depth"] == 4
    assert params["min_samples_leaf"] == 5 and params["class_weight"] == "balanced_subsample"
    assert params["random_state"] == 5


def test_registry_builds_a_fresh_random_forest_for_pushup() -> None:
    a, b = make_classifier("rf", PushUp(), seed=1), make_classifier("rf", PushUp(), seed=1)
    assert isinstance(a, RandomForest) and a is not b


def test_probability_exactly_at_the_threshold_counts_as_an_error() -> None:
    # Ngưỡng đăng ký trước là "xác suất ≥ 0,5": đúng 0,5 thì báo. Rừng giả trả đúng 0,5.
    class Half:
        classes_ = np.array([0, 1])

        def predict_proba(self, x: np.ndarray) -> np.ndarray:
            return np.full((len(x), 2), 0.5)

    model = fitted()
    model._models["a"] = Half()  # type: ignore[assignment]
    result = model.predict([Rep(0, 0, 1, {"x": 1.0, "y": 50.0})])[0]
    assert result.scores["a"] == 0.5 and "a" in result.errors


def test_skipped_lists_errors_without_enough_positives() -> None:
    reps, errors = make_reps(40, seed=0)
    errors = [e - {"b"} for e in errors]  # không còn rep nào có lỗi b trong train
    model = RandomForest(TwoErrorExercise())
    model.fit(reps, errors)
    assert model.skipped_ == ["b"]
    model.fit(*make_reps(40, seed=0))  # fit lại với đủ rep dương: danh sách được làm mới
    assert model.skipped_ == []
