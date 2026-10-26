from datetime import date, datetime, timedelta, timezone

import pytest

from formcoach.progress.goals import (
    Goal,
    SetRecord,
    daily_progress,
    day_of,
    goal_on,
    streak,
)

VN = timezone(timedelta(hours=7))
D = date(2026, 10, 20)  # thứ Ba


def _set(day: date, n_reps: int, n_good: int | None = None, hour: int = 18) -> SetRecord:
    at = datetime(day.year, day.month, day.day, hour, 0, tzinfo=VN)
    return SetRecord(at, n_reps, n_reps if n_good is None else n_good)


def test_day_is_local_date_not_utc() -> None:
    # 23:30 giờ VN = 16:30 UTC cùng ngày; 06:00 giờ VN = 23:00 UTC ngày hôm trước.
    late = SetRecord(datetime(2026, 10, 20, 23, 30, tzinfo=VN), 5, 5)
    early = SetRecord(datetime(2026, 10, 21, 6, 0, tzinfo=VN), 5, 5)
    assert day_of(late) == date(2026, 10, 20)
    assert day_of(early) == date(2026, 10, 21)  # UTC là 20/10 nhưng người tập thấy 21/10


def test_two_sets_same_day_add_up() -> None:
    days = daily_progress([_set(D, 10, 8), _set(D, 6, 4, hour=20)], [], D, D)
    assert (days[0].n_reps, days[0].n_good) == (16, 12)
    assert days[0].good_ratio == pytest.approx(0.75)


def test_every_day_in_range_including_empty_days() -> None:
    days = daily_progress([_set(D, 10), _set(D + timedelta(days=3), 5)], [], D, D + timedelta(6))
    assert [d.day for d in days] == [D + timedelta(i) for i in range(7)]
    assert [d.n_reps for d in days] == [10, 0, 0, 5, 0, 0, 0]
    assert days[1].good_ratio is None and not days[1].met


def test_met_by_daily_reps_and_min_good_ratio() -> None:
    reps_only = [Goal(20, D)]
    assert not daily_progress([_set(D, 19)], reps_only, D, D)[0].met
    assert daily_progress([_set(D, 20, 0)], reps_only, D, D)[0].met  # đếm mọi rep, kể cả rep sai
    with_ratio = [Goal(20, D, min_good_ratio=0.8)]
    assert not daily_progress([_set(D, 20, 15)], with_ratio, D, D)[0].met  # 0,75 < 0,8
    assert daily_progress([_set(D, 20, 16)], with_ratio, D, D)[0].met  # 0,8 đúng ngưỡng


def test_no_goal_means_any_training_counts() -> None:
    days = daily_progress([_set(D, 1)], [], D, D + timedelta(1))
    assert [d.met for d in days] == [True, False]
    assert days[0].goal is None


def test_goal_change_does_not_rewrite_past_days() -> None:
    goals = [Goal(10, D), Goal(30, D + timedelta(2))]
    assert goal_on(D - timedelta(1), goals) is None
    assert goal_on(D + timedelta(1), goals) == goals[0]
    assert goal_on(D + timedelta(5), goals) == goals[1]
    sets = [_set(D + timedelta(i), 15) for i in range(4)]
    days = daily_progress(sets, goals, D, D + timedelta(3))
    assert [d.met for d in days] == [True, True, False, False]  # 15 ≥ 10, rồi 15 < 30


def test_streak_today_not_done_yet_does_not_break() -> None:
    goals = [Goal(10, D)]
    today = D + timedelta(3)
    sets = [_set(D + timedelta(i), 10) for i in range(3)]  # đạt 20, 21, 22
    assert streak(sets, goals, today) == 3  # hôm nay (23) chưa tập: vẫn 3
    assert streak(sets + [_set(today, 4)], goals, today) == 3  # tập chưa đủ: vẫn 3
    assert streak(sets + [_set(today, 10)], goals, today) == 4  # hôm nay đạt: 4


def test_streak_breaks_on_a_missed_day() -> None:
    goals = [Goal(10, D)]
    today = D + timedelta(4)
    sets = [_set(D, 10), _set(D + timedelta(2), 10), _set(D + timedelta(3), 10)]  # 21 trống
    assert streak(sets, goals, today) == 2
    assert streak(sets, goals, today + timedelta(1)) == 0  # hôm qua (24) không tập: đứt
    assert streak([], goals, today) == 0


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        Goal(0, D)
    with pytest.raises(ValueError):
        Goal(10, D, min_good_ratio=1.5)
    with pytest.raises(ValueError):
        daily_progress([], [], D, D - timedelta(1))
