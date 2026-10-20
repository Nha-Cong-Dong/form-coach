import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

from formcoach.exercises import PushUp
from formcoach.labels import (
    LabelFormatError,
    RepLabel,
    check_alignment,
    default_labels,
    from_dict,
    labels_path,
    load_labels,
    save_labels,
    to_dict,
)
from formcoach.types import Rep

FPS = 30.0
TIMES = np.arange(600) / FPS  # 20 s


def reps(spans: list[tuple[int, int]]) -> list[Rep]:
    return [Rep(index=i, start_frame=s, end_frame=e, features={}) for i, (s, e) in enumerate(spans)]


SPANS = [(30, 75), (100, 145), (170, 215)]


def make_labels(set_errors=frozenset()):
    return default_labels(
        "2026-10-20T19-05-12_pushup",
        "pushup",
        reps(SPANS),
        TIMES,
        frozenset(set_errors),
        PushUp().phase_thresholds(),
    )


# --- nhãn mặc định ---


def test_default_labels_take_set_errors_and_boundaries() -> None:
    labels = make_labels({"shallow"})
    assert len(labels.reps) == 3
    for lab, (s, e) in zip(labels.reps, SPANS, strict=True):
        assert (lab.start_frame, lab.end_frame) == (s, e)
        # Thời gian được làm tròn tới mili giây khi lưu: dung sai 1 ms.
        assert lab.start_s == pytest.approx(s / FPS, abs=1e-3)
        assert lab.end_s == pytest.approx(e / FPS, abs=1e-3)
        assert lab.valid and lab.errors == frozenset({"shallow"})
    assert labels.segmenter_thresholds == PushUp().phase_thresholds()


def test_default_labels_good_set_is_empty() -> None:
    assert all(lab.errors == frozenset() for lab in make_labels().reps)


# --- lưu / đọc ---


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    labels = make_labels({"hip_sag"})
    edited = dataclasses.replace(
        labels,
        reps=(
            labels.reps[0],
            dataclasses.replace(
                labels.reps[1], errors=frozenset({"hip_sag", "shallow"}), note="mệt"
            ),
            dataclasses.replace(labels.reps[2], valid=False, errors=frozenset()),
        ),
    )
    path = save_labels(edited, tmp_path)
    assert path == tmp_path / "labels" / "pushup" / "2026-10-20T19-05-12_pushup.json"
    assert load_labels(tmp_path, "pushup", edited.session_id) == edited
    assert not list(path.parent.glob("*.tmp"))  # không để lại file tạm


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_labels(tmp_path, "pushup", "chua_co") is None


def test_saved_file_is_stable_json(tmp_path: Path) -> None:
    labels = make_labels({"shallow", "hip_sag"})
    data = json.loads(save_labels(labels, tmp_path).read_text(encoding="utf-8"))
    assert data["format_version"] == 1
    assert data["reps"][0]["errors"] == ["hip_sag", "shallow"]  # sắp xếp cố định


def test_save_overwrites_previous(tmp_path: Path) -> None:
    labels = make_labels()
    save_labels(labels, tmp_path)
    changed = dataclasses.replace(labels, reps=labels.reps[:2])
    save_labels(changed, tmp_path)
    assert len(load_labels(tmp_path, "pushup", labels.session_id).reps) == 2


# --- báo lỗi rõ ràng ---


def broken(**changes) -> dict:
    data = to_dict(make_labels())
    for key, value in changes.items():
        if value is ...:
            del data[key]
        else:
            data[key] = value
    return data


def rep_dict(i: int, s: int, e: int, **kw) -> dict:
    return {"rep_index": i, "start_frame": s, "end_frame": e, "start_s": s / FPS,
            "end_s": e / FPS, "valid": True, "errors": [], "note": ""} | kw  # fmt: skip


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (broken(format_version=2), "format_version"),
        (broken(reps=...), "thiếu"),
        (broken(session_id="../evil"), "session_id"),
        (broken(exercise="deadlift"), "không hỗ trợ"),
        (broken(reps=[rep_dict(0, 30, 75, errors=["good"])]), "không hợp lệ"),
        (broken(reps=[rep_dict(0, 75, 30)]), "start_frame < end_frame"),
        (broken(reps=[rep_dict(0, 30, 75), rep_dict(1, 60, 100)]), "chồng"),
        (broken(reps=[rep_dict(1, 30, 75)]), "rep_index"),
        (broken(reps=[rep_dict(0, 30, 75, valid=False, errors=["shallow"])]), "valid=false"),
        (broken(reps=[{"rep_index": 0}]), "thiếu"),
    ],
)
def test_invalid_labels(data: dict, message: str) -> None:
    with pytest.raises(LabelFormatError, match=message):
        from_dict(data)


def test_labels_path_blocks_traversal(tmp_path: Path) -> None:
    with pytest.raises(LabelFormatError):
        labels_path(tmp_path, "pushup", "../../etc/passwd")


def test_corrupt_file_reports_clearly(tmp_path: Path) -> None:
    path = labels_path(tmp_path, "pushup", "hong")
    path.parent.mkdir(parents=True)
    path.write_text("{ không phải json", encoding="utf-8")
    with pytest.raises(LabelFormatError, match="không phải JSON"):
        load_labels(tmp_path, "pushup", "hong")


# --- nhãn còn khớp với rep cắt lại không ---


def test_alignment_ok_when_reps_unchanged() -> None:
    assert check_alignment(make_labels(), reps(SPANS), TIMES) == []


def test_alignment_tolerates_small_shift() -> None:
    shifted = [(s + 3, e - 3) for s, e in SPANS]  # lệch 0,1 s < 0,2 s
    assert check_alignment(make_labels(), reps(shifted), TIMES) == []


def test_alignment_reports_moved_and_missing_reps() -> None:
    moved = [SPANS[0], (130, 175), SPANS[2]]  # rep 1 dời 1 s
    problems = check_alignment(make_labels(), reps(moved), TIMES)
    assert len(problems) == 1 and "rep 1" in problems[0]
    problems = check_alignment(make_labels(), reps(SPANS[:2]), TIMES)
    assert any("số rep khác" in p for p in problems)


def test_replace_keeps_type() -> None:
    # RepLabel bất biến (frozen): sửa nhãn bằng dataclasses.replace tạo bản mới.
    lab = make_labels().reps[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        lab.valid = False  # type: ignore[misc]
    assert isinstance(dataclasses.replace(lab, valid=False), RepLabel)
