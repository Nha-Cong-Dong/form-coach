"""Nhãn từng rep của một hiệp: lưu mỗi hiệp một file `data/labels/<bài>/<session_id>.json`.

Nhãn gắn với rep qua **ranh giới** (frame và giây), không chỉ qua số thứ tự: nếu sau này đổi
ngưỡng bộ đếm, rep được cắt lại khác đi thì `check_alignment` phát hiện, không gán nhầm nhãn.
Nhãn là multi-label: mỗi rep một tập lỗi (rỗng = good); rep cắt nhầm có `valid = False`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from formcoach.exercises import EXERCISES
from formcoach.pose.session_json import SESSION_ID_RE
from formcoach.types import Rep

FORMAT_VERSION = 1


class LabelFormatError(ValueError):
    """File nhãn sai định dạng hoặc nội dung không hợp lệ."""


@dataclass(frozen=True)
class RepLabel:
    rep_index: int
    start_frame: int
    end_frame: int
    start_s: float  # ranh giới theo giây, để so lại khi rep được cắt lại
    end_s: float
    valid: bool = True  # False = bộ đếm cắt nhầm (không phải rep thật), loại khỏi train
    errors: frozenset[str] = frozenset()  # rỗng = good
    note: str = ""


@dataclass(frozen=True)
class SessionLabels:
    session_id: str
    exercise: str
    labeled_at: str  # ISO 8601
    segmenter_thresholds: dict[str, float]  # phase_thresholds lúc cắt rep để gán nhãn
    reps: tuple[RepLabel, ...]


def labels_path(data_dir: Path, exercise: str, session_id: str) -> Path:
    """Đường dẫn file nhãn. Kiểm tra session_id để không ghi ra ngoài thư mục."""
    if not SESSION_ID_RE.match(session_id):
        raise LabelFormatError("'session_id' chỉ được gồm chữ, số, '_' và '-'")
    if exercise not in EXERCISES:
        raise LabelFormatError(f"bài tập {exercise!r} không hỗ trợ")
    return Path(data_dir) / "labels" / exercise / f"{session_id}.json"


def default_labels(
    session_id: str,
    exercise: str,
    reps: list[Rep],
    times_s: np.ndarray,
    set_errors: frozenset[str],
    segmenter_thresholds: dict[str, float],
) -> SessionLabels:
    """Nhãn ban đầu: mọi rep nhận tập lỗi cố ý của cả hiệp, đều hợp lệ. Sửa từng rep sau."""
    labels = SessionLabels(
        session_id=session_id,
        exercise=exercise,
        labeled_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        segmenter_thresholds=dict(segmenter_thresholds),
        reps=tuple(
            RepLabel(
                rep_index=r.index,
                start_frame=r.start_frame,
                end_frame=r.end_frame,
                start_s=round(float(times_s[r.start_frame]), 3),
                end_s=round(float(times_s[r.end_frame]), 3),
                errors=frozenset(set_errors),
            )
            for r in reps
        ),
    )
    validate(labels)
    return labels


def validate(labels: SessionLabels) -> None:
    """Báo LabelFormatError nếu nhãn không hợp lệ."""
    labels_path(Path("."), labels.exercise, labels.session_id)  # kiểm tra id + bài tập
    allowed = set(EXERCISES[labels.exercise].error_labels)
    prev_end = -1
    for i, r in enumerate(labels.reps):
        where = f"rep {i}"
        if r.rep_index != i:
            raise LabelFormatError(f"{where}: rep_index phải là {i} (đánh số liên tiếp từ 0)")
        if not 0 <= r.start_frame < r.end_frame:
            raise LabelFormatError(f"{where}: cần 0 ≤ start_frame < end_frame")
        if r.start_frame < prev_end:
            raise LabelFormatError(f"{where}: chồng lên rep trước")
        if not r.start_s < r.end_s:
            raise LabelFormatError(f"{where}: cần start_s < end_s")
        unknown = sorted(r.errors - allowed)
        if unknown:
            raise LabelFormatError(f"{where}: lỗi không hợp lệ cho {labels.exercise}: {unknown}")
        if not r.valid and r.errors:
            raise LabelFormatError(f"{where}: rep không hợp lệ (valid=false) thì không gắn lỗi")
        prev_end = r.end_frame


def to_dict(labels: SessionLabels) -> dict[str, Any]:
    return {
        "format_version": FORMAT_VERSION,
        "session_id": labels.session_id,
        "exercise": labels.exercise,
        "labeled_at": labels.labeled_at,
        "segmenter_thresholds": labels.segmenter_thresholds,
        "reps": [
            {
                "rep_index": r.rep_index,
                "start_frame": r.start_frame,
                "end_frame": r.end_frame,
                "start_s": r.start_s,
                "end_s": r.end_s,
                "valid": r.valid,
                "errors": sorted(r.errors),  # sắp xếp để file ổn định, dễ so sánh
                "note": r.note,
            }
            for r in labels.reps
        ],
    }


def from_dict(data: Any) -> SessionLabels:
    """dict (đã json.loads, hoặc body API) → SessionLabels đã kiểm tra."""
    try:
        if data["format_version"] != FORMAT_VERSION:
            raise LabelFormatError(f"format_version {data['format_version']!r} không hỗ trợ")
        thresholds = {str(k): float(v) for k, v in data["segmenter_thresholds"].items()}
        reps = tuple(
            RepLabel(
                rep_index=int(r["rep_index"]),
                start_frame=int(r["start_frame"]),
                end_frame=int(r["end_frame"]),
                start_s=float(r["start_s"]),
                end_s=float(r["end_s"]),
                valid=bool(r["valid"]),
                errors=frozenset(str(e) for e in r["errors"]),
                note=str(r.get("note", "")),
            )
            for r in data["reps"]
        )
        labels = SessionLabels(
            session_id=str(data["session_id"]),
            exercise=str(data["exercise"]),
            labeled_at=str(data["labeled_at"]),
            segmenter_thresholds=thresholds,
            reps=reps,
        )
    except LabelFormatError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise LabelFormatError(f"thiếu hoặc sai kiểu trường: {e}") from None
    validate(labels)
    return labels


def save_labels(labels: SessionLabels, data_dir: Path) -> Path:
    """Ghi file nhãn. Ghi ra file tạm rồi đổi tên: lỡ tắt máy giữa chừng không làm hỏng file cũ."""
    validate(labels)
    path = labels_path(data_dir, labels.exercise, labels.session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(to_dict(labels), ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_labels(data_dir: Path, exercise: str, session_id: str) -> SessionLabels | None:
    """Đọc nhãn đã lưu; chưa gán nhãn thì trả None."""
    path = labels_path(data_dir, exercise, session_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise LabelFormatError(f"{path.name} không phải JSON hợp lệ: {e}") from None
    return from_dict(data)


def check_alignment(
    labels: SessionLabels, reps: list[Rep], times_s: np.ndarray, tolerance_s: float = 0.2
) -> list[str]:
    """So nhãn đã lưu với rep vừa cắt lại. Trả danh sách khác biệt; rỗng = khớp.

    Khác số rep, hoặc ranh giới lệch quá tolerance_s → nhãn có thể đang gắn nhầm rep.
    """
    problems: list[str] = []
    if len(labels.reps) != len(reps):
        problems.append(f"số rep khác: nhãn có {len(labels.reps)}, cắt lại ra {len(reps)}")
    for lab, rep in zip(labels.reps, reps, strict=False):
        start, end = float(times_s[rep.start_frame]), float(times_s[rep.end_frame])
        if abs(start - lab.start_s) > tolerance_s or abs(end - lab.end_s) > tolerance_s:
            problems.append(
                f"rep {lab.rep_index}: nhãn {lab.start_s:.2f}–{lab.end_s:.2f} s, "
                f"cắt lại {start:.2f}–{end:.2f} s"
            )
    return problems
