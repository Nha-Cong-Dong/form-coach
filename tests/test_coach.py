from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone

from formcoach.coach import CoachProgress, TemplateCoach, progress_after
from formcoach.coach.prompt import SYSTEM_PROMPT, build_coach_prompt
from formcoach.coach.template import rep_ranges
from formcoach.exercises import get_exercise
from formcoach.progress.goals import Goal, SetRecord
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


def test_measure_shown_only_for_reps_past_rule_threshold() -> None:
    # Mô hình chấm "shallow" cả 2 rep, nhưng chỉ rep 2 vượt ngưỡng luật (> 67°): chỉ in số đo rep 2.
    # Không rep nào vượt thì không in số (tránh "57°, mục tiêu ≤ 67°").
    results = [
        _result(0, {"shallow"}, min_elbow_angle=57.0),
        _result(1, {"shallow"}, min_elbow_angle=80.0),
    ]
    text = TemplateCoach().summarize(Session("s", "pushup", results))
    assert "Chưa xuống đủ sâu ở rep 1–2 (góc khuỷu ở đáy 80°, mục tiêu ≤ 67°)." in text.splitlines()
    text = TemplateCoach().summarize(Session("s", "pushup", results[:1]))
    assert "Chưa xuống đủ sâu ở rep 1." in text.splitlines()
    assert "°" not in text


VN = timezone(timedelta(hours=7))
D = date(2026, 10, 20)


def _set(day: date, hour: int, n_reps: int) -> SetRecord:
    return SetRecord(datetime(day.year, day.month, day.day, hour, 0, tzinfo=VN), n_reps, n_reps)


def test_progress_after_counts_only_sets_up_to_this_one() -> None:
    # Hôm qua 10 rep, hôm nay 3 hiệp; xem hiệp lúc 18h: hiệp 20h (ghi sau) chưa tính.
    records = [_set(D - timedelta(1), 18, 10), _set(D, 7, 12), _set(D, 18, 8), _set(D, 20, 30)]
    goals = [Goal(daily_reps=20, from_date=D - timedelta(1))]
    at = datetime(2026, 10, 20, 18, 0, tzinfo=VN)
    assert progress_after(records, goals, at) == CoachProgress(20, 20, streak=1)
    # Hiệp lúc 7h: hôm nay mới 12/20 (chưa đạt), hôm qua 10/20 cũng chưa đạt → streak 0.
    at7 = datetime(2026, 10, 20, 7, 0, tzinfo=VN)
    assert progress_after(records, goals, at7) == CoachProgress(12, 20, streak=0)


def test_progress_after_without_goal_and_naive_time() -> None:
    # Chưa đặt mục tiêu: có tập là đạt. Chuỗi không múi giờ vẫn so được với chuỗi có múi giờ.
    records = [_set(D - timedelta(1), 18, 5), _set(D, 9, 4)]
    at = datetime(2026, 10, 20, 9, 0)  # không múi giờ
    assert progress_after(records, [], at) == CoachProgress(4, None, streak=2)


def test_prompt_carries_template_facts_and_exercise() -> None:
    # LLM nhận đúng các dòng của mẫu câu: không có con số nào khác với cái người dùng vẫn thấy.
    results = [_result(0, min_elbow_angle=60.0), _result(1, {"shallow"}, min_elbow_angle=80.0)]
    session = Session("s", "pushup", results)
    progress = CoachProgress(day_reps=20, daily_reps=50, streak=2)
    prompt = build_coach_prompt(session, progress)
    facts = TemplateCoach().summarize(session, progress)
    assert prompt.user.startswith("Bài tập: pushup\n")
    assert prompt.user.endswith(facts)
    assert "80°" in prompt.user and "20/50 rep" in prompt.user


def test_prompt_system_is_fixed_and_has_no_session_data() -> None:
    # Chỉ dẫn giống hệt nhau ở mọi hiệp; số liệu chỉ nằm ở phần user.
    a = build_coach_prompt(Session("id-aaa", "pushup", [_result(0, {"hip_sag"})]))
    b = build_coach_prompt(Session("id-bbb", "pushup", []), CoachProgress(3, None, 1))
    assert a.system == b.system == SYSTEM_PROMPT
    assert a.user != b.user


def test_prompt_does_not_send_session_id() -> None:
    # Chỉ gửi thứ cần để viết nhận xét; mã hiệp không cần.
    prompt = build_coach_prompt(Session("pushup_20261101_abc123", "pushup", [_result(0)]))
    assert "abc123" not in prompt.system + prompt.user


def test_prompt_names_every_pushup_error() -> None:
    # Quy tắc giọng văn trong prompt ghi cứng tên hiển thị của lỗi: đổi tên ở error_display mà quên
    # sửa prompt thì Claude không biết lỗi đó thuộc nhóm chắc hay mơ hồ.
    for name in get_exercise("pushup").error_display.values():
        assert f'"{name}"' in SYSTEM_PROMPT, name
