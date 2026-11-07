"""format_version 2 (ARCHITECTURE §2b): keypoint int16 base64, cùng kết quả với v1."""

import base64

import numpy as np
import pytest

from formcoach.exercises import PushUp
from formcoach.pipeline import analyze
from formcoach.pose.session_json import (
    KP_LIMIT,
    KP_MISSING,
    SessionFormatError,
    encode_kp_i16,
    parse_session,
)
from tests.synthetic import make_session, three_rep_session, to_v2


def _kp_bytes(data: dict) -> np.ndarray:
    raw = base64.b64decode(data["kp_i16"])
    return np.frombuffer(raw, dtype="<i2").copy()


def _with_kp(data: dict, values: np.ndarray) -> dict:
    return {**data, "kp_i16": base64.b64encode(values.astype("<i2").tobytes()).decode()}


# --- v1 và v2 cùng một hiệp cho cùng kết quả ---


def test_v2_matches_v1() -> None:
    v1 = three_rep_session()
    pose1, meta1 = parse_session(v1)
    pose2, meta2 = parse_session(to_v2(v1))
    # v2 làm tròn 4 chữ số (như trang quay); sai số tối đa nửa đơn vị cuối.
    np.testing.assert_allclose(pose2.keypoints, pose1.keypoints, atol=0.5e-4 + 1e-12)
    np.testing.assert_array_equal(meta2.timestamps_ms, meta1.timestamps_ms)
    assert pose2.fps == pose1.fps and pose2.frame_size == pose1.frame_size
    # SessionMeta chứa mảng numpy nên không so bằng ==; so từng trường còn lại.
    for name in ("session_id", "exercise", "set_errors", "recorded_at", "source", "notes"):
        assert getattr(meta2, name) == getattr(meta1, name)
    assert meta2.capture_mode == meta1.capture_mode


def test_v2_same_reps_as_v1() -> None:
    v1 = three_rep_session()
    _, reps1 = analyze(parse_session(v1)[0], PushUp())
    _, reps2 = analyze(parse_session(to_v2(v1))[0], PushUp())
    assert len(reps1) == len(reps2) == 3
    assert [(r.start_frame, r.end_frame) for r in reps1] == [
        (r.start_frame, r.end_frame) for r in reps2
    ]


def test_exact_roundtrip_of_4_digit_values() -> None:
    """Giá trị đã làm tròn 4 chữ số (như web gửi) đi qua v2 không đổi."""
    rng = np.random.default_rng(0)
    kp = np.round(rng.uniform(-0.5, 1.5, (10, 33, 3)), 4)
    data = make_session()
    data.update(format_version=2, t_ms=[i * 33.3 for i in range(10)], kp_i16=encode_kp_i16(kp))
    del data["frames"]
    pose, _ = parse_session(data)
    np.testing.assert_allclose(pose.keypoints, kp, atol=1e-12)


def test_null_frame_is_nan_row() -> None:
    v1 = make_session()
    v1["frames"][5]["kp"] = None
    data = to_v2(v1)
    assert (_kp_bytes(data).reshape(60, 33, 3)[5] == KP_MISSING).all()
    pose, _ = parse_session(data)
    assert np.isnan(pose.keypoints[5]).all()
    assert np.isfinite(pose.keypoints[4]).all() and np.isfinite(pose.keypoints[6]).all()


def test_out_of_frame_coordinates_kept_and_clipped() -> None:
    """Toạ độ âm / > 1 (khớp ra ngoài khung) giữ nguyên; quá ±KP_LIMIT thì kẹp."""
    kp = np.full((2, 33, 3), 0.5)
    kp[0, 0] = [-0.25, 1.75, 0.9]
    kp[1, 0] = [-9.0, 9.0, 0.9]
    out = np.frombuffer(base64.b64decode(encode_kp_i16(kp)), dtype="<i2").reshape(2, 33, 3)
    assert out[0, 0].tolist() == [-2500, 17500, 9000]
    assert out[1, 0, 0] / 10_000 == pytest.approx(-KP_LIMIT)
    assert out[1, 0, 1] / 10_000 == pytest.approx(KP_LIMIT)
    assert KP_MISSING not in out  # kẹp không đụng giá trị đánh dấu "không thấy người"


def test_encode_rejects_partial_nan_and_bad_shape() -> None:
    kp = np.full((2, 33, 3), 0.5)
    kp[0, 3, 1] = np.nan
    with pytest.raises(ValueError, match="toàn NaN"):
        encode_kp_i16(kp)
    with pytest.raises(ValueError, match="dạng"):
        encode_kp_i16(np.zeros((2, 32, 3)))


# --- báo lỗi rõ ràng ---


def test_v2_missing_fields() -> None:
    data = to_v2(make_session())
    del data["kp_i16"]
    with pytest.raises(SessionFormatError, match="thiếu trường: kp_i16"):
        parse_session(data)


def test_v1_fields_not_enough_for_v2() -> None:
    data = make_session()
    data["format_version"] = 2
    with pytest.raises(SessionFormatError, match="thiếu trường: t_ms, kp_i16"):
        parse_session(data)


@pytest.mark.parametrize(
    ("t_ms", "message"),
    [
        ([0.0], "ít nhất 2 khung"),
        ("0,33", "ít nhất 2 khung"),
        ([0.0, 33.0, -1.0], "khung 2: 't_ms' phải là số không âm"),
        ([0.0, True], "khung 1"),
        ([0.0, 33.0, 33.0], "khung 2: 't_ms' phải tăng ngặt"),
    ],
)
def test_v2_bad_t_ms(t_ms, message: str) -> None:
    data = to_v2(make_session())
    data["t_ms"] = t_ms
    with pytest.raises(SessionFormatError, match=message):
        parse_session(data)


def test_v2_bad_base64() -> None:
    data = to_v2(make_session())
    for bad in (123, "không phải base64!", data["kp_i16"][:-4] + "@@@@"):
        with pytest.raises(SessionFormatError, match="kp_i16"):
            parse_session({**data, "kp_i16": bad})


def test_v2_length_mismatch() -> None:
    data = to_v2(make_session())
    data["t_ms"] = data["t_ms"][:-1]  # 59 khung nhưng kp có 60
    with pytest.raises(SessionFormatError, match="cần 11682"):
        parse_session(data)


def test_v2_partial_missing_rejected() -> None:
    data = to_v2(make_session())
    values = _kp_bytes(data).reshape(60, 33, 3)
    values[7, 2, 0] = KP_MISSING
    with pytest.raises(SessionFormatError, match="khung 7"):
        parse_session(_with_kp(data, values))


# --- cắt bớt khung (server lưu phần đầu hiệp dài) ---


@pytest.mark.parametrize("version", [1, 2])
def test_truncate_keeps_first_frames(version: int) -> None:
    from formcoach.pose.session_json import truncate_session

    full = three_rep_session()
    if version == 2:
        full = to_v2(full)
    pose_full, meta_full = parse_session(full)
    cut = truncate_session(full, 25)
    pose_cut, meta_cut = parse_session(cut)
    assert cut["format_version"] == version
    np.testing.assert_array_equal(pose_cut.keypoints, pose_full.keypoints[:25])
    np.testing.assert_array_equal(meta_cut.timestamps_ms, meta_full.timestamps_ms[:25])
    # Không sửa file gốc.
    assert parse_session(full)[0].keypoints.shape[0] == pose_full.keypoints.shape[0]
    with pytest.raises(ValueError, match="ít nhất 2"):
        truncate_session(full, 1)
