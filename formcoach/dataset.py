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

from formcoach.conditions import parse_condition
from formcoach.exercises import get_exercise
from formcoach.labels import LabelFormatError, check_alignment, load_labels
from formcoach.pipeline import analyze
from formcoach.pose.session_json import SessionFormatError, load_session_json

# Khoá trong Rep.features không phải đặc trưng tư thế: vị trí khung đáy phụ thuộc lúc bắt đầu
# quay, đưa vào model chỉ thêm nhiễu.
NON_FEATURES = frozenset({"bottom_frame"})
# Dữ liệu train/test chỉ lấy từ trang quay của app: keypoint MediaPipe Python (đường offline) có
# thể lệch hệ thống so với MediaPipe JS.
ALLOWED_POSE_SOURCE = "mediapipe-js"


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
    # Lỗi cố ý đã chọn trước khi quay hiệp này (không phải nhãn của rep): để phân tích xem luật
    # báo nhầm/bỏ sót ở loại hiệp nào. Không đưa vào đặc trưng.
    set_errors: frozenset[str] = frozenset()
    # "dataset" (Quay dữ liệu, có kịch bản lỗi) hoặc "train" (chế độ Tập, không kịch bản). Đánh giá
    # mặc định chỉ dùng "dataset" (evaluation/split.py); app học trên cả hai nếu đã gán nhãn.
    capture_mode: str = "dataset"


@dataclass(frozen=True)
class SessionCount:
    """Bộ đếm cắt bao nhiêu rep ở một hiệp đã gán nhãn, bao nhiêu rep là thật (valid)."""

    session_id: str
    recorded_at: datetime
    counted: int
    valid: int
    capture_mode: str = "dataset"

    @property
    def extra(self) -> int:
        """Rep bộ đếm cắt thừa (người gán nhãn bỏ tick "Là rep")."""
        return self.counted - self.valid


@dataclass(frozen=True)
class Dataset:
    exercise: str
    error_labels: tuple[str, ...]
    rows: tuple[RepRow, ...]
    skipped: tuple[tuple[str, str], ...]  # (session_id, lý do) của hiệp không đưa vào
    sessions: tuple[SessionCount, ...] = ()  # mọi hiệp đã đưa vào (kể cả rep không hợp lệ)

    def feature_names(self) -> list[str]:
        """Mọi tên đặc trưng xuất hiện ở ít nhất một rep, sắp xếp cố định."""
        return sorted({k for r in self.rows for k in r.features})


def build_dataset(data_dir: Path, exercise: str) -> Dataset:
    """Đọc `<data_dir>/sessions/<exercise>/*.json` + nhãn tương ứng → Dataset."""
    ex = get_exercise(exercise)
    rows: list[RepRow] = []
    skipped: list[tuple[str, str]] = []
    sessions: list[SessionCount] = []
    for path in sorted((Path(data_dir) / "sessions" / exercise).glob("*.json")):
        sid = path.stem
        try:
            pose, meta = load_session_json(path)
            labels = load_labels(Path(data_dir), exercise, sid)
        except (SessionFormatError, LabelFormatError) as e:
            skipped.append((sid, f"file hỏng: {e}"))
            continue
        if meta.source.get("pose") != ALLOWED_POSE_SOURCE:
            skipped.append(
                (sid, f"nguồn keypoint {meta.source.get('pose')!r}, không phải trang quay")
            )
            continue
        # Hiệp thí nghiệm điều kiện quay (ghi chú `ao:… goc:…`): đáp án đã biết là "tập đúng",
        # chỉ để đo báo nhầm. Lỡ gán nhãn cũng không đưa vào train/đánh giá.
        if parse_condition(meta.notes) is not None:
            skipped.append((sid, "hiệp thí nghiệm điều kiện quay, không dùng để train"))
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
        sessions.append(
            SessionCount(
                sid,
                recorded_at,
                counted=len(reps),
                valid=sum(lab.valid for lab in labels.reps),
                capture_mode=meta.capture_mode,
            )
        )
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
                    set_errors=meta.set_errors,
                    capture_mode=meta.capture_mode,
                )
            )
    return Dataset(exercise, tuple(ex.error_labels), tuple(rows), tuple(skipped), tuple(sessions))


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
