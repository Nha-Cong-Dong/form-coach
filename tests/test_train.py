from datetime import datetime

import pytest

from formcoach.dataset import Dataset, RepRow
from formcoach.exercises import get_exercise
from formcoach.models.rule_based import RuleBased
from formcoach.models.train import train_classifier
from formcoach.types import Rep

PUSHUP = get_exercise("pushup")
NOW = datetime(2026, 10, 24, 12, 0)


def _dataset(rows: list[RepRow]) -> Dataset:
    return Dataset("pushup", tuple(PUSHUP.error_labels), tuple(rows), ())


def _row(i: int, elbow: float, errors: frozenset[str]) -> RepRow:
    return RepRow(f"s{i % 3}", NOW, i, 0.0, 1.0, {"min_elbow_angle": elbow}, errors)


def test_rules_needs_no_data() -> None:
    classifier, name = train_classifier("rules", PUSHUP, None)
    assert name == "rules" and isinstance(classifier, RuleBased)


@pytest.mark.parametrize("dataset", [None, _dataset([])])
def test_learned_model_without_data_falls_back_to_rules(dataset) -> None:
    classifier, name = train_classifier("stump", PUSHUP, dataset)
    assert name == "rules" and isinstance(classifier, RuleBased)


def test_unknown_model_raises() -> None:
    with pytest.raises(ValueError):
        train_classifier("khong-co", PUSHUP, None)


def test_random_forest_trains_from_rows() -> None:
    # Mô hình mặc định của app (FORMCOACH_MODEL=rf) đi qua đúng đường này.
    rows = [_row(i, 80.0 + i, frozenset()) for i in range(10)]
    rows += [_row(10 + i, 120.0 + i, frozenset({"shallow"})) for i in range(10)]
    classifier, name = train_classifier("rf", PUSHUP, _dataset(rows))
    assert name == "rf"
    pred = classifier.predict([Rep(0, 0, 0, {"min_elbow_angle": 125.0})])
    assert "shallow" in pred[0].errors and pred[0].scores is not None


def test_stump_learns_threshold_from_rows() -> None:
    # Tách được ở 100°: rep sâu (<100) tốt, rep nông (>100) lỗi shallow.
    rows = [_row(i, 80.0 + i, frozenset()) for i in range(10)]
    rows += [_row(10 + i, 120.0 + i, frozenset({"shallow"})) for i in range(10)]
    classifier, name = train_classifier("stump", PUSHUP, _dataset(rows))
    assert name == "stump"
    pred = classifier.predict(
        [
            Rep(0, 0, 0, {"min_elbow_angle": 85.0}),
            Rep(1, 0, 0, {"min_elbow_angle": 125.0}),
        ]
    )
    assert "shallow" not in pred[0].errors and "shallow" in pred[1].errors
