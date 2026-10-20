"""Gom mọi hiệp đã gán nhãn thành bảng dataset: mỗi dòng một rep (đặc trưng + nhãn lỗi).

Chỉ đọc file và dựng bảng; chia train/test và loại hiệp quay thử nằm ở `evaluation/`.
Rep `valid = false` (không phải rep) bị bỏ. Hiệp chưa gán nhãn, nhãn hỏng hoặc nhãn không còn
khớp rep (bộ đếm đã đổi) bị bỏ qua và ghi lý do, không gán bừa.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from formcoach.exercises import get_exercise
from formcoach.labels import LabelFormatError, check_alignment, load_labels
from formcoach.pipeline import analyze
from formcoach.pose.session_json import SessionFormatError, load_session_json

# Khoá trong Rep.features không phải đặc trưng tư thế: vị trí khung đáy phụ thuộc lúc bắt đầu
# quay, đưa vào model chỉ thêm nhiễu.
NON_FEATURES = frozenset({"bottom_frame"})


@dataclass(frozen=True)
class RepRow:
    """Một rep hợp lệ đã gán nhãn."""

    session_id: str
    recorded_at: datetime  # lúc bắt đầu hiệp, để nhóm theo ngày / theo buổi
    rep_index: int
    start_s: float
    end_s: float
    features: dict[str, float]
    errors: frozenset[str]


@dataclass(frozen=True)
class Dataset:
    exercise: str
    error_labels: tuple[str, ...]
    rows: tuple[RepRow, ...]
    skipped: tuple[tuple[str, str], ...]  # (session_id, lý do) của hiệp không đưa vào

    def feature_names(self) -> list[str]:
        """Mọi tên đặc trưng xuất hiện ở ít nhất một rep, sắp xếp cố định."""
        return sorted({k for r in self.rows for k in r.features})


def build_dataset(data_dir: Path, exercise: str) -> Dataset:
    """Đọc `<data_dir>/sessions/<exercise>/*.json` + nhãn tương ứng → Dataset."""
    ex = get_exercise(exercise)
    rows: list[RepRow] = []
    skipped: list[tuple[str, str]] = []
    for path in sorted((Path(data_dir) / "sessions" / exercise).glob("*.json")):
        sid = path.stem
        try:
            pose, meta = load_session_json(path)
            labels = load_labels(Path(data_dir), exercise, sid)
        except (SessionFormatError, LabelFormatError) as e:
            skipped.append((sid, f"file hỏng: {e}"))
            continue
        if labels is None:
            skipped.append((sid, "chưa gán nhãn"))
            continue

        _, reps = analyze(pose, ex)
        times = (meta.timestamps_ms - meta.timestamps_ms[0]) / 1000.0
        problems = check_alignment(labels, reps, times)
        if problems:
            skipped.append((sid, "nhãn không khớp rep: " + "; ".join(problems)))
            continue

        recorded_at = datetime.fromisoformat(meta.recorded_at)
        for rep, lab in zip(reps, labels.reps, strict=True):
            if not lab.valid:
                continue
            rows.append(
                RepRow(
                    session_id=sid,
                    recorded_at=recorded_at,
                    rep_index=rep.index,
                    start_s=float(times[rep.start_frame]),
                    end_s=float(times[rep.end_frame]),
                    features={k: v for k, v in rep.features.items() if k not in NON_FEATURES},
                    errors=lab.errors,
                )
            )
    return Dataset(exercise, tuple(ex.error_labels), tuple(rows), tuple(skipped))


def write_csv(dataset: Dataset, path: Path, extra: dict[str, list[str]] | None = None) -> Path:
    """Bảng ra CSV: định danh, (cột thêm, vd nhóm chia), đặc trưng, rồi mỗi lỗi một cột 0/1.

    Đặc trưng thiếu ở một rep (vd cả rep không thấy tai) để trống.
    """
    extra = extra or {}
    features = dataset.feature_names()
    header = ["session_id", "recorded_at", "rep_index", "start_s", "end_s", *extra, *features]
    header += list(dataset.error_labels)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for i, r in enumerate(dataset.rows):
            w.writerow(
                [r.session_id, r.recorded_at.isoformat(), r.rep_index, f"{r.start_s:.3f}"]
                + [f"{r.end_s:.3f}", *(col[i] for col in extra.values())]
                + [r.features.get(name, "") for name in features]
                + [int(e in r.errors) for e in dataset.error_labels]
            )
    return path
