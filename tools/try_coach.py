"""Thử coach Claude trên vài hiệp TỔNG HỢP (không đọc data/), in số liệu gửi đi và câu trả lời.

Cần `FORMCOACH_LLM_API_KEY` và `FORMCOACH_LLM_BASE_URL` trong terminal
(vd `set -a; source .env; set +a`).
Mỗi lần chạy gọi API 5 lần (khoảng vài phần trăm cent với Haiku 5.5).

    python -m tools.try_coach
"""

from __future__ import annotations

import logging
import sys

from backend.coach_llm import coach_text, llm_coach
from formcoach.coach import CoachProgress
from formcoach.types import Rep, RepResult, Session


def _rep(i: int, errors: set[str] | None = None, **features: float) -> RepResult:
    return RepResult(Rep(i, i * 10, i * 10 + 9, features), frozenset(errors or ()), None)


CASES: list[tuple[str, Session, CoachProgress | None]] = [
    (
        "tất cả đúng, đạt mục tiêu",
        Session("t1", "pushup", [_rep(i, min_elbow_angle=60.0) for i in range(12)]),
        CoachProgress(day_reps=52, daily_reps=50, streak=4),
    ),
    (
        "chưa đủ sâu kèm số đo + hông võng",
        Session(
            "t2",
            "pushup",
            [_rep(i, min_elbow_angle=60.0) for i in range(5)]
            + [_rep(5, {"hip_sag"}, min_elbow_angle=62.0)]
            + [_rep(i, {"shallow"}, min_elbow_angle=75.0 + i) for i in range(6, 10)],
        ),
        CoachProgress(day_reps=30, daily_reps=50, streak=3),
    ),
    (
        "lỗi không kèm số đo (mô hình chấm, góc trong mục tiêu)",
        Session(
            "t3",
            "pushup",
            [_rep(i, {"shallow"}, min_elbow_angle=58.0) for i in range(3)]
            + [_rep(i, {"neck_drop"}) for i in range(3, 6)],
        ),
        CoachProgress(day_reps=6, daily_reps=None, streak=0),
    ),
    (
        "không đếm được rep",
        Session("t4", "pushup", []),
        CoachProgress(day_reps=0, daily_reps=50, streak=2),
    ),
    (
        "không có dòng tiến độ, hông nhô cao",
        Session("t5", "pushup", [_rep(i, {"hip_high"}) for i in range(8)]),
        None,
    ),
]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="  [log] %(message)s")
    if llm_coach() is None:
        sys.exit("Chưa đặt FORMCOACH_LLM_API_KEY và FORMCOACH_LLM_BASE_URL: chỉ có mẫu câu.")
    from formcoach.coach.prompt import build_coach_prompt

    for name, session, progress in CASES:
        print(f"\n=== {name} ===")
        print(build_coach_prompt(session, progress).user)
        text, source = coach_text(session, progress)
        print(f"--- trả lời ({source}) ---\n{text}")


if __name__ == "__main__":
    main()
