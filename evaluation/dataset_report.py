"""Dựng bảng dataset, in thống kê theo nhóm và các lần chia, xuất CSV.

Chạy từ gốc repo:
    python -m evaluation.dataset_report                 # nhóm theo ngày (mặc định)
    python -m evaluation.dataset_report --group block   # nhóm theo buổi (cách nhau ≥ 1 giờ)
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from evaluation.split import (
    error_counts,
    evaluation_rows,
    group_keys,
    is_pilot,
    leave_one_group_out,
    missing_errors,
)
from formcoach.dataset import build_dataset, write_csv


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m evaluation.dataset_report")
    p.add_argument("--data", type=Path, default=Path("data"), help="thư mục dữ liệu")
    p.add_argument("--exercise", default="pushup")
    p.add_argument("--group", choices=["day", "block"], default="day", help="cách nhóm buổi")
    p.add_argument("--out", type=Path, default=Path("outputs"), help="thư mục ghi CSV")
    args = p.parse_args(argv)

    ds = build_dataset(args.data, args.exercise)
    for sid, reason in ds.skipped:
        print(f"bỏ qua {sid}: {reason}")

    # CSV gồm cả hiệp quay thử (cột pilot = 1) để xem lại ngưỡng; chấm điểm thì bỏ.
    pilot = [str(int(is_pilot(r))) for r in ds.rows]
    out = write_csv(ds, args.out / f"dataset_{args.exercise}.csv", {"pilot": pilot})
    print(f"\n{len(ds.rows)} rep hợp lệ đã gán nhãn ({pilot.count('1')} rep quay thử) → {out}")

    rows = evaluation_rows(ds)
    groups = group_keys(rows, args.group)
    counts = error_counts(rows, groups, ds.error_labels)
    print(f"\nDùng để chấm điểm: {len(rows)} rep, nhóm theo {args.group}:")
    print(f"  {'nhóm':<14}{'rep':>5}" + "".join(f"{e:>20}" for e in ds.error_labels))
    for g, c in counts.items():
        print(f"  {g:<14}{c['reps']:>5}" + "".join(f"{c[e]:>20}" for e in ds.error_labels))
    for warning in missing_errors(counts, ds.error_labels):
        print(f"  CẢNH BÁO {warning}")

    if len(counts) < 2:
        print("\nChưa đủ 2 nhóm để kiểm định chéo.")
        return
    print("\nCác lần chia (bỏ ra một nhóm):")
    for f in leave_one_group_out(groups):
        print(f"  test {f.test_group}: {len(f.test)} rep | train {len(f.train)} rep")


if __name__ == "__main__":
    main()
