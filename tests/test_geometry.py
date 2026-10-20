import numpy as np
import pytest

from formcoach.features.geometry import joint_angle, segment_tilt, signed_offset, to_pixel_space


def angle(a, b, c) -> float:
    return float(joint_angle(np.array(a), np.array(b), np.array(c)))


# --- joint_angle: đáp án biết trước ---


@pytest.mark.parametrize(
    ("a", "b", "c", "expected"),
    [
        ((1, 0), (0, 0), (0, 1), 90.0),  # vuông góc
        ((-1, 0), (0, 0), (1, 0), 180.0),  # thẳng hàng, b ở giữa
        ((1, 0), (0, 0), (2, 0), 0.0),  # gập hết: a và c cùng phía
        ((1, 0), (0, 0), (1, np.sqrt(3)), 60.0),  # tam giác 30-60-90
        ((np.sqrt(3), 0), (0, 0), (np.sqrt(3), 1), 30.0),
    ],
)
def test_known_angles(a, b, c, expected) -> None:
    assert angle(a, b, c) == pytest.approx(expected, abs=1e-6)


def test_vectorized_over_frames() -> None:
    # T khung, mỗi khung một góc khác nhau: c quay quanh b.
    expected = np.array([10.0, 45.0, 90.0, 135.0, 170.0])
    rad = np.radians(expected)
    b = np.zeros((5, 2))
    a = np.tile([1.0, 0.0], (5, 1))
    c = np.stack([np.cos(rad), np.sin(rad)], axis=1)
    result = joint_angle(a, b, c)
    assert result.shape == (5,)
    np.testing.assert_allclose(result, expected, atol=1e-6)


def test_collinear_rounding_does_not_give_nan() -> None:
    # Bộ điểm thẳng hàng này cho cos = 1.0000000000000002 do làm tròn số thực
    # (tìm bằng cách thử ngẫu nhiên). Không clip thì arccos trả NaN.
    a = np.array([2.739233746429086, -4.604265724722594])
    b = np.array([0.0, 0.0])
    c = np.array([1.3850603634567384, -2.328091192089427])
    ba, bc = a - b, c - b
    assert np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc)) > 1.0  # tiền đề của test
    assert joint_angle(a, b, c) == pytest.approx(0.0, abs=1e-6)


def test_zero_length_segment_gives_nan() -> None:
    assert np.isnan(angle((0, 0), (0, 0), (1, 1)))


def test_nan_input_gives_nan_without_affecting_other_frames() -> None:
    a = np.array([[1.0, 0.0], [np.nan, np.nan]])
    b = np.zeros((2, 2))
    c = np.array([[0.0, 1.0], [0.0, 1.0]])
    result = joint_angle(a, b, c)
    assert result[0] == pytest.approx(90.0)
    assert np.isnan(result[1])


def test_invariant_to_translation_and_scale() -> None:
    a, b, c = np.array([3.0, 1.0]), np.array([1.0, 2.0]), np.array([4.0, 5.0])
    base = joint_angle(a, b, c)
    shift, k = np.array([100.0, -50.0]), 7.5
    assert joint_angle(a * k + shift, b * k + shift, c * k + shift) == pytest.approx(base)


# --- to_pixel_space: vì sao bắt buộc ---


def test_normalized_coords_distort_angle_on_non_square_frame() -> None:
    # Góc 90° thật trên khung 1280x720 (tính bằng pixel), cạnh nằm chéo.
    size = (1280, 720)
    b_px = np.array([400.0, 400.0])
    a_px = b_px + [300.0, 300.0]
    c_px = b_px + [300.0, -300.0]
    assert float(joint_angle(a_px, b_px, c_px)) == pytest.approx(90.0)

    scale = np.array(size, dtype=float)
    a, b, c = a_px / scale, b_px / scale, c_px / scale  # như MediaPipe trả về
    wrong = float(joint_angle(a, b, c))
    assert abs(wrong - 90.0) > 20  # tính thẳng trên toạ độ 0–1: méo rõ rệt

    fixed = joint_angle(to_pixel_space(a, size), to_pixel_space(b, size), to_pixel_space(c, size))
    assert float(fixed) == pytest.approx(90.0)


def test_to_pixel_space_keeps_shape_and_nan() -> None:
    xy = np.array([[[0.5, 0.5], [np.nan, np.nan]]])  # (1, 2, 2)
    out = to_pixel_space(xy, (1920, 1080))
    assert out.shape == xy.shape
    np.testing.assert_allclose(out[0, 0], [960.0, 540.0])
    assert np.isnan(out[0, 1]).all()


# --- segment_tilt ---


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ((0, 0), (10, 0), 0.0),  # nằm ngang
        ((0, 0), (0, 10), 90.0),  # dựng đứng
        ((0, 0), (5, 5), 45.0),
        ((0, 0), (10, -2), np.degrees(np.arctan(0.2))),  # y âm (lên trên trong ảnh)
    ],
)
def test_known_tilts(a, b, expected) -> None:
    assert float(segment_tilt(np.array(a), np.array(b))) == pytest.approx(expected)


def test_tilt_independent_of_direction() -> None:
    a, b = np.array([1.0, 2.0]), np.array([7.0, 5.0])
    assert segment_tilt(a, b) == pytest.approx(segment_tilt(b, a))


def test_tilt_zero_length_and_nan() -> None:
    assert np.isnan(segment_tilt(np.array([1.0, 1.0]), np.array([1.0, 1.0])))
    assert np.isnan(segment_tilt(np.array([np.nan, 0.0]), np.array([1.0, 1.0])))


def test_tilt_vectorized() -> None:
    a = np.zeros((3, 2))
    b = np.array([[10.0, 0.0], [0.0, 10.0], [5.0, 5.0]])
    np.testing.assert_allclose(segment_tilt(a, b), [0.0, 90.0, 45.0])


# --- signed_offset: hông so với đường vai–cổ chân (y ảnh hướng xuống) ---

SHOULDER, ANKLE = np.array([0.0, 100.0]), np.array([200.0, 100.0])


@pytest.mark.parametrize(
    ("hip", "expected"),
    [
        ((100.0, 80.0), 0.1),  # cao hơn đường 20 px / dài 200 px → nhô
        ((100.0, 130.0), -0.15),  # thấp hơn đường → võng
        ((100.0, 100.0), 0.0),  # nằm trên đường
        ((40.0, 80.0), 0.1),  # không phụ thuộc vị trí dọc theo đường
    ],
)
def test_known_offsets(hip, expected) -> None:
    assert float(signed_offset(np.array(hip), SHOULDER, ANKLE)) == pytest.approx(expected)


def test_offset_independent_of_line_direction() -> None:
    hip = np.array([100.0, 80.0])
    assert signed_offset(hip, SHOULDER, ANKLE) == pytest.approx(signed_offset(hip, ANKLE, SHOULDER))


def test_offset_unchanged_by_horizontal_flip() -> None:
    # Camera trước lật ảnh trái–phải: người quay đầu sang phía kia, dấu phải giữ nguyên.
    def flip(v: np.ndarray) -> np.ndarray:
        return np.array([1000.0 - v[0], v[1]])

    hip = np.array([100.0, 80.0])
    assert signed_offset(flip(hip), flip(SHOULDER), flip(ANKLE)) == pytest.approx(0.1)


def test_offset_invariant_to_scale_and_translation() -> None:
    hip = np.array([100.0, 130.0])
    moved = [3.0 * v + np.array([50.0, -20.0]) for v in (hip, SHOULDER, ANKLE)]
    assert signed_offset(*moved) == pytest.approx(signed_offset(hip, SHOULDER, ANKLE))


def test_offset_on_tilted_body() -> None:
    # Thân nghiêng 30° (đầu cao hơn chân như push-up thật); hông lệch vuông góc 0,1 về phía trên.
    u = np.array([np.cos(np.radians(30)), np.sin(np.radians(30))])  # vai → cổ chân, đi xuống
    normal_up = np.array([u[1], -u[0]])  # vuông góc, hướng lên trên ảnh (y âm)
    shoulder, ankle = np.array([0.0, 0.0]), 200.0 * u
    hip = 100.0 * u + 20.0 * normal_up
    assert float(signed_offset(hip, shoulder, ankle)) == pytest.approx(0.1)


def test_offset_zero_length_and_nan() -> None:
    assert np.isnan(signed_offset(np.array([1.0, 1.0]), SHOULDER, SHOULDER))
    assert np.isnan(signed_offset(np.array([np.nan, 0.0]), SHOULDER, ANKLE))


def test_offset_vectorized() -> None:
    hips = np.array([[100.0, 80.0], [100.0, 100.0], [100.0, 130.0]])
    np.testing.assert_allclose(signed_offset(hips, SHOULDER, ANKLE), [0.1, 0.0, -0.15])
