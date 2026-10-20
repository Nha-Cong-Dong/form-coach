import dataclasses
import json

import numpy as np

from formcoach.exercises import PushUp
from formcoach.labels import default_labels
from formcoach.pose.session_json import parse_session
from formcoach.review import STICK_JOINTS, build_review
from formcoach.types import Rep
from tests.synthetic import three_rep_session


def test_review_without_saved_labels_uses_defaults() -> None:
    pose, meta = parse_session(three_rep_session(["shallow"]))
    review = build_review(pose, meta, PushUp(), saved=None)
    n = len(pose.keypoints)

    assert len(review["reps"]) == 3
    assert review["labels_saved"] is False
    assert review["alignment_problems"] == []
    assert [r["errors"] for r in review["labels"]["reps"]] == [["shallow"]] * 3
    assert len(review["times_s"]) == n and review["times_s"][0] == 0.0
    assert set(review["signals"]) == {
        "elbow_angle",
        "body_angle",
        "neck_angle",
        "body_tilt",
        "hip_offset",
    }
    assert all(len(v) == n for v in review["signals"].values())
    assert review["joints"] == STICK_JOINTS
    assert len(review["keypoints"]) == n and len(review["keypoints"][0]) == len(STICK_JOINTS)
    assert review["error_labels"] == PushUp.error_labels


def test_review_is_json_safe_with_missing_frames() -> None:
    data = three_rep_session()
    data["frames"][5]["kp"] = None  # khung không thấy người → NaN → phải thành null
    pose, meta = parse_session(data)
    review = build_review(pose, meta, PushUp(), saved=None)
    text = json.dumps(review, allow_nan=False)  # NaN lọt ra sẽ báo lỗi ở đây
    assert review["keypoints"][5] == [None] * len(STICK_JOINTS)
    assert "NaN" not in text


def test_review_reports_misaligned_saved_labels() -> None:
    pose, meta = parse_session(three_rep_session())
    review = build_review(pose, meta, PushUp(), saved=None)
    times = np.array(review["times_s"], dtype=float)
    fake = [Rep(index=0, start_frame=10, end_frame=40, features={})]  # chỉ 1 rep, sai chỗ
    saved = default_labels(meta.session_id, "pushup", fake, times, frozenset(), {})
    review = build_review(pose, meta, PushUp(), saved=saved)
    assert review["labels_saved"] is True
    assert review["alignment_problems"]  # báo nhãn không khớp
    assert len(review["labels"]["reps"]) == 1  # vẫn trả nhãn đã lưu để người dùng thấy


def test_review_keeps_saved_edits() -> None:
    pose, meta = parse_session(three_rep_session())
    first = build_review(pose, meta, PushUp(), saved=None)
    times = np.array(first["times_s"], dtype=float)
    reps = [Rep(r["index"], r["start_frame"], r["end_frame"], {}) for r in first["reps"]]
    labels = default_labels(meta.session_id, "pushup", reps, times, frozenset(), {})
    edited = dataclasses.replace(
        labels, reps=(dataclasses.replace(labels.reps[0], valid=False), *labels.reps[1:])
    )
    review = build_review(pose, meta, PushUp(), saved=edited)
    assert review["alignment_problems"] == []
    assert review["labels"]["reps"][0]["valid"] is False
