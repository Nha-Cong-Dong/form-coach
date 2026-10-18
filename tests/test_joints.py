from formcoach.pose.joints import MEDIAPIPE_JOINTS


def test_has_33_unique_joints() -> None:
    assert len(MEDIAPIPE_JOINTS) == 33
    assert len(set(MEDIAPIPE_JOINTS)) == 33


def test_known_indices() -> None:
    # Đối chiếu vài index với enum PoseLandmark của mediapipe 1.1.1.
    assert MEDIAPIPE_JOINTS[0] == "nose"
    assert MEDIAPIPE_JOINTS[11] == "left_shoulder"
    assert MEDIAPIPE_JOINTS[14] == "right_elbow"
    assert MEDIAPIPE_JOINTS[23] == "left_hip"
    assert MEDIAPIPE_JOINTS[28] == "right_ankle"
    assert MEDIAPIPE_JOINTS[32] == "right_foot_index"


def test_body_joints_exist_on_both_sides() -> None:
    for base in ("ear", "shoulder", "elbow", "wrist", "hip", "knee", "ankle"):
        assert f"left_{base}" in MEDIAPIPE_JOINTS
        assert f"right_{base}" in MEDIAPIPE_JOINTS
