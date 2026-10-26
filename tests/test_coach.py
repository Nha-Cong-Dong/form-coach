from collections.abc import Iterable

from formcoach.coach import CoachProgress, TemplateCoach
from formcoach.coach.template import rep_ranges
from formcoach.types import Rep, RepResult, Session


def _result(i: int, errors: Iterable[str] = (), **features: float) -> RepResult:
    rep = Rep(index=i, start_frame=i * 10, end_frame=i * 10 + 9, features=features)
    return RepResult(rep, frozenset(errors), None)


def test_rep_ranges_merges_consecutive() -> None:
    assert rep_ranges([1, 2, 3, 5, 7, 8]) == "1–3, 5, 7–8"
    assert rep_ranges([4]) == "4"
    assert rep_ranges([]) == ""


def test_readme_example() -> None:
    # Ví dụ README §4.5: 12 rep, rep 1–6 tốt, rep 7 hông võng, rep 9–12 chưa đủ sâu.
    results = [_result(i, min_elbow_angle=60.0) for i in range(6)]
    results.append(_result(6, {"hip_sag"}, min_elbow_angle=62.0))
    results.append(_result(7, min_elbow_angle=64.0))
    results += [_result(i, {"shallow"}, min_elbow_angle=104.0 + 2 * (i - 8)) for i in range(8, 12)]
    text = TemplateCoach().summarize(
        Session("s", "pushup", results), CoachProgress(day_reps=36, daily_reps=50, streak=4)
    )
    assert text.splitlines() == [
        "Hiệp này: 12 rep, 7 rep đúng kỹ thuật.",
        "Rep 1–6, 8: tốt.",
        "Chưa xuống đủ sâu ở rep 9–12 (góc khuỷu ở đáy 104–110°, mục tiêu ≤ 67°).",
        "Hông võng ở rep 7.",
        "Hôm nay 36/50 rep, streak 4 ngày.",
    ]


def test_all_good_and_no_progress() -> None:
    text = TemplateCoach().summarize(Session("s", "pushup", [_result(i) for i in range(5)]))
    assert text == "Hiệp này: 5 rep, cả 5 rep đều đúng kỹ thuật."


def test_no_reps() -> None:
    text = TemplateCoach().summarize(Session("s", "pushup", []), CoachProgress(0, None, 0))
    assert text.splitlines() == ["Hiệp này chưa đếm được rep nào.", "Hôm nay 0 rep, streak 0 ngày."]


def test_one_rep_with_two_errors_listed_under_each() -> None:
    rep = _result(0, {"shallow", "incomplete_lockout"}, min_elbow_angle=90.4, top_elbow_angle=130.0)
    text = TemplateCoach().summarize(Session("s", "pushup", [rep]))
    assert text.splitlines() == [
        "Hiệp này: 1 rep, 0 rep đúng kỹ thuật.",
        "Chưa xuống đủ sâu ở rep 1 (góc khuỷu ở đáy 90°, mục tiêu ≤ 67°).",
        "Chưa duỗi hết tay ở rep 1 (góc khuỷu ở đỉnh 130°, mục tiêu ≥ 146°).",
    ]


def test_missing_measure_is_not_invented() -> None:
    # Không có số đo (NaN hoặc thiếu) thì không in khoảng số đo nào.
    results = [_result(0, {"shallow"}, min_elbow_angle=float("nan")), _result(1, {"shallow"})]
    text = TemplateCoach().summarize(Session("s", "pushup", results))
    assert "Chưa xuống đủ sâu ở rep 1–2." in text.splitlines()
    assert "°" not in text
