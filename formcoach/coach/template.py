"""Coach bằng mẫu câu: không AI, mọi con số lấy thẳng từ kết quả phân loại (README §4.5)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from formcoach.coach.base import Coach, CoachProgress
from formcoach.exercises import get_exercise
from formcoach.types import Session


def rep_ranges(numbers: Sequence[int]) -> str:
    """Số rep (đếm từ 1, đã sắp xếp) → chuỗi gộp đoạn liền nhau, vd [1, 2, 3, 5] → "1–3, 5"."""
    parts: list[str] = []
    i = 0
    while i < len(numbers):
        j = i
        while j + 1 < len(numbers) and numbers[j + 1] == numbers[j] + 1:
            j += 1
        parts.append(str(numbers[i]) if i == j else f"{numbers[i]}–{numbers[j]}")
        i = j + 1
    return ", ".join(parts)


class TemplateCoach(Coach):
    """Mỗi dòng một ý: tổng quát, rep đúng, từng lỗi (kèm số đo nếu có), tiến độ hôm nay."""

    def summarize(self, session: Session, progress: CoachProgress | None = None) -> str:
        exercise = get_exercise(session.exercise)
        results = session.results
        lines: list[str] = []

        n_good = sum(1 for r in results if not r.errors)
        if not results:
            lines.append("Hiệp này chưa đếm được rep nào.")
        elif n_good == len(results):
            lines.append(f"Hiệp này: {len(results)} rep, cả {n_good} rep đều đúng kỹ thuật.")
        else:
            lines.append(f"Hiệp này: {len(results)} rep, {n_good} rep đúng kỹ thuật.")
            good = [r.rep.index + 1 for r in results if not r.errors]
            if good:
                lines.append(f"Rep {rep_ranges(good)}: tốt.")

        rules = exercise.error_rules()
        for error in exercise.error_labels:
            hit = [r for r in results if error in r.errors]
            if not hit:
                continue
            name = exercise.error_display.get(error, error)
            line = f"{name} ở rep {rep_ranges([r.rep.index + 1 for r in hit])}"
            rule = rules.get(error)
            # Chỉ kèm số đo người tập hiểu được (measure_display); lỗi hông/cổ không có số.
            if rule is not None and rule.feature in exercise.measure_display:
                label, unit = exercise.measure_display[rule.feature]
                values = [r.rep.features.get(rule.feature, math.nan) for r in hit]
                values = [v for v in values if math.isfinite(v)]
                if values:
                    lo, hi = round(min(values)), round(max(values))
                    shown = f"{lo}{unit}" if lo == hi else f"{lo}–{hi}{unit}"
                    # Lỗi khi giá trị <op> ngưỡng, nên mục tiêu là phía ngược lại.
                    target = "≤" if rule.op == ">" else "≥"
                    label = label[0].lower() + label[1:]
                    line += f" ({label} {shown}, mục tiêu {target} {rule.threshold:.0f}{unit})"
            lines.append(line + ".")

        if progress is not None:
            today = (
                f"{progress.day_reps} rep"
                if progress.daily_reps is None
                else f"{progress.day_reps}/{progress.daily_reps} rep"
            )
            lines.append(f"Hôm nay {today}, streak {progress.streak} ngày.")

        return "\n".join(lines)
