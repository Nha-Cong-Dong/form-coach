"""Bộ đếm trực tiếp (OnlineRepCounter) so với bộ đếm cả hiệp (analyze) trên các hiệp đã lưu (C4).

Phát lại từng khung của mỗi hiệp qua OnlineRepCounter đúng như lúc đang tập, rồi so số rep cuối
với `len(reps)` của `analyze` (số chính thức ở trang kết quả). Không chia train/test: không có gì
học từ dữ liệu (cùng máy trạng thái, ngưỡng cố định), đây là so hai cách tính trên cùng dữ liệu.
Dùng mọi hiệp (cả quay thử, chế độ Tập): không dùng nhãn nên không có lý do loại.

Chạy (từ gốc repo):
    python -m evaluation.online_agreement [--all]
Mục tiêu (plan tuần 3): mọi hiệp lệch ≤ 1. Số trực tiếp chỉ để hiển thị.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from formcoach.exercises import get_exercise
from formcoach.features.online import OnlineRepCounter
from formcoach.pipeline import analyze
from formcoach.pose.session_json import SessionFormatError, load_session_json
from formcoach.types import PoseSequence


@dataclass(frozen=True)
class Agreement:
    session_id: str
    offline: int  # analyze (cả hiệp)
    online: int  # OnlineRepCounter (từng khung)
    side: str  # bên bộ đếm trực tiếp hiển thị lúc cuối

    @property
    def diff(self) -> int:
        return self.online - self.offline


def compare_session(session_id: str, pose: PoseSequence, exercise_name: str) -> Agreement:
    exercise = get_exercise(exercise_name)
    offline = len(analyze(pose, exercise)[1])
    counter = OnlineRepCounter(exercise, pose.fps, pose.frame_size, pose.joint_names)
    for frame in pose.keypoints:
        counter.update(frame)
    online = counter.finish()
    return Agreement(session_id, offline, online, counter.side)


def summarize(results: Sequence[Agreement]) -> dict[str, float | int]:
    """Tỉ lệ khớp, tỉ lệ lệch ≤ 1, lệch tuyệt đối TB, số hiệp đếm thừa/thiếu."""
    d = np.array([r.diff for r in results])
    if d.size == 0:
        return {"n": 0}
    return {
        "n": int(d.size),
        "exact": float(np.mean(d == 0)),
        "within_one": float(np.mean(np.abs(d) <= 1)),
        "mean_abs": float(np.mean(np.abs(d))),
        "over": int(np.sum(d > 0)),  # trực tiếp đếm thừa
        "under": int(np.sum(d < 0)),  # trực tiếp đếm thiếu
    }


def report(results: Sequence[Agreement], show_all: bool = False) -> str:
    s = summarize(results)
    if s["n"] == 0:
        return "Không có hiệp nào."
    lines = []
    for r in results:
        if show_all or r.diff != 0:
            mark = "" if r.diff == 0 else f"  <-- lệch {r.diff:+d} (bên {r.side})"
            lines.append(f"{r.session_id}: cả hiệp {r.offline}, trực tiếp {r.online}{mark}")

    def pct(v: float) -> str:
        return f"{v:.0%}"

    lines.append(
        f"\n{s['n']} hiệp: khớp {pct(s['exact'])}, lệch ≤ 1: {pct(s['within_one'])}, "
        f"lệch TB {s['mean_abs']:.2f} rep · trực tiếp đếm thừa {s['over']} hiệp, thiếu {s['under']}"
    )
    if s["within_one"] < 1:
        lines.append("CHƯA ĐẠT mục tiêu (mọi hiệp lệch ≤ 1): xem các hiệp lệch ở trên.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--exercise", default="pushup")
    parser.add_argument("--all", action="store_true", help="in cả hiệp khớp, không chỉ hiệp lệch")
    args = parser.parse_args(argv)

    results = []
    for path in sorted((args.data / "sessions" / args.exercise).glob("*.json")):
        try:
            pose, meta = load_session_json(path)
        except SessionFormatError as e:
            print(f"bỏ qua {path.stem}: {e}")
            continue
        results.append(compare_session(meta.session_id, pose, args.exercise))
    print(report(results, show_all=args.all))


if __name__ == "__main__":
    main()
