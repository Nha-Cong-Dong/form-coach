from formcoach.exercises import PushUp
from formcoach.pose.joints import MEDIAPIPE_JOINTS


def test_primary_signal_is_an_angle() -> None:
    ex = PushUp()
    assert ex.primary_signal() in ex.angle_definitions()


def test_all_joints_exist_in_mediapipe_on_both_sides() -> None:
    ex = PushUp()
    joints = {j for triple in ex.angle_definitions().values() for j in triple}
    joints |= {j for pair in ex.tilt_definitions().values() for j in pair}
    for j in joints:
        assert f"left_{j}" in MEDIAPIPE_JOINTS, j
        assert f"right_{j}" in MEDIAPIPE_JOINTS, j


def test_each_angle_uses_three_distinct_joints() -> None:
    for a, b, c in PushUp().angle_definitions().values():
        assert len({a, b, c}) == 3


def test_good_is_not_an_error_label() -> None:
    labels = PushUp.error_labels
    assert "good" not in labels
    assert len(set(labels)) == len(labels)


def test_amplitude_between_noise_and_real_reps() -> None:
    # Lớn hơn nhiễu (vài độ) nhưng nhỏ hơn biên độ rep nông nhất đo được (~60°).
    amp = PushUp().phase_thresholds()["min_amplitude_deg"]
    assert 15 < amp < 60


def test_top_tolerance_well_below_amplitude() -> None:
    # Ranh giới rep phải nằm gần đỉnh: dung sai lớn hơn nhiễu nhưng nhỏ hơn hẳn biên độ đếm.
    th = PushUp().phase_thresholds()
    assert 3 < th["top_tolerance_deg"] < th["min_amplitude_deg"] / 2


def test_required_phase_keys() -> None:
    th = PushUp().phase_thresholds()
    for key in (
        "top_min",
        "min_amplitude_deg",
        "top_tolerance_deg",
        "top_settle_s",
        "ready_hold_s",
        "ready_max_tilt_deg",
        "min_rep_duration_s",
        "smoothing_window_s",
        "max_gap_s",
        "min_joint_visibility",
    ):
        assert key in th, key


def test_time_thresholds_are_seconds() -> None:
    # Quy ước: ngưỡng thời gian có hậu tố _s và là số dương (giây, không phải số frame).
    th = PushUp().phase_thresholds()
    time_keys = [k for k in th if k.endswith("_s")]
    assert time_keys
    for k in time_keys:
        assert 0 < th[k] < 10, k


def test_ready_tilt_is_between_plank_and_standing() -> None:
    tilt = PushUp().phase_thresholds()["ready_max_tilt_deg"]
    assert 0 < tilt < 90
