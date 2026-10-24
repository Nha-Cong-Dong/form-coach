import pytest

from formcoach.exercises import PushUp
from formcoach.models import FormClassifier, RuleBased, classifier_names, make_classifier


def test_rules_is_registered_and_returns_a_fresh_instance() -> None:
    assert "rules" in classifier_names()
    a, b = make_classifier("rules", PushUp()), make_classifier("rules", PushUp())
    assert isinstance(a, RuleBased) and isinstance(a, FormClassifier)
    assert a is not b  # mỗi lần gọi một bộ phân loại mới: không dùng chung giữa các lần chia


def test_unknown_name_lists_valid_names() -> None:
    with pytest.raises(ValueError, match="rules"):
        make_classifier("khong_co", PushUp())


def test_seed_is_accepted_by_every_model() -> None:
    for name in classifier_names():
        assert isinstance(make_classifier(name, PushUp(), seed=7), FormClassifier)
