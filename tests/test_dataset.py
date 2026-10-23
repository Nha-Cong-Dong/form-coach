import csv
import dataclasses
import json
from pathlib import Path

import pytest

from formcoach.dataset import build_dataset, write_csv
from formcoach.exercises import PushUp
from formcoach.labels import default_labels, save_labels
from formcoach.pipeline import analyze
from formcoach.pose.session_json import parse_session
from tests.synthetic import three_rep_session


def add_session(
    data_dir: Path,
    session_id: str,
    recorded_at: str = "2026-10-21T08:00:00+07:00",
    set_errors: tuple[str, ...] = (),
    label: bool = True,
    edit=None,
    pose_source: str = "mediapipe-js",
) -> None:
    """Ghi một hiệp tổng hợp (3 rep) vào <data_dir>/sessions/pushup/ và (tuỳ chọn) nhãn của nó.

    edit(reps) → reps mới: sửa nhãn từng rep trước khi lưu.
    """
    data = three_rep_session(set_errors)
    data["session_id"] = session_id
    data["recorded_at"] = recorded_at
    data["source"]["pose"] = pose_source
    folder = data_dir / "sessions" / "pushup"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{session_id}.json").write_text(json.dumps(data), encoding="utf-8")
    if not label:
        return
    pose, meta = parse_session(data)
    _, reps = analyze(pose, PushUp())
    times = (meta.timestamps_ms - meta.timestamps_ms[0]) / 1000
    labels = default_labels(session_id, "pushup", reps, times, meta.set_errors,
                            PushUp().phase_thresholds())  # fmt: skip
    if edit is not None:
        labels = dataclasses.replace(labels, reps=tuple(edit(list(labels.reps))))
    save_labels(labels, data_dir)


def test_rows_carry_features_and_labels(tmp_path: Path) -> None:
    add_session(tmp_path, "a_pushup", set_errors=("shallow",))
    add_session(tmp_path, "b_pushup")
    ds = build_dataset(tmp_path, "pushup")
    assert [r.session_id for r in ds.rows] == ["a_pushup"] * 3 + ["b_pushup"] * 3
    assert all(r.errors == frozenset({"shallow"}) for r in ds.rows[:3])
    assert all(r.errors == frozenset() for r in ds.rows[3:])
    assert ds.rows[0].recorded_at.isoformat() == "2026-10-21T08:00:00+07:00"
    assert ds.error_labels == tuple(PushUp.error_labels)


def test_features_exclude_frame_position(tmp_path: Path) -> None:
    add_session(tmp_path, "a_pushup")
    names = build_dataset(tmp_path, "pushup").feature_names()
    assert "bottom_frame" not in names  # phụ thuộc lúc bắt đầu quay, không phải tư thế
    assert {"min_elbow_angle", "median_elbow_angle", "top_elbow_angle", "duration_s"} <= set(names)


def test_invalid_reps_are_dropped(tmp_path: Path) -> None:
    def mark_second_invalid(reps):
        reps[1] = dataclasses.replace(reps[1], valid=False, errors=frozenset())
        return reps

    add_session(tmp_path, "a_pushup", edit=mark_second_invalid)
    ds = build_dataset(tmp_path, "pushup")
    assert [r.rep_index for r in ds.rows] == [0, 2]


def test_unlabeled_corrupt_and_misaligned_sessions_are_skipped_with_reason(
    tmp_path: Path,
) -> None:
    add_session(tmp_path, "ok_pushup")
    add_session(tmp_path, "unlabeled_pushup", label=False)
    (tmp_path / "sessions" / "pushup" / "broken_pushup.json").write_text("{", encoding="utf-8")

    def shift(reps):  # ranh giới lệch 1 s: như khi bộ đếm đổi sau lúc gán nhãn
        return [dataclasses.replace(r, start_s=r.start_s + 1.0, end_s=r.end_s + 1.0) for r in reps]

    add_session(tmp_path, "moved_pushup", edit=shift)

    ds = build_dataset(tmp_path, "pushup")
    assert {r.session_id for r in ds.rows} == {"ok_pushup"}
    reasons = dict(ds.skipped)
    assert reasons["unlabeled_pushup"] == "chưa gán nhãn"
    assert reasons["broken_pushup"].startswith("file hỏng")
    assert reasons["moved_pushup"].startswith("nhãn không khớp rep")


def test_empty_data_dir(tmp_path: Path) -> None:
    ds = build_dataset(tmp_path, "pushup")
    assert ds.rows == () and ds.skipped == ()


def test_csv_has_error_columns_and_blank_missing_features(tmp_path: Path) -> None:
    add_session(tmp_path, "a_pushup", set_errors=("hip_high", "shallow"))
    ds = build_dataset(tmp_path, "pushup")
    # Bỏ một đặc trưng ở rep đầu: ô đó phải để trống, không phải 0.
    first = dataclasses.replace(
        ds.rows[0], features={k: v for k, v in ds.rows[0].features.items() if k != "duration_s"}
    )
    ds = dataclasses.replace(ds, rows=(first, *ds.rows[1:]))
    path = write_csv(ds, tmp_path / "out" / "d.csv", {"pilot": ["0", "0", "1"]})

    with path.open(encoding="utf-8") as f:
        table = list(csv.DictReader(f))
    assert len(table) == 3
    assert [row["pilot"] for row in table] == ["0", "0", "1"]
    assert table[0]["duration_s"] == "" and table[1]["duration_s"] != ""
    assert table[0]["shallow"] == "1" and table[0]["hip_high"] == "1"
    assert table[0]["hip_sag"] == "0" and table[0]["neck_drop"] == "0"
    assert float(table[0]["min_elbow_angle"]) == pytest.approx(70.0, abs=0.5)


def test_sessions_from_other_pose_source_are_skipped(tmp_path: Path) -> None:
    # Chỉ dùng keypoint từ trang quay (MediaPipe JS); nguồn khác có thể lệch hệ thống.
    add_session(tmp_path, "js_pushup")
    add_session(tmp_path, "py_pushup", pose_source="mediapipe-python")
    ds = build_dataset(tmp_path, "pushup")
    assert {r.session_id for r in ds.rows} == {"js_pushup"}
    assert "không phải trang quay" in dict(ds.skipped)["py_pushup"]


def test_rows_remember_the_sessions_intended_errors(tmp_path: Path) -> None:
    # set_errors = lỗi cố ý chọn lúc quay; nhãn từng rep có thể khác (sửa lúc gán nhãn).
    def drop_labels(reps):
        return [dataclasses.replace(r, errors=frozenset()) for r in reps]

    add_session(tmp_path, "a_pushup", set_errors=("shallow",), edit=drop_labels)
    ds = build_dataset(tmp_path, "pushup")
    assert all(r.set_errors == frozenset({"shallow"}) for r in ds.rows)
    assert all(r.errors == frozenset() for r in ds.rows)


def test_session_counts_include_invalid_reps_and_skip_unlabeled(tmp_path: Path) -> None:
    def mark_last_invalid(reps):
        reps[-1] = dataclasses.replace(reps[-1], valid=False, errors=frozenset())
        return reps

    add_session(tmp_path, "a_pushup", edit=mark_last_invalid)
    add_session(tmp_path, "b_pushup")
    add_session(tmp_path, "c_pushup", label=False)  # chưa gán nhãn: không có thống kê
    ds = build_dataset(tmp_path, "pushup")
    counts = {s.session_id: (s.counted, s.valid, s.extra) for s in ds.sessions}
    assert counts == {"a_pushup": (3, 2, 1), "b_pushup": (3, 3, 0)}
    assert len(ds.rows) == 5  # rep không hợp lệ không vào bảng
