"""Mục tiêu và tiến độ của người dùng: đọc/ghi bảng `goals`, dựng dữ liệu cho Dashboard.

Logic "đạt mục tiêu" và streak nằm ở formcoach/progress/goals.py (hàm thuần, có test); file này
chỉ đọc DB, gọi hàm đó rồi đổi kết quả sang JSON.

"Hôm nay" do web gửi (ngày theo giờ điện thoại), vì server không biết múi giờ người dùng. Server
chỉ chấp nhận ngày lệch ≤ 1 ngày so với ngày UTC của server (múi giờ trên thế giới lệch UTC từ
−12 đến +14 giờ), để không đặt được mục tiêu lùi về quá khứ mà chấm lại lịch sử.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from typing import Any

from backend import results
from formcoach.coach import TemplateCoach, progress_after
from formcoach.progress.goals import DayProgress, Goal, SetRecord, daily_progress, goal_on, streak
from formcoach.types import Session

MAX_DAYS = 366  # một lần hỏi tối đa một năm: đủ cho đồ thị, chặn khoảng ngày vô lý


def plausible_today(day: date) -> bool:
    """Ngày "hôm nay" web gửi có thể đúng ở một múi giờ nào đó không."""
    return abs((day - datetime.now(UTC).date()).days) <= 1


def set_records(db: sqlite3.Connection, user_id: int, exercise: str) -> list[SetRecord]:
    """Mọi hiệp của user cho một bài (dùng lại truy vấn lịch sử của trang kết quả)."""
    return [
        SetRecord(datetime.fromisoformat(r["recorded_at"]), r["n_reps"], r["n_good"])
        for r in results.list_results(db, user_id)
        if r["exercise"] == exercise and r["recorded_at"]
    ]


def load_goals(db: sqlite3.Connection, user_id: int, exercise: str) -> list[Goal]:
    rows = db.execute(
        "SELECT daily_reps, min_good_ratio, from_date FROM goals"
        " WHERE user_id = ? AND exercise = ? ORDER BY from_date",
        (user_id, exercise),
    ).fetchall()
    return [
        Goal(r["daily_reps"], date.fromisoformat(r["from_date"]), r["min_good_ratio"]) for r in rows
    ]


def save_goal(db: sqlite3.Connection, user_id: int, exercise: str, goal: Goal) -> None:
    """Thêm mục tiêu mới; đã có mục tiêu cùng ngày thì ghi đè (route commit)."""
    db.execute(
        "INSERT INTO goals (user_id, exercise, daily_reps, min_good_ratio, from_date, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (user_id, exercise, from_date) DO UPDATE SET"
        " daily_reps = excluded.daily_reps, min_good_ratio = excluded.min_good_ratio,"
        " created_at = excluded.created_at",
        (
            user_id,
            exercise,
            goal.daily_reps,
            goal.min_good_ratio,
            goal.from_date.isoformat(),
            datetime.now(UTC).isoformat(),
        ),
    )


def goal_json(goal: Goal | None) -> dict[str, Any] | None:
    if goal is None:
        return None
    return {
        "daily_reps": goal.daily_reps,
        "min_good_ratio": goal.min_good_ratio,
        "from_date": goal.from_date.isoformat(),
    }


def _day_json(d: DayProgress) -> dict[str, Any]:
    return {
        "day": d.day.isoformat(),
        "n_reps": d.n_reps,
        "n_good": d.n_good,
        "good_ratio": d.good_ratio,
        "daily_reps": d.goal.daily_reps if d.goal else None,
        "met": d.met,
    }


def progress_json(
    records: list[SetRecord], goals: list[Goal], start: date, end: date
) -> dict[str, Any]:
    """Tiến độ từ `start` tới `end`; `end` là "hôm nay" của Dashboard (streak tính tới đó)."""
    days = daily_progress(records, goals, start, end)
    n_reps = sum(d.n_reps for d in days)
    n_good = sum(d.n_good for d in days)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "goal": goal_json(goal_on(end, goals)),
        "today": _day_json(days[-1]),
        "streak": streak(records, goals, end),
        "totals": {
            "n_reps": n_reps,
            "n_good": n_good,
            "good_ratio": n_good / n_reps if n_reps else None,
        },
        "days": [_day_json(d) for d in days],
    }


def coach_json(
    db: sqlite3.Connection, user_id: int, session: Session, recorded_at: str
) -> dict[str, Any]:
    """Nhận xét của coach cho một hiệp đã lưu, tính lúc đọc (không lưu chữ vào DB).

    Tiến độ chỉ tính tới hết hiệp này; mục tiêu là mục tiêu hiện có cho ngày đó.
    """
    records = set_records(db, user_id, session.exercise)
    goals = load_goals(db, user_id, session.exercise)
    at = progress_after(records, goals, datetime.fromisoformat(recorded_at))
    return {"text": TemplateCoach().summarize(session, at), "source": "template"}
