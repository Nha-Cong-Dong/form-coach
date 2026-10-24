import numpy as np
import pytest

from formcoach.exercises import get_exercise
from formcoach.models.base import FormClassifier
from formcoach.models.rule_based import RuleBased
from formcoach.pipeline import classify_session
from formcoach.pose.session_json import parse_session
from formcoach.progress.summary import summarize
from formcoach.types import Rep, RepResult, Session
from tests.synthetic import make_session, three_rep_session

PUSHUP = get_exercise("pushup")


class FixedErrors(FormClassifier):
    """Bộ phân loại giả: rep thứ i nhận errors[i] (đáp án biết trước)."""

    def __init__(self, errors: list[frozenset[str]]) -> None:
        self.errors = errors

    def fit(self, reps: list[Rep], errors: list[frozenset[str]]) -> None:
        pass

    def predict(self, reps: list[Rep]) -> list[RepResult]:
        return [RepResult(rep, self.errors[i], None) for i, rep in enumerate(reps)]


def _rep(i: int) -> Rep:
    return Rep(index=i, start_frame=i * 10, end_frame=i * 10 + 9, features={})


def test_classify_session_three_reps_in_order() -> None:
    pose, meta = parse_session(three_rep_session())
    errors = [frozenset(), frozenset({"shallow"}), frozenset({"shallow", "hip_sag"})]
    session = classify_session(pose, PUSHUP, FixedErrors(errors), meta.session_id)
    assert session.session_id == meta.session_id and session.exercise == "pushup"
    assert [r.rep.index for r in session.results] == [0, 1, 2]
    assert [r.errors for r in session.results] == errors


def test_classify_session_with_rules_runs() -> None:
    pose, meta = parse_session(three_rep_session())
    session = classify_session(pose, PUSHUP, RuleBased(PUSHUP), meta.session_id)
    assert len(session.results) == 3


def test_summarize_counts() -> None:
    errors = [frozenset(), frozenset({"shallow"}), frozenset({"shallow", "hip_sag"}), frozenset()]
    session = Session("s", "pushup", [RepResult(_rep(i), e, None) for i, e in enumerate(errors)])
    s = summarize(session, PUSHUP.error_labels)
    assert s["n_reps"] == 4 and s["n_good"] == 2
    assert s["good_ratio"] == pytest.approx(0.5)
    # Đủ mọi lỗi, đúng thứ tự, rep hai lỗi được đếm ở cả hai.
    assert list(s["error_counts"]) == PUSHUP.error_labels
    assert s["error_counts"] == {
        "shallow": 2,
        "incomplete_lockout": 0,
        "hip_sag": 1,
        "hip_high": 0,
        "neck_drop": 0,
    }


def test_summarize_no_reps() -> None:
    pose, meta = parse_session(make_session(np.full(60, 165.0)))  # đứng yên: không có rep
    session = classify_session(pose, PUSHUP, FixedErrors([]), meta.session_id)
    s = summarize(session, PUSHUP.error_labels)
    assert s["n_reps"] == 0 and s["n_good"] == 0 and s["good_ratio"] is None
    assert set(s["error_counts"].values()) == {0}
